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

import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki.services.wiki_service import WikiService
from erenshor.cli.context import CLIContext
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.database.repositories.stances import StanceRepository
from erenshor.infrastructure.wiki.client import MediaWikiClient
from erenshor.registry.resolver import RegistryResolver

app = typer.Typer(
    name="wiki",
    help="Manage MediaWiki pages and content",
    no_args_is_help=True,
)

console = Console()


def _read_page_titles(pages_file: str) -> list[str]:
    """Read page titles from file or stdin.

    Args:
        pages_file: Path to file containing page titles (one per line), or "-" for stdin.

    Returns:
        List of page titles (stripped, no empty lines or comments).

    Raises:
        typer.Exit: If file doesn't exist or can't be read.
    """
    try:
        if pages_file == "-":
            # Read from stdin
            lines = sys.stdin.readlines()
        else:
            # Read from file
            file_path = Path(pages_file)
            if not file_path.exists():
                logger.error(f"File not found: {pages_file}")
                raise typer.Exit(1)
            lines = file_path.read_text(encoding="utf-8").splitlines()

        # Parse lines: strip whitespace, ignore empty lines and comments
        titles = []
        for raw_line in lines:
            line = raw_line.strip()
            if line and not line.startswith("#"):
                titles.append(line)

        logger.debug(f"Read {len(titles)} page titles from {pages_file}")
        return titles

    except Exception as e:
        logger.error(f"Failed to read page titles from {pages_file}: {e}")
        raise typer.Exit(1) from e


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
    skill_repo = SkillRepository(db_connection)
    stance_repo = StanceRepository(db_connection)
    faction_repo = FactionRepository(db_connection)
    spawn_repo = SpawnPointRepository(db_connection)
    loot_repo = LootTableRepository(db_connection)
    quest_repo = QuestRepository(db_connection)

    # Create registry resolver
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    mapping_json_path = cli_ctx.repo_root / "mapping.json"
    resolver = RegistryResolver(registry_db_path, game_db_path=db_path, mapping_json_path=mapping_json_path)

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

    # Create class display name service
    class_display = ClassDisplayNameService(db_connection)

    # Create and return service
    return WikiService(
        wiki_client=wiki_client,
        storage=storage,
        item_repo=item_repo,
        character_repo=character_repo,
        spell_repo=spell_repo,
        skill_repo=skill_repo,
        stance_repo=stance_repo,
        faction_repo=faction_repo,
        spawn_repo=spawn_repo,
        loot_repo=loot_repo,
        quest_repo=quest_repo,
        registry_resolver=resolver,
        class_display=class_display,
    )


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def fetch(
    ctx: typer.Context,
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to fetch (for testing)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-fetch even if pages are already cached",
    ),
    pages_file: str | None = typer.Option(
        None,
        "--pages-file",
        help="File with page titles to fetch (one per line), or '-' for stdin. If not specified, fetches all pages.",
    ),
) -> None:
    """Fetch wiki pages from MediaWiki.

    Downloads existing wiki pages from MediaWiki and saves them to local
    storage for later use during generation. This allows you to work offline
    and avoid re-fetching pages multiple times.

    By default, skips pages that have already been fetched. Use --force to
    re-fetch all pages regardless of cache status.

    You can specify which pages to fetch using --pages-file:
    - Fetch from file: --pages-file pages.txt
    - Fetch from stdin: --pages-file - < pages.txt
    - Fetch all pages: (no --pages-file option)

    When --pages-file is used, --limit is ignored.

    Fetched pages are cached in variants/{variant}/wiki/fetched/
    """
    cli_ctx: CLIContext = ctx.obj

    # Read page titles if specified
    page_titles: list[str] | None = None
    if pages_file:
        page_titles = _read_page_titles(pages_file)
        logger.info(f"Fetching {len(page_titles)} pages from {pages_file}")

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Fetching wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}\n"
            f"Pages: {'from ' + pages_file if pages_file else 'all'}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Fetch pages (all or specified)
        result = service.fetch_all(
            dry_run=cli_ctx.dry_run,
            limit=limit,
            force_refetch=force,
            page_titles=page_titles,
        )

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
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to generate (for testing)",
    ),
    pages_file: str | None = typer.Option(
        None,
        "--pages-file",
        help=(
            "File with page titles to generate (one per line), or '-' for stdin. If not specified, generates all pages."
        ),
    ),
) -> None:
    """Generate wiki pages locally.

    Creates new wiki pages from database content, merges with fetched pages
    (if available), preserves manually-edited fields, and removes legacy
    templates. Generated pages are saved locally for review before deployment.

    You can specify which pages to generate using --pages-file:
    - Generate from file: --pages-file pages.txt
    - Generate from stdin: --pages-file - < pages.txt
    - Generate all pages: (no --pages-file option)

    Generates all entity types (items, characters, spells, skills) and groups
    them by resolved page titles from the registry. Multi-entity pages (e.g.,
    spell + skill sharing one page) are automatically handled.

    Generated pages are saved to variants/{variant}/wiki/generated/

    You can review generated files before deploying them with:
        $ cat variants/{variant}/wiki/generated/*.txt
        $ git diff variants/{variant}/wiki/fetched/ variants/{variant}/wiki/generated/
    """
    cli_ctx: CLIContext = ctx.obj

    # Read page titles if specified
    page_titles: list[str] | None = None
    if pages_file:
        page_titles = _read_page_titles(pages_file)
        logger.info(f"Generating {len(page_titles)} pages from {pages_file}")

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Generating wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}\n"
            f"Pages: {'from ' + pages_file if pages_file else 'all'}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Generate pages (all or specified)
        result = service.generate_all(
            dry_run=cli_ctx.dry_run,
            limit=limit,
            page_titles=page_titles,
        )

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
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  Review generated files: {wiki_dir / 'generated'}")
            console.print("  Deploy to wiki: [cyan]erenshor wiki deploy[/cyan]")
            console.print()

    except Exception as e:
        console.print(f"[red]Error during wiki generation: {e}[/red]")
        logger.exception("Wiki generation failed")
        raise typer.Exit(1) from e


@app.command()
def deploy(
    ctx: typer.Context,
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Limit number of pages to deploy (for testing)",
    ),
    pages_file: str | None = typer.Option(
        None,
        "--pages-file",
        help="File with page titles to deploy (one per line), or '-' for stdin. If not specified, deploys all pages.",
    ),
) -> None:
    """Deploy generated wiki pages to MediaWiki.

    Uploads generated pages from local storage to MediaWiki. Only pages that have
    been generated (exist in variants/{variant}/wiki/generated/) will be deployed.

    You can specify which pages to deploy using --pages-file:
    - Deploy from file: --pages-file pages.txt
    - Deploy from stdin: --pages-file - < pages.txt
    - Deploy all pages: (no --pages-file option)

    Use --dry-run to preview what would be uploaded without actually doing it.
    """
    cli_ctx: CLIContext = ctx.obj

    # Read page titles if specified
    page_titles: list[str] | None = None
    if pages_file:
        page_titles = _read_page_titles(pages_file)
        logger.info(f"Deploying {len(page_titles)} pages from {pages_file}")

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Deploying wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}\n"
            f"Pages: {'from ' + pages_file if pages_file else 'all'}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        # Create service
        service = _create_wiki_service(cli_ctx)

        # Deploy pages (all or specified)
        result = service.deploy_all(
            dry_run=cli_ctx.dry_run,
            limit=limit,
            page_titles=page_titles,
        )

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
