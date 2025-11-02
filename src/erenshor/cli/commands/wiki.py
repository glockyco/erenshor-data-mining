"""Wiki commands for MediaWiki page management.

This module provides commands for managing MediaWiki content through a three-stage
workflow:

1. fetch: Download existing pages from MediaWiki and cache locally
2. generate: Create new pages from database, merge with fetched content, save locally
3. deploy: Upload generated pages to MediaWiki

This workflow enables reviewing content before deployment and interrupting/resuming
at any stage.

Example workflow:
    $ erenshor wiki fetch --entity-type items
    $ erenshor wiki generate --entity-type items
    $ # Review generated files in variants/main/wiki/generated/
    $ erenshor wiki deploy --entity-type items
"""

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.services.wiki_service import WikiService
from erenshor.application.services.wiki_storage import WikiStorage
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

    # Create wiki storage
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    storage = WikiStorage(wiki_dir)

    # Create and return service
    return WikiService(
        wiki_client=wiki_client,
        storage=storage,
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
def fetch(
    ctx: typer.Context,
    entity_type: str = typer.Option(
        "items",
        "--entity-type",
        "-t",
        help="Entity type to fetch: items, characters, spells",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to fetch (for testing)",
    ),
) -> None:
    """Fetch wiki pages from MediaWiki.

    Downloads existing wiki pages from MediaWiki and saves them to local
    storage for later use during generation. This allows you to work offline
    and avoid re-fetching pages multiple times.

    Fetched pages are cached in variants/{variant}/wiki/fetched/
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Fetching {entity_type} wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Fetch pages based on entity type
        if entity_type == "items":
            result = service.fetch_item_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "characters":
            result = service.fetch_character_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "spells":
            result = service.fetch_spell_pages(dry_run=cli_ctx.dry_run, limit=limit)
        else:
            console.print(f"[red]Error: Invalid entity type '{entity_type}'[/red]")
            console.print("Valid types: items, characters, spells")
            raise typer.Exit(1)

        # Show warnings and errors
        if result.has_warnings():
            logger.warning(f"Fetch completed with {len(result.warnings)} warnings")

        if result.failed > 0:
            logger.error(f"Fetch completed with {result.failed} failures")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error during wiki fetch: {e}[/red]")
        logger.exception("Wiki fetch failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def generate(
    ctx: typer.Context,
    entity_type: str = typer.Option(
        "items",
        "--entity-type",
        "-t",
        help="Entity type to generate: items, characters, spells",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to generate (for testing)",
    ),
) -> None:
    """Generate wiki pages locally.

    Creates new wiki pages from database content, merges with fetched pages
    (if available), preserves manually-edited fields, and removes legacy
    templates. Generated pages are saved locally for review before deployment.

    Generated pages are saved to variants/{variant}/wiki/generated/

    You can review generated files before deploying them with:
        $ cat variants/{variant}/wiki/generated/item:*.txt
        $ git diff variants/{variant}/wiki/fetched/ variants/{variant}/wiki/generated/
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Generating {entity_type} wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Generate pages based on entity type
        if entity_type == "items":
            result = service.generate_item_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "characters":
            result = service.generate_character_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "spells":
            result = service.generate_spell_pages(dry_run=cli_ctx.dry_run, limit=limit)
        else:
            console.print(f"[red]Error: Invalid entity type '{entity_type}'[/red]")
            console.print("Valid types: items, characters, spells")
            raise typer.Exit(1)

        # Show warnings and errors
        if result.has_warnings():
            logger.warning(f"Generation completed with {len(result.warnings)} warnings")

        if result.failed > 0:
            logger.error(f"Generation completed with {result.failed} failures")
            raise typer.Exit(1)

        # Show next steps
        if not cli_ctx.dry_run and result.succeeded > 0:
            variant_config = cli_ctx.config.variants[cli_ctx.variant]
            wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
            console.print(f"[bold]Next steps:[/bold]")
            console.print(f"  Review generated files: {wiki_dir / 'generated'}")
            console.print(f"  Deploy to wiki: [cyan]erenshor wiki deploy --entity-type {entity_type}[/cyan]")
            console.print()

    except Exception as e:
        console.print(f"[red]Error during wiki generation: {e}[/red]")
        logger.exception("Wiki generation failed")
        raise typer.Exit(1) from e


@app.command()
def deploy(
    ctx: typer.Context,
    entity_type: str = typer.Option(
        "items",
        "--entity-type",
        "-t",
        help="Entity type to deploy: items, characters, spells",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to deploy (for testing)",
    ),
) -> None:
    """Deploy generated wiki pages to MediaWiki.

    Uploads pages from local storage to MediaWiki. Only pages that have been
    generated (exist in variants/{variant}/wiki/generated/) will be deployed.

    Use --dry-run to preview what would be uploaded without actually doing it.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Deploying {entity_type} wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Deploy pages based on entity type
        if entity_type == "items":
            result = service.deploy_item_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "characters":
            result = service.deploy_character_pages(dry_run=cli_ctx.dry_run, limit=limit)
        elif entity_type == "spells":
            result = service.deploy_spell_pages(dry_run=cli_ctx.dry_run, limit=limit)
        else:
            console.print(f"[red]Error: Invalid entity type '{entity_type}'[/red]")
            console.print("Valid types: items, characters, spells")
            raise typer.Exit(1)

        # Show warnings and errors
        if result.has_warnings():
            logger.warning(f"Deployment completed with {len(result.warnings)} warnings")

        if result.failed > 0:
            logger.error(f"Deployment completed with {result.failed} failures")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error during wiki deployment: {e}[/red]")
        logger.exception("Wiki deployment failed")
        raise typer.Exit(1) from e
