"""Precondition check system for CLI commands.

This module provides a decorator-based precondition system that makes it
structurally hard to forget preconditions or bypass them. Commands use
the @require_preconditions decorator to enforce checks before execution.

Example:
    @require_preconditions(
        database_exists,
        database_valid,
        unity_project_exists,
    )
    def export_command(ctx: typer.Context):
        # Command logic here
        # Checks run automatically before this executes
        pass
"""

from .base import PreconditionCheck, PreconditionResult
from .decorator import require_preconditions

__all__ = [
    "PreconditionCheck",
    "PreconditionResult",
    "require_preconditions",
]
