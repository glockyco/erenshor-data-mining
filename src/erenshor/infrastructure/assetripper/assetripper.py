"""AssetRipper wrapper for extracting Unity assets from game files.

This module provides a Python wrapper around the AssetRipper tool, enabling
programmatic extraction of Unity assets from compiled game files into an
editable Unity project structure.

Features:
- Extract game assets to Unity project directories
- Web API-based control (HTTP server mode)
- Server lifecycle management (start/stop)
- Export progress monitoring
- Proper error handling and logging

The AssetRipper class wraps the AssetRipper CLI and provides type-safe, testable
interfaces for extracting game assets. It's designed to work with the
multi-variant system (main/playtest/demo).
"""

import subprocess
from pathlib import Path

import httpx
from loguru import logger

from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.time import Clock, RealClock

_STOP_GRACE_SECONDS = 10
_API_TIMEOUT_SECONDS = 30
# The export request blocks until the export finishes. The wrapper stops
# waiting for the response after this long and follows the log instead.
_EXPORT_REQUEST_SECONDS = 10


class AssetRipperError(Exception):
    """Base exception for AssetRipper-related errors.

    This is the parent exception for all AssetRipper-specific errors.
    Catch this to handle all AssetRipper failures.
    """

    pass


class AssetRipperNotFoundError(AssetRipperError):
    """Raised when AssetRipper executable is not found on the system.

    This typically means AssetRipper is not installed or the configured path is incorrect.
    Download from: https://github.com/AssetRipper/AssetRipper/releases
    """

    pass


class AssetRipperServerError(AssetRipperError):
    """Raised when AssetRipper server fails to start or respond.

    This can occur due to:
    - Port already in use
    - Permission errors
    - AssetRipper binary is corrupted
    - Server startup timeout
    """

    pass


class AssetRipperExportError(AssetRipperError):
    """Raised when asset extraction/export fails.

    This can occur due to:
    - Invalid input files
    - Insufficient disk space
    - Permission errors
    - Export timeout
    - AssetRipper processing failure
    """

    pass


class AssetRipper:
    """Wrapper for AssetRipper extraction tool.

    This class provides a Python interface to AssetRipper for extracting
    Unity assets from game files. It manages the AssetRipper server lifecycle
    and provides methods for loading and exporting assets.

    Attributes:
        executable_path: Path to AssetRipper executable.
        port: Port for AssetRipper web API server.
        timeout: Maximum time to wait for export operations (seconds).

    Example:
        >>> # Extract game assets to Unity project
        >>> assetripper = AssetRipper(
        ...     executable_path=Path("/path/to/AssetRipper.GUI.Free"),
        ...     port=8080,
        ...     timeout=3600
        ... )
        >>> assetripper.extract(
        ...     source_dir=Path("variants/main/game/Erenshor_Data"),
        ...     target_dir=Path("variants/main/unity"),
        ...     log_dir=Path("variants/main/logs")
        ... )
    """

    def __init__(
        self,
        executable_path: Path,
        port: int = 8080,
        timeout: int = 3600,
        clock: Clock | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialize AssetRipper wrapper.

        Args:
            executable_path: Path to AssetRipper executable (required).
            port: Port for AssetRipper web API server (default: 8080).
            timeout: Maximum time to wait for export operations in seconds (default: 3600).
            clock: Clock implementation for time operations (default: RealClock()).
            transport: HTTP transport for the AssetRipper API (default: real network).

        Raises:
            AssetRipperNotFoundError: If AssetRipper executable is not found.
        """
        self.executable_path = executable_path
        self.port = port
        self.timeout = timeout
        self.clock = clock if clock is not None else RealClock()
        self._transport = transport
        self._process: subprocess.Popen[bytes] | None = None
        self._log_file: Path | None = None

        # Verify AssetRipper exists and is executable
        if not self.executable_path.exists():
            raise AssetRipperNotFoundError(
                f"AssetRipper executable not found at: {self.executable_path}\n"
                "Configure path in .erenshor/config.local.toml:\n"
                "[global.assetripper]\n"
                'path = "/path/to/AssetRipper.GUI.Free"\n'
                "Download from: https://github.com/AssetRipper/AssetRipper/releases"
            )

        if not self.executable_path.is_file():
            raise AssetRipperNotFoundError(
                f"AssetRipper path is not a file: {self.executable_path}\n"
                "Configure correct path in .erenshor/config.local.toml"
            )

        logger.debug(f"AssetRipper initialized: executable={self.executable_path}, port={port}, timeout={timeout}s")

    def _get_base_url(self) -> str:
        """Get AssetRipper web API base URL.

        Returns:
            Base URL for AssetRipper HTTP API.
        """
        return f"http://localhost:{self.port}"

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        timeout: float | None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        with httpx.Client(base_url=self._get_base_url(), transport=self._transport, timeout=timeout) as client:
            return client.request(method, endpoint, params=params, data=data)

    def _api(
        self,
        method: str,
        endpoint: str,
        *,
        timeout: float | None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Call the AssetRipper API, naming the request when it cannot complete."""
        try:
            return self._request(method, endpoint, timeout=timeout, params=params, data=data)
        except httpx.TransportError as error:
            raise AssetRipperServerError(f"AssetRipper API request {method} {endpoint} failed: {error}") from error

    def _check_server_running(self) -> bool:
        """Check if AssetRipper server is running and responding.

        Returns:
            True if server is responding, False otherwise.
        """
        try:
            return self._request("GET", "/", timeout=5).is_success
        except httpx.TransportError:
            return False

    def launch_command(self) -> list[str]:
        """Build the argv that starts the AssetRipper web server.

        `--headless` keeps AssetRipper from opening a browser window, which is
        what makes the GUI build usable as a headless HTTP API.

        Returns:
            Executable and arguments for the server process.
        """
        return [
            str(self.executable_path),
            "--port",
            str(self.port),
            "--headless",
        ]

    def start_server(self, log_dir: Path) -> None:
        """Start AssetRipper web API server.

        Args:
            log_dir: Directory for log files (required).

        Raises:
            AssetRipperServerError: If server fails to start.
            ValueError: If log_dir is not provided.
        """
        if self._process is not None:
            logger.debug(f"Server already running (PID: {self._process.pid})")
            return

        logger.info(f"Starting AssetRipper server on port {self.port}...")

        # Create log directory and file
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = log_dir / f"assetripper_{int(self.clock.time())}.log"

        # Start server in background
        try:
            with self._log_file.open("w") as log_file:
                process = subprocess.Popen(
                    self.launch_command(),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                self._process = process
        except Exception as e:
            raise AssetRipperServerError(f"Failed to start AssetRipper server: {e}") from e

        # Wait for server to start (up to 30 seconds)
        startup_timeout = 30
        wait_time = 0

        while wait_time < startup_timeout:
            if self._check_server_running():
                logger.info(f"Server started successfully (PID: {process.pid})")
                logger.debug(f"Server log: {self._log_file}")
                return

            exit_code = process.poll()
            if exit_code is not None:
                self._process = None
                raise AssetRipperServerError(
                    f"AssetRipper exited with code {exit_code} before its server answered.\n"
                    f"Check log file: {self._log_file}"
                )

            self.clock.sleep(1)
            wait_time += 1

        # Server failed to start within timeout
        self.stop_server()
        raise AssetRipperServerError(
            f"Server failed to start within {startup_timeout} seconds.\nCheck log file: {self._log_file}"
        )

    def stop_server(self) -> None:
        """Stop the AssetRipper web API server and reap its process.

        Sends SIGTERM first. Sends SIGKILL only when the process is still
        alive after the grace period.
        """
        if self._process is None:
            logger.debug("No server to stop")
            return

        process, self._process = self._process, None
        logger.info("Stopping AssetRipper server...")
        process.terminate()
        try:
            process.wait(timeout=_STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            logger.warning(f"AssetRipper did not exit within {_STOP_GRACE_SECONDS}s after SIGTERM; killing it")
            process.kill()
            process.wait()

    def _load_files(self, source_dir: Path) -> None:
        """Load game files into AssetRipper.

        Args:
            source_dir: Directory containing game files to load.

        Raises:
            AssetRipperExportError: If loading files fails.
        """
        logger.info(f"Loading files from: {source_dir}")
        source = str(source_dir.absolute())

        exists = self._api("GET", "/IO/Directory/Exists", params={"Path": source}, timeout=_API_TIMEOUT_SECONDS)
        if exists.text.strip().lower() != "true":
            raise AssetRipperExportError(f"Source directory does not exist: {source_dir}")

        # LoadFolder answers only after loading finishes, with a redirect on success.
        response = self._api("POST", "/LoadFolder", data={"path": source}, timeout=None)
        if response.status_code != 302:
            raise AssetRipperExportError(f"Failed to load files. HTTP status: {response.status_code}")

        logger.info("Files loaded successfully. Processing...")
        self.clock.sleep(5)  # Wait for initial processing

    def _export_files(self, target_dir: Path) -> None:
        """Export loaded files to Unity project.

        Args:
            target_dir: Target directory for Unity project export.

        Raises:
            AssetRipperExportError: If export fails.
        """
        logger.info(f"Starting export to: {target_dir}")

        # Create target directory if needed
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            response = self._request(
                "POST",
                "/Export/UnityProject",
                data={"path": str(target_dir.absolute())},
                timeout=_EXPORT_REQUEST_SECONDS,
            )
        except httpx.ReadTimeout:
            # A large export outlives the request. AssetRipper keeps exporting,
            # and _monitor_export follows its log until it reports completion.
            logger.info("Export started")
            return
        except httpx.TransportError as error:
            raise AssetRipperServerError(f"AssetRipper export request failed: {error}") from error

        if response.status_code != 302:
            raise AssetRipperExportError(f"Failed to start export. HTTP status: {response.status_code}")
        logger.info("Export finished before the request returned")

    def _monitor_export(self) -> None:
        """Monitor export progress by watching log file.

        Raises:
            AssetRipperExportError: If export times out or fails.
        """
        if self._log_file is None or not self._log_file.is_file():
            raise AssetRipperExportError(
                f"AssetRipper log file is missing, so the export cannot be followed: {self._log_file}"
            )

        logger.info(f"Monitoring export progress (timeout: {self.timeout}s)...")
        logger.info("This may take 15-20 minutes. Progress updates every 30 seconds...")

        poll_interval = 5
        wait_time = 0

        while wait_time < self.timeout:
            self.clock.sleep(poll_interval)
            wait_time += poll_interval

            # Show progress periodically
            if wait_time % 30 == 0:
                logger.info(f"Still exporting... ({wait_time}s elapsed)")

            # Check log for completion indicators
            # Only read the last 10KB of the log file to avoid blocking on huge files
            try:
                with self._log_file.open("rb") as f:
                    # Seek to last 10KB (or start of file if smaller)
                    f.seek(0, 2)  # Seek to end
                    file_size = f.tell()
                    read_size = min(10240, file_size)  # Read last 10KB max
                    f.seek(max(0, file_size - read_size))
                    log_tail = f.read().decode("utf-8", errors="ignore")
            except OSError as error:
                raise AssetRipperExportError(f"Cannot read AssetRipper log {self._log_file}: {error}") from error

            # AssetRipper outputs these messages when export completes
            if "Finished post-export" in log_tail or "Finished exporting assets" in log_tail:
                logger.info("Export completed successfully!")
                return

            exit_code = self._process.poll() if self._process is not None else None
            if exit_code is not None:
                raise AssetRipperExportError(
                    f"AssetRipper exited with code {exit_code} before finishing the export.\n"
                    f"Check log: {self._log_file}"
                )
        raise AssetRipperExportError(
            f"Export monitoring timed out after {self.timeout} seconds.\n"
            f"Export may still be running. Check log: {self._log_file}"
        )

    def extract(
        self,
        source_dir: Path,
        target_dir: Path,
        log_dir: Path,
        profile: ExportProfileRecorder | None = None,
    ) -> None:
        """Extract game assets to Unity project.

        This is the main entry point for asset extraction. It starts the AssetRipper
        server, loads game files, exports to Unity project format, and monitors progress.

        Args:
            source_dir: Directory containing game data files (e.g., Erenshor_Data).
            target_dir: Target directory for Unity project (will be created if needed).
            log_dir: Directory for AssetRipper logs (required).

        Raises:
            AssetRipperNotFoundError: If source directory doesn't exist.
            AssetRipperServerError: If server fails to start.
            AssetRipperExportError: If extraction fails or times out.
            ValueError: If log_dir is not provided.

        Example:
            >>> assetripper = AssetRipper()
            >>> assetripper.extract(
            ...     source_dir=Path("variants/main/game/Erenshor_Data"),
            ...     target_dir=Path("variants/main/unity"),
            ...     log_dir=Path("variants/main/logs")
            ... )
        """
        logger.info("Starting asset extraction...")
        logger.debug(f"Source: {source_dir}")
        logger.debug(f"Target: {target_dir}")

        # Validate source directory
        if not source_dir.exists():
            raise AssetRipperNotFoundError(f"Source directory does not exist: {source_dir}")

        # Ensure we clean up server on any exit
        try:
            if profile is None:
                self.start_server(log_dir=log_dir)
                self._load_files(source_dir)
                self._export_files(target_dir)
                self._monitor_export()
            else:
                with profile.span("assetripper.start_server", category="assetripper"):
                    self.start_server(log_dir=log_dir)
                with profile.span("assetripper.load_files", category="assetripper"):
                    self._load_files(source_dir)
                with profile.span("assetripper.export_start", category="assetripper"):
                    self._export_files(target_dir)
                with profile.span("assetripper.monitor_export", category="assetripper"):
                    self._monitor_export()

            logger.info("Asset extraction complete!")
            logger.info(f"Unity project ready at: {target_dir}")
            if self._log_file:
                logger.info(f"Log file: {self._log_file}")

        finally:
            if profile is None:
                self.stop_server()
            else:
                with profile.span("assetripper.stop_server", category="assetripper"):
                    self.stop_server()

    def is_installed(self) -> bool:
        """Check if AssetRipper is properly installed and accessible.

        Returns:
            True if AssetRipper executable exists and is executable, False otherwise.
        """
        return self.executable_path.exists() and self.executable_path.is_file()

    def get_version(self) -> str | None:
        """Get AssetRipper version if available.

        Returns:
            Version string if available, None otherwise.

        Note:
            This is a best-effort attempt. AssetRipper may not have a --version flag.
        """
        try:
            result = subprocess.run(
                [str(self.executable_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except Exception:
            pass

        return None
