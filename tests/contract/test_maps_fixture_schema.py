"""Pin the maps prerender fixture to the real clean-database schema.

The maps site is verified two different ways, against two different databases.
Locally ``erenshor maps build`` prerenders against the real clean DB, which has
every table. CI has no game data, so its prerender smoke builds against the
hand-written fixture in ``src/maps/tests/fixtures/map-database.sql``, which
carries only the subset the site reads.

Nothing else couples those two schemas. Rename or drop a column that the fixture
also names and the local build stays green -- it never reads the fixture --
while CI fails on a database the local workflow never touches. This test closes
that gap by asserting the fixture is a faithful subset of what the writer
actually produces, so the drift is caught by ``uv run pytest`` rather than by a
red pipeline.

A table missing from the fixture entirely is out of scope here and belongs to
the prerender smoke, which renders the pages and fails when a loader queries
something the fixture does not have.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.writer import Writer

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "src/maps/tests/fixtures/map-database.sql"


def _relation_names(conn: sqlite3.Connection) -> set[str]:
    """Every table and view name in a database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _columns(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Map every table in a database to its column names.

    Tables only. A view's columns resolve through its SELECT, which a schema
    created but never populated cannot always answer, and the fixture is free to
    satisfy a view with a plain table anyway.
    """
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return {
        str(table[0]): {str(column[1]) for column in conn.execute(f"PRAGMA table_info({table[0]})")} for table in tables
    }


@pytest.fixture(scope="module")
def clean_schema(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, set[str]], set[str]]:
    """Columns and relation names of the real clean database, from the writer's DDL."""
    writer = Writer(tmp_path_factory.mktemp("clean") / "clean.sqlite")
    writer.create_schema()
    try:
        return _columns(writer.conn), _relation_names(writer.conn)
    finally:
        writer.conn.close()


@pytest.fixture(scope="module")
def fixture_schema() -> dict[str, set[str]]:
    """Column names of the maps prerender fixture."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(FIXTURE.read_text(encoding="utf-8"))
        return _columns(conn)
    finally:
        conn.close()


def test_fixture_defines_only_real_tables(
    fixture_schema: dict[str, set[str]], clean_schema: tuple[dict[str, set[str]], set[str]]
) -> None:
    """Every fixture table exists in the database the pipeline actually writes."""
    _, relations = clean_schema
    unknown = sorted(set(fixture_schema) - relations)
    assert not unknown, (
        f"Maps fixture defines tables the clean DB does not have: {unknown}. "
        "Either the pipeline dropped them or the fixture invented them."
    )


def test_fixture_columns_match_the_clean_schema(
    fixture_schema: dict[str, set[str]], clean_schema: tuple[dict[str, set[str]], set[str]]
) -> None:
    """No fixture column drifts from its real counterpart.

    This is the failure that renaming ``game_build_updated_at`` would have caused:
    green locally, red in CI, on a schema the local build never reads.
    """
    clean_columns, _ = clean_schema
    drifted = {
        table: sorted(columns - clean_columns[table])
        for table, columns in fixture_schema.items()
        if table in clean_columns and columns - clean_columns[table]
    }
    assert not drifted, (
        f"Maps fixture columns absent from the clean DB: {drifted}. "
        "Update src/maps/tests/fixtures/map-database.sql to match the writer schema."
    )


def test_fixture_carries_the_footer_provenance() -> None:
    """The provenance row is load-bearing, not decorative.

    `getDataProvenance` runs in the (app) layout's server load, so a fixture
    without it does not merely drop the footer line -- it 500s every page in the
    group during prerender.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    assert "CREATE TABLE code_facts_meta" in text
    assert "INSERT INTO code_facts_meta" in text
