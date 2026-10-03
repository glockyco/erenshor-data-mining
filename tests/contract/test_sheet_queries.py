"""Run every sheet query against the clean-database schema.

The sheet queries read the clean database, which CI does not have. The data
leaf runs them against a real build, but only on a machine with game data. A
query that names a renamed or dropped column therefore passed CI. SQLite
resolves every table and column when it prepares a statement, so running each
query against the empty schema that the writer creates catches that drift
without any game data.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

import erenshor.application.sheets as sheets_package
from erenshor.application.processor.writer import Writer
from erenshor.application.sheets.formatter import SheetsFormatter

QUERIES_DIR = Path(sheets_package.__file__).parent / "queries"


def test_every_sheet_query_runs_against_the_clean_schema(tmp_path: Path) -> None:
    database = tmp_path / "clean.sqlite"
    writer = Writer(database)
    writer.create_schema()
    writer.conn.close()
    formatter = SheetsFormatter(
        create_engine(f"sqlite:///{database}"), QUERIES_DIR, map_base_url="https://maps.example.invalid"
    )

    sheets = formatter.format_all_sheets()

    assert set(sheets) == {path.stem for path in QUERIES_DIR.glob("*.sql")}
    empty_headers = sorted(name for name, rows in sheets.items() if not rows or not rows[0])
    assert not empty_headers, f"Sheet queries without a header row: {empty_headers}"
