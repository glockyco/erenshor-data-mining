"""Main CLI entry point for Erenshor data mining tool.

This module provides the Typer CLI application with global options,
configuration loading, logging setup, and error handling.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from typing import Any

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from erenshor import __version__
from erenshor.infrastructure.config import ConfigLoadError, get_repo_root, load_config
from erenshor.infrastructure.logging import setup_logging
from erenshor.infrastructure.logging.setup import LoggingSetupError

from .commands import extract, maps, sheets, wiki
from .context import CLIContext

console = Console()

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
def status(  # noqa: PLR0915 (too many statements)
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
    cli_ctx: CLIContext = ctx.obj

    # Determine which variants to show
    variants_to_show = list(cli_ctx.config.variants.keys()) if all_variants else [cli_ctx.variant]

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Erenshor Data Mining Pipeline Status[/bold cyan]\nVersion: {__version__}",
            border_style="cyan",
        )
    )
    console.print()

    # Configuration section
    console.print("[bold yellow]Configuration:[/bold yellow]")
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("Key", style="cyan")
    config_table.add_column("Value")

    config_table.add_row("Config file", str(cli_ctx.repo_root / "config.toml"))
    local_config = cli_ctx.config.global_.paths.resolved_config_local(cli_ctx.repo_root)
    if local_config.exists():
        config_table.add_row("Local config", f"{local_config} [green](exists)[/green]")
    else:
        config_table.add_row("Local config", f"{local_config} [dim](not found)[/dim]")

    config_table.add_row("Log directory", str(cli_ctx.config.global_.paths.resolved_logs(cli_ctx.repo_root)))
    config_table.add_row("Log level", cli_ctx.config.global_.logging.level)
    config_table.add_row("Default variant", cli_ctx.config.default_variant)

    console.print(config_table)
    console.print()

    # Variants section
    for variant_name in variants_to_show:
        if variant_name not in cli_ctx.config.variants:
            console.print(f"[red]Error: Variant '{variant_name}' not found in config[/red]")
            continue

        variant_config = cli_ctx.config.variants[variant_name]
        is_current = variant_name == cli_ctx.variant

        # Variant header
        header_style = "bold green" if is_current else "bold white"
        marker = " [cyan](current)[/cyan]" if is_current else ""
        console.print(f"[{header_style}]Variant: {variant_name}{marker}[/{header_style}]")

        variant_table = Table(show_header=False, box=None, padding=(0, 2))
        variant_table.add_column("Key", style="cyan")
        variant_table.add_column("Value")

        variant_table.add_row("Name", variant_config.name)
        variant_table.add_row("Description", variant_config.description)
        variant_table.add_row("App ID", variant_config.app_id)
        variant_table.add_row("Enabled", "[green]Yes[/green]" if variant_config.enabled else "[red]No[/red]")

        # Database info
        db_path = variant_config.resolved_database(cli_ctx.repo_root)
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            variant_table.add_row(
                "Database",
                f"{db_path}\n[green]Size: {size_mb:.2f} MB[/green]",
            )
        else:
            variant_table.add_row("Database", f"{db_path}\n[dim](not found)[/dim]")

        # Paths
        unity_path = variant_config.resolved_unity_project(cli_ctx.repo_root)
        unity_status = "[green](exists)[/green]" if unity_path.exists() else "[dim](not found)[/dim]"
        variant_table.add_row("Unity project", f"{unity_path} {unity_status}")

        game_files_path = variant_config.resolved_game_files(cli_ctx.repo_root)
        game_status = "[green](exists)[/green]" if game_files_path.exists() else "[dim](not found)[/dim]"
        variant_table.add_row("Game files", f"{game_files_path} {game_status}")

        logs_path = variant_config.resolved_logs(cli_ctx.repo_root)
        logs_status = "[green](exists)[/green]" if logs_path.exists() else "[dim](not found)[/dim]"
        variant_table.add_row("Logs", f"{logs_path} {logs_status}")

        backups_path = variant_config.resolved_backups(cli_ctx.repo_root)
        backups_status = "[green](exists)[/green]" if backups_path.exists() else "[dim](not found)[/dim]"
        variant_table.add_row("Backups", f"{backups_path} {backups_status}")

        console.print(variant_table)
        console.print()

    # Tools section
    console.print("[bold yellow]Tools:[/bold yellow]")
    tools_table = Table(show_header=False, box=None, padding=(0, 2))
    tools_table.add_column("Tool", style="cyan")
    tools_table.add_column("Status")

    unity_path = cli_ctx.config.global_.unity.resolved_path(cli_ctx.repo_root, validate=False)
    unity_status = "[green]Found[/green]" if unity_path.exists() else "[red]Not found[/red]"
    tools_table.add_row("Unity", f"{unity_path}\n{unity_status}")

    assetripper_path = cli_ctx.config.global_.assetripper.resolved_path(cli_ctx.repo_root, validate=False)
    assetripper_status = "[green]Found[/green]" if assetripper_path.exists() else "[red]Not found[/red]"
    tools_table.add_row("AssetRipper", f"{assetripper_path}\n{assetripper_status}")

    console.print(tools_table)
    console.print()


@app.command()
def doctor(  # noqa: PLR0915 (too many statements)
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
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]System Health Check[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    all_checks_passed = True

    # Check 1: Configuration files
    console.print("[bold]Configuration Files:[/bold]")
    config_file = cli_ctx.repo_root / "config.toml"
    if config_file.exists():
        console.print("  [green]\u2713[/green] config.toml exists")
    else:
        console.print("  [red]\u2717[/red] config.toml not found")
        all_checks_passed = False

    local_config = cli_ctx.config.global_.paths.resolved_config_local(cli_ctx.repo_root)
    if local_config.exists():
        console.print(f"  [green]\u2713[/green] config.local.toml exists at {local_config}")
    else:
        console.print("  [dim]\u2022[/dim] config.local.toml not found (optional)")

    console.print()

    # Check 2: Log directories
    console.print("[bold]Log Directories:[/bold]")
    global_logs = cli_ctx.config.global_.paths.resolved_logs(cli_ctx.repo_root)
    if global_logs.exists():
        if global_logs.is_dir():
            console.print(f"  [green]\u2713[/green] Global logs directory exists at {global_logs}")
        else:
            console.print(f"  [red]\u2717[/red] Global logs path exists but is not a directory: {global_logs}")
            all_checks_passed = False
    else:
        # Try to create it
        try:
            global_logs.mkdir(parents=True, exist_ok=True)
            console.print(f"  [green]\u2713[/green] Created global logs directory at {global_logs}")
        except Exception as e:
            console.print(f"  [red]\u2717[/red] Cannot create global logs directory: {e}")
            all_checks_passed = False

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    variant_logs = variant_config.resolved_logs(cli_ctx.repo_root)
    if variant_logs.exists():
        if variant_logs.is_dir():
            console.print(f"  [green]\u2713[/green] Variant logs directory exists at {variant_logs}")
        else:
            console.print(f"  [red]\u2717[/red] Variant logs path exists but is not a directory: {variant_logs}")
            all_checks_passed = False
    else:
        console.print(
            f"  [yellow]\u26a0[/yellow] Variant logs directory not found (will be created when needed): {variant_logs}"
        )

    console.print()

    # Check 3: Unity installation
    console.print("[bold]Unity Installation:[/bold]")
    unity_path = cli_ctx.config.global_.unity.resolved_path(cli_ctx.repo_root, validate=False)
    if unity_path.exists():
        console.print(f"  [green]\u2713[/green] Unity found at {unity_path}")
        console.print(f"  [dim]  Version: {cli_ctx.config.global_.unity.version}[/dim]")
    else:
        console.print(f"  [red]\u2717[/red] Unity not found at {unity_path}")
        console.print(f"  [dim]  Expected version: {cli_ctx.config.global_.unity.version}[/dim]")
        all_checks_passed = False

    console.print()

    # Check 4: AssetRipper
    console.print("[bold]AssetRipper:[/bold]")
    assetripper_path = cli_ctx.config.global_.assetripper.resolved_path(cli_ctx.repo_root, validate=False)
    if assetripper_path.exists():
        console.print(f"  [green]\u2713[/green] AssetRipper found at {assetripper_path}")
    else:
        console.print(f"  [yellow]\u26a0[/yellow] AssetRipper not found at {assetripper_path}")
        console.print("  [dim]  AssetRipper is only needed for extracting Unity projects from game files[/dim]")

    console.print()

    # Check 5: Database
    console.print(f"[bold]Database (variant: {cli_ctx.variant}):[/bold]")
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    if db_path.exists():
        console.print(f"  [green]\u2713[/green] Database found at {db_path}")
        size_bytes = db_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        console.print(f"  [dim]  Size: {size_mb:.2f} MB[/dim]")
    else:
        console.print(f"  [yellow]\u26a0[/yellow] Database not found at {db_path}")
        console.print("  [dim]  Database will be created during export[/dim]")

    console.print()

    # Check 6: Google Sheets credentials
    console.print("[bold]Google Sheets Credentials:[/bold]")
    credentials_file = cli_ctx.config.global_.google_sheets.resolved_credentials_file(cli_ctx.repo_root, validate=False)
    if credentials_file.exists():
        console.print(f"  [green]\u2713[/green] Credentials file found at {credentials_file}")
    else:
        console.print(f"  [yellow]\u26a0[/yellow] Credentials file not found at {credentials_file}")
        console.print("  [dim]  Google Sheets credentials are only needed for sheets deployment[/dim]")

    console.print()

    # Summary
    if all_checks_passed:
        console.print(
            Panel(
                "[bold green]All critical checks passed![/bold green]\nYour system is ready to run the pipeline.",
                border_style="green",
            )
        )
        console.print()
    else:
        console.print(
            Panel(
                "[bold red]Some checks failed![/bold red]\nPlease fix the issues above before running the pipeline.",
                border_style="red",
            )
        )
        console.print()
        raise typer.Exit(1)


# Config command group
config_app = typer.Typer(
    name="config",
    help="View and manage configuration",
    no_args_is_help=True,
)


def _get_nested_value(obj: Any, key: str) -> Any:
    """Get nested value from object using dot notation."""
    parts = key.split(".")
    current = obj
    for part in parts:
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise AttributeError(f"Key '{key}' not found in config")
    return current


def _format_config_tree(obj: Any, name: str = "config") -> Tree:
    """Format config object as a Rich tree."""
    tree = Tree(f"[bold cyan]{name}[/bold cyan]")

    if hasattr(obj, "model_dump"):
        # Pydantic model
        data = obj.model_dump()
        for key, value in data.items():
            _add_tree_node(tree, key, value)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            _add_tree_node(tree, key, value)
    else:
        tree.add(f"[yellow]{obj}[/yellow]")

    return tree


def _add_tree_node(tree: Tree, key: str, value: Any) -> None:
    """Add a node to the config tree."""
    if isinstance(value, dict):
        if value:  # Non-empty dict
            branch = tree.add(f"[bold]{key}[/bold]")
            for k, v in value.items():
                _add_tree_node(branch, k, v)
        else:
            tree.add(f"[bold]{key}[/bold]: [dim]{{}}[/dim]")
    elif isinstance(value, list):
        if value:
            branch = tree.add(f"[bold]{key}[/bold]")
            for i, item in enumerate(value):
                _add_tree_node(branch, f"[{i}]", item)
        else:
            tree.add(f"[bold]{key}[/bold]: [dim][][/dim]")
    elif value is None:
        tree.add(f"[bold]{key}[/bold]: [dim]null[/dim]")
    elif isinstance(value, bool):
        color = "green" if value else "red"
        tree.add(f"[bold]{key}[/bold]: [{color}]{value}[/{color}]")
    elif isinstance(value, int | float):
        tree.add(f"[bold]{key}[/bold]: [cyan]{value}[/cyan]")
    elif isinstance(value, str):
        # Highlight paths
        if "/" in value or "\\" in value or value.startswith("$"):
            tree.add(f"[bold]{key}[/bold]: [yellow]{value!r}[/yellow]")
        else:
            tree.add(f"[bold]{key}[/bold]: [green]{value!r}[/green]")
    else:
        tree.add(f"[bold]{key}[/bold]: {value}")


@config_app.command("show")
def config_show(  # noqa: PLR0915 (too many statements)
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
    cli_ctx: CLIContext = ctx.obj

    console.print()

    if key:
        # Show specific key
        try:
            # Try to get from global config first
            try:
                value = _get_nested_value(cli_ctx.config.global_, key)
                section = f"global.{key}"
            except AttributeError:
                # Try variants
                if key.startswith("variants."):
                    value = _get_nested_value(cli_ctx.config, key)
                    section = key
                else:
                    # Try top-level config
                    value = _get_nested_value(cli_ctx.config, key)
                    section = key

            console.print(f"[bold cyan]{section}:[/bold cyan]")
            console.print()

            # Format the value
            if hasattr(value, "model_dump") or isinstance(value, dict):
                tree = _format_config_tree(value, section)
                console.print(tree)
            elif isinstance(value, list | tuple):
                for item in value:
                    console.print(f"  - {item}")
            else:
                console.print(f"  [yellow]{value}[/yellow]")

            console.print()

        except AttributeError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print()
            console.print("[yellow]Available top-level keys:[/yellow]")
            console.print("  - version")
            console.print("  - default_variant")
            console.print("  - global.*")
            console.print("  - variants.*")
            console.print()
            raise typer.Exit(1) from None

    else:
        # Show all config
        console.print(
            Panel.fit(
                "[bold cyan]Configuration[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()

        # Basic info
        console.print(f"[bold]Version:[/bold] {cli_ctx.config.version}")
        console.print(f"[bold]Default Variant:[/bold] {cli_ctx.config.default_variant}")
        console.print()

        # Global config
        console.print("[bold yellow]Global Configuration:[/bold yellow]")
        global_tree = _format_config_tree(cli_ctx.config.global_, "global")
        console.print(global_tree)
        console.print()

        # Variants
        console.print("[bold yellow]Variants:[/bold yellow]")
        for variant_name, variant_config in cli_ctx.config.variants.items():
            variant_tree = _format_config_tree(variant_config, variant_name)
            console.print(variant_tree)
            console.print()

        # Show config file locations
        console.print("[bold yellow]Config Files:[/bold yellow]")
        config_table = Table(show_header=False, box=None, padding=(0, 2))
        config_table.add_column("File", style="cyan")
        config_table.add_column("Status")

        config_file = cli_ctx.repo_root / "config.toml"
        config_table.add_row("config.toml", f"{config_file} [green](exists)[/green]")

        local_config = cli_ctx.config.global_.paths.resolved_config_local(cli_ctx.repo_root)
        if local_config.exists():
            config_table.add_row("config.local.toml", f"{local_config} [green](exists)[/green]")
        else:
            config_table.add_row("config.local.toml", f"{local_config} [dim](not found)[/dim]")

        console.print(config_table)
        console.print()


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
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Database Backups (variant: {cli_ctx.variant})[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    backups_dir = variant_config.resolved_backups(cli_ctx.repo_root)

    # Check if backups directory exists
    if not backups_dir.exists():
        console.print(f"[yellow]No backups directory found at:[/yellow] {backups_dir}")
        console.print()
        console.print("[dim]The backups directory will be created when the first backup is made.[/dim]")
        console.print()
        return

    # List all backup files
    backup_files = sorted(
        backups_dir.glob("*.sqlite"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backup_files:
        console.print(f"[yellow]No backup files found in:[/yellow] {backups_dir}")
        console.print()
        console.print("[dim]Backups will appear here after running the backup command.[/dim]")
        console.print()
        return

    # Show backup directory
    console.print(f"[bold]Backup Directory:[/bold] {backups_dir}")
    console.print()

    # Show backups table
    console.print(f"[bold]Available Backups:[/bold] {len(backup_files)} file(s)")
    console.print()

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Backup File", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Modified", justify="right")

    total_size = 0
    for backup_file in backup_files:
        stats = backup_file.stat()
        size_bytes = stats.st_size
        size_mb = size_bytes / (1024 * 1024)
        total_size += size_bytes

        # Format modification time
        mtime = datetime.datetime.fromtimestamp(stats.st_mtime)
        time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

        table.add_row(
            backup_file.name,
            f"{size_mb:.2f} MB",
            time_str,
        )

    console.print(table)
    console.print()

    # Show total size
    total_mb = total_size / (1024 * 1024)
    console.print(f"[bold]Total Backup Size:[/bold] {total_mb:.2f} MB")
    console.print()


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
        cli_ctx: CLIContext = ctx.obj

        console.print()
        console.print("[bold cyan]Running all tests...[/bold cyan]")
        console.print()

        # Build pytest command
        cmd = ["uv", "run", "pytest"]
        if coverage:
            cmd.extend(["--cov", "--cov-report=term-missing"])

        # Run pytest
        result = subprocess.run(
            cmd,
            cwd=cli_ctx.repo_root,
            check=False,
        )

        sys.exit(result.returncode)


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
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print("[bold cyan]Running unit tests...[/bold cyan]")
    console.print()

    # Build pytest command
    cmd = ["uv", "run", "pytest", "-m", "unit"]
    if coverage:
        cmd.extend(["--cov", "--cov-report=term-missing"])

    # Run pytest
    result = subprocess.run(
        cmd,
        cwd=cli_ctx.repo_root,
        check=False,
    )

    sys.exit(result.returncode)


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
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print("[bold cyan]Running integration tests...[/bold cyan]")
    console.print()

    # Build pytest command
    cmd = ["uv", "run", "pytest", "-m", "integration"]
    if coverage:
        cmd.extend(["--cov", "--cov-report=term-missing"])

    # Run pytest
    result = subprocess.run(
        cmd,
        cwd=cli_ctx.repo_root,
        check=False,
    )

    sys.exit(result.returncode)


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
