"""Unit tests for SteamCMD wrapper.

These tests verify the SteamCMD wrapper's behavior using mocks to avoid
requiring actual Steam downloads or credentials.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from erenshor.infrastructure.steam import (
    SteamCMD,
    SteamCMDAuthenticationError,
    SteamCMDDownloadError,
    SteamCMDNotFoundError,
)


class TestSteamCMDInitialization:
    """Test SteamCMD initialization and validation."""

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_init_success(self, mock_which: MagicMock) -> None:
        """Test successful initialization when SteamCMD is installed."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        steamcmd = SteamCMD(username="testuser", platform="windows")

        assert steamcmd.username == "testuser"
        assert steamcmd.platform == "windows"
        mock_which.assert_called_once_with("steamcmd")

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_init_steamcmd_not_found(self, mock_which: MagicMock) -> None:
        """Test initialization fails when SteamCMD is not installed."""
        mock_which.return_value = None

        with pytest.raises(SteamCMDNotFoundError) as exc_info:
            SteamCMD()

        assert "SteamCMD not found" in str(exc_info.value)
        assert "brew install steamcmd" in str(exc_info.value)

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_init_defaults(self, mock_which: MagicMock) -> None:
        """Test default values are set correctly."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        steamcmd = SteamCMD()

        assert steamcmd.username == "anonymous"
        assert steamcmd.platform == "windows"


class TestSteamCMDDownload:
    """Test SteamCMD download functionality."""

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    @patch("erenshor.infrastructure.steam.steamcmd.subprocess.run")
    def test_download_success(self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test successful game download."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Mock successful run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        steamcmd = SteamCMD(username="testuser", platform="windows")
        install_dir = tmp_path / "game"

        steamcmd.download(app_id="2382520", install_dir=install_dir, validate=False)

        # Verify directory was created
        assert install_dir.exists()

        # Verify subprocess.run was called with correct command
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "steamcmd"
        assert "+@sSteamCmdForcePlatformType" in call_args
        assert "windows" in call_args
        assert "+force_install_dir" in call_args
        assert "+login" in call_args
        assert "testuser" in call_args
        assert "+app_update" in call_args
        assert "2382520" in call_args
        assert "+quit" in call_args

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    @patch("erenshor.infrastructure.steam.steamcmd.subprocess.run")
    def test_download_with_validation(self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test download with file validation enabled."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Mock successful run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        steamcmd = SteamCMD()
        install_dir = tmp_path / "game"

        steamcmd.download(app_id="2382520", install_dir=install_dir, validate=True)

        # Verify 'validate' flag is in command
        call_args = mock_run.call_args[0][0]
        assert "validate" in call_args

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    @patch("erenshor.infrastructure.steam.steamcmd.subprocess.run")
    def test_download_authentication_failure(self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test download fails with authentication error."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Mock authentication failure (exit code 5)
        mock_result = MagicMock()
        mock_result.returncode = 5
        mock_run.return_value = mock_result

        steamcmd = SteamCMD(username="testuser")
        install_dir = tmp_path / "game"

        with pytest.raises(SteamCMDAuthenticationError):
            steamcmd.download(app_id="2382520", install_dir=install_dir)

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    @patch("erenshor.infrastructure.steam.steamcmd.subprocess.run")
    def test_download_process_failure(self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test download fails when SteamCMD process fails."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Mock process failure (exit code 7 = disk write failure)
        mock_result = MagicMock()
        mock_result.returncode = 7
        mock_run.return_value = mock_result

        steamcmd = SteamCMD()
        install_dir = tmp_path / "game"

        with pytest.raises(SteamCMDDownloadError) as exc_info:
            steamcmd.download(app_id="2382520", install_dir=install_dir)

        assert "Game download failed" in str(exc_info.value)


class TestSteamCMDBuildID:
    """Test build ID extraction from manifest files."""

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_get_build_id_success(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test successful build ID extraction."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Create mock manifest file
        manifest_dir = tmp_path / "steamapps"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "appmanifest_2382520.acf"
        manifest_file.write_text('"AppState"\n{\n\t"buildid"\t\t"20287268"\n\t"other"\t\t"value"\n}\n')

        steamcmd = SteamCMD()
        build_id = steamcmd.get_build_id(install_dir=tmp_path, app_id="2382520")

        assert build_id == "20287268"

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_get_build_id_manifest_missing(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test build ID returns None when manifest doesn't exist."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        steamcmd = SteamCMD()
        build_id = steamcmd.get_build_id(install_dir=tmp_path, app_id="2382520")

        assert build_id is None

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_get_build_id_malformed_manifest(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test build ID returns None when manifest is malformed."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Create malformed manifest
        manifest_dir = tmp_path / "steamapps"
        manifest_dir.mkdir(parents=True)
        manifest_file = manifest_dir / "appmanifest_2382520.acf"
        manifest_file.write_text("invalid manifest content")

        steamcmd = SteamCMD()
        build_id = steamcmd.get_build_id(install_dir=tmp_path, app_id="2382520")

        assert build_id is None


class TestSteamCMDGameInstalled:
    """Test game installation detection."""

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_is_game_installed_true(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test game is detected when files exist."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Create mock game files
        (tmp_path / "Erenshor.exe").touch()
        (tmp_path / "Erenshor_Data").mkdir()

        steamcmd = SteamCMD()
        is_installed = steamcmd.is_game_installed(install_dir=tmp_path)

        assert is_installed is True

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_is_game_installed_false_missing_exe(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test game is not detected when executable is missing."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Only create data directory, no executable
        (tmp_path / "Erenshor_Data").mkdir()

        steamcmd = SteamCMD()
        is_installed = steamcmd.is_game_installed(install_dir=tmp_path)

        assert is_installed is False

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_is_game_installed_false_missing_data(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test game is not detected when data directory is missing."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Only create executable, no data directory
        (tmp_path / "Erenshor.exe").touch()

        steamcmd = SteamCMD()
        is_installed = steamcmd.is_game_installed(install_dir=tmp_path)

        assert is_installed is False

    @patch("erenshor.infrastructure.steam.steamcmd.shutil.which")
    def test_is_game_installed_custom_executable(self, mock_which: MagicMock, tmp_path: Path) -> None:
        """Test game detection with custom executable name."""
        mock_which.return_value = "/usr/local/bin/steamcmd"

        # Create custom game files
        (tmp_path / "CustomGame.exe").touch()
        (tmp_path / "CustomGame_Data").mkdir()

        steamcmd = SteamCMD()
        is_installed = steamcmd.is_game_installed(install_dir=tmp_path, game_executable="CustomGame.exe")

        assert is_installed is True
