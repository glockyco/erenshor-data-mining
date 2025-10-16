"""Upload commands for wiki content publishing with rich progress UI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from erenshor.application.reporting import Category, Reporter
from erenshor.application.services import UploadService
from erenshor.application.upload import PageUploader
from erenshor.domain.events import UploadComplete
from erenshor.domain.exceptions import WikiAPIError
from erenshor.infrastructure.config.settings import load_settings
from erenshor.infrastructure.wiki.auth import BotCredentials, MediaWikiAuth
from erenshor.infrastructure.wiki.client import WikiAPIClient
from erenshor.cli.shared import (
    OperationResult,
    WikiEnvironment,
    create_upload_stats_table,
    handle_upload_event,
    print_upload_summary,
    setup_wiki_environment,
)

__all__ = ["diff", "diff_operation", "push", "status", "status_operation"]


app = typer.Typer()


@app.command("push")
def push(
    pages: list[str] = typer.Argument(
        None,
        help="Specific page titles to upload",
    ),
    all: bool = typer.Option(False, "--all", help="Upload all modified pages"),
    stdin: bool = typer.Option(False, "--stdin", help="Read page titles from stdin"),
    characters: bool = typer.Option(
        False, "--characters", help="Only upload character/enemy pages"
    ),
    items: bool = typer.Option(False, "--items", help="Only upload item pages"),
    weapons: bool = typer.Option(False, "--weapons", help="Only upload weapon pages"),
    armor: bool = typer.Option(False, "--armor", help="Only upload armor pages"),
    abilities: bool = typer.Option(
        False, "--abilities", help="Only upload ability (spell/skill) pages"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview uploads without making changes"
    ),
    batch_size: int | None = typer.Option(
        None, "--batch-size", help="Max pages to upload (skipped pages don't count)"
    ),
    delay: float | None = typer.Option(
        None, "--delay", help="Override delay between uploads"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force upload even if content is identical",
    ),
    summary: str | None = typer.Option(None, "--summary", help="Edit summary"),
    minor: bool | None = typer.Option(
        None, "--minor/--no-minor", help="Mark as minor edit"
    ),
) -> None:
    """Upload wiki pages with safety checks and real-time progress.

    By default, only uploads pages that have been modified since last push.
    Use --dry-run to preview what would be uploaded without making changes.

    Examples:
        # Dry-run all modified pages
        wiki push --all --dry-run

        # Upload only character pages
        wiki push --characters --dry-run

        # Upload only weapon pages
        wiki push --weapons --dry-run

        # Upload only armor pages
        wiki push --armor --dry-run

        # Upload specific pages
        wiki push Armor Weapons "Time Stone"

        # Upload from stdin (for scripting)
        git diff --name-only | wiki push --stdin

        # Upload batch with custom summary
        wiki push --all --batch-size 50 --summary "Update drop rates"
    """
    # Load config
    config = load_settings()

    # Check credentials (even in dry-run, warn if missing)
    console = Console()
    if not config.bot_username or not config.bot_password:
        if dry_run:
            console.print(
                "[yellow]Warning: Bot credentials not configured "
                "(set ERENSHOR_BOT_USERNAME and ERENSHOR_BOT_PASSWORD)[/yellow]"
            )
        else:
            console.print("[red]Error: Bot credentials required for upload[/red]")
            console.print(
                "Set ERENSHOR_BOT_USERNAME and ERENSHOR_BOT_PASSWORD in .env or environment"
            )
            raise typer.Exit(1)

    # Apply overrides
    batch_size = batch_size or config.upload_batch_size
    delay = delay or config.upload_delay
    summary = summary or config.upload_edit_summary
    minor = minor if minor is not None else config.upload_minor_edit

    # Setup environment
    env = setup_wiki_environment(settings=config)

    # Determine pages to upload
    with console.status("[bold blue]Discovering pages to upload..."):
        titles = _get_titles(
            pages, all, stdin, characters, items, weapons, armor, abilities, env
        )

    if not titles:
        console.print(
            "[red]Error: No pages specified. Use --all, provide page names, or use --stdin[/red]"
        )
        raise typer.Exit(1)

    # NOTE: Batch limit is applied AFTER skipping (in the upload loop)
    # so that skipped pages don't count toward the batch size
    console.print(f"Found {len(titles):,} pages to process\n")

    if dry_run:
        console.print("[yellow]DRY-RUN MODE: No actual uploads will be made[/yellow]\n")

    # Initialize reporting
    reporter = Reporter.open(
        command="wiki push",
        args={
            "batch_size": batch_size,
            "delay": delay,
            "dry_run": dry_run,
            "force": force,
        },
        reports_dir=config.reports_dir,
    )

    # Wire up components
    client = WikiAPIClient(api_url=config.api_url)

    # Authenticate (unless dry-run)
    if not dry_run:
        if not config.bot_username or not config.bot_password:
            console.print("[red]Error: Bot credentials not configured[/red]")
            reporter.finish(exit_code=1)
            raise typer.Exit(1)
        credentials = BotCredentials(
            username=config.bot_username,
            password=config.bot_password,
            api_url=config.api_url,
        )
        auth = MediaWikiAuth(credentials)
        try:
            if not auth.login():
                console.print(
                    "[red]Error: Authentication failed (wrong credentials)[/red]"
                )
                reporter.finish(exit_code=1)
                raise typer.Exit(1)
        except WikiAPIError as e:
            console.print(f"[red]Error: Authentication failed: {e}[/red]")
            reporter.finish(exit_code=1)
            raise typer.Exit(1)
        client.set_auth_session(auth.session)

    # Setup stats and recent items tracking
    stats = {"uploaded": 0, "skipped": 0, "failed": 0}
    recent_items: list[tuple[str, str, str]] = []
    panel_title = "[DRY-RUN] Uploading Pages" if dry_run else "Uploading Pages"
    duration_seconds = 0.0

    # Execute upload with Live display
    if dry_run:
        # Dry-run mode: simulate upload
        with Live(
            Panel(
                create_upload_stats_table(stats, recent_items),
                title=panel_title,
                border_style="green",
            ),
            refresh_per_second=4,
        ) as live:
            for event in _dry_run_upload_events(titles, env, force, batch_size):
                if isinstance(event, UploadComplete):
                    duration_seconds = event.duration_seconds
                    reporter.metric("total", event.total)
                    reporter.metric("uploaded", event.uploaded)
                    reporter.metric("skipped", event.skipped)
                    reporter.metric("failed", event.failed)
                    reporter.metric("duration_seconds", event.duration_seconds)
                else:
                    handle_upload_event(
                        event,
                        stats,
                        recent_items,
                        console,
                        reporter,
                        Category.IO,
                        live,
                        panel_title,
                    )
    else:
        # Real upload mode
        uploader = PageUploader(client)
        service = UploadService(
            uploader, env.output_storage, env.cache_storage, env.registry
        )

        with Live(
            Panel(
                create_upload_stats_table(stats, recent_items),
                title=panel_title,
                border_style="green",
            ),
            refresh_per_second=4,
        ) as live:
            for event in service.upload_pages(
                titles, summary, minor, bot=True, force=force, batch_size=batch_size
            ):
                if isinstance(event, UploadComplete):
                    duration_seconds = event.duration_seconds
                    reporter.metric("total", event.total)
                    reporter.metric("uploaded", event.uploaded)
                    reporter.metric("skipped", event.skipped)
                    reporter.metric("failed", event.failed)
                    reporter.metric("duration_seconds", event.duration_seconds)
                else:
                    handle_upload_event(
                        event,
                        stats,
                        recent_items,
                        console,
                        reporter,
                        Category.IO,
                        live,
                        panel_title,
                    )

    # Display summary
    print_upload_summary(stats, console, reporter, env.registry, duration_seconds)

    reporter.finish(exit_code=1 if stats["failed"] > 0 else 0)

    if stats["failed"] > 0:
        raise typer.Exit(code=1)


def _filter_pages_with_content(titles: list[str], env: WikiEnvironment) -> list[str]:
    """Filter page titles to only those with existing content files.

    Args:
        titles: List of page titles to filter
        env: WikiEnvironment with registry and storage

    Returns:
        List of page titles that have content files
    """
    filtered_titles = []
    for title in titles:
        page = env.registry.get_page_by_title(title)
        if page and env.output_storage.exists(page):
            filtered_titles.append(title)
    return filtered_titles


def _get_items_by_kind(env: WikiEnvironment, weapons: bool, armor: bool) -> list[Any]:
    """Get item pages filtered by ItemKind (weapon/armor).

    Args:
        env: WikiEnvironment with engine and registry
        weapons: Include weapon pages
        armor: Include armor pages

    Returns:
        List of WikiPage objects for matching items
    """
    from erenshor.domain.services.item_classifier import classify_item_kind
    from erenshor.domain.value_objects.entity_type import EntityType
    from erenshor.infrastructure.database.repositories.items import get_items

    # Get all items from database
    items = get_items(env.engine, obtainable_only=False)

    # Build mapping of item ID to ItemKind
    item_kinds: dict[str, str] = {}
    for item in items:
        kind = classify_item_kind(
            required_slot=item.RequiredSlot,
            teach_spell=item.TeachSpell,
            teach_skill=item.TeachSkill,
            template_flag=item.Template,
            click_effect=item.ItemEffectOnClick,
            disposable=item.Disposable,
        )
        item_kinds[item.Id] = kind

    # Filter pages by ItemKind
    all_item_pages = env.registry.list_pages_by_entity_type(EntityType.ITEM)
    filtered_pages = []
    for page in all_item_pages:
        # Check if any entity on this page matches the desired kind
        for entity in page.entities:
            if entity.entity_type == EntityType.ITEM:
                entity_id = entity.db_id
                if entity_id and entity_id in item_kinds:
                    kind = item_kinds[entity_id]
                    if (weapons and kind == "weapon") or (armor and kind == "armor"):
                        filtered_pages.append(page)
                        break  # Found a match, no need to check other entities on this page

    return filtered_pages


def _get_titles(
    pages: list[str] | None,
    all: bool,
    stdin: bool,
    characters: bool,
    items: bool,
    weapons: bool,
    armor: bool,
    abilities: bool,
    env: WikiEnvironment,
) -> list[str]:
    """Determine which pages to upload based on CLI arguments.

    Args:
        pages: Positional page titles
        all: Upload all modified pages
        stdin: Read titles from stdin
        characters: Only upload character/enemy pages
        items: Only upload item pages
        weapons: Only upload weapon pages
        armor: Only upload armor pages
        abilities: Only upload ability pages
        env: WikiEnvironment with registry

    Returns:
        List of page titles to upload
    """
    from erenshor.domain.value_objects.entity_type import EntityType

    # Determine which pages to consider
    if all:
        # All pages
        all_pages = env.registry.list_pages()
    elif characters:
        # Character pages only
        all_pages = env.registry.list_pages_by_entity_type(EntityType.CHARACTER)
    elif items:
        # Item pages only
        all_pages = env.registry.list_pages_by_entity_type(EntityType.ITEM)
    elif weapons or armor:
        # Filter items by ItemKind
        all_pages = _get_items_by_kind(env, weapons, armor)
    elif abilities:
        # Ability pages (both spells and skills)
        spell_pages = env.registry.list_pages_by_entity_type(EntityType.SPELL)
        skill_pages = env.registry.list_pages_by_entity_type(EntityType.SKILL)
        # Combine and deduplicate (some pages may have both spells and skills)
        all_pages = list({p.title: p for p in spell_pages + skill_pages}.values())
    elif stdin:
        # Read titles from stdin - filter to only pages with content
        titles_from_stdin = [line.strip() for line in sys.stdin if line.strip()]
        return _filter_pages_with_content(titles_from_stdin, env)
    elif pages:
        # Use positional arguments - filter to only pages with content
        return _filter_pages_with_content(pages, env)
    else:
        # No source specified
        return []

    # Filter to only pages that need upload AND have content files
    # This prevents errors when pages are marked as needing upload but files don't exist
    pages_to_upload = []
    for page in all_pages:
        if page.needs_upload():
            # Verify content file exists before including in upload list
            if env.output_storage.exists(page):
                pages_to_upload.append(page.title)
    return pages_to_upload


def _dry_run_upload_events(
    titles: list[str],
    env: WikiEnvironment,
    force: bool,
    batch_size: int | None,
) -> Any:  # Returns Iterator[UploadEvent]
    """Simulate upload operation for dry-run mode, emitting events.

    Simulates the same skip logic as real uploads:
    - LOCAL-BASED SKIP: Content hash unchanged and already pushed
    - WIKI-BASED SKIP: Would be detected by comparing with wiki (not simulated in dry-run)

    Args:
        titles: List of page titles to simulate
        env: WikiEnvironment with storage and registry
        force: Whether to force upload even if content is identical
        batch_size: Maximum number of uploads + failures (None = unlimited)

    Yields:
        UploadEvent instances (PageUploaded, UploadFailed, UploadComplete)
    """
    import hashlib

    from erenshor.domain.events import PageUploaded, UploadComplete, UploadFailed

    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    processed_count = 0  # Uploaded + failed (not skipped)

    for title in titles:
        # Check batch limit (skips don't count)
        if batch_size is not None and processed_count >= batch_size:
            break

        page = env.registry.get_page_by_title(title)
        if not page:
            failed_count += 1
            processed_count += 1
            yield UploadFailed(
                page_title=title,
                error="Page not in registry",
            )
            continue

        updated_content = env.output_storage.read(page)
        if not updated_content:
            failed_count += 1
            processed_count += 1
            yield UploadFailed(
                page_title=title,
                error="No content found in wiki_updated/",
            )
            continue

        # Compare with cached content (wiki_cache/) - trust actual files, not registry
        if not force:
            cached_content = env.cache_storage.read(page)
            if cached_content is not None:
                # Compare actual file hashes
                cached_hash = hashlib.sha256(cached_content.encode()).hexdigest()
                updated_hash = hashlib.sha256(updated_content.encode()).hexdigest()

                if cached_hash == updated_hash:
                    # Content unchanged between cache and updated - skip
                    skipped_count += 1
                    yield PageUploaded(
                        page_title=title,
                        action="skipped",
                        message="Would skip - no changes between cached and updated content",
                    )
                    continue
            # If no cached content, proceed with upload (new page or never fetched)

        # Simulate successful upload
        uploaded_count += 1
        processed_count += 1
        yield PageUploaded(
            page_title=title,
            action="uploaded",
            message=f"Would upload {len(updated_content)} bytes",
        )

    # Emit completion event
    yield UploadComplete(
        total=len(titles),
        uploaded=uploaded_count,
        skipped=skipped_count,
        failed=failed_count,
        duration_seconds=0.0,  # Simulated, no real time
    )


@app.command("status")
def status(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
) -> None:
    """Show upload status of all pages in the registry."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = status_operation(env, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def status_operation(
    env: WikiEnvironment, reports_dir: Path | None = None
) -> OperationResult:
    """Show upload status - testable business logic."""
    from erenshor.application.reporting import Category, entity

    reporter = Reporter.open(
        command="wiki status",
        args={"db": "database"},
        reports_dir=reports_dir,
    )

    try:
        # Use existing registry and storage from environment
        registry = env.registry

        needs_upload = []
        up_to_date = []

        pages = registry.list_pages()
        for page in pages:
            if page.needs_upload():
                needs_upload.append(page)
            else:
                up_to_date.append(page)

        # Report metrics
        reporter.metric("needs_upload", len(needs_upload))
        reporter.metric("up_to_date", len(up_to_date))

        summary_lines = [
            "Upload Status:",
            f"  Needs upload: {len(needs_upload)}",
            f"  Up to date: {len(up_to_date)}",
        ]

        if needs_upload:
            summary_lines.append("\nPages needing upload:")
            for page in needs_upload[:10]:  # Show first 10
                summary_lines.append(f"  - {page.title} ({page.upload_status()})")
            if len(needs_upload) > 10:
                summary_lines.append(f"  ... and {len(needs_upload) - 10} more")

        reporter.finish(exit_code=0)
        return OperationResult(
            success=True,
            updated=0,
            summary_line="\n".join(summary_lines),
        )

    except Exception as exc:
        reporter.emit_error(
            message="Failed to get upload status",
            exception=exc,
            entity=entity(),
            category=Category.IO,
        )
        reporter.finish(exit_code=1)
        return OperationResult(
            success=False,
            updated=0,
            summary_line=f"Status operation failed: {exc}",
            errors=[str(exc)],
        )


@app.command("diff")
def diff(
    db: Path | None = typer.Option(None, help="Database path"),
    cache_dir: Path | None = typer.Option(None, help="Cache directory"),
    output_dir: Path | None = typer.Option(None, help="Output directory"),
    reports_dir: Path | None = typer.Option(None, help="Reports directory"),
    page_title: str = typer.Argument(..., help="Page title to show diff for"),
) -> None:
    """Show differences between local and original wiki content for a page."""
    env = setup_wiki_environment(db, cache_dir, output_dir)
    result = diff_operation(env, page_title, reports_dir)
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def diff_operation(
    env: WikiEnvironment, page_title: str, reports_dir: Path | None = None
) -> OperationResult:
    """Show diff for page - testable business logic."""
    from erenshor.application.reporting import Category, entity

    reporter = Reporter.open(
        command="wiki diff",
        args={"db": "database", "page_title": page_title},
        reports_dir=reports_dir,
    )

    try:
        # Use existing registry and storage from environment
        registry = env.registry
        storage = env.output_storage

        # Find the page
        page = registry.get_page_by_title(page_title)
        if not page:
            reporter.emit_error(
                message=f"Page not found: {page_title}",
                exception=None,
                entity=entity(page_title=page_title),
                category=Category.IO,
            )
            reporter.finish(exit_code=1)
            return OperationResult(
                success=False,
                updated=0,
                summary_line=f"Page not found: {page_title}",
                errors=[f"Page not found: {page_title}"],
            )

        # Check if page exists locally
        if not storage.exists(page):
            summary = f"No local content found for {page_title}"
        else:
            # Get diff information
            content = storage.read(page)
            if content is None:
                summary = f"Cannot read local content for {page_title}"
            else:
                # Show basic diff information
                char_count = len(content)
                line_count = content.count("\n") + 1
                upload_status = page.upload_status()

                summary_parts = [
                    f"Diff for {page_title}:",
                    f"  Local content: {char_count} characters, {line_count} lines",
                    f"  Upload status: {upload_status}",
                ]

                if page.original_content_hash:
                    import hashlib

                    current_hash = hashlib.sha256(content.encode()).hexdigest()
                    if current_hash == page.original_content_hash:
                        summary_parts.append("  Status: No changes from original")
                    else:
                        summary_parts.append("  Status: Content modified from original")
                else:
                    summary_parts.append("  Status: New or untracked content")

                # Add timestamps if available
                if page.last_fetched:
                    summary_parts.append(f"  Last fetched: {page.last_fetched}")
                if page.last_updated:
                    summary_parts.append(f"  Last updated: {page.last_updated}")
                if page.last_pushed:
                    summary_parts.append(f"  Last pushed: {page.last_pushed}")

                summary = "\n".join(summary_parts)

        reporter.finish(exit_code=0)
        return OperationResult(
            success=True,
            updated=0,
            summary_line=summary,
        )

    except Exception as exc:
        reporter.emit_error(
            message=f"Failed to show diff for {page_title}",
            exception=exc,
            entity=entity(page_title=page_title),
            category=Category.IO,
        )
        reporter.finish(exit_code=1)
        return OperationResult(
            success=False,
            updated=0,
            summary_line=f"Diff operation failed: {exc}",
            errors=[str(exc)],
        )
