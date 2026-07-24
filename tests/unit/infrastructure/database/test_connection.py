"""Lifecycle tests for the cached database connection."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.infrastructure.database.connection import DatabaseConnection


def test_connect_reuses_the_same_cached_handle(tmp_path: Path) -> None:
    """Separate connect scopes reuse one lazily-created SQLite handle."""
    db = DatabaseConnection(tmp_path / "lifecycle.sqlite")

    with db.connect() as first:
        first.execute("CREATE TABLE values_table (value INTEGER)")

    with db.connect() as second:
        assert second is first
        second.execute("INSERT INTO values_table VALUES (1)")

    db.close()


def test_connect_scope_does_not_close_cached_handle(tmp_path: Path) -> None:
    """Leaving connect() keeps the cached handle open for later use."""
    db = DatabaseConnection(tmp_path / "lifecycle.sqlite")

    with db.connect() as connection:
        connection.execute("CREATE TABLE values_table (value INTEGER)")

    assert connection.execute("SELECT COUNT(*) FROM values_table").fetchone()[0] == 0

    db.close()


def test_close_is_idempotent_and_clears_cached_handle(tmp_path: Path) -> None:
    """Repeated close calls are safe and clear the cached connection."""
    db = DatabaseConnection(tmp_path / "lifecycle.sqlite")
    with db.connect() as connection:
        pass

    db.close()
    db.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")

    with db.connect() as reopened:
        assert reopened is not connection
        assert reopened.execute("SELECT 1").fetchone()[0] == 1
    db.close()


def test_outer_context_closes_cached_handle(tmp_path: Path) -> None:
    """The manager context owns cleanup after inner connect scopes finish."""
    with DatabaseConnection(tmp_path / "lifecycle.sqlite") as db, db.connect() as connection:
        connection.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
