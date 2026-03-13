"""Sheets service for orchestrating Google Sheets deployment.

This module provides the SheetsService class that orchestrates the complete
Google Sheets deployment workflow including:
- Listing available sheets from SQL query files
- Loading and executing SQL queries
- Formatting results for spreadsheets
- Publishing to Google Sheets via API
- Push-style progress notifications

The service uses a "fail-soft" approach where individual sheet failures don't
stop the entire batch, allowing users to see all issues at once.

Example:
    >>> from erenshor.application.sheets.service import SheetsService
    >>> from erenshor.application.sheets.formatter import SheetsFormatter
    >>> from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher
    >>>
    >>> # Initialize service with dependencies
    >>> formatter = SheetsFormatter(engine=engine, queries_dir=queries_dir, map_base_url=url)
    >>> publisher = GoogleSheetsPublisher(credentials_file=creds_path)
    >>> service = SheetsService(
    ...     formatter=formatter,
    ...     publisher=publisher,
    ...     spreadsheet_id="abc123",
    ... )
    >>>
    >>> # Deploy all sheets with progress display
    >>> result = service.deploy(all_sheets=True, dry_run=False)
    >>> print(f"Deployed {result.deployed} sheets")
"""

import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher


class SheetsServiceError(Exception):
    """Base exception for sheets service errors."""

    pass


@dataclass
class SheetMetadata:
    """Metadata for an available sheet.

    Attributes:
        name: Sheet name (e.g., 'items', 'characters').
        description: Description from SQL comment (if any).
        query_file: Path to the SQL query file.
        row_count: Number of data rows (excluding header), None if not yet queried.
    """

    name: str
    description: str
    query_file: Path
    row_count: int | None = None


@dataclass
class DeploymentResult:
    """Result of a sheets deployment operation.

    Attributes:
        total_sheets: Total number of sheets processed.
        deployed: Number of sheets successfully deployed.
        failed: Number of sheets that failed to deploy.
        total_rows: Total number of data rows deployed (excluding headers).
        errors: List of error messages.
        duration_seconds: Time taken for deployment in seconds.
    """

    total_sheets: int
    deployed: int
    failed: int
    total_rows: int
    errors: list[str]
    duration_seconds: float

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0


class SheetsService:
    """Service for orchestrating Google Sheets deployment.

    This service coordinates the sheets deployment workflow:
    1. List available sheets from SQL query files
    2. Load SQL queries from files
    3. Execute queries via SheetsFormatter
    4. Format results as spreadsheet rows
    5. Publish to Google Sheets via GoogleSheetsPublisher
    6. Display progress and notifications inline

    The service uses dependency injection for testability and follows
    a "fail-soft" approach where individual failures don't stop the batch.

    Example:
        >>> service = SheetsService(
        ...     formatter=formatter,
        ...     publisher=publisher,
        ...     spreadsheet_id="abc123",
        ... )
        >>> result = service.deploy(all_sheets=True)
        >>> print(f"Deployed: {result.deployed}, Failed: {result.failed}")
    """

    def __init__(
        self,
        formatter: SheetsFormatter,
        publisher: GoogleSheetsPublisher,
        spreadsheet_id: str,
    ) -> None:
        """Initialize sheets service.

        Args:
            formatter: SheetsFormatter for executing queries and formatting results.
            publisher: GoogleSheetsPublisher for publishing to Google Sheets API.
            spreadsheet_id: Google Sheets spreadsheet ID for publishing.
        """
        self._formatter = formatter
        self._publisher = publisher
        self._spreadsheet_id = spreadsheet_id

        # Console for Rich output
        self._console = Console()

        logger.debug("SheetsService initialized")

    def list_sheets(self) -> list[SheetMetadata]:
        """List available sheets from SQL query files.

        Returns:
            List of SheetMetadata for all available sheets.

        Example:
            >>> sheets = service.list_sheets()
            >>> for sheet in sheets:
            ...     print(f"{sheet.name}: {sheet.description}")
        """
        logger.info("Listing available sheets")

        sheet_names = self._formatter.get_sheet_names()
        metadata_list: list[SheetMetadata] = []

        for name in sheet_names:
            query_file = self._formatter.queries_dir / f"{name}.sql"

            # Extract description from first comment line in SQL file
            description = self._extract_description(query_file)

            metadata = SheetMetadata(
                name=name,
                description=description,
                query_file=query_file,
                row_count=None,  # Not queried yet
            )
            metadata_list.append(metadata)

        logger.debug(f"Found {len(metadata_list)} available sheets")
        return metadata_list

    def deploy(
        self,
        sheet_names: list[str] | None = None,
        all_sheets: bool = False,
        dry_run: bool = False,
    ) -> DeploymentResult:
        """Deploy sheets to Google Sheets.

        Args:
            sheet_names: List of sheet names to deploy (e.g., ['items', 'characters']).
                If None and all_sheets=False, no sheets are deployed.
            all_sheets: If True, deploy all available sheets.
            dry_run: If True, format data but don't publish to Google Sheets.

        Returns:
            DeploymentResult with summary statistics and errors.

        Raises:
            SheetsServiceError: If no sheets specified or invalid configuration.

        Example:
            >>> # Deploy specific sheets
            >>> result = service.deploy(sheet_names=['items', 'characters'])
            >>> # Deploy all sheets
            >>> result = service.deploy(all_sheets=True)
            >>> # Dry-run mode
            >>> result = service.deploy(all_sheets=True, dry_run=True)
        """
        start_time = time.time()

        # Determine which sheets to deploy
        if all_sheets:
            sheets_to_deploy = self._formatter.get_sheet_names()
            logger.info(f"Deploying all {len(sheets_to_deploy)} sheets")
        elif sheet_names:
            sheets_to_deploy = sheet_names
            logger.info(f"Deploying {len(sheets_to_deploy)} sheets: {', '.join(sheets_to_deploy)}")
        else:
            raise SheetsServiceError("Must specify either sheet_names or all_sheets=True")

        # Validate sheet names exist
        available_sheets = set(self._formatter.get_sheet_names())
        invalid_sheets = [name for name in sheets_to_deploy if name not in available_sheets]
        if invalid_sheets:
            raise SheetsServiceError(
                f"Invalid sheet names: {', '.join(invalid_sheets)}. "
                f"Available sheets: {', '.join(sorted(available_sheets))}"
            )

        # Track deployment progress
        total_sheets = len(sheets_to_deploy)
        deployed = 0
        failed = 0
        total_rows = 0
        errors: list[str] = []

        self._console.print(f"\n[bold]Deploying {total_sheets} sheets...[/bold]\n")

        # Deploy each sheet with progress tracking
        for sheet_name in track(
            sheets_to_deploy,
            description="Deploying sheets",
            total=total_sheets,
        ):
            try:
                # Format query results
                rows = self._formatter.format_sheet(sheet_name)
                row_count = len(rows) - 1  # Exclude header

                # Publish to Google Sheets (skip in dry-run)
                if not dry_run:
                    result = self._publisher.publish(
                        spreadsheet_id=self._spreadsheet_id,
                        sheet_name=sheet_name,
                        rows=rows,
                        dry_run=False,
                    )

                    if result.success:
                        deployed += 1
                        total_rows += row_count
                        self._console.print(f"[green]✓[/green] Deployed {sheet_name}: {row_count:,} rows")
                    else:
                        error_msg = f"Failed to deploy {sheet_name}: {result.error}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        self._console.print(f"[red]✗[/red] {error_msg}")
                        failed += 1
                else:
                    # In dry-run, count as deployed (would have been deployed)
                    deployed += 1
                    total_rows += row_count
                    self._console.print(f"[dim]○[/dim] Would deploy {sheet_name}: {row_count:,} rows")

            except Exception as e:
                error_msg = f"Error processing {sheet_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Calculate duration
        duration_seconds = time.time() - start_time

        # Display summary
        self._display_summary(
            total_sheets=total_sheets,
            deployed=deployed,
            failed=failed,
            total_rows=total_rows,
            errors=errors,
            duration_seconds=duration_seconds,
            dry_run=dry_run,
        )

        return DeploymentResult(
            total_sheets=total_sheets,
            deployed=deployed,
            failed=failed,
            total_rows=total_rows,
            errors=errors,
            duration_seconds=duration_seconds,
        )

    def _extract_description(self, query_file: Path) -> str:
        """Extract description from SQL file comment.

        Looks for the first comment line (-- ...) in the file and uses it
        as the description. If no comment found, uses the filename.

        Args:
            query_file: Path to SQL query file.

        Returns:
            Description string.
        """
        try:
            content = query_file.read_text(encoding="utf-8")
            for raw_line in content.splitlines():
                line = raw_line.strip()
                if line.startswith("--"):
                    # Remove comment prefix and strip whitespace
                    description = line[2:].strip()
                    if description:
                        return description
        except Exception as e:
            logger.warning(f"Failed to read {query_file}: {e}")

        # Fallback to filename
        return query_file.stem.replace("-", " ").title()

    def _display_summary(
        self,
        total_sheets: int,
        deployed: int,
        failed: int,
        total_rows: int,
        errors: list[str],
        duration_seconds: float,
        dry_run: bool,
    ) -> None:
        """Display deployment summary with Rich formatting.

        Args:
            total_sheets: Total sheets processed.
            deployed: Sheets successfully deployed.
            failed: Sheets that failed.
            total_rows: Total data rows deployed.
            errors: Error messages.
            duration_seconds: Time taken.
            dry_run: Whether this was a dry-run.
        """
        self._console.print()
        self._console.print("[bold]Summary:[/bold]")
        self._console.print(f"  Total sheets:  {total_sheets}")

        if dry_run:
            self._console.print(f"  [dim]Would deploy:  {deployed}[/dim]")
        else:
            self._console.print(f"  [green]Deployed:      {deployed}[/green]")

        if failed > 0:
            self._console.print(f"  [red]Failed:        {failed}[/red]")

        self._console.print(f"  Total rows:    {total_rows:,}")
        self._console.print(f"  Duration:      {duration_seconds:.1f}s")

        if errors:
            self._console.print(f"  [red]Errors:        {len(errors)}[/red]")

        if dry_run:
            self._console.print("\n[dim]Dry-run mode: No sheets were actually deployed[/dim]")

        self._console.print()
