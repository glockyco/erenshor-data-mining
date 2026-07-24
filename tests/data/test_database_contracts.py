"""Canonical clean-database integrity contracts.

These checks belong to the ``test data`` leaf rather than a standalone
validator script.  The clean schema keys rows by ``stable_key`` but keeps the
game's numeric identifiers as ordinary columns, so duplicate numeric IDs can
otherwise pass SQLite constraints and leak into downstream consumers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

import pytest

# The source export treats these identifiers as unique within their entity
# table.  They are deliberately not schema-primary keys because stable_key is
# the canonical repository identity.
_DUPLICATE_IDENTIFIER_CHECKS: Final[tuple[tuple[str, str], ...]] = (
    ("items", "id"),
    ("spells", "id"),
    ("skills", "id"),
    ("quest_variants", "quest_db_index"),
)


def _duplicate_identifier_rows(db_path: Path, table: str, column: str) -> list[tuple[object, int]]:
    """Return duplicate nonblank identifier values from one clean table."""
    # Table and column names come only from _DUPLICATE_IDENTIFIER_CHECKS.
    predicate = f"{column} IS NOT NULL AND {column} != ''" if column == "id" else f"{column} IS NOT NULL"
    with sqlite3.connect(db_path) as connection:
        return list(
            connection.execute(
                f"""
                SELECT {column}, COUNT(*)
                FROM {table}
                WHERE {predicate}
                GROUP BY {column}
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC, {column}
                """
            )
        )


def _assert_identifier_uniqueness(db_path: Path, table: str, column: str) -> None:
    duplicates = _duplicate_identifier_rows(db_path, table, column)
    assert not duplicates, f"{table}.{column} contains duplicate values: {duplicates}"


@pytest.mark.parametrize(
    ("table", "column"),
    _DUPLICATE_IDENTIFIER_CHECKS,
)
def test_main_clean_database_has_unique_numeric_identifiers(main_clean_db: Path, table: str, column: str) -> None:
    """Every retained game identifier is unique in the canonical clean DB."""
    _assert_identifier_uniqueness(main_clean_db, table, column)


@pytest.fixture(params=_DUPLICATE_IDENTIFIER_CHECKS)
def duplicate_identifier_fixture(tmp_path: Path, request: pytest.FixtureRequest) -> tuple[Path, str, str]:
    """Build one plausible duplicate-ID export for each retained invariant."""
    table, column = request.param
    db_path = tmp_path / f"duplicate-{table}.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(f"CREATE TABLE {table} (stable_key TEXT PRIMARY KEY, {column} INTEGER)")
        connection.executemany(
            f"INSERT INTO {table} (stable_key, {column}) VALUES (?, ?)",
            [("first", 314159), ("second", 314159)],
        )
        connection.commit()
    return db_path, table, column


def test_duplicate_identifier_fixture_fails_canonical_contract(
    duplicate_identifier_fixture: tuple[Path, str, str],
) -> None:
    """Each retained invariant has a focused fixture that the contract rejects."""
    db_path, table, column = duplicate_identifier_fixture
    with pytest.raises(AssertionError, match=rf"{table}\.{column}"):
        _assert_identifier_uniqueness(db_path, table, column)
