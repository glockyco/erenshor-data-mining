"""Golden baseline capture command.

Captures the current pipeline output as golden baseline files used by
regression tests to detect unintended changes during the pipeline rewrite.

Three output types are captured:
  - Wiki pages: one .txt file per page title (copied from generated/)
  - Sheets: one CSV per SQL query (23 files)
  - Map spawn-points: full spawn-points query output as CSV

Run this once before any pipeline changes. The captured files are committed
to tests/golden/ and become the regression baseline.
"""

from __future__ import annotations

import csv
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from sqlalchemy import create_engine

from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="golden",
    help="Capture and manage golden baseline outputs for regression testing",
    no_args_is_help=True,
)

console = Console()

# SQL that mirrors the TypeScript map spawn-points query in database.base.ts.
# Run without a scene filter to capture all rows; Scene column added so the
# regression test can verify per-scene correctness.
#
# Uses GROUP_CONCAT aggregate ORDER BY syntax for deterministic patrol paths.
_MAP_SPAWN_POINTS_SQL = """
WITH rep_groups AS (
    SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
    FROM character_deduplications d
    WHERE d.is_map_visible = 1
    GROUP BY d.group_key
)
SELECT
    cs.scene                        AS Scene,
    cs.spawn_point_stable_key       AS StableKey,
    cs.x                            AS PositionX,
    cs.y                            AS PositionY,
    cs.z                            AS PositionZ,
    cs.spawn_delay_4                AS SpawnDelay,
    cs.is_enabled                   AS IsEnabled,
    cs.night_spawn                  AS IsNightSpawn,
    cs.random_wander_range          AS WanderRange,
    cs.loop_patrol                  AS LoopPatrol,
    (
        SELECT GROUP_CONCAT(pp.x || ',' || pp.z, ';' ORDER BY pp.sequence_index)
        FROM spawn_point_patrol_points pp
        WHERE pp.spawn_point_stable_key = cs.spawn_point_stable_key
    )                               AS PatrolPath,
    rep.display_name                AS NPCName,
    rep.stable_key                  AS CharacterStableKey,
    rep.level                       AS Level,
    rep.is_vendor                   AS IsVendor,
    rep.has_dialog                  AS HasDialog,
    rep.invulnerable                AS Invulnerable,
    sum(cs.spawn_chance)            AS SpawnChance,
    rep.is_common                   AS IsCommon,
    rep.is_rare                     AS IsRare,
    rep.is_unique                   AS IsUnique,
    min(rep.is_friendly)            AS IsFriendly
FROM rep_groups rg
JOIN characters rep ON rep.stable_key = rg.rep_stable_key
JOIN character_deduplications d ON d.group_key = rg.group_key AND d.is_map_visible = 1
JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
WHERE cs.spawn_chance > 0
  AND cs.spawn_point_stable_key IS NOT NULL
GROUP BY cs.spawn_point_stable_key, rep.stable_key
ORDER BY cs.scene, cs.spawn_point_stable_key, rep.stable_key
"""


def _golden_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "golden"


def _capture_wiki(generated_dir: Path, golden_wiki_dir: Path, dry_run: bool) -> int:
    """Copy wiki generated .txt files to golden/wiki/."""
    if not generated_dir.exists():
        raise FileNotFoundError(
            f"Wiki generated directory not found: {generated_dir}\nRun 'erenshor wiki generate' first."
        )

    txt_files = sorted(generated_dir.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {generated_dir}\nRun 'erenshor wiki generate' first.")

    if not dry_run:
        parent = golden_wiki_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            tmp_dir = Path(tmp)
            for src in txt_files:
                shutil.copy2(src, tmp_dir / src.name)
            if golden_wiki_dir.exists():
                shutil.rmtree(golden_wiki_dir)
            shutil.move(str(tmp_dir), golden_wiki_dir)

    return len(txt_files)


def _capture_sheets(
    db_path: Path, queries_dir: Path, golden_sheets_dir: Path, dry_run: bool, *, map_base_url: str
) -> int:
    """Run all sheet queries and write CSVs to golden/sheets/."""
    engine = create_engine(f"sqlite:///{db_path}")
    formatter = SheetsFormatter(engine=engine, queries_dir=queries_dir, map_base_url=map_base_url)
    sheet_names = formatter.get_sheet_names()

    if not dry_run:
        golden_sheets_dir.mkdir(parents=True, exist_ok=True)

    for sheet_name in sheet_names:
        rows = formatter.format_sheet(sheet_name)
        if not dry_run:
            csv_path = golden_sheets_dir / f"{sheet_name}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

    engine.dispose()
    return len(sheet_names)


def _capture_map(db_path: Path, golden_map_dir: Path, dry_run: bool) -> int:
    """Run the map spawn-points query and write to golden/map/spawn-points.csv."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(_MAP_SPAWN_POINTS_SQL)
        rows = cursor.fetchall()
        if not rows:
            raise ValueError("Map spawn-points query returned no rows — is the DB populated?")

        headers = list(rows[0].keys())
        data_rows = [list(row) for row in rows]

        if not dry_run:
            golden_map_dir.mkdir(parents=True, exist_ok=True)
            csv_path = golden_map_dir / "spawn-points.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data_rows)
    finally:
        conn.close()

    return len(data_rows)


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def capture(
    ctx: typer.Context,
) -> None:
    """Capture current pipeline output as golden regression baseline.

    Snapshots three output types into tests/golden/ before any pipeline
    changes are made. The captured files are committed to the repository
    and used by regression tests to detect unintended changes.

    Prerequisites:
      - 'erenshor wiki generate' must have been run for the current variant
      - The variant database must exist and be populated

    Captured outputs:
      - tests/golden/wiki/    — one .txt per wiki page (from wiki/generated/)
      - tests/golden/sheets/  — one CSV per SQL query (23 files)
      - tests/golden/map/     — spawn-points.csv (full map query output)

    Safe to re-run: overwrites any existing golden files.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    repo_root = cli_ctx.repo_root
    dry_run = cli_ctx.dry_run

    db_path = variant_config.resolved_database(repo_root)
    wiki_dir = variant_config.resolved_wiki(repo_root)
    generated_dir = wiki_dir / "generated"

    import erenshor.application.sheets

    queries_dir = Path(erenshor.application.sheets.__file__).parent / "queries"

    golden_dir = _golden_dir(repo_root)
    golden_wiki_dir = golden_dir / "wiki"
    golden_sheets_dir = golden_dir / "sheets"
    golden_map_dir = golden_dir / "map"

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Capturing Golden Baseline[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}" + (" [yellow](dry run)[/yellow]" if dry_run else ""),
            border_style="cyan",
        )
    )
    console.print()

    errors: list[str] = []

    # Wiki pages
    console.print("[bold]Wiki pages[/bold]")
    console.print(f"  Source:      {generated_dir}")
    console.print(f"  Destination: {golden_wiki_dir}")
    try:
        count = _capture_wiki(generated_dir, golden_wiki_dir, dry_run)
        status = "[dim](dry run)[/dim]" if dry_run else "[green]done[/green]"
        console.print(f"  {status} — {count} pages")
    except Exception as e:
        console.print(f"  [red]failed[/red] — {e}")
        logger.exception("Wiki golden capture failed")
        errors.append(f"wiki: {e}")
    console.print()

    # Sheets
    console.print("[bold]Sheets[/bold]")
    console.print(f"  Source:      {db_path}")
    console.print(f"  Destination: {golden_sheets_dir}")
    try:
        map_base_url = variant_config.maps.base_url
        count = _capture_sheets(db_path, queries_dir, golden_sheets_dir, dry_run, map_base_url=map_base_url)
        status = "[dim](dry run)[/dim]" if dry_run else "[green]done[/green]"
        console.print(f"  {status} — {count} queries")
    except Exception as e:
        console.print(f"  [red]failed[/red] — {e}")
        logger.exception("Sheets golden capture failed")
        errors.append(f"sheets: {e}")
    console.print()

    # Map
    console.print("[bold]Map spawn-points[/bold]")
    console.print(f"  Source:      {db_path}")
    console.print(f"  Destination: {golden_map_dir / 'spawn-points.csv'}")
    try:
        count = _capture_map(db_path, golden_map_dir, dry_run)
        status = "[dim](dry run)[/dim]" if dry_run else "[green]done[/green]"
        console.print(f"  {status} — {count} rows")
    except Exception as e:
        console.print(f"  [red]failed[/red] — {e}")
        logger.exception("Map golden capture failed")
        errors.append(f"map: {e}")
    console.print()

    if errors:
        console.print(f"[red]Capture failed ({len(errors)} error(s)):[/red]")
        for err in errors:
            console.print(f"  - {err}")
        raise typer.Exit(1)

    if dry_run:
        console.print("[yellow]Dry run — no files written.[/yellow]")
    else:
        console.print(
            f"[green]Golden baseline captured to {golden_dir}[/green]\n"
            "Commit these files before making any pipeline changes."
        )
    console.print()
