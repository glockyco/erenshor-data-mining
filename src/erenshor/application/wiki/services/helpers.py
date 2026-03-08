"""Shared helper functions for wiki services.

This module contains common functionality used across WikiFetchService,
WikiGenerateService, and WikiDeployService to avoid duplication.
"""

from rich.console import Console


def display_operation_summary(
    console: Console,
    operation: str,
    total: int,
    succeeded: int,
    failed: int,
    skipped: int,
    warnings: list[str],
    errors: list[str],
    dry_run: bool,
) -> None:
    """Display operation summary.

    Args:
        console: Rich console for output.
        operation: Name of the operation (e.g., "Fetch", "Generate", "Deploy").
        total: Total number of pages processed.
        succeeded: Number of successful operations.
        failed: Number of failed operations.
        skipped: Number of skipped operations.
        warnings: List of warning messages.
        errors: List of error messages.
        dry_run: Whether this was a dry run.
    """
    console.print()
    console.print(f"[bold]{operation} Summary:[/bold]")
    console.print(f"  Total pages:   {total}")
    console.print(f"  Succeeded:     {succeeded}")

    if failed > 0:
        console.print(f"  [red]Failed:        {failed}[/red]")

    if skipped > 0:
        console.print(f"  Skipped:       {skipped}")

    if warnings:
        console.print(f"  [yellow]Warnings:      {len(warnings)}[/yellow]")

    if dry_run:
        console.print("  [dim](Dry run - no changes made)[/dim]")

    console.print()
