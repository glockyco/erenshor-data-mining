from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from erenshor.cli.commands import extract
from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.time import MockClock


class VariantStub:
    app_id = "3090030"

    def __init__(self, root: Path) -> None:
        self.root = root

    def resolved_game_files(self, repo_root: Path) -> Path:
        return self.root / "game"

    def resolved_profiles(self, repo_root: Path) -> Path:
        return self.root / "profiles"


def _context(tmp_path: Path, variant: VariantStub) -> SimpleNamespace:
    return SimpleNamespace(
        repo_root=tmp_path,
        variant="playtest",
        dry_run=False,
        config=SimpleNamespace(variants={"playtest": variant}),
    )


def test_export_command_registers_profile_option() -> None:
    command = get_command(extract.app).commands["export"]

    assert any("--profile" in param.opts for param in command.params)


def test_profile_report_command_registers_latest_option() -> None:
    command = get_command(extract.app).commands["profile"].commands["report"]

    assert any("--latest" in param.opts for param in command.params)


def test_profile_report_prints_latest_profile(tmp_path: Path) -> None:
    clock = MockClock()
    variant = VariantStub(tmp_path)
    profile = ExportProfileRecorder.open_or_create(
        root=variant.resolved_profiles(tmp_path),
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with profile.span("unity.batch_subprocess", category="unity"):
        clock.advance(10.0)
    with profile.span("unity.ExportBatch", category="unity"):
        clock.advance(8.0)
    profile.finish("ok")

    result = CliRunner().invoke(
        extract.app,
        ["profile", "report", "--latest"],
        obj=_context(tmp_path, variant),
    )

    assert result.exit_code == 0
    assert profile.run_id in result.stdout
    assert "Unity overhead before/after ExportBatch: 2000.00 ms" in result.stdout


def _write_manifest(game_files: Path, app_id: str, build_id: str) -> None:
    steamapps = game_files / "steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / f"appmanifest_{app_id}.acf").write_text(f'"AppState"\n{{\n    "buildid" "{build_id}"\n}}\n')


def test_open_profile_uses_variant_profile_root_and_metadata(tmp_path: Path) -> None:
    variant = VariantStub(tmp_path)
    _write_manifest(variant.resolved_game_files(tmp_path), variant.app_id, "23789241")
    ctx = _context(tmp_path, variant)

    completed = MagicMock(stdout="abcdef0\n")
    with patch("erenshor.cli.commands.extract.subprocess.run", return_value=completed):
        profile = extract._open_profile(
            ctx,
            variant,
            "extract export",
            unity_version="2021.3.45f2",
            assetripper_version="1.2.3",
        )

    assert profile.root == tmp_path / "profiles"
    assert profile.variant == "playtest"
    assert profile.game_build_id == "23789241"
    assert profile.git_sha == "abcdef0"
    assert profile.unity_version == "2021.3.45f2"
    assert profile.assetripper_version == "1.2.3"


def test_profile_command_finishes_terminal_stage(tmp_path: Path) -> None:
    clock = MockClock()
    variant = VariantStub(tmp_path)
    ctx = _context(tmp_path, variant)
    profile = ExportProfileRecorder.open_or_create(
        root=variant.resolved_profiles(tmp_path),
        variant="playtest",
        command="extract build",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        machine="darwin-arm64",
        clock=clock,
    )

    with extract._profile_command(profile, "extract build", ctx, terminal=True):
        clock.advance(1.25)

    with closing(sqlite3.connect(profile.root / "export-runs.sqlite")) as conn:
        run = conn.execute(
            """
            SELECT status, last_command, last_command_status
            FROM export_profile_runs
            WHERE run_id = ?
            """,
            (profile.run_id,),
        ).fetchone()
        span = conn.execute(
            "SELECT name, duration_ms, status FROM export_profile_spans WHERE run_id = ?",
            (profile.run_id,),
        ).fetchone()

    assert run == ("ok", "extract build", "ok")
    assert span == ("extract build", 1250.0, "ok")


def test_profile_command_marks_failed_run(tmp_path: Path) -> None:
    clock = MockClock()
    variant = VariantStub(tmp_path)
    ctx = _context(tmp_path, variant)
    profile = ExportProfileRecorder.open_or_create(
        root=variant.resolved_profiles(tmp_path),
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )

    with pytest.raises(ValueError, match="boom"), extract._profile_command(profile, "extract export", ctx):
        clock.advance(0.5)
        raise ValueError("boom")

    with closing(sqlite3.connect(profile.root / "export-runs.sqlite")) as conn:
        run = conn.execute(
            """
            SELECT status, last_command, last_command_status
            FROM export_profile_runs
            WHERE run_id = ?
            """,
            (profile.run_id,),
        ).fetchone()
        span = conn.execute(
            "SELECT name, duration_ms, status FROM export_profile_spans WHERE run_id = ?",
            (profile.run_id,),
        ).fetchone()

    assert run == ("failed", "extract export", "failed")
    assert span == ("extract export", 500.0, "failed")


def test_import_unity_profile_output_records_listener_spans(tmp_path: Path) -> None:
    clock = MockClock()
    variant = VariantStub(tmp_path)
    profile = ExportProfileRecorder.open_or_create(
        root=variant.resolved_profiles(tmp_path),
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with profile.span("unity.batch_subprocess", category="unity"):
        clock.advance(10.0)
    output_path = tmp_path / "unity-profile.json"
    output_path.write_text(
        json.dumps(
            [
                {
                    "category": "listener.OnAssetFound",
                    "name": "CharacterListener",
                    "calls": 100,
                    "total_ms": 3000.0,
                    "avg_ms": 30.0,
                    "max_ms": 50.0,
                    "first_start_ms": 2000.0,
                }
            ]
        )
    )

    extract._import_unity_profile_output(profile, output_path)

    with closing(sqlite3.connect(profile.root / "export-runs.sqlite")) as conn:
        row = conn.execute(
            """
            SELECT name, category, duration_ms, attributes_json
            FROM export_profile_spans
            WHERE name = 'listener.OnAssetFound.CharacterListener'
            """,
        ).fetchone()

    assert row[:3] == ("listener.OnAssetFound.CharacterListener", "listener.OnAssetFound", 3000.0)
    assert json.loads(row[3]) == {"calls": 100, "avg_ms": 30.0, "max_ms": 50.0}
