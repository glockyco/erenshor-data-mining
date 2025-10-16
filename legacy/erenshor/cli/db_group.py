"""Database utilities CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from erenshor.application.services.junction_audit import audit_junction_coverage
from erenshor.infrastructure.config.settings import load_settings
from erenshor.infrastructure.database.repositories import get_engine

__all__ = ["app", "audit_junctions"]


app = typer.Typer(help="Database utilities")


@app.command("audit-junctions")
def audit_junctions(
    db: Path | None = typer.Option(None, help="Database path"),
) -> None:
    """Validate junction table coverage against registered metadata.

    This command detects junction tables in the database and compares them
    against the centrally registered junction metadata to identify any
    unregistered tables that might need to be added to the registry.

    Junction tables are typically:
    - 2-4 columns
    - At least 2 foreign key references (columns ending in Id/Guid)
    - Used to populate entity fields (e.g., ItemClasses -> DbItem.Classes)

    Exit codes:
        0: All junction tables are registered
        1: Some junction tables are missing from registry
    """
    console = Console()
    settings = load_settings()

    if db is not None:
        settings.db_path = db

    # Get database engine
    engine = get_engine(settings.db_path)

    # Run audit
    result = audit_junction_coverage(engine)

    # Display header
    console.print("\n[bold cyan]Junction Table Audit[/bold cyan]")
    console.print("=" * 40)
    console.print()

    # Summary counts
    console.print(f"Database Junction Tables: [bold]{len(result.db_tables)}[/bold]")
    console.print(
        f"Registered in Metadata:   [bold]{len(result.registered_tables)}[/bold]"
    )
    console.print()

    # Registered tables
    if result.registered:
        console.print(f"[green]✅ Registered ({len(result.registered)}):[/green]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Name", style="green")

        for name in sorted(result.registered):
            table.add_row(f"  - {name}")

        console.print(table)
        console.print()

    # Unregistered tables
    if result.missing:
        console.print(f"[yellow]⚠️  Unregistered ({len(result.missing)}):[/yellow]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Name", style="yellow")

        for name in sorted(result.missing):
            table.add_row(f"  - {name} (found in database, missing from registry)")

        console.print(table)
        console.print()

        # Exit with error code if missing tables
        console.print(
            "[yellow]Some junction tables are not registered in metadata.[/yellow]"
        )
        console.print(
            "[dim]Consider adding them to infrastructure/database/junction_metadata.py[/dim]"
        )
        raise typer.Exit(code=1)
    else:
        console.print("[green]✅ All junction tables are registered![/green]")
        console.print()
