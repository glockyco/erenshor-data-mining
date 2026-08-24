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
from typing import TYPE_CHECKING, Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from erenshor.application.maps import build_info
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.cli.preconditions.checks.maps import (
    build_exists,
    build_matches_inputs,
    cloudflare_auth_configured,
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
PRERENDER_SMOKE_COMMAND = ("node", "scripts/test-prerender.mjs")

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
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        console.print(f"[red]Step failed ({' '.join(cmd[:2])}…): exit {result.returncode}[/red]")
        raise typer.Exit(result.returncode)


def _check_pnpm_available() -> bool:
    """Check if pnpm is available in PATH."""
    return shutil.which("pnpm") is not None


def _check_node_modules(maps_dir: Path) -> bool:
    """Check if node_modules directory exists."""
    return (maps_dir / "node_modules").exists()


def _get_database_path(cli_ctx: CLIContext) -> Path:
    """Get the variant database path."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_database(cli_ctx.repo_root)


def _get_maps_db_path(cli_ctx: CLIContext) -> Path:
    """Get the maps database path (symlink/copy target)."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_db_dir = variant_config.maps.resolved_database_dir(cli_ctx.repo_root)
    return maps_db_dir / "erenshor.sqlite"


class DatabaseLinkTransaction:
    """Temporarily replace a database symlink and restore its exact prior state."""

    def __init__(self, source: Path, target: Path) -> None:
        self.source = source
        self.target = target
        self._prior_target: Path | None = None
        self._installed = False
        self._temporary_target = source

    def install(self) -> None:
        if self.target.is_symlink():
            self._prior_target = self.target.readlink()
            self.target.unlink()
        elif self.target.exists():
            raise RuntimeError(f"refusing to replace regular file or directory: {self.target}")
        self.target.symlink_to(self.source)
        self._installed = True

    def restore(self) -> None:
        if not self._installed:
            return
        if not self.target.is_symlink() or self.target.readlink() != self._temporary_target:
            raise RuntimeError(f"database link changed concurrently; refusing to overwrite: {self.target}")
        self.target.unlink()
        if self._prior_target is not None:
            self.target.symlink_to(self._prior_target)


@app.command()
def dev(
    ctx: typer.Context,
    port: int = typer.Option(
        5173,
        "--port",
        help="Port for development server",
    ),
) -> None:
    """Start development server with symlinked database.

    Launches Vite development server for the interactive maps
    website. Uses symlinked database for live updates during
    development. Includes hot module reloading.
    """
    cli_ctx: CLIContext = ctx.obj

    # Check pnpm availability
    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        console.print("\nPlease install pnpm:")
        console.print("  https://pnpm.io/installation")
        raise typer.Exit(1)

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    maps_db_dir = variant_config.maps.resolved_database_dir(cli_ctx.repo_root)
    db_path = _get_database_path(cli_ctx)
    maps_db_path = _get_maps_db_path(cli_ctx)

    # Check maps directory
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)

    # Check node_modules
    if not _check_node_modules(maps_dir):
        console.print("[yellow]Warning: node_modules not found[/yellow]")
        console.print("\nPlease install dependencies first:")
        console.print(f"  cd {maps_dir}")
        console.print("  pnpm install")
        raise typer.Exit(1)

    # Check database exists
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("\nPlease export the database first:")
        console.print(f"  erenshor -V {cli_ctx.variant} export")
        raise typer.Exit(1)

    # Ensure maps db directory exists
    maps_db_dir.mkdir(parents=True, exist_ok=True)

    link = DatabaseLinkTransaction(db_path, maps_db_path)
    process: subprocess.Popen[bytes] | None = None
    previous_handlers: dict[signal.Signals, signal.Handlers] = {}
    try:
        link.install()
        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]Starting Maps Development Server[/bold cyan]\n"
                f"Variant: {cli_ctx.variant}\n"
                f"Port: {port}\n"
                f"Database: {db_path}\n"
                f"Maps DB: {maps_db_path} (symlinked)",
                border_style="cyan",
            )
        )
        console.print()
        console.print("[dim]Database changes will be reflected immediately (symlinked)[/dim]")
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")
        console.print()

        process = subprocess.Popen(
            ["pnpm", "exec", "vite", "dev", "--port", str(port)],
            cwd=maps_dir,
            start_new_session=True,
        )

        def request_shutdown(_signum: int, _frame: object) -> None:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)

        for handled_signal in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[handled_signal] = signal.signal(handled_signal, request_shutdown)
        return_code = process.wait()
        if return_code != 0:
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
        link.restore()


@app.command()
@require_preconditions(build_exists, build_matches_inputs)
def preview(
    ctx: typer.Context,
    port: int = typer.Option(
        4173,
        "--port",
        help="Port for preview server",
    ),
) -> None:
    """Preview built site.

    Serves the production build locally for testing before
    deployment. Uses the built static files with copied
    database.
    """
    cli_ctx: CLIContext = ctx.obj

    # Check pnpm availability
    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        console.print("\nPlease install pnpm:")
        console.print("  https://pnpm.io/installation")
        raise typer.Exit(1)

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)

    # Check maps directory
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)

    # Check build exists
    if not build_dir.exists():
        console.print(f"[red]Error: Build directory not found: {build_dir}[/red]")
        console.print("\nPlease build the site first:")
        console.print(f"  erenshor -V {cli_ctx.variant} maps build")
        raise typer.Exit(1)

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
def check(ctx: typer.Context) -> None:
    """Run lint, Svelte diagnostics, and fixture-backed Vitest tests."""
    cli_ctx: CLIContext = ctx.obj

    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        console.print("\nPlease install pnpm:")
        console.print("  https://pnpm.io/installation")
        raise typer.Exit(1)

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)
    if not _check_node_modules(maps_dir):
        console.print("[yellow]Warning: node_modules not found[/yellow]")
        console.print("\nPlease install dependencies first:")
        console.print(f"  cd {maps_dir}")
        console.print("  pnpm install")
        raise typer.Exit(1)

    _run_checks(maps_dir)


@app.command()
@require_preconditions(database_exists, database_valid, database_has_items)
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
    """Build production site with copied database.

    Builds static site for production deployment. Copies
    database into build output for deployment to Cloudflare
    Pages. Optimizes assets and generates production bundles.
    """
    cli_ctx: CLIContext = ctx.obj

    # Check pnpm availability
    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        console.print("\nPlease install pnpm:")
        console.print("  https://pnpm.io/installation")
        raise typer.Exit(1)

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    maps_db_dir = variant_config.maps.resolved_database_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)
    db_path = _get_database_path(cli_ctx)
    maps_db_path = _get_maps_db_path(cli_ctx)

    # Check maps directory
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)

    # Check node_modules
    if not _check_node_modules(maps_dir):
        console.print("[yellow]Warning: node_modules not found[/yellow]")
        console.print("\nPlease install dependencies first:")
        console.print(f"  cd {maps_dir}")
        console.print("  pnpm install")
        raise typer.Exit(1)

    # Check database exists
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("\nPlease export the database first:")
        console.print(f"  erenshor -V {cli_ctx.variant} export")
        raise typer.Exit(1)

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

    # Run verify, prebuild, and build
    try:
        if not skip_checks:
            logger.info("Running maps verification")
            _run_checks(maps_dir)

        maps_db_dir.mkdir(parents=True, exist_ok=True)
        try:
            logger.info(f"Copying database: {db_path} -> {maps_db_path}")
            if maps_db_path.is_symlink():
                maps_db_path.unlink()
            shutil.copy2(db_path, maps_db_path)
            console.print(f"[green]Database copied to {maps_db_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error copying database: {e}[/red]")
            raise typer.Exit(1) from e

        logger.info("Running maps prebuild steps")
        _run(["node", "scripts/generate-og-image.mjs"], maps_dir)
        _run(["node", "scripts/generate-item-icons.mjs", cli_ctx.variant], maps_dir)

        logger.info("Running Vite build")
        _run(
            ["pnpm", "exec", "vite", "build"],
            maps_dir,
            env={**os.environ, "ERENSHOR_MAPS_DATABASE_PATH": str(db_path)},
        )
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
@require_preconditions(build_exists, build_matches_inputs, cloudflare_auth_configured)
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

    # Check pnpm availability
    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        console.print("\nPlease install pnpm:")
        console.print("  https://pnpm.io/installation")
        raise typer.Exit(1)

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)

    # Check maps directory
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)

    # Check build exists
    if not build_dir.exists():
        console.print(f"[red]Error: Build directory not found: {build_dir}[/red]")
        console.print("\nPlease build the site first:")
        console.print(f"  erenshor -V {cli_ctx.variant} maps build")
        raise typer.Exit(1)

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

    if not _check_pnpm_available():
        console.print("[red]Error: pnpm not found in PATH[/red]")
        raise typer.Exit(1)

    if not _check_node_modules(maps_dir):
        console.print("[yellow]Error: node_modules not found. Run pnpm install first.[/yellow]")
        raise typer.Exit(1)

    args = ["node", "scripts/generate-thumbnails.mjs", *zones]

    env = os.environ.copy()
    env["MAPS_URL"] = url

    console.print(f"[bold cyan]Generating thumbnails[/bold cyan] ({url})")
    if zones:
        console.print(f"  Zones: {', '.join(zones)}")
    else:
        console.print("  Zones: all")
    console.print()

    try:
        result = subprocess.run(args, cwd=maps_dir, env=env, check=False)
        if result.returncode != 0:
            console.print(f"[red]Thumbnail generation failed (exit {result.returncode})[/red]")
            raise typer.Exit(result.returncode)
        console.print()
        console.print("[green]Thumbnails generated.[/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
