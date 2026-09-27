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
from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.time import MockClock


def _running_process() -> MagicMock:
    """Return a Popen double for a server process that is still running."""
    process = MagicMock()
    process.pid = 12345
    process.poll.return_value = None
    return process


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

        mock_popen.return_value = _running_process()

        # Mock server check to return True (server is running)
        mock_run.return_value = MagicMock(returncode=0)

        assetripper = AssetRipper(executable_path=executable, port=8080)
        assetripper.start_server(log_dir=tmp_path)

        # Verify server was started
        assert assetripper._process is mock_popen.return_value
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert str(executable) in call_args
        assert "--port" in call_args
        assert "8080" in call_args
        # Without this the GUI build opens a browser instead of serving the API.
        assert "--headless" in call_args

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_timeout(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test server startup times out if server doesn't respond."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        mock_popen.return_value = _running_process()

        # Mock server check to always return False (server not responding)
        mock_run.return_value = MagicMock(returncode=1)

        # Use MockClock for instant timeout (no actual waiting)
        mock_clock = MockClock()
        assetripper = AssetRipper(executable_path=executable, port=8080, clock=mock_clock)

        with pytest.raises(AssetRipperServerError) as exc_info:
            assetripper.start_server(log_dir=tmp_path)

        assert "failed to start" in str(exc_info.value).lower()
        assert assetripper._process is None  # Server stopped after failure

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
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_reports_early_exit(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """A server process that exits before answering fails at once with its exit code."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()
        process = _running_process()
        process.poll.return_value = 3
        mock_popen.return_value = process
        mock_run.return_value = MagicMock(returncode=1)
        clock = MockClock()
        started_at = clock.time()
        assetripper = AssetRipper(executable_path=executable, clock=clock)

        with pytest.raises(AssetRipperServerError, match="exited with code 3"):
            assetripper.start_server(log_dir=tmp_path)

        assert clock.time() == started_at
        assert assetripper._process is None

    def test_stop_server_terminates_without_force_when_process_exits(self, tmp_path: Path) -> None:
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()
        process = _running_process()
        assetripper = AssetRipper(executable_path=executable)
        assetripper._process = process

        assetripper.stop_server()

        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()
        assert assetripper._process is None

    def test_stop_server_kills_process_that_ignores_terminate(self, tmp_path: Path) -> None:
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()
        process = _running_process()
        process.wait.side_effect = [subprocess.TimeoutExpired("AssetRipper", 10), 0]
        assetripper = AssetRipper(executable_path=executable)
        assetripper._process = process

        assetripper.stop_server()

        process.kill.assert_called_once_with()
        assert process.wait.call_count == 2
        assert assetripper._process is None

    def test_stop_server_without_running_server_is_a_no_op(self, tmp_path: Path) -> None:
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        AssetRipper(executable_path=executable).stop_server()

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_start_server_already_running(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test starting server when already running is a no-op."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable)
        assetripper._process = _running_process()

        assetripper.start_server(log_dir=tmp_path)

        # Should not spawn new process
        mock_popen.assert_not_called()


class TestAssetRipperExtraction:
    """Test AssetRipper extraction workflow."""

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_extract_success(
        self,
        mock_popen: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful extraction workflow."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game/Erenshor_Data"
        source_dir.mkdir(parents=True)

        target_dir = tmp_path / "unity"
        log_dir = tmp_path

        mock_popen.return_value = _running_process()

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

        # Use MockClock for instant execution
        mock_clock = MockClock()
        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1, clock=mock_clock)

        # Patch Path.open to return completion message when log file is read in binary mode
        original_path_open = Path.open
        from io import BytesIO

        def patched_path_open(self, mode="r", *args, **kwargs):
            # When log file is read in binary mode for monitoring, return completion message
            if "assetripper_" in str(self) and "rb" in mode:
                return BytesIO(b"Export started\nFinished post-export\n")
            return original_path_open(self, mode, *args, **kwargs)

        with patch.object(Path, "open", patched_path_open):
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=log_dir)

        # Verify target directory was created
        assert target_dir.exists()

        # Verify server was stopped
        assert assetripper._process is None

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_extract_records_internal_profile_spans(
        self,
        mock_popen: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test extraction records AssetRipper sub-stage profile spans."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()
        source_dir = tmp_path / "game" / "Erenshor_Data"
        source_dir.mkdir(parents=True)
        target_dir = tmp_path / "unity"
        profile = ExportProfileRecorder.open_or_create(
            root=tmp_path / "profiles",
            variant="playtest",
            command="extract rip",
            game_build_id="23789241",
            git_sha="abcdef0",
            unity_version=None,
            assetripper_version="1.2.3",
            machine="darwin-arm64",
            clock=MockClock(),
        )

        mock_popen.return_value = _running_process()

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if "curl" in cmd:
                if any("/IO/Directory/Exists" in str(arg) for arg in cmd):
                    return MagicMock(returncode=0, stdout="true")
                if any("LoadFolder" in str(arg) for arg in cmd) or any(
                    "Export/UnityProject" in str(arg) for arg in cmd
                ):
                    return MagicMock(returncode=0, stdout="\n302")
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect
        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1, clock=profile.clock)

        original_path_open = Path.open
        from io import BytesIO

        def patched_path_open(self, mode="r", *args, **kwargs):
            if "assetripper_" in str(self) and "rb" in mode:
                return BytesIO(b"Export started\nFinished post-export\n")
            return original_path_open(self, mode, *args, **kwargs)

        with patch.object(Path, "open", patched_path_open):
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path, profile=profile)

        names = {span.name for span in profile.spans}
        assert "assetripper.start_server" in names
        assert "assetripper.load_files" in names
        assert "assetripper.export_start" in names
        assert "assetripper.monitor_export" in names
        assert "assetripper.stop_server" in names

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
    def test_extract_load_files_error(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test extraction fails when loading files fails."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game"
        source_dir.mkdir()

        target_dir = tmp_path / "unity"

        mock_popen.return_value = _running_process()

        # Mock server check success, but LoadFolder failure
        mock_run.side_effect = [
            MagicMock(returncode=0),  # Server health check
            MagicMock(returncode=0, stdout="false"),  # Directory doesn't exist
        ]

        # Use MockClock for instant execution
        mock_clock = MockClock()
        assetripper = AssetRipper(executable_path=executable, port=8080, clock=mock_clock)

        with pytest.raises(AssetRipperExportError) as exc_info:
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)

        assert "does not exist" in str(exc_info.value).lower()

        # Verify server was stopped despite error
        assert assetripper._process is None

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_extract_export_timeout(self, mock_popen: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test extraction fails when export times out."""
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()

        source_dir = tmp_path / "game"
        source_dir.mkdir()

        target_dir = tmp_path / "unity"

        mock_popen.return_value = _running_process()

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

        # Use MockClock for instant timeout
        mock_clock = MockClock()
        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1, clock=mock_clock)

        with (
            patch.object(Path, "read_text", return_value=log_content),
            pytest.raises(AssetRipperExportError) as exc_info,
        ):
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)

        assert "timed out" in str(exc_info.value).lower()

        # Verify server was stopped despite timeout
        assert assetripper._process is None


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
