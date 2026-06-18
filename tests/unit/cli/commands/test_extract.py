from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

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
