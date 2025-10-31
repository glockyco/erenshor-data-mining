"""Database precondition checks.

Check functions for database existence, validity, and content.
These checks ensure the SQLite database is present and usable
before running commands that depend on it.
"""

import sqlite3
from pathlib import Path
from typing import Any

from ..base import PreconditionResult


def database_exists(context: dict[str, Any]) -> PreconditionResult:
    """Check if SQLite database file exists.

    Args:
        context: Check context containing 'database_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    db_path = Path(context["database_path"])

    if not db_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="database_exists",
            message="Database not found",
            detail=f"Missing: {db_path}\nRun 'erenshor extract export' to create database",
        )

    return PreconditionResult(
        passed=True,
        check_name="database_exists",
        message=f"Database exists: {db_path.name}",
    )


def database_valid(context: dict[str, Any]) -> PreconditionResult:
    """Check if database is a valid SQLite file.

    This check attempts to open the database and query the schema
    to ensure it's a valid SQLite database and not corrupted.

    Args:
        context: Check context containing 'database_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    db_path = Path(context["database_path"])

    # First check if file exists
    if not db_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="database_valid",
            message="Cannot validate database: file not found",
            detail=f"Missing: {db_path}",
        )

    # Try to open and query the database
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Query schema to ensure it's a valid SQLite DB
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        cursor.fetchone()
        conn.close()
    except sqlite3.DatabaseError as e:
        return PreconditionResult(
            passed=False,
            check_name="database_valid",
            message="Database is corrupted or invalid",
            detail=f"Error: {e}\nTry re-running 'erenshor extract export' to recreate database",
        )
    except Exception as e:
        return PreconditionResult(
            passed=False,
            check_name="database_valid",
            message="Failed to validate database",
            detail=f"Unexpected error: {e}",
        )

    return PreconditionResult(
        passed=True,
        check_name="database_valid",
        message="Database is valid",
    )


def database_has_items(context: dict[str, Any]) -> PreconditionResult:
    """Check if database contains items.

    This check verifies that the database has been populated with
    data by checking if the Item table has rows.

    Args:
        context: Check context containing 'database_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    db_path = Path(context["database_path"])

    # First check if file exists
    if not db_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="database_has_items",
            message="Cannot check database: file not found",
            detail=f"Missing: {db_path}",
        )

    # Check if Item table has data
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if Items table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Items'")
        if not cursor.fetchone():
            conn.close()
            return PreconditionResult(
                passed=False,
                check_name="database_has_items",
                message="Database has no Items table",
                detail="Database may be empty or from old export\nRun 'erenshor extract export' to populate",
            )

        # Count items
        cursor.execute("SELECT COUNT(*) FROM Items")
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            return PreconditionResult(
                passed=False,
                check_name="database_has_items",
                message="Database is empty (no items found)",
                detail="Run 'erenshor extract export' to populate database with game data",
            )

        return PreconditionResult(
            passed=True,
            check_name="database_has_items",
            message=f"Database has {count} items",
        )

    except sqlite3.Error as e:
        return PreconditionResult(
            passed=False,
            check_name="database_has_items",
            message="Failed to check database content",
            detail=f"SQL error: {e}",
        )
    except Exception as e:
        return PreconditionResult(
            passed=False,
            check_name="database_has_items",
            message="Failed to check database content",
            detail=f"Unexpected error: {e}",
        )
