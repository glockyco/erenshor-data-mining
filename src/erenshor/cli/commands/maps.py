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
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from ..context import CLIContext

app = typer.Typer(
    name="maps",
    help="Build and deploy the interactive maps website",
    no_args_is_help=True,
)

console = Console()


def _check_npm_available() -> bool:
    """Check if npm is available in PATH."""
    return shutil.which("npm") is not None


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


def _create_symlink(source: Path, target: Path) -> None:
    """Create symlink, removing existing target if necessary."""
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            logger.debug(f"Removing existing symlink: {target}")
        else:
            logger.debug(f"Removing existing file: {target}")
        target.unlink()

    logger.info(f"Creating symlink: {target} -> {source}")
    target.symlink_to(source)


def _remove_symlink(target: Path) -> None:
    """Remove symlink if it exists."""
    if target.is_symlink():
        logger.info(f"Removing symlink: {target}")
        target.unlink()
    elif target.exists():
        logger.warning(f"Target exists but is not a symlink: {target}")


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

    # Check npm availability
    if not _check_npm_available():
        console.print("[red]Error: npm not found in PATH[/red]")
        console.print("\nPlease install Node.js and npm:")
        console.print("  https://nodejs.org/")
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
        console.print("  npm install")
        raise typer.Exit(1)

    # Check database exists
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("\nPlease export the database first:")
        console.print(f"  erenshor export --variant {cli_ctx.variant}")
        raise typer.Exit(1)

    # Ensure maps db directory exists
    maps_db_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink
    try:
        _create_symlink(db_path, maps_db_path)
    except Exception as e:
        console.print(f"[red]Error creating symlink: {e}[/red]")
        raise typer.Exit(1) from e

    # Show info panel
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

    # Setup cleanup handler
    def cleanup_handler(signum: int, frame: object) -> None:
        """Clean up symlink on exit."""
        console.print("\n[yellow]Shutting down...[/yellow]")
        _remove_symlink(maps_db_path)
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)

    # Run dev server
    try:
        env = os.environ.copy()
        env["PORT"] = str(port)

        result = subprocess.run(
            ["npm", "run", "dev", "--", "--port", str(port)],
            cwd=maps_dir,
            env=env,
            check=False,
        )

        # Cleanup on normal exit
        _remove_symlink(maps_db_path)

        if result.returncode != 0:
            console.print(f"[red]Dev server exited with code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        _remove_symlink(maps_db_path)
        raise typer.Exit(0) from None
    except Exception as e:
        console.print(f"[red]Error running dev server: {e}[/red]")
        _remove_symlink(maps_db_path)
        raise typer.Exit(1) from e


@app.command()
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

    # Check npm availability
    if not _check_npm_available():
        console.print("[red]Error: npm not found in PATH[/red]")
        console.print("\nPlease install Node.js and npm:")
        console.print("  https://nodejs.org/")
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
        console.print(f"  erenshor maps build --variant {cli_ctx.variant}")
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
        env = os.environ.copy()
        env["PORT"] = str(port)

        result = subprocess.run(
            ["npm", "run", "preview", "--", "--port", str(port)],
            cwd=maps_dir,
            env=env,
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


@app.command()
def build(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force rebuild even if build is up-to-date",
    ),
) -> None:
    """Build production site with copied database.

    Builds static site for production deployment. Copies
    database into build output for deployment to Cloudflare
    Pages. Optimizes assets and generates production bundles.
    """
    cli_ctx: CLIContext = ctx.obj

    # Check npm availability
    if not _check_npm_available():
        console.print("[red]Error: npm not found in PATH[/red]")
        console.print("\nPlease install Node.js and npm:")
        console.print("  https://nodejs.org/")
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
        console.print("  npm install")
        raise typer.Exit(1)

    # Check database exists
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("\nPlease export the database first:")
        console.print(f"  erenshor export --variant {cli_ctx.variant}")
        raise typer.Exit(1)

    # Check if rebuild needed
    if build_dir.exists() and not force:
        console.print("[yellow]Build directory already exists[/yellow]")
        console.print("\nUse --force to rebuild:")
        console.print(f"  erenshor maps build --variant {cli_ctx.variant} --force")
        raise typer.Exit(1)

    # Ensure maps db directory exists
    maps_db_dir.mkdir(parents=True, exist_ok=True)

    # Copy database
    try:
        logger.info(f"Copying database: {db_path} -> {maps_db_path}")
        shutil.copy2(db_path, maps_db_path)
        console.print(f"[green]Database copied to {maps_db_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error copying database: {e}[/red]")
        raise typer.Exit(1) from e

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

    # Run build
    try:
        logger.info("Running npm run build")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=maps_dir,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]Build failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)

        console.print()
        console.print("[green]Build completed successfully![/green]")
        console.print(f"[dim]Output: {build_dir}[/dim]")
        console.print()
        console.print("Next steps:")
        console.print(f"  erenshor maps preview --variant {cli_ctx.variant}  # Preview locally")
        console.print(f"  erenshor maps deploy --variant {cli_ctx.variant}   # Deploy to Cloudflare Pages")
        console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]Build interrupted[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error during build: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def deploy(
    ctx: typer.Context,
) -> None:
    """Deploy to Cloudflare Pages.

    Deploys built site to Cloudflare Pages. Requires valid
    Cloudflare credentials and configured project. Automatically
    builds before deployment if needed.
    """
    cli_ctx: CLIContext = ctx.obj

    # Check npm/npx availability
    if not _check_npm_available():
        console.print("[red]Error: npm not found in PATH[/red]")
        console.print("\nPlease install Node.js and npm:")
        console.print("  https://nodejs.org/")
        raise typer.Exit(1)

    if not shutil.which("npx"):
        console.print("[red]Error: npx not found in PATH[/red]")
        console.print("\nPlease install Node.js and npm:")
        console.print("  https://nodejs.org/")
        raise typer.Exit(1)

    # Get paths
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    maps_dir = variant_config.maps.resolved_source_dir(cli_ctx.repo_root)
    build_dir = variant_config.maps.resolved_build_dir(cli_ctx.repo_root)
    deploy_target = variant_config.maps.deploy_target

    # Check maps directory
    if not maps_dir.exists():
        console.print(f"[red]Error: Maps directory not found: {maps_dir}[/red]")
        raise typer.Exit(1)

    # Check build exists
    if not build_dir.exists():
        console.print(f"[red]Error: Build directory not found: {build_dir}[/red]")
        console.print("\nPlease build the site first:")
        console.print(f"  erenshor maps build --variant {cli_ctx.variant}")
        raise typer.Exit(1)

    # Show info panel
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]Deploying to Cloudflare Pages[/bold cyan]\n"
            f"Variant: {cli_ctx.variant}\n"
            f"Build: {build_dir}\n"
            f"Project: {deploy_target}",
            border_style="cyan",
        )
    )
    console.print()

    if cli_ctx.dry_run:
        console.print("[yellow]DRY RUN: Would deploy with:[/yellow]")
        console.print(f"  npx wrangler pages deploy {build_dir} --project-name {deploy_target}")
        console.print()
        return

    # Run deployment
    try:
        logger.info(f"Deploying to Cloudflare Pages: {deploy_target}")
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", str(build_dir), "--project-name", deploy_target],
            cwd=maps_dir,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]Deployment failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)

        console.print()
        console.print("[green]Deployment completed successfully![/green]")
        console.print()
        console.print(f"[dim]Project: {deploy_target}[/dim]")
        console.print("[dim]Check deployment status at: https://dash.cloudflare.com/[/dim]")
        console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]Deployment interrupted[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error during deployment: {e}[/red]")
        raise typer.Exit(1) from e
