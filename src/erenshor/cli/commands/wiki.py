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


@app.command()
def fetch(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-fetch even if cached data exists",
    ),
) -> None:
    """Fetch current wiki templates and pages.

    Downloads current wiki page content and templates from
    MediaWiki for comparison with database content. Cached
    locally for offline comparison and conflict resolution.
    """
    typer.echo("Not yet implemented: wiki fetch")


@app.command()
def update(
    ctx: typer.Context,
) -> None:
    """Update wiki pages with new data.

    Generates updated wiki pages from database content and
    compares with current wiki state. Shows diffs and prepares
    pages for pushing. Respects --dry-run flag.
    """
    typer.echo("Not yet implemented: wiki update")


@app.command()
def push(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force push even if conflicts exist",
    ),
) -> None:
    """Push changes to wiki.

    Uploads prepared wiki page changes to MediaWiki. Requires
    MediaWiki credentials and edit permissions. Will abort if
    conflicts exist unless --force is used.
    """
    typer.echo("Not yet implemented: wiki push")


@app.command()
def conflicts(
    ctx: typer.Context,
) -> None:
    """List wiki page conflicts.

    Shows pages that have been modified on the wiki since last
    fetch, which would conflict with local changes. Used to
    identify pages that need conflict resolution before pushing.
    """
    typer.echo("Not yet implemented: wiki conflicts")


@app.command()
def resolve_conflict(
    ctx: typer.Context,
    conflict_id: int = typer.Argument(
        ...,
        help="ID of the conflict to resolve",
    ),
) -> None:
    """Resolve a specific conflict.

    Interactive conflict resolution for a wiki page. Shows
    both versions and allows choosing how to merge changes.
    """
    typer.echo(f"Not yet implemented: wiki resolve-conflict (ID: {conflict_id})")
