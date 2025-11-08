"""Unit tests for SheetsService.

Tests the Google Sheets deployment orchestration service including:
- Listing available sheets
- Deploying specific sheets
- Deploying all sheets
- Error handling
- Dry-run mode
- Progress display
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from erenshor.application.sheets.service import (
    DeploymentResult,
    SheetMetadata,
    SheetsService,
    SheetsServiceError,
)
from erenshor.infrastructure.publishers.sheets import PublishResult


@pytest.fixture
def mock_formatter():
    """Mock SheetsFormatter."""
    formatter = Mock()
    formatter.queries_dir = Path("/fake/queries")
    formatter.get_sheet_names.return_value = []
    formatter.format_sheet.return_value = []
    return formatter


@pytest.fixture
def mock_publisher():
    """Mock GoogleSheetsPublisher."""
    publisher = Mock()
    return publisher


@pytest.fixture
def sheets_service(mock_formatter, mock_publisher):
    """SheetsService instance with mocked dependencies."""
    return SheetsService(
        formatter=mock_formatter,
        publisher=mock_publisher,
        spreadsheet_id="test-spreadsheet-id",
    )


@pytest.fixture
def sample_query_file(tmp_path):
    """Create a sample SQL query file."""
    query_file = tmp_path / "items.sql"
    query_file.write_text(
        """-- All items with stats
SELECT ItemName, ItemLevel, HP
FROM Items
ORDER BY ItemDBIndex;
"""
    )
    return query_file


class TestSheetsServiceInit:
    """Tests for SheetsService initialization."""

    def test_init_with_dependencies(self, mock_formatter, mock_publisher):
        """Test service initializes with all dependencies."""
        service = SheetsService(
            formatter=mock_formatter,
            publisher=mock_publisher,
            spreadsheet_id="abc123",
        )

        assert service._formatter == mock_formatter
        assert service._publisher == mock_publisher
        assert service._spreadsheet_id == "abc123"


class TestListSheets:
    """Tests for list_sheets method."""

    def test_empty_queries_directory(self, sheets_service, mock_formatter):
        """Test listing when no query files exist."""
        mock_formatter.get_sheet_names.return_value = []

        sheets = sheets_service.list_sheets()

        assert sheets == []

    def test_lists_available_sheets(self, sheets_service, mock_formatter, tmp_path):
        """Test listing available sheets from query files."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters", "spells"]
        mock_formatter.queries_dir = tmp_path

        # Create query files
        (tmp_path / "items.sql").write_text("-- All game items\nSELECT * FROM Items;")
        (tmp_path / "characters.sql").write_text("-- NPCs and enemies\nSELECT * FROM Characters;")
        (tmp_path / "spells.sql").write_text("SELECT * FROM Spells;")  # No comment

        sheets = sheets_service.list_sheets()

        assert len(sheets) == 3

        # Check items sheet
        items_sheet = next(s for s in sheets if s.name == "items")
        assert items_sheet.description == "All game items"
        assert items_sheet.query_file == tmp_path / "items.sql"
        assert items_sheet.row_count is None

        # Check characters sheet
        characters_sheet = next(s for s in sheets if s.name == "characters")
        assert characters_sheet.description == "NPCs and enemies"

        # Check spells sheet (fallback to filename)
        spells_sheet = next(s for s in sheets if s.name == "spells")
        assert spells_sheet.description == "Spells"  # Title case filename

    def test_extracts_description_from_comment(self, sheets_service, mock_formatter, tmp_path):
        """Test extracting description from SQL comment."""
        mock_formatter.get_sheet_names.return_value = ["test"]
        mock_formatter.queries_dir = tmp_path

        query_file = tmp_path / "test.sql"
        query_file.write_text(
            """-- This is the description
-- This is not the description
SELECT * FROM Test;
"""
        )

        sheets = sheets_service.list_sheets()

        assert len(sheets) == 1
        assert sheets[0].description == "This is the description"

    def test_handles_missing_description(self, sheets_service, mock_formatter, tmp_path):
        """Test fallback when no description comment found."""
        mock_formatter.get_sheet_names.return_value = ["drop-chances"]
        mock_formatter.queries_dir = tmp_path

        query_file = tmp_path / "drop-chances.sql"
        query_file.write_text("SELECT * FROM DropChances;")

        sheets = sheets_service.list_sheets()

        assert len(sheets) == 1
        assert sheets[0].description == "Drop Chances"  # Filename formatted


class TestDeploy:
    """Tests for deploy method."""

    def test_no_sheets_specified_raises_error(self, sheets_service):
        """Test error when no sheets specified and all_sheets=False."""
        with pytest.raises(SheetsServiceError, match="Must specify either"):
            sheets_service.deploy(sheet_names=None, all_sheets=False)

    def test_invalid_sheet_name_raises_error(self, sheets_service, mock_formatter):
        """Test error when invalid sheet name specified."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters"]

        with pytest.raises(SheetsServiceError, match="Invalid sheet names: invalid-sheet"):
            sheets_service.deploy(sheet_names=["invalid-sheet"])

    def test_deploy_specific_sheets(self, sheets_service, mock_formatter, mock_publisher):
        """Test deploying specific sheets."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters", "spells"]
        mock_formatter.format_sheet.return_value = [
            ["ID", "Name", "Level"],  # Header
            ["1", "Sword", "10"],
            ["2", "Shield", "5"],
        ]
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            row_count=2,
            spreadsheet_id="test-id",
            sheet_name="items",
        )

        result = sheets_service.deploy(sheet_names=["items", "characters"])

        assert result.total_sheets == 2
        assert result.deployed == 2
        assert result.failed == 0
        assert result.total_rows == 4  # 2 rows per sheet

        # Verify formatter called for each sheet
        assert mock_formatter.format_sheet.call_count == 2
        mock_formatter.format_sheet.assert_any_call("items")
        mock_formatter.format_sheet.assert_any_call("characters")

        # Verify publisher called for each sheet
        assert mock_publisher.publish.call_count == 2

    def test_deploy_all_sheets(self, sheets_service, mock_formatter, mock_publisher):
        """Test deploying all available sheets."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters"]
        mock_formatter.format_sheet.return_value = [
            ["ID", "Name"],
            ["1", "Test"],
        ]
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            row_count=1,
            spreadsheet_id="test-id",
            sheet_name="items",
        )

        result = sheets_service.deploy(all_sheets=True)

        assert result.total_sheets == 2
        assert result.deployed == 2
        assert result.failed == 0

    def test_dry_run_mode(self, sheets_service, mock_formatter, mock_publisher):
        """Test dry-run mode doesn't publish to Google Sheets."""
        mock_formatter.get_sheet_names.return_value = ["items"]
        mock_formatter.format_sheet.return_value = [
            ["ID", "Name"],
            ["1", "Sword"],
        ]

        result = sheets_service.deploy(sheet_names=["items"], dry_run=True)

        # Should format but not publish
        mock_formatter.format_sheet.assert_called_once_with("items")
        mock_publisher.publish.assert_not_called()

        # Should count as deployed (would have been deployed)
        assert result.total_sheets == 1
        assert result.deployed == 1
        assert result.failed == 0
        assert result.total_rows == 1

    def test_tracks_total_rows(self, sheets_service, mock_formatter, mock_publisher):
        """Test tracking total rows across multiple sheets."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters"]

        # Different row counts per sheet
        def format_sheet_side_effect(sheet_name):
            if sheet_name == "items":
                return [["ID"], ["1"], ["2"], ["3"]]  # 3 rows
            return [["ID"], ["1"], ["2"]]  # 2 rows

        mock_formatter.format_sheet.side_effect = format_sheet_side_effect
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            row_count=0,
            spreadsheet_id="test-id",
            sheet_name="test",
        )

        result = sheets_service.deploy(all_sheets=True)

        assert result.total_rows == 5  # 3 + 2

    def test_tracks_duration(self, sheets_service, mock_formatter, mock_publisher):
        """Test tracking deployment duration."""
        mock_formatter.get_sheet_names.return_value = ["items"]
        mock_formatter.format_sheet.return_value = [["ID"], ["1"]]
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            row_count=1,
            spreadsheet_id="test-id",
            sheet_name="items",
        )

        result = sheets_service.deploy(sheet_names=["items"])

        assert result.duration_seconds >= 0


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_continues_on_individual_failure(self, sheets_service, mock_formatter, mock_publisher):
        """Test service continues processing after individual sheet failure."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters", "spells"]
        mock_formatter.format_sheet.return_value = [["ID"], ["1"]]

        # First succeeds, second fails, third succeeds
        mock_publisher.publish.side_effect = [
            PublishResult(success=True, row_count=1, spreadsheet_id="test-id", sheet_name="items"),
            PublishResult(
                success=False, row_count=0, spreadsheet_id="test-id", sheet_name="characters", error="API error"
            ),
            PublishResult(success=True, row_count=1, spreadsheet_id="test-id", sheet_name="spells"),
        ]

        result = sheets_service.deploy(all_sheets=True)

        assert result.total_sheets == 3
        assert result.deployed == 2
        assert result.failed == 1
        assert result.has_errors()
        assert "Failed to deploy characters" in result.errors[0]

    def test_handles_formatter_error(self, sheets_service, mock_formatter, mock_publisher):
        """Test handling error during formatting."""
        mock_formatter.get_sheet_names.return_value = ["items", "characters"]

        # First sheet succeeds, second fails during formatting
        def format_sheet_side_effect(sheet_name):
            if sheet_name == "items":
                return [["ID"], ["1"]]
            raise ValueError("SQL syntax error")

        mock_formatter.format_sheet.side_effect = format_sheet_side_effect
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            row_count=1,
            spreadsheet_id="test-id",
            sheet_name="items",
        )

        result = sheets_service.deploy(all_sheets=True)

        assert result.total_sheets == 2
        assert result.deployed == 1
        assert result.failed == 1
        assert result.has_errors()
        assert "Error processing characters" in result.errors[0]

    def test_handles_publisher_exception(self, sheets_service, mock_formatter, mock_publisher):
        """Test handling exception during publishing."""
        mock_formatter.get_sheet_names.return_value = ["items"]
        mock_formatter.format_sheet.return_value = [["ID"], ["1"]]
        mock_publisher.publish.side_effect = Exception("Network timeout")

        result = sheets_service.deploy(sheet_names=["items"])

        assert result.total_sheets == 1
        assert result.deployed == 0
        assert result.failed == 1
        assert result.has_errors()
        assert "Network timeout" in result.errors[0]


class TestDeploymentResult:
    """Tests for DeploymentResult dataclass."""

    def test_has_errors(self):
        """Test has_errors method."""
        result = DeploymentResult(
            total_sheets=1,
            deployed=0,
            failed=1,
            total_rows=0,
            errors=["Error 1"],
            duration_seconds=1.0,
        )
        assert result.has_errors()

        result_no_errors = DeploymentResult(
            total_sheets=1,
            deployed=1,
            failed=0,
            total_rows=10,
            errors=[],
            duration_seconds=1.0,
        )
        assert not result_no_errors.has_errors()


class TestSheetMetadata:
    """Tests for SheetMetadata dataclass."""

    def test_metadata_fields(self):
        """Test SheetMetadata fields."""
        query_file = Path("/fake/items.sql")
        metadata = SheetMetadata(
            name="items",
            description="All game items",
            query_file=query_file,
            row_count=100,
        )

        assert metadata.name == "items"
        assert metadata.description == "All game items"
        assert metadata.query_file == query_file
        assert metadata.row_count == 100

    def test_metadata_optional_row_count(self):
        """Test row_count is optional."""
        metadata = SheetMetadata(
            name="items",
            description="All game items",
            query_file=Path("/fake/items.sql"),
        )

        assert metadata.row_count is None
