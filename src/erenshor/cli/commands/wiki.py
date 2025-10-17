"""Wiki commands for MediaWiki page management.

This module provides commands for managing MediaWiki content:
- Fetching templates and pages from the wiki
- Updating wiki pages with extracted game data
- Validating wiki content against database
"""

import typer

app = typer.Typer(
    name="wiki",
    help="Manage MediaWiki pages and content",
    no_args_is_help=True,
)
