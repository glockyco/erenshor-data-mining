"""Erenshor Wiki CLI - Main command registration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from erenshor.cli.commands import (
    audit,
    fetch,
    upload,
    validation,
)

__all__ = ["get_registry"]

logger = logging.getLogger(__name__)

app = typer.Typer(help="Erenshor Wiki CLI")

app.add_typer(fetch.app, name="", no_args_is_help=False)
app.add_typer(audit.app, name="", no_args_is_help=False)
app.add_typer(upload.app, name="", no_args_is_help=False)
app.add_typer(validation.app, name="", no_args_is_help=False)


def get_registry(engine: Any) -> Any:
    """Initialize or load central registry with automatic cleanup."""
    from erenshor.infrastructure.config.settings import load_settings
    from erenshor.registry.core import WikiRegistry
    from erenshor.registry.migration import MappingImporter, RegistryBuilder

    console = Console()
    settings = load_settings()

    # Use central registry location
    registry_dir = Path("registry")
    registry = WikiRegistry(registry_dir)
    mapping_file = Path("mapping.json")

    if not registry.registry_file.exists():
        # First run - build from scratch
        console.print("[yellow]Building registry from database...[/yellow]")

        # Import manual mappings
        importer = MappingImporter()
        mapping_rules = importer.import_manual_mappings(mapping_file, registry)

        # Build from database
        builder = RegistryBuilder()
        builder.build_from_db(engine, registry, mapping_rules)

        registry.save()
        console.print(
            f"[green]Registry created with {len(registry.pages)} pages[/green]"
        )
    else:
        registry.load()

        # Check if mapping.json has been updated since registry was saved
        if mapping_file.exists():
            mapping_mtime = mapping_file.stat().st_mtime
            registry_mtime = registry.registry_file.stat().st_mtime

            if mapping_mtime > registry_mtime:
                console.print(
                    "[yellow]Mapping file is newer than registry, rebuilding...[/yellow]"
                )

                # Snapshot existing files before rebuild
                orphaned_files = _snapshot_updated_files(settings.output_dir, registry)

                # Rebuild registry
                importer = MappingImporter()
                mapping_rules = importer.import_manual_mappings(mapping_file, registry)

                builder = RegistryBuilder()
                builder.build_from_db(engine, registry, mapping_rules)

                # Clean up orphaned files after rebuild
                cleanup_count = _cleanup_orphaned_files(
                    settings.output_dir, registry, orphaned_files, console
                )

                registry.save()

                if cleanup_count > 0:
                    console.print(
                        f"[green]Registry rebuilt with {len(registry.pages)} pages "
                        f"(cleaned up {cleanup_count} orphaned file(s))[/green]"
                    )
                else:
                    console.print(
                        f"[green]Registry rebuilt with {len(registry.pages)} pages[/green]"
                    )
            else:
                console.print(f"Registry loaded with {len(registry.pages)} pages")
        else:
            console.print(f"Registry loaded with {len(registry.pages)} pages")

    return registry


def _snapshot_updated_files(output_dir: Path, old_registry: Any) -> set[Path]:
    """Snapshot files that currently exist in wiki_updated/.

    Args:
        output_dir: Path to wiki_updated directory
        old_registry: Current registry before rebuild

    Returns:
        Set of Path objects for all .txt files that currently exist
    """
    if not output_dir.exists():
        return set()

    # Get all .txt files in the output directory
    return set(output_dir.glob("*.txt"))


def _get_expected_filenames(output_dir: Path, registry: Any) -> set[Path]:
    """Get set of expected filenames based on registry.

    Args:
        output_dir: Path to wiki_updated directory
        registry: Registry with current page mappings

    Returns:
        Set of Path objects for files that should exist based on registry
    """
    expected = set()

    for page in registry.pages.values():
        # Get the path that would be used for this page
        page_path = output_dir / page.safe_filename
        expected.add(page_path)

    return expected


def _cleanup_orphaned_files(
    output_dir: Path,
    new_registry: Any,
    old_files: set[Path],
    console: Console,
) -> int:
    """Clean up orphaned files after registry rebuild.

    Args:
        output_dir: Path to wiki_updated directory
        new_registry: Registry after rebuild
        old_files: Set of files that existed before rebuild
        console: Rich console for output

    Returns:
        Number of files successfully cleaned up
    """
    if not old_files:
        return 0

    # Get expected filenames from new registry
    expected_files = _get_expected_filenames(output_dir, new_registry)

    # Find orphans: files that existed before but are no longer expected
    orphaned = old_files - expected_files

    if not orphaned:
        return 0

    # Clean up orphaned files
    cleanup_count = 0
    for orphan_file in orphaned:
        try:
            orphan_file.unlink()
            console.print(f"[dim]  Removed orphaned file: {orphan_file.name}[/dim]")
            logger.info(f"Removed orphaned file: {orphan_file.name}")
            cleanup_count += 1
        except OSError as e:
            logger.warning(f"Could not delete {orphan_file.name}: {e}")
            console.print(
                f"[yellow]  Warning: Could not remove {orphan_file.name} (file in use?)[/yellow]"
            )

    return cleanup_count
