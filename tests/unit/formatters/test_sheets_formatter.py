"""Unit tests for SheetsFormatter with query files."""

from pathlib import Path

import pytest


def test_query_files_exist():
    """Test that all 23 query files exist."""
    queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

    expected_queries = [
        "achievement-triggers",
        "ascensions",
        "books",
        "character-dialogs",
        "characters",
        "classes",
        "drop-chances",
        "factions",
        "fishing",
        "item-bags",
        "items",
        "mining-nodes",
        "quests",
        "secret-passages",
        "skills",
        "spawn-points",
        "spells",
        "teleport-destinations",
        "teleports",
        "treasure-locations",
        "wishing-wells",
        "wiki-comparison",
        "zones",
    ]

    for query_name in expected_queries:
        query_file = queries_dir / f"{query_name}.sql"
        assert query_file.exists(), f"Query file {query_name}.sql not found"


def test_query_files_not_empty():
    """Test that all query files have content."""
    queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

    # Get all .sql files
    sql_files = list(queries_dir.glob("*.sql"))
    assert len(sql_files) == 23, f"Expected 23 query files, found {len(sql_files)}"

    for sql_file in sql_files:
        content = sql_file.read_text(encoding="utf-8").strip()
        assert content, f"Query file {sql_file.name} is empty"
        assert "SELECT" in content.upper(), f"Query file {sql_file.name} doesn't contain SELECT"


def test_sheets_formatter_get_sheet_names():
    """Test that SheetsFormatter can read sheet names from query files."""
    from erenshor.application.formatters.sheets import SheetsFormatter
    from sqlalchemy import create_engine

    # Use in-memory database for testing
    engine = create_engine("sqlite:///:memory:")
    queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

    formatter = SheetsFormatter(engine, queries_dir)
    sheet_names = formatter.get_sheet_names()

    # Should have 23 sheets
    assert len(sheet_names) == 23

    # Should be sorted alphabetically
    assert sheet_names[0] == "achievement-triggers"
    assert "items" in sheet_names
    assert "characters" in sheet_names


def test_sheets_formatter_validates_missing_file():
    """Test that SheetsFormatter raises error for missing query file."""
    from erenshor.application.formatters.sheets import SheetsFormatter
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

    formatter = SheetsFormatter(engine, queries_dir)

    with pytest.raises(ValueError, match="Query file 'nonexistent.sql' not found"):
        formatter.format_sheet("nonexistent")


def test_query_files_have_valid_sql():
    """Test that all query files contain valid SQL syntax (basic check)."""
    queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

    sql_files = list(queries_dir.glob("*.sql"))

    for sql_file in sql_files:
        content = sql_file.read_text(encoding="utf-8").strip()

        # Basic SQL validation
        upper_content = content.upper()

        # Should start with SELECT or WITH (for CTEs)
        assert (
            upper_content.startswith("SELECT") or upper_content.startswith("WITH")
        ), f"{sql_file.name} doesn't start with SELECT or WITH"

        # Should end with semicolon (optional but good practice)
        # Note: Not all queries have semicolons, so this is just a warning check
        if not content.endswith(";"):
            print(f"Warning: {sql_file.name} doesn't end with semicolon")
