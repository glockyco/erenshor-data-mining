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
import tempfile
import uuid
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki.services.deploy_service import WikiDeployService
from erenshor.application.wiki.services.fetch_service import WikiFetchService
from erenshor.application.wiki.services.generate_service import WikiGenerateService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.article_identity import build_article_identity_map
from erenshor.application.wiki_deploy.link_audit import (
    ERROR_CODES,
    FINDING_CODES,
    LinkAuditReport,
)
from erenshor.application.wiki_deploy.link_audit_service import LinkAuditService
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    build_repo_page_manifest,
    read_repo_page_manifest,
    select_repo_page_manifest,
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
from erenshor.application.wiki_interface.deploy import (
    InterfaceDeployPlan,
    deploy_interface_pages,
    plan_interface_pages,
    rollback_interface_pages,
)
from erenshor.application.wiki_interface.manifest import (
    InterfaceDeployManifest,
    read_interface_deploy_manifest,
    write_interface_deploy_manifest,
)
from erenshor.application.wiki_interface.sync import MediaWikiInterfaceClient, sync_interface_pages
from erenshor.application.wiki_inventory.api import FixtureDirectoryTransport, MediaWikiInventoryClient
from erenshor.application.wiki_inventory.templates import render_ownership_manifest, template_inventory_from_api
from erenshor.application.wiki_lua.generation import (
    generate_lua_data_modules,
    item_shard_dir,
    planned_top_level_module_paths,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry, build_link_catalog_entries
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
from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestor, MediaWikiRequestPolicy

app = typer.Typer(
    name="wiki",
    help="Manage MediaWiki pages and content",
    no_args_is_help=True,
)

console = Console()

_INTERFACE_ARTIFACT_ROOT = Path("output/wiki-interface")
_INTERFACE_ROLLBACK_ROOT = Path("rollback")


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


@dataclass(frozen=True, slots=True)
class _MediaWikiCredentials:
    """Credentials selected for one CLI-owned MediaWiki client."""

    username: str
    password: str


def _normal_bot_credentials(cli_ctx: CLIContext) -> _MediaWikiCredentials:
    """Return the normal bot credentials used by wiki data commands."""
    wiki_config = cli_ctx.config.global_.mediawiki
    return _MediaWikiCredentials(wiki_config.bot_username, wiki_config.bot_password)


def _interface_admin_credentials(cli_ctx: CLIContext) -> _MediaWikiCredentials:
    """Return dedicated interface-admin credentials without bot fallback."""
    wiki_config = cli_ctx.config.global_.mediawiki
    username = wiki_config.interface_username.strip()
    password = wiki_config.interface_password
    if not username or not password:
        raise ValueError(
            "Interface deployment requires dedicated interface-admin credentials. "
            "Set [global.mediawiki].interface_username and interface_password in "
            ".erenshor/config.local.toml; bot_username and bot_password are never used as a fallback."
        )
    return _MediaWikiCredentials(username, password)


@dataclass(slots=True)
class _WikiComposition:
    """Own the resources shared by one fetch, generate, or deploy command."""

    database: DatabaseConnection
    context: GeneratorContext
    storage: WikiStorage
    wiki_client: MediaWikiClient | None = None

    def __enter__(self) -> "_WikiComposition":
        return self

    def __exit__(self, *_: object) -> None:
        try:
            if self.wiki_client is not None:
                self.wiki_client.close()
        finally:
            self.database.close()


def _create_normal_bot_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create a normal bot client without logging in yet."""
    wiki_config = cli_ctx.config.global_.mediawiki
    credentials = _normal_bot_credentials(cli_ctx)
    return MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=credentials.username,
        bot_password=credentials.password,
    )


def _create_wiki_composition(cli_ctx: CLIContext, *, with_client: bool) -> _WikiComposition:
    """Create one database, storage, and GeneratorContext for a wiki command."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    database = DatabaseConnection(variant_config.resolved_database(cli_ctx.repo_root), read_only=True)
    storage = WikiStorage(variant_config.resolved_wiki(cli_ctx.repo_root))
    maps_source_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    zone_positions_path = maps_source_dir / "src" / "lib" / "data" / "zone-positions.json"
    zone_output_dir = cli_ctx.repo_root / "wiki" / "zones"
    context = GeneratorContext(
        item_repo=ItemRepository(database),
        character_repo=CharacterRepository(database),
        spell_repo=SpellRepository(database),
        skill_repo=SkillRepository(database),
        stance_repo=StanceRepository(database),
        faction_repo=FactionRepository(database),
        spawn_repo=SpawnPointRepository(database),
        loot_repo=LootTableRepository(database),
        quest_repo=QuestRepository(database),
        zone_repo=ZoneRepository(database),
        storage=storage,
        class_display=ClassDisplayNameService(database),
        maps_base_url=variant_config.maps.base_url,
        zone_positions_path=zone_positions_path,
        zone_output_dir=zone_output_dir,
    )
    wiki_client = None
    try:
        if with_client:
            wiki_client = _create_normal_bot_mediawiki_client(cli_ctx)
    except Exception:
        database.close()
        raise
    return _WikiComposition(database=database, context=context, storage=storage, wiki_client=wiki_client)


def _create_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create an authenticated MediaWiki client for deployment commands."""
    wiki_config = cli_ctx.config.global_.mediawiki
    credentials = _normal_bot_credentials(cli_ctx)
    client = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=credentials.username,
        bot_password=credentials.password,
    )
    client.login()
    return client


def _interface_assert_user(cli_ctx: CLIContext) -> str:
    """Return the owning username asserted for interface BotPassword sessions."""
    login_name = cli_ctx.config.global_.mediawiki.interface_username.strip()
    return login_name.partition("@")[0]


def _create_readonly_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create an anonymous client for read-only manifest dependency checks."""
    wiki_config = cli_ctx.config.global_.mediawiki
    return MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
    )


def _create_interface_mediawiki_client(cli_ctx: CLIContext) -> MediaWikiClient:
    """Create and log in the dedicated interface-admin MediaWiki client."""
    wiki_config = cli_ctx.config.global_.mediawiki
    credentials = _interface_admin_credentials(cli_ctx)

    client = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=credentials.username,
        bot_password=credentials.password,
        batch_size=wiki_config.upload_batch_size,
        rate_limit_delay=wiki_config.upload_delay,
        edit_summary=wiki_config.upload_edit_summary,
        minor_edit=wiki_config.upload_minor_edit,
    )
    try:
        client.login()
    except Exception:
        client.close()
        raise
    return client


def _interface_artifact_root(cli_ctx: CLIContext) -> Path:
    """Return the dedicated repository-local interface artifact root."""
    return (cli_ctx.repo_root / _INTERFACE_ARTIFACT_ROOT).resolve()


def _resolve_interface_manifest_path(cli_ctx: CLIContext, path: Path) -> Path:
    """Resolve an interface manifest within the dedicated artifact root."""
    root = cli_ctx.repo_root.resolve()
    artifact_root = _interface_artifact_root(cli_ctx)
    try:
        artifact_root.relative_to(root)
    except ValueError as error:
        raise ValueError("Dedicated interface artifact root must stay inside the repository root") from error
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError as error:
        raise ValueError(
            "Interface manifest path must be inside the repository root and the dedicated interface artifact root"
        ) from error
    if resolved == artifact_root:
        raise ValueError("Interface manifest path must name a file below the dedicated interface artifact root")
    return resolved


def _path_alias(left: Path, right: Path) -> bool:
    """Return whether two paths identify the same file, including hard links."""
    if left == right:
        return True
    if not left.exists() or not right.exists():
        return False
    try:
        return left.samefile(right)
    except OSError:
        return False


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_interface_manifest_output(
    cli_ctx: CLIContext,
    manifest_output: Path,
    plan: InterfaceDeployPlan,
) -> None:
    """Reject manifest paths that can overwrite interface inputs or rollback artifacts."""
    root = cli_ctx.repo_root.resolve()
    artifact_root = _interface_artifact_root(cli_ctx)
    manifest_output = manifest_output.resolve()
    rollback_location = (artifact_root / _INTERFACE_ROLLBACK_ROOT).resolve()
    if _path_is_within(manifest_output, rollback_location):
        raise ValueError("Interface manifest path must not alias the interface rollback location")
    if rollback_location.exists():
        for sidecar in rollback_location.rglob("*"):
            if sidecar.is_file() and _path_alias(manifest_output, sidecar):
                raise ValueError(f"Interface manifest path aliases rollback sidecar: {sidecar}")

    managed_paths = [root / entry.source_path for entry in plan.entries]
    managed_paths.append(root / "wiki" / "gadgets" / "gadgets.toml")
    for managed_path in managed_paths:
        if _path_alias(manifest_output, managed_path.resolve()):
            raise ValueError(f"Interface manifest path aliases managed source: {managed_path}")


def _new_interface_rollback_root(cli_ctx: CLIContext) -> Path:
    """Reserve a collision-free rollback directory for one deployment."""
    rollback_parent = _interface_artifact_root(cli_ctx) / _INTERFACE_ROLLBACK_ROOT
    rollback_parent.mkdir(parents=True, exist_ok=True)
    for _ in range(128):
        candidate = rollback_parent / f"deploy-{uuid.uuid4().hex}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    return Path(tempfile.mkdtemp(prefix="deploy-", dir=rollback_parent))


def _report_changed_cargo_declarations(manifest: RepoWikiPageManifest, changed_titles: set[str]) -> None:
    """Report changed Cargo-declaring templates so their tables can be recreated.
    Recreation is intentionally not automated: the Cargo API cannot switch in a
    replacement table, so an API-driven recreate would force a downtime window
    while the table repopulates. When a declaration's fields change, recreate
    the table via Special:CargoTables, which builds a replacement table and
    switches it in with no downtime.
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
    FactionRepository,
    ClassDisplayNameService,
]:
    """Create repositories for local Lua data generation from one read-only connection."""
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
        FactionRepository(db_connection),
        ClassDisplayNameService(db_connection),
    )


def _build_link_audit_catalog(cli_ctx: CLIContext) -> tuple[LinkCatalogEntry, ...]:
    """Build semantic-link identities from the canonical read-only repositories."""
    (
        item_repo,
        character_repo,
        _spawn_repo,
        _loot_repo,
        spell_repo,
        skill_repo,
        stance_repo,
        quest_repo,
        zone_repo,
        faction_repo,
        class_display,
    ) = _create_lua_repositories(cli_ctx)
    return build_link_catalog_entries(
        items=item_repo.get_items_for_link_catalog(),
        characters=character_repo.get_characters_for_wiki_generation(),
        quests=quest_repo.get_quests_for_wiki_generation(),
        zones=zone_repo.get_all_zones(),
        spells=spell_repo.get_spells_for_wiki_generation(),
        skills=skill_repo.get_skills_for_wiki_generation(),
        stances=stance_repo.get_all(),
        factions=faction_repo.get_factions_for_wiki_generation(),
        class_display=class_display,
    )


def _default_link_audit_output(cli_ctx: CLIContext) -> Path:
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_wiki(cli_ctx.repo_root) / "link-audit.json"


def _print_link_audit_summary(report: LinkAuditReport, output_path: Path | None) -> None:
    """Print deterministic per-code audit counts and report metadata."""
    console.print(
        Panel.fit(
            "[bold cyan]Semantic link audit[/bold cyan]\n"
            f"Variant: {report.variant}\n"
            f"Remote checked: {str(report.remote_checked).lower()}\n"
            f"Generated content SHA-256: {report.generated_content_sha256}",
            border_style="cyan",
        )
    )
    for code in sorted(FINDING_CODES, key=lambda value: (value not in ERROR_CODES, value)):
        severity = "error" if code in ERROR_CODES else "warning"
        color = "red" if severity == "error" else "yellow"
        console.print(f"[{color}]{severity.upper()}[/{color}] {code}: {report.summary.get(code, 0)}")
    if output_path is not None:
        console.print(f"[green]Wrote audit report:[/green] {output_path}", soft_wrap=True)


def _run_link_audit(
    cli_ctx: CLIContext,
    generated_pages: Mapping[str, str],
    *,
    online: bool,
    include_live_pages: bool,
    output_path: Path | None,
) -> LinkAuditReport:
    """Run one audit from canonical repositories and optional read-only live facts."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    storage = WikiStorage(variant_config.resolved_wiki(cli_ctx.repo_root))
    known_generated_titles = set(storage.list_generated_titles()) | set(generated_pages)
    client = _create_readonly_mediawiki_client(cli_ctx) if online else None
    try:
        audit_service = LinkAuditService(_build_link_audit_catalog(cli_ctx), client=client)
        report = audit_service.audit(
            generated_pages=generated_pages,
            planned_titles=tuple(generated_pages),
            variant=cli_ctx.variant,
            online=online,
            include_live_pages=include_live_pages,
            known_generated_titles=known_generated_titles,
        )
    finally:
        if client is not None:
            client.close()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.write_json(output_path)
    _print_link_audit_summary(report, output_path)
    return report


@require_preconditions(database_exists, database_valid, database_has_items)
def _assert_generated_deploy_preconditions(ctx: typer.Context) -> None:
    """Require clean database inputs only for generated-storage deployment."""


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
            "[bold cyan]Fetching wiki pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Dry-run: {cli_ctx.dry_run}\n"
            f"Pages: {'from ' + pages_file if pages_file else 'all'}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        with _create_wiki_composition(cli_ctx, with_client=True) as composition:
            assert composition.wiki_client is not None
            service = WikiFetchService(
                wiki_client=composition.wiki_client,
                context=composition.context,
            )

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
        (
            item_repo,
            character_repo,
            spawn_repo,
            loot_repo,
            spell_repo,
            skill_repo,
            stance_repo,
            quest_repo,
            zone_repo,
            faction_repo,
            class_display,
        ) = _create_lua_repositories(cli_ctx)
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
            faction_repo=faction_repo,
            class_display=class_display,
            output_root=output_root,
        )
        for path in result.written_paths:
            console.print(f"[green]Wrote:[/green] {path}", soft_wrap=True)
            console.print(f"[green]Validated with:[/green] {result.validation_tools[path]}")
    except Exception as e:
        console.print(f"[red]Error during wiki Lua generation: {e}[/red]")
        logger.exception("Wiki Lua generation failed")
        raise typer.Exit(1) from e


@app.command("audit-links")
@require_preconditions(database_exists, database_valid, database_has_items)
def audit_links_command(
    ctx: typer.Context,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Skip MediaWiki API reads and enforce only local catalog and planned-page invariants.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Audit report path (default: the variant wiki directory/link-audit.json).",
        ),
    ] = None,
) -> None:
    """Audit generated semantic links without editing MediaWiki."""
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    storage = WikiStorage(variant_config.resolved_wiki(cli_ctx.repo_root))
    output_path: Path | None = output or _default_link_audit_output(cli_ctx)
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: audit report will not be written.[/yellow]")
        output_path = None

    try:
        report = _run_link_audit(
            cli_ctx,
            storage.read_generated_pages(),
            online=not offline,
            include_live_pages=not offline,
            output_path=output_path,
        )
    except Exception as error:
        console.print(f"[red]Semantic link audit failed: {error}[/red]")
        logger.exception("Semantic link audit failed")
        raise typer.Exit(1) from error

    if report.has_errors:
        raise typer.Exit(1)


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
    requestor = (
        None
        if transport is not None
        else MediaWikiRequestor(
            api_url=wiki_config.api_url,
            policy=MediaWikiRequestPolicy(read_delay=wiki_config.api_delay),
        )
    )
    client = MediaWikiInventoryClient(transport=transport, requestor=requestor)

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
        if requestor is not None:
            requestor.close()


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
        with _create_wiki_composition(cli_ctx, with_client=False) as composition:
            service = WikiGenerateService(context=composition.context)

            # Generate pages (all or specified) and audit the exact processed
            # snapshot before generation reports success.
            def audit_generated_pages(generated_pages: Mapping[str, str]) -> None:
                report = _run_link_audit(
                    cli_ctx,
                    generated_pages,
                    online=False,
                    include_live_pages=False,
                    output_path=None if cli_ctx.dry_run else _default_link_audit_output(cli_ctx),
                )
                if report.has_errors:
                    error_count = sum(1 for finding in report.findings if finding.severity == "error")
                    raise ValueError(f"Semantic link audit found {error_count} blocking finding(s)")

            result = service.generate_all(
                dry_run=cli_ctx.dry_run,
                limit=limit,
                page_titles=page_titles,
                generator_names=generator,
                preflight=audit_generated_pages,
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
    wiki_config = cli_ctx.config.global_.mediawiki
    requestor = MediaWikiRequestor(
        api_url=wiki_config.api_url,
        policy=MediaWikiRequestPolicy(read_delay=rate_limit_delay),
    )
    client = MediaWikiInterfaceClient(requestor)
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
        requestor.close()

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


@app.command("deploy-interface")
def deploy_interface_command(
    ctx: typer.Context,
    manifest_path: Annotated[
        Path | None,
        typer.Option(
            "--manifest",
            help="Path for the deployment manifest (default: output/wiki-interface/deploy-manifest.json).",
        ),
    ] = None,
    summary: Annotated[
        str,
        typer.Option("--summary", help="Edit summary for interface page uploads."),
    ] = "Deploy repo-owned interface gadgets",
) -> None:
    """Deploy repo-owned gadget source pages and Gadgets-definition with an interface-admin account."""
    cli_ctx: CLIContext = ctx.obj
    manifest_output = _resolve_interface_manifest_path(
        cli_ctx,
        manifest_path if manifest_path is not None else Path("output/wiki-interface/deploy-manifest.json"),
    )
    interface_username = _interface_assert_user(cli_ctx)
    client: MediaWikiClient | None = None
    try:
        client = _create_interface_mediawiki_client(cli_ctx)
        plan = plan_interface_pages(
            cli_ctx.repo_root,
            client,
            assert_user=interface_username,
        )
        _validate_interface_manifest_output(cli_ctx, manifest_output, plan)
        if cli_ctx.dry_run:
            rights = client.get_current_user_rights(assertion="user", assert_user=interface_username)
            if "editinterface" not in rights:
                raise ValueError(
                    f"Interface account {interface_username!r} lacks the MediaWiki 'editinterface' right; "
                    "use a dedicated interface-admin account."
                )
            counts = Counter(action.planned_action for action in plan.entries)
            console.print(f"[yellow]Dry run: {len(plan.entries)} interface actions planned[/yellow]")
            for status, count in sorted(counts.items(), key=lambda item: str(item[0])):
                console.print(f"  {status}: {count}")
            return

        def checkpoint(checkpointed_manifest: InterfaceDeployManifest) -> None:
            write_interface_deploy_manifest(checkpointed_manifest, manifest_output)

        result = deploy_interface_pages(
            plan,
            repo_root=cli_ctx.repo_root,
            client=client,
            summary=summary,
            rollback_root=_new_interface_rollback_root(cli_ctx),
            checkpoint=checkpoint,
        )
        write_interface_deploy_manifest(result.manifest, manifest_output)
    except Exception as e:
        console.print(f"[red]Error during interface deployment: {e}[/red]")
        logger.exception("Interface deployment failed")
        raise typer.Exit(1) from e
    finally:
        if client is not None:
            client.close()

    completed_counts = Counter(
        action for entry in result.manifest.entries if (action := entry.deploy_action) is not None
    )
    console.print(
        "[green]Interface deploy complete[/green] "
        + " ".join(
            f"{status}: {count}" for status, count in sorted(completed_counts.items(), key=lambda item: str(item[0]))
        )
        + f" Manifest: {manifest_output}"
    )


@app.command("rollback-interface")
def rollback_interface_command(
    ctx: typer.Context,
    manifest_path: Annotated[
        Path | None,
        typer.Option(
            "--manifest",
            help="Deployment manifest to restore (default: output/wiki-interface/deploy-manifest.json).",
        ),
    ] = None,
    summary: Annotated[
        str,
        typer.Option("--summary", help="Edit summary for interface rollback edits."),
    ] = "Rollback repo-owned interface gadgets",
    force: Annotated[
        bool,
        typer.Option("--force", help="Restore even if a page changed since the interface deploy."),
    ] = False,
) -> None:
    """Restore repo-owned interface pages without deleting pages created by the deploy."""
    cli_ctx: CLIContext = ctx.obj
    manifest_file = _resolve_interface_manifest_path(
        cli_ctx,
        manifest_path if manifest_path is not None else Path("output/wiki-interface/deploy-manifest.json"),
    )
    if not manifest_file.exists():
        console.print(f"[red]Interface deployment manifest not found: {manifest_file}[/red]")
        raise typer.Exit(1)

    try:
        manifest = read_interface_deploy_manifest(manifest_file)
    except Exception as e:
        console.print(f"[red]Invalid interface deployment manifest: {e}[/red]")
        raise typer.Exit(1) from e

    interface_username = _interface_assert_user(cli_ctx)
    client: MediaWikiClient | None = None
    try:
        client = _create_interface_mediawiki_client(cli_ctx)
        if cli_ctx.dry_run:
            rights = client.get_current_user_rights(assertion="user", assert_user=interface_username)
            if "editinterface" not in rights:
                raise ValueError(
                    f"Interface account {interface_username!r} lacks the MediaWiki 'editinterface' right; "
                    "use a dedicated interface-admin account."
                )
            restorable = sum(
                entry.deploy_action == "edited" and entry.new_revision_id is not None for entry in manifest.entries
            )
            created = sum(
                entry.deploy_action == "created" and entry.new_revision_id is not None for entry in manifest.entries
            )
            console.print(
                f"[yellow]Dry run: would restore {restorable} interface pages; "
                f"created pages left in place: {created}[/yellow]"
            )
            return

        result = rollback_interface_pages(
            manifest,
            cli_ctx.repo_root,
            client,
            summary,
            force=force,
            assert_user=interface_username,
        )
    except Exception as e:
        console.print(f"[red]Error during interface rollback: {e}[/red]")
        logger.exception("Interface rollback failed")
        raise typer.Exit(1) from e
    finally:
        if client is not None:
            client.close()

    console.print(
        f"[green]Interface rollback complete[/green] Restored: {len(result.restored_titles)} "
        f"Created left in place: {len(result.created_titles)}"
    )
    if result.restored_titles:
        console.print("[green]Restored interface pages:[/green]")
        for title in result.restored_titles:
            console.print(f"  {title}", markup=False)
    if result.created_titles:
        console.print("[yellow]Created interface pages were left in place (no automatic deletion):[/yellow]")
        for title in result.created_titles:
            console.print(f"  {title}", markup=False)


_DIRECT_DATA_LINK_CONSUMER_TITLES = frozenset(
    {
        "Module:Erenshor/Link",
        "Module:Erenshor/AbilityLink",
        "Module:Erenshor/Link/Search",
        "Module:Erenshor/Item",
    }
)
_DATA_LINKS_TITLE = "Module:Erenshor/Data/Links"


def _manifest_requires_live_links(manifest: RepoWikiPageManifest) -> bool:
    """Return whether a direct consumer lacks an earlier Links catalog page."""
    earlier_titles: set[str] = set()
    for entry in manifest.entries:
        if entry.title in _DIRECT_DATA_LINK_CONSUMER_TITLES and _DATA_LINKS_TITLE not in earlier_titles:
            return True
        earlier_titles.add(entry.title)
    return False


def _candidate_repo_page_manifest(
    manifest: RepoWikiPageManifest,
    *,
    requested_titles: set[str] | None,
    include_templates: bool,
    include_generated_data: bool,
    include_content_pages: bool,
) -> RepoWikiPageManifest:
    """Apply CLI scope filters before the live catalog dependency check."""
    entries = tuple(
        entry
        for entry in manifest.entries
        if (include_templates or entry.upload_stage not in {"template", "cargo_declaration"})
        and (include_generated_data or entry.upload_stage != "generated_data")
        and (include_content_pages or entry.upload_stage != "content_page")
        and (requested_titles is None or entry.title in requested_titles)
    )
    return RepoWikiPageManifest(entries=entries)


@app.command("deploy-repo-pages")
def deploy_repo_pages_command(
    ctx: typer.Context,
    pages_file: Annotated[
        str | None,
        typer.Option(
            "--pages-file",
            help=(
                "Deploy only repo-owned page titles listed in this file, or '-' for stdin. "
                "Required with --include-generated-data."
            ),
        ),
    ] = None,
    summary: Annotated[
        str,
        typer.Option("--summary", help="Edit summary for repo-owned page uploads."),
    ] = "Deploy repo-owned wiki pages",
    assertion: Annotated[
        Literal["user", "bot"],
        typer.Option("--assertion", help="MediaWiki assertion guard (user or bot)."),
    ] = "bot",
    assert_user: Annotated[
        str | None,
        typer.Option("--assert-user", help="Expected MediaWiki username for assertuser guard."),
    ] = None,
    manifest_output: Annotated[
        Path | None,
        typer.Option("--manifest-output", help="Path for the deployment manifest JSON."),
    ] = None,
    include_templates: Annotated[
        bool,
        typer.Option(
            "--include-templates",
            help="Explicitly include wiki templates. Disabled by default because template edits affect all pages.",
        ),
    ] = False,
    include_generated_data: Annotated[
        bool,
        typer.Option(
            "--include-generated-data",
            help=(
                "Explicitly include generated Lua data modules selected by --pages-file. "
                "A page-title filter is required to avoid deploying the full generated tree."
            ),
        ),
    ] = False,
    include_content_pages: Annotated[
        bool,
        typer.Option(
            "--include-content-pages",
            help="Explicitly include maintained wiki content pages. Disabled by default.",
        ),
    ] = False,
) -> None:
    """Deploy repo-owned wiki pages; generated data, content pages, and templates require opt-in."""
    cli_ctx: CLIContext = ctx.obj
    if include_generated_data and not pages_file:
        console.print("[red]--include-generated-data requires --pages-file with explicit page titles[/red]")
        raise typer.Exit(1)
    requested_titles = set(_read_page_titles(pages_file)) if pages_file else None
    known_live_titles: set[str] = set()
    try:
        manifest = build_repo_page_manifest(
            cli_ctx.repo_root,
            variant=cli_ctx.variant,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
            requested_titles=requested_titles,
        )
        candidate_manifest = _candidate_repo_page_manifest(
            manifest,
            requested_titles=requested_titles,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
        )
        if _manifest_requires_live_links(candidate_manifest):
            readonly_client = _create_readonly_mediawiki_client(cli_ctx)
            try:
                if readonly_client.page_exists(_DATA_LINKS_TITLE):
                    known_live_titles.add(_DATA_LINKS_TITLE)
            finally:
                readonly_client.close()
        manifest = select_repo_page_manifest(
            manifest,
            requested_titles=requested_titles,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
            known_live_titles=known_live_titles,
        )
    except Exception as e:
        console.print(f"[red]Unable to select repo-owned wiki pages: {e}[/red]")
        raise typer.Exit(1) from e

    if manifest_output is None:
        manifest_output = (
            cli_ctx.config.variants[cli_ctx.variant].resolved_wiki(cli_ctx.repo_root) / "deploy-manifest.json"
        )

    if not manifest.entries:
        console.print("[yellow]No repo-owned wiki pages selected; no remote edits made[/yellow]")
        return

    if cli_ctx.dry_run:
        scope = f" filtered by {pages_file}" if pages_file else ""
        console.print(f"[yellow]Dry run: {len(manifest.entries)} repo-owned pages in manifest{scope}[/yellow]")
        return

    def checkpoint_manifest(checkpointed_manifest: RepoWikiPageManifest) -> None:
        write_repo_page_manifest(checkpointed_manifest, manifest_output)

    client = _create_mediawiki_client(cli_ctx)
    try:
        result = deploy_repo_pages(
            manifest=manifest,
            repo_root=cli_ctx.repo_root,
            client=client,
            summary=summary,
            assertion=assertion,
            assert_user=assert_user,
            rollback_root=manifest_output.parent / "rollback",
            checkpoint=checkpoint_manifest,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
            known_live_titles=known_live_titles,
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
    page_titles: Annotated[
        list[str] | None,
        typer.Option(
            "--page",
            help="Refresh only this exact wiki page; repeat for multiple pages.",
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
    page_titles = page_titles or []
    namespaces = namespaces or []
    if not dependency_titles and not source_tables and not page_titles:
        console.print("[red]At least one dependency title, source table, or page is required.[/red]")
        raise typer.Exit(1)
    if dependency_titles and not namespaces:
        console.print("[red]At least one --namespace is required with dependency titles.[/red]")
        raise typer.Exit(1)

    if cli_ctx.dry_run:
        console.print(
            f"[yellow]Dry run: would refresh pages for {len(dependency_titles)} dependencies, "
            f"{len(source_tables)} source tables, and {len(set(page_titles))} explicit pages "
            f"in namespaces {', '.join(str(namespace) for namespace in namespaces)}[/yellow]"
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
        if page_titles:
            unique_page_titles = tuple(dict.fromkeys(page_titles))
            refreshed_titles.update(
                client.purge_pages(
                    unique_page_titles,
                    force_link_update=True,
                    assertion="bot",
                    assert_user=assert_user,
                )
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
        if from_dir:
            with _create_wiki_composition(cli_ctx, with_client=True) as composition:
                assert composition.wiki_client is not None
                service = WikiDeployService(
                    wiki_client=composition.wiki_client,
                    storage=composition.storage,
                )
                console.print(
                    "[yellow]Directory uploads are outside the generated-content gate. "
                    "Run 'erenshor wiki audit-links' explicitly for generated storage.[/yellow]"
                )
                result = service.deploy_from_dir(
                    source_dir=Path(from_dir),
                    dry_run=cli_ctx.dry_run,
                )
        else:
            _assert_generated_deploy_preconditions(ctx)
            with _create_wiki_composition(cli_ctx, with_client=True) as composition:
                assert composition.wiki_client is not None
                service = WikiDeployService(
                    wiki_client=composition.wiki_client,
                    storage=composition.storage,
                )
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

                def audit_deployment_pages(generated_pages: Mapping[str, str]) -> None:
                    report = _run_link_audit(
                        cli_ctx,
                        generated_pages,
                        online=True,
                        include_live_pages=False,
                        output_path=None if cli_ctx.dry_run else _default_link_audit_output(cli_ctx),
                    )
                    stale_catalog = any(finding.code == "live_link_catalog_stale" for finding in report.findings)
                    if stale_catalog:
                        raise ValueError(
                            "Generated article deployment requires the live semantic-link catalog to match "
                            "the generated catalog. Deploy repo-owned Lua/data pages first."
                        )
                    if report.has_errors:
                        error_count = sum(1 for finding in report.findings if finding.severity == "error")
                        raise ValueError(f"Semantic link audit found {error_count} blocking finding(s)")

                result = service.deploy_all(
                    dry_run=cli_ctx.dry_run,
                    limit=limit,
                    page_titles=page_titles,
                    preflight=audit_deployment_pages,
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
