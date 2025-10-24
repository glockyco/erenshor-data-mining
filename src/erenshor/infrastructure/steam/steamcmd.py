"""SteamCMD wrapper for downloading game files from Steam.

This module provides a Python wrapper around the SteamCMD command-line tool,
enabling programmatic download and management of Steam game files.

Features:
- Download game files by App ID
- Support for different platforms (Windows/macOS/Linux)
- Steam authentication (username/password or anonymous)
- File validation options
- Build ID and manifest tracking
- Proper error handling and logging

The SteamCMD class wraps the steamcmd CLI and provides type-safe, testable
interfaces for downloading game files. It's designed to work with the
multi-variant system (main/playtest/demo).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from loguru import logger


class SteamCMDError(Exception):
    """Base exception for SteamCMD-related errors.

    This is the parent exception for all SteamCMD-specific errors.
    Catch this to handle all SteamCMD failures.
    """

    pass


class SteamCMDNotFoundError(SteamCMDError):
    """Raised when SteamCMD executable is not found on the system.

    This typically means SteamCMD is not installed or not in PATH.
    On macOS: brew install steamcmd
    On Linux: Install via package manager or download from Valve
    """

    pass


class SteamCMDDownloadError(SteamCMDError):
    """Raised when game download fails.

    This can occur due to:
    - Network errors
    - Invalid App ID
    - Insufficient disk space
    - Permission errors
    - SteamCMD process failure
    """

    pass


class SteamCMDAuthenticationError(SteamCMDError):
    """Raised when Steam authentication fails.

    This occurs when:
    - Invalid username/password
    - Account requires Steam Guard
    - Account is locked or banned
    - Network connectivity issues
    """

    pass


PlatformType = Literal["windows", "macos", "linux"]


class SteamCMD:
    """Wrapper for SteamCMD command-line tool.

    This class provides a Python interface to SteamCMD for downloading
    game files from Steam. It handles authentication, platform selection,
    and file validation.

    Attributes:
        username: Steam username (use "anonymous" for anonymous login).
        platform: Target platform for game files.

    Example:
        >>> # Download game files
        >>> steamcmd = SteamCMD(username="myuser", platform="windows")
        >>> steamcmd.download(
        ...     app_id="2382520",
        ...     install_dir=Path("variants/main/game"),
        ...     validate=False
        ... )

        >>> # Anonymous download (if game supports it)
        >>> steamcmd = SteamCMD(username="anonymous")
        >>> steamcmd.download(app_id="2382520", install_dir=Path("game"))

        >>> # Download with full file validation
        >>> steamcmd.download(
        ...     app_id="2382520",
        ...     install_dir=Path("game"),
        ...     validate=True
        ... )
    """

    def __init__(
        self,
        username: str = "anonymous",
        platform: PlatformType = "windows",
    ) -> None:
        """Initialize SteamCMD wrapper.

        Args:
            username: Steam username or "anonymous" for anonymous login.
            platform: Target platform for game downloads (usually "windows" for cross-platform compatibility).

        Raises:
            SteamCMDNotFoundError: If steamcmd executable is not found in PATH.
        """
        self.username = username
        self.platform = platform

        # Verify SteamCMD is installed
        if not self._check_installed():
            raise SteamCMDNotFoundError(
                "SteamCMD not found in PATH.\n"
                "Install with: brew install steamcmd (macOS)\n"
                "Or download from: https://developer.valvesoftware.com/wiki/SteamCMD"
            )

        logger.debug(f"SteamCMD initialized: username={username}, platform={platform}")

    def _check_installed(self) -> bool:
        """Check if SteamCMD is installed and available in PATH.

        Returns:
            True if steamcmd is found, False otherwise.
        """
        return shutil.which("steamcmd") is not None

    def download(
        self,
        app_id: str,
        install_dir: Path,
        validate: bool = False,
    ) -> None:
        """Download game files from Steam.

        Downloads the specified Steam app to the target directory. Supports
        incremental updates (only downloads changed files) unless validate=True.

        SteamCMD will use saved login tokens if available. On first run or if
        token expired, it will prompt for password and Steam Guard code
        interactively. Login tokens are cached for future use.

        Args:
            app_id: Steam App ID to download (e.g., "2382520" for Erenshor).
            install_dir: Target directory for game files (will be created if needed).
            validate: If True, validates all files against Steam servers (slower, ensures integrity).

        Raises:
            SteamCMDDownloadError: If download fails.
            SteamCMDAuthenticationError: If authentication fails.

        Example:
            >>> steamcmd = SteamCMD(username="myuser", platform="windows")
            >>> steamcmd.download(
            ...     app_id="2382520",
            ...     install_dir=Path("variants/main/game"),
            ...     validate=False
            ... )
        """
        logger.debug(f"Starting game download: app_id={app_id}, install_dir={install_dir}")

        # Ensure install directory exists
        install_dir.mkdir(parents=True, exist_ok=True)

        # Build SteamCMD command
        # Note: Don't pass password on command line - let SteamCMD use saved login token
        # or prompt for password. Passing password prevents token caching.
        cmd = [
            "steamcmd",
            "+@sSteamCmdForcePlatformType",
            self.platform,
            "+force_install_dir",
            str(install_dir.absolute()),
            "+login",
            self.username,
        ]

        # Add app_update command with optional validation
        if validate:
            logger.debug("File validation enabled: all files will be verified against Steam servers")
            cmd.extend(["+app_update", app_id, "validate"])
        else:
            logger.debug("Incremental update mode: only changed files will be downloaded")
            cmd.extend(["+app_update", app_id])

        # Add quit command
        cmd.append("+quit")

        logger.debug(f"Executing SteamCMD: {' '.join(cmd)}")

        # Execute SteamCMD with real-time output
        try:
            # Use Popen to stream output line by line
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
            )

            # Collect output for error checking while showing progress
            output_lines = []
            if process.stdout:
                for line in process.stdout:
                    output_lines.append(line)
                    # Show progress lines to user
                    line_stripped = line.rstrip()
                    if line_stripped and any(
                        keyword in line_stripped
                        for keyword in ["Logging in", "Update state", "Success", "Downloading", "Validating"]
                    ):
                        logger.info(line_stripped)

            # Wait for process to complete
            return_code = process.wait()
            full_output = "".join(output_lines)

            # Check for errors
            if return_code != 0:
                # Check for authentication errors
                if "Login Failure" in full_output or "Invalid Password" in full_output:
                    logger.error("Steam authentication failed")
                    raise SteamCMDAuthenticationError(
                        f"Steam authentication failed for user: {self.username}\n"
                        "Check username and password, or ensure account is not locked.\n"
                        "Note: Some accounts may require Steam Guard verification."
                    )

                # General download error
                logger.error(f"SteamCMD failed with exit code {return_code}")
                raise SteamCMDDownloadError(
                    f"Game download failed: app_id={app_id}\n"
                    f"Exit code: {return_code}\n"
                    "Check network connectivity, disk space, and App ID."
                )

            logger.info(f"Download completed successfully: app_id={app_id}")

        except SteamCMDAuthenticationError:
            # Re-raise authentication errors
            raise
        except SteamCMDDownloadError:
            # Re-raise download errors
            raise

        except FileNotFoundError as e:
            # This shouldn't happen if _check_installed worked, but handle it anyway
            raise SteamCMDNotFoundError("SteamCMD executable not found") from e

    def get_build_id(self, install_dir: Path, app_id: str) -> str | None:
        """Get the currently installed build ID for a game.

        Reads the Steam manifest file to extract the build ID. Returns None
        if the game is not installed or the manifest is missing.

        Args:
            install_dir: Directory where game is installed.
            app_id: Steam App ID.

        Returns:
            Build ID string if found, None if game not installed or manifest missing.

        Example:
            >>> steamcmd = SteamCMD()
            >>> build_id = steamcmd.get_build_id(
            ...     install_dir=Path("variants/main/game"),
            ...     app_id="2382520"
            ... )
            >>> print(f"Current build: {build_id}")
        """
        manifest_file = install_dir / "steamapps" / f"appmanifest_{app_id}.acf"

        if not manifest_file.exists():
            logger.debug(f"Manifest file not found: {manifest_file}")
            return None

        try:
            content = manifest_file.read_text(encoding="utf-8")

            # Parse build ID from manifest (ACF format)
            for line in content.splitlines():
                if '"buildid"' in line:
                    # Extract number from line
                    parts = line.split('"')
                    if len(parts) >= 4:
                        build_id = parts[3]
                        logger.debug(f"Found build ID: {build_id}")
                        return build_id

            logger.warning(f"Build ID not found in manifest: {manifest_file}")
            return None

        except Exception as e:
            logger.error(f"Failed to read manifest file: {e}")
            return None

    def is_game_installed(self, install_dir: Path, game_executable: str = "Erenshor.exe") -> bool:
        """Check if game files are present in the install directory.

        This is a simple check for the main game executable to verify
        that the game has been downloaded.

        Args:
            install_dir: Directory to check for game files.
            game_executable: Name of main game executable (default: "Erenshor.exe").

        Returns:
            True if game files are present, False otherwise.

        Example:
            >>> steamcmd = SteamCMD()
            >>> if steamcmd.is_game_installed(Path("variants/main/game")):
            ...     print("Game is installed")
            ... else:
            ...     print("Game not found")
        """
        executable_path = install_dir / game_executable
        data_dir = install_dir / f"{game_executable.replace('.exe', '')}_Data"

        is_installed = executable_path.exists() and data_dir.exists()
        logger.debug(f"Game installed check: {is_installed} (executable={executable_path}, data={data_dir})")

        return is_installed
