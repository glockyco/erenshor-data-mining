"""Main CLI entry point for Erenshor data mining tool.

This module provides the Typer CLI application with global options,
configuration loading, logging setup, and error handling.
"""

from __future__ import annotations

import sys

import typer
from loguru import logger

from erenshor import __version__
from erenshor.infrastructure.config import ConfigLoadError, get_repo_root, load_config
from erenshor.infrastructure.logging import setup_logging
from erenshor.infrastructure.logging.setup import LoggingSetupError

from .commands import extract, maps, sheets, wiki
from .context import CLIContext

# Create Typer app instance
app = typer.Typer(
    name="erenshor",
    help="Erenshor data mining and wiki management tool",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register command groups
app.add_typer(extract.app, name="extract")
app.add_typer(wiki.app, name="wiki")
app.add_typer(sheets.app, name="sheets")
app.add_typer(maps.app, name="maps")


@app.callback()
def main(
    ctx: typer.Context,
    variant: str = typer.Option(
        "main",
        "--variant",
        "-V",
        help="Game variant to operate on (main, playtest, demo)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output (DEBUG level)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-error output (ERROR level only)",
    ),
) -> None:
    """Erenshor data mining and wiki management tool.

    This tool extracts game data from Erenshor Unity projects, exports
    to SQLite databases, and deploys to MediaWiki and Google Sheets.

    Global options can be used with any command to control behavior,
    logging verbosity, and variant selection.
    """
    try:
        # Load configuration first
        config = load_config()
        repo_root = get_repo_root()

        # Override log level based on verbose/quiet flags
        if verbose and quiet:
            typer.echo("Error: Cannot use both --verbose and --quiet", err=True)
            raise typer.Exit(1)

        if verbose:
            config.global_.logging.level = "debug"
        elif quiet:
            config.global_.logging.level = "error"

        # Setup logging (variant-specific if specified, global otherwise)
        # Only use variant-specific logging if the variant exists
        variant_for_logging = variant if variant in config.variants else None
        setup_logging(config, variant=variant_for_logging)

        # Create CLI context
        ctx.obj = CLIContext(
            config=config,
            variant=variant,
            dry_run=dry_run,
            repo_root=repo_root,
        )

        # Log CLI invocation
        if dry_run:
            logger.info("DRY RUN mode enabled - no changes will be made")

        logger.debug(f"CLI initialized: variant={variant}, dry_run={dry_run}")

    except ConfigLoadError as e:
        typer.echo(f"Configuration Error: {e}", err=True)
        raise typer.Exit(1) from None
    except LoggingSetupError as e:
        typer.echo(f"Logging Setup Error: {e}", err=True)
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(f"Unexpected error during initialization: {e}", err=True)
        if "--verbose" in sys.argv or "-v" in sys.argv:
            raise
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"erenshor version {__version__}")


@app.command()
def status(
    ctx: typer.Context,
    all_variants: bool = typer.Option(
        False,
        "--all-variants",
        help="Show status for all variants",
    ),
) -> None:
    """Show system status.

    Displays current system status including database state,
    last export time, configuration, and health checks.
    Can show status for all variants or just the selected one.
    """
    typer.echo("Not yet implemented: status")


@app.command()
def doctor(
    ctx: typer.Context,
) -> None:
    """Run system health check.

    Performs comprehensive system health checks including:
    - Unity installation and version
    - Database connectivity and schema validation
    - Configuration file validity
    - Required tools availability (SteamCMD, AssetRipper)
    - Credential validation
    """
    typer.echo("Not yet implemented: doctor")


# Config command group
config_app = typer.Typer(
    name="config",
    help="View and manage configuration",
    no_args_is_help=True,
)


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    key: str = typer.Argument(
        None,
        help="Specific config key to show (e.g., 'unity.path')",
    ),
) -> None:
    """Show configuration.

    Displays current configuration values. Can show all config
    or a specific key using dot notation (e.g., 'unity.path').
    """
    if key:
        typer.echo(f"Not yet implemented: config show (key: {key})")
    else:
        typer.echo("Not yet implemented: config show")


app.add_typer(config_app, name="config")


# Backup command group
backup_app = typer.Typer(
    name="backup",
    help="Manage database backups",
    no_args_is_help=True,
)


@backup_app.command("info")
def backup_info(
    ctx: typer.Context,
) -> None:
    """Show backup information.

    Displays information about database backups including
    last backup time, backup location, and backup history.
    """
    typer.echo("Not yet implemented: backup info")


app.add_typer(backup_app, name="backup")


# Test command group
test_app = typer.Typer(
    name="test",
    help="Run tests and validation",
    no_args_is_help=True,
)


@test_app.callback(invoke_without_command=True)
def test_callback(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run all tests.

    Executes the complete test suite including unit and
    integration tests. Optionally generates coverage report.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Not yet implemented: test")


@test_app.command("unit")
def test_unit(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run unit tests only.

    Executes only unit tests (fast, no external dependencies).
    Optionally generates coverage report.
    """
    typer.echo("Not yet implemented: test unit")


@test_app.command("integration")
def test_integration(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run integration tests only.

    Executes only integration tests (slower, requires database
    and external services). Optionally generates coverage report.
    """
    typer.echo("Not yet implemented: test integration")


app.add_typer(test_app, name="test")


# Docs command group
docs_app = typer.Typer(
    name="docs",
    help="Generate documentation",
    no_args_is_help=True,
)


@docs_app.command("generate")
def docs_generate(
    ctx: typer.Context,
    format: str = typer.Option(
        "markdown",
        "--format",
        help="Output format (markdown, html, etc.)",
    ),
) -> None:
    """Generate documentation.

    Generates documentation from source code, database schema,
    and configuration. Supports multiple output formats.
    """
    typer.echo(f"Not yet implemented: docs generate (format: {format})")


app.add_typer(docs_app, name="docs")


def cli_main() -> None:
    """Main entry point with global exception handling.

    This wrapper catches any unhandled exceptions and displays
    user-friendly error messages before exiting.
    """
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\n\nInterrupted by user", err=True)
        raise typer.Exit(130) from None  # Standard SIGINT exit code
    except Exception as e:
        logger.exception("Unhandled exception in CLI")
        typer.echo(f"\nFatal error: {e}", err=True)
        typer.echo("\nRun with --verbose for detailed error information", err=True)
        raise typer.Exit(1) from None


if __name__ == "__main__":
    cli_main()
