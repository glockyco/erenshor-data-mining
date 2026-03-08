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
SELECT
    sp.Scene,
    sp.StableKey,
    sp.X AS PositionX,
    sp.Y AS PositionY,
    sp.Z AS PositionZ,
    sp.SpawnDelay4 AS SpawnDelay,
    sp.IsEnabled,
    sp.NightSpawn AS IsNightSpawn,
    sp.RandomWanderRange AS WanderRange,
    sp.LoopPatrol,
    (
        SELECT GROUP_CONCAT(pp.X || ',' || pp.Z, ';' ORDER BY pp.SequenceIndex)
        FROM SpawnPointPatrolPoints pp
        WHERE pp.SpawnPointStableKey = sp.StableKey
    ) AS PatrolPath,
    c.NPCName,
    c.StableKey AS CharacterStableKey,
    c.Level,
    c.IsVendor,
    c.HasDialog,
    c.Invulnerable,
    sum(spc.SpawnChance) AS SpawnChance,
    c.IsCommon,
    c.IsRare,
    c.IsUnique,
    min(c.IsFriendly) AS IsFriendly
FROM SpawnPoints sp
JOIN SpawnPointCharacters spc ON spc.SpawnPointStableKey = sp.StableKey
JOIN Characters c ON c.StableKey = spc.CharacterStableKey
WHERE spc.SpawnChance > 0
GROUP BY sp.StableKey, c.StableKey
ORDER BY sp.Scene, sp.StableKey, c.StableKey
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
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{DB_PATH}")
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

        formatter = SheetsFormatter(engine=golden_sheets_engine, queries_dir=QUERIES_DIR)
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

        formatter = SheetsFormatter(engine=golden_sheets_engine, queries_dir=QUERIES_DIR)
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
