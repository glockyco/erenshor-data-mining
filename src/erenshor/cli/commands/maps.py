"""Maps commands for interactive map website.

This module provides commands for building and deploying the interactive maps:
- Building the maps website from game data
- Deploying maps to hosting platform
- Validating map data and assets
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.maps import build_info
from erenshor.application.maps.catalog_images import build_character_portraits, build_item_icons
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.cli.preconditions.checks.inputs import program_available, required_path
from erenshor.cli.preconditions.checks.maps import (
    build_exists,
    build_matches_inputs,
    cloudflare_auth_configured,
    no_static_database_files,
)

if TYPE_CHECKING:
    from ..context import CLIContext

app = typer.Typer(
    name="maps",
    help="Build and deploy the interactive maps website",
    no_args_is_help=True,
)

console = Console()

CHECK_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("pnpm", "run", "lint"),
    ("pnpm", "run", "check"),
    ("pnpm", "run", "test"),
)
BROWSER_SMOKE_COMMAND = ("pnpm", "run", "test:e2e")
# The site build, its prebuild scripts, and the dev server read the clean
# database from this variable. Nothing links the database into the source tree.
MAPS_DATABASE_PATH_ENV = "ERENSHOR_MAPS_DATABASE_PATH"

# The two hostnames are two Cloudflare services deployed from one build. The
# canonical service owns erenshor.compendiums.org, the legacy service keeps
# erenshor-maps.wowmuch1.workers.dev for shipped companion overlays.
DEPLOY_CONFIGS: dict[str, str] = {
    "site": "wrangler.jsonc",
    "legacy": "wrangler.legacy.jsonc",
}
# Order matters. Only a config that declares a route moves a Custom Domain, so
# the canonical deploy is the single point where hostname ownership changes.
# Deploying it first means a failure leaves the previous owner untouched.
DEPLOY_ORDER: tuple[str, ...] = ("site", "legacy")


class DeployTarget(str, Enum):
    """Which Worker service(s) `maps deploy` should publish."""

    ALL = "all"
    SITE = "site"
    LEGACY = "legacy"


def _deploy_command(target: str, *, dry_run: bool) -> list[str]:
    """Build the wrangler invocation for one service."""
    command = ["pnpm", "exec", "wrangler", "deploy", "--config", DEPLOY_CONFIGS[target]]
    if dry_run:
        command.append("--dry-run")
    return command


def _run(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> None:
    """Run a command step, streaming output and failing with the child exit code."""
    if shutil.which(cmd[0]) is None:
        console.print(f"[red]Error: {cmd[0]} not found on PATH. The Nix development shell provides it.[/red]")
        raise typer.Exit(1)
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        console.print(f"[red]Step failed ({' '.join(cmd[:2])}…): exit {result.returncode}[/red]")
        raise typer.Exit(result.returncode)


def _get_database_path(cli_ctx: CLIContext) -> Path:
    """Get the variant database path."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_database(cli_ctx.repo_root)


def _build_catalog_images(cli_ctx: CLIContext, maps_dir: Path, db_path: Path) -> None:
    """Build item icons and character portraits from the variant's image catalog."""
    images_dir = cli_ctx.config.variants[cli_ctx.variant].resolved_images_output(cli_ctx.repo_root)
    try:
        result = build_item_icons(db_path, images_dir, maps_dir / "static" / "items")
        portraits = build_character_portraits(db_path, images_dir, maps_dir / "static" / "characters")
    except FileNotFoundError as error:
        console.print(f"[red]Error: {error}. Rebuild the database with `erenshor extract build`.[/red]")
        raise typer.Exit(1) from error
    logger.info(f"Item icons: {result.written} built, {result.kept} kept, {result.removed} removed")
    logger.info(f"Character portraits: {portraits.written} built, {portraits.kept} kept, {portraits.removed} removed")


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
    no_static_database_files,
    program_available("pnpm"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def dev(
    ctx: typer.Context,
    port: int = typer.Option(
        5173,
        "--port",
        help="Port for development server",
    ),
) -> None:
    """Start the development server on the selected variant database.

    Launches the Vite development server for the interactive maps website
    after building the catalog-backed icons and portraits. Server loads read the
    database at request time, so a rebuilt database shows after a page reload.
    Includes hot module reloading.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    db_path = _get_database_path(cli_ctx)
    _build_catalog_images(cli_ctx, maps_dir, db_path)

    process: subprocess.Popen[bytes] | None = None
    previous_handlers: dict[signal.Signals, Any] = {}
    shutdown_requested = False
    try:
        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]Starting Maps Development Server[/bold cyan]\n"
                f"Variant: {cli_ctx.variant}\n"
                f"Port: {port}\n"
                f"Database: {db_path}",
                border_style="cyan",
            )
        )
        console.print()
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")
        console.print()

        process = subprocess.Popen(
            ["pnpm", "exec", "vite", "dev", "--port", str(port)],
            cwd=maps_dir,
            env={**os.environ, MAPS_DATABASE_PATH_ENV: str(db_path)},
            start_new_session=True,
        )

        def request_shutdown(_signum: int, _frame: object) -> None:
            nonlocal shutdown_requested
            shutdown_requested = True
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)

        for handled_signal in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[handled_signal] = signal.signal(handled_signal, request_shutdown)
        return_code = process.wait()
        if shutdown_requested:
            console.print("\n[yellow]Shutting down...[/yellow]")
        elif return_code != 0:
            raise RuntimeError(f"Dev server exited with code {return_code}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except (OSError, RuntimeError) as exc:
        console.print(f"[red]Error running dev server: {exc}[/red]")
        raise typer.Exit(1) from exc
    finally:
        for handled_signal, previous_handler in previous_handlers.items():
            signal.signal(handled_signal, previous_handler)
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


@app.command()
@require_preconditions(
    build_exists,
    build_matches_inputs,
    program_available("pnpm"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def preview(
    ctx: typer.Context,
    port: int = typer.Option(
        4173,
        "--port",
        help="Port for preview server",
    ),
) -> None:
    """Preview built site.

    Serves the production build locally for testing before deployment.
    """
    cli_ctx: CLIContext = ctx.obj

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)

    # Show info panel
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Starting Maps Preview Server[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Port: {port}\n"
            f"Build: {build_dir}",
            border_style="cyan",
        )
    )
    console.print()
    console.print(f"[dim]Preview URL: http://localhost:{port}[/dim]")
    console.print("[dim]Press Ctrl+C to stop the server[/dim]")
    console.print()

    # Run preview server
    try:
        result = subprocess.run(
            ["pnpm", "exec", "vite", "preview", "--port", str(port)],
            cwd=maps_dir,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]Preview server exited with code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        raise typer.Exit(0) from None
    except Exception as e:
        console.print(f"[red]Error running preview server: {e}[/red]")
        raise typer.Exit(1) from e


def _run_checks(maps_dir: Path) -> None:
    """Run the deterministic frontend verification commands once."""
    for command in CHECK_COMMANDS:
        _run(list(command), maps_dir)


@app.command()
@require_preconditions(
    program_available("pnpm"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def check(ctx: typer.Context) -> None:
    """Run lint, Svelte diagnostics, and fixture-backed Vitest tests."""
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)

    _run_checks(maps_dir)


@app.command()
@require_preconditions(
    database_exists,
    database_valid,
    database_has_items,
    no_static_database_files,
    program_available("pnpm"),
    program_available("node"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def build(
    ctx: typer.Context,
    skip_checks: Annotated[
        bool,
        typer.Option(
            "--skip-checks",
            help="Skip checks already completed by the verification DAG.",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Build the production site from the selected variant database.

    The prebuild scripts and the Vite build read the database path from
    ERENSHOR_MAPS_DATABASE_PATH. Writes the build sidecar that deploy uses to
    reject a stale build.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)
    db_path = _get_database_path(cli_ctx)
    site_env = {**os.environ, MAPS_DATABASE_PATH_ENV: str(db_path)}

    try:
        build_info.validate_tile_files(maps_dir)
    except build_info.TileInputError as error:
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from error

    _run(["node", "scripts/generate-tiles-manifest.js"], maps_dir)
    try:
        build_info.validate_tile_inputs(maps_dir)
    except build_info.TileInputError as error:
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from error

    # Show info panel
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Building Maps Site[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Database: {db_path}\n"
            f"Output: {build_dir}",
            border_style="cyan",
        )
    )
    console.print()

    try:
        if not skip_checks:
            logger.info("Running maps verification")
            _run_checks(maps_dir)

        logger.info("Running maps prebuild steps")
        _run(["node", "scripts/generate-og-image.mjs"], maps_dir)
        _build_catalog_images(cli_ctx, maps_dir, db_path)

        logger.info("Running Vite build")
        _run(["pnpm", "exec", "vite", "build"], maps_dir, env=site_env)
        hashes = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=db_path)
        build_info.write_build_info(build_dir, hashes)
        console.print()
        console.print("[green]Build completed successfully![/green]")
        console.print(f"[dim]Output: {build_dir}[/dim]")
        console.print()
        console.print("Next steps:")
        console.print(f"  erenshor -V {cli_ctx.variant} maps preview  # Preview locally")
        console.print(f"  erenshor -V {cli_ctx.variant} maps deploy   # Deploy to Cloudflare")
        console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]Build interrupted[/yellow]")
        raise typer.Exit(1) from None
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error during build: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
@require_preconditions(
    build_exists,
    build_matches_inputs,
    cloudflare_auth_configured,
    program_available("pnpm"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def deploy(
    ctx: typer.Context,
    target: Annotated[
        DeployTarget,
        typer.Option(
            "--target",
            help="Which Worker service to publish: the canonical site, the legacy compatibility host, or both.",
        ),
    ] = DeployTarget.ALL,
) -> None:
    """Deploy to Cloudflare.

    Deploys the built site to Cloudflare using wrangler. Requires valid
    Cloudflare credentials. Build must exist before deploying.

    One build is published to two Worker services: `erenshor-maps-site`
    serves erenshor.compendiums.org, and `erenshor-maps` keeps
    erenshor-maps.wowmuch1.workers.dev alive for shipped companion mods.
    With the default target both are deployed, canonical first, because
    that is the deploy that moves the Custom Domain.
    """
    cli_ctx: CLIContext = ctx.obj

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)

    targets = DEPLOY_ORDER if target is DeployTarget.ALL else (target.value,)

    # Show info panel
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Deploying to Cloudflare[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Build: {build_dir}\n"
            f"Services: {', '.join(DEPLOY_CONFIGS[name] for name in targets)}",
            border_style="cyan",
        )
    )
    console.print()

    if cli_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would deploy with:[/yellow]")
        for name in targets:
            console.print(f"  {' '.join(_deploy_command(name, dry_run=False))}  (in {maps_dir})")
        console.print()
        return

    # Run deployment
    for position, name in enumerate(targets):
        try:
            logger.info(f"Deploying {DEPLOY_CONFIGS[name]} to Cloudflare via wrangler")
            _run(_deploy_command(name, dry_run=False), maps_dir)
        except KeyboardInterrupt:
            console.print("\n[yellow]Deployment interrupted[/yellow]")
            raise typer.Exit(1) from None
        except typer.Exit:
            # The canonical deploy is what repoints the Custom Domain, so a
            # partial run leaves production in a known state worth naming.
            if position > 0:
                console.print()
                console.print(f"[yellow]{DEPLOY_CONFIGS[targets[0]]} is already live. Resume with:[/yellow]")
                console.print(f"  erenshor -V {cli_ctx.variant} maps deploy --target {name}")
                console.print()
            raise
        except Exception as e:
            console.print(f"[red]Error during deployment: {e}[/red]")
            raise typer.Exit(1) from e

    console.print()
    console.print("[green]Deployment completed successfully![/green]")
    console.print("[dim]Check deployment status at: https://dash.cloudflare.com/[/dim]")
    console.print()


@app.command()
@require_preconditions(
    program_available("node"),
    required_path("maps_source_dir", kind="directory"),
    required_path("maps_source_dir", "node_modules", kind="directory"),
)
def thumbnails(
    ctx: typer.Context,
    zones: list[str] = typer.Option(
        [],
        "--zones",
        help="Zone keys to screenshot (default: all zones)",
    ),
    url: str = typer.Option(
        "http://localhost:5174",
        "--url",
        help="Base URL of the running maps dev/preview server",
    ),
) -> None:
    """Generate zone thumbnail images for the zone-maps gallery.

    Opens each zone map in a headless browser, fits the view to the full zone,
    crops to the tile content area, and saves as a JPEG thumbnail.

    Requires a dev or preview server running at --url (default: http://localhost:5174).
    Run 'uv run erenshor maps dev' or 'uv run erenshor maps preview' first.
    """
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)

    env = os.environ.copy()
    env["MAPS_URL"] = url

    console.print(f"[bold cyan]Generating thumbnails[/bold cyan] ({url})")
    if zones:
        console.print(f"  Zones: {', '.join(zones)}")
    else:
        console.print("  Zones: all")
    console.print()

    try:
        _run(["node", "scripts/generate-thumbnails.mjs", *zones], maps_dir, env=env)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(1) from None
    console.print()
    console.print("[green]Thumbnails generated.[/green]")
