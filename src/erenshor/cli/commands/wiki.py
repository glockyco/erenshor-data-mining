"""Wiki commands for MediaWiki page management.

Generated articles follow a three-stage workflow:

1. fetch: Download the live pages and their revisions.
2. generate: Create pages from the clean database and merge each one into
   its fetched page.
3. deploy: Write each changed page while its live revision is still the
   fetched revision.

Example workflow:
    $ erenshor wiki fetch
    $ erenshor wiki generate
    $ erenshor --dry-run wiki deploy
    $ erenshor wiki deploy
"""

import json
import sqlite3
import sys
import tempfile
import uuid
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer
from loguru import logger
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from erenshor.application.extract.database_comparison import recorded_build_id
from erenshor.application.wiki.chat_knowledge import load_chat_knowledge
from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.lifecycle import ContentLifecycle, load_content_lifecycle, with_chat_knowledge
from erenshor.application.wiki.semantic_validation import validate_wiki_pages
from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki.services.fetch_service import WikiFetchService
from erenshor.application.wiki.services.generate_service import GeneratedCorpus, WikiGenerateService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.article_report import CHANGE_KINDS, ArticleDeployReport, build_article_report
from erenshor.application.wiki_deploy.articles import (
    ArticleDeployPlan,
    ArticleDeployResult,
    deploy_articles,
    plan_article_deploy,
)
from erenshor.application.wiki_deploy.link_audit import (
    ERROR_CODES,
    FINDING_CODES,
    LinkAuditReport,
    LinkTargets,
)
from erenshor.application.wiki_deploy.link_audit_service import LinkAuditService
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    build_repo_page_manifest,
    read_repo_page_manifest,
    select_repo_page_manifest,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.pages import (
    RepoPageDrift,
    RepoPageDriftError,
    build_deployed_manifest,
    deploy_repo_pages,
    find_drift,
    prepare_repo_page_checks,
    read_repo_page_sources,
    render_repo_page_checks,
    repo_page_action,
)
from erenshor.application.wiki_deploy.refresh import refresh_embedded_pages
from erenshor.application.wiki_deploy.render_check import RenderCheck
from erenshor.application.wiki_deploy.retired_apply import apply_retired_edits, plan_retired_edits
from erenshor.application.wiki_deploy.retired_pages import RetiredPageReport, audit_retired_pages
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
from erenshor.application.wiki_lua.generation import (
    generate_lua_data_modules,
    item_shard_dir,
    planned_top_level_module_paths,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.cli.context import CLIContext
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.cli.preconditions.checks.inputs import option_path, wiki_credentials
from erenshor.cli.preconditions.checks.wiki import interface_admin_credentials, wiki_endpoint
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.build_metadata import BuildMetadataRepository
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
from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestor

app = typer.Typer(
    name="wiki",
    help="Manage MediaWiki pages and content",
    no_args_is_help=True,
)

console = Console()

# Semantic findings printed when generation fails. The rest are counted.
_SHOWN_FINDINGS = 20
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
        batch_size=50,
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
        batch_size=50,
        user_agent="erenshor-data-mining/1.0 (WoWMuch)",
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
    """Resolve an interface manifest within the dedicated artifact root.

    A path outside that root is a usage error of the ``--manifest`` option.
    """
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
        raise typer.BadParameter(
            f"must be a file below {_INTERFACE_ARTIFACT_ROOT}", param_hint="'--manifest'"
        ) from error
    if resolved == artifact_root:
        raise typer.BadParameter(f"must name a file below {_INTERFACE_ARTIFACT_ROOT}", param_hint="'--manifest'")
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
    SpellRepository,
    SkillRepository,
    StanceRepository,
    QuestRepository,
    ZoneRepository,
    FactionRepository,
    ClassDisplayNameService,
    BuildMetadataRepository,
]:
    """Create repositories for local Lua data generation from one read-only connection."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    db_connection = DatabaseConnection(db_path, read_only=True)
    return (
        ItemRepository(db_connection),
        CharacterRepository(db_connection),
        SpellRepository(db_connection),
        SkillRepository(db_connection),
        StanceRepository(db_connection),
        QuestRepository(db_connection),
        ZoneRepository(db_connection),
        FactionRepository(db_connection),
        ClassDisplayNameService(db_connection),
        BuildMetadataRepository(db_connection),
    )


def _build_link_audit_catalog(cli_ctx: CLIContext) -> tuple[LinkCatalogEntry, ...]:
    """Build semantic-link identities from the canonical read-only repositories."""
    with _create_wiki_composition(cli_ctx, with_client=False) as composition:
        return composition.context.link_catalog_entries()


def _default_link_audit_output(cli_ctx: CLIContext) -> Path:
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_wiki(cli_ctx.repo_root) / "link-audit.json"


def _publish_link_audit(report: LinkAuditReport, output_path: Path | None) -> None:
    """Write the audit report when a path is given and print its per-code counts."""
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.write_json(output_path)
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
    known_generated_titles: Collection[str] | None = None,
    catalog: Sequence[LinkCatalogEntry] | None = None,
) -> LinkAuditReport:
    """Run one audit from canonical repositories and optional read-only live facts.

    ``catalog`` is the link catalog that generation used. Without it the audit
    builds the catalog from the database.
    """
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    storage = WikiStorage(variant_config.resolved_wiki(cli_ctx.repo_root))
    if known_generated_titles is None:
        known_generated_titles = storage.list_generated_titles()
    complete_generated_titles = set(known_generated_titles) | set(generated_pages)
    if catalog is None:
        catalog = _build_link_audit_catalog(cli_ctx)
    client = _create_readonly_mediawiki_client(cli_ctx) if online else None
    try:
        audit_service = LinkAuditService(catalog, client=client)
        report = audit_service.audit(
            generated_pages=generated_pages,
            planned_titles=tuple(generated_pages),
            variant=cli_ctx.variant,
            online=online,
            include_live_pages=include_live_pages,
            known_generated_titles=complete_generated_titles,
        )
    finally:
        if client is not None:
            client.close()

    _publish_link_audit(report, output_path)
    return report


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
        help="Re-download every page, even when its saved revision is current",
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

    By default, compares each page's current wiki revision with the revision
    saved at the last fetch, and downloads only pages that changed. Pages that
    were deleted on the wiki are removed from local storage. Use --force to
    re-download all pages.

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
            spell_repo,
            skill_repo,
            stance_repo,
            quest_repo,
            zone_repo,
            faction_repo,
            class_display,
            build_repo,
        ) = _create_lua_repositories(cli_ctx)
        result = generate_lua_data_modules(
            item_repo=item_repo,
            character_repo=character_repo,
            spell_repo=spell_repo,
            skill_repo=skill_repo,
            stance_repo=stance_repo,
            quest_repo=quest_repo,
            zone_repo=zone_repo,
            faction_repo=faction_repo,
            class_display=class_display,
            build_repo=build_repo,
            output_root=output_root,
            max_page_bytes=cli_ctx.config.global_.mediawiki.max_page_bytes,
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


def _load_retired_lifecycle(cli_ctx: CLIContext) -> ContentLifecycle:
    """Read the lifecycle facts, with the chat flag that the clean knowledge base gives."""
    lifecycle = load_content_lifecycle(cli_ctx.repo_root / "content-lifecycle.json")
    database = cli_ctx.config.variants[cli_ctx.variant].resolved_database(cli_ctx.repo_root)
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as clean:
        return with_chat_knowledge(lifecycle, load_chat_knowledge(clean))


def _run_retired_audit(
    cli_ctx: CLIContext, storage: WikiStorage, *, lifecycle: ContentLifecycle | None = None
) -> RetiredPageReport:
    """Read current articles and lifecycle facts for a complete live review."""
    if lifecycle is None:
        lifecycle = _load_retired_lifecycle(cli_ctx)
    generated = storage.read_generated_pages()
    client = _create_readonly_mediawiki_client(cli_ctx)
    try:
        report = audit_retired_pages(client, generated, lifecycle)
    finally:
        client.close()
    console.print("[bold]Retired WoWBot pages[/bold]")
    for page in report.pages:
        console.print(
            f"  {escape(page.title)} | key: {escape(page.stable_key or 'unknown')} | "
            f"current: {escape(page.current_title or 'none')} | "
            f"expected: {escape(page.expected)} | {escape(page.state)}"
            + (f" | {escape(page.reason)}" if page.reason else "")
        )
    if report.reviewed_non_bot:
        console.print("[bold]Reviewed pages not created by WoWBot[/bold]")
        for page in report.reviewed_non_bot:
            console.print(
                f"  {escape(page.title)} | key: {escape(page.stable_key or 'unknown')} | "
                f"current: {escape(page.current_title or 'none')} | "
                f"expected: {escape(page.expected)} | {escape(page.state)}"
                + (f" | {escape(page.reason)}" if page.reason else "")
            )
    console.print(
        f"Created titles checked: {report.checked} | Retired: {len(report.pages)} | "
        f"Pending: {report.pending} | Unexplained: {report.unexplained}"
    )
    return report


@app.command("audit-retired-pages")
@require_preconditions(wiki_endpoint, database_exists, database_valid)
def audit_retired_pages_command(ctx: typer.Context) -> None:
    """Review live pages created by WoWBot that generation no longer writes."""
    cli_ctx: CLIContext = ctx.obj
    variant = cli_ctx.config.variants[cli_ctx.variant]
    try:
        report = _run_retired_audit(cli_ctx, WikiStorage(variant.resolved_wiki(cli_ctx.repo_root)))
    except Exception as error:
        console.print(f"[red]Retired page review is incomplete: {escape(str(error))}[/red]")
        raise typer.Exit(1) from error
    if report.has_errors:
        raise typer.Exit(1)


@app.command("apply-retired-pages")
@require_preconditions(wiki_endpoint, wiki_credentials, database_exists, database_valid)
def apply_retired_pages_command(ctx: typer.Context) -> None:
    """Apply reviewed historical notices, redirects, and split pages with revision guards."""
    cli_ctx: CLIContext = ctx.obj
    wiki_dir = cli_ctx.config.variants[cli_ctx.variant].resolved_wiki(cli_ctx.repo_root)
    try:
        lifecycle = _load_retired_lifecycle(cli_ctx)
        report = _run_retired_audit(cli_ctx, WikiStorage(wiki_dir), lifecycle=lifecycle)
        edits = plan_retired_edits(report, lifecycle)
    except Exception as error:
        console.print(f"[red]Retired page review is incomplete: {escape(str(error))}[/red]")
        raise typer.Exit(1) from error

    actions = Counter(edit.action for edit in edits)
    console.print(
        f"Pending changes: notices {actions['notice']} | redirects {actions['redirect']} | "
        f"disambiguation pages {actions['disambiguation']}"
    )
    if cli_ctx.dry_run:
        for edit in edits:
            console.print(f"{edit.title} ({edit.action})", markup=False)
            console.print(edit.content, markup=False, soft_wrap=True)
        return
    if not edits:
        return

    run_dir = (
        wiki_dir / "retired-page-deploys" / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    )
    client = _create_mediawiki_client(cli_ctx)
    try:
        result = apply_retired_edits(edits, repo_root=cli_ctx.repo_root, run_dir=run_dir, client=client)
    finally:
        client.close()
    console.print(f"Manifest: {result.manifest_path}", markup=False)
    for title in result.edited:
        console.print(f"[green]Edited[/green] {escape(title)}")
    for conflict in result.conflicts:
        console.print(f"[yellow]Changed after review[/yellow] {escape(conflict)}")
    if result.stopped:
        console.print(f"[red]Stopped[/red] {escape(result.stopped)}")
    if result.failed:
        raise typer.Exit(1)


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

    Generates the entity, overview, and zone articles from the clean database
    and merges each article into its fetched live page. Generated roots take
    the database values, except where a preservation rule keeps the value of
    an editor. Overview pages take the new generated table. Text outside the
    generated roots and tables stays.

    You can specify which pages to generate using --pages-file:
    - Generate from file: --pages-file pages.txt
    - Generate from stdin: --pages-file - < pages.txt
    - Generate all pages: (no --pages-file option)

    Generated pages are saved to variants/{variant}/wiki/generated/

    You can compare generated files with the fetched pages before deploying them:
        $ git diff --no-index variants/{variant}/wiki/fetched/ variants/{variant}/wiki/generated/
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
            link_catalog = composition.context.link_catalog_entries()
            lifecycle = load_content_lifecycle(cli_ctx.repo_root / "content-lifecycle.json")
            service = WikiGenerateService(context=composition.context, link_catalog=link_catalog, lifecycle=lifecycle)

            # Validate the exact pages of the run before generation reports
            # success. Validation includes the offline semantic-link audit.
            def validate_generated_corpus(corpus: GeneratedCorpus) -> None:
                pages = tuple(corpus.pages)
                report = validate_wiki_pages(
                    corpus.pages,
                    expectations=corpus.expectations,
                    catalog_entries=link_catalog,
                    planned_titles=pages,
                    known_generated_titles=pages,
                    variant=cli_ctx.variant,
                )
                _publish_link_audit(report.link_audit, None if cli_ctx.dry_run else _default_link_audit_output(cli_ctx))
                if report.has_errors:
                    for finding in report.findings[:_SHOWN_FINDINGS]:
                        console.print(f"[red]✗[/red] {escape(f'[{finding.code}] {finding.page}: {finding.detail}')}")
                    hidden = len(report.findings) - _SHOWN_FINDINGS
                    if hidden > 0:
                        console.print(f"[red]… and {hidden} more[/red]")
                    raise ValueError(f"Semantic validation found {len(report.findings)} blocking finding(s)")

            result = service.generate_all(
                dry_run=cli_ctx.dry_run,
                limit=limit,
                page_titles=page_titles,
                generator_names=generator,
                validate=validate_generated_corpus,
            )

        # Show warnings and errors. Warnings name the live roots that generation
        # kept because no generated entity matches them; a human reviews them.
        if result.has_warnings():
            logger.warning(f"Generation completed with {len(result.warnings)} warnings")
            for warning in result.warnings:
                console.print(f"[yellow]![/yellow] {escape(warning)}")

        if result.failed > 0:
            logger.error(f"Generation completed with {result.failed} failures")
            raise typer.Exit(1)

        # Show next steps
        if not cli_ctx.dry_run and result.succeeded > 0:
            variant_config = cli_ctx.config.variants[cli_ctx.variant]
            wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
            console.print("[bold]Next steps:[/bold]")
            console.print(f"  Review generated files: {wiki_dir / 'generated'}")
            console.print("  Review the deploy plan: [cyan]erenshor --dry-run wiki deploy[/cyan]")
            console.print()

    except Exception as e:
        console.print(f"[red]Error during wiki generation: {e}[/red]")
        logger.exception("Wiki generation failed")
        raise typer.Exit(1) from e


@app.command("sync-interface")
@require_preconditions(wiki_endpoint)
def sync_interface(ctx: typer.Context) -> None:
    """Sync live MediaWiki interface pages for local preview.

    Writes the gitignored local mirror to wiki-dev/interface and CSS assets to wiki-dev/images.
    """
    cli_ctx: CLIContext = ctx.obj
    output_root = Path("wiki-dev/interface")
    image_root = Path("wiki-dev/images")
    wiki_config = cli_ctx.config.global_.mediawiki
    requestor = MediaWikiRequestor(
        api_url=wiki_config.api_url,
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
@require_preconditions(wiki_endpoint, interface_admin_credentials)
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
@require_preconditions(
    wiki_endpoint,
    interface_admin_credentials,
    option_path("manifest_path", default="output/wiki-interface/deploy-manifest.json"),
)
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


@app.command("deploy-repo-pages")
@require_preconditions(wiki_endpoint, wiki_credentials, option_path("pages_file"))
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
        typer.Option(
            "--manifest-output",
            help=(
                "Path for the deployment manifest JSON. The rollback sources go to a rollback directory beside it. "
                "Default: a new repo-page-deploys/<UTC time>-<id>/manifest.json in the variant's wiki directory."
            ),
        ),
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
    full_render_check: Annotated[
        bool,
        typer.Option("--full-render-check", help="Parse every main-namespace page that uses each changed page."),
    ] = False,
    accept_drift: Annotated[
        list[str] | None,
        typer.Option(
            "--accept-drift",
            help=(
                "Overwrite this page although another account made its latest revision. "
                "Review its live text first. May be repeated."
            ),
        ),
    ] = None,
) -> None:
    """Deploy repo-owned wiki pages; generated data, content pages, and templates require opt-in.

    The deploy stops before its first write when another account made the latest
    revision of a page whose live text differs from the repository. Copy that live
    text into the repository, or name the page with --accept-drift. A dry run reads
    the live pages, counts the planned changes, and names each such page.
    """
    cli_ctx: CLIContext = ctx.obj
    if include_generated_data and not pages_file:
        console.print("[red]--include-generated-data requires --pages-file with explicit page titles[/red]")
        raise typer.Exit(1)
    requested_titles = set(_read_page_titles(pages_file)) if pages_file else None
    try:
        manifest = build_repo_page_manifest(
            cli_ctx.repo_root,
            variant=cli_ctx.variant,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
            requested_titles=requested_titles,
        )
        manifest = select_repo_page_manifest(
            manifest,
            requested_titles=requested_titles,
            include_templates=include_templates,
            include_generated_data=include_generated_data,
            include_content_pages=include_content_pages,
        )
    except Exception as e:
        console.print(f"[red]Unable to select repo-owned wiki pages: {e}[/red]")
        raise typer.Exit(1) from e

    if manifest_output is None:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        wiki_dir = cli_ctx.config.variants[cli_ctx.variant].resolved_wiki(cli_ctx.repo_root)
        manifest_output = wiki_dir / "repo-page-deploys" / run_id / "manifest.json"
    manifest_output = manifest_output.resolve()

    if not manifest.entries:
        console.print("[yellow]No repo-owned wiki pages selected; no remote edits made[/yellow]")
        return

    accepted = tuple(accept_drift or ())
    if cli_ctx.dry_run:
        readonly_client = _create_readonly_mediawiki_client(cli_ctx)
        try:
            snapshots = readonly_client.get_page_snapshots([entry.title for entry in manifest.entries])
            source_texts = read_repo_page_sources(manifest, cli_ctx.repo_root)
            drift = find_drift(
                manifest.entries,
                source_texts,
                snapshots,
                deploy_account=readonly_client.edit_account,
                accepted=accepted,
            )
            live_modules: dict[str, str | None] = {}
            manifest = prepare_repo_page_checks(manifest, source_texts, snapshots, readonly_client, live_modules)
            catalog = (
                {entry.key.casefold(): entry for entry in _build_link_audit_catalog(cli_ctx)}
                if any(
                    repo_page_action(snapshots[entry.title], source_texts[entry.title]) != "unchanged"
                    for entry in manifest.entries
                )
                else {}
            )
            render_repo_page_checks(
                manifest,
                source_texts,
                snapshots,
                readonly_client,
                catalog=catalog,
                full=full_render_check,
                dry_run=True,
                live_modules=live_modules,
                report=_print_repo_render_check,
            )
        except Exception as e:
            console.print(f"[red]Repo-owned page dry run failed: {escape(str(e))}[/red]")
            raise typer.Exit(1) from e
        finally:
            readonly_client.close()
        planned = {
            entry.title: repo_page_action(snapshots[entry.title], source_texts[entry.title])
            for entry in manifest.entries
        }
        actions = Counter(planned.values())
        scope = f" filtered by {pages_file}" if pages_file else ""
        console.print(
            f"[yellow]Dry run: {len(manifest.entries)} repo-owned pages in manifest{scope}[/yellow] "
            f"Create: {actions['created']} Edit: {actions['edited']} Unchanged: {actions['unchanged']}"
        )
        for title, action in sorted(planned.items()):
            if action != "unchanged":
                console.print(f"  {'Create' if action == 'created' else 'Edit'} {escape(title)}", soft_wrap=True)
        _print_repo_page_drift(drift)
        if drift:
            raise typer.Exit(1)
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
            accept_drift=accepted,
            catalog={entry.key.casefold(): entry for entry in _build_link_audit_catalog(cli_ctx)},
            full_render_check=full_render_check,
            report_render=_print_repo_render_check,
        )
    except RepoPageDriftError as e:
        _print_repo_page_drift(e.drift)
        raise typer.Exit(1) from e
    except ValueError as e:
        console.print(f"[red]Repo-owned page deploy failed: {escape(str(e))}[/red]")
        raise typer.Exit(1) from e
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


def _print_repo_render_check(result: RenderCheck) -> None:
    """Show render coverage and visible differences for one changed page."""
    status = " (provisional)" if result.provisional else ""
    if not result.users:
        console.print(f"  Render {escape(result.title)}: no main-namespace users{status}")
        return
    console.print(f"  Render {escape(result.title)}: checked {len(result.checked)} of {result.users} users{status}")
    for difference in result.differences:
        console.print(f"    Visible change on {escape(difference.title)}")
        for line in difference.removed:
            console.print(f"      - {escape(line)}")
        for line in difference.added:
            console.print(f"      + {escape(line)}")


def _print_repo_page_drift(drift: Sequence[RepoPageDrift]) -> None:
    """Name each page that another account changed, and how to resolve it."""
    for item in drift:
        console.print(
            f"[red]Drift[/red] {escape(item.title)}: revision {item.revision_id} by "
            f"{escape(item.user or 'a hidden user')} differs from the repository"
        )
    if drift:
        console.print("Copy the live text of each page into the repository, or review it and pass --accept-drift.")


@app.command("refresh-embedded")
@require_preconditions(wiki_endpoint, wiki_credentials)
def refresh_embedded_command(
    ctx: typer.Context,
    dependency_titles: Annotated[
        list[str] | None,
        typer.Option(
            "--dependency-title",
            help="Template or module title whose transcluding pages should be refreshed.",
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
    page_titles = page_titles or []
    namespaces = namespaces or []
    if not dependency_titles and not page_titles:
        console.print("[red]At least one dependency title or page is required.[/red]")
        raise typer.Exit(1)
    if dependency_titles and not namespaces:
        console.print("[red]At least one --namespace is required with dependency titles.[/red]")
        raise typer.Exit(1)

    if cli_ctx.dry_run:
        console.print(
            f"[yellow]Dry run: would refresh pages for {len(dependency_titles)} dependencies "
            f"and {len(set(page_titles))} explicit pages "
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
    finally:
        client.close()

    console.print(f"[green]Embedded dependency refresh complete[/green] Refreshed: {len(refreshed_titles)}")


@app.command("rollback-repo-pages")
@require_preconditions(wiki_endpoint, wiki_credentials, option_path("manifest_path"))
def rollback_repo_pages_command(
    ctx: typer.Context,
    manifest_path: Annotated[
        Path,
        typer.Option("--manifest", help="Deployment manifest JSON produced by deploy-repo-pages or deploy."),
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
    """Restore the page text recorded in a deploy-repo-pages or deploy manifest."""
    cli_ctx: CLIContext = ctx.obj

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
@require_preconditions(
    wiki_endpoint,
    wiki_credentials,
    option_path("pages_file"),
    database_exists,
    database_valid,
    database_has_items,
)
def deploy(
    ctx: typer.Context,
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Write at most this many articles.",
    ),
    pages_file: str | None = typer.Option(
        None,
        "--pages-file",
        help="File with page titles to deploy (one per line), or '-' for stdin. If not specified, deploys all pages.",
    ),
) -> None:
    """Deploy generated articles that changed since their fetched revision.

    Each article is written only while its live page is still at the revision
    that generation merged into. A page that changed or was deleted after the
    fetch is a conflict and is not written. Before the first write, a manifest
    lists every planned page with its base revision. Each written page gets its
    new revision there, and `wiki rollback-repo-pages` restores the written pages.

    A dry run writes nothing to the wiki. It groups the planned writes by kind
    of change, lists the encounter tier changes, the live roots that generation
    kept, and the conflicts, and saves the full report as deploy-plan.json in
    the wiki directory of the variant.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    storage = WikiStorage(wiki_dir)
    try:
        page_titles = _read_page_titles(pages_file) if pages_file else None
        plan = plan_article_deploy(storage, page_titles=page_titles, limit=limit)
    except Exception as e:
        console.print(f"[red]Unable to plan the article deploy: {escape(str(e))}[/red]")
        raise typer.Exit(1) from e

    _print_article_plan(plan)
    writes = {article.title: article.generated_text for article in plan.writes}
    review_failed = False
    if cli_ctx.dry_run:
        if page_titles is not None or limit is not None:
            console.print(
                "[yellow]Filtered dry run: retired pages were not reviewed. This is not a complete review.[/yellow]"
            )
        else:
            try:
                retirement = _run_retired_audit(cli_ctx, storage)
            except Exception as error:
                console.print(f"[red]Retired page review is incomplete: {escape(str(error))}[/red]")
                raise typer.Exit(1) from error
            review_failed = review_failed or retirement.has_errors
    catalog = _build_link_audit_catalog(cli_ctx) if writes else ()
    if cli_ctx.dry_run and writes:
        readonly_client = _create_readonly_mediawiki_client(cli_ctx)
        try:
            live_revisions = readonly_client.get_page_revision_ids(list(writes))
        finally:
            readonly_client.close()
        review = build_article_report(plan, storage, live_revisions, LinkTargets(catalog))
        review_path = wiki_dir / "deploy-plan.json"
        review_path.write_text(json.dumps(review.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _print_article_report(review, review_path)
        review_failed = review_failed or bool(review.conflicts)

    if writes:
        report = _run_link_audit(
            cli_ctx,
            writes,
            online=True,
            include_live_pages=False,
            output_path=None if cli_ctx.dry_run else _default_link_audit_output(cli_ctx),
            catalog=catalog,
        )
        if any(finding.code == "live_link_catalog_stale" for finding in report.findings):
            console.print(
                "[red]The live semantic-link catalog differs from the generated catalog. "
                "Deploy the repository Lua data pages first.[/red]"
            )
            raise typer.Exit(1)
        if report.has_errors:
            error_count = sum(1 for finding in report.findings if finding.severity == "error")
            console.print(f"[red]Semantic link audit found {error_count} blocking finding(s).[/red]")
            raise typer.Exit(1)

    if cli_ctx.dry_run or not writes:
        if plan.stale or review_failed:
            raise typer.Exit(1)
        return

    try:
        build_id = recorded_build_id(variant_config.resolved_database(cli_ctx.repo_root))
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(1) from e
    run_dir = wiki_dir / "article-deploys" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = run_dir / "manifest.json"

    def checkpoint_manifest(manifest: RepoWikiPageManifest) -> None:
        write_repo_page_manifest(manifest, manifest_path)

    client = _create_mediawiki_client(cli_ctx)
    try:
        result = deploy_articles(
            plan,
            client=client,
            storage=storage,
            repo_root=cli_ctx.repo_root,
            rollback_root=run_dir / "rollback",
            summary=f"Update game data from build {build_id}",
            checkpoint=checkpoint_manifest,
        )
    finally:
        client.close()
    write_repo_page_manifest(result.manifest, manifest_path)

    _print_article_deploy_result(result, manifest_path)
    if result.failed or plan.stale:
        raise typer.Exit(1)


def _print_article_plan(plan: ArticleDeployPlan) -> None:
    """Print what the article deploy writes and the pages it cannot guard."""
    console.print(
        f"[bold]Article deploy plan[/bold] Edit: {plan.count('edit')} Create: {plan.count('create')} "
        f"Unchanged: {plan.count('unchanged')} Stale: {len(plan.stale)}"
    )
    for issue in plan.stale:
        console.print(f"[red]Stale[/red] {escape(issue.title)}: {escape(issue.reason)}")


def _print_article_report(review: ArticleDeployReport, review_path: Path) -> None:
    """Print the planned writes by kind of change, the kept live roots, and the conflicts."""
    console.print("[bold]Planned writes by kind of change[/bold]")
    for kind in CHANGE_KINDS:
        console.print(f"  {kind}: {len(review.pages(kind))}")
    console.print(f"  only links and stable keys: {len(review.invisible_pages())}")
    tier_changes = [(change.title, tier) for change in review.changes for tier in change.tier_changes]
    if tier_changes:
        console.print(f"[bold]Encounter tier changes[/bold] ({len(tier_changes)})")
        for title, tier in tier_changes:
            label = title if tier.name == title else f"{title} ({tier.name})"
            console.print(f"  {escape(label)}: {escape(tier.old)} -> {escape(tier.new)}")
    field_pages = review.field_pages()
    if field_pages:
        console.print("[bold]Most changed field values[/bold]")
        for field, titles in list(field_pages.items())[:15]:
            console.print(f"  {escape(field)}: {len(titles)}")
    structure = [change for change in review.changes if change.structure]
    if structure:
        console.print(f"[bold]Structure changes[/bold] ({len(structure)})")
        for change in structure[:20]:
            console.print(f"  {escape(change.title)}: {escape('; '.join(change.structure))}")
        if len(structure) > 20:
            console.print(f"  ... and {len(structure) - 20} more in the full report")
    for change in review.changes:
        for root in change.kept_roots:
            console.print(f"[yellow]Kept live root[/yellow] {escape(change.title)}: {escape(root)}")
    for issue in review.conflicts:
        console.print(f"[yellow]Conflict[/yellow] {escape(issue.title)}: {escape(issue.reason)}")
    console.print(f"Full report: {review_path}", markup=False)


def _print_article_deploy_result(result: ArticleDeployResult, manifest_path: Path) -> None:
    """Print the written pages, the pages that were not written, and why."""
    console.print(
        f"[green]Article deploy complete[/green] Edited: {result.count('edited')} "
        f"Created: {result.count('created')} Unchanged: {len(result.unchanged)} "
        f"Conflicts: {len(result.conflicts)} Blocked: {len(result.blocked)}"
    )
    console.print(f"Manifest: {manifest_path}", markup=False)
    for issue in result.conflicts:
        console.print(f"[yellow]Conflict[/yellow] {escape(issue.title)}: {escape(issue.reason)}")
    for issue in result.blocked:
        console.print(f"[red]Blocked[/red] {escape(issue.title)}: {escape(issue.reason)}")
    if result.stopped is not None:
        console.print(
            f"[red]Deploy stopped:[/red] {escape(result.stopped)}. "
            "The output is partial. The manifest records the new revision of each written page."
        )
