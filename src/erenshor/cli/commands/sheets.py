"""Sheets commands for Google Sheets deployment.

This module provides commands for deploying data to Google Sheets:
- Listing available sheets and queries
- Validating Google Sheets credentials
- Deploying formatted data to spreadsheets
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import create_engine

from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.application.sheets.service import SheetsService
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="sheets",
    help="Deploy data to Google Sheets",
    no_args_is_help=True,
)

console = Console()


def _create_sheets_service(cli_ctx: CLIContext) -> SheetsService:
    """Create SheetsService with dependencies.

    Args:
        cli_ctx: CLI context with config and variant info.

    Returns:
        Configured SheetsService instance.
    """
    # Get variant config
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Create database engine for formatter
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    engine = create_engine(f"sqlite:///{db_path}")

    # Get queries directory path
    from pathlib import Path

    import erenshor.application.sheets

    queries_dir = Path(erenshor.application.sheets.__file__).parent / "queries"

    # Create formatter
    formatter = SheetsFormatter(engine=engine, queries_dir=queries_dir)

    # Create publisher
    sheets_config = cli_ctx.config.global_.google_sheets
    credentials_file = sheets_config.resolved_credentials_file(cli_ctx.repo_root)
    publisher = GoogleSheetsPublisher(credentials_file=credentials_file)

    # Get spreadsheet ID for variant
    variant_sheets_config = variant_config.google_sheets
    if not variant_sheets_config or not variant_sheets_config.spreadsheet_id:
        raise ValueError(f"No spreadsheet_id configured for variant '{cli_ctx.variant}'")

    spreadsheet_id = variant_sheets_config.spreadsheet_id

    # Create and return service
    return SheetsService(
        formatter=formatter,
        publisher=publisher,
        spreadsheet_id=spreadsheet_id,
    )


@app.command("list")
def list_sheets(
    ctx: typer.Context,
) -> None:
    """List available Google Sheets.

    Shows all available sheets and their corresponding SQL
    queries. Displays sheet names, descriptions, and whether
    they are configured for the current variant.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Available Google Sheets[/bold cyan]\nVariant: {cli_ctx.variant}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_sheets_service(cli_ctx)

        # Get sheet metadata
        sheets = service.list_sheets()

        if not sheets:
            console.print("[yellow]No sheets found[/yellow]")
            console.print()
            return

        # Display as table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Sheet Name", style="cyan")
        table.add_column("Description")
        table.add_column("Query File", style="dim")

        for sheet in sheets:
            table.add_row(
                sheet.name,
                sheet.description,
                str(sheet.query_file.name),
            )

        console.print(table)
        console.print()
        console.print(f"[bold]Total:[/bold] {len(sheets)} sheet(s)")
        console.print()

    except Exception as e:
        console.print(f"[red]Error listing sheets: {e}[/red]")
        logger.exception("Failed to list sheets")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def deploy(
    ctx: typer.Context,
    sheet_names: list[str] | None = typer.Option(
        None,
        "--sheets",
        help="Specific sheets to deploy (can be used multiple times)",
    ),
    all_sheets: bool = typer.Option(
        False,
        "--all-sheets",
        help="Deploy all available sheets",
    ),
) -> None:
    """Deploy data to Google Sheets.

    Executes SQL queries, formats results, and uploads to
    Google Sheets via API. Requires valid service account
    credentials with Editor access to the spreadsheet.
    Respects --dry-run flag.
    """
    cli_ctx: CLIContext = ctx.obj

    # Validate that either sheet_names or all_sheets is specified
    if not sheet_names and not all_sheets:
        console.print("[red]Error: Must specify either --sheets or --all-sheets[/red]")
        console.print()
        console.print("Examples:")
        console.print("  erenshor sheets deploy --sheets items")
        console.print("  erenshor sheets deploy --sheets items --sheets characters")
        console.print("  erenshor sheets deploy --all-sheets")
        console.print()
        raise typer.Exit(1)

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Deploying Google Sheets[/bold cyan]\nVariant: {cli_ctx.variant}\nDry-run: {cli_ctx.dry_run}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_sheets_service(cli_ctx)

        # Deploy sheets
        result = service.deploy(
            sheet_names=sheet_names,
            all_sheets=all_sheets,
            dry_run=cli_ctx.dry_run,
        )

        # Exit with error code if there were failures
        if result.failed > 0:
            logger.error(f"Deployment completed with {result.failed} failures")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error during sheets deployment: {e}[/red]")
        logger.exception("Sheets deployment failed")
        raise typer.Exit(1) from e
