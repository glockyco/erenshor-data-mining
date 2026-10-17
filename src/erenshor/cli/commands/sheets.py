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

from erenshor.application.sheets.service import SheetsService, create_sheets_service
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="sheets",
    help="Deploy data to Google Sheets",
    no_args_is_help=True,
)

console = Console()


def _create_sheets_service(cli_ctx: CLIContext, *, service: SheetsService | None = None) -> SheetsService:
    """Create SheetsService with dependencies.

    Args:
        cli_ctx: CLI context with config and variant info.
        service: A caller-supplied service, such as a test's double, returned
            unchanged instead of building the real one.

    Returns:
        Configured SheetsService instance.
    """
    if service is not None:
        return service
    return create_sheets_service(cli_ctx)


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
