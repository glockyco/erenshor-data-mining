"""Decorator for enforcing precondition checks on CLI commands.

This module provides the @require_preconditions decorator that makes it
structurally hard to forget or bypass precondition checks. The decorator
runs all specified checks before command execution and fails fast with
clear error messages if any check fails.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from rich.console import Console

from erenshor.cli.context import CLIContext

from .base import PreconditionCheck, PreconditionResult


def require_preconditions(*checks: PreconditionCheck) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to enforce precondition checks on command functions.

    This decorator provides structural enforcement of preconditions:
    - Can't forget checks (visible at function definition)
    - Can't bypass checks (run before function body)
    - Minimal boilerplate (one line per command)
    - Clear error messages with actionable hints

    The decorator automatically extracts context from Typer's CLIContext
    and builds a simple dict for check functions. All checks are run
    before the command executes, and if any fail, the command is aborted
    with a clear error message.

    Usage:
        @require_preconditions(
            database_exists,
            database_valid,
            database_has_items
        )
        def deploy_command(ctx: typer.Context):
            # Command logic here
            # Checks run automatically before this executes
            pass

    Args:
        *checks: Variable number of check functions. Each check receives
            a context dict and returns a PreconditionResult.

    Returns:
        Decorated function that enforces precondition checks.

    Example:
        from erenshor.cli.preconditions import require_preconditions
        from erenshor.cli.preconditions.checks.database import (
            database_exists,
            database_valid,
        )

        @require_preconditions(database_exists, database_valid)
        def export_command(ctx: typer.Context):
            cli_ctx: CLIContext = ctx.obj
            # No manual precondition checking needed
            # Command logic here
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            console = Console()

            # Extract CLIContext from first argument (Typer passes it as ctx)
            # Note: Typer passes ctx in kwargs (not args) and uses click.core.Context at runtime
            ctx = args[0] if args else kwargs.get("ctx")

            # Fail fast if context is missing or invalid
            if not ctx or not hasattr(ctx, "obj"):
                raise RuntimeError("Command missing ctx parameter - preconditions require ctx: typer.Context")

            if not isinstance(ctx.obj, CLIContext):
                raise RuntimeError(f"Invalid context object type: {type(ctx.obj)} - expected CLIContext")

            # Build context for precondition checks
            cli_ctx: CLIContext = ctx.obj
            context = _build_check_context(cli_ctx)

            # Run all precondition checks
            results: list[PreconditionResult] = []
            for check in checks:
                try:
                    result = check(context)
                    results.append(result)
                except Exception as e:
                    # If check raises exception, treat as failure
                    results.append(
                        PreconditionResult(
                            passed=False,
                            check_name=check.__name__,
                            message=f"Check failed with exception: {type(e).__name__}",
                            detail=str(e),
                        )
                    )

            # Check if all passed
            all_passed = all(r.passed for r in results)

            if not all_passed:
                # Show failure with Rich formatting
                console.print("\n[bold red]Precondition checks failed:[/bold red]\n")
                for result in results:
                    if result.passed:
                        console.print(f"  [green]{result}[/green]")
                    else:
                        console.print(f"  [red]{result}[/red]")

                console.print("\n[yellow]Abort: Fix issues before running command[/yellow]\n")
                raise typer.Exit(1)

            # All checks passed - run command
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _build_check_context(cli_ctx: CLIContext) -> dict[str, Any]:
    """Build context dict for check functions from CLIContext.

    Extracts relevant information from CLIContext and variant config
    to build a simple dict that check functions can use.

    Args:
        cli_ctx: CLI context containing config, variant, repo_root.

    Returns:
        Context dict with resolved paths and configuration.
    """
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    return {
        "variant": cli_ctx.variant,
        "repo_root": cli_ctx.repo_root,
        "database_path": variant_config.resolved_database(cli_ctx.repo_root),
        "unity_project": variant_config.resolved_unity_project(cli_ctx.repo_root),
        "game_dir": variant_config.resolved_game_files(cli_ctx.repo_root),
        "logs_dir": variant_config.resolved_logs(cli_ctx.repo_root),
        "backups_dir": variant_config.resolved_backups(cli_ctx.repo_root),
        "config": cli_ctx.config,
        "dry_run": cli_ctx.dry_run,
    }
