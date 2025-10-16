"""Service for deploying game data to Google Sheets.

This module orchestrates the complete workflow:
1. Load SQL queries from queries directory
2. Execute queries and format data with SheetsFormatter
3. Publish formatted data with GoogleSheetsPublisher
4. Emit progress events
5. Handle errors gracefully
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from sqlalchemy.engine import Engine

from erenshor.application.formatters.sheets.items import SheetsFormatter
from erenshor.infrastructure.publishers.sheets import (
    GoogleSheetsPublisher,
)

__all__ = [
    "SheetsDeployService",
    "DeploymentResult",
    "SheetDeployment",
]


@dataclass
class SheetDeployment:
    """Details of a single sheet deployment."""

    sheet_name: str
    """Name of the sheet (e.g., 'items', 'characters')."""

    row_count: int
    """Number of data rows (excluding header)."""

    success: bool
    """Whether deployment succeeded."""

    error: str | None = None
    """Error message if deployment failed."""


@dataclass
class DeploymentResult:
    """Result of deploying all sheets."""

    success: bool
    """Whether all deployments succeeded."""

    total_sheets: int
    """Total number of sheets attempted."""

    successful_sheets: int
    """Number of sheets successfully deployed."""

    failed_sheets: int
    """Number of sheets that failed."""

    deployments: List[SheetDeployment]
    """Details of each sheet deployment."""

    spreadsheet_id: str
    """ID of the target spreadsheet."""


ProgressCallback = Callable[[str, int, int], None]
"""Callback signature: (sheet_name, current_index, total_sheets) -> None"""


class SheetsDeployService:
    """Orchestrate deployment of game data to Google Sheets.

    This service manages the complete deployment workflow:
    - Loads SQL queries from queries directory
    - Executes queries against SQLite database
    - Formats results for Google Sheets
    - Publishes to spreadsheet
    - Provides progress callbacks
    - Handles errors gracefully

    Example:
        service = SheetsDeployService(
            engine=create_engine("sqlite:///erenshor-main.sqlite"),
            queries_dir=Path("src/erenshor/application/formatters/sheets/queries"),
            publisher=GoogleSheetsPublisher(...),
        )

        result = service.deploy_all(
            spreadsheet_id="abc123",
            sheet_names=["items", "characters"],
            dry_run=False,
            progress_callback=lambda name, idx, total: print(f"{name} ({idx}/{total})"),
        )
    """

    def __init__(
        self,
        engine: Engine,
        queries_dir: Path,
        publisher: GoogleSheetsPublisher,
    ):
        """Initialize service.

        Args:
            engine: SQLAlchemy database engine
            queries_dir: Path to directory containing .sql query files
            publisher: Google Sheets publisher instance
        """
        self.engine = engine
        self.queries_dir = queries_dir
        self.publisher = publisher
        self.formatter = SheetsFormatter(engine, queries_dir)

    def get_available_sheets(self) -> List[str]:
        """Get list of all available sheet names from queries directory.

        Returns:
            List of sheet names
        """
        return self.formatter.get_sheet_names()

    def deploy_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        dry_run: bool = False,
    ) -> SheetDeployment:
        """Deploy a single sheet to Google Sheets.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_name: Name of the sheet to deploy
            dry_run: If True, format data but don't publish

        Returns:
            SheetDeployment with results
        """
        try:
            # Format data
            rows = self.formatter.format_sheet(sheet_name)
            row_count = len(rows) - 1  # Exclude header

            # Publish
            result = self.publisher.publish(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=rows,
                dry_run=dry_run,
            )

            return SheetDeployment(
                sheet_name=sheet_name,
                row_count=row_count,
                success=result.success,
                error=result.error,
            )

        except Exception as e:
            return SheetDeployment(
                sheet_name=sheet_name,
                row_count=0,
                success=False,
                error=str(e),
            )

    def deploy_all(
        self,
        spreadsheet_id: str,
        sheet_names: List[str] | None = None,
        dry_run: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> DeploymentResult:
        """Deploy multiple sheets to Google Sheets.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            sheet_names: List of sheet names to deploy (None = all sheets)
            dry_run: If True, format data but don't publish
            progress_callback: Optional callback for progress updates

        Returns:
            DeploymentResult with overall results
        """
        # Determine which sheets to deploy
        if sheet_names is None:
            sheet_names = self.get_available_sheets()

        deployments: List[SheetDeployment] = []
        total_sheets = len(sheet_names)

        # Deploy each sheet
        for idx, sheet_name in enumerate(sheet_names, start=1):
            # Progress callback
            if progress_callback:
                progress_callback(sheet_name, idx, total_sheets)

            # Deploy sheet
            deployment = self.deploy_sheet(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                dry_run=dry_run,
            )
            deployments.append(deployment)

        # Calculate summary
        successful = sum(1 for d in deployments if d.success)
        failed = total_sheets - successful
        overall_success = failed == 0

        return DeploymentResult(
            success=overall_success,
            total_sheets=total_sheets,
            successful_sheets=successful,
            failed_sheets=failed,
            deployments=deployments,
            spreadsheet_id=spreadsheet_id,
        )

    def test_connection(self) -> bool:
        """Test connection to Google Sheets API.

        Returns:
            True if connection successful
        """
        return self.publisher.test_connection()
