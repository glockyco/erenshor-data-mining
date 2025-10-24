"""Extract commands for data extraction pipeline.

This module provides commands for managing the data extraction pipeline:
- Downloading game files from Steam via SteamCMD
- Extracting Unity projects via AssetRipper
- Exporting game data to SQLite via Unity batch mode
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from loguru import logger
from rich.console import Console

from erenshor.application.services.backup_service import BackupService
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.steam import game_files_exist, steam_credentials_exist
from erenshor.cli.preconditions.checks.unity import editor_scripts_linked, unity_project_exists, unity_version_matches
from erenshor.infrastructure.assetripper.assetripper import AssetRipper
from erenshor.infrastructure.steam.steamcmd import SteamCMD
from erenshor.infrastructure.unity.batch_mode import UnityBatchMode

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="extract",
    help="Extract game data from Steam, AssetRipper, and Unity",
    no_args_is_help=True,
)

console = Console()


@app.command()
def full(
    ctx: typer.Context,
    skip_download: bool = typer.Option(
        False,
        "--skip-download",
        help="Skip download step (use existing game files)",
    ),
    skip_rip: bool = typer.Option(
        False,
        "--skip-rip",
        help="Skip AssetRipper extraction step (use existing Unity project)",
    ),
    skip_export: bool = typer.Option(
        False,
        "--skip-export",
        help="Skip Unity export step (use existing database)",
    ),
) -> None:
    """Run full extraction pipeline (download → rip → export).

    This command orchestrates the complete data extraction process:
    1. Downloads game files from Steam via SteamCMD
    2. Extracts Unity project from game files via AssetRipper
    3. Exports game data to SQLite via Unity batch mode

    Steps can be skipped if data already exists.
    """
    cli_ctx: CLIContext = ctx.obj

    logger.info(f"Running full extraction pipeline: variant={cli_ctx.variant}, dry_run={cli_ctx.dry_run}")

    try:
        # Step 1: Download
        if not skip_download:
            console.print("[bold]Step 1/3: Downloading game files from Steam[/bold]")
            download(ctx)
        else:
            console.print("[yellow]Skipping download step[/yellow]")
            console.print()

        # Step 2: Rip
        if not skip_rip:
            console.print("[bold]Step 2/3: Extracting Unity project via AssetRipper[/bold]")
            rip(ctx, force=False)
        else:
            console.print("[yellow]Skipping AssetRipper extraction step[/yellow]")
            console.print()

        # Step 3: Export
        if not skip_export:
            console.print("[bold]Step 3/3: Exporting data to SQLite via Unity[/bold]")
            export(ctx, force=False)
        else:
            console.print("[yellow]Skipping Unity export step[/yellow]")
            console.print()

        console.print("[green bold]Full extraction pipeline completed successfully![/green bold]")
        console.print()

    except typer.Exit:
        # Re-raise typer.Exit to preserve exit code
        raise
    except Exception as e:
        console.print(f"[red]Error during full extraction pipeline: {e}[/red]")
        logger.exception("Full extraction pipeline failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(steam_credentials_exist)
def download(
    ctx: typer.Context,
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Verify file integrity and redownload corrupted files (slower)",
    ),
) -> None:
    """Download or update game files from Steam via SteamCMD.

    Downloads the Erenshor game files for the selected variant using SteamCMD.
    Automatically detects and downloads updates if a newer build is available.

    Use --validate only if you suspect file corruption or extraction issues.
    Validation checks all files against Steam's checksums and redownloads any
    that don't match. This is slower but ensures complete file integrity.

    Requires valid Steam credentials and game ownership.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    game_files_dir = variant_config.resolved_game_files(cli_ctx.repo_root)

    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would download/update game files: app_id={variant_config.app_id}, dir={game_files_dir}")
        return

    try:
        # Log what we're doing
        if validate:
            logger.info(
                f"Downloading game files with validation: variant={cli_ctx.variant}, app_id={variant_config.app_id}"
            )
            logger.info("File validation enabled - all files will be verified (slower)")
        else:
            logger.info(f"Downloading game files: variant={cli_ctx.variant}, app_id={variant_config.app_id}")

        # Create SteamCMD wrapper
        steam_config = cli_ctx.config.global_.steam
        steamcmd = SteamCMD(
            username=steam_config.username,
            platform=steam_config.platform,
        )

        # Download/update game files
        steamcmd.download(
            app_id=variant_config.app_id,
            install_dir=game_files_dir,
            validate=validate,
        )

        logger.info(f"Download complete: {game_files_dir}")

    except Exception as e:
        console.print(f"[red]Error during download: {e}[/red]")
        logger.exception("Game download failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(game_files_exist)
def rip(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-extraction even if Unity project exists",
    ),
) -> None:
    """Extract Unity project from game files via AssetRipper.

    Uses AssetRipper to decompile the Erenshor game files into
    a Unity project structure. This allows access to game assets
    and ScriptableObjects for data mining.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    game_files_dir = variant_config.resolved_game_files(cli_ctx.repo_root)
    unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
    logs_dir = variant_config.resolved_logs(cli_ctx.repo_root)

    # Check if Unity project already exists
    if not force and unity_project_dir.exists() and (unity_project_dir / "Assets").exists():
        logger.info(f"Unity project already exists: {unity_project_dir}")
        logger.info("Use --force to re-extract")
        return

    if cli_ctx.dry_run:
        source_dir = game_files_dir / "Erenshor_Data"
        logger.info(f"[Dry-run] Would extract Unity project: source={source_dir}, target={unity_project_dir}")
        return

    try:
        logger.info(f"Extracting Unity project: variant={cli_ctx.variant}")

        # Create AssetRipper wrapper
        assetripper_config = cli_ctx.config.global_.assetripper
        assetripper = AssetRipper(
            executable_path=assetripper_config.resolved_path(cli_ctx.repo_root),
            port=assetripper_config.port,
            timeout=assetripper_config.timeout,
        )

        # Extract Unity project
        assetripper.extract(
            source_dir=game_files_dir / "Erenshor_Data",
            target_dir=unity_project_dir,
            log_dir=logs_dir,
        )

        logger.info(f"Unity project extraction complete: {unity_project_dir}")

    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.exception("AssetRipper extraction failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    unity_project_exists,
    editor_scripts_linked,
    unity_version_matches,
)
def export(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-export even if database is up-to-date",
    ),
) -> None:
    """Export data to SQLite via Unity batch mode.

    Runs Unity Editor in batch mode to scan game assets and
    export data to SQLite database. Uses custom Unity Editor
    scripts to extract items, NPCs, quests, spells, and more.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
    database_path = variant_config.resolved_database(cli_ctx.repo_root)
    logs_dir = variant_config.resolved_logs(cli_ctx.repo_root)

    # Check if database already exists
    if not force and database_path.exists():
        logger.info(f"Database already exists: {database_path}")
        logger.info("Use --force to re-export")
        return

    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would export data to SQLite: unity={unity_project_dir}, db={database_path}")
        return

    try:
        logger.info(f"Exporting game data: variant={cli_ctx.variant}")

        # Create Unity batch mode wrapper
        unity_config = cli_ctx.config.global_.unity
        unity = UnityBatchMode(
            unity_path=unity_config.resolved_path(cli_ctx.repo_root),
            timeout=unity_config.timeout,
        )

        # Create log file path
        import time

        log_file = logs_dir / f"export_{int(time.time())}.log"

        # Export data
        unity.execute_method(
            project_path=unity_project_dir,
            class_name="ExportBatch",
            method_name="Run",
            log_file=log_file,
            arguments={
                "dbPath": str(database_path.absolute()),
                "logLevel": cli_ctx.config.global_.logging.level,
            },
        )

        logger.info(f"Data export complete: db={database_path}, log={log_file}")

        # Create backup for cross-version analysis
        _create_backup_after_export(cli_ctx, variant_config, database_path)

    except Exception as e:
        console.print(f"[red]Error during export: {e}[/red]")
        logger.exception("Unity export failed")
        raise typer.Exit(1) from e


def _create_backup_after_export(cli_ctx: CLIContext, variant_config: Any, database_path: Path) -> None:
    """Create backup after successful Unity export.

    Attempts to get Steam build ID from manifest. If not available, falls back
    to timestamp-based ID. Backups are for cross-version analysis (SQL queries,
    C# diffs, change detection), not for restoration.

    Args:
        cli_ctx: CLI context with config and variant info.
        variant_config: Variant-specific configuration.
        database_path: Path to exported database.
    """
    from datetime import datetime

    console.print("[bold]Creating backup...[/bold]")

    try:
        # Get build ID from Steam manifest
        game_files_dir = variant_config.resolved_game_files(cli_ctx.repo_root)
        steam_config = cli_ctx.config.global_.steam
        steamcmd = SteamCMD(
            username=steam_config.username,
            platform=steam_config.platform,
        )

        build_id = steamcmd.get_build_id(game_files_dir, variant_config.app_id)

        # Fallback: Use timestamp-based ID if Steam build ID unavailable
        if not build_id:
            build_id = datetime.now().strftime("backup-%Y%m%d-%H%M%S")
            logger.warning(f"Could not determine Steam build ID, using timestamp: {build_id}")
            console.print(f"[yellow]Using timestamp-based backup ID: {build_id}[/yellow]")

        # Get paths for backup
        unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
        scripts_path = unity_project_dir / "Assets" / "Scripts"
        backup_dir = variant_config.resolved_backups(cli_ctx.repo_root)

        # Create backup
        service = BackupService()
        stats = service.create_backup(
            variant=cli_ctx.variant,
            build_id=build_id,
            database_path=database_path,
            scripts_path=scripts_path,
            backup_dir=backup_dir,
            app_id=variant_config.app_id,
        )

        # Display backup stats
        service.display_backup_stats(stats)

    except Exception as e:
        # Log error but don't fail the export
        logger.error(f"Failed to create backup: {e}")
        console.print(f"[yellow]Warning: Backup creation failed: {e}[/yellow]")
        console.print("[yellow]Export succeeded but backup was not created.[/yellow]")
        console.print()
