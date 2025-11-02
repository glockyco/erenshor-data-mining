"""Unit tests for AssetRipper wrapper.

These tests verify the AssetRipper wrapper's behavior using mocks to avoid
requiring actual AssetRipper installation or long-running extraction processes.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from erenshor.infrastructure.assetripper import (
    AssetRipper,
    AssetRipperError,
    AssetRipperExportError,
    AssetRipperNotFoundError,
    AssetRipperServerError,
)


class TestAssetRipperInitialization:
    """Test AssetRipper initialization and validation."""

    def test_init_with_explicit_path(self, tmp_path: Path) -> None:
        """Test successful initialization with explicit executable path."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=3600)

        assert assetripper.executable_path == executable
        assert assetripper.port == 8080
        assert assetripper.timeout == 3600

    def test_init_executable_not_found(self, tmp_path: Path) -> None:
        """Test initialization fails when executable doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(AssetRipperNotFoundError) as exc_info:
            AssetRipper(executable_path=nonexistent)

        assert "not found" in str(exc_info.value).lower()

    def test_init_path_is_directory(self, tmp_path: Path) -> None:
        """Test initialization fails when path is a directory."""
        directory = tmp_path / "assetripper_dir"
        directory.mkdir()

        with pytest.raises(AssetRipperNotFoundError) as exc_info:
            AssetRipper(executable_path=directory)

        assert "not a file" in str(exc_info.value).lower()
        assert "config.local.toml" in str(exc_info.value)


class TestAssetRipperServerManagement:
    """Test AssetRipper server lifecycle management."""

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_success(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful server startup."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Mock server check to return True (server is running)
        mock_run.return_value = MagicMock(returncode=0)

        assetripper = AssetRipper(executable_path=executable, port=8080)
        assetripper.start_server(log_dir=tmp_path)

        # Verify server was started
        assert assetripper._server_pid == 12345
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert str(executable) in call_args
        assert "--port" in call_args
        assert "8080" in call_args

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_timeout(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test server startup times out if server doesn't respond."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Mock server check to always return False (server not responding)
        mock_run.return_value = MagicMock(returncode=1)

        assetripper = AssetRipper(executable_path=executable, port=8080)

        with pytest.raises(AssetRipperServerError) as exc_info:
            assetripper.start_server(log_dir=tmp_path)

        assert "failed to start" in str(exc_info.value).lower()
        assert assetripper._server_pid is None  # Server stopped after failure

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_spawn_error(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test server startup fails when process spawn fails."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        # Mock Popen to raise exception
        mock_popen.side_effect = OSError("Permission denied")

        assetripper = AssetRipper(executable_path=executable, port=8080)

        with pytest.raises(AssetRipperServerError) as exc_info:
            assetripper.start_server(log_dir=tmp_path)

        assert "failed to start" in str(exc_info.value).lower()

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_stop_server(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test stopping server."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)
        assetripper._server_pid = 12345

        assetripper.stop_server()

        # Verify kill commands were called
        assert assetripper._server_pid is None
        assert mock_run.call_count >= 1

    def test_stop_server_no_pid(self, tmp_path: Path) -> None:
        """Test stopping server when no server is running."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)
        assetripper._server_pid = None

        # Should not raise exception
        assetripper.stop_server()

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_already_running(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test starting server when already running is a no-op."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)
        assetripper._server_pid = 12345

        assetripper.start_server(log_dir=tmp_path)

        # Should not spawn new process
        mock_popen.assert_not_called()


class TestAssetRipperExtraction:
    """Test AssetRipper extraction workflow."""

    @patch("erenshor.infrastructure.assetripper.assetripper.time.time")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    @patch("erenshor.infrastructure.assetripper.assetripper.time.sleep")
    def test_extract_success(
        self,
        mock_sleep: MagicMock,
        mock_popen: MagicMock,
        mock_run: MagicMock,
        mock_time: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful extraction workflow."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game/Erenshor_Data"
        source_dir.mkdir(parents=True)

        target_dir = tmp_path / "unity"
        log_dir = tmp_path

        # Mock time.time() to return fixed timestamp for log filename
        mock_time.return_value = 1234567890

        # Mock process for server
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Mock API responses - need more responses for multiple curl calls
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if "curl" in cmd:
                # Check what API endpoint is being called
                if any("/IO/Directory/Exists" in str(arg) for arg in cmd):
                    return MagicMock(returncode=0, stdout="true")
                if any("LoadFolder" in str(arg) for arg in cmd) or any(
                    "Export/UnityProject" in str(arg) for arg in cmd
                ):
                    return MagicMock(returncode=0, stdout="\n302")
                # Server health check
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        assetripper = AssetRipper(executable_path=executable, port=8080)

        # Create log file with known filename (based on mocked time)
        log_file = log_dir / "assetripper_1234567890.log"

        # Mock sleep to write completion message to log on first check
        sleep_count = 0

        def mock_sleep_side_effect(seconds):
            nonlocal sleep_count
            sleep_count += 1
            # After first sleep in _monitor_export, write completion message
            if sleep_count == 1:
                log_file.write_text("Export started\nFinished post-export\n")

        mock_sleep.side_effect = mock_sleep_side_effect

        assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=log_dir)

        # Verify target directory was created
        assert target_dir.exists()

        # Verify server was stopped
        assert assetripper._server_pid is None

    def test_extract_source_not_found(self, tmp_path: Path) -> None:
        """Test extraction fails when source directory doesn't exist."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "nonexistent"
        target_dir = tmp_path / "unity"

        assetripper = AssetRipper(executable_path=executable)

        with pytest.raises(AssetRipperNotFoundError) as exc_info:
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)

        assert "does not exist" in str(exc_info.value).lower()

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    @patch("erenshor.infrastructure.assetripper.assetripper.time.sleep")
    def test_extract_load_files_error(
        self, mock_sleep: MagicMock, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test extraction fails when loading files fails."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game"
        source_dir.mkdir()

        target_dir = tmp_path / "unity"

        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Mock server check success, but LoadFolder failure
        mock_run.side_effect = [
            MagicMock(returncode=0),  # Server health check
            MagicMock(returncode=0, stdout="false"),  # Directory doesn't exist
        ]

        assetripper = AssetRipper(executable_path=executable, port=8080)

        with pytest.raises(AssetRipperExportError) as exc_info:
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)

        assert "does not exist" in str(exc_info.value).lower()

        # Verify server was stopped despite error
        assert assetripper._server_pid is None

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    @patch("erenshor.infrastructure.assetripper.assetripper.time.sleep")
    def test_extract_export_timeout(
        self, mock_sleep: MagicMock, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test extraction fails when export times out."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game"
        source_dir.mkdir()

        target_dir = tmp_path / "unity"

        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        # Mock API responses (all successful)
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if "curl" in cmd:
                # Check what API endpoint is being called
                if any("/IO/Directory/Exists" in str(arg) for arg in cmd):
                    return MagicMock(returncode=0, stdout="true")
                if any("LoadFolder" in str(arg) for arg in cmd) or any(
                    "Export/UnityProject" in str(arg) for arg in cmd
                ):
                    return MagicMock(returncode=0, stdout="\n302")
                # Server health check
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect

        # Mock log file without completion message (will timeout)
        log_content = "Export started\\nProcessing...\\n"

        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1)

        with (
            patch.object(Path, "read_text", return_value=log_content),
            pytest.raises(AssetRipperExportError) as exc_info,
        ):
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)

        assert "timed out" in str(exc_info.value).lower()

        # Verify server was stopped despite timeout
        assert assetripper._server_pid is None


class TestAssetRipperUtilities:
    """Test AssetRipper utility methods."""

    def test_is_installed_true(self, tmp_path: Path) -> None:
        """Test is_installed returns True when executable exists."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)

        assert assetripper.is_installed() is True

    def test_is_installed_false(self, tmp_path: Path) -> None:
        """Test is_installed returns False when executable is removed."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)

        # Remove executable
        executable.unlink()

        assert assetripper.is_installed() is False

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_get_version_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test getting version when available."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_run.return_value = MagicMock(returncode=0, stdout="AssetRipper v1.3.4\n", stderr="")

        assetripper = AssetRipper(executable_path=executable)
        version = assetripper.get_version()

        assert version == "AssetRipper v1.3.4"
        mock_run.assert_called_once()

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_get_version_not_available(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test get_version returns None when version command fails."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        assetripper = AssetRipper(executable_path=executable)
        version = assetripper.get_version()

        assert version is None

    def test_get_base_url(self, tmp_path: Path) -> None:
        """Test base URL construction."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable, port=9000)

        assert assetripper._get_base_url() == "http://localhost:9000"

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_check_server_running_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test server running check returns True when server responds."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_run.return_value = MagicMock(returncode=0)

        assetripper = AssetRipper(executable_path=executable, port=8080)

        assert assetripper._check_server_running() is True

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_check_server_running_false(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test server running check returns False when server doesn't respond."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_run.return_value = MagicMock(returncode=1)

        assetripper = AssetRipper(executable_path=executable, port=8080)

        assert assetripper._check_server_running() is False

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_check_server_running_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test server running check handles timeout gracefully."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_run.side_effect = subprocess.TimeoutExpired("curl", 5)

        assetripper = AssetRipper(executable_path=executable, port=8080)

        assert assetripper._check_server_running() is False


class TestAssetRipperErrorHierarchy:
    """Test exception hierarchy and inheritance."""

    def test_exception_hierarchy(self) -> None:
        """Test all exceptions inherit from AssetRipperError."""
        assert issubclass(AssetRipperNotFoundError, AssetRipperError)
        assert issubclass(AssetRipperServerError, AssetRipperError)
        assert issubclass(AssetRipperExportError, AssetRipperError)

    def test_base_exception_catchable(self, tmp_path: Path) -> None:
        """Test catching base exception catches all AssetRipper errors."""
        executable = tmp_path / "nonexistent"

        try:
            AssetRipper(executable_path=executable)
            pytest.fail("Should have raised exception")
        except AssetRipperError:
            pass  # Successfully caught via base exception
