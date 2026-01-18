"""Integration tests for sheets SQL queries.

These tests verify that all SQL queries in src/erenshor/application/sheets/queries/
execute successfully against real exported databases. Tests focus on:

1. Query execution without errors
2. Expected columns exist in results
3. MapLink URLs use new ?marker= format (not old ?coordinateId=)

Tests do NOT assert specific row counts since those vary with each export.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# Path to SQL query files
QUERIES_DIR = Path(__file__).parent.parent.parent / "src/erenshor/application/sheets/queries"

# All sheet SQL query files
ALL_QUERIES = [
    "achievement-triggers",
    "ascensions",
    "books",
    "character-dialogs",
    "characters",
    "classes",
    "drop-chances",
    "factions",
    "fishing",
    "guild-topics",
    "item-bags",
    "items",
    "mining-nodes",
    "quests",
    "secret-passages",
    "skills",
    "spawn-points",
    "spells",
    "stances",
    "teleports",
    "treasure-locations",
    "wishing-wells",
    "zones",
]

# Queries that have MapLink column with new ?marker= format
MAPLINK_QUERIES = {
    "achievement-triggers",
    "secret-passages",
    "spawn-points",
    "teleports",
    "treasure-locations",
    "wishing-wells",
}


class TestSheetsQueries:
    """Test all sheets SQL queries execute correctly against exported database."""

    @pytest.mark.parametrize("query_name", ALL_QUERIES)
    def test_query_executes_successfully(self, sheets_engine: Engine, query_name: str):
        """Verify query executes without error and returns columns.

        This test ensures each SQL query:
        - Parses correctly (no syntax errors)
        - Executes without database errors
        - Returns at least one column
        - References valid tables and columns

        Args:
            sheets_engine: SQLAlchemy engine for exported database
            query_name: Name of the query file (without .sql extension)
        """
        sql_file = QUERIES_DIR / f"{query_name}.sql"
        assert sql_file.exists(), f"Query file not found: {sql_file}"

        query = sql_file.read_text(encoding="utf-8").strip()
        assert query, f"Query file is empty: {sql_file}"

        with sheets_engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())

            # Should have at least one column
            assert len(columns) > 0, f"{query_name} returned no columns"

            # Fetch to ensure no runtime errors during iteration
            # We don't assert row count since it varies with exports
            rows = result.fetchall()

            # Just verify it's iterable and doesn't crash
            assert isinstance(rows, list)

    @pytest.mark.parametrize("query_name", list(MAPLINK_QUERIES))
    def test_maplink_uses_new_format(self, sheets_engine: Engine, query_name: str):
        """Verify MapLink URLs use new ?marker= format instead of old ?coordinateId=.

        After the stable keys migration, all MapLink URLs should use:
        - New format: ?marker=<stableKey>
        - NOT old format: ?coordinateId=<number>

        Args:
            sheets_engine: SQLAlchemy engine for exported database
            query_name: Name of the query file (must be in MAPLINK_QUERIES set)
        """
        sql_file = QUERIES_DIR / f"{query_name}.sql"
        query = sql_file.read_text(encoding="utf-8").strip()

        with sheets_engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())

            # Verify MapLink column exists
            assert "MapLink" in columns, f"{query_name} missing MapLink column"

            maplink_idx = columns.index("MapLink")
            for row in result:
                url = row[maplink_idx]
                if url:  # May be NULL for some rows
                    # Should use new ?marker= format
                    assert "?marker=" in url, f"{query_name}: Expected ?marker= in MapLink URL: {url}"

                    # Should NOT use old ?coordinateId= format
                    assert "?coordinateId=" not in url, (
                        f"{query_name}: Found old ?coordinateId= format in MapLink URL: {url}"
                    )

    def test_all_query_files_exist(self):
        """Verify all expected query files exist in the queries directory.

        This is a sanity check to ensure the test suite is kept in sync with
        actual query files. If this test fails, update the ALL_QUERIES list.
        """
        actual_queries = sorted([f.stem for f in QUERIES_DIR.glob("*.sql")])
        expected_queries = sorted(ALL_QUERIES)

        missing = set(expected_queries) - set(actual_queries)
        extra = set(actual_queries) - set(expected_queries)

        assert not missing, f"Tests missing for queries: {missing}"
        assert not extra, f"Queries not tested: {extra}. Update ALL_QUERIES list."
