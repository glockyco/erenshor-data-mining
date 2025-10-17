"""Sheets commands for Google Sheets deployment.

This module provides commands for deploying data to Google Sheets:
- Listing available sheets and queries
- Validating Google Sheets credentials
- Deploying formatted data to spreadsheets
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="sheets",
    help="Deploy data to Google Sheets",
    no_args_is_help=True,
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
    typer.echo("Not yet implemented: sheets list")


@app.command()
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
    typer.echo("Not yet implemented: sheets deploy")
