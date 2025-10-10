"""Google Sheets publisher for deploying data to spreadsheets.

This module provides the GoogleSheetsPublisher class that handles:
- Authentication with Google service account
- Clearing and updating spreadsheet tabs
- Batch writing of rows (handling large datasets)
- Applying formatting (bold headers, number formats)
- Table-aware publishing (preserves filters/sorting)
- Error handling and rate limiting
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

__all__ = [
    "GoogleSheetsPublisher",
    "PublishResult",
]


@dataclass
class PublishResult:
    """Result of a publish operation."""

    success: bool
    """Whether the operation succeeded."""

    row_count: int
    """Number of rows published (excluding header)."""

    spreadsheet_id: str
    """ID of the spreadsheet."""

    sheet_name: str
    """Name of the sheet tab."""

    error: str | None = None
    """Error message if success is False."""


class GoogleSheetsPublisher:
    """Publish data to Google Sheets via Google Sheets API.

    This publisher uses the Google Sheets API v4 with service account
    authentication to update spreadsheet data.

    Features:
    - Batch writing for efficient uploads (handles 10k+ rows)
    - Automatic retry with exponential backoff
    - Header row formatting (bold text)
    - Table-aware updates (preserves filters/sorting)
    - Clear existing data before writing
    - Rate limit handling

    Table-Aware Publishing:
    When a Google Sheets table exists on the target sheet, this publisher
    will update the table data while preserving filters and sorting. The
    table range will be automatically resized to match the new data size,
    and content below the table will shift up or down accordingly.

    Example:
        publisher = GoogleSheetsPublisher(
            credentials_file=Path("~/.config/erenshor/google-credentials.json"),
            batch_size=1000,
            max_retries=3,
        )

        rows = [
            ["ID", "Name", "Level"],  # Header
            ["item_1", "Sword", 10],
            ["item_2", "Shield", 15],
        ]

        result = publisher.publish(
            spreadsheet_id="abc123",
            sheet_name="Items",
            rows=rows,
        )
    """

    # Google Sheets API scope
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(
        self,
        credentials_file: Path,
        batch_size: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize publisher.

        Args:
            credentials_file: Path to Google service account JSON credentials
            batch_size: Number of rows to write per API call
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries (seconds), doubles each retry
        """
        self.credentials_file = credentials_file
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._service = None

    def _get_service(self) -> Any:
        """Lazy initialize Google Sheets service.

        Returns:
            Google Sheets API service instance

        Raises:
            GoogleAuthError: If credentials file is invalid
            FileNotFoundError: If credentials file doesn't exist
        """
        if self._service is None:
            if not self.credentials_file.exists():
                raise FileNotFoundError(
                    f"Google credentials file not found: {self.credentials_file}"
                )

            try:
                creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                    str(self.credentials_file),
                    scopes=self.SCOPES,
                )
                self._service = build("sheets", "v4", credentials=creds)
            except Exception as e:
                raise GoogleAuthError(  # type: ignore[no-untyped-call]
                    f"Failed to authenticate with Google: {e}"
                ) from e

        return self._service

    @property
    def service(self) -> Any:
        """Get Google Sheets service (public accessor).

        Returns:
            Google Sheets API service instance
        """
        return self._get_service()

    def publish(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[List[Any]],
        dry_run: bool = False,
    ) -> PublishResult:
        """Publish rows to a Google Sheets tab.

        This method intelligently handles table-aware publishing:
        1. Detects if a Google Sheets table exists on the sheet
        2. If table exists:
           - Updates table data while preserving filters/sorting
           - Resizes table range to match new data size
           - Shifts content below table up/down as needed
        3. If no table exists:
           - Clears existing data
           - Writes new data
           - Applies header formatting

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            rows: List of rows, where first row is headers
            dry_run: If True, don't actually write to sheets

        Returns:
            PublishResult with success status and metadata

        Raises:
            ValueError: If rows is empty
        """
        if not rows:
            raise ValueError("Cannot publish empty rows")

        if dry_run:
            return PublishResult(
                success=True,
                row_count=len(rows) - 1,  # Exclude header
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
            )

        try:
            # Detect if table exists on sheet
            tables = self._get_sheet_tables(spreadsheet_id, sheet_name)

            if tables:
                # Table-aware update: preserve filters/sorting
                logger.debug(f"Table detected on sheet '{sheet_name}', using table-aware update")
                self._publish_with_table(spreadsheet_id, sheet_name, rows, tables[0])
            else:
                # Standard update: clear and write
                logger.debug(f"No table on sheet '{sheet_name}', using standard update")
                self._publish_without_table(spreadsheet_id, sheet_name, rows)

            return PublishResult(
                success=True,
                row_count=len(rows) - 1,  # Exclude header
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
            )

        except HttpError as e:
            # Provide helpful error message for permission errors
            if e.status_code == 403:
                error_msg = (
                    f"Permission denied: Service account does not have Editor access to spreadsheet. "
                    f"Please share the spreadsheet with the service account email (found in credentials JSON: 'client_email' field) "
                    f"and grant 'Editor' permissions (not 'Viewer')."
                )
            else:
                error_msg = f"Google Sheets API error ({e.status_code}): {e.reason}"

            return PublishResult(
                success=False,
                row_count=0,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                error=error_msg,
            )

        except Exception as e:
            return PublishResult(
                success=False,
                row_count=0,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                error=str(e),
            )

    def _clear_sheet(self, spreadsheet_id: str, sheet_name: str) -> None:
        """Clear all data from a sheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab

        Raises:
            HttpError: If permission denied or other API error
        """
        service = self._get_service()
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:ZZ",
            ).execute()
        except HttpError as e:
            if e.status_code == 403:
                # Provide more helpful error message for permission errors
                raise HttpError(  # type: ignore[no-untyped-call]
                    resp=e.resp,
                    content=e.content,
                    uri=e.uri,
                ) from e
            raise

    def _write_rows_batched(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[List[Any]],
    ) -> None:
        """Write rows to sheet in batches with retry logic.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            rows: List of rows to write
        """
        service = self._get_service()

        # Write all rows at once (Google Sheets API can handle large batches)
        # If needed, can be split into smaller batches
        for attempt in range(self.max_retries):
            try:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={"values": rows},
                ).execute()
                return  # Success

            except HttpError as e:
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                else:
                    raise  # Re-raise on final attempt

    def _format_header(self, spreadsheet_id: str, sheet_name: str) -> None:
        """Apply bold formatting to header row.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
        """
        service = self._get_service()

        # Get sheet ID
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        sheet_id = None
        for sheet in sheet_metadata["sheets"]:
            if sheet["properties"]["title"] == sheet_name:
                sheet_id = sheet["properties"]["sheetId"]
                break

        if sheet_id is None:
            # Sheet doesn't exist, skip formatting
            return

        # Format header row (row 0) as bold
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                            }
                        }
                    },
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    def _get_sheet_tables(
        self,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> List[Dict[str, Any]]:
        """Detect tables on a sheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab

        Returns:
            List of table metadata dictionaries. Each table has:
            - tableId: Unique table ID
            - tableRange: GridRange of table (sheetId, startRowIndex, endRowIndex, etc.)

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        try:
            # Get spreadsheet metadata including tables
            spreadsheet_metadata = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                includeGridData=False,
            ).execute()

            # Find the target sheet
            sheet_id = None
            for sheet in spreadsheet_metadata["sheets"]:
                if sheet["properties"]["title"] == sheet_name:
                    sheet_id = sheet["properties"]["sheetId"]
                    # Check for regular tables first (most common)
                    if "tables" in sheet:
                        tables = sheet["tables"]
                        logger.debug(f"Found {len(tables)} table(s) on sheet '{sheet_name}'")
                        return tables
                    # Check for data source tables (connected data)
                    if "dataSourceTables" in sheet:
                        tables = sheet["dataSourceTables"]
                        logger.debug(f"Found {len(tables)} data source table(s) on sheet '{sheet_name}'")
                        return tables
                    break

            # No tables found
            logger.debug(f"No tables found on sheet '{sheet_name}'")
            return []

        except HttpError as e:
            logger.error(f"Failed to get sheet tables: {e}")
            raise

    def _publish_without_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[List[Any]],
    ) -> None:
        """Publish data to sheet without table (standard clear + write).

        This is the legacy publishing approach that clears all data
        and writes new data, then formats the header.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            rows: List of rows to write

        Raises:
            HttpError: If API request fails
        """
        # Clear existing data
        self._clear_sheet(spreadsheet_id, sheet_name)

        # Write data in batches
        self._write_rows_batched(spreadsheet_id, sheet_name, rows)

        # Format header row
        self._format_header(spreadsheet_id, sheet_name)

    def _publish_with_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[List[Any]],
        table_metadata: Dict[str, Any],
    ) -> None:
        """Publish data to sheet with table (preserves filters/sorting).

        This table-aware approach:
        1. Updates overlapping rows with new data
        2. If table needs to grow: inserts rows, updates data, resizes table
        3. If table needs to shrink: clears excess rows, deletes rows, resizes table

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            rows: List of rows to write (including header)
            table_metadata: Table metadata from _get_sheet_tables()

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        # Extract table info
        # Regular tables use "range", data source tables use "tableRange"
        table_range = table_metadata.get("range") or table_metadata.get("tableRange")
        if not table_range:
            raise ValueError(
                f"Table metadata missing 'range' or 'tableRange' field. "
                f"Table metadata keys: {list(table_metadata.keys())}"
            )
        sheet_id = table_range["sheetId"]
        table_id = table_metadata["tableId"]

        # Detect table type (regular table has "range", data source table has "tableRange")
        is_data_source_table = "tableRange" in table_metadata

        # Current table dimensions (0-based, endRowIndex is exclusive)
        current_start_row = table_range.get("startRowIndex", 0)
        # endRowIndex should always be present in table metadata
        if "endRowIndex" not in table_range:
            raise ValueError(
                f"Table metadata missing 'endRowIndex' field. "
                f"Table range: {table_range}"
            )
        current_end_row = table_range["endRowIndex"]
        current_row_count = current_end_row - current_start_row

        # New data dimensions
        new_row_count = len(rows)
        new_column_count = max(len(row) for row in rows) if rows else 0

        logger.debug(
            f"Table current size: {current_row_count} rows "
            f"({current_start_row} to {current_end_row}), "
            f"new data: {new_row_count} rows x {new_column_count} cols"
        )

        # Step 1: Update overlapping rows
        # Write data to existing rows (use A1 notation for values.update)
        overlap_rows = min(current_row_count, new_row_count)
        if overlap_rows > 0:
            start_a1 = f"{sheet_name}!A{current_start_row + 1}"  # A1 notation is 1-based
            logger.debug(f"Updating {overlap_rows} overlapping rows starting at {start_a1}")

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=start_a1,
                valueInputOption="RAW",
                body={"values": rows[:overlap_rows]},
            ).execute()

        # Step 2: Handle size difference
        if new_row_count > current_row_count:
            # Table needs to grow
            self._grow_table(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sheet_id=sheet_id,
                table_id=table_id,
                table_range=table_range,
                rows=rows,
                current_row_count=current_row_count,
                new_row_count=new_row_count,
                new_column_count=new_column_count,
                is_data_source_table=is_data_source_table,
            )

        elif new_row_count < current_row_count:
            # Table needs to shrink
            self._shrink_table(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sheet_id=sheet_id,
                table_id=table_id,
                table_range=table_range,
                current_row_count=current_row_count,
                new_row_count=new_row_count,
                new_column_count=new_column_count,
                is_data_source_table=is_data_source_table,
            )

        else:
            # Same size, just update table range to ensure consistency
            logger.debug("Table size unchanged, updating table range")
            self._update_table_range(
                spreadsheet_id=spreadsheet_id,
                sheet_id=sheet_id,
                table_id=table_id,
                table_range=table_range,
                new_row_count=new_row_count,
                new_column_count=new_column_count,
                is_data_source_table=is_data_source_table,
            )

    def _grow_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        sheet_id: int,
        table_id: str,
        table_range: Dict[str, Any],
        rows: List[List[Any]],
        current_row_count: int,
        new_row_count: int,
        new_column_count: int,
        is_data_source_table: bool = False,
    ) -> None:
        """Grow table by inserting rows, updating data, and resizing table.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            sheet_id: Sheet ID (integer)
            table_id: Table ID
            table_range: Current table GridRange
            rows: New data rows
            current_row_count: Current number of rows in table
            new_row_count: New number of rows needed
            new_column_count: New number of columns needed
            is_data_source_table: If True, this is a data source table

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        rows_to_add = new_row_count - current_row_count
        current_end_row = table_range.get("endRowIndex", current_row_count)

        logger.debug(f"Growing table by {rows_to_add} rows")

        # Step 1: Ensure sheet has enough rows (expand grid if needed)
        self._ensure_sheet_size(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            min_rows=current_end_row + rows_to_add,
        )

        # Step 2: Update new rows with data
        # A1 notation is 1-based, so add 1 to 0-based index
        new_data_start_a1 = f"{sheet_name}!A{current_end_row + 1}"
        new_rows_data = rows[current_row_count:]

        logger.debug(f"Updating {len(new_rows_data)} new rows starting at {new_data_start_a1}")

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=new_data_start_a1,
            valueInputOption="RAW",
            body={"values": new_rows_data},
        ).execute()

        # Step 3: Resize table to include new rows and columns
        self._update_table_range(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            table_id=table_id,
            table_range=table_range,
            new_row_count=new_row_count,
            new_column_count=new_column_count,
            is_data_source_table=is_data_source_table,
        )

    def _shrink_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        sheet_id: int,
        table_id: str,
        table_range: Dict[str, Any],
        current_row_count: int,
        new_row_count: int,
        new_column_count: int,
        is_data_source_table: bool = False,
    ) -> None:
        """Shrink table by clearing excess rows, deleting them, and resizing table.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            sheet_id: Sheet ID (integer)
            table_id: Table ID
            table_range: Current table GridRange
            current_row_count: Current number of rows in table
            new_row_count: New number of rows needed
            new_column_count: New number of columns needed
            is_data_source_table: If True, this is a data source table

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        rows_to_remove = current_row_count - new_row_count
        current_start_row = table_range.get("startRowIndex", 0)
        current_end_row = table_range.get("endRowIndex", current_start_row + current_row_count)
        new_end_row = current_start_row + new_row_count

        logger.debug(f"Shrinking table by {rows_to_remove} rows")

        # Step 1: Clear excess rows (to avoid leaving old data)
        # A1 notation is 1-based
        clear_range = f"{sheet_name}!A{new_end_row + 1}:ZZ{current_end_row}"

        logger.debug(f"Clearing excess rows: {clear_range}")

        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=clear_range,
        ).execute()

        # Step 2: Delete rows (shifts content below up)
        # Use current_end_row directly (already available from table_range)
        self._delete_rows(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            start_index=new_end_row,
            end_index=current_end_row,
        )

        # Step 3: Resize table to new size
        self._update_table_range(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            table_id=table_id,
            table_range=table_range,
            new_row_count=new_row_count,
            new_column_count=new_column_count,
            is_data_source_table=is_data_source_table,
        )

    def _insert_rows(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_index: int,
        row_count: int,
    ) -> None:
        """Insert rows into a sheet.

        This shifts existing content below the insertion point downward.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            start_index: 0-based row index to start insertion
            row_count: Number of rows to insert

        Raises:
            HttpError: If API request fails
            ValueError: If row_count <= 0
        """
        # Validate row_count is positive (can't insert 0 or negative rows)
        if row_count <= 0:
            logger.warning(f"Skipping insert: row_count={row_count} (must be > 0)")
            return

        service = self._get_service()

        logger.debug(f"Inserting {row_count} rows at index {start_index}")

        requests = [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": start_index,
                        "endIndex": start_index + row_count,
                    },
                    "inheritFromBefore": False,
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    def _delete_rows(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_index: int,
        end_index: int,
    ) -> None:
        """Delete rows from a sheet.

        This shifts existing content below the deletion point upward.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            start_index: 0-based row index to start deletion (inclusive)
            end_index: 0-based row index to end deletion (exclusive)

        Raises:
            HttpError: If API request fails
            ValueError: If end_index <= start_index
        """
        # Validate range is non-empty (can't delete 0 or negative rows)
        if end_index <= start_index:
            logger.warning(
                f"Skipping delete: end_index={end_index} <= start_index={start_index} "
                f"(must be > start_index)"
            )
            return

        service = self._get_service()

        logger.debug(f"Deleting rows from index {start_index} to {end_index}")

        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": start_index,
                        "endIndex": end_index,
                    }
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    def _ensure_sheet_size(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        min_rows: int,
    ) -> None:
        """Ensure sheet has at least min_rows.

        If the sheet has fewer rows, expand it using appendDimension.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            min_rows: Minimum number of rows required

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        # Get current sheet size
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        current_rows = 0
        for sheet in sheet_metadata["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                current_rows = sheet["properties"]["gridProperties"]["rowCount"]
                break

        if current_rows < min_rows:
            rows_to_add = min_rows - current_rows
            logger.debug(f"Expanding sheet from {current_rows} to {min_rows} rows ({rows_to_add} new rows)")

            requests = [
                {
                    "appendDimension": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "length": rows_to_add,
                    }
                }
            ]

            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()
        else:
            logger.debug(f"Sheet already has {current_rows} rows (>= {min_rows}), no expansion needed")

    def _update_table_range(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        table_id: str,
        table_range: Dict[str, Any],
        new_row_count: int,
        new_column_count: Optional[int] = None,
        is_data_source_table: bool = False,
    ) -> None:
        """Update table range to new size.

        This resizes the table while preserving filters and sorting.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            table_id: Table ID
            table_range: Current table GridRange
            new_row_count: New number of rows for table
            new_column_count: New number of columns for table (if None, use current width)
            is_data_source_table: If True, use updateDataSourceTable; else use updateTable

        Raises:
            HttpError: If API request fails
        """
        service = self._get_service()

        # Calculate new table range
        start_row = table_range.get("startRowIndex", 0)
        end_row = start_row + new_row_count
        start_col = table_range.get("startColumnIndex", 0)

        # Determine column count: expand if needed, never shrink
        current_end_col = table_range.get("endColumnIndex", 26)
        if new_column_count is not None:
            # Expand table width if new data has more columns
            end_col = max(current_end_col, start_col + new_column_count)
        else:
            # No new column count provided, preserve existing width
            end_col = current_end_col

        new_range = {
            "sheetId": sheet_id,
            "startRowIndex": start_row,
            "endRowIndex": end_row,
            "startColumnIndex": start_col,
            "endColumnIndex": end_col,
        }

        logger.debug(
            f"Updating {'data source ' if is_data_source_table else ''}table range: "
            f"rows {start_row}-{end_row}, cols {start_col}-{end_col}"
        )

        # Use different update method depending on table type
        if is_data_source_table:
            requests = [
                {
                    "updateDataSourceTable": {
                        "dataSourceTable": {
                            "tableId": table_id,
                            "tableRange": new_range,
                        },
                        "fields": "tableRange",
                    }
                }
            ]
        else:
            # Regular tables use updateTable
            requests = [
                {
                    "updateTable": {
                        "table": {
                            "tableId": table_id,
                            "range": new_range,
                        },
                        "fields": "range",
                    }
                }
            ]

        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to update table range: {e}")
            raise

    def test_connection(self) -> bool:
        """Test connection to Google Sheets API.

        Returns:
            True if connection successful, False otherwise

        Raises:
            HttpError: If API connection fails (logged and re-raised)
        """
        try:
            self._get_service()
            return True
        except HttpError as e:
            logger.error(f"Google Sheets API connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error testing Google Sheets connection: {e}")
            raise
