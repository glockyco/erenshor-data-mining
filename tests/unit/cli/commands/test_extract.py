from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from erenshor.cli.commands import extract
from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.steam.installation import GameInstallation, GameInstallationError
from erenshor.infrastructure.time import MockClock

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


class VariantStub:
    app_id = "3090030"

    def __init__(self, root: Path) -> None:
        self.root = root

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


def test_open_profile_uses_variant_profile_root_and_metadata(tmp_path: Path) -> None:
    variant = VariantStub(tmp_path)
    ctx = _context(tmp_path, variant)

    completed = MagicMock(stdout="abcdef0\n")
    with patch("erenshor.cli.commands.extract.subprocess.run", return_value=completed):
        profile = extract._open_profile(
            ctx,
            "extract export",
            game_build_id="23789241",
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


def _write_comparison_db(path: Path, *, include_new_rows: bool, build_id: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        if build_id is not None:
            connection.execute("CREATE TABLE code_facts_meta (game_build_id TEXT)")
            connection.execute("INSERT INTO code_facts_meta VALUES (?)", (build_id,))
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


def _comparison_context(
    cli_context: CLIContext, tmp_path: Path, *, include_new_db: bool = True, new_build_id: str | None = "200"
) -> CLIContext:
    original = cli_context.config.variants["main"]
    base = original.model_copy(update={"database": str(tmp_path / "main/database.sqlite")})
    new = original.model_copy(update={"name": "Demo", "database": str(tmp_path / "demo/database.sqlite")})
    _write_comparison_db(base.resolved_database(cli_context.repo_root), include_new_rows=False, build_id="100")
    if include_new_db:
        _write_comparison_db(new.resolved_database(cli_context.repo_root), include_new_rows=True, build_id=new_build_id)
    cli_context.config.variants.update({"main": base, "demo": new})
    return cli_context


def test_compare_variants_reports_added_rows_per_table(cli_context: CLIContext, tmp_path: Path) -> None:
    result = CliRunner().invoke(extract.app, ["compare-variants"], obj=_comparison_context(cli_context, tmp_path))

    assert result.exit_code == 0
    assert "main (build 100) → demo (build 200)" in result.stdout
    assert "| items | 1 | 2 | 1 | 0 | 0 |" in result.stdout
    assert "| characters | 1 | 2 | 1 | 0 | 0 |" in result.stdout
    assert "object_name=char:new, display_name=New Vendor" in result.stdout


def test_compare_variants_registers_options_and_help() -> None:
    command = get_command(extract.app).commands["compare-variants"]
    option_names = {opt for param in command.params for opt in param.opts}

    assert {"--base-variant", "--new-variant", "--output"} <= option_names
    assert command.help is not None
    assert "Compare the clean databases" in command.help


def test_compare_variants_rejects_unknown_variant(cli_context: CLIContext, tmp_path: Path) -> None:
    context = _comparison_context(cli_context, tmp_path)
    result = CliRunner().invoke(extract.app, ["compare-variants", "--base-variant", "unknown"], obj=context)

    assert result.exit_code == 1
    assert "Unknown variant 'unknown'" in result.output


def test_compare_variants_rejects_missing_database(cli_context: CLIContext, tmp_path: Path) -> None:
    context = _comparison_context(cli_context, tmp_path, include_new_db=False)
    output = tmp_path / "report.md"
    result = CliRunner().invoke(extract.app, ["compare-variants", "--output", str(output)], obj=context)

    assert result.exit_code == 1
    assert "New database not found for variant 'demo'" in result.output
    assert not output.exists()


def test_compare_variants_rejects_database_without_build_provenance(cli_context: CLIContext, tmp_path: Path) -> None:
    context = _comparison_context(cli_context, tmp_path, new_build_id=None)
    result = CliRunner().invoke(extract.app, ["compare-variants"], obj=context)

    assert result.exit_code == 1
    assert "has no build provenance" in result.output
    assert "erenshor extract build" in result.output


def test_packages_rejects_missing_manifest_before_restore(cli_context: CLIContext, tmp_path: Path) -> None:
    cli_context.repo_root = tmp_path

    with patch.object(extract, "restore_packages", side_effect=AssertionError("restore ran")):
        result = CliRunner().invoke(extract.app, ["packages"], obj=cli_context)

    assert result.exit_code == 1
    assert "packages.config" in result.output
    assert not (tmp_path / "src/Assets/Packages").exists()


@pytest.mark.parametrize("installed", [False, True])
def test_ide_setup_rejects_missing_game_assemblies_before_generation(
    cli_context: CLIContext, tmp_path: Path, installed: bool
) -> None:
    editor = tmp_path / "UnityEditor"
    editor.write_text("")
    cli_context.config.global_.unity.path = str(editor)
    scripts = tmp_path / "unity/ExportedProject/Assets/Scripts/Assembly-CSharp"
    scripts.mkdir(parents=True)
    game = tmp_path / "game"
    (game / "Erenshor_Data/Managed").mkdir(parents=True)

    def resolve(variant: str, app_id: str) -> GameInstallation:
        if not installed:
            raise GameInstallationError(f"Variant {variant!r} (Steam app {app_id}) is not installed")
        return GameInstallation(game, tmp_path / "appmanifest.acf", "Steam")

    with (
        patch("erenshor.cli.preconditions.checks.extract.find_game_installation", resolve),
        patch.object(extract.UnityPaths, "from_executable", return_value=object()),
        patch.object(extract, "generate_game_scripts_csproj", side_effect=AssertionError("generation ran")),
    ):
        result = CliRunner().invoke(extract.app, ["ide-setup"], obj=cli_context)

    assert result.exit_code == 1
    assert ("No DLLs found" if installed else "is not installed") in result.output
    assert not list(tmp_path.glob("**/*.csproj"))


def test_build_id_comes_from_the_installation_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "appmanifest_3090030.acf"
    manifest.write_text('"AppState"\n{\n    "buildid" "20287269"\n}\n')

    assert extract._installed_build_id(GameInstallation(tmp_path / "game", manifest, "Steam")) == "20287269"


def test_manifest_without_build_id_is_named(tmp_path: Path) -> None:
    manifest = tmp_path / "appmanifest_3090030.acf"
    manifest.write_text('"AppState"\n{\n}\n')

    with pytest.raises(GameInstallationError, match=r"appmanifest_3090030\.acf"):
        extract._installed_build_id(GameInstallation(tmp_path / "game", manifest, "Steam"))


def test_unreachable_build_feed_fails_publication_lookup(tmp_path: Path) -> None:
    variant = VariantStub(tmp_path)
    failure = httpx.ConnectError("SteamDB unreachable")

    with patch.object(extract, "fetch_build_feed", side_effect=failure), pytest.raises(httpx.ConnectError):
        extract._resolve_build_published_at(variant, "24405256")


def test_build_outside_the_feed_window_has_no_publication_time(tmp_path: Path) -> None:
    variant = VariantStub(tmp_path)

    with patch.object(extract, "fetch_build_feed", return_value=[]):
        assert extract._resolve_build_published_at(variant, "24405256") is None


def _clean_db(path: Path, build_id: str, item_level: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(
            f"""
            CREATE TABLE code_facts_meta (game_build_id TEXT);
            INSERT INTO code_facts_meta VALUES ('{build_id}');
            CREATE TABLE items (stable_key TEXT PRIMARY KEY, item_level INTEGER);
            INSERT INTO items VALUES ('item:sword', {item_level});
            """
        )
    return path


def _backup(backups: Path, build_id: str, *, item_level: int | None) -> None:
    database = backups / f"build-{build_id}" / "database"
    database.mkdir(parents=True)
    (database / "erenshor-main-raw.sqlite").write_bytes(b"raw")
    clean = None
    if item_level is not None:
        _clean_db(database / "erenshor-main.sqlite", build_id, item_level)
        clean = "erenshor-main.sqlite"
    metadata = {
        "variant": "main",
        "build_id": build_id,
        "app_id": "2382520",
        "created_at": "2026-01-01T00:00:00+00:00",
        "database_path": "erenshor-main-raw.sqlite",
        "database_size_bytes": 3,
        "scripts_count": 1,
        "scripts_size_bytes": 1,
        "total_size_bytes": 4,
        "clean_database_path": clean,
    }
    (backups / f"build-{build_id}" / "metadata.json").write_text(json.dumps(metadata))


def _changes_context(cli_context: CLIContext, tmp_path: Path) -> tuple[CLIContext, Path]:
    variant = cli_context.config.variants["main"]
    current = variant.resolved_database(cli_context.repo_root)
    current.unlink(missing_ok=True)
    _clean_db(current, "300", 12)
    return cli_context, variant.resolved_backups(cli_context.repo_root)


def test_changes_default_to_the_newest_earlier_build(cli_context: CLIContext, tmp_path: Path) -> None:
    context, backups = _changes_context(cli_context, tmp_path)
    _backup(backups, "100", item_level=5)
    _backup(backups, "200", item_level=10)
    _backup(backups, "300", item_level=12)

    result = CliRunner().invoke(extract.app, ["changes"], obj=context)

    assert result.exit_code == 0, result.output
    assert "main build 200 → main build 300" in result.stdout
    assert "stable_key=item:sword: item_level: 10 → 12" in result.stdout


def test_changes_since_an_explicit_build(cli_context: CLIContext, tmp_path: Path) -> None:
    context, backups = _changes_context(cli_context, tmp_path)
    _backup(backups, "100", item_level=5)
    _backup(backups, "200", item_level=10)

    result = CliRunner().invoke(extract.app, ["changes", "--since", "100"], obj=context)

    assert result.exit_code == 0, result.output
    assert "item_level: 5 → 12" in result.stdout


def test_changes_name_a_backup_without_a_clean_database(cli_context: CLIContext, tmp_path: Path) -> None:
    context, backups = _changes_context(cli_context, tmp_path)
    _backup(backups, "200", item_level=None)

    result = CliRunner().invoke(extract.app, ["changes"], obj=context)

    assert result.exit_code == 1
    assert "build-200" in result.output
    assert "holds no clean database" in result.output


def test_changes_without_an_earlier_build(cli_context: CLIContext, tmp_path: Path) -> None:
    context, backups = _changes_context(cli_context, tmp_path)
    _backup(backups, "300", item_level=12)

    result = CliRunner().invoke(extract.app, ["changes"], obj=context)

    assert result.exit_code == 1
    assert "No earlier build is backed up" in result.output
