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

from loguru import logger

from erenshor.infrastructure.time import Clock, RealClock


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
    ) -> None:
        """Initialize AssetRipper wrapper.

        Args:
            executable_path: Path to AssetRipper executable (required).
            port: Port for AssetRipper web API server (default: 8080).
            timeout: Maximum time to wait for export operations in seconds (default: 3600).
            clock: Clock implementation for time operations (default: RealClock()).

        Raises:
            AssetRipperNotFoundError: If AssetRipper executable is not found.
        """
        self.executable_path = executable_path
        self.port = port
        self.timeout = timeout
        self.clock = clock if clock is not None else RealClock()
        self._server_pid: int | None = None
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

    def _check_server_running(self) -> bool:
        """Check if AssetRipper server is running and responding.

        Returns:
            True if server is responding, False otherwise.
        """
        try:
            # Use curl to check if server responds (avoid adding requests dependency)
            result = subprocess.run(
                ["curl", "-s", "-f", f"{self._get_base_url()}/"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def start_server(self, log_dir: Path) -> None:
        """Start AssetRipper web API server.

        Args:
            log_dir: Directory for log files (required).

        Raises:
            AssetRipperServerError: If server fails to start.
            ValueError: If log_dir is not provided.
        """
        if self._server_pid is not None:
            logger.debug(f"Server already running (PID: {self._server_pid})")
            return

        logger.info(f"Starting AssetRipper server on port {self.port}...")

        # Create log directory and file
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = log_dir / f"assetripper_{int(self.clock.time())}.log"

        # Start server in background
        try:
            with self._log_file.open("w") as log_file:
                process = subprocess.Popen(
                    [
                        str(self.executable_path),
                        "--port",
                        str(self.port),
                        "--launch-browser=false",
                    ],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                self._server_pid = process.pid
        except Exception as e:
            raise AssetRipperServerError(f"Failed to start AssetRipper server: {e}") from e

        # Wait for server to start (up to 30 seconds)
        startup_timeout = 30
        wait_time = 0

        while wait_time < startup_timeout:
            if self._check_server_running():
                logger.info(f"Server started successfully (PID: {self._server_pid})")
                logger.debug(f"Server log: {self._log_file}")
                return

            self.clock.sleep(1)
            wait_time += 1

        # Server failed to start within timeout
        self.stop_server()
        raise AssetRipperServerError(
            f"Server failed to start within {startup_timeout} seconds.\nCheck log file: {self._log_file}"
        )

    def stop_server(self) -> None:
        """Stop AssetRipper web API server."""
        if self._server_pid is None:
            logger.debug("No server to stop")
            return

        logger.info("Stopping AssetRipper server...")

        try:
            # Try graceful termination first
            subprocess.run(["kill", str(self._server_pid)], check=False)

            # Wait briefly for graceful shutdown
            self.clock.sleep(2)

            # Force kill if still running
            subprocess.run(["kill", "-9", str(self._server_pid)], check=False)

        except Exception as e:
            logger.warning(f"Error stopping server: {e}")

        finally:
            self._server_pid = None

    def _url_encode(self, path: str) -> str:
        """URL encode a path for API requests.

        Args:
            path: Path to encode.

        Returns:
            URL-encoded path.
        """
        # Simple URL encoding for paths (avoid adding urllib dependency)
        # This is sufficient for file paths
        import urllib.parse

        return urllib.parse.quote(path, safe="")

    def _api_post(self, endpoint: str, data: dict[str, str], timeout: int | None = None) -> tuple[str, int]:
        """Make POST request to AssetRipper API.

        Args:
            endpoint: API endpoint (e.g., "/LoadFolder").
            data: Form data to post.
            timeout: Request timeout in seconds (None = no timeout).

        Returns:
            Tuple of (response body, HTTP status code).

        Raises:
            AssetRipperServerError: If API request fails.
        """
        url = f"{self._get_base_url()}{endpoint}"

        # Build curl command
        cmd = ["curl", "-s", "-w", "\\n%{http_code}", "-X", "POST", url]
        cmd.extend(["-H", "Content-Type: application/x-www-form-urlencoded"])

        # Add timeout if specified
        if timeout:
            cmd.extend(["--max-time", str(timeout)])

        # Add form data
        for key, value in data.items():
            cmd.extend(["--data-urlencode", f"{key}={value}"])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            lines = result.stdout.rsplit("\n", 1)
            body = lines[0] if len(lines) > 1 else ""
            status_code = int(lines[-1]) if lines[-1].isdigit() else 0

            return body, status_code

        except Exception as e:
            raise AssetRipperServerError(f"API request failed: {e}") from e

    def _api_get(self, endpoint: str) -> str:
        """Make GET request to AssetRipper API.

        Args:
            endpoint: API endpoint with query params.

        Returns:
            Response body.

        Raises:
            AssetRipperServerError: If API request fails.
        """
        url = f"{self._get_base_url()}{endpoint}"

        try:
            result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, check=False)
            return result.stdout

        except Exception as e:
            raise AssetRipperServerError(f"API request failed: {e}") from e

    def _load_files(self, source_dir: Path) -> None:
        """Load game files into AssetRipper.

        Args:
            source_dir: Directory containing game files to load.

        Raises:
            AssetRipperExportError: If loading files fails.
        """
        logger.info(f"Loading files from: {source_dir}")

        # Verify source directory exists via API
        exists = self._api_get(f"/IO/Directory/Exists?Path={self._url_encode(str(source_dir.absolute()))}")

        if exists.strip().lower() != "true":
            raise AssetRipperExportError(f"Source directory does not exist: {source_dir}")

        # Load files
        _, status_code = self._api_post("/LoadFolder", {"path": str(source_dir.absolute())})

        if status_code != 302:  # AssetRipper returns 302 redirect on success
            raise AssetRipperExportError(f"Failed to load files. HTTP status: {status_code}")

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

        # Start export with short timeout (API call is synchronous and blocks until completion)
        # We timeout after 10 seconds to avoid blocking, then monitor via log file
        _, status_code = self._api_post("/Export/UnityProject", {"path": str(target_dir.absolute())}, timeout=10)

        # Status code 0 means curl timed out, which is expected for long-running exports
        # Status code 302 means immediate success (unlikely for large exports)
        # Any other status code is an error
        if status_code not in (0, 302):
            raise AssetRipperExportError(f"Failed to start export. HTTP status: {status_code}")

        logger.info("Export started successfully")

    def _monitor_export(self) -> None:
        """Monitor export progress by watching log file.

        Raises:
            AssetRipperExportError: If export times out or fails.
        """
        if not self._log_file or not self._log_file.exists():
            logger.warning("Log file not available, skipping progress monitoring")
            return

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

                # AssetRipper outputs these messages when export completes
                if "Finished post-export" in log_tail or "Finished exporting assets" in log_tail:
                    logger.info("Export completed successfully!")
                    return

            except Exception as e:
                logger.debug(f"Error reading log file: {e}")

        raise AssetRipperExportError(
            f"Export monitoring timed out after {self.timeout} seconds.\n"
            f"Export may still be running. Check log: {self._log_file}"
        )

    def extract(
        self,
        source_dir: Path,
        target_dir: Path,
        log_dir: Path,
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
            # Start server
            self.start_server(log_dir=log_dir)

            # Load files
            self._load_files(source_dir)

            # Export to Unity project
            self._export_files(target_dir)

            # Monitor export progress
            self._monitor_export()

            logger.info("Asset extraction complete!")
            logger.info(f"Unity project ready at: {target_dir}")
            if self._log_file:
                logger.info(f"Log file: {self._log_file}")

        finally:
            # Always stop server
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
