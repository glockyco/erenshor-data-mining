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
