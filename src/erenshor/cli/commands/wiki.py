"""Wiki commands for MediaWiki page management.

This module provides commands for managing MediaWiki content:
- Fetching templates and pages from the wiki
- Updating wiki pages with extracted game data
- Validating wiki content against database
"""

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.services.wiki_service import WikiService
from erenshor.cli.context import CLIContext
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.wiki.client import MediaWikiClient

app = typer.Typer(
    name="wiki",
    help="Manage MediaWiki pages and content",
    no_args_is_help=True,
)

console = Console()


def _create_wiki_service(cli_ctx: CLIContext) -> WikiService:
    """Create WikiService with dependencies.

    Args:
        cli_ctx: CLI context with config and variant info.

    Returns:
        Configured WikiService instance.
    """
    # Get variant config
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Create database connection
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    db_connection = DatabaseConnection(db_path, read_only=True)

    # Create repositories
    item_repo = ItemRepository(db_connection)
    character_repo = CharacterRepository(db_connection)
    spell_repo = SpellRepository(db_connection)

    # Create wiki client
    wiki_config = cli_ctx.config.global_.mediawiki
    wiki_client = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
    )

    # Create and return service
    return WikiService(
        wiki_client=wiki_client,
        item_repo=item_repo,
        character_repo=character_repo,
        spell_repo=spell_repo,
    )


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def update(
    ctx: typer.Context,
    entity_type: str = typer.Option(
        "items",
        "--entity-type",
        "-t",
        help="Entity type to update: items, characters, spells",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to update (for testing)",
    ),
) -> None:
    """Update wiki pages with new data.

    Generates updated wiki pages from database content and
    updates the wiki. Preserves manually-edited fields and
    removes legacy templates. Shows warnings for manual edits.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Updating {entity_type} wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Update pages based on entity type
        if entity_type == "items":
            result = service.update_item_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "characters":
            result = service.update_character_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "spells":
            result = service.update_spell_pages(dry_run=cli_ctx.dry_run, limit=limit)
        else:
            console.print(f"[red]Error: Invalid entity type '{entity_type}'[/red]")
            console.print("Valid types: items, characters, spells")
            raise typer.Exit(1)

        # Exit with error code if there were failures
        if result.failed > 0:
            logger.error(f"Update completed with {result.failed} failures")
            raise typer.Exit(1)

        # Exit with warning if there were warnings
        if result.has_warnings():
            logger.warning(f"Update completed with {len(result.warnings)} warnings")

    except Exception as e:
        console.print(f"[red]Error during wiki update: {e}[/red]")
        logger.exception("Wiki update failed")
        raise typer.Exit(1) from e


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
