"""Extract commands for data extraction pipeline.

This module provides commands for managing the data extraction pipeline:
- Extracting Unity projects via AssetRipper
- Exporting game data to raw SQLite via Unity batch mode
- Building the clean database from the raw export
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from loguru import logger
from rich.console import Console

from erenshor.application.code_facts import extract_code_facts
from erenshor.application.extract.clean_database_workflow import (
    CleanDatabaseRequest,
    CleanDatabaseWorkflow,
)
from erenshor.application.extract.database_comparison import diff_databases, recorded_build_id, render_report
from erenshor.application.extract.editor_packages import (
    PackageRestoreError,
    read_packages_config,
    restore_packages,
)
from erenshor.application.extract.export_workflow import (
    ExportRequest,
    ExportWorkflow,
    adapter_exit_code,
)
from erenshor.application.extract.rip_workflow import RipRequest, RipWorkflow
from erenshor.application.services.backup_service import BackupError, BackupService
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, raw_database_exists
from erenshor.cli.preconditions.checks.extract import comparison_databases, ide_sources
from erenshor.cli.preconditions.checks.field_coverage import export_field_coverage_current
from erenshor.cli.preconditions.checks.inputs import game_installation, required_path
from erenshor.cli.preconditions.checks.unity import (
    editor_packages_restored,
    editor_scripts_linked,
    unity_project_exists,
    unity_version_matches,
)
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
from erenshor.infrastructure.steam.build_feed import fetch_build_feed, resolve_build_published_at
from erenshor.infrastructure.steam.installation import (
    GameInstallation,
    GameInstallationError,
    find_game_installation,
    read_manifest_fields,
)
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


def _game_installation(cli_ctx: CLIContext) -> GameInstallation:
    """Return the selected variant's Steam client installation."""
    return find_game_installation(cli_ctx.variant, cli_ctx.config.variants[cli_ctx.variant].app_id)


def _installed_build_id(installation: GameInstallation) -> str:
    """Return the Steam build ID recorded in the installation's app manifest."""
    build_id = read_manifest_fields(installation.manifest, {"buildid"}).get("buildid")
    if not build_id:
        raise GameInstallationError(f"Steam app manifest has no buildid: {installation.manifest}")
    return build_id


def _resolve_build_published_at(variant_config: Any, build_id: str) -> str | None:
    """Resolve an installed build's authoritative SteamDB publication time.

    A feed that cannot be fetched or parsed raises. A build that is not in the
    feed window returns None, because the feed holds only recent builds.
    """
    builds = fetch_build_feed(str(variant_config.app_id))
    published_at = resolve_build_published_at(builds, build_id)
    if published_at is None:
        logger.warning(f"SteamDB build feed does not contain installed build {build_id}")
        return None
    return published_at.astimezone(UTC).isoformat()


def _profile_root(cli_ctx: CLIContext) -> Path:
    """Return the durable profile root for the selected variant."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return Path(variant_config.resolved_profiles(cli_ctx.repo_root))


def _open_profile(
    cli_ctx: CLIContext,
    command: str,
    *,
    game_build_id: str,
    unity_version: str | None,
    assetripper_version: str | None,
) -> ExportProfileRecorder:
    """Open the active extraction profile run for a subcommand."""
    profile_root = _profile_root(cli_ctx)
    return ExportProfileRecorder.open_or_create(
        root=profile_root,
        variant=cli_ctx.variant,
        command=command,
        game_build_id=game_build_id,
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


@app.command("compare-variants")
@require_preconditions(comparison_databases)
def compare_variants(
    ctx: typer.Context,
    base_variant: str = typer.Option(
        "main",
        "--base-variant",
        help="Older variant to compare against (default: main)",
    ),
    new_variant: str = typer.Option(
        "demo",
        "--new-variant",
        help="Newer variant to compare (default: demo)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the report to this Markdown file",
    ),
    print_report: bool = typer.Option(
        False,
        "--print",
        help="Print the report to stdout when --output is also supplied",
    ),
    limit: int = typer.Option(50, "--limit", min=0, help="Rows listed per table and category (0 lists all)"),
) -> None:
    """Compare the clean databases of two configured game variants table by table."""
    cli_ctx: CLIContext = ctx.obj
    variants = cli_ctx.config.variants
    base_db = variants[base_variant].resolved_database(cli_ctx.repo_root)
    new_db = variants[new_variant].resolved_database(cli_ctx.repo_root)

    try:
        old_label = f"{base_variant} (build {recorded_build_id(base_db)})"
        new_label = f"{new_variant} (build {recorded_build_id(new_db)})"
        report = render_report(diff_databases(base_db, new_db), old_label, new_label, limit=limit)
    except (ValueError, sqlite3.Error) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    _emit_report(report, output, print_report)


@app.command("changes")
@require_preconditions(database_exists)
def changes(
    ctx: typer.Context,
    since: str | None = typer.Option(
        None,
        "--since",
        help="Backed-up build to compare against (default: the newest earlier build)",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write the report to this Markdown file"),
    print_report: bool = typer.Option(
        False, "--print", help="Print the report to stdout when --output is also supplied"
    ),
    limit: int = typer.Option(50, "--limit", min=0, help="Rows listed per table and category (0 lists all)"),
) -> None:
    """Report what changed in the clean database since an earlier game build."""
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    current_db = variant_config.resolved_database(cli_ctx.repo_root)
    try:
        current_build = recorded_build_id(current_db)
        old_build, old_db = BackupService().baseline_clean_database(
            variant_config.resolved_backups(cli_ctx.repo_root), current_build, since
        )
        report = render_report(
            diff_databases(old_db, current_db),
            f"{cli_ctx.variant} build {old_build}",
            f"{cli_ctx.variant} build {current_build}",
            limit=limit,
        )
    except (BackupError, ValueError, sqlite3.Error) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    _emit_report(report, output, print_report)


def _emit_report(report: str, output: Path | None, print_report: bool) -> None:
    if output is not None:
        output.write_text(report, encoding="utf-8")
        typer.echo(f"Report written to: {output}")
    if output is None or print_report:
        typer.echo(report, nl=False)


@app.command()
@require_preconditions(required_path("repo_root", "src/Assets/packages.config"))
def packages(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Re-extract packages that are already present"),
) -> None:
    """Restore the NuGet dependencies the Unity Editor scripts compile against.

    `src/Assets/Packages` is generated output that NuGetForUnity normally writes
    from inside the Editor, so a fresh checkout does not have it and the batch
    export fails on unresolved references. Versions come from
    `src/Assets/packages.config`, and the archives are cached under
    `.erenshor/cache/nuget`.

    `extract rip` copies the result into the ripped Unity project.
    """
    cli_ctx: CLIContext = ctx.obj
    packages_config = cli_ctx.repo_root / "src" / "Assets" / "packages.config"
    packages_dir = cli_ctx.repo_root / "src" / "Assets" / "Packages"
    cache_dir = cli_ctx.repo_root / ".erenshor" / "cache" / "nuget"

    if cli_ctx.dry_run:
        for package in read_packages_config(packages_config):
            logger.info(f"[Dry-run] Would restore {package.directory_name} into {packages_dir}")
        return

    try:
        result = restore_packages(
            packages_config=packages_config,
            packages_dir=packages_dir,
            cache_dir=cache_dir,
            force=force,
        )
    except PackageRestoreError as e:
        console.print(f"[red]Error restoring Editor packages: {e}[/red]")
        logger.exception("Editor package restore failed")
        raise typer.Exit(1) from e

    logger.info(
        f"Editor packages ready for {result.runtime_id}: "
        f"{len(result.restored)} restored, {len(result.reused)} already present"
    )


@app.command()
@require_preconditions(game_installation, editor_packages_restored)
def rip(ctx: typer.Context) -> None:
    """Extract Unity project from game files via AssetRipper.

    Uses AssetRipper to decompile the Erenshor game files into
    a Unity project structure. This allows access to game assets
    and ScriptableObjects for data mining.

    Always performs a fresh extraction into a staging directory, then replaces
    the existing Unity project. A failed extraction leaves the old project.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    installation = _game_installation(cli_ctx)
    game_files_dir = installation.path
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
        command_name,
        game_build_id=_installed_build_id(installation),
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
            _generate_ide_project_files(unity_project_dir, installation.managed_dir)

            logger.info("Next: Run 'erenshor extract export' to export game data to SQLite")

    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.exception("AssetRipper extraction failed")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    game_installation,
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
    build_id = _installed_build_id(_game_installation(cli_ctx))

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
        command_name,
        game_build_id=build_id,
        unity_version=unity.get_version(),
        assetripper_version=None,
    )
    profile_output_path = (
        Path(variant_config.resolved_profiles(cli_ctx.repo_root)) / "runs" / f"{recorder.run_id}.unity.json"
    )

    try:
        with _profile_command(recorder, command_name, cli_ctx):
            logger.info(f"Exporting game data: variant={cli_ctx.variant}")

            # Map Python log levels to Unity log levels.
            python_to_unity_log_level = {
                "DEBUG": "verbose",
                "INFO": "normal",
                "WARNING": "normal",
                "ERROR": "quiet",
                "CRITICAL": "quiet",
            }
            unity_log_level = python_to_unity_log_level.get(cli_ctx.config.global_.logging.level.upper(), "normal")

            def backup(database: Path) -> None:
                console.print("[bold]Creating backup...[/bold]")
                service = BackupService()
                try:
                    stats = service.create_backup(
                        variant=cli_ctx.variant,
                        build_id=build_id,
                        database_path=database,
                        scripts_path=unity_project_dir / "ExportedProject" / "Assets" / "Scripts",
                        backup_dir=variant_config.resolved_backups(cli_ctx.repo_root),
                        app_id=variant_config.app_id,
                    )
                except (BackupError, OSError) as error:
                    raise RuntimeError(f"The raw database was exported to {database}, but {error}") from error
                service.display_backup_stats(stats)

            workflow = ExportWorkflow(
                unity,
                profile_importer=lambda output_path: _import_unity_profile_output(recorder, output_path),
                backup=backup,
            )
            result = workflow.run(
                ExportRequest(
                    unity_project_dir=unity_project_dir,
                    database_path=database_path,
                    logs_dir=logs_dir,
                    log_level=unity_log_level,
                    profile_enabled=profile,
                    profile_output_path=profile_output_path,
                    profile=recorder,
                )
            )
            logger.info(f"Raw data exported: raw_db={result.database_path}, log={result.log_file}")
            logger.info("Run 'erenshor extract build' to produce the clean database")

    except Exception as e:
        console.print(f"[red]Error during export: {e}[/red]")
        logger.exception("Unity export failed")
        exit_code = adapter_exit_code(e)
        raise typer.Exit(exit_code if exit_code is not None else 1) from e


@app.command()
@require_preconditions(game_installation, raw_database_exists)
def build(ctx: typer.Context) -> None:
    """Build the clean database from the raw export.

    Reads the raw SQLite database produced by 'extract export', applies
    mapping.json overrides, filters excluded entities and SimPlayers,
    deduplicates identical characters, recomputes IsUnique per display
    name group, and writes the clean database consumed by wiki, sheets,
    and map. The clean database is then added to the backup of the game
    build it records, so 'extract changes' can compare later builds with it.

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
        command_name,
        game_build_id=_installed_build_id(_game_installation(cli_ctx)),
        unity_version=None,
        assetripper_version=None,
    )

    try:
        with _profile_command(profile, command_name, cli_ctx, terminal=True):
            result = CleanDatabaseWorkflow().run(
                CleanDatabaseRequest(
                    raw_db_path=raw_db_path,
                    clean_db_path=clean_db_path,
                    mapping_json_path=mapping_json_path,
                )
            )
            logger.info(f"Clean database built: clean_db={result.clean_db_path}")
            build_id = recorded_build_id(result.clean_db_path)
            stored = BackupService().add_clean_database(
                variant_config.resolved_backups(cli_ctx.repo_root), build_id, result.clean_db_path
            )
            logger.info(f"Clean database backed up for build {build_id}: {stored}")
            logger.info("Next: Run 'erenshor wiki generate' or 'erenshor sheets deploy'")
    except Exception as e:
        console.print(f"[red]Error during build: {e}[/red]")
        logger.exception("Clean DB build failed")
        raise typer.Exit(1) from e


@app.command("code-facts")
@require_preconditions(game_installation, raw_database_exists)
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
    installation = _game_installation(cli_ctx)
    assembly = installation.managed_dir / "Assembly-CSharp.dll"
    raw_db_path = variant_config.resolved_database_raw(cli_ctx.repo_root)

    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would extract code facts: assembly={assembly}, raw_db={raw_db_path}")
        return

    command_name = "extract code-facts"
    build_id = _installed_build_id(installation)
    profile = _open_profile(
        cli_ctx,
        command_name,
        game_build_id=build_id,
        unity_version=None,
        assetripper_version=None,
    )

    try:
        with _profile_command(profile, command_name, cli_ctx):
            count = extract_code_facts(
                cli_ctx.repo_root,
                assembly,
                raw_db_path,
                cli_ctx.variant,
                game_build_id=build_id,
                game_build_published_at=_resolve_build_published_at(variant_config, build_id),
            )
            logger.info(f"Extracted {count} code-fact rows. Run 'erenshor extract build' next.")
    except Exception as e:
        console.print(f"[red]Error during code-facts extraction: {e}[/red]")
        logger.exception("Code-facts extraction failed")
        raise typer.Exit(1) from e


def _generate_ide_project_files(unity_project_dir: Path, managed_dir: Path) -> None:
    """Generate .csproj and .sln files for LSP support.

    Creates project files that enable IDE features like "Find References"
    for the decompiled game scripts.

    Args:
        unity_project_dir: Path to Unity project directory.
        managed_dir: The installation's managed assembly directory.

    Raises:
        RuntimeError: If the project files cannot be generated. The Unity
            project is already in place at that point.
    """
    scripts_dir = unity_project_dir / "ExportedProject" / "Assets" / "Scripts" / "Assembly-CSharp"
    plugins_dir = unity_project_dir / "ExportedProject" / "Assets" / "Plugins"
    solution_dir = unity_project_dir / "ExportedProject"

    try:
        csproj_path = generate_game_scripts_csproj(
            scripts_dir=scripts_dir,
            managed_dlls_dir=managed_dir,
            plugins_dir=plugins_dir,
        )
        logger.info(f"Generated project file for LSP support: {csproj_path}")
        sln_path = generate_solution_file(
            solution_dir=solution_dir,
            csproj_path=csproj_path,
        )
        logger.info(f"Generated solution file: {sln_path}")
    except (OSError, ValueError) as e:
        raise RuntimeError(
            f"The Unity project was extracted to {unity_project_dir}, but IDE project generation failed: {e}. "
            "Run 'erenshor extract ide-setup' after fixing the cause."
        ) from e


@app.command("ide-setup")
@require_preconditions(ide_sources)
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
    failures: list[str] = []

    # Get Unity paths for Editor script references
    unity_config = cli_ctx.config.global_.unity
    unity_editor_path = unity_config.resolved_path(cli_ctx.repo_root)

    unity_paths = UnityPaths(executable=unity_editor_path)

    # Process all variants - generate per-variant project files
    console.print("[bold]Generating variant project files:[/bold]")
    for variant_name, variant_config in cli_ctx.config.variants.items():
        unity_project_dir = variant_config.resolved_unity_project(cli_ctx.repo_root)

        scripts_dir = unity_project_dir / "ExportedProject" / "Assets" / "Scripts" / "Assembly-CSharp"
        plugins_dir = unity_project_dir / "ExportedProject" / "Assets" / "Plugins"
        solution_dir = unity_project_dir / "ExportedProject"
        editor_dir = unity_project_dir / "ExportedProject" / "Assets" / "Editor"

        # Skip variants that don't have extracted game scripts
        if not scripts_dir.exists():
            logger.info(f"Variant '{variant_name}' not extracted, skipping")
            console.print(f"  [dim]- {variant_name} (not extracted)[/dim]")
            continue
        try:
            managed_dir = find_game_installation(variant_name, variant_config.app_id).managed_dir
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
                except (OSError, ValueError) as e:
                    failures.append(f"{variant_name} Editor scripts: {e}")
                    console.print(f"  [red]✗[/red] Editor scripts: {e}")

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

        except (OSError, ValueError) as e:
            failures.append(f"{variant_name}: {e}")
            console.print(f"  [red]✗[/red] {variant_name}: {e}")

    # Generate the root Editor scripts project from the selected variant's configured source.
    selected_variant_config = cli_ctx.config.variants[cli_ctx.variant]
    root_editor_dir = selected_variant_config.resolved_editor_scripts(cli_ctx.repo_root)
    root_editor_csproj: Path | None = None
    if root_editor_dir.exists():
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
                root_editor_csproj = generate_editor_scripts_csproj(
                    editor_scripts_dir=root_editor_dir,
                    unity_paths=unity_paths,
                    game_scripts_csproj=game_scripts_ref,
                )
                logger.info(f"Generated: {root_editor_csproj}")
                console.print(f"  [green]✓[/green] {root_editor_csproj.relative_to(cli_ctx.repo_root)}")
            except (OSError, ValueError) as e:
                failures.append(f"root Editor scripts: {e}")
                console.print(f"  [red]✗[/red] {e}")

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
    if root_editor_csproj:
        all_mod_projects.insert(0, root_editor_csproj)  # Add Editor scripts to mods list

    # Generate root solution with mods and Editor (game scripts excluded to save memory)
    if not all_mod_projects and not test_projects:
        _raise_ide_failures(failures)
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
    _raise_ide_failures(failures)

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


def _raise_ide_failures(failures: list[str]) -> None:
    """Fail IDE setup after every project that could be generated was written."""
    if failures:
        raise RuntimeError("IDE project generation failed for:\n  " + "\n  ".join(failures))
