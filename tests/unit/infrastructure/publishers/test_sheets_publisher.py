"""Unit tests for GoogleSheetsPublisher."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError

from erenshor.infrastructure.publishers.sheets import (
    GoogleSheetsPublisher,
    PublishResult,
)


@pytest.fixture
def mock_credentials_file(tmp_path: Path) -> Path:
    """Create a temporary credentials file."""
    creds_file = tmp_path / "test-credentials.json"
    creds_file.write_text('{"type": "service_account", "client_email": "test@example.com"}')
    return creds_file


@pytest.fixture
def publisher(mock_credentials_file: Path) -> GoogleSheetsPublisher:
    """Create a publisher instance with mock credentials."""
    return GoogleSheetsPublisher(
        credentials_file=mock_credentials_file,
        batch_size=1000,
        max_retries=3,
        retry_delay=0.1,
    )


@pytest.fixture
def sample_rows() -> list[list[str | int]]:
    """Sample spreadsheet rows for testing."""
    return [
        ["ID", "Name", "Level"],  # Header
        ["item_1", "Sword", 10],
        ["item_2", "Shield", 15],
        ["item_3", "Potion", 5],
    ]


class TestGoogleSheetsPublisherInit:
    """Tests for GoogleSheetsPublisher initialization."""

    def test_init_creates_publisher(self, mock_credentials_file: Path) -> None:
        """Test that publisher can be initialized."""
        publisher = GoogleSheetsPublisher(
            credentials_file=mock_credentials_file,
            batch_size=500,
            max_retries=5,
            retry_delay=2.0,
        )

        assert publisher.credentials_file == mock_credentials_file
        assert publisher.batch_size == 500
        assert publisher.max_retries == 5
        assert publisher.retry_delay == 2.0
        assert publisher._service is None  # Lazy initialization

    def test_init_with_defaults(self, mock_credentials_file: Path) -> None:
        """Test that publisher uses default values."""
        publisher = GoogleSheetsPublisher(credentials_file=mock_credentials_file)

        assert publisher.batch_size == 1000
        assert publisher.max_retries == 3
        assert publisher.retry_delay == 1.0


class TestGoogleSheetsPublisherAuth:
    """Tests for GoogleSheetsPublisher authentication."""

    def test_get_service_lazy_initialization(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that service is lazily initialized."""
        assert publisher._service is None

        with (
            patch("erenshor.infrastructure.publishers.sheets.service_account"),
            patch("erenshor.infrastructure.publishers.sheets.build") as mock_build,
        ):
            mock_build.return_value = MagicMock()

            service = publisher._get_service()

            assert service is not None
            assert publisher._service is service  # Cached

    def test_get_service_reuses_cached_service(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that service is cached after first initialization."""
        mock_service = MagicMock()
        publisher._service = mock_service

        service = publisher._get_service()

        assert service is mock_service

    def test_get_service_missing_credentials_file(self, tmp_path: Path) -> None:
        """Test that missing credentials file raises error."""
        nonexistent_file = tmp_path / "nonexistent.json"
        publisher = GoogleSheetsPublisher(credentials_file=nonexistent_file)

        with pytest.raises(FileNotFoundError, match="Google credentials file not found"):
            publisher._get_service()

    def test_get_service_invalid_credentials(self, mock_credentials_file: Path) -> None:
        """Test that invalid credentials raise error."""
        publisher = GoogleSheetsPublisher(credentials_file=mock_credentials_file)

        with patch(
            "erenshor.infrastructure.publishers.sheets.service_account.Credentials.from_service_account_file"
        ) as mock_creds:
            mock_creds.side_effect = Exception("Invalid credentials")

            with pytest.raises(GoogleAuthError, match="Failed to authenticate"):
                publisher._get_service()

    def test_service_property_accessor(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that service property works."""
        with (
            patch("erenshor.infrastructure.publishers.sheets.service_account"),
            patch("erenshor.infrastructure.publishers.sheets.build") as mock_build,
        ):
            mock_build.return_value = MagicMock()

            service = publisher.service

            assert service is not None


class TestGoogleSheetsPublisherPublish:
    """Tests for GoogleSheetsPublisher publish method."""

    def test_publish_empty_rows_raises_error(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that publishing empty rows raises ValueError."""
        with pytest.raises(ValueError, match="Cannot publish empty rows"):
            publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=[],
            )

    def test_publish_dry_run_returns_success(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that dry run returns success without making API calls."""
        result = publisher.publish(
            spreadsheet_id="test123",
            sheet_name="TestSheet",
            rows=sample_rows,
            dry_run=True,
        )

        assert result.success is True
        assert result.row_count == 3  # Excludes header
        assert result.spreadsheet_id == "test123"
        assert result.sheet_name == "TestSheet"
        assert result.error is None

    def test_publish_without_table_calls_correct_methods(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that publish without table calls the right methods."""
        with (
            patch.object(publisher, "_get_sheet_tables", return_value=[]) as mock_get_tables,
            patch.object(publisher, "_publish_without_table") as mock_publish_without_table,
        ):
            result = publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=sample_rows,
            )

            mock_get_tables.assert_called_once_with("test123", "TestSheet")
            mock_publish_without_table.assert_called_once_with("test123", "TestSheet", sample_rows)
            assert result.success is True
            assert result.row_count == 3

    def test_publish_with_table_calls_correct_methods(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that publish with table calls the right methods."""
        mock_table = {
            "tableId": "table123",
            "range": {
                "sheetId": 0,
                "startRowIndex": 0,
                "endRowIndex": 10,
                "startColumnIndex": 0,
                "endColumnIndex": 5,
            },
        }

        with (
            patch.object(publisher, "_get_sheet_tables", return_value=[mock_table]) as mock_get_tables,
            patch.object(publisher, "_publish_with_table") as mock_publish_with,
        ):
            result = publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=sample_rows,
            )

            mock_get_tables.assert_called_once_with("test123", "TestSheet")
            mock_publish_with.assert_called_once_with("test123", "TestSheet", sample_rows, mock_table)
            assert result.success is True

    def test_publish_handles_http_error_403(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that 403 permission errors are handled gracefully."""
        mock_response = Mock()
        mock_response.status = 403
        mock_error = HttpError(resp=mock_response, content=b"Permission denied")

        with patch.object(publisher, "_get_sheet_tables", side_effect=mock_error):
            result = publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=sample_rows,
            )

            assert result.success is False
            assert result.row_count == 0
            assert "Permission denied" in result.error
            assert "Editor access" in result.error

    def test_publish_handles_generic_http_error(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that generic HTTP errors are handled gracefully."""
        mock_response = Mock()
        mock_response.status = 500
        mock_response.reason = "Internal Server Error"
        mock_error = HttpError(resp=mock_response, content=b"Server error")

        with patch.object(publisher, "_get_sheet_tables", side_effect=mock_error):
            result = publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=sample_rows,
            )

            assert result.success is False
            assert "500" in result.error
            assert "Internal Server Error" in result.error

    def test_publish_handles_generic_exception(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that generic exceptions are handled gracefully."""
        with patch.object(publisher, "_get_sheet_tables", side_effect=RuntimeError("Unexpected error")):
            result = publisher.publish(
                spreadsheet_id="test123",
                sheet_name="TestSheet",
                rows=sample_rows,
            )

            assert result.success is False
            assert "Unexpected error" in result.error


class TestGoogleSheetsPublisherWriteOperations:
    """Tests for write operation helper methods."""

    def test_clear_sheet_calls_api(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that clear_sheet makes correct API call."""
        mock_service = MagicMock()
        publisher._service = mock_service

        publisher._clear_sheet("test123", "TestSheet")

        # Verify API call
        mock_service.spreadsheets().values().clear.assert_called_once()
        call_args = mock_service.spreadsheets().values().clear.call_args[1]
        assert call_args["spreadsheetId"] == "test123"
        assert call_args["range"] == "TestSheet!A:ZZ"

    def test_write_rows_batched_calls_api(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that write_rows_batched makes correct API call."""
        mock_service = MagicMock()
        publisher._service = mock_service

        publisher._write_rows_batched("test123", "TestSheet", sample_rows)

        # Verify API call
        mock_service.spreadsheets().values().update.assert_called_once()
        call_args = mock_service.spreadsheets().values().update.call_args[1]
        assert call_args["spreadsheetId"] == "test123"
        assert call_args["range"] == "TestSheet!A1"
        assert call_args["valueInputOption"] == "RAW"
        assert call_args["body"]["values"] == sample_rows

    def test_write_rows_batched_retries_on_error(
        self, publisher: GoogleSheetsPublisher, sample_rows: list[list[str | int]]
    ) -> None:
        """Test that write_rows_batched retries on HTTP errors."""
        mock_service = MagicMock()
        publisher._service = mock_service

        # Fail twice, then succeed
        mock_response = Mock()
        mock_response.status = 500
        mock_error = HttpError(resp=mock_response, content=b"Server error")

        mock_update = mock_service.spreadsheets().values().update
        mock_update.side_effect = [
            mock_error,
            mock_error,
            MagicMock(),  # Success on third try
        ]

        publisher._write_rows_batched("test123", "TestSheet", sample_rows)

        # Should have retried 3 times
        assert mock_update.call_count == 3

    def test_format_header_applies_bold_formatting(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that format_header applies bold formatting to header row."""
        mock_service = MagicMock()
        publisher._service = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {
                    "properties": {
                        "title": "TestSheet",
                        "sheetId": 123,
                    }
                }
            ]
        }

        publisher._format_header("test123", "TestSheet")

        # Verify batchUpdate call
        mock_service.spreadsheets().batchUpdate.assert_called_once()
        call_args = mock_service.spreadsheets().batchUpdate.call_args[1]
        requests = call_args["body"]["requests"]

        assert len(requests) == 1
        assert "repeatCell" in requests[0]
        assert requests[0]["repeatCell"]["range"]["sheetId"] == 123
        assert requests[0]["repeatCell"]["range"]["startRowIndex"] == 0
        assert requests[0]["repeatCell"]["range"]["endRowIndex"] == 1
        assert requests[0]["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"]["bold"]


class TestGoogleSheetsPublisherTableDetection:
    """Tests for table detection."""

    def test_get_sheet_tables_returns_regular_tables(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that get_sheet_tables returns regular tables."""
        mock_service = MagicMock()
        publisher._service = mock_service

        mock_table = {
            "tableId": "table123",
            "range": {
                "sheetId": 0,
                "startRowIndex": 0,
                "endRowIndex": 10,
            },
        }

        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {
                    "properties": {"title": "TestSheet"},
                    "tables": [mock_table],
                }
            ]
        }

        tables = publisher._get_sheet_tables("test123", "TestSheet")

        assert len(tables) == 1
        assert tables[0] == mock_table

    def test_get_sheet_tables_returns_empty_list_when_no_tables(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that get_sheet_tables returns empty list when no tables exist."""
        mock_service = MagicMock()
        publisher._service = mock_service

        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {
                    "properties": {"title": "TestSheet"},
                }
            ]
        }

        tables = publisher._get_sheet_tables("test123", "TestSheet")

        assert tables == []

    def test_get_sheet_tables_returns_data_source_tables(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that get_sheet_tables returns data source tables."""
        mock_service = MagicMock()
        publisher._service = mock_service

        mock_table = {
            "tableId": "table123",
            "tableRange": {
                "sheetId": 0,
                "startRowIndex": 0,
                "endRowIndex": 10,
            },
        }

        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {
                    "properties": {"title": "TestSheet"},
                    "dataSourceTables": [mock_table],
                }
            ]
        }

        tables = publisher._get_sheet_tables("test123", "TestSheet")

        assert len(tables) == 1
        assert tables[0] == mock_table


class TestGoogleSheetsPublisherTestConnection:
    """Tests for test_connection method."""

    def test_test_connection_success(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that test_connection returns True on success."""
        with patch.object(publisher, "_get_service", return_value=MagicMock()):
            result = publisher.test_connection()

            assert result is True

    def test_test_connection_http_error(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that test_connection re-raises HTTP errors."""
        mock_response = Mock()
        mock_response.status = 403
        mock_error = HttpError(resp=mock_response, content=b"Permission denied")

        with patch.object(publisher, "_get_service", side_effect=mock_error), pytest.raises(HttpError):
            publisher.test_connection()

    def test_test_connection_generic_error(self, publisher: GoogleSheetsPublisher) -> None:
        """Test that test_connection re-raises generic errors."""
        with (
            patch.object(publisher, "_get_service", side_effect=RuntimeError("Network error")),
            pytest.raises(RuntimeError, match="Network error"),
        ):
            publisher.test_connection()


class TestPublishResult:
    """Tests for PublishResult dataclass."""

    def test_publish_result_success(self) -> None:
        """Test creating a successful PublishResult."""
        result = PublishResult(
            success=True,
            row_count=100,
            spreadsheet_id="test123",
            sheet_name="TestSheet",
        )

        assert result.success is True
        assert result.row_count == 100
        assert result.spreadsheet_id == "test123"
        assert result.sheet_name == "TestSheet"
        assert result.error is None

    def test_publish_result_failure(self) -> None:
        """Test creating a failed PublishResult."""
        result = PublishResult(
            success=False,
            row_count=0,
            spreadsheet_id="test123",
            sheet_name="TestSheet",
            error="Permission denied",
        )

        assert result.success is False
        assert result.row_count == 0
        assert result.error == "Permission denied"
