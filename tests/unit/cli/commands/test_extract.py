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

    def resolved_database_raw(self, repo_root: Path) -> Path:
        return self.root / "database_raw.sqlite"

    def resolved_database(self, repo_root: Path) -> Path:
        return self.root / "database.sqlite"

    def resolved_backups(self, repo_root: Path) -> Path:
        return self.root / "backups"


def _context(tmp_path: Path, variant: VariantStub) -> SimpleNamespace:
    return SimpleNamespace(
        repo_root=tmp_path,
        variant="playtest",
        dry_run=False,
        config=SimpleNamespace(variants={"playtest": variant}),
    )


def test_rip_command_composes() -> None:
    result = CliRunner().invoke(extract.app, ["rip", "--help"])

    assert result.exit_code == 0
    assert "Extract Unity project from game files via AssetRipper" in result.stdout

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


def _write_comparison_db(path: Path, *, include_new_rows: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE items (
                resource_name TEXT PRIMARY KEY,
                display_name TEXT,
                required_slot TEXT,
                item_level INTEGER,
                lore TEXT
            );
            CREATE TABLE spells (
                resource_name TEXT PRIMARY KEY,
                display_name TEXT,
                type TEXT,
                spell_desc TEXT
            );
            CREATE TABLE skills (resource_name TEXT PRIMARY KEY);
            CREATE TABLE characters (
                object_name TEXT PRIMARY KEY,
                display_name TEXT,
                level INTEGER,
                is_npc INTEGER,
                is_vendor INTEGER,
                effective_hp INTEGER,
                stable_key TEXT
            );
            CREATE TABLE character_spawns (character_stable_key TEXT, zone_stable_key TEXT);
            CREATE TABLE zones (stable_key TEXT PRIMARY KEY, zone_name TEXT, scene_name TEXT);
            CREATE TABLE quests (db_name TEXT PRIMARY KEY, stable_key TEXT);
            CREATE TABLE quest_variants (
                quest_stable_key TEXT,
                quest_name TEXT,
                xp_on_complete INTEGER,
                gold_on_complete INTEGER,
                quest_desc TEXT
            );
            INSERT INTO items VALUES ('item:base', 'Base Sword', 'Weapon', 1, 'Base lore');
            INSERT INTO spells VALUES ('spell:base', 'Base Spell', 'Combat', 'Base spell');
            INSERT INTO skills VALUES ('skill:base');
            INSERT INTO characters VALUES ('char:base', 'Base NPC', 2, 1, 0, 100, 'char:base');
            INSERT INTO zones VALUES ('zone:base', 'Base Zone', 'BaseScene');
            INSERT INTO quests VALUES ('quest:base', 'quest:base');
            INSERT INTO quest_variants VALUES ('quest:base', 'Base Quest', 10, 0, 'Base quest');
            """
        )
        if include_new_rows:
            connection.executescript(
                """
                INSERT INTO items VALUES ('item:new', 'New Sword', 'Weapon', 5, 'New\n lore');
                INSERT INTO spells VALUES ('spell:new', 'New Spell', 'Combat', 'New\n spell');
                INSERT INTO skills VALUES ('skill:new');
                INSERT INTO characters VALUES ('char:new', 'New Vendor', 8, 1, 1, 1234, 'char:new');
                INSERT INTO character_spawns VALUES ('char:new', 'zone:new');
                INSERT INTO zones VALUES ('zone:new', 'New Zone', 'NewScene');
                INSERT INTO quests VALUES ('quest:new', 'quest:new');
                INSERT INTO quest_variants VALUES ('quest:new', 'New Quest', 250, 3, 'New quest');
                """
            )


def _comparison_context(tmp_path: Path, *, include_new_db: bool = True) -> SimpleNamespace:
    base_variant = VariantStub(tmp_path / "main")
    new_variant = VariantStub(tmp_path / "demo")
    _write_comparison_db(base_variant.resolved_database(tmp_path), include_new_rows=False)
    if include_new_db:
        _write_comparison_db(new_variant.resolved_database(tmp_path), include_new_rows=True)
    return SimpleNamespace(
        repo_root=tmp_path,
        variant="main",
        dry_run=False,
        config=SimpleNamespace(variants={"main": base_variant, "demo": new_variant}),
    )


def test_compare_variants_main_vs_demo_report_preserves_metrics(tmp_path: Path) -> None:
    result = CliRunner().invoke(extract.app, ["compare-variants"], obj=_comparison_context(tmp_path))

    assert result.exit_code == 0
    assert "# Erenshor: Demo vs Main Comparison" in result.stdout
    assert "| Zones | 1 | 2 | +1 |" in result.stdout
    assert "| Items | 1 | 2 | +1 |" in result.stdout
    assert "| Spells | 1 | 2 | +1 |" in result.stdout
    assert "| Characters | 1 | 2 | +1 |" in result.stdout
    assert "| Quests | 1 | 2 | +1 |" in result.stdout
    assert "| Skills | 1 | 2 | +1 |" in result.stdout
    assert "## New Zones (1)" in result.stdout
    assert "## New Items (1)" in result.stdout
    assert "## New Spells (1)" in result.stdout
    assert "## New Characters/NPCs (1)" in result.stdout
    assert "## New Quests (1)" in result.stdout
    assert "New Vendor" in result.stdout


def test_compare_variants_registers_options_and_help() -> None:
    result = CliRunner().invoke(extract.app, ["compare-variants", "--help"])

    assert result.exit_code == 0
    assert "--base-variant" in result.stdout
    assert "--new-variant" in result.stdout
    assert "--output" in result.stdout
    assert "Compare the clean databases" in result.stdout


def test_compare_variants_rejects_unknown_variant(tmp_path: Path) -> None:
    context = _comparison_context(tmp_path)
    result = CliRunner().invoke(extract.app, ["compare-variants", "--base-variant", "unknown"], obj=context)

    assert result.exit_code == 1
    assert "Unknown variant 'unknown'" in result.output


def test_compare_variants_rejects_missing_database(tmp_path: Path) -> None:
    context = _comparison_context(tmp_path, include_new_db=False)
    result = CliRunner().invoke(extract.app, ["compare-variants"], obj=context)

    assert result.exit_code == 1
    assert "New database not found for variant 'demo'" in result.output
