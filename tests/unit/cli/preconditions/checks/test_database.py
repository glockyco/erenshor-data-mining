"""Tests for database precondition checks."""

import sqlite3
from pathlib import Path

from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid


def test_database_exists_when_file_exists(tmp_path: Path):
    """Test database_exists passes when database file exists."""
    db_path = tmp_path / "test.sqlite"
    db_path.touch()

    context = {"database_path": db_path}
    result = database_exists(context)

    assert result.passed is True
    assert "exists" in result.message.lower()


def test_database_exists_when_file_missing(tmp_path: Path):
    """Test database_exists fails when database file is missing."""
    db_path = tmp_path / "nonexistent.sqlite"

    context = {"database_path": db_path}
    result = database_exists(context)

    assert result.passed is False
    assert "not found" in result.message.lower()
    assert str(db_path) in result.detail


def test_database_valid_with_valid_database(tmp_path: Path):
    """Test database_valid passes with valid SQLite database."""
    db_path = tmp_path / "test.sqlite"

    # Create valid SQLite database
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    context = {"database_path": db_path}
    result = database_valid(context)

    assert result.passed is True
    assert "valid" in result.message.lower()


def test_database_valid_with_missing_file(tmp_path: Path):
    """Test database_valid fails when file doesn't exist."""
    db_path = tmp_path / "nonexistent.sqlite"

    context = {"database_path": db_path}
    result = database_valid(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_database_valid_with_corrupted_file(tmp_path: Path):
    """Test database_valid fails with corrupted database file."""
    db_path = tmp_path / "corrupted.sqlite"

    # Create non-SQLite file
    db_path.write_text("This is not a SQLite database")

    context = {"database_path": db_path}
    result = database_valid(context)

    assert result.passed is False
    assert "corrupted" in result.message.lower() or "invalid" in result.message.lower()


def test_database_has_items_with_populated_database(tmp_path: Path):
    """Test database_has_items passes when Item table has data."""
    db_path = tmp_path / "test.sqlite"

    # Create database with items
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE Item (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO Item (id, name) VALUES (1, 'Test Item')")
    conn.execute("INSERT INTO Item (id, name) VALUES (2, 'Another Item')")
    conn.commit()
    conn.close()

    context = {"database_path": db_path}
    result = database_has_items(context)

    assert result.passed is True
    assert "2 items" in result.message.lower()


def test_database_has_items_with_empty_table(tmp_path: Path):
    """Test database_has_items fails when Item table is empty."""
    db_path = tmp_path / "test.sqlite"

    # Create database with empty Item table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE Item (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

    context = {"database_path": db_path}
    result = database_has_items(context)

    assert result.passed is False
    assert "empty" in result.message.lower()


def test_database_has_items_with_missing_table(tmp_path: Path):
    """Test database_has_items fails when Item table doesn't exist."""
    db_path = tmp_path / "test.sqlite"

    # Create database without Item table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE OtherTable (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    context = {"database_path": db_path}
    result = database_has_items(context)

    assert result.passed is False
    assert "no item table" in result.message.lower()


def test_database_has_items_with_missing_file(tmp_path: Path):
    """Test database_has_items fails when file doesn't exist."""
    db_path = tmp_path / "nonexistent.sqlite"

    context = {"database_path": db_path}
    result = database_has_items(context)

    assert result.passed is False
    assert "not found" in result.message.lower()
