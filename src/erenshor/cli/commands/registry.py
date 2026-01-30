"""Registry management commands.

Provides commands for managing the entity registry database including conflict
detection, rebuild operations, and health status reporting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, create_engine

from erenshor.registry.operations import (
    count_entities_by_type,
    find_conflicts,
    initialize_registry,
    load_mapping_json,
    populate_all_entities,
    validate_conflicts,
)

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

__all__ = ["app"]

app = typer.Typer(
    name="registry",
    help="Manage entity registry database",
    no_args_is_help=True,
)
console = Console()


@app.command("conflicts")
def conflicts(ctx: typer.Context) -> None:
    """Show display_name conflicts in registry.

    Lists all entities that share the same display name within an entity type.
    Shows which conflicts are resolved (all entities have mapping.json entries)
    vs unresolved (some entities lack mappings).

    Example:
        erenshor registry conflicts
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    mapping_json_path = cli_ctx.repo_root / "mapping.json"

    # Check registry exists
    if not registry_db_path.exists():
        console.print(f"[red]Error: Registry database not found: {registry_db_path}[/red]")
        console.print("Run [cyan]erenshor registry rebuild[/cyan] to create it")
        raise typer.Exit(1)

    # Load conflicts
    engine = create_engine(f"sqlite:///{registry_db_path}")
    with Session(engine) as session:
        all_conflicts = find_conflicts(session)
        resolved, unresolved = validate_conflicts(session, mapping_json_path)

    # Print header
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Registry Conflicts: {cli_ctx.variant} variant[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Summary
    console.print("[bold]Summary:[/bold]")
    if not all_conflicts:
        console.print("  [green]No conflicts found - all entities have unique display names[/green]")
        console.print()
        return

    console.print(f"  Total conflicts: {len(all_conflicts)}")
    resolved_pct = len(resolved) / len(all_conflicts) * 100 if all_conflicts else 0
    console.print(f"  [green]✅ Resolved: {len(resolved)} ({resolved_pct:.0f}%)[/green]")
    unresolved_pct = len(unresolved) / len(all_conflicts) * 100 if all_conflicts else 0
    console.print(f"  [red]❌ Unresolved: {len(unresolved)} ({unresolved_pct:.0f}%)[/red]")
    console.print()

    # By entity type
    console.print("[bold]By entity type:[/bold]")
    type_stats = {}
    for _display_name, entities in all_conflicts:
        entity_type = entities[0].entity_type
        if entity_type not in type_stats:
            type_stats[entity_type] = {"total": 0, "resolved": 0, "unresolved": 0}
        type_stats[entity_type]["total"] += 1

    for _display_name, entities in resolved:
        entity_type = entities[0].entity_type
        type_stats[entity_type]["resolved"] += 1

    for _display_name, entities, _unmapped in unresolved:
        entity_type = entities[0].entity_type
        type_stats[entity_type]["unresolved"] += 1

    for entity_type, stats in sorted(type_stats.items(), key=lambda x: x[0].value):
        console.print(
            f"  {entity_type.value}: {stats['total']} conflicts "
            f"([green]{stats['resolved']} resolved[/green], "
            f"[red]{stats['unresolved']} unresolved[/red])"
        )
    console.print()

    # List all conflicts
    if unresolved:
        console.print("[bold]Unresolved conflicts:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Display Name", style="cyan")
        table.add_column("Type")
        table.add_column("Total", justify="right")
        table.add_column("Unmapped", justify="right")

        sorted_unresolved = sorted(unresolved, key=lambda x: len(x[2]), reverse=True)
        for display_name, all_ents, unmapped in sorted_unresolved:
            entity_type = all_ents[0].entity_type
            table.add_row(
                display_name,
                entity_type.value,
                str(len(all_ents)),
                f"[red]{len(unmapped)}[/red]",
            )

        console.print(table)
        console.print()
        console.print("[dim]Add explicit mapping.json entries for all entities in each conflict[/dim]")

    console.print()

    # Exit code
    if unresolved:
        raise typer.Exit(1)


@app.command("rebuild")
def rebuild(ctx: typer.Context) -> None:
    """Delete and rebuild registry database.

    Performs a complete registry rebuild:
    1. Deletes existing registry.db
    2. Creates new database with schema
    3. Populates all entities from game database
    4. Applies mapping.json overrides
    5. Validates conflicts

    This is an idempotent operation - safe to run multiple times.

    Example:
        erenshor registry rebuild
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    game_db_path = variant_config.resolved_database(cli_ctx.repo_root)
    mapping_json_path = cli_ctx.repo_root / "mapping.json"

    # Check game database exists
    if not game_db_path.exists():
        console.print(f"[red]Error: Game database not found: {game_db_path}[/red]")
        console.print("Run [cyan]erenshor extract export[/cyan] first")
        raise typer.Exit(1)

    console.print()
    console.print(f"[bold]Rebuilding registry for {cli_ctx.variant} variant...[/bold]")
    console.print()

    # Delete existing registry
    if registry_db_path.exists():
        registry_db_path.unlink()
        console.print("  [green]✓[/green] Deleted existing registry")

    # Create new database
    initialize_registry(registry_db_path)
    console.print("  [green]✓[/green] Created new database")

    # Populate entities
    engine = create_engine(f"sqlite:///{registry_db_path}")
    with Session(engine) as session:
        entity_count = populate_all_entities(session, game_db_path)
        console.print(f"  [green]✓[/green] Populated {entity_count} entities")

        # Show counts by type
        counts = count_entities_by_type(session)
        for entity_type, count in sorted(counts.items(), key=lambda x: x[0].value):
            if count > 0:
                console.print(f"    - {entity_type.value}: {count}")

        # Load mapping.json
        mapping_count = load_mapping_json(session, mapping_json_path)
        console.print(f"  [green]✓[/green] Loaded mapping.json ({mapping_count} rules)")

        # Check conflicts
        conflicts = find_conflicts(session)
        _resolved, unresolved = validate_conflicts(session, mapping_json_path)

        if not conflicts:
            console.print("  [green]✓[/green] No conflicts (all entities have unique names)")
        elif not unresolved:
            console.print(f"  [green]✓[/green] All {len(conflicts)} conflicts resolved")
        else:
            console.print(f"  [red]✗[/red] {len(unresolved)} unresolved conflicts (of {len(conflicts)} total)")

    console.print()
    console.print("[green]Registry rebuilt successfully![/green]")
    console.print()

    # Exit code based on conflicts
    if unresolved:
        console.print("[yellow]Run [cyan]erenshor registry conflicts[/cyan] to see details[/yellow]")
        console.print()
        raise typer.Exit(1)


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Show registry health status.

    Displays:
    - Database file info (path, size, last modified)
    - Entity counts by type
    - Conflict summary

    Example:
        erenshor registry status
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    mapping_json_path = cli_ctx.repo_root / "mapping.json"

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Registry Status: {cli_ctx.variant} variant[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Check registry exists
    if not registry_db_path.exists():
        console.print("[red]✗ Registry database not found[/red]")
        console.print(f"  Path: {registry_db_path}")
        console.print()
        console.print("[yellow]Run [cyan]erenshor registry rebuild[/cyan] to create it[/yellow]")
        console.print()
        raise typer.Exit(1)

    # Database info
    console.print("[bold]Database:[/bold]")
    stat = registry_db_path.stat()
    console.print(f"  Path: {registry_db_path}")
    console.print(f"  Size: {stat.st_size / 1024:.1f} KB")
    from datetime import datetime

    mod_time = datetime.fromtimestamp(stat.st_mtime)
    console.print(f"  Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()

    # Load data
    engine = create_engine(f"sqlite:///{registry_db_path}")
    with Session(engine) as session:
        counts = count_entities_by_type(session)
        conflicts = find_conflicts(session)
        resolved, unresolved = validate_conflicts(session, mapping_json_path)

    # Entity counts
    console.print("[bold]Entity Counts:[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Type")
    table.add_column("Count", justify="right")

    for entity_type, count in sorted(counts.items(), key=lambda x: x[0].value):
        if count > 0:
            table.add_row(entity_type.value, str(count))

    console.print(table)
    console.print()

    # Conflicts
    console.print("[bold]Conflicts:[/bold]")
    if not conflicts:
        console.print("  [green]✓ No conflicts[/green]")
    else:
        console.print(f"  Total: {len(conflicts)}")
        resolved_pct = len(resolved) / len(conflicts) * 100
        console.print(f"  [green]✅ Resolved: {len(resolved)} ({resolved_pct:.0f}%)[/green]")
        unresolved_pct = len(unresolved) / len(conflicts) * 100
        console.print(f"  [red]❌ Unresolved: {len(unresolved)} ({unresolved_pct:.0f}%)[/red]")
    console.print()

    # Health
    console.print("[bold]Health:[/bold]")
    if not conflicts:
        console.print("  [green]✓ HEALTHY[/green]")
        console.print("  All entities have unique display names")
    elif not unresolved:
        console.print("  [green]✓ HEALTHY[/green]")
        console.print("  All conflicts are resolved via mapping.json")
    else:
        console.print("  [red]✗ ERRORS[/red]")
        console.print(f"  {len(unresolved)} unresolved conflicts block wiki operations")
        console.print()
        console.print("[bold]Recommendations:[/bold]")
        console.print("  - Run [cyan]erenshor registry conflicts[/cyan] to see conflict details")
        console.print("  - Add mapping.json entries for all conflicting entities")
        console.print("  - Run [cyan]erenshor registry rebuild[/cyan] after fixing")

    console.print()

    # Exit code
    if unresolved:
        raise typer.Exit(1)
