from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.extract.export_workflow import (
    ExportRequest,
    ExportWorkflow,
    ExportWorkflowError,
)


class FakeUnity:
    def __init__(self, action=None) -> None:
        self.action = action
        self.calls: list[dict[str, object]] = []

    def execute_method(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.action is not None:
            self.action(kwargs)


def _request(tmp_path: Path, *, profile: bool = False) -> ExportRequest:
    return ExportRequest(
        unity_project_dir=tmp_path / "unity",
        database_path=tmp_path / "raw.sqlite",
        logs_dir=tmp_path / "logs",
        log_level="normal",
        profile_enabled=profile,
        profile_output_path=tmp_path / "profile.json",
    )


def _write_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE exported (value TEXT)")
        connection.commit()


def test_success_stages_and_publishes_exact_paths(tmp_path: Path) -> None:
    unity = FakeUnity(lambda call: _write_sqlite(Path(call["arguments"]["dbPath"])))
    request = _request(tmp_path)
    events: list[str] = []

    result = ExportWorkflow(unity, backup=lambda path: events.append(f"backup:{path.name}")).run(request)

    assert result.database_path == request.database_path
    assert result.log_file.parent == request.logs_dir
    assert request.database_path.is_file()
    assert not list(tmp_path.glob(".raw.sqlite.*.tmp"))
    assert events == ["backup:raw.sqlite"]
    assert unity.calls[0]["project_path"] == request.unity_project_dir / "ExportedProject"
    assert unity.calls[0]["arguments"]["dbPath"] != str(request.database_path.absolute())


def test_unity_failure_preserves_previous_database(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.database_path.write_bytes(b"old")

    def fail(_call):
        raise RuntimeError("Unity failed")

    with pytest.raises(RuntimeError, match="Unity failed"):
        ExportWorkflow(FakeUnity(fail)).run(request)

    assert request.database_path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".raw.sqlite.*.tmp"))


@pytest.mark.parametrize("output", ["missing", "invalid"])
def test_missing_or_invalid_staged_output_preserves_previous_database(tmp_path: Path, output: str) -> None:
    request = _request(tmp_path)
    request.database_path.write_bytes(b"old")

    def produce(call):
        if output == "invalid":
            Path(call["arguments"]["dbPath"]).write_bytes(b"not sqlite")

    with pytest.raises(ExportWorkflowError):
        ExportWorkflow(FakeUnity(produce)).run(request)

    assert request.database_path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".raw.sqlite.*.tmp"))


def test_profile_import_precedes_replacement_and_backup(tmp_path: Path) -> None:
    request = _request(tmp_path, profile=True)
    request.database_path.write_bytes(b"old")
    events: list[str] = []

    def produce(call):
        _write_sqlite(Path(call["arguments"]["dbPath"]))
        events.append("unity")

    def import_profile(path: Path):
        assert request.database_path.read_bytes() == b"old"
        events.append(f"profile:{path.name}")

    def backup(path: Path):
        assert path.read_bytes() != b"old"
        events.append("backup")

    ExportWorkflow(FakeUnity(produce), profile_importer=import_profile, backup=backup).run(request)

    assert events == ["unity", "profile:profile.json", "backup"]


def test_profile_failure_preserves_database_and_skips_backup(tmp_path: Path) -> None:
    request = _request(tmp_path, profile=True)
    request.database_path.write_bytes(b"old")
    backed_up = False

    def produce(call):
        _write_sqlite(Path(call["arguments"]["dbPath"]))

    def import_profile(_path):
        raise ValueError("profile failed")

    def backup(_path):
        nonlocal backed_up
        backed_up = True

    with pytest.raises(ValueError, match="profile failed"):
        ExportWorkflow(FakeUnity(produce), profile_importer=import_profile, backup=backup).run(request)

    assert request.database_path.read_bytes() == b"old"
    assert not backed_up


def test_dynamic_spawn_failure_preserves_adapter_exit_code(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.database_path.write_bytes(b"old")

    class DynamicSpawnError(RuntimeError):
        exit_code = 3

    def fail(_call):
        raise DynamicSpawnError("dynamic spawn coverage failed")

    with pytest.raises(DynamicSpawnError) as raised:
        ExportWorkflow(FakeUnity(fail)).run(request)

    assert raised.value.exit_code == 3
    assert request.database_path.read_bytes() == b"old"


def test_backup_failure_keeps_published_database(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.database_path.write_bytes(b"old")

    def produce(call):
        _write_sqlite(Path(call["arguments"]["dbPath"]))

    with pytest.raises(RuntimeError, match="backup failed"):
        ExportWorkflow(
            FakeUnity(produce),
            backup=lambda _path: (_ for _ in ()).throw(RuntimeError("backup failed")),
        ).run(request)

    with sqlite3.connect(request.database_path) as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)
