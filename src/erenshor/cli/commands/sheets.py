"""Sheets commands for Google Sheets deployment.

This module provides commands for deploying data to Google Sheets:
- Listing available sheets and queries
- Validating Google Sheets credentials
- Deploying formatted data to spreadsheets
"""

import typer

app = typer.Typer(
    name="sheets",
    help="Deploy data to Google Sheets",
    no_args_is_help=True,
)
