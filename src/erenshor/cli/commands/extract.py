"""Extract commands for data extraction pipeline.

This module provides commands for managing the data extraction pipeline:
- Downloading game files from Steam via SteamCMD
- Extracting Unity projects via AssetRipper
- Exporting game data to raw SQLite via Unity batch mode
- Building the clean database from the raw export
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from loguru import logger
from rich.console import Console

from erenshor.application.code_facts import extract_code_facts
from erenshor.application.extract.rip_workflow import RipRequest, RipWorkflow
from erenshor.application.processor.build import build as build_clean_db
from erenshor.application.services.backup_service import BackupService
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import raw_database_exists
from erenshor.cli.preconditions.checks.field_coverage import export_field_coverage_current
from erenshor.cli.preconditions.checks.steam import game_files_exist, steam_credentials_exist
from erenshor.cli.preconditions.checks.unity import editor_scripts_linked, unity_project_exists, unity_version_matches
from erenshor.infrastructure.assetripper.assetripper import AssetRipper
from erenshor.infrastructure.csproj_generator import (
    UnityPaths,
    discover_mod_projects,
    generate_editor_scripts_csproj,
    generate_game_scripts_csproj,
    generate_root_solution,
    generate_solution_file,
)
from erenshor.infrastructure.export_profile import ExportProfileRecorder, ExportProfileReport
from erenshor.infrastructure.steam.steamcmd import SteamCMD
from erenshor.infrastructure.unity.batch_mode import UnityBatchMode

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="extract",
    help="Extract game data from Steam, AssetRipper, and Unity",
    no_args_is_help=True,
)
profile_app = typer.Typer(name="profile", help="Inspect extraction profile runs", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


console = Console()


def _read_git_sha(repo_root: Path) -> str | None:
    """Return the short Git SHA for the current checkout when available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"Could not read git SHA for export profile: {e}")
        return None
    sha = result.stdout.strip()
    return sha or None


def _read_build_id(cli_ctx: CLIContext, variant_config: Any) -> str | None:
    """Read the installed Steam build ID without requiring SteamCMD itself."""
    game_files_dir = Path(variant_config.resolved_game_files(cli_ctx.repo_root))
    manifest_file = game_files_dir / "steamapps" / f"appmanifest_{variant_config.app_id}.acf"
    if not manifest_file.exists():
        return None
    try:
        for line in manifest_file.read_text(encoding="utf-8").splitlines():
            if '"buildid"' in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    return parts[3]
    except OSError as e:
        logger.debug(f"Could not read Steam build ID for export profile: {e}")
    return None


def _profile_root(cli_ctx: CLIContext) -> Path:
    """Return the durable profile root for the selected variant."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return Path(variant_config.resolved_profiles(cli_ctx.repo_root))


def _open_profile(
    cli_ctx: CLIContext,
    variant_config: Any,
    command: str,
    *,
    unity_version: str | None,
    assetripper_version: str | None,
) -> ExportProfileRecorder:
    """Open the active extraction profile run for a subcommand."""
    profile_root = _profile_root(cli_ctx)
    return ExportProfileRecorder.open_or_create(
        root=profile_root,
        variant=cli_ctx.variant,
        command=command,
        game_build_id=_read_build_id(cli_ctx, variant_config),
        git_sha=_read_git_sha(cli_ctx.repo_root),
        unity_version=unity_version,
        assetripper_version=assetripper_version,
        machine=None,
    )


@contextmanager
def _profile_command(
    profile: ExportProfileRecorder,
    command: str,
    cli_ctx: CLIContext,
    *,
    terminal: bool = False,
) -> Iterator[None]:
    """Record a CLI command span and persist command status."""
    try:
        with profile.span(command, category="cli", attributes={"variant": cli_ctx.variant}):
            yield
    except Exception:
        profile.finish_command(command, "failed")
        profile.finish("failed")
        raise
    else:
        profile.finish_command(command, "ok")
        if terminal:
            profile.finish("ok")


def _import_unity_profile_output(profile: ExportProfileRecorder, output_path: Path) -> None:
    """Import Unity scanner profile rows into the durable profile run."""
    if not output_path.exists():
        return

    rows = cast("list[dict[str, Any]]", json.loads(output_path.read_text()))
    base_started_at = max(
        (span.started_at for span in profile.spans if span.name == "unity.batch_subprocess"),
        default=profile.started_at,
    )
    for row in rows:
        category = str(row["category"])
        name = str(row["name"])
        profile.record_external_span(
            f"{category}.{name}",
            category=category,
            started_at=base_started_at + (float(row.get("first_start_ms", 0.0)) / 1000.0),
            duration_ms=float(row["total_ms"]),
            attributes={
                "calls": int(row["calls"]),
                "avg_ms": float(row["avg_ms"]),
                "max_ms": float(row["max_ms"]),
            },
        )


@profile_app.command("report")
def profile_report(
    ctx: typer.Context,
    latest: bool = typer.Option(True, "--latest", help="Report the latest profile run"),
) -> None:
    """Print a Markdown summary for an extraction profile run."""
    cli_ctx: CLIContext = ctx.obj
    if not latest:
        raise typer.BadParameter("Only --latest is currently supported")
    report = ExportProfileReport.load_latest(_profile_root(cli_ctx))
    console.print(report.to_markdown(), soft_wrap=True)


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

    command_name = "extract download"
    profile = _open_profile(
        cli_ctx,
        variant_config,
        command_name,
        unity_version=None,
        assetripper_version=None,
    )

    try:
        with _profile_command(profile, command_name, cli_ctx):
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
            profile.update_game_build_id(_read_build_id(cli_ctx, variant_config))

            logger.info(f"Download complete: {game_files_dir}")
            logger.info("Next: Run 'erenshor extract rip' to extract Unity project")

    except Exception as e:
        console.print(f"[red]Error during download: {e}[/red]")
        logger.exception("Game download failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(game_files_exist)
def rip(ctx: typer.Context) -> None:
    """Extract Unity project from game files via AssetRipper.

    Uses AssetRipper to decompile the Erenshor game files into
    a Unity project structure. This allows access to game assets
    and ScriptableObjects for data mining.

    Always performs fresh extraction, removing any existing Unity project.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    game_files_dir = variant_config.resolved_game_files(cli_ctx.repo_root)
    unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
    logs_dir = variant_config.resolved_logs(cli_ctx.repo_root)

    if cli_ctx.dry_run:
        source_dir = game_files_dir / "Erenshor_Data"
        logger.info(f"[Dry-run] Would extract Unity project: source={source_dir}, target={unity_project_dir}")
        return

    assetripper_config = cli_ctx.config.global_.assetripper
    assetripper = AssetRipper(
        executable_path=assetripper_config.resolved_path(cli_ctx.repo_root),
        port=assetripper_config.port,
        timeout=assetripper_config.timeout,
    )
    command_name = "extract rip"
    profile = _open_profile(
        cli_ctx,
        variant_config,
        command_name,
        unity_version=None,
        assetripper_version=assetripper.get_version(),
    )

    try:
        with _profile_command(profile, command_name, cli_ctx):
            logger.info(f"Extracting Unity project: variant={cli_ctx.variant}")
            RipWorkflow(assetripper).run(
                RipRequest(
                    source_dir=game_files_dir / "Erenshor_Data",
                    unity_project_dir=unity_project_dir,
                    logs_dir=logs_dir,
                    editor_source=variant_config.resolved_editor_scripts(cli_ctx.repo_root),
                    packages_source=cli_ctx.repo_root / "src" / "Assets" / "Packages",
                    profile=profile,
                )
            )

            # Generate .csproj for LSP support
            _generate_ide_project_files(cli_ctx, variant_config, unity_project_dir, game_files_dir)

            logger.info("Next: Run 'erenshor extract export' to export game data to SQLite")

    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.exception("AssetRipper extraction failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    export_field_coverage_current,
    unity_project_exists,
    editor_scripts_linked,
    unity_version_matches,
)
def export(
    ctx: typer.Context,
    profile: bool = typer.Option(
        False,
        "--profile",
        help="Enable Unity scanner listener profiling and import the rows into the profile run",
    ),
) -> None:
    """Export data to SQLite via Unity batch mode.

    Runs Unity Editor in batch mode to scan game assets and
    export data to SQLite database. Uses custom Unity Editor
    scripts to extract items, NPCs, quests, spells, and more.

    Always performs fresh export, overwriting any existing database.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
    database_path = variant_config.resolved_database_raw(cli_ctx.repo_root)
    logs_dir = variant_config.resolved_logs(cli_ctx.repo_root)

    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would export data to SQLite: unity={unity_project_dir}, raw_db={database_path}")
        return

    # Create Unity batch mode wrapper
    unity_config = cli_ctx.config.global_.unity
    unity = UnityBatchMode(
        unity_path=unity_config.resolved_path(cli_ctx.repo_root),
        timeout=unity_config.timeout,
    )
    command_name = "extract export"
    recorder = _open_profile(
        cli_ctx,
        variant_config,
        command_name,
        unity_version=unity.get_version(),
        assetripper_version=None,
    )
    profile_output_path = (
        Path(variant_config.resolved_profiles(cli_ctx.repo_root)) / "runs" / f"{recorder.run_id}.unity.json"
    )

    try:
        with _profile_command(recorder, command_name, cli_ctx):
            # Clean up old raw database before export
            if database_path.exists():
                logger.info(f"Removing old raw database: {database_path}")
                database_path.unlink()

            logger.info(f"Exporting game data: variant={cli_ctx.variant}")

            # Create log file path
            import time

            log_file = logs_dir / f"export_{int(time.time())}.log"

            # Map Python log levels to Unity log levels
            python_to_unity_log_level = {
                "DEBUG": "verbose",
                "INFO": "normal",
                "WARNING": "normal",
                "ERROR": "quiet",
                "CRITICAL": "quiet",
            }
            unity_log_level = python_to_unity_log_level.get(cli_ctx.config.global_.logging.level.upper(), "normal")

            # Export data
            unity.execute_method(
                project_path=unity_project_dir / "ExportedProject",
                class_name="ExportBatch",
                method_name="Run",
                log_file=log_file,
                arguments={
                    "dbPath": str(database_path.absolute()),
                    "logLevel": unity_log_level,
                    "profile": "true" if profile else "false",
                    "profileOutput": str(profile_output_path),
                },
                profile=recorder,
            )
            if profile:
                _import_unity_profile_output(recorder, profile_output_path)

            logger.info(f"Raw data exported: raw_db={database_path}, log={log_file}")
            logger.info("Run 'erenshor extract build' to produce the clean database")

            # Create backup for cross-version analysis
            _create_backup_after_export(cli_ctx, variant_config, database_path)

    except Exception as e:
        console.print(f"[red]Error during export: {e}[/red]")
        logger.exception("Unity export failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(raw_database_exists)
def build(ctx: typer.Context) -> None:
    """Build the clean database from the raw export.

    Reads the raw SQLite database produced by 'extract export', applies
    mapping.json overrides, filters excluded entities and SimPlayers,
    deduplicates identical characters, recomputes IsUnique per display
    name group, and writes the clean database consumed by wiki, sheets,
    and map.

    Does not require a fresh 'extract export' — re-running 'extract build'
    after changing build logic is much faster than a full re-export.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    raw_db_path = variant_config.resolved_database_raw(cli_ctx.repo_root)
    clean_db_path = variant_config.resolved_database(cli_ctx.repo_root)
    mapping_json_path = cli_ctx.repo_root / "mapping.json"

    if cli_ctx.dry_run:
        logger.info(
            f"[Dry-run] Would build clean DB: raw={raw_db_path}, clean={clean_db_path}, mapping={mapping_json_path}"
        )
        return

    command_name = "extract build"
    profile = _open_profile(
        cli_ctx,
        variant_config,
        command_name,
        unity_version=None,
        assetripper_version=None,
    )

    try:
        with _profile_command(profile, command_name, cli_ctx, terminal=True):
            build_clean_db(
                raw_db_path=raw_db_path,
                clean_db_path=clean_db_path,
                mapping_json_path=mapping_json_path,
            )
            logger.info("Next: Run 'erenshor wiki generate' or 'erenshor sheets deploy'")
    except Exception as e:
        console.print(f"[red]Error during build: {e}[/red]")
        logger.exception("Clean DB build failed")
        raise typer.Exit(1) from e


@app.command("code-facts")
@require_preconditions(game_files_exist, raw_database_exists)
def code_facts(ctx: typer.Context) -> None:
    """Extract hardcoded game constants from the shipped assembly into the raw DB.

    Runs the CodeFacts analyzer against the shipped Assembly-CSharp.dll and
    writes the results into the writer-owned ``code_facts`` tables of the raw
    database. The analyzer's exit code stops the pipeline when the game code
    changed shape, so hardcoded constants flow through the same review gates
    as asset data.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    assembly = (
        variant_config.resolved_game_files(cli_ctx.repo_root) / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
    )
    raw_db_path = variant_config.resolved_database_raw(cli_ctx.repo_root)

    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would extract code facts: assembly={assembly}, raw_db={raw_db_path}")
        return

    command_name = "extract code-facts"
    profile = _open_profile(
        cli_ctx,
        variant_config,
        command_name,
        unity_version=None,
        assetripper_version=None,
    )

    try:
        with _profile_command(profile, command_name, cli_ctx):
            count = extract_code_facts(cli_ctx.repo_root, assembly, raw_db_path, cli_ctx.variant)
            logger.info(f"Extracted {count} code-fact rows. Run 'erenshor extract build' next.")
    except Exception as e:
        console.print(f"[red]Error during code-facts extraction: {e}[/red]")
        logger.exception("Code-facts extraction failed")
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
        scripts_path = unity_project_dir / "ExportedProject" / "Assets" / "Scripts"
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


def _generate_ide_project_files(
    cli_ctx: CLIContext, variant_config: Any, unity_project_dir: Path, game_files_dir: Path
) -> None:
    """Generate .csproj and .sln files for LSP support.

    Creates project files that enable IDE features like "Find References"
    for the decompiled game scripts.

    Args:
        cli_ctx: CLI context.
        variant_config: Variant-specific configuration.
        unity_project_dir: Path to Unity project directory.
        game_files_dir: Path to game files directory.
    """
    scripts_dir = unity_project_dir / "ExportedProject" / "Assets" / "Scripts" / "Assembly-CSharp"
    managed_dir = game_files_dir / "Erenshor_Data" / "Managed"
    plugins_dir = unity_project_dir / "ExportedProject" / "Assets" / "Plugins"
    solution_dir = unity_project_dir / "ExportedProject"

    if not scripts_dir.exists():
        logger.warning(f"Scripts directory not found, skipping IDE setup: {scripts_dir}")
        return

    if not managed_dir.exists():
        logger.warning(f"Managed DLLs directory not found, skipping IDE setup: {managed_dir}")
        return

    try:
        # Generate .csproj
        csproj_path = generate_game_scripts_csproj(
            scripts_dir=scripts_dir,
            managed_dlls_dir=managed_dir,
            plugins_dir=plugins_dir,
        )
        logger.info(f"Generated project file for LSP support: {csproj_path}")

        # Generate .sln
        sln_path = generate_solution_file(
            solution_dir=solution_dir,
            csproj_path=csproj_path,
        )
        logger.info(f"Generated solution file: {sln_path}")

    except Exception as e:
        # Log error but don't fail the rip
        logger.warning(f"Failed to generate IDE project files: {e}")
        console.print(f"[yellow]Warning: IDE setup failed: {e}[/yellow]")
        console.print("[yellow]Rip succeeded but LSP support may not work.[/yellow]")


@app.command("ide-setup")
def ide_setup(ctx: typer.Context) -> None:
    """Generate IDE project files for all variants and mods.

    Creates .csproj and .sln files that enable IDE features like "Find References"
    and "Go to Definition" for the decompiled game scripts and mods in Zed, VS Code,
    or other editors with C# LSP support.

    This command:
    1. Discovers all existing game variants (main, playtest, demo)
    2. Generates Assembly-CSharp.csproj for each variant's game scripts
    3. Discovers all mod projects under src/mods/
    4. Generates a root Erenshor.sln including all projects

    For Zed users: Configure OmniSharp as the language server for proper
    cross-file "Find References" support:

        "languages": { "CSharp": { "language_servers": ["omnisharp", "!roslyn"] } }
    """
    cli_ctx: CLIContext = ctx.obj

    if cli_ctx.dry_run:
        logger.info("[Dry-run] Would generate IDE project files for all variants")
        return

    try:
        _generate_all_ide_project_files(cli_ctx)
    except Exception as e:
        console.print(f"[red]Error generating IDE project files: {e}[/red]")
        logger.exception("IDE setup failed")
        raise typer.Exit(1) from e


def _generate_all_ide_project_files(cli_ctx: CLIContext) -> None:
    """Generate IDE project files for all variants and create root solution.

    Discovers all existing variants and mod projects, generates .csproj files
    for game scripts and Editor scripts, and creates a lightweight Erenshor.sln
    at the repo root containing mods and Editor scripts (game scripts excluded
    to avoid excessive memory usage).

    Args:
        cli_ctx: CLI context with config and repo root.
    """
    variant_solutions: list[Path] = []
    editor_csproj_path: Path | None = None

    # Get Unity paths for Editor script references
    unity_config = cli_ctx.config.global_.unity
    unity_editor_path = unity_config.resolved_path(cli_ctx.repo_root)

    try:
        unity_paths = UnityPaths.from_executable(unity_editor_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Unity Editor is required for IDE setup.[/yellow]")
        raise typer.Exit(1) from e

    # Process all variants - generate per-variant project files
    console.print("[bold]Generating variant project files:[/bold]")
    for variant_name, variant_config in cli_ctx.config.variants.items():
        unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
        game_files_dir = variant_config.resolved_game_files(cli_ctx.repo_root)

        scripts_dir = unity_project_dir / "ExportedProject" / "Assets" / "Scripts" / "Assembly-CSharp"
        managed_dir = game_files_dir / "Erenshor_Data" / "Managed"
        plugins_dir = unity_project_dir / "ExportedProject" / "Assets" / "Plugins"
        solution_dir = unity_project_dir / "ExportedProject"
        editor_dir = unity_project_dir / "ExportedProject" / "Assets" / "Editor"

        # Skip variants that don't have extracted game scripts
        if not scripts_dir.exists():
            logger.info(f"Variant '{variant_name}' not extracted, skipping")
            console.print(f"  [dim]- {variant_name} (not extracted)[/dim]")
            continue

        if not managed_dir.exists():
            logger.warning(f"Variant '{variant_name}' missing Managed DLLs, skipping")
            console.print(f"  [yellow]⚠[/yellow] {variant_name} (missing Managed DLLs)")
            continue

        try:
            # Generate .csproj for game scripts
            csproj_path = generate_game_scripts_csproj(
                scripts_dir=scripts_dir,
                managed_dlls_dir=managed_dir,
                plugins_dir=plugins_dir,
            )
            logger.info(f"Generated: {csproj_path}")
            console.print(f"  [green]✓[/green] {csproj_path.relative_to(cli_ctx.repo_root)}")

            # Generate .csproj for Editor scripts if they exist
            editor_csproj = None
            if editor_dir.exists():
                try:
                    editor_csproj = generate_editor_scripts_csproj(
                        editor_scripts_dir=editor_dir,
                        unity_paths=unity_paths,
                        game_scripts_csproj=csproj_path,
                    )
                    logger.info(f"Generated: {editor_csproj}")
                    console.print(f"  [green]✓[/green] {editor_csproj.relative_to(cli_ctx.repo_root)}")
                    # Track the first Editor csproj for root solution
                    if editor_csproj_path is None:
                        editor_csproj_path = editor_csproj
                except Exception as e:
                    logger.warning(f"Failed to generate Editor project for '{variant_name}': {e}")
                    console.print(f"  [yellow]⚠[/yellow] Editor scripts: {e}")

            # Generate variant-specific .sln (includes both game scripts and Editor)
            additional_projects = [editor_csproj] if editor_csproj else None
            sln_path = generate_solution_file(
                solution_dir=solution_dir,
                csproj_path=csproj_path,
                additional_projects=additional_projects,
            )
            logger.info(f"Generated: {sln_path}")
            console.print(f"  [green]✓[/green] {sln_path.relative_to(cli_ctx.repo_root)}")
            variant_solutions.append(sln_path)

        except Exception as e:
            logger.warning(f"Failed to generate IDE files for variant '{variant_name}': {e}")
            console.print(f"  [yellow]⚠[/yellow] {variant_name}: {e}")

    # Generate Editor scripts csproj in src/Assets/Editor for root solution
    src_editor_dir = cli_ctx.repo_root / "src" / "Assets" / "Editor"
    src_editor_csproj: Path | None = None
    if src_editor_dir.exists():
        console.print()
        console.print("[bold]Generating Editor scripts project:[/bold]")

        # Find any existing game scripts csproj to reference (use first variant)
        game_scripts_ref = None
        for variant_config in cli_ctx.config.variants.values():
            unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)
            potential_csproj = (
                unity_project_dir
                / "ExportedProject"
                / "Assets"
                / "Scripts"
                / "Assembly-CSharp"
                / "Assembly-CSharp.csproj"
            )
            if potential_csproj.exists():
                game_scripts_ref = potential_csproj
                break

        if game_scripts_ref is None:
            console.print("  [yellow]⚠[/yellow] No game scripts csproj found - skipping Editor project")
            console.print("    [dim]Run 'extract ide-setup' after extracting at least one variant[/dim]")
        else:
            try:
                src_editor_csproj = generate_editor_scripts_csproj(
                    editor_scripts_dir=src_editor_dir,
                    unity_paths=unity_paths,
                    game_scripts_csproj=game_scripts_ref,
                )
                logger.info(f"Generated: {src_editor_csproj}")
                console.print(f"  [green]✓[/green] {src_editor_csproj.relative_to(cli_ctx.repo_root)}")
            except Exception as e:
                logger.warning(f"Failed to generate Editor scripts project: {e}")
                console.print(f"  [yellow]⚠[/yellow] {e}")

    # Discover mod projects
    mods_dir = cli_ctx.repo_root / "src" / "mods"
    mod_projects, test_projects = discover_mod_projects(mods_dir)

    if mod_projects:
        console.print()
        console.print("[bold]Discovered mod projects:[/bold]")
        for proj in mod_projects:
            console.print(f"  [green]✓[/green] {proj.relative_to(cli_ctx.repo_root)}")

    if test_projects:
        console.print()
        console.print("[bold]Discovered test projects:[/bold]")
        for proj in test_projects:
            console.print(f"  [green]✓[/green] {proj.relative_to(cli_ctx.repo_root)}")

    # Build list of projects for root solution (mods + Editor scripts, no game scripts)
    all_mod_projects = list(mod_projects)
    if src_editor_csproj:
        all_mod_projects.insert(0, src_editor_csproj)  # Add Editor scripts to mods list

    # Generate root solution with mods and Editor (game scripts excluded to save memory)
    if not all_mod_projects and not test_projects:
        console.print()
        console.print("[yellow]No mod or Editor projects found. Root solution not generated.[/yellow]")
        if variant_solutions:
            console.print()
            console.print("[green bold]IDE setup complete![/green bold]")
            console.print()
            console.print("For game script analysis, open a variant solution:")
            for sln in variant_solutions:
                console.print(f"  • {sln.relative_to(cli_ctx.repo_root)}")
        return

    console.print()
    console.print("[bold]Generating root solution (mods + Editor)...[/bold]")

    root_sln_path = cli_ctx.repo_root / "Erenshor.sln"
    generate_root_solution(
        solution_path=root_sln_path,
        game_script_projects={},  # Empty - don't include game scripts to save memory
        mod_projects=all_mod_projects,
        test_projects=test_projects,
    )

    console.print(f"  [green]✓[/green] {root_sln_path.relative_to(cli_ctx.repo_root)}")
    console.print()
    console.print("[green bold]IDE setup complete![/green bold]")
    console.print()
    console.print(f"[bold]Root solution (mods + Editor):[/bold] {root_sln_path}")
    for proj in all_mod_projects:
        console.print(f"  • {proj.stem}")
    for proj in test_projects:
        console.print(f"  • {proj.stem}")

    if variant_solutions:
        console.print()
        console.print("[bold]Game script solutions (per-variant):[/bold]")
        for sln in variant_solutions:
            console.print(f"  • {sln.relative_to(cli_ctx.repo_root)}")

    console.print()
    console.print("[dim]Tip: For Zed, use OmniSharp for cross-file Find References:[/dim]")
    console.print('[dim]  "languages": { "CSharp": { "language_servers": ["omnisharp", "!roslyn"] } }[/dim]')
