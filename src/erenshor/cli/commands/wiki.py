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

import difflib
import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki.services.wiki_service import WikiService
from erenshor.application.wiki_deploy.article_identity import build_article_identity_map
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    build_repo_page_manifest,
    read_repo_page_manifest,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.override_migration import (
    ArticleOverrideReview,
    MissingArticleError,
    review_article_overrides,
)
from erenshor.application.wiki_deploy.pages import build_deployed_manifest, deploy_repo_pages
from erenshor.application.wiki_deploy.refresh import (
    refresh_embedded_pages,
    refresh_item_owners_for_source_changes,
)
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.application.wiki_interface.sync import MediaWikiInterfaceClient, sync_interface_pages
from erenshor.application.wiki_inventory.api import FixtureDirectoryTransport, MediaWikiInventoryClient
from erenshor.application.wiki_inventory.templates import render_ownership_manifest, template_inventory_from_api
from erenshor.application.wiki_lua.generation import (
    generate_lua_data_modules,
    item_shard_dir,
    planned_top_level_module_paths,
)
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
from erenshor.infrastructure.database.repositories.zones import ZoneRepository
from erenshor.infrastructure.wiki.client import MediaWikiClient

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
    zone_repo = ZoneRepository(db_connection)
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
    maps_base_url = variant_config.maps.base_url
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
        zone_repo=zone_repo,
        class_display=class_display,
        maps_base_url=maps_base_url,
    )


def _create_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create an authenticated MediaWiki client for deployment commands."""
    wiki_config = cli_ctx.config.global_.mediawiki
    client = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
    )
    client.login()
    return client


def _report_changed_cargo_declarations(manifest: RepoWikiPageManifest, changed_titles: set[str]) -> None:
    """Report changed Cargo-declaring templates so their tables can be recreated.
    Recreation is intentionally not automated: the Cargo API cannot switch in a
    replacement table, so an API-driven recreate would force a downtime window
    while the table repopulates. When a declaration's fields change, recreate the
    table via Special:CargoTables, which builds a replacement table and switches
    it in with no downtime.
    """
    changed = [entry for entry in manifest.entries if entry.declares_cargo_table and entry.title in changed_titles]
    if not changed:
        return
    tables = sorted({table for entry in changed for table in entry.cargo_tables})
    console.print(
        f"[yellow]{len(changed)} Cargo declaration(s) changed (tables: {', '.join(tables)}). "
        f"If the declared fields changed, recreate the table(s) via Special:CargoTables "
        f"(use a replacement table and 'Switch in' for no downtime).[/yellow]"
    )


def _join_fields(fields: list[str]) -> str:
    """Format a field list for a review report."""
    return ", ".join(fields) if fields else "(none)"


def _build_item_article_identities(cli_ctx: CLIContext) -> dict[str, tuple[str, ...]]:
    """Build the authoritative Item article title -> stable keys map."""
    item_repo = _create_item_repository(cli_ctx)
    return build_article_identity_map(item_repo.get_items_for_wiki_generation())


def _print_override_review(review: ArticleOverrideReview) -> None:
    """Print one review-only override minimization report."""
    if review.migration is None:
        console.print(f"[bold]{review.title}[/bold]")
        console.print(f"Skipped: {review.skipped_reason}", markup=False)
        return

    decisions = review.migration.classification.decisions
    manual_overrides = [decision.field for decision in decisions if decision.decision == "preserved_manual_override"]
    intentional_blanks = [decision.field for decision in decisions if decision.decision == "intentional_blank"]

    console.print(f"[bold]{review.title}[/bold]")
    console.print(f"Removed generated duplicates: {_join_fields(list(review.migration.removed_fields))}", markup=False)
    console.print(f"Preserved manual overrides: {_join_fields(manual_overrides)}", markup=False)
    console.print(f"Intentional blanks: {_join_fields(intentional_blanks)}", markup=False)

    diff = difflib.unified_diff(
        review.original_wikitext.splitlines(),
        review.migration.minimized_wikitext.splitlines(),
        fromfile=f"{review.title} (current)",
        tofile=f"{review.title} (minimized)",
        lineterm="",
    )
    for line in diff:
        console.print(line, markup=False)


def _create_item_repository(cli_ctx: CLIContext) -> ItemRepository:
    """Create an item repository for local Lua data generation."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    db_connection = DatabaseConnection(db_path, read_only=True)
    return ItemRepository(db_connection)


def _create_lua_repositories(
    cli_ctx: CLIContext,
) -> tuple[
    ItemRepository,
    CharacterRepository,
    SpawnPointRepository,
    LootTableRepository,
    SpellRepository,
    SkillRepository,
    StanceRepository,
    QuestRepository,
    ZoneRepository,
]:
    """Create repositories for local Lua data generation."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    db_connection = DatabaseConnection(db_path, read_only=True)
    return (
        ItemRepository(db_connection),
        CharacterRepository(db_connection),
        SpawnPointRepository(db_connection),
        LootTableRepository(db_connection),
        SpellRepository(db_connection),
        SkillRepository(db_connection),
        StanceRepository(db_connection),
        QuestRepository(db_connection),
        ZoneRepository(db_connection),
    )


def _lua_output_root(cli_ctx: CLIContext) -> Path:
    """Return the local generated Lua module output directory."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_wiki(cli_ctx.repo_root) / "lua"


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
    generator: list[str] | None = typer.Option(
        None,
        "--generator",
        "-g",
        help="Generator names to run (e.g. --generator zones). Default: all.",
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
            generator_names=generator,
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


@app.command("generate-lua")
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def generate_lua(ctx: typer.Context) -> None:
    """Generate local Lua data modules from the clean database."""
    cli_ctx: CLIContext = ctx.obj
    output_root = _lua_output_root(cli_ctx)
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Generating wiki Lua data modules[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}\n"
            f"Output: {output_root}",
            border_style="cyan",
        )
    )
    console.print()

    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: no database opened and no files written.[/yellow]")
        for module_path in planned_top_level_module_paths(output_root):
            console.print(f"Would write: {module_path}", soft_wrap=True)
        console.print(f"Would write item shards below: {item_shard_dir(output_root)}", soft_wrap=True)
        return

    try:
        item_repo, character_repo, spawn_repo, loot_repo, spell_repo, skill_repo, stance_repo, quest_repo, zone_repo = (
            _create_lua_repositories(cli_ctx)
        )
        result = generate_lua_data_modules(
            item_repo=item_repo,
            character_repo=character_repo,
            spawn_repo=spawn_repo,
            loot_repo=loot_repo,
            spell_usage_repo=spell_repo,
            spell_repo=spell_repo,
            skill_repo=skill_repo,
            stance_repo=stance_repo,
            quest_repo=quest_repo,
            zone_repo=zone_repo,
            output_root=output_root,
        )
        for path in result.written_paths:
            console.print(f"[green]Wrote:[/green] {path}", soft_wrap=True)
            console.print(f"[green]Validated with:[/green] {result.validation_tools[path]}")
    except Exception as e:
        console.print(f"[red]Error during wiki Lua generation: {e}[/red]")
        logger.exception("Wiki Lua generation failed")
        raise typer.Exit(1) from e


@app.command("inventory-templates")
def inventory_templates(
    ctx: typer.Context,
    output: Path = typer.Option(
        Path("wiki/ownership.yml"),
        "--output",
        "-o",
        help="Path to write the template ownership manifest.",
    ),
    fixture_dir: Path | None = typer.Option(
        None,
        "--fixture-dir",
        help="Replay recorded MediaWiki API fixtures instead of calling the live wiki.",
    ),
) -> None:
    """Inventory production templates and write the ownership manifest."""
    cli_ctx: CLIContext = ctx.obj
    wiki_config = cli_ctx.config.global_.mediawiki
    transport = FixtureDirectoryTransport(fixture_dir) if fixture_dir is not None else None
    client = MediaWikiInventoryClient(
        api_url=wiki_config.api_url,
        transport=transport,
        rate_limit_delay=wiki_config.api_delay,
    )

    try:
        manifest = render_ownership_manifest(template_inventory_from_api(client))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(manifest, encoding="utf-8")
        console.print(f"[green]Wrote template ownership manifest:[/green] {output}", soft_wrap=True)
    except Exception as e:
        console.print(f"[red]Error during template inventory: {e}[/red]")
        logger.exception("Template inventory failed")
        raise typer.Exit(1) from e
    finally:
        client.close()


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
    generator: list[str] | None = typer.Option(
        None,
        "--generator",
        "-g",
        help="Generator names to run (e.g. --generator zones --generator entities). Default: all.",
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
            generator_names=generator,
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
            console.print("  These are legacy Python-generated articles. During the Lua/Cargo cutover the article")
            console.print(
                "  deploy is gated: deploy repo-owned Lua data and templates with "
                "[cyan]erenshor wiki deploy-repo-pages[/cyan],"
            )
            console.print(
                "  or deploy these legacy articles intentionally with "
                "[cyan]erenshor wiki deploy --legacy-article-deploy[/cyan]."
            )
            console.print()

    except Exception as e:
        console.print(f"[red]Error during wiki generation: {e}[/red]")
        logger.exception("Wiki generation failed")
        raise typer.Exit(1) from e


@app.command("sync-interface")
def sync_interface(
    ctx: typer.Context,
    rate_limit_delay: Annotated[
        float,
        typer.Option(
            help="Delay between live wiki API reads.",
            min=0.0,
        ),
    ] = 1.0,
) -> None:
    """Sync live MediaWiki interface pages for local preview.

    Writes the gitignored local mirror to wiki-dev/interface and CSS assets to wiki-dev/images.
    """
    cli_ctx: CLIContext = ctx.obj
    output_root = Path("wiki-dev/interface")
    image_root = Path("wiki-dev/images")
    client = MediaWikiInterfaceClient(api_url="https://erenshor.wiki.gg/api.php", rate_limit_delay=rate_limit_delay)
    try:
        result = sync_interface_pages(
            client=client,
            output_root=output_root,
            image_root=image_root,
            dry_run=cli_ctx.dry_run,
        )
    except Exception as e:
        console.print(f"[red]Error during wiki interface sync: {e}[/red]")
        logger.exception("Wiki interface sync failed")
        raise typer.Exit(1) from e
    finally:
        client.close()

    if cli_ctx.dry_run:
        console.print("[yellow]Dry run - no files written[/yellow]")

    for page in result.changed_pages:
        if page.diff:
            console.print(page.diff, end="")

    for asset in result.missing_assets:
        console.print(f"[yellow]Skipped unresolved live CSS asset {asset.source_path} ({asset.file_title})[/yellow]")

    changed_assets = [asset for asset in result.assets if asset.changed]
    console.print(
        f"Synced {len(result.pages)} MediaWiki interface pages to {output_root} "
        f"({len(result.changed_pages)} changed) and {len(result.assets)} CSS assets to {image_root} "
        f"({len(changed_assets)} changed)"
    )


@app.command("deploy-repo-pages")
def deploy_repo_pages_command(
    ctx: typer.Context,
    pages_file: Annotated[
        str | None,
        typer.Option(
            "--pages-file",
            help="Deploy only repo-owned page titles listed in this file, or '-' for stdin.",
        ),
    ] = None,
    summary: Annotated[
        str,
        typer.Option("--summary", help="Edit summary for repo-owned page uploads."),
    ] = "Deploy repo-owned wiki pages",
    assert_user: Annotated[
        str | None,
        typer.Option("--assert-user", help="Expected MediaWiki username for assertuser guard."),
    ] = None,
    manifest_output: Annotated[
        Path | None,
        typer.Option("--manifest-output", help="Path for the deployment manifest JSON."),
    ] = None,
) -> None:
    """Deploy repo-owned Lua modules, templates, and generated Lua data."""
    cli_ctx: CLIContext = ctx.obj
    manifest = build_repo_page_manifest(cli_ctx.repo_root, variant=cli_ctx.variant)
    if pages_file:
        requested_titles = set(_read_page_titles(pages_file))
        manifest = RepoWikiPageManifest(
            entries=tuple(entry for entry in manifest.entries if entry.title in requested_titles)
        )
    if manifest_output is None:
        manifest_output = (
            cli_ctx.config.variants[cli_ctx.variant].resolved_wiki(cli_ctx.repo_root) / "deploy-manifest.json"
        )

    if cli_ctx.dry_run:
        scope = f" filtered by {pages_file}" if pages_file else ""
        console.print(f"[yellow]Dry run: {len(manifest.entries)} repo-owned pages in manifest{scope}[/yellow]")
        return

    client = _create_mediawiki_client(cli_ctx)
    try:
        result = deploy_repo_pages(
            manifest=manifest,
            repo_root=cli_ctx.repo_root,
            client=client,
            summary=summary,
            assertion="bot",
            assert_user=assert_user,
            rollback_root=manifest_output.parent / "rollback",
        )
    finally:
        client.close()

    deployed_manifest = build_deployed_manifest(manifest, result)
    write_repo_page_manifest(deployed_manifest, manifest_output)

    created = sum(1 for entry in result.entries if entry.status == "created")
    edited = sum(1 for entry in result.entries if entry.status == "edited")
    unchanged = sum(1 for entry in result.entries if entry.status == "unchanged")
    console.print(
        f"[green]Repo-owned page deploy complete[/green] Created: {created} Edited: {edited} "
        f"Unchanged: {unchanged} Manifest: {manifest_output}"
    )

    changed_titles = {entry.title for entry in result.entries if entry.status != "unchanged"}
    _report_changed_cargo_declarations(manifest, changed_titles)


@app.command("review-overrides")
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
)
def review_overrides_command(
    ctx: typer.Context,
    page_titles: Annotated[
        list[str] | None,
        typer.Option("--page", help="Article title to review. May be repeated."),
    ] = None,
    pages_file: Annotated[
        str | None,
        typer.Option("--pages-file", "-p", help="File containing article titles, one per line."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of pages to review."),
    ] = None,
    template_names: Annotated[
        list[str] | None,
        typer.Option("--template", help="Root infobox template name. May be repeated."),
    ] = None,
    module: Annotated[
        str,
        typer.Option("--module", help="Lua presentation module exposing the field accessor."),
    ] = "Erenshor/Item",
) -> None:
    """Review article infobox parameters that duplicate generated Lua values."""
    cli_ctx: CLIContext = ctx.obj
    article_identities = _build_item_article_identities(cli_ctx)
    titles = list(page_titles or ())
    if pages_file:
        titles.extend(_read_page_titles(pages_file))
    if not titles:
        titles = sorted(article_identities)
    if limit is not None:
        titles = titles[:limit]

    templates = tuple(template_names or ("Item",))
    client = _create_mediawiki_client(cli_ctx)
    try:
        reviews = review_article_overrides(
            client=client,
            titles=tuple(titles),
            template_names=templates,
            module=module,
            article_identities=article_identities,
        )
    except MissingArticleError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    finally:
        client.close()

    changed = sum(1 for review in reviews if review.changed)
    skipped = sum(1 for review in reviews if review.migration is None)
    console.print(
        f"[green]Article override review complete[/green] "
        f"Changed: {changed} Skipped: {skipped} Reviewed: {len(reviews)}"
    )
    for review in reviews:
        _print_override_review(review)


@app.command("refresh-embedded")
def refresh_embedded_command(
    ctx: typer.Context,
    dependency_titles: Annotated[
        list[str] | None,
        typer.Option(
            "--dependency-title",
            help="Template or module title whose transcluding pages should be refreshed.",
        ),
    ] = None,
    source_tables: Annotated[
        list[str] | None,
        typer.Option(
            "--source-table",
            help="Source data table whose item-owned Cargo pages should be reparsed.",
        ),
    ] = None,
    namespaces: Annotated[
        list[int] | None,
        typer.Option("--namespace", help="MediaWiki namespace ID to include in embeddedin discovery."),
    ] = None,
    assert_user: Annotated[
        str | None,
        typer.Option("--assert-user", help="Expected MediaWiki username for assertuser guard."),
    ] = None,
) -> None:
    """Force a link/Cargo refresh on pages that transclude the given templates/modules."""
    cli_ctx: CLIContext = ctx.obj
    dependency_titles = dependency_titles or []
    source_tables = source_tables or []
    namespaces = namespaces or []
    if not dependency_titles and not source_tables:
        console.print("[red]At least one dependency title or source table is required.[/red]")
        raise typer.Exit(1)
    if dependency_titles and not namespaces:
        console.print("[red]At least one --namespace is required with dependency titles.[/red]")
        raise typer.Exit(1)

    if cli_ctx.dry_run:
        console.print(
            f"[yellow]Dry run: would refresh pages for {len(dependency_titles)} dependencies and "
            f"{len(source_tables)} source tables in namespaces "
            f"{', '.join(str(namespace) for namespace in namespaces)}[/yellow]"
        )
        return

    client = _create_mediawiki_client(cli_ctx)
    refreshed_titles: set[str] = set()
    try:
        if dependency_titles:
            refreshed_titles.update(
                refresh_embedded_pages(
                    client=client,
                    dependency_titles=tuple(dependency_titles),
                    namespaces=tuple(namespaces),
                    assertion="bot",
                    assert_user=assert_user,
                ).refreshed
            )
        if source_tables:
            refreshed_titles.update(
                refresh_item_owners_for_source_changes(
                    client=client,
                    changed_source_tables=tuple(source_tables),
                    assertion="bot",
                    assert_user=assert_user,
                ).refreshed
            )
    finally:
        client.close()

    console.print(f"[green]Embedded dependency refresh complete[/green] Refreshed: {len(refreshed_titles)}")


@app.command("rollback-repo-pages")
def rollback_repo_pages_command(
    ctx: typer.Context,
    manifest_path: Annotated[
        Path,
        typer.Option("--manifest", help="Deployment manifest JSON produced by deploy-repo-pages."),
    ],
    summary: Annotated[
        str,
        typer.Option("--summary", help="Edit summary for rollback edits."),
    ] = "Rollback repo-owned wiki deploy",
    assert_user: Annotated[
        str | None,
        typer.Option("--assert-user", help="Expected MediaWiki username for assertuser guard."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Restore even if a page changed since the deploy being rolled back."),
    ] = False,
) -> None:
    """Restore repo-owned page text recorded in a deployment manifest."""
    cli_ctx: CLIContext = ctx.obj
    if not manifest_path.exists():
        console.print(f"[red]Deployment manifest not found: {manifest_path}[/red]")
        raise typer.Exit(1)

    manifest = read_repo_page_manifest(manifest_path)

    if cli_ctx.dry_run:
        restorable = sum(1 for entry in manifest.entries if entry.rollback_text_source is not None)
        console.print(f"[yellow]Dry run: {restorable} repo-owned pages with recorded rollback text[/yellow]")
        return

    client = _create_mediawiki_client(cli_ctx)
    try:
        result = rollback_repo_pages(
            manifest=manifest,
            repo_root=cli_ctx.repo_root,
            client=client,
            summary=summary,
            assertion="bot",
            assert_user=assert_user,
            force=force,
        )
    finally:
        client.close()

    console.print(f"[green]Repo-owned page rollback complete[/green] Restored: {len(result.entries)}")
    if result.created_titles:
        console.print(
            "[yellow]These pages were created by the deploy and need manual deletion "
            "(the deploy bot cannot delete pages):[/yellow]"
        )
        for created_title in result.created_titles:
            console.print(f"  {created_title}", markup=False)

    rolled_back_titles = {entry.title for entry in result.entries}
    _report_changed_cargo_declarations(manifest, rolled_back_titles)


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
    from_dir: str | None = typer.Option(
        None,
        "--from-dir",
        help="Deploy .txt files from this directory instead of generated storage. Title derived from filename.",
    ),
    legacy_article_deploy: bool = typer.Option(
        False,
        "--legacy-article-deploy",
        help="Allow the legacy Python-generated article deploy path during Lua cutover.",
    ),
) -> None:
    """Deploy legacy Python-generated article pages to MediaWiki."""
    cli_ctx: CLIContext = ctx.obj
    if not legacy_article_deploy:
        console.print(
            "[red]Legacy article deploy is disabled during Lua/Cargo cutover. "
            "Use 'wiki deploy-repo-pages' for repo-owned Lua/templates, or pass "
            "--legacy-article-deploy to run the old generated article deploy path intentionally.[/red]"
        )
        raise typer.Exit(1)

    try:
        service = _create_wiki_service(cli_ctx)

        if from_dir:
            result = service.deploy_from_dir(
                source_dir=Path(from_dir),
                dry_run=cli_ctx.dry_run,
            )
        else:
            page_titles: list[str] | None = None
            if pages_file:
                page_titles = _read_page_titles(pages_file)
                logger.info(f"Deploying {len(page_titles)} pages from {pages_file}")

            console.print()
            console.print(
                Panel.fit(
                    f"[bold cyan]Deploying legacy generated wiki article pages[/bold cyan]\n"
                    f"Variant: {cli_ctx.variant}\n"
                    f"Dry-run: {cli_ctx.dry_run}\n"
                    f"Pages: {'from ' + pages_file if pages_file else 'all'}",
                    border_style="cyan",
                )
            )
            console.print()

            result = service.deploy_all(
                dry_run=cli_ctx.dry_run,
                limit=limit,
                page_titles=page_titles,
            )

        if result.has_warnings():
            logger.warning(f"Deployment completed with {len(result.warnings)} warnings")

        if result.failed > 0:
            logger.error(f"Deployment completed with {result.failed} failures")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error during wiki deployment: {e}[/red]")
        logger.exception("Wiki deployment failed")
        raise typer.Exit(1) from e
