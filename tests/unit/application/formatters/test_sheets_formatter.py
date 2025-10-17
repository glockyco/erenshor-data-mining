"""Unit tests for SheetsFormatter."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from erenshor.application.formatters.sheets import SheetsFormatter


@pytest.fixture
def test_db(tmp_path: Path):
    """Create a test database with sample data."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    # Create test table
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE items (
                id TEXT PRIMARY KEY,
                name TEXT,
                level INTEGER,
                is_rare INTEGER
            )
        """
            )
        )
        conn.execute(
            text(
                """
            INSERT INTO items (id, name, level, is_rare)
            VALUES
                ('item_1', 'Sword', 10, 1),
                ('item_2', 'Shield', 15, 0),
                ('item_3', NULL, 5, 1)
        """
            )
        )
        conn.commit()

    return engine


@pytest.fixture
def queries_dir(tmp_path: Path) -> Path:
    """Create a temporary queries directory."""
    queries_path = tmp_path / "queries"
    queries_path.mkdir()

    # Create sample query files
    (queries_path / "items.sql").write_text("SELECT * FROM items ORDER BY level")
    (queries_path / "empty.sql").write_text("")
    (queries_path / "invalid.sql").write_text("INVALID SQL QUERY")

    return queries_path


@pytest.fixture
def formatter(test_db, queries_dir: Path) -> SheetsFormatter:
    """Create a formatter instance."""
    return SheetsFormatter(test_db, queries_dir)


class TestSheetsFormatterInit:
    """Tests for SheetsFormatter initialization."""

    def test_init_creates_formatter(self, test_db, queries_dir: Path) -> None:
        """Test that formatter can be initialized."""
        formatter = SheetsFormatter(test_db, queries_dir)

        assert formatter.engine == test_db
        assert formatter.queries_dir == queries_dir


class TestSheetsFormatterGetSheetNames:
    """Tests for get_sheet_names method."""

    def test_get_sheet_names_returns_all_sql_files(self, formatter: SheetsFormatter) -> None:
        """Test that get_sheet_names returns all .sql files."""
        sheet_names = formatter.get_sheet_names()

        assert len(sheet_names) == 3
        assert "items" in sheet_names
        assert "empty" in sheet_names
        assert "invalid" in sheet_names

    def test_get_sheet_names_sorted_alphabetically(self, formatter: SheetsFormatter) -> None:
        """Test that sheet names are sorted alphabetically."""
        sheet_names = formatter.get_sheet_names()

        assert sheet_names == ["empty", "invalid", "items"]

    def test_get_sheet_names_empty_directory(self, test_db, tmp_path: Path) -> None:
        """Test that get_sheet_names returns empty list for empty directory."""
        empty_dir = tmp_path / "empty_queries"
        empty_dir.mkdir()

        formatter = SheetsFormatter(test_db, empty_dir)
        sheet_names = formatter.get_sheet_names()

        assert sheet_names == []

    def test_get_sheet_names_nonexistent_directory(self, test_db, tmp_path: Path) -> None:
        """Test that get_sheet_names returns empty list for nonexistent directory."""
        nonexistent_dir = tmp_path / "nonexistent"

        formatter = SheetsFormatter(test_db, nonexistent_dir)
        sheet_names = formatter.get_sheet_names()

        assert sheet_names == []


class TestSheetsFormatterFormatSheet:
    """Tests for format_sheet method."""

    def test_format_sheet_returns_headers_and_data(self, formatter: SheetsFormatter) -> None:
        """Test that format_sheet returns headers and data rows."""
        rows = formatter.format_sheet("items")

        # Should have header + 3 data rows
        assert len(rows) == 4

        # Check headers
        assert rows[0] == ["id", "name", "level", "is_rare"]

        # Check data rows (sorted by level)
        assert rows[1][0] == "item_3"  # level 5
        assert rows[1][2] == 5
        assert rows[2][0] == "item_1"  # level 10
        assert rows[2][2] == 10
        assert rows[3][0] == "item_2"  # level 15
        assert rows[3][2] == 15

    def test_format_sheet_handles_null_values(self, formatter: SheetsFormatter) -> None:
        """Test that NULL values are converted to empty strings."""
        rows = formatter.format_sheet("items")

        # item_3 has NULL name
        assert rows[1][0] == "item_3"
        assert rows[1][1] == ""  # NULL converted to empty string

    def test_format_sheet_handles_boolean_values(self, formatter: SheetsFormatter) -> None:
        """Test that boolean values are preserved as integers (SQLite stores booleans as 0/1)."""
        rows = formatter.format_sheet("items")

        # is_rare column - SQLite returns integers, not booleans
        assert rows[1][3] == 1  # item_3 is rare (1)
        assert rows[2][3] == 1  # item_1 is rare (1)
        assert rows[3][3] == 0  # item_2 is not rare (0)

    def test_format_sheet_preserves_numbers(self, formatter: SheetsFormatter) -> None:
        """Test that numeric values are preserved as numbers."""
        rows = formatter.format_sheet("items")

        # level column should be integers
        assert isinstance(rows[1][2], int)
        assert rows[1][2] == 5
        assert isinstance(rows[2][2], int)
        assert rows[2][2] == 10

    def test_format_sheet_nonexistent_query_raises_error(self, formatter: SheetsFormatter) -> None:
        """Test that nonexistent query file raises ValueError."""
        with pytest.raises(ValueError, match="Query file 'nonexistent.sql' not found"):
            formatter.format_sheet("nonexistent")

    def test_format_sheet_empty_query_raises_error(self, formatter: SheetsFormatter) -> None:
        """Test that empty query file raises ValueError."""
        with pytest.raises(ValueError, match="Query file 'empty.sql' is empty"):
            formatter.format_sheet("empty")

    def test_format_sheet_invalid_sql_raises_error(self, formatter: SheetsFormatter) -> None:
        """Test that invalid SQL raises an error."""
        # SQLite will raise an OperationalError for invalid SQL
        with pytest.raises(Exception):  # noqa: B017  # Could be OperationalError or similar
            formatter.format_sheet("invalid")


class TestSheetsFormatterFormatAllSheets:
    """Tests for format_all_sheets method."""

    def test_format_all_sheets_returns_dict(self, formatter: SheetsFormatter) -> None:
        """Test that format_all_sheets returns a dictionary."""
        # Remove invalid queries for this test
        (formatter.queries_dir / "empty.sql").unlink()
        (formatter.queries_dir / "invalid.sql").unlink()

        results = formatter.format_all_sheets()

        assert isinstance(results, dict)
        assert "items" in results

    def test_format_all_sheets_includes_all_valid_sheets(self, formatter: SheetsFormatter) -> None:
        """Test that format_all_sheets processes all valid sheets."""
        # Remove invalid queries
        (formatter.queries_dir / "empty.sql").unlink()
        (formatter.queries_dir / "invalid.sql").unlink()

        results = formatter.format_all_sheets()

        assert len(results) == 1
        assert "items" in results
        assert len(results["items"]) == 4  # header + 3 rows


class TestSheetsFormatterGetRowCount:
    """Tests for get_row_count method."""

    def test_get_row_count_returns_data_rows_only(self, formatter: SheetsFormatter) -> None:
        """Test that get_row_count excludes header row."""
        count = formatter.get_row_count("items")

        assert count == 3  # 3 data rows, excluding header

    def test_get_row_count_for_empty_result(self, test_db, queries_dir: Path) -> None:
        """Test that get_row_count returns 0 for empty results."""
        # Create query that returns no rows
        (queries_dir / "empty_result.sql").write_text("SELECT * FROM items WHERE 1=0")

        formatter = SheetsFormatter(test_db, queries_dir)
        count = formatter.get_row_count("empty_result")

        assert count == 0


class TestSheetsFormatterFormatValue:
    """Tests for _format_value method."""

    def test_format_value_none_to_empty_string(self, formatter: SheetsFormatter) -> None:
        """Test that None is converted to empty string."""
        result = formatter._format_value(None)

        assert result == ""

    def test_format_value_bool_true_to_string(self, formatter: SheetsFormatter) -> None:
        """Test that True is converted to 'TRUE' string."""
        result = formatter._format_value(True)

        assert result == "TRUE"

    def test_format_value_bool_false_to_string(self, formatter: SheetsFormatter) -> None:
        """Test that False is converted to 'FALSE' string."""
        result = formatter._format_value(False)

        assert result == "FALSE"

    def test_format_value_int_preserved(self, formatter: SheetsFormatter) -> None:
        """Test that integers are preserved."""
        result = formatter._format_value(42)

        assert result == 42
        assert isinstance(result, int)

    def test_format_value_float_preserved(self, formatter: SheetsFormatter) -> None:
        """Test that floats are preserved."""
        result = formatter._format_value(3.14)

        assert result == 3.14
        assert isinstance(result, float)

    def test_format_value_string_preserved(self, formatter: SheetsFormatter) -> None:
        """Test that strings are preserved."""
        result = formatter._format_value("test")

        assert result == "test"
        assert isinstance(result, str)

    def test_format_value_converts_other_types_to_string(self, formatter: SheetsFormatter) -> None:
        """Test that other types are converted to strings."""
        # Test with a list
        result = formatter._format_value([1, 2, 3])

        assert result == "[1, 2, 3]"
        assert isinstance(result, str)


class TestSheetsFormatterIntegrationWithRealQueries:
    """Integration tests with actual query files."""

    def test_format_sheet_with_production_queries(self) -> None:
        """Test formatter with production query files."""
        # Use actual queries directory from project
        queries_dir = Path("src/erenshor/application/formatters/sheets/queries")

        if not queries_dir.exists():
            pytest.skip("Production queries directory not found")

        # Create in-memory database (won't have data, just testing file loading)
        engine = create_engine("sqlite:///:memory:")

        formatter = SheetsFormatter(engine, queries_dir)
        sheet_names = formatter.get_sheet_names()

        # Should have 21 query files (as per test_sheets_formatter.py)
        assert len(sheet_names) >= 21

        # Check some expected sheets exist
        assert "items" in sheet_names
        assert "characters" in sheet_names
        assert "spells" in sheet_names
