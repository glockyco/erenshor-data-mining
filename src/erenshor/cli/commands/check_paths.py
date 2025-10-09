"""Check paths command - diagnostic tool for path resolution."""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.table import Table

from erenshor.infrastructure.config.paths import get_path_resolver

__all__ = ["check_paths"]


def check_paths() -> None:
    """Display current path configuration and check which paths exist.

    Useful for debugging path issues and verifying environment variable overrides.
    Shows project root, mode, all resolved paths, and which paths exist on disk.
    """
    console = Console()
    resolver = get_path_resolver()

    # Header
    console.print("\n[bold cyan]Path Configuration[/bold cyan]\n")

    # Basic info
    console.print(f"[bold]Project Root:[/bold] {resolver.root}")
    console.print(f"[bold]Mode:[/bold] {resolver.mode}")
    console.print()

    # Environment variables table
    env_table = Table(title="Environment Variables", show_header=True)
    env_table.add_column("Variable", style="cyan")
    env_table.add_column("Value", style="yellow")
    env_table.add_column("Set?", style="green")

    env_vars = [
        "ERENSHOR_PROJECT_ROOT",
        "ERENSHOR_DB_PATH",
        "ERENSHOR_MAPPING_FILE",
        "ERENSHOR_ENV_FILE",
        "ERENSHOR_REGISTRY_DIR",
        "ERENSHOR_WIKI_CACHE_DIR",
        "ERENSHOR_WIKI_UPDATED_DIR",
        "ERENSHOR_OUT_REPORTS_DIR",
        "ERENSHOR_LOG_LEVEL",
    ]

    for var in env_vars:
        value = os.environ.get(var)
        is_set = "✓" if value else "✗"
        display_value = value if value else "[dim]not set[/dim]"
        env_table.add_row(var, display_value, is_set)

    console.print(env_table)
    console.print()

    # Paths table
    paths_table = Table(title="Resolved Paths", show_header=True)
    paths_table.add_column("Path Type", style="cyan")
    paths_table.add_column("Location", style="yellow")
    paths_table.add_column("Exists?", style="green")

    path_checks: list[tuple[str, Path]] = [
        ("Project Root", resolver.root),
        ("Database", resolver.db_path),
        ("Mapping File", resolver.mapping_file),
        (".env File", resolver.env_file),
        ("Registry Directory", resolver.registry_dir),
        ("Wiki Cache Directory", resolver.cache_dir),
        ("Wiki Output Directory", resolver.output_dir),
        ("Reports Directory", resolver.reports_dir),
        ("Zones Config", resolver.zones_json),
    ]

    # Add package_dir only in development mode
    if resolver.is_development():
        path_checks.insert(1, ("Package Directory", resolver.package_dir))

    for name, path in path_checks:
        exists = path.exists()
        exists_str = "[green]✓[/green]" if exists else "[red]✗[/red]"
        paths_table.add_row(name, str(path), exists_str)

    console.print(paths_table)
    console.print()

    # Summary
    existing_paths = sum(1 for _, path in path_checks if path.exists())
    total_paths = len(path_checks)

    if existing_paths == total_paths:
        console.print(
            f"[bold green]✓ All paths exist ({existing_paths}/{total_paths})[/bold green]"
        )
    else:
        console.print(
            f"[bold yellow]⚠ Some paths missing ({existing_paths}/{total_paths} exist)[/bold yellow]"
        )
        console.print(
            "[dim]Missing paths will be created automatically when needed.[/dim]"
        )

    console.print()
