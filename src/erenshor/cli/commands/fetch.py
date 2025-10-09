"""Fetch commands for wiki content retrieval with rich progress UI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from erenshor.application.fetch import (
    PageFetched,
    PageFetcher,
    ProgressEvent,
)
from erenshor.application.reporting import Reporter
from erenshor.application.services import FetchService
from erenshor.infrastructure.config.settings import load_settings
from erenshor.infrastructure.wiki.client import WikiAPIClient
from erenshor.infrastructure.wiki.template_cache import (
    fetch_templates as fetch_templates_func,
)
from erenshor.cli.shared import (
    OperationResult,
    setup_wiki_environment,
)

__all__ = ["fetch", "fetch_templates", "fetch_templates_operation"]


app = typer.Typer()


@app.command("fetch")
def fetch(
    pages: list[str] = typer.Argument(
        None,
        help="Specific page titles to fetch",
    ),
    all: bool = typer.Option(False, "--all", help="Fetch all pages from wiki"),
    stdin: bool = typer.Option(False, "--stdin", help="Read page titles from stdin"),
    clean_cache: bool = typer.Option(
        False, "--clean-cache", help="Clear cache before fetch"
    ),
    batch_size: int | None = typer.Option(
        None, "--batch-size", help="Override batch size"
    ),
    delay: float | None = typer.Option(
        None, "--delay", help="Override delay between batches"
    ),
    api_url: str | None = typer.Option(None, "--api-url", help="Override API URL"),
) -> None:
    """Fetch wiki pages with real-time progress.

    Examples:
        # Fetch all pages
        wiki fetch --all

        # Fetch specific pages
        wiki fetch Armor Weapons "Time Stone"

        # Fetch from stdin
        echo -e "Armor\\nWeapons" | wiki fetch --stdin

        # Clean cache and re-fetch
        wiki fetch --all --clean-cache
    """
    # Load config
    config = load_settings()

    # Apply overrides
    api_url = api_url or config.api_url
    batch_size = batch_size or config.api_batch_size
    delay = delay or config.api_delay

    # Setup environment
    env = setup_wiki_environment(settings=config)

    # Clear cache if requested
    if clean_cache:
        for f in env.cache_storage.pages_dir.glob("*.txt"):
            f.unlink()

    # Determine pages to fetch
    console = Console()
    with console.status("[bold blue]Discovering pages..."):
        titles = _get_titles(pages, all, stdin, api_url)

    if not titles:
        console.print(
            "[red]Error: No pages specified. Use --all, provide page names, or use --stdin[/red]"
        )
        raise typer.Exit(1)

    console.print(f"Found {len(titles):,} pages to fetch\n")

    # Initialize reporting
    reporter = Reporter.open(
        command="wiki fetch",
        args={"batch_size": batch_size, "delay": delay, "api_url": api_url},
        reports_dir=config.reports_dir,
    )

    # Setup progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        TransferSpeedColumn(),
        console=console,
    )

    # Wire up components
    client = WikiAPIClient(api_url=api_url)

    task_id = None

    def on_progress(event: ProgressEvent) -> None:
        nonlocal task_id
        if isinstance(event, PageFetched):
            if task_id:
                progress.update(
                    task_id,
                    advance=1,
                    description=f"Fetching: {event.title} ({event.size_bytes / 1024:.1f} KB)",
                )
            from erenshor.application.reporting import Category

            reporter.emit_update(
                entity={"page_title": event.title},
                action="fetched" if event.success else "failed",
                category=Category.IO,
            )

    fetcher = PageFetcher(client, on_progress=on_progress)
    service = FetchService(fetcher, env.cache_storage, env.registry)

    # Execute with progress
    with progress:
        task_id = progress.add_task(
            f"Fetching {len(titles):,} pages", total=len(titles)
        )
        result = service.fetch_pages(titles)

    # Finalize reporting
    reporter.metric("total", result.total)
    reporter.metric("successful", len(result.successful))
    reporter.metric("failed", len(result.failed))
    reporter.metric("duration_seconds", result.duration_seconds)
    reporter.metric("bytes_fetched", result.bytes_fetched)
    reporter.finish(exit_code=0)

    # Display summary
    _display_fetch_summary(result, console, reporter.base_dir)

    raise typer.Exit(0)


def _get_titles(
    pages: list[str] | None,
    all: bool,
    stdin: bool,
    api_url: str,
) -> list[str]:
    """Determine which pages to fetch based on CLI arguments.

    Args:
        pages: Positional page titles
        all: Fetch all pages from wiki
        stdin: Read titles from stdin
        api_url: MediaWiki API URL

    Returns:
        List of page titles to fetch
    """
    if all:
        # Fetch all pages from the wiki
        client = WikiAPIClient(api_url=api_url)
        return client.list_pages(namespace=0)
    elif stdin:
        # Read titles from stdin
        return [line.strip() for line in sys.stdin if line.strip()]
    elif pages:
        # Use positional arguments
        return pages
    else:
        # No source specified
        return []


def _display_fetch_summary(result: Any, console: Console, report_dir: Path) -> None:
    """Display rich summary table after fetch completes.

    Args:
        result: FetchOperation result
        console: Rich console for output
        report_dir: Path to reports directory
    """
    table = Table(title="Fetch Complete")
    table.add_column("Metric")
    table.add_column("Value", style="cyan")

    table.add_row("Total", str(result.total))
    success_pct = len(result.successful) / result.total * 100 if result.total > 0 else 0
    table.add_row(
        "Successful",
        f"[green]{len(result.successful)} ({success_pct:.1f}%)[/green]",
    )
    failed_pct = len(result.failed) / result.total * 100 if result.total > 0 else 0
    table.add_row("Failed", f"[red]{len(result.failed)} ({failed_pct:.1f}%)[/red]")
    table.add_row("Size", f"{result.bytes_fetched / 1024 / 1024:.1f} MB")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    rate = result.total / result.duration_seconds if result.duration_seconds > 0 else 0
    table.add_row("Rate", f"{rate:.1f} pages/sec")

    console.print(table)

    # Show failed pages
    if result.failed:
        console.print("\n[red]Failed Pages (showing first 10):[/red]")
        for f in result.failed[:10]:
            console.print(f"  - {f.title}: {f.error}")
        if len(result.failed) > 10:
            console.print(f"  ... and {len(result.failed) - 10} more")

    console.print(f"\n[dim]Full report: {report_dir}/[/dim]")


@app.command("fetch-templates")
def fetch_templates(
    api_url: str = typer.Option(
        "https://erenshor.wiki.gg/api.php", help="MediaWiki API endpoint"
    ),
    out_dir: Path = typer.Option(
        Path("templates_cache"), help="Directory to store template cache"
    ),
    batch_size: int = typer.Option(25, help="Titles per request"),
    delay: float = typer.Option(1.0, help="Delay between batch requests (seconds)"),
) -> None:
    """Fetch wiki templates."""
    result = fetch_templates_operation(
        api_url=api_url,
        out_dir=out_dir,
        batch_size=batch_size,
        delay=delay,
    )
    typer.echo(result.summary_line)
    if result.errors:
        raise typer.Exit(1)


def fetch_templates_operation(
    api_url: str = "https://erenshor.wiki.gg/api.php",
    out_dir: Path = Path("templates_cache"),
    batch_size: int = 25,
    delay: float = 1.0,
) -> OperationResult:
    """Fetch wiki templates - testable business logic."""
    client = WikiAPIClient(api_url=api_url)
    idx = fetch_templates_func(client, out_dir, delay=delay, batch_size=batch_size)

    return OperationResult(
        success=True,
        updated=0,  # fetch_templates_func doesn't return a count
        summary_line=f"Fetched template pages via {api_url} (batch={batch_size}, delay={delay:.1f}s). Wrote template cache index to {idx}",
    )
