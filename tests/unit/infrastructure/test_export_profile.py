from __future__ import annotations

import json
import sqlite3
from contextlib import closing

from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.time import MockClock


def test_profile_recorder_persists_run_span_jsonl_and_trace(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    recorder = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract export --profile",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        machine="darwin-arm64",
        clock=clock,
    )

    with recorder.span("extract.export", category="cli", attributes={"variant": "playtest"}):
        clock.advance(2.5)
        with recorder.span(
            "extract.export.unity_subprocess",
            category="unity",
            attributes={"log": "export.log"},
        ):
            clock.advance(5.0)

    recorder.finish("ok")

    db_path = root / "export-runs.sqlite"
    assert db_path.exists()
    with closing(sqlite3.connect(db_path)) as conn:
        run = conn.execute(
            "SELECT variant, status FROM export_profile_runs WHERE run_id = ?",
            (recorder.run_id,),
        ).fetchone()
        spans = conn.execute(
            "SELECT name, duration_ms FROM export_profile_spans WHERE run_id = ? ORDER BY duration_ms DESC",
            (recorder.run_id,),
        ).fetchall()

    assert run == ("playtest", "ok")
    assert spans[0] == ("extract.export", 7500.0)
    assert spans[1] == ("extract.export.unity_subprocess", 5000.0)

    jsonl_path = root / "runs" / f"{recorder.run_id}.jsonl"
    lines = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    assert lines[0]["type"] == "run"
    assert {line["name"] for line in lines if line["type"] == "span"} == {
        "extract.export",
        "extract.export.unity_subprocess",
    }

    trace = json.loads((root / "runs" / f"{recorder.run_id}.trace.json").read_text())
    assert trace["traceEvents"][0]["ph"] == "X"
    assert trace["traceEvents"][0]["name"] == "extract.export"


def test_profile_recorder_reuses_active_run_across_cli_invocations(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    download = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract download",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with download.span("extract.download", category="cli"):
        clock.advance(1.0)
    download.finish_command("extract download", "ok")

    export = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with export.span("extract.export", category="cli"):
        clock.advance(2.0)
    export.finish_command("extract export", "ok")

    assert export.run_id == download.run_id
    assert json.loads((root / "current-run.json").read_text())["run_id"] == download.run_id
    with closing(sqlite3.connect(root / "export-runs.sqlite")) as conn:
        spans = conn.execute(
            "SELECT name FROM export_profile_spans WHERE run_id = ? ORDER BY span_id",
            (download.run_id,),
        ).fetchall()
    assert spans == [("extract.download",), ("extract.export",)]

    lines = [json.loads(line) for line in (root / "runs" / f"{download.run_id}.jsonl").read_text().splitlines()]
    assert {line["name"] for line in lines if line["type"] == "span"} == {
        "extract.download",
        "extract.export",
    }
    trace = json.loads((root / "runs" / f"{download.run_id}.trace.json").read_text())
    assert {event["name"] for event in trace["traceEvents"]} == {
        "extract.download",
        "extract.export",
    }


def test_profile_recorder_does_not_reuse_finished_run(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    first = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract build",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        machine="darwin-arm64",
        clock=clock,
    )
    first.finish("ok")
    assert not (root / "current-run.json").exists()

    second = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract download",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )

    assert second.run_id != first.run_id


def test_profile_recorder_updates_active_build_id(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    download = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract download",
        game_build_id=None,
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    download.update_game_build_id("23789241")

    export = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        clock=clock,
    )

    assert export.run_id == download.run_id
    assert json.loads((root / "current-run.json").read_text())["game_build_id"] == "23789241"
    with closing(sqlite3.connect(root / "export-runs.sqlite")) as conn:
        stored_metadata = conn.execute(
            """
            SELECT game_build_id, unity_version, assetripper_version
            FROM export_profile_runs
            WHERE run_id = ?
            """,
            (download.run_id,),
        ).fetchone()
    assert stored_metadata == ("23789241", "2021.3.45f2", "1.2.3")


def test_profile_recorder_marks_failed_runs(tmp_path):
    clock = MockClock()
    recorder = ExportProfileRecorder.open_or_create(
        root=tmp_path / "profiles",
        variant="playtest",
        command="extract export",
        game_build_id=None,
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )

    try:
        with recorder.span("extract.export", category="cli"):
            clock.advance(1.0)
            raise RuntimeError("boom")
    except RuntimeError:
        recorder.finish("failed")

    with closing(sqlite3.connect(tmp_path / "profiles" / "export-runs.sqlite")) as conn:
        status = conn.execute(
            "SELECT status FROM export_profile_runs WHERE run_id = ?",
            (recorder.run_id,),
        ).fetchone()[0]
        span_status = conn.execute(
            "SELECT status FROM export_profile_spans WHERE run_id = ?",
            (recorder.run_id,),
        ).fetchone()[0]

    assert status == "failed"
    assert span_status == "failed"
