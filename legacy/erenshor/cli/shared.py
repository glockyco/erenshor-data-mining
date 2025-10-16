"""Shared infrastructure for CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Type

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from sqlalchemy.engine import Engine

from erenshor.infrastructure.config.settings import WikiSettings, load_settings
from erenshor.infrastructure.database.repositories import get_engine
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry

__all__ = [
    "ContentTypeConfig",
    "OperationResult",
    "WikiEnvironment",
    "create_update_stats_table",
    "create_upload_stats_table",
    "handle_update_event",
    "handle_upload_event",
    "print_update_summary",
    "print_upload_summary",
    "run_update_command",
    "setup_wiki_environment",
]


@dataclass
class WikiEnvironment:
    """Complete environment setup for wiki operations."""

    engine: Engine
    registry: WikiRegistry
    cache_storage: PageStorage
    output_storage: PageStorage
    settings: WikiSettings


@dataclass
class ContentTypeConfig:
    """Configuration for a content type update command.

    Defines all the components needed to run an update for a specific
    content type (items, characters, abilities, etc.).

    Attributes:
        name: Display name for the content type (e.g., "items", "abilities")
        generator_class: Generator class for this content type
        transformer_class: Transformer class for this content type
        validator_class: Validator class for this content type (optional)
        category: Reporter category for event emission
        requires_parser_merger: Whether transformer needs WikiParser and FieldMerger
    """

    name: str
    generator_class: Type[Any]
    transformer_class: Type[Any]
    validator_class: Optional[Type[Any]]
    category: str
    requires_parser_merger: bool = False


@dataclass
class OperationResult:
    """Base result class for command operations."""

    success: bool
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    summary_line: str = ""
    index_path: str = ""


def setup_wiki_environment(
    db: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    settings: Optional[WikiSettings] = None,
) -> WikiEnvironment:
    """Common setup that every command needs.

    Eliminates the repetitive boilerplate found in every command.

    Args:
        db: Database path (uses default from settings if None)
        cache_dir: Cache directory (uses default from settings if None)
        output_dir: Output directory (uses default from settings if None)
        settings: Pre-loaded settings (loads from config if None)

    Returns:
        WikiEnvironment with all necessary components initialized
    """
    if settings is None:
        settings = load_settings()

    # Use provided paths or fall back to settings
    if db is None:
        db = settings.db_path
    if cache_dir is None:
        cache_dir = settings.cache_dir
    if output_dir is None:
        output_dir = settings.output_dir

    engine = get_engine(str(db))

    # Import here to avoid circular dependency
    from erenshor.cli.wiki_group import get_registry

    registry = get_registry(engine)
    cache_storage = PageStorage(registry, pages_dir=cache_dir)
    output_storage = PageStorage(registry, pages_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    return WikiEnvironment(
        engine=engine,
        registry=registry,
        cache_storage=cache_storage,
        output_storage=output_storage,
        settings=settings,
    )


def create_update_stats_table(
    stats: dict[str, int], recent_items: list[tuple[str, str, str]]
) -> Table:
    """Create a stats table for update progress display.

    Args:
        stats: Dictionary with 'updated', 'unchanged', 'failed' counts
        recent_items: List of (title, status, icon) tuples for recent updates

    Returns:
        Rich Table with formatted stats and recent items
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="right")
    table.add_column(style="magenta")

    table.add_row("Updated:", str(stats["updated"]))
    table.add_row("Unchanged:", str(stats["unchanged"]))
    table.add_row("Failed:", str(stats["failed"]))
    table.add_row("", "")

    for title, status, icon in recent_items[-5:]:
        table.add_row(icon, f"{title} ({status})")

    return table


def handle_update_event(
    event: Any,
    stats: dict[str, int],
    recent_items: list[tuple[str, str, str]],
    console: Console,
    reporter: Any,
    category: Any,
    live: Live,
    title: str,
) -> None:
    """Handle update events with consistent UI and reporting.

    Args:
        event: UpdateEvent (PageUpdated, ValidationFailed, UpdateFailed, or UpdateComplete)
        stats: Statistics dictionary to update
        recent_items: Recent items list to append to
        console: Rich console for output
        reporter: Reporter instance for event emission
        category: Category enum value for reporting
        live: Rich Live display to update
        title: Title string for panel display (e.g., "Updating Items")
    """
    from erenshor.application.reporting import entity
    from erenshor.domain.events import (
        PageUpdated,
        UpdateComplete,
        UpdateFailed,
        ValidationFailed,
    )

    if isinstance(event, PageUpdated):
        action = "updated" if event.changed else "unchanged"
        icon = "✓" if event.changed else "○"
        stats[action] += 1
        recent_items.append((event.page_title, action, icon))
        live.update(
            Panel(
                create_update_stats_table(stats, recent_items),
                title=title,
                border_style="green",
            )
        )

        reporter.emit_update(
            entity=entity(page_title=event.page_title),
            action=action,
            category=category,
        )

    elif isinstance(event, ValidationFailed):
        stats["failed"] += 1
        recent_items.append((event.page_title, "validation failed", "✗"))
        live.update(
            Panel(
                create_update_stats_table(stats, recent_items),
                title=title,
                border_style="green",
            )
        )

        console.print(f"\n[red]✗ Validation failed:[/red] {event.page_title}")
        for violation in event.violations:
            severity_color = "red" if violation.severity == "error" else "yellow"
            severity_label = "ERROR" if violation.severity == "error" else "WARN"
            console.print(
                f"  [{severity_color}]{severity_label}[/{severity_color}] "
                f"{violation.field}: {violation.message}"
            )

        reporter.emit_error(
            message="Validation failed",
            entity=entity(page_title=event.page_title),
            category=category,
        )

    elif isinstance(event, UpdateFailed):
        stats["failed"] += 1
        recent_items.append((event.page_title, "error", "✗"))
        live.update(
            Panel(
                create_update_stats_table(stats, recent_items),
                title=title,
                border_style="green",
            )
        )

        reporter.emit_error(
            message=f"Update failed: {event.error}",
            entity=entity(page_title=event.page_title),
            category=category,
        )

    elif isinstance(event, UpdateComplete):
        pass


def create_upload_stats_table(
    stats: dict[str, int], recent_items: list[tuple[str, str, str]]
) -> Table:
    """Create a stats table for upload progress display.

    Args:
        stats: Dictionary with 'uploaded', 'skipped', 'failed' counts
        recent_items: List of (title, status, icon) tuples for recent uploads

    Returns:
        Rich Table with formatted stats and recent items
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="right")
    table.add_column(style="magenta")

    table.add_row("Uploaded:", str(stats["uploaded"]))
    table.add_row("Skipped:", str(stats["skipped"]))
    table.add_row("Failed:", str(stats["failed"]))
    table.add_row("", "")

    for title, status, icon in recent_items[-5:]:
        table.add_row(icon, f"{title} ({status})")

    return table


def handle_upload_event(
    event: Any,
    stats: dict[str, int],
    recent_items: list[tuple[str, str, str]],
    console: Console,
    reporter: Any,
    category: Any,
    live: Live,
    title: str,
) -> None:
    """Handle upload events with consistent UI and reporting.

    Args:
        event: UploadEvent (PageUploaded, UploadFailed, or UploadComplete)
        stats: Statistics dictionary to update
        recent_items: Recent items list to append to
        console: Rich console for output
        reporter: Reporter instance for event emission
        category: Category enum value for reporting
        live: Rich Live display to update
        title: Title string for panel display (e.g., "Uploading Pages")
    """
    from erenshor.application.reporting import entity
    from erenshor.domain.events import (
        PageUploaded,
        UploadComplete,
        UploadFailed,
    )

    if isinstance(event, PageUploaded):
        action = event.action  # "uploaded", "skipped", "failed"
        icon = {"uploaded": "✓", "skipped": "⊘", "failed": "✗"}.get(action, "•")
        stats[action] = stats.get(action, 0) + 1
        recent_items.append((event.page_title, action, icon))
        live.update(
            Panel(
                create_upload_stats_table(stats, recent_items),
                title=title,
                border_style="green",
            )
        )

        details = {"message": event.message} if event.message else {}
        reporter.emit_update(
            entity=entity(page_title=event.page_title),
            action=action,
            category=category,
            details=details,
        )

    elif isinstance(event, UploadFailed):
        stats["failed"] = stats.get("failed", 0) + 1
        recent_items.append((event.page_title, "failed", "✗"))
        live.update(
            Panel(
                create_upload_stats_table(stats, recent_items),
                title=title,
                border_style="green",
            )
        )

        console.print(f"\n[red]✗ Upload failed:[/red] {event.page_title}")
        console.print(f"  Error: {event.error}")

        reporter.emit_error(
            message=f"Upload failed: {event.error}",
            entity=entity(page_title=event.page_title),
            category=category,
        )

    elif isinstance(event, UploadComplete):
        pass


def print_update_summary(
    stats: dict[str, int],
    console: Console,
    reporter: Any,
    registry: Any,
    content_type: str,
) -> None:
    """Print final summary after update completion.

    Args:
        stats: Statistics dictionary with counts
        console: Rich console for output
        reporter: Reporter instance
        registry: WikiRegistry for page count
        content_type: Content type name for display (e.g., "items", "abilities")
    """
    total = stats["updated"] + stats["unchanged"] + stats["failed"]
    console.print()
    console.print(f"[bold green]✓[/bold green] Processed {total} {content_type}")
    console.print(f"  Updated: {stats['updated']}")
    console.print(f"  Unchanged: {stats['unchanged']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print()
    console.print(f"Registry saved with {len(registry.pages)} pages")

    if stats["failed"] > 0:
        console.print()
        console.print(f"[yellow]Detailed report:[/yellow] {reporter.base_dir}")
        console.print("[yellow]Next steps:[/yellow]")
        console.print("  → Review full report: cat out/reports/*/summary.json")
        console.print(
            "  → Check specific events: grep 'validation' out/reports/*/events.jsonl"
        )


def print_upload_summary(
    stats: dict[str, int],
    console: Console,
    reporter: Any,
    registry: Any,
    duration: float,
) -> None:
    """Print final summary after upload completion.

    Args:
        stats: Statistics dictionary with counts
        console: Rich console for output
        reporter: Reporter instance
        registry: WikiRegistry for page count
        duration: Upload duration in seconds
    """
    total = stats["uploaded"] + stats["skipped"] + stats["failed"]
    console.print()
    console.print(f"[bold green]✓[/bold green] Processed {total} pages")
    console.print(f"  Uploaded: {stats['uploaded']}")
    console.print(f"  Skipped: {stats['skipped']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print()

    if duration > 0:
        rate = total / duration
        console.print(f"Duration: {duration:.1f}s ({rate:.1f} pages/sec)")

    console.print(f"Registry saved with {len(registry.pages)} pages")

    if stats["failed"] > 0:
        console.print()
        console.print(f"[yellow]Detailed report:[/yellow] {reporter.base_dir}")
        console.print("[yellow]Next steps:[/yellow]")
        console.print("  → Review full report: cat out/reports/*/summary.json")
        console.print(
            "  → Check specific events: grep 'failed' out/reports/*/events.jsonl"
        )


def run_update_command(
    config: ContentTypeConfig,
    filter_str: Optional[str],
    validate: bool,
    validate_only: bool,
    dry_run: bool,
    db: Optional[Path],
    cache_dir: Optional[Path],
    output_dir: Optional[Path],
) -> None:
    """Generic update command runner - eliminates CLI duplication.

    This function encapsulates the common pattern shared by all update commands,
    eliminating 85%+ duplication across update_items, update_characters, etc.

    Args:
        config: ContentTypeConfig defining generator, transformer, validator
        filter_str: Optional filter string (name or ID)
        validate: Whether to validate content before writing
        validate_only: Only validate, don't write files
        dry_run: Show what would change without writing
        db: Database path override
        cache_dir: Cache directory override
        output_dir: Output directory override

    Raises:
        typer.Exit: With code 1 if any updates failed
    """
    from erenshor.application.reporting import Category, Reporter
    from erenshor.application.services.update_service import UpdateService
    from erenshor.domain.events import ContentGenerated, UpdateComplete

    console = Console()
    env = setup_wiki_environment(db, cache_dir, output_dir)

    generator = config.generator_class()

    if config.requires_parser_merger:
        from erenshor.application.transformers.merger import FieldMerger
        from erenshor.application.transformers.parser import WikiParser

        parser = WikiParser()
        merger = FieldMerger()
        transformer = config.transformer_class(parser, merger)
    else:
        transformer = config.transformer_class()

    validator = (
        config.validator_class() if (validate and config.validator_class) else None
    )

    service = UpdateService(
        generator=generator,
        transformer=transformer,
        validator=validator,
        cache_storage=env.cache_storage,
        output_storage=env.output_storage,
        registry=env.registry,
    )

    reporter = Reporter.open(
        command=f"update {config.name}", args={"db": str(db) if db else "default"}
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        expand=True,
    )

    stats = {"updated": 0, "unchanged": 0, "failed": 0}
    recent_items: list[tuple[str, str, str]] = []
    title = f"Updating {config.name.capitalize()}"

    with Live(
        Panel(
            create_update_stats_table(stats, recent_items),
            title=title,
            border_style="green",
        ),
        refresh_per_second=4,
    ) as live:
        task_id = progress.add_task(f"Processing {config.name}...", total=None)

        for event in service.update_pages(
            env.engine,
            skip_validation=not validate,
            validate_only=validate_only,
            dry_run=dry_run,
            filter=filter_str,
        ):
            if isinstance(event, ContentGenerated):
                progress.update(task_id, description=f"Generating: {event.page_title}")

            elif isinstance(event, UpdateComplete):
                progress.update(
                    task_id,
                    description="Complete!",
                    completed=event.total,
                    total=event.total,
                )
                reporter.metric(f"{config.name}_processed", event.total)
                reporter.metric(f"{config.name}_updated", event.updated)
                reporter.metric(f"{config.name}_unchanged", event.unchanged)
                reporter.metric(f"{config.name}_failed", event.failed)

            else:
                category_obj = getattr(Category, config.category.upper())
                handle_update_event(
                    event,
                    stats,
                    recent_items,
                    console,
                    reporter,
                    category_obj,
                    live,
                    title,
                )

    print_update_summary(stats, console, reporter, env.registry, config.name)

    reporter.finish(exit_code=1 if stats["failed"] > 0 else 0)

    if stats["failed"] > 0:
        raise typer.Exit(code=1)
