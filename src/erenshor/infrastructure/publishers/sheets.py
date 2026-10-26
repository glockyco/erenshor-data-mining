"""Google Sheets publisher for deploying data to spreadsheets.

This module provides the GoogleSheetsPublisher class that handles:
- Authentication with Google service account
- Capturing stable workbook preimages, including non-owned references and chips
- Freezing one atomic batch of selected table updates with typed RAW cells
- Preserving surrounding content and explicit cell formatting
- Retaining acknowledgements and observed workbook postimages without retries
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

__all__ = [
    "GoogleSheetsPublisher",
    "PublishResult",
    "SheetsRequestError",
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


class SheetsRequestError(Exception):
    """A stopped request sequence, with acknowledged writes retained."""

    def __init__(self, message: str, evidence: dict[str, Any], *, uncertain: bool):
        super().__init__(message)
        self.evidence = evidence
        self.uncertain = uncertain


class GoogleSheetsPublisher:
    """Publish data to Google Sheets via Google Sheets API.

    This publisher uses the Google Sheets API v4 with service account
    authentication to update spreadsheet data.

    Features:
    - Batch writing for efficient uploads
    - Exact prepared RAW and structural requests
    - Table-aware updates that preserve surrounding content
    - One atomic batch acknowledgement without automatic retries

    Table-Aware Publishing:
    When a Google Sheets table exists on the target sheet, this publisher
    will update the table data while preserving filters and sorting. The
    table range will be automatically resized to match the new data size,
    and content below the table will shift up or down accordingly.

    Example:
        publisher = GoogleSheetsPublisher(
            credentials_file=Path("~/.config/erenshor/google-credentials.json"),
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
    SCOPES: ClassVar[list[str]] = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, credentials_file: Path) -> None:
        """Use service-account credentials with a single non-retrying transport."""
        self.credentials_file = credentials_file
        self._service: Any = None
        self._prepared_requests: list[dict[str, Any]] | None = None
        self._prepared_metadata: dict[str, Any] | None = None

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
                raise FileNotFoundError(f"Google credentials file not found: {self.credentials_file}")

            try:
                creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                    str(self.credentials_file),
                    scopes=self.SCOPES,
                )
                self._service = build("sheets", "v4", credentials=creds)
                transport = self._service._http
                getattr(transport, "http", transport).timeout = 240
            except Exception as e:
                raise GoogleAuthError(f"Failed to authenticate with Google: {e}") from e  # type: ignore[no-untyped-call]

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
        rows: list[list[Any]],
        dry_run: bool = False,
    ) -> PublishResult:
        """Publish rows to a Google Sheets tab.

        This method requires a Google Sheets table to exist on the target sheet.
        Tables are required to preserve filters and sorting when updating data.

        Process:
        1. Detects if a Google Sheets table exists on the sheet
        2. If table exists:
           - Updates table data while preserving filters/sorting
           - Resizes table range to match new data size
           - Shifts content below table up/down as needed
        3. If no table exists:
           - Returns PublishResult with success=False and clear error message
           - User must create a table before deployment

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
            prepared = self.prepare_table(spreadsheet_id, sheet_name, rows)
            self.execute_prepared(prepared)

            return PublishResult(
                success=True,
                row_count=len(rows) - 1,  # Exclude header
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
            )

        except SheetsRequestError as e:
            error = str(e)
            if e.uncertain:
                error += ". Outcome is uncertain. Reconcile the spreadsheet before preparing another publication."
            return PublishResult(
                success=False, row_count=0, spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, error=error
            )

        except HttpError as e:
            # Provide helpful error message for permission errors
            if e.status_code == 403:
                error_msg = (
                    "Permission denied: Service account does not have Editor access to spreadsheet. "
                    "Please share the spreadsheet with the service account email "
                    "(found in credentials JSON: 'client_email' field) "
                    "and grant 'Editor' permissions (not 'Viewer')."
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

    def _publish_with_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: list[list[Any]],
        table_metadata: dict[str, Any],
    ) -> None:
        """Record the native table-aware mutation sequence from frozen metadata.

        This table-aware approach:
        1. Updates overlapping rows with new data
        2. If table needs to grow: inserts rows, updates data, resizes table
        3. If table needs to shrink: clears excess rows, deletes rows, resizes table

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            rows: List of rows to write (including header)
            table_metadata: Table metadata from the captured workbook

        Raises:
            ValueError: If captured table metadata is incomplete
        """

        # Extract table info
        table_range = table_metadata.get("range")
        if not table_range:
            raise ValueError(
                f"Table metadata missing 'range' field. Table metadata keys: {list(table_metadata.keys())}"
            )
        sheet_id = table_range["sheetId"]
        table_id = table_metadata["tableId"]

        # Current table dimensions (0-based, endRowIndex is exclusive)
        current_start_row = table_range.get("startRowIndex", 0)
        # endRowIndex should always be present in table metadata
        if "endRowIndex" not in table_range:
            raise ValueError(f"Table metadata missing 'endRowIndex' field. Table range: {table_range}")
        current_end_row = table_range["endRowIndex"]
        current_row_count = current_end_row - current_start_row

        # New data dimensions
        new_row_count = len(rows)
        new_column_count = max(len(row) for row in rows) if rows else 0
        self._ensure_sheet_size(
            spreadsheet_id,
            sheet_id,
            min_rows=0,
            min_columns=table_range.get("startColumnIndex", 0) + new_column_count,
        )

        logger.debug(
            f"Table current size: {current_row_count} rows "
            f"({current_start_row} to {current_end_row}), "
            f"new data: {new_row_count} rows x {new_column_count} cols"
        )

        # Step 1: Update overlapping rows
        # Write data to existing rows (use A1 notation for values.update)
        overlap_rows = min(current_row_count, new_row_count)
        if overlap_rows > 0:
            start_a1 = _a1_cell(sheet_name, table_range.get("startColumnIndex", 0), current_start_row)
            logger.debug(f"Updating {overlap_rows} overlapping rows starting at {start_a1}")

            self._record_request(
                "values.update",
                spreadsheet_id,
                {
                    "range": start_a1,
                    "valueInputOption": "RAW",
                    "body": {"values": rows[:overlap_rows]},
                },
            )

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
            )

    def _grow_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        sheet_id: int,
        table_id: str,
        table_range: dict[str, Any],
        *,
        rows: list[list[Any]],
        current_row_count: int,
        new_row_count: int,
        new_column_count: int,
    ) -> None:
        """Record table growth, row insertion, typed values and table resizing.

        This method preserves any existing content outside the table:
        1. Expands the sheet if needed (adds rows to the end)
        2. Inserts rows at table's end position (shifts content below down)
        3. Writes new data to the inserted rows
        4. Resizes table to include the new rows

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

        Raises:
            RuntimeError: If called outside preparation
        """

        rows_to_add = new_row_count - current_row_count
        current_end_row = table_range.get("endRowIndex", current_row_count)

        logger.debug(f"Growing table by {rows_to_add} rows")

        # Step 1: Ensure sheet has enough rows to accommodate the table growth
        # This expands the sheet at the end if needed, preserving all existing content
        min_rows_needed = current_end_row + rows_to_add
        self._ensure_sheet_size(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            min_rows=min_rows_needed,
        )

        # Step 2: Insert rows (shifts content below down)
        self._insert_rows(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            start_index=current_end_row,
            row_count=rows_to_add,
        )

        # Step 3: Update new rows with data
        # A1 notation is 1-based, so add 1 to 0-based index
        new_data_start_a1 = _a1_cell(sheet_name, table_range.get("startColumnIndex", 0), current_end_row)
        new_rows_data = rows[current_row_count:]

        logger.debug(f"Updating {len(new_rows_data)} new rows starting at {new_data_start_a1}")

        self._record_request(
            "values.update",
            spreadsheet_id,
            {
                "range": new_data_start_a1,
                "valueInputOption": "RAW",
                "body": {"values": new_rows_data},
            },
        )

        # Step 4: Resize table to include new rows and columns
        self._update_table_range(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_id,
            table_id=table_id,
            table_range=table_range,
            new_row_count=new_row_count,
            new_column_count=new_column_count,
        )

    def _shrink_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        sheet_id: int,
        table_id: str,
        table_range: dict[str, Any],
        *,
        current_row_count: int,
        new_row_count: int,
        new_column_count: int,
    ) -> None:
        """Record clearing, row deletion and table shrinking.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet tab
            sheet_id: Sheet ID (integer)
            table_id: Table ID
            table_range: Current table GridRange
            current_row_count: Current number of rows in table
            new_row_count: New number of rows needed
            new_column_count: New number of columns needed

        Raises:
            RuntimeError: If called outside preparation
        """

        rows_to_remove = current_row_count - new_row_count
        current_start_row = table_range.get("startRowIndex", 0)
        current_end_row = table_range.get("endRowIndex", current_start_row + current_row_count)
        new_end_row = current_start_row + new_row_count

        logger.debug(f"Shrinking table by {rows_to_remove} rows")

        # Step 1: Clear excess rows (to avoid leaving old data)
        # A1 notation is 1-based
        clear_range = f"{_quote_sheet(sheet_name)}!{new_end_row + 1}:{current_end_row}"

        logger.debug(f"Clearing excess rows: {clear_range}")

        self._record_request("values.clear", spreadsheet_id, {"range": clear_range})

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
        )

    def _insert_rows(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_index: int,
        row_count: int,
    ) -> None:
        """Record row insertion into a sheet.

        This shifts existing content below the insertion point downward.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            start_index: 0-based row index to start insertion
            row_count: Number of rows to insert

        Raises:
            RuntimeError: If called outside preparation
            ValueError: If row_count <= 0
        """
        # Validate row_count is positive (can't insert 0 or negative rows)
        if row_count <= 0:
            raise ValueError("Inserted row count must be positive")

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

        self._record_request("batchUpdate", spreadsheet_id, {"body": {"requests": requests}})

    def _delete_rows(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_index: int,
        end_index: int,
    ) -> None:
        """Record row deletion from a sheet.

        This shifts existing content below the deletion point upward.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            start_index: 0-based row index to start deletion (inclusive)
            end_index: 0-based row index to end deletion (exclusive)

        Raises:
            RuntimeError: If called outside preparation
            ValueError: If end_index <= start_index
        """
        # Validate range is non-empty (can't delete 0 or negative rows)
        if end_index <= start_index:
            raise ValueError("Deleted row range must be nonempty")

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

        self._record_request("batchUpdate", spreadsheet_id, {"body": {"requests": requests}})

    def _ensure_sheet_size(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        min_rows: int,
        min_columns: int | None = None,
    ) -> None:
        """Record append requests when frozen grid dimensions are insufficient.

        If the sheet has fewer rows, expand it using appendDimension.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            min_rows: Minimum number of rows required

        Raises:
            RuntimeError: If called outside preparation
        """

        # Get current sheet size
        sheet_metadata = self._prepared_metadata
        if sheet_metadata is None:
            raise RuntimeError("Native table requests require captured workbook metadata")

        current_rows = 0
        current_columns = 0
        for sheet in sheet_metadata["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                current_rows = sheet["properties"]["gridProperties"]["rowCount"]
                current_columns = sheet["properties"]["gridProperties"]["columnCount"]
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

            self._record_request("batchUpdate", spreadsheet_id, {"body": {"requests": requests}})
        else:
            logger.debug(f"Sheet already has {current_rows} rows (>= {min_rows}), no expansion needed")
        if min_columns is not None and current_columns < min_columns:
            self._record_request(
                "batchUpdate",
                spreadsheet_id,
                {
                    "body": {
                        "requests": [
                            {
                                "appendDimension": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "length": min_columns - current_columns,
                                },
                            }
                        ]
                    }
                },
            )

    def _update_table_range(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        table_id: str,
        table_range: dict[str, Any],
        new_row_count: int,
        *,
        new_column_count: int | None = None,
    ) -> None:
        """Record a new table range.

        This resizes the table while preserving filters and sorting.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_id: Sheet ID (integer)
            table_id: Table ID
            table_range: Current table GridRange
            new_row_count: New number of rows for table
            new_column_count: New number of columns for table (if None, use current width)

        Raises:
            RuntimeError: If called outside preparation
        """

        # Calculate new table range
        start_row = table_range.get("startRowIndex", 0)
        end_row = start_row + new_row_count
        start_col = table_range.get("startColumnIndex", 0)

        # Determine column count from data
        current_end_col = table_range.get("endColumnIndex", 26)
        if new_column_count is not None:
            # Resize table width to match data (expand or shrink)
            end_col = start_col + new_column_count
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

        logger.debug(f"Updating table range: rows {start_row}-{end_row}, cols {start_col}-{end_col}")

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

        self._record_request("batchUpdate", spreadsheet_id, {"body": {"requests": requests}})

    def _record_request(self, method: str, _spreadsheet_id: str, arguments: dict[str, Any]) -> None:
        """Record builder intent without exposing an individual mutation path."""
        if self._prepared_requests is None:
            raise RuntimeError("Native table requests can only be recorded during preparation")
        self._prepared_requests.append(copy.deepcopy({"method": method, "arguments": arguments}))

    def _request(self, method: str, spreadsheet_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Send the owning provider's one atomic batch, without transport retries."""
        if method != "batchUpdate":
            raise ValueError("Only a prepared atomic Sheets batch can mutate the provider")
        request = self._get_service().spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, **arguments)
        if request.body != _batch_body(arguments["body"]):
            raise ValueError("Native Sheets transport changed the approved batch body bytes")
        response: dict[str, Any] = request.execute(num_retries=0)
        return response

    def inspect_workbook(self, spreadsheet_id: str) -> dict[str, Any]:
        """Capture stable workbook inputs, including unselected dependencies.

        Effective values, displayed text, effective formats and hyperlink output
        are derived from retained CellData inputs. Execution status is volatile.
        Formula text and named ranges are retained, not locally interpreted.
        """
        response = (
            self._get_service()
            .spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                includeGridData=True,
            )
            .execute(num_retries=0)
        )
        if not isinstance(response, dict) or response.get("spreadsheetId") != spreadsheet_id:
            raise ValueError("Cannot identify the workbook before Sheets publication")
        if not isinstance(response.get("sheets"), list):
            raise ValueError("Cannot inspect complete workbook content before Sheets publication")
        response = _stable_content(response)
        return {
            "metadata": _prune({key: value for key, value in response.items() if key != "sheets"}),
            "sheets": {str(sheet["properties"]["sheetId"]): _sheet_snapshot(sheet) for sheet in response["sheets"]},
        }

    def prepare_table(self, spreadsheet_id: str, sheet_name: str, rows: list[list[Any]]) -> dict[str, Any]:
        """Use the grouped atomic builder for a standalone one-tab publication."""
        return self.prepare_tables(spreadsheet_id, {sheet_name: rows})

    def prepare_tables(self, spreadsheet_id: str, tabs: dict[str, list[list[Any]]]) -> dict[str, Any]:
        """Freeze one provider-atomic batch for exact selected tabs."""
        if not tabs:
            raise ValueError("Sheets publication requires selected tabs")
        if self._prepared_requests is not None:
            raise RuntimeError("Nested table preparation is not supported")
        base = self.inspect_workbook(spreadsheet_id)
        by_title = {sheet["metadata"]["properties"]["title"]: sheet for sheet in base["sheets"].values()}
        for title, sheet in by_title.items():
            _reject_unknown_cells(sheet, title)
        batch: list[dict[str, Any]] = []
        selected = []
        sheet_ids: set[int] = set()
        for sheet_name in sorted(tabs, key=lambda name: (name.casefold(), name)):
            rows = tabs[sheet_name]
            if not rows or not rows[0]:
                raise ValueError("Cannot publish empty rows or headers")
            if any(not isinstance(value, str | int | float | bool) for row in rows for value in row):
                raise ValueError("Prepared RAW cells must be strings, numbers or booleans")
            json.dumps(rows, allow_nan=False)
            if sheet_name not in by_title:
                raise ValueError(f"Sheet tab '{sheet_name}' does not exist")
            sheet = by_title[sheet_name]
            metadata = sheet["metadata"]
            sheet_id = metadata["properties"]["sheetId"]
            if sheet_id in sheet_ids:
                raise ValueError(f"Selected tabs alias the same sheetId: {sheet_name}")
            sheet_ids.add(sheet_id)
            tables = metadata.get("tables") or []
            if not tables:
                raise ValueError(f"No Google Sheets table found on sheet '{sheet_name}'")
            table = tables[0]
            table_range = table.get("range")
            if not table_range or "endRowIndex" not in table_range or "endColumnIndex" not in table_range:
                raise ValueError(f"Unreadable table range on sheet '{sheet_name}'")
            _check_owned_footprint(sheet, table, rows, sheet_name)
            native: list[dict[str, Any]] = []
            self._prepared_requests = native
            self._prepared_metadata = {"sheets": [metadata]}
            try:
                self._publish_with_table(spreadsheet_id, sheet_name, rows, table)
            finally:
                self._prepared_requests = None
                self._prepared_metadata = None
            converted = _atomic_requests(native, sheet_id)
            _check_anchor_footprint(sheet, converted, sheet_name)
            batch.extend(converted)
            final_range = next(
                request["updateTable"]["table"]["range"] for request in reversed(converted) if "updateTable" in request
            )
            selected.append(
                {
                    "sheet_name": sheet_name,
                    "sheet_id": sheet_id,
                    "table_id": table["tableId"],
                    "range": copy.deepcopy(final_range),
                    "rows": copy.deepcopy(rows),
                }
            )
        # Native JSON insertion order must survive the plan's canonical JSON round trip.
        body = json.loads(json.dumps({"requests": batch}, sort_keys=True, allow_nan=False))
        body_text = _batch_body(body)
        return {
            "spreadsheet_id": spreadsheet_id,
            "tabs": selected,
            "requests": [{"method": "batchUpdate", "arguments": {"body": body}}],
            "batch_body": body_text,
            "batch_body_bytes": len(body_text.encode()),
            "batch_body_sha256": hashlib.sha256(body_text.encode()).hexdigest(),
            "base_snapshot": base,
            "base_sha256": _snapshot_digest(base),
            "affected_region": {
                "scope": "full workbook preimage and provider-rebased references, exact selected-tab writes only",
                "sheet_ids": sorted(sheet_ids),
            },
            "guard": "full-workbook-preflight-owned-postflight-observed-receipt",
            "limitations": [
                "Sheets has no atomic compare-and-set guard. A concurrent writer can race preflight.",
                "Google applies this batch atomically and owns formula and named-range rebasing.",
                "Only owned values, table ranges and stable preservation invariants are asserted after writing.",
                "Retained cell content, explicit dimensions, table settings and identities are checked.",
                "Non-owned formula text, pivot source ranges and reference-bearing metadata are provider-managed.",
                "Stable connected-anchor identities and remaining definitions are checked.",
                "Inserted-row inherited formatting is a provider-managed effect.",
                "Unexposed dynamic-output extents are delegated to native validation and are not inferred locally.",
                "The complete observed stable workbook postimage is retained for exact resume reconciliation.",
                "Calculated outputs, execution status, threaded comments and derived formatting are excluded.",
                "No automatic retry, request splitting or transactional rollback is available.",
            ],
        }

    def check_prepared(self, prepared: dict[str, Any]) -> dict[str, Any]:
        """Recheck the exact stable workbook preimage without projecting formulas."""
        _check_batch_body(prepared)
        snapshot = self.inspect_workbook(prepared["spreadsheet_id"])
        if _snapshot_digest(snapshot) != prepared["base_sha256"]:
            raise ValueError(f"Spreadsheet '{prepared['spreadsheet_id']}' base snapshot changed")
        return snapshot

    def execute_prepared(
        self, prepared: dict[str, Any], outcome_sink: Callable[[dict[str, Any]], None] | None = None
    ) -> dict[str, Any]:
        """Send one native atomic batch and retain its observed stable postimage."""
        try:
            self.check_prepared(prepared)
        except Exception as exc:
            raise SheetsRequestError(str(exc), {"safe_to_resume": True, "outcomes": []}, uncertain=False) from exc
        evidence: dict[str, Any] = {
            "spreadsheet_id": prepared["spreadsheet_id"],
            "base_sha256": prepared["base_sha256"],
            "batch_body_sha256": prepared["batch_body_sha256"],
            "outcomes": [],
            "running_request": 0,
        }
        if outcome_sink is not None:
            outcome_sink(evidence)
        response: Any = None
        try:
            request = prepared["requests"][0]
            response = self._request("batchUpdate", prepared["spreadsheet_id"], request["arguments"])
            if not isinstance(response, dict) or response.get("spreadsheetId") != prepared["spreadsheet_id"]:
                raise ValueError("Sheets returned an unidentified batch acknowledgement")
            replies = response.get("replies")
            if not isinstance(replies, list) or len(replies) != len(request["arguments"]["body"]["requests"]):
                raise ValueError("Sheets returned an incomplete batch acknowledgement")
        except BaseException as exc:
            known_rejection = (
                isinstance(exc, HttpError) and 400 <= exc.status_code < 500 and exc.status_code not in {408, 499}
            )
            evidence["outcomes"] = [
                {
                    "index": 0,
                    "method": "batchUpdate",
                    "status": "rejected" if known_rejection else "uncertain",
                    "error": str(exc),
                    "response": response,
                }
            ]
            evidence.pop("running_request")
            evidence["safe_to_resume"] = known_rejection
            if outcome_sink is not None:
                outcome_sink(evidence)
            raise SheetsRequestError(
                f"Spreadsheet '{prepared['spreadsheet_id']}' atomic batch stopped: {exc}",
                evidence,
                uncertain=not known_rejection,
            ) from exc
        evidence["outcomes"] = [{"index": 0, "method": "batchUpdate", "status": "succeeded", "response": response}]
        evidence.pop("running_request")
        if outcome_sink is not None:
            outcome_sink(evidence)
        try:
            observed = self.inspect_workbook(prepared["spreadsheet_id"])
            _check_owned_postimage(prepared, observed)
        except BaseException as exc:
            evidence["postflight_error"] = str(exc)
            if outcome_sink is not None:
                outcome_sink(evidence)
            raise SheetsRequestError(
                f"Spreadsheet '{prepared['spreadsheet_id']}' postflight could not confirm owned outputs",
                evidence,
                uncertain=True,
            ) from exc
        evidence["postflight_snapshot"] = observed
        evidence["postflight_sha256"] = _snapshot_digest(observed)
        if outcome_sink is not None:
            outcome_sink(evidence)
        return evidence

    def reconcile_prepared(self, prepared: dict[str, Any], receipt: dict[str, Any]) -> None:
        """Require an acknowledged batch and the exact retained observed state."""
        _check_batch_body(prepared)
        for key in ("spreadsheet_id", "base_sha256", "batch_body_sha256"):
            if receipt.get(key) != prepared[key]:
                raise ValueError("Sheets receipt does not identify the approved atomic operation")
        outcomes = receipt.get("outcomes", [])
        if len(outcomes) != 1 or outcomes[0].get("index") != 0 or outcomes[0].get("method") != "batchUpdate":
            raise ValueError("Incomplete Sheets receipt requires provider reconciliation and a new plan")
        outcome = outcomes[0]
        response = outcome.get("response", {})
        if (
            outcome.get("status") != "succeeded"
            or not isinstance(response, dict)
            or response.get("spreadsheetId") != prepared["spreadsheet_id"]
            or not isinstance(response.get("replies"), list)
            or len(response.get("replies", [])) != len(prepared["requests"][0]["arguments"]["body"]["requests"])
        ):
            raise ValueError("Sheets receipt has no complete acknowledged atomic batch")
        observed = receipt.get("postflight_snapshot")
        if not isinstance(observed, dict) or receipt.get("postflight_sha256") != _snapshot_digest(observed):
            raise ValueError("Sheets receipt has no intact observed postimage")
        _check_owned_postimage(prepared, observed)
        current = self.inspect_workbook(prepared["spreadsheet_id"])
        if _snapshot_digest(current) != receipt["postflight_sha256"]:
            raise ValueError("Spreadsheet completed state changed from its observed receipt")

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


def _quote_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _a1_cell(sheet_name: str, column: int, row: int) -> str:
    label = ""
    column += 1
    while column:
        column, remainder = divmod(column - 1, 26)
        label = chr(65 + remainder) + label
    return f"{_quote_sheet(sheet_name)}!{label}{row + 1}"


def _snapshot_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _prune(value: Any) -> Any:
    """Normalize omitted empty API containers without discarding scalar types."""
    if isinstance(value, dict):
        result = {key: clean for key, item in value.items() if (clean := _prune(item)) not in ({}, [])}
        if "sheetId" in result and ("endRowIndex" in result or "endColumnIndex" in result):
            result.setdefault("startRowIndex", 0)
            result.setdefault("startColumnIndex", 0)
        return result
    if isinstance(value, list):
        return [_prune(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _sheet_snapshot(sheet: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "metadata": {key: copy.deepcopy(value) for key, value in sheet.items() if key != "data"},
        "cells": {},
        "row_metadata": {},
        "column_metadata": {},
    }
    for table in snapshot["metadata"].get("tables", []):
        for index, column in enumerate(table.get("columnProperties", [])):
            column.setdefault("columnIndex", index)
            if column.get("columnType") == "COLUMN_TYPE_UNSPECIFIED":
                column.pop("columnType")
    for grid in sheet.get("data", []):
        row_start, column_start = grid.get("startRow", 0), grid.get("startColumn", 0)
        for r, row in enumerate(grid.get("rowData", []), row_start):
            for c, raw_cell in enumerate(row.get("values", []), column_start):
                cell = _prune(raw_cell)
                if cell:
                    snapshot["cells"][f"{r}:{c}"] = cell
        for axis, start in (("row", row_start), ("column", column_start)):
            for index, raw_item in enumerate(grid.get(f"{axis}Metadata", []), start):
                item = _prune(raw_item)
                # API dimension metadata includes default sizes even when no
                # custom formatting is set. Appended blank dimensions use them.
                if item.get("pixelSize") == (21 if axis == "row" else 100):
                    item.pop("pixelSize")
                if item.get("hiddenByUser") is False:
                    item.pop("hiddenByUser")
                if item:
                    snapshot[f"{axis}_metadata"][str(index)] = item
    normalized: dict[str, Any] = _prune(snapshot)
    return normalized | {
        "cells": snapshot["cells"],
        "row_metadata": snapshot["row_metadata"],
        "column_metadata": snapshot["column_metadata"],
    }


def _reject_unknown_cells(snapshot: dict[str, Any], sheet_name: str) -> None:
    supported = {
        "userEnteredValue",
        "userEnteredFormat",
        "note",
        "textFormatRuns",
        "chipRuns",
        "dataValidation",
        "pivotTable",
        "dataSourceTable",
        "dataSourceFormula",
    }
    for address, cell in snapshot["cells"].items():
        for field in cell.keys() - supported:
            row, column = map(int, address.split(":"))
            raise ValueError(
                f"Cannot prepare sheet '{sheet_name}': unsupported {field} at "
                f"{_a1_cell(sheet_name, column, row)} has no supported RAW-write preservation contract"
            )


def _check_anchor_footprint(sheet: dict[str, Any], requests: list[dict[str, Any]], title: str) -> None:
    """Reject known anchor erasure without inferring computed output extents."""
    for address, cell in sheet["cells"].items():
        origin, column = map(int, address.split(":"))
        for field in ("pivotTable", "dataSourceTable", "dataSourceFormula"):
            if field not in cell:
                continue
            row = origin
            for request in requests:
                effect = ""
                if "updateCells" in request:
                    update = request["updateCells"]
                    start = update["start"]
                    index = row - start["rowIndex"]
                    if 0 <= index < len(update["rows"]):
                        width = len(update["rows"][index].get("values", []))
                        if start["columnIndex"] <= column < start["columnIndex"] + width:
                            effect = "RAW writes overlap its anchor cell"
                elif "repeatCell" in request:
                    region = request["repeatCell"]["range"]
                    if region.get("startRowIndex", 0) <= row < region["endRowIndex"] and region.get(
                        "startColumnIndex", 0
                    ) <= column < region.get("endColumnIndex", 2**31 - 1):
                        effect = "cleared rows overlap its anchor cell"
                elif "insertDimension" in request or "deleteDimension" in request:
                    insert = "insertDimension" in request
                    region = request["insertDimension" if insert else "deleteDimension"]["range"]
                    at, end = region["startIndex"], region["endIndex"]
                    if insert and row >= at:
                        row += end - at
                    elif not insert and row >= end:
                        row -= end - at
                    elif not insert and row >= at:
                        effect = "row deletion removes its anchor cell"
                if effect:
                    raise ValueError(
                        f"Cannot prepare '{title}': unsupported {field} at {_a1_cell(title, column, origin)}. {effect}"
                    )


def _stable_content(workbook: dict[str, Any]) -> dict[str, Any]:
    """Remove only documented calculated fields at their schema locations."""
    stable = copy.deepcopy(workbook)
    stable.pop("comments", None)
    stable.pop("commentsViewMode", None)
    for schedule in stable.get("dataSourceSchedules", []):
        schedule.pop("nextRun", None)
    for sheet in stable["sheets"]:
        sheet["properties"].get("dataSourceSheetProperties", {}).pop("dataExecutionStatus", None)
        for chart in sheet.get("charts", []):
            chart.get("spec", {}).get("dataSourceChartProperties", {}).pop("dataExecutionStatus", None)
        for grid in sheet.get("data", []):
            for row in grid.get("rowData", []):
                for cell in row.get("values", []):
                    for field in ("effectiveValue", "formattedValue", "effectiveFormat", "hyperlink"):
                        cell.pop(field, None)
                    for anchor in ("pivotTable", "dataSourceTable", "dataSourceFormula"):
                        cell.get(anchor, {}).pop("dataExecutionStatus", None)
            for axis in ("rowMetadata", "columnMetadata"):
                for dimension in grid.get(axis, []):
                    dimension.pop("hiddenByFilter", None)
    return stable


def _batch_body(body: dict[str, Any]) -> str:
    """Match googleapiclient's JSON model without changing its owning transport."""
    return json.dumps(body, allow_nan=False)


def _raw_cell(value: str | int | float | bool) -> dict[str, Any]:
    if value == "":
        return {}
    key = "boolValue" if isinstance(value, bool) else "numberValue" if isinstance(value, int | float) else "stringValue"
    return {"userEnteredValue": {key: value}}


def _atomic_requests(native: list[dict[str, Any]], sheet_id: int) -> list[dict[str, Any]]:
    """Translate only the native builder's bounded values operations."""
    result: list[dict[str, Any]] = []
    for request in native:
        method, arguments = request["method"], request["arguments"]
        if method == "batchUpdate":
            result.extend(copy.deepcopy(arguments["body"]["requests"]))
        elif method == "values.update":
            address = re.search(r"!([A-Z]+)([0-9]+)$", arguments["range"])
            if address is None or arguments["valueInputOption"] != "RAW":
                raise ValueError("Unreadable native RAW cell update")
            column = 0
            for letter in address[1]:
                column = column * 26 + ord(letter) - 64
            result.append(
                {
                    "updateCells": {
                        "start": {"sheetId": sheet_id, "rowIndex": int(address[2]) - 1, "columnIndex": column - 1},
                        "rows": [
                            {"values": [_raw_cell(value) for value in row]} for row in arguments["body"]["values"]
                        ],
                        "fields": "userEnteredValue",
                    }
                }
            )
        elif method == "values.clear":
            bounds = re.search(r"!([0-9]+):([0-9]+)$", arguments["range"])
            if bounds is None:
                raise ValueError("Unreadable native cleared row range")
            result.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": int(bounds[1]) - 1,
                            "endRowIndex": int(bounds[2]),
                        },
                        "cell": {},
                        "fields": "userEnteredValue",
                    }
                }
            )
        else:
            raise ValueError(f"Unsupported native table request: {method}")
    return result


def _check_batch_body(prepared: dict[str, Any]) -> None:
    requests = prepared["requests"]
    if len(requests) != 1 or requests[0]["method"] != "batchUpdate":
        raise ValueError("Prepared Sheets publication must contain one atomic batch")
    body = _batch_body(requests[0]["arguments"]["body"])
    if (
        body != prepared["batch_body"]
        or len(body.encode()) != prepared["batch_body_bytes"]
        or hashlib.sha256(body.encode()).hexdigest() != prepared["batch_body_sha256"]
        or _snapshot_digest(prepared["base_snapshot"]) != prepared["base_sha256"]
    ):
        raise ValueError("Prepared Sheets batch body or preimage differs from its approved bytes")


def _check_owned_footprint(sheet: dict[str, Any], table: dict[str, Any], rows: list[list[Any]], title: str) -> None:
    bounds = table["range"]
    start, old_end = bounds.get("startRowIndex", 0), bounds["endRowIndex"]
    left, old_right = bounds.get("startColumnIndex", 0), bounds["endColumnIndex"]
    end, right = start + len(rows), left + max(map(len, rows))
    for address, cell in sheet["cells"].items():
        row, column = map(int, address.split(":"))
        if end <= row < old_end and not left <= column < old_right:
            raise ValueError(
                f"Cannot prepare '{title}': deleting whole rows would destroy non-owned cell "
                f"{_a1_cell(title, column, row)} outside the exported table"
            )
        if start <= row < min(end, old_end) and old_right <= column < right and cell:
            raise ValueError(
                f"Cannot prepare '{title}': table width expansion overlaps non-owned cell "
                f"{_a1_cell(title, column, row)}"
            )
    for other in sheet["metadata"].get("tables", []):
        if other["tableId"] == table["tableId"]:
            continue
        region = other["range"]
        top, bottom = region.get("startRowIndex", 0), region["endRowIndex"]
        if end < old_end and top < old_end and bottom > end:
            raise ValueError(
                f"Cannot prepare '{title}': deleting whole rows overlaps non-owned table {other['tableId']}"
            )
        if (
            right > old_right
            and top < min(end, old_end)
            and bottom > start
            and region.get("startColumnIndex", 0) < right
            and region["endColumnIndex"] > old_right
        ):
            raise ValueError(f"Cannot prepare '{title}': width expansion overlaps non-owned table {other['tableId']}")
    regions = [("merged cells", region) for region in sheet["metadata"].get("merges", [])]
    for field in ("protectedRanges", "bandedRanges", "filterViews"):
        regions.extend((field, item["range"]) for item in sheet["metadata"].get(field, []) if "range" in item)
    for rule in sheet["metadata"].get("conditionalFormats", []):
        regions.extend(("conditional formatting", region) for region in rule.get("ranges", []))
    basic_filter = sheet["metadata"].get("basicFilter", {})
    if "range" in basic_filter:
        regions.append(("basic filter", basic_filter["range"]))
    for field, region in regions:
        intersects_deleted_rows = (
            end < old_end and region.get("startRowIndex", 0) < old_end and region.get("endRowIndex", 2**31 - 1) > end
        )
        outside_columns = (
            region.get("startColumnIndex", 0) < left or region.get("endColumnIndex", 2**31 - 1) > old_right
        )
        if intersects_deleted_rows and outside_columns:
            raise ValueError(
                f"Cannot prepare '{title}': deleting whole rows intersects non-owned {field} outside the exported table"
            )


def _formula_invariant(value: Any) -> Any:
    """Retain reference-bearing rule structure without predicting Google text."""
    if isinstance(value, dict):
        return {
            key: None
            if key in {"formulaValue", "formula", "userEnteredValue"} and isinstance(item, str) and item.startswith("=")
            else _formula_invariant(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_formula_invariant(item) for item in value]
    return value


def _cell_invariant(cell: dict[str, Any], written: bool) -> dict[str, Any]:
    excluded = {"userEnteredValue", "textFormatRuns", "chipRuns"} if written else set()
    retained = {key: value for key, value in cell.items() if key not in excluded}
    if "pivotTable" in retained:
        pivot = {key: value for key, value in retained["pivotTable"].items() if key != "source"}
        if "source" in retained["pivotTable"]:
            source = retained["pivotTable"]["source"]
            pivot["source"] = {"sheetId": source["sheetId"]} if "sheetId" in source else {}
        retained["pivotTable"] = pivot
    invariant: dict[str, Any] = _formula_invariant(retained)
    return invariant


def _moved_row(row: int, resize: tuple[int, int] | None) -> int | None:
    if resize is None:
        return row
    old_end, end = resize
    if end < old_end and end <= row < old_end:
        return None
    return row + end - old_end if row >= old_end else row


def _check_owned_postimage(prepared: dict[str, Any], observed: dict[str, Any]) -> None:
    """Check owned writes and retained stable content, not provider formula text."""
    base = prepared["base_snapshot"]
    if set(observed["sheets"]) != set(base["sheets"]):
        raise ValueError("Workbook tabs changed during publication")
    if observed["metadata"].get("properties") != base["metadata"].get("properties"):
        raise ValueError("Workbook properties changed during publication")
    tabs = {str(tab["sheet_id"]): tab for tab in prepared["tabs"]}
    for sheet_id, old_sheet in base["sheets"].items():
        sheet = observed["sheets"][sheet_id]
        tab = tabs.get(sheet_id)
        old_tables = {table["tableId"]: table for table in old_sheet["metadata"].get("tables", [])}
        tables = {table["tableId"]: table for table in sheet["metadata"].get("tables", [])}
        resize = (
            (old_tables[tab["table_id"]]["range"]["endRowIndex"], tab["range"]["endRowIndex"])
            if tab is not None
            else None
        )
        for table_id, old_table in old_tables.items():
            if table_id not in tables:
                raise ValueError(f"Stable table identity disappeared: {table_id}")
            actual_table = tables[table_id]
            for field, value in old_table.items():
                if field not in {"range", "columnProperties"} and _formula_invariant(
                    actual_table.get(field)
                ) != _formula_invariant(value):
                    raise ValueError(f"Stable table configuration changed for {table_id}")
            actual_columns = {column["columnIndex"]: column for column in actual_table.get("columnProperties", [])}
            width = actual_table["range"]["endColumnIndex"] - actual_table["range"].get("startColumnIndex", 0)
            for column in old_table.get("columnProperties", []):
                index = column["columnIndex"]
                if index >= width:
                    continue
                for field, value in column.items():
                    if field != "columnName" and _formula_invariant(
                        actual_columns.get(index, {}).get(field)
                    ) != _formula_invariant(value):
                        raise ValueError(f"Stable table column configuration changed for {table_id}")
        before_properties, properties = old_sheet["metadata"]["properties"], sheet["metadata"]["properties"]
        for field in ("sheetId", "title", "sheetType", "hidden", "tabColor", "tabColorStyle", "rightToLeft"):
            if before_properties.get(field) != properties.get(field):
                raise ValueError(f"Sheet identity or presentation changed for {before_properties['title']}")
        owned: set[str] = set()
        if tab is not None:
            if tab["table_id"] not in tables or tables[tab["table_id"]]["range"] != tab["range"]:
                raise ValueError(f"Owned table range differs for {tab['sheet_name']}")
            start, left = tab["range"].get("startRowIndex", 0), tab["range"].get("startColumnIndex", 0)
            for row_index, row in enumerate(tab["rows"], start):
                for column, value in enumerate(row, left):
                    address = f"{row_index}:{column}"
                    owned.add(address)
                    cell = sheet["cells"].get(address, {})
                    if cell.get("userEnteredValue", {}) != _raw_cell(value).get("userEnteredValue", {}):
                        raise ValueError(f"Owned RAW value differs at {_a1_cell(tab['sheet_name'], column, row_index)}")
                    if cell.get("chipRuns") or cell.get("textFormatRuns"):
                        raise ValueError(f"Owned RAW write retained stale runs at {address}")
        for address, cell in old_sheet["cells"].items():
            row, column = map(int, address.split(":"))
            moved = _moved_row(row, resize)
            if moved is None:
                continue
            target = f"{moved}:{column}"
            actual = sheet["cells"].get(target, {})
            if _cell_invariant(cell, target in owned) != _cell_invariant(actual, target in owned):
                raise ValueError(f"Stable cell content changed at {_a1_cell(properties['title'], column, moved)}")
        for axis in ("row", "column"):
            for index, metadata in old_sheet[f"{axis}_metadata"].items():
                moved = _moved_row(int(index), resize) if axis == "row" else int(index)
                if moved is None:
                    continue
                actual = sheet[f"{axis}_metadata"].get(str(moved), {})
                for field in ("pixelSize", "hiddenByUser", "dataSourceColumnReference"):
                    if actual.get(field) != metadata.get(field):
                        raise ValueError(f"Explicit {axis} formatting changed on {properties['title']}")
