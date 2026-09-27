"""Unit tests for the AssetRipper wrapper.

The AssetRipper process is replaced by a Popen double and its HTTP API by an
httpx mock transport, so the tests need no AssetRipper installation.
"""

import subprocess
from pathlib import Path
from typing import IO, Any
from unittest.mock import MagicMock, patch

import httpx
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

POPEN = "erenshor.infrastructure.assetripper.assetripper.subprocess.Popen"


def _running_process() -> MagicMock:
    """Return a Popen double for a server process that is still running."""
    process = MagicMock()
    process.pid = 12345
    process.poll.return_value = None
    return process


def _server(log_text: str = "") -> Any:
    """Return a Popen replacement that writes ``log_text`` to the server log."""

    def popen(_argv: list[str], stdout: IO[str], stderr: int) -> MagicMock:
        stdout.write(log_text)
        return _running_process()

    return popen


def _api(
    *,
    up: bool = True,
    directory_exists: str = "true",
    load_status: int = 302,
    export: int | None = None,
) -> httpx.MockTransport:
    """Fake AssetRipper API. ``export=None`` means the export outlives the request."""

    def handle(request: httpx.Request) -> httpx.Response:
        if not up:
            raise httpx.ConnectError("connection refused", request=request)
        match request.url.path:
            case "/":
                return httpx.Response(200)
            case "/IO/Directory/Exists":
                return httpx.Response(200, text=directory_exists)
            case "/LoadFolder":
                return httpx.Response(load_status)
            case "/Export/UnityProject":
                if export is None:
                    raise httpx.ReadTimeout("still exporting", request=request)
                return httpx.Response(export)
        return httpx.Response(404)

    return httpx.MockTransport(handle)


def _assetripper(tmp_path: Path, transport: httpx.MockTransport, **kwargs: Any) -> AssetRipper:
    executable = tmp_path / "AssetRipper"
    executable.touch()
    return AssetRipper(
        executable_path=executable, clock=kwargs.pop("clock", MockClock()), transport=transport, **kwargs
    )


def _game(tmp_path: Path) -> Path:
    source = tmp_path / "game" / "Erenshor_Data"
    source.mkdir(parents=True)
    return source


class TestAssetRipperInitialization:
    """Test AssetRipper initialization and validation."""

    def test_init_with_explicit_path(self, tmp_path: Path) -> None:
        executable = tmp_path / "AssetRipper"
        executable.touch()

        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=3600)

        assert assetripper.executable_path == executable
        assert assetripper.port == 8080
        assert assetripper.timeout == 3600

    def test_init_executable_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(AssetRipperNotFoundError, match="not found"):
            AssetRipper(executable_path=tmp_path / "nonexistent")

    def test_init_path_is_directory(self, tmp_path: Path) -> None:
        directory = tmp_path / "assetripper_dir"
        directory.mkdir()

        with pytest.raises(AssetRipperNotFoundError, match="not a file") as exc_info:
            AssetRipper(executable_path=directory)

        assert "config.local.toml" in str(exc_info.value)


class TestAssetRipperServerManagement:
    """Test AssetRipper server lifecycle management."""

    def test_start_server_launches_headless_api_on_the_port(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(), port=8080)

        with patch(POPEN, side_effect=_server()) as popen:
            assetripper.start_server(log_dir=tmp_path)

        argv = popen.call_args[0][0]
        assert argv[0] == str(assetripper.executable_path)
        assert argv[argv.index("--port") + 1] == "8080"
        # Without this the GUI build opens a browser instead of serving the API.
        assert "--headless" in argv

    def test_start_server_times_out_when_the_api_never_answers(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(up=False))

        with patch(POPEN, side_effect=_server()), pytest.raises(AssetRipperServerError, match="failed to start"):
            assetripper.start_server(log_dir=tmp_path)

        assert assetripper._process is None

    def test_start_server_spawn_error(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api())

        with patch(POPEN, side_effect=OSError("Permission denied")), pytest.raises(AssetRipperServerError):
            assetripper.start_server(log_dir=tmp_path)

    def test_start_server_reports_early_exit(self, tmp_path: Path) -> None:
        """A server process that exits before answering fails at once with its exit code."""
        process = _running_process()
        process.poll.return_value = 3
        clock = MockClock()
        started_at = clock.time()
        assetripper = _assetripper(tmp_path, _api(up=False), clock=clock)

        with patch(POPEN, return_value=process), pytest.raises(AssetRipperServerError, match="exited with code 3"):
            assetripper.start_server(log_dir=tmp_path)

        assert clock.time() == started_at
        assert assetripper._process is None

    def test_start_server_when_already_running_is_a_no_op(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api())
        assetripper._process = _running_process()

        with patch(POPEN) as popen:
            assetripper.start_server(log_dir=tmp_path)

        popen.assert_not_called()

    def test_stop_server_terminates_without_force_when_process_exits(self, tmp_path: Path) -> None:
        process = _running_process()
        assetripper = _assetripper(tmp_path, _api())
        assetripper._process = process

        assetripper.stop_server()

        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()
        assert assetripper._process is None

    def test_stop_server_kills_process_that_ignores_terminate(self, tmp_path: Path) -> None:
        process = _running_process()
        process.wait.side_effect = [subprocess.TimeoutExpired("AssetRipper", 10), 0]
        assetripper = _assetripper(tmp_path, _api())
        assetripper._process = process

        assetripper.stop_server()

        process.kill.assert_called_once_with()
        assert process.wait.call_count == 2
        assert assetripper._process is None

    def test_stop_server_without_running_server_is_a_no_op(self, tmp_path: Path) -> None:
        _assetripper(tmp_path, _api()).stop_server()


class TestAssetRipperExtraction:
    """Test AssetRipper extraction workflow."""

    def test_extract_follows_a_long_export_to_completion(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(export=None), timeout=60)
        target = tmp_path / "unity"

        with patch(POPEN, side_effect=_server("Export started\nFinished post-export\n")):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=target, log_dir=tmp_path)

        assert target.is_dir()
        assert assetripper._process is None

    def test_extract_records_internal_profile_spans(self, tmp_path: Path) -> None:
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
        assetripper = _assetripper(tmp_path, _api(export=302), timeout=60, clock=profile.clock)

        with patch(POPEN, side_effect=_server("Finished exporting assets\n")):
            assetripper.extract(
                source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path, profile=profile
            )

        names = {span.name for span in profile.spans}
        assert {
            "assetripper.start_server",
            "assetripper.load_files",
            "assetripper.export_start",
            "assetripper.monitor_export",
            "assetripper.stop_server",
        } <= names

    def test_extract_source_not_found(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api())

        with pytest.raises(AssetRipperNotFoundError, match="does not exist"):
            assetripper.extract(source_dir=tmp_path / "nonexistent", target_dir=tmp_path / "unity", log_dir=tmp_path)

    def test_extract_fails_when_assetripper_cannot_see_the_source(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(directory_exists="false"))

        with patch(POPEN, side_effect=_server()), pytest.raises(AssetRipperExportError, match="does not exist"):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)

        assert assetripper._process is None

    def test_extract_fails_when_loading_is_rejected(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(load_status=500))

        with patch(POPEN, side_effect=_server()), pytest.raises(AssetRipperExportError, match="HTTP status: 500"):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)

    def test_extract_fails_when_the_export_request_is_rejected(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(export=500))

        with patch(POPEN, side_effect=_server()), pytest.raises(AssetRipperExportError, match="HTTP status: 500"):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)

    def test_extract_times_out_without_a_completion_message(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(export=None), timeout=10)

        with (
            patch(POPEN, side_effect=_server("Export started\nProcessing...\n")),
            pytest.raises(AssetRipperExportError, match="timed out"),
        ):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)

        assert assetripper._process is None

    def test_extract_fails_at_once_when_assetripper_exits_during_the_export(self, tmp_path: Path) -> None:
        process = _running_process()
        process.poll.side_effect = [None, 134, 134]
        assetripper = _assetripper(tmp_path, _api(export=None), timeout=3600)

        def popen(_argv: list[str], stdout: IO[str], stderr: int) -> MagicMock:
            stdout.write("Export started\n")
            return process

        with patch(POPEN, side_effect=popen), pytest.raises(AssetRipperExportError, match="exited with code 134"):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)

    def test_unreadable_log_is_reported_instead_of_polled(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api(export=None), timeout=3600)
        original_open = Path.open

        def open_log(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if path.name.startswith("assetripper_") and mode == "rb":
                raise PermissionError("denied")
            return original_open(path, mode, *args, **kwargs)

        with (
            patch(POPEN, side_effect=_server("Export started\n")),
            patch.object(Path, "open", open_log),
            pytest.raises(AssetRipperExportError, match=r"Cannot read AssetRipper log .*denied"),
        ):
            assetripper.extract(source_dir=_game(tmp_path), target_dir=tmp_path / "unity", log_dir=tmp_path)


class TestAssetRipperUtilities:
    """Test AssetRipper utility methods."""

    def test_is_installed_true(self, tmp_path: Path) -> None:
        assert _assetripper(tmp_path, _api()).is_installed() is True

    def test_is_installed_false(self, tmp_path: Path) -> None:
        assetripper = _assetripper(tmp_path, _api())
        assetripper.executable_path.unlink()

        assert assetripper.is_installed() is False

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_get_version_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="AssetRipper v1.3.4\n", stderr="")

        assert _assetripper(tmp_path, _api()).get_version() == "AssetRipper v1.3.4"

    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    def test_get_version_not_available(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        assert _assetripper(tmp_path, _api()).get_version() is None

    def test_get_base_url(self, tmp_path: Path) -> None:
        assert _assetripper(tmp_path, _api(), port=9000)._get_base_url() == "http://localhost:9000"

    def test_check_server_running(self, tmp_path: Path) -> None:
        assert _assetripper(tmp_path, _api())._check_server_running() is True
        assert _assetripper(tmp_path, _api(up=False))._check_server_running() is False


class TestAssetRipperErrorHierarchy:
    """Test exception hierarchy and inheritance."""

    def test_exception_hierarchy(self) -> None:
        assert issubclass(AssetRipperNotFoundError, AssetRipperError)
        assert issubclass(AssetRipperServerError, AssetRipperError)
        assert issubclass(AssetRipperExportError, AssetRipperError)

    def test_base_exception_catchable(self, tmp_path: Path) -> None:
        with pytest.raises(AssetRipperError):
            AssetRipper(executable_path=tmp_path / "nonexistent")
