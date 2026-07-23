"""Golden baseline capture command.

Captures the current pipeline output as golden baseline files used by
regression tests to detect unintended changes during the pipeline rewrite.

Three output types are captured:
  - Wiki pages: representative exact snapshots plus a semantic all-page manifest
  - Sheets: one CSV per SQL query (23 files)
  - Map spawn-points: full spawn-points query output as CSV

Run this once before any pipeline changes. The captured files are committed
to tests/golden/ and become the regression baseline.
"""

from __future__ import annotations

import csv
import json
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from sqlalchemy import create_engine

from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.application.wiki.representative_samples import (
    load_representative_sample_spec,
    validate_representative_sample_content,
)
from erenshor.application.wiki.semantic_validation import (
    build_semantic_manifest,
    derive_corpus_expectations,
    validate_wiki_pages,
)
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.cli.commands.wiki import _build_link_audit_catalog
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

# Code facts are hardcoded game constants carried verbatim into the clean DB.
# code_facts_meta (assembly sha + extraction timestamp) is deliberately
# excluded — it is volatile and would reintroduce capture thrash.
_CODE_FACTS_SQL = "SELECT fact_id, key, value, value_type FROM code_facts ORDER BY fact_id, key"


_CAPTURED_FAMILIES = frozenset({"wiki", "sheets", "map", "code_facts"})


@dataclass(frozen=True, slots=True)
class _CaptureCounts:
    wiki_pages: int
    sheets: int
    map_rows: int
    code_facts_rows: int


class _GoldenCaptureError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__(f"Golden capture failed for {len(errors)} families")


def _golden_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "golden"


def _write_golden_csv(path: Path, rows: list[list[object]]) -> None:
    """Write hook-clean CSV goldens without changing cell values.

    csv.writer defaults to CRLF and leaves unquoted final cells ending in spaces
    as physical trailing whitespace. Quote every cell and force LF so regenerated
    golden files preserve game data while remaining commit-clean.
    """
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_ALL)
        writer.writerows(rows)


def _capture_wiki(
    generated_dir: Path,
    zone_dir: Path,
    sample_spec_path: Path,
    golden_wiki_dir: Path,
    dry_run: bool,
) -> int:
    """Copy only declared representative pages to the wiki golden family."""
    if not generated_dir.is_dir():
        raise FileNotFoundError(
            f"Wiki generated directory not found: {generated_dir}\nRun 'erenshor wiki generate' first."
        )

    spec = load_representative_sample_spec(sample_spec_path)
    sources: list[tuple[Path, str]] = []
    for sample in spec.samples:
        source = (
            zone_dir / f"{sample.title.replace(' ', '_')}.txt"
            if sample.generator == "zones"
            else generated_dir / f"{quote(sample.title, safe='_-.')}.txt"
        )
        if not source.is_file():
            raise FileNotFoundError(f"Representative wiki source missing for {sample.title!r}: {source}")
        sources.append((source, f"{quote(sample.title, safe='_-.')}.txt"))

    if not dry_run:
        parent = golden_wiki_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            staged_wiki = Path(temporary)
            for source, filename in sources:
                shutil.copy2(source, staged_wiki / filename)
            if golden_wiki_dir.exists():
                shutil.rmtree(golden_wiki_dir)
            shutil.move(str(staged_wiki), golden_wiki_dir)

    return len(sources)


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
            _write_golden_csv(csv_path, rows)

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
            _write_golden_csv(csv_path, [headers, *data_rows])
    finally:
        conn.close()

    return len(data_rows)


def _capture_code_facts(db_path: Path, golden_code_facts_dir: Path, dry_run: bool) -> int:
    """Run the code-facts query and write to golden/code_facts/code_facts.csv."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(_CODE_FACTS_SQL)
        rows = cursor.fetchall()
        if not rows:
            raise ValueError("Code-facts query returned no rows — run 'erenshor extract code-facts'?")

        headers = list(rows[0].keys())
        data_rows = [list(row) for row in rows]

        if not dry_run:
            golden_code_facts_dir.mkdir(parents=True, exist_ok=True)
            csv_path = golden_code_facts_dir / "code_facts.csv"
            _write_golden_csv(csv_path, [headers, *data_rows])
    finally:
        conn.close()

    return len(data_rows)


def _copy_uncaptured_baseline_entries(source: Path, destination: Path) -> None:
    """Carry checked-in specifications and other non-generated entries into a staged tree."""
    if not source.exists():
        return
    for entry in source.iterdir():
        if entry.name in _CAPTURED_FAMILIES:
            continue
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)


def _replace_golden_baseline(golden_dir: Path, populate: Callable[[Path], None]) -> None:
    """Populate a sibling tree and replace the baseline only after the callback succeeds."""
    parent = golden_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".golden-stage-", dir=parent) as temporary:
        transaction_dir = Path(temporary)
        staged = transaction_dir / "staged"
        backup = transaction_dir / "previous"
        staged.mkdir()
        populate(staged)

        had_baseline = golden_dir.exists()
        if had_baseline:
            golden_dir.rename(backup)
        try:
            staged.rename(golden_dir)
        except BaseException:
            if had_baseline and backup.exists():
                backup.rename(golden_dir)
            raise


def _validate_staged_baseline(
    staged: Path,
    *,
    counts: _CaptureCounts,
    cli_ctx: CLIContext,
    wiki_dir: Path,
) -> None:
    """Run every semantic and structural gate against the completed candidate tree."""
    storage = WikiStorage(wiki_dir)
    titles = storage.list_generated_titles()
    pages = storage.read_generated_pages(titles)
    expectations = derive_corpus_expectations(storage, titles)
    catalog = _build_link_audit_catalog(cli_ctx)
    validate_wiki_pages(
        pages,
        expectations=expectations,
        catalog_entries=catalog,
        planned_titles=titles,
        known_generated_titles=titles,
        variant=cli_ctx.variant,
    ).raise_for_errors()

    spec = load_representative_sample_spec(staged / "wiki-samples.json")
    expected_wiki_files = {f"{quote(sample.title, safe='_-.')}.txt" for sample in spec.samples}
    staged_wiki_dir = staged / "wiki"
    actual_wiki_files = {path.name for path in staged_wiki_dir.glob("*.txt")}
    if actual_wiki_files != expected_wiki_files or len(actual_wiki_files) != counts.wiki_pages:
        missing = sorted(expected_wiki_files - actual_wiki_files)
        extra = sorted(actual_wiki_files - expected_wiki_files)
        raise ValueError(f"Staged wiki inventory mismatch: missing={missing}, extra={extra}")

    for sample in spec.samples:
        staged_content = (staged_wiki_dir / f"{quote(sample.title, safe='_-.')}.txt").read_text(encoding="utf-8")
        if sample.generator == "zones":
            source_path = cli_ctx.repo_root / "wiki" / "zones" / f"{sample.title.replace(' ', '_')}.txt"
            if not source_path.is_file():
                raise ValueError(f"Representative zone output missing: {source_path}")
            source_content = source_path.read_text(encoding="utf-8")
        else:
            try:
                source_content = pages[sample.title]
            except KeyError as exc:
                raise ValueError(f"Representative wiki page missing: {sample.title!r}") from exc
        if staged_content != source_content:
            raise ValueError(f"Representative wiki snapshot changed while staging: {sample.title!r}")
        validate_representative_sample_content(sample, staged_content)

    manifest = build_semantic_manifest(pages, expectations=expectations, catalog_entries=catalog)
    manifest_path = staged_wiki_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Staged semantic wiki manifest did not round-trip")

    sheet_files = tuple((staged / "sheets").glob("*.csv"))
    if len(sheet_files) != counts.sheets or any(path.stat().st_size == 0 for path in sheet_files):
        raise ValueError(f"Staged sheet inventory is invalid: expected {counts.sheets}, found {len(sheet_files)}")
    for family, filename, expected_rows in (
        ("map", "spawn-points.csv", counts.map_rows),
        ("code_facts", "code_facts.csv", counts.code_facts_rows),
    ):
        path = staged / family / filename
        if expected_rows < 1 or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Staged {family} baseline is invalid: {path}")


def _capture_candidate_families(
    *,
    target: Path,
    display_target: Path,
    generated_dir: Path,
    repo_root: Path,
    db_path: Path,
    queries_dir: Path,
    map_base_url: str,
    dry_run: bool,
) -> _CaptureCounts:
    """Capture all generated families into one candidate root."""
    errors: list[str] = []
    counts = {"wiki": 0, "sheets": 0, "map": 0, "code_facts": 0}
    destinations = {
        "wiki": target / "wiki",
        "sheets": target / "sheets",
        "map": target / "map",
        "code_facts": target / "code_facts",
    }
    display_destinations = {name: display_target / name for name in destinations}
    status = "[dim](dry run)[/dim]" if dry_run else "[green]staged[/green]"

    captures: tuple[tuple[str, str, Path, str, Callable[[], int]], ...] = (
        (
            "wiki",
            "Wiki pages",
            generated_dir,
            "pages",
            lambda: _capture_wiki(
                generated_dir,
                repo_root / "wiki" / "zones",
                target / "wiki-samples.json",
                destinations["wiki"],
                dry_run,
            ),
        ),
        (
            "sheets",
            "Sheets",
            db_path,
            "queries",
            lambda: _capture_sheets(
                db_path,
                queries_dir,
                destinations["sheets"],
                dry_run,
                map_base_url=map_base_url,
            ),
        ),
        ("map", "Map spawn-points", db_path, "rows", lambda: _capture_map(db_path, destinations["map"], dry_run)),
        (
            "code_facts",
            "Code facts",
            db_path,
            "rows",
            lambda: _capture_code_facts(db_path, destinations["code_facts"], dry_run),
        ),
    )
    for name, label, source, unit, capture_family in captures:
        console.print(f"[bold]{label}[/bold]")
        console.print(f"  Source:      {source}")
        destination = display_destinations[name]
        if name in {"map", "code_facts"}:
            destination /= "spawn-points.csv" if name == "map" else "code_facts.csv"
        console.print(f"  Destination: {destination}")
        try:
            counts[name] = capture_family()
            console.print(f"  {status} — {counts[name]} {unit}")
        except Exception as exc:
            console.print(f"  [red]failed[/red] — {exc}")
            logger.exception(f"{label} golden capture failed")
            errors.append(f"{name}: {exc}")
        console.print()

    if errors:
        raise _GoldenCaptureError(errors)
    return _CaptureCounts(
        wiki_pages=counts["wiki"],
        sheets=counts["sheets"],
        map_rows=counts["map"],
        code_facts_rows=counts["code_facts"],
    )


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

    Snapshots four output types into tests/golden/ before any pipeline
    changes are made. The captured files are committed to the repository
    and used by regression tests to detect unintended changes.

    Prerequisites:
      - 'erenshor wiki generate' must have been run for the current variant
      - The variant database must exist and be populated

    Captured outputs:
      - tests/golden/wiki/    — representative page snapshots and semantic manifest
      - tests/golden/sheets/  — one CSV per SQL query (23 files)
      - tests/golden/map/     — spawn-points.csv (full map query output)
      - tests/golden/code_facts/ — code_facts.csv (hardcoded game constants)

    Safe to re-run: stages and validates every family before replacing the
    complete baseline tree. A failed capture leaves the prior tree unchanged.
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
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Capturing Golden Baseline[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}" + (" [yellow](dry run)[/yellow]" if dry_run else ""),
            border_style="cyan",
        )
    )
    console.print()

    try:
        if dry_run:
            _capture_candidate_families(
                target=golden_dir,
                display_target=golden_dir,
                generated_dir=generated_dir,
                repo_root=repo_root,
                db_path=db_path,
                queries_dir=queries_dir,
                map_base_url=variant_config.maps.base_url,
                dry_run=True,
            )
        else:

            def populate(staged: Path) -> None:
                _copy_uncaptured_baseline_entries(golden_dir, staged)
                counts = _capture_candidate_families(
                    target=staged,
                    display_target=golden_dir,
                    generated_dir=generated_dir,
                    repo_root=repo_root,
                    db_path=db_path,
                    queries_dir=queries_dir,
                    map_base_url=variant_config.maps.base_url,
                    dry_run=False,
                )
                _validate_staged_baseline(staged, counts=counts, cli_ctx=cli_ctx, wiki_dir=wiki_dir)

            _replace_golden_baseline(golden_dir, populate)
    except _GoldenCaptureError as exc:
        console.print(f"[red]Capture failed ({len(exc.errors)} error(s)):[/red]")
        for error in exc.errors:
            console.print(f"  - {error}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        logger.exception("Golden baseline validation or replacement failed")
        console.print(f"[red]Capture failed before baseline replacement:[/red] {exc}")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[yellow]Dry run — no files written.[/yellow]")
    else:
        console.print(
            f"[green]Golden baseline captured atomically to {golden_dir}[/green]\n"
            "Commit these files before making any pipeline changes."
        )
    console.print()
