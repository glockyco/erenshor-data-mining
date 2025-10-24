"""Backup commands for managing game data backups.

This module provides commands for viewing and managing backups:
- Listing backups across all variants or specific variant
- Viewing backup details and disk usage

Backups are created automatically during Unity exports and are intended for
cross-version analysis (SQL queries, C# diffs, change detection).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from erenshor.application.services.backup_service import BackupService

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="backup",
    help="Manage game data backups",
    no_args_is_help=True,
)

console = Console()


@app.command("list")
def list_backups(
    ctx: typer.Context,
    variant: str | None = typer.Option(
        None,
        "--variant",
        "-v",
        help="Show backups for specific variant (default: all variants)",
    ),
) -> None:
    """List all backups with disk usage information.

    Shows backup details including build ID, creation date, and sizes.
    By default shows all variants. Use --variant to filter to specific variant.

    Backups are for cross-version analysis (SQL queries, C# diffs), not restoration.
    """
    cli_ctx: CLIContext = ctx.obj
    service = BackupService()

    # Determine which variants to show
    if variant:
        # Show specific variant
        if variant not in cli_ctx.config.variants:
            console.print(f"[red]Error: Unknown variant '{variant}'[/red]")
            raise typer.Exit(1)

        variants_to_show = [variant]
    else:
        # Show all enabled variants
        variants_to_show = [name for name, config in cli_ctx.config.variants.items() if config.enabled]

    if not variants_to_show:
        console.print("[yellow]No enabled variants found[/yellow]")
        return

    # Track totals across all variants
    total_backups = 0
    total_size = 0

    # Display backups for each variant
    for variant_name in variants_to_show:
        variant_config = cli_ctx.config.variants[variant_name]
        backup_dir = variant_config.resolved_backups(cli_ctx.repo_root)

        # Get backups for this variant
        backups = service.list_backups(backup_dir)

        # Display variant header
        console.print()
        console.print(f"[bold cyan]Backups for variant: {variant_name}[/bold cyan]")

        if not backups:
            console.print("  [dim]No backups found[/dim]")
            continue

        # Create table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Build ID", style="cyan")
        table.add_column("Created")
        table.add_column("Database", justify="right")
        table.add_column("Scripts", justify="right")
        table.add_column("Total", justify="right", style="bold")

        # Add rows
        variant_total_size = 0
        for backup in backups:
            table.add_row(
                backup.build_id,
                backup.created_at[:19].replace("T", " "),  # Format: YYYY-MM-DD HH:MM:SS
                service._format_size(backup.database_size_bytes),
                service._format_size(backup.scripts_size_bytes),
                service._format_size(backup.total_size_bytes),
            )
            variant_total_size += backup.total_size_bytes

        # Add separator and total row
        table.add_row("─" * 20, "─" * 19, "─" * 10, "─" * 10, "─" * 10)
        table.add_row(
            f"Total: {len(backups)} backup{'s' if len(backups) != 1 else ''}",
            "",
            "",
            "",
            service._format_size(variant_total_size),
        )

        console.print(table)

        # Update grand totals
        total_backups += len(backups)
        total_size += variant_total_size

        # Show location if filtering to specific variant
        if len(variants_to_show) == 1:
            console.print()
            console.print(f"  [dim]Location: {backup_dir}[/dim]")

    # Show grand total if multiple variants
    if len(variants_to_show) > 1 and total_backups > 0:
        console.print()
        console.print("─" * 70)
        console.print(
            f"[bold]Grand Total: {total_backups} backup{'s' if total_backups != 1 else ''} "
            f"across all variants[/bold] — {service._format_size(total_size)}"
        )

    console.print()
