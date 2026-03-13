"""Golden baseline regression tests.

These tests compare freshly generated pipeline output against the golden
baseline files captured in tests/golden/ before the pipeline rewrite began.

Any difference from the golden baseline is an unintended regression and
fails the test. Intentional changes (bug fixes) must be reflected by
re-running 'golden capture' and committing the updated golden files.

Run these tests after every significant pipeline change:
    uv run pytest tests/integration/test_golden.py -v

Prerequisites:
    - variants/main/erenshor-main.sqlite must exist (run extract export)
    - variants/main/wiki/generated/ must be populated (run wiki generate)
    - tests/golden/ must be populated (run golden capture)

All three tests are marked integration and are skipped when the required
files are absent.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
GOLDEN_WIKI_DIR = GOLDEN_DIR / "wiki"
GOLDEN_SHEETS_DIR = GOLDEN_DIR / "sheets"
GOLDEN_MAP_DIR = GOLDEN_DIR / "map"

QUERIES_DIR = REPO_ROOT / "src" / "erenshor" / "application" / "sheets" / "queries"
WIKI_GENERATED_DIR = REPO_ROOT / "variants" / "main" / "wiki" / "generated"
DB_PATH = REPO_ROOT / "variants" / "main" / "erenshor-main.sqlite"

# ---------------------------------------------------------------------------
# Map spawn-points SQL (mirrors database.base.ts, all scenes)
#
# Uses GROUP_CONCAT aggregate ORDER BY syntax for deterministic patrol paths.
# ---------------------------------------------------------------------------

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
JOIN character_spawns cs ON cs.character_stable_key = d.member_stable_key
WHERE cs.spawn_chance > 0
  AND cs.spawn_point_stable_key IS NOT NULL
GROUP BY cs.spawn_point_stable_key, rep.stable_key
ORDER BY cs.scene, cs.spawn_point_stable_key, rep.stable_key
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_golden_csv(path: Path) -> list[list[str]]:
    """Read a golden CSV file, returning all rows including the header."""
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def _rows_to_strings(rows: list[list]) -> list[list[str]]:
    """Convert all cell values to strings, mapping None to empty string."""
    return [[str(v) if v is not None else "" for v in row] for row in rows]


def _skip_if_missing(path: Path, description: str) -> None:
    if not path.exists():
        pytest.skip(f"{description} not found: {path}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden_sheets_engine():
    """SQLAlchemy engine connected to the main variant database."""
    _skip_if_missing(DB_PATH, "Main variant database")
    from typing import Any

    from sqlalchemy import create_engine, event

    engine = create_engine(f"sqlite:///{DB_PATH}")

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
        dbapi_connection.create_function(
            "map_marker_url",
            1,
            lambda key: f"https://erenshor-maps.wowmuch1.workers.dev/map?sel=marker:{key}",
        )

    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWikiGolden:
    """Regression tests for wiki page generation output."""

    def test_golden_dir_exists(self):
        """Skip clearly if golden capture has not been run."""
        if not GOLDEN_WIKI_DIR.exists():
            pytest.skip(
                f"Golden wiki directory not found: {GOLDEN_WIKI_DIR}\n"
                "Run 'uv run erenshor golden capture' before running regression tests."
            )

    def test_no_pages_missing(self):
        """Every page in the golden baseline must exist in the generated output."""
        _skip_if_missing(GOLDEN_WIKI_DIR, "Golden wiki directory")
        _skip_if_missing(WIKI_GENERATED_DIR, "Wiki generated directory")

        golden_files = {f.name for f in GOLDEN_WIKI_DIR.glob("*.txt")}
        generated_files = {f.name for f in WIKI_GENERATED_DIR.glob("*.txt")}

        missing = golden_files - generated_files
        assert not missing, (
            f"{len(missing)} wiki page(s) present in golden but missing from generated output:\n"
            + "\n".join(sorted(missing)[:20])
            + ("\n..." if len(missing) > 20 else "")
        )

    def test_no_unexpected_pages_added(self):
        """No new pages should appear that weren't in the golden baseline."""
        _skip_if_missing(GOLDEN_WIKI_DIR, "Golden wiki directory")
        _skip_if_missing(WIKI_GENERATED_DIR, "Wiki generated directory")

        golden_files = {f.name for f in GOLDEN_WIKI_DIR.glob("*.txt")}
        generated_files = {f.name for f in WIKI_GENERATED_DIR.glob("*.txt")}

        added = generated_files - golden_files
        assert not added, (
            f"{len(added)} wiki page(s) in generated output not present in golden baseline:\n"
            + "\n".join(sorted(added)[:20])
            + ("\n..." if len(added) > 20 else "")
        )

    def test_page_content_unchanged(self):
        """Every generated page must match its golden counterpart exactly."""
        _skip_if_missing(GOLDEN_WIKI_DIR, "Golden wiki directory")
        _skip_if_missing(WIKI_GENERATED_DIR, "Wiki generated directory")

        regressions: list[str] = []

        for golden_file in sorted(GOLDEN_WIKI_DIR.glob("*.txt")):
            generated_file = WIKI_GENERATED_DIR / golden_file.name
            if not generated_file.exists():
                continue  # caught by test_no_pages_missing

            from urllib.parse import unquote

            page_title = unquote(golden_file.stem)

            golden_content = golden_file.read_text(encoding="utf-8")
            generated_content = generated_file.read_text(encoding="utf-8")

            if golden_content != generated_content:
                regressions.append(page_title)

        assert not regressions, (
            f"{len(regressions)} wiki page(s) differ from golden baseline:\n"
            + "\n".join(sorted(regressions)[:20])
            + ("\n..." if len(regressions) > 20 else "")
        )


@pytest.mark.integration
class TestSheetsGolden:
    """Regression tests for sheets SQL query output."""

    def test_golden_dir_exists(self):
        """Skip clearly if golden capture has not been run."""
        if not GOLDEN_SHEETS_DIR.exists():
            pytest.skip(
                f"Golden sheets directory not found: {GOLDEN_SHEETS_DIR}\n"
                "Run 'uv run erenshor golden capture' before running regression tests."
            )

    def test_all_sheets_match_golden(self, golden_sheets_engine):
        """Every sheet query result must match the golden CSV exactly."""
        _skip_if_missing(GOLDEN_SHEETS_DIR, "Golden sheets directory")

        from erenshor.application.sheets.formatter import SheetsFormatter

        formatter = SheetsFormatter(
            engine=golden_sheets_engine,
            queries_dir=QUERIES_DIR,
            map_base_url="https://erenshor-maps.wowmuch1.workers.dev",
        )
        sheet_names = formatter.get_sheet_names()

        regressions: list[str] = []

        for sheet_name in sheet_names:
            golden_path = GOLDEN_SHEETS_DIR / f"{sheet_name}.csv"
            if not golden_path.exists():
                regressions.append(f"{sheet_name}: golden CSV not found")
                continue

            actual_rows = formatter.format_sheet(sheet_name)
            actual_as_strings = _rows_to_strings(actual_rows)
            golden_rows = _read_golden_csv(golden_path)

            if actual_as_strings != golden_rows:
                regressions.append(sheet_name)

        assert not regressions, f"{len(regressions)} sheet(s) differ from golden baseline:\n" + "\n".join(
            sorted(regressions)
        )

    def test_no_golden_sheets_missing(self, golden_sheets_engine):
        """Every golden CSV must correspond to an existing query."""
        _skip_if_missing(GOLDEN_SHEETS_DIR, "Golden sheets directory")

        from erenshor.application.sheets.formatter import SheetsFormatter

        formatter = SheetsFormatter(
            engine=golden_sheets_engine,
            queries_dir=QUERIES_DIR,
            map_base_url="https://erenshor-maps.wowmuch1.workers.dev",
        )
        current_sheets = set(formatter.get_sheet_names())
        golden_sheets = {f.stem for f in GOLDEN_SHEETS_DIR.glob("*.csv")}

        missing = golden_sheets - current_sheets
        assert not missing, f"Golden CSVs exist for queries that no longer exist: {missing}"


@pytest.mark.integration
class TestMapGolden:
    """Regression tests for the map spawn-points query output."""

    def test_golden_file_exists(self):
        """Skip clearly if golden capture has not been run."""
        golden_path = GOLDEN_MAP_DIR / "spawn-points.csv"
        if not golden_path.exists():
            pytest.skip(
                f"Golden map file not found: {golden_path}\n"
                "Run 'uv run erenshor golden capture' before running regression tests."
            )

    def test_spawn_points_match_golden(self):
        """The map spawn-points query result must match the golden CSV exactly."""
        _skip_if_missing(DB_PATH, "Main variant database")
        golden_path = GOLDEN_MAP_DIR / "spawn-points.csv"
        _skip_if_missing(golden_path, "Golden map spawn-points CSV")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(_MAP_SPAWN_POINTS_SQL)
            rows = cursor.fetchall()
            headers = list(rows[0].keys()) if rows else []
            actual_rows = [headers, *_rows_to_strings([list(row) for row in rows])]
        finally:
            conn.close()

        golden_rows = _read_golden_csv(golden_path)

        assert actual_rows == golden_rows, (
            f"Map spawn-points output differs from golden baseline.\n"
            f"Actual rows: {len(actual_rows) - 1}, Golden rows: {len(golden_rows) - 1}"
        )
