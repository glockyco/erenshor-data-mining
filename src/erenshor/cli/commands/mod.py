"""Mod commands for companion mod development.

This module provides commands for building and deploying the InteractiveMapCompanion mod:
- Copying game DLLs for compilation
- Building the mod with dotnet
- Deploying to BepInEx plugins folder
- Launching the game
"""

from __future__ import annotations

import os
import shutil
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
    name="mod",
    help="Build and deploy companion mods",
    no_args_is_help=True,
)

console = Console()

# Mod directory relative to repo root
MOD_DIR = Path("src/mods/InteractiveMapCompanion")

# Required DLLs to copy from game
REQUIRED_DLLS = [
    "Assembly-CSharp.dll",
    "UnityEngine.dll",
    "UnityEngine.CoreModule.dll",
]


def _check_dotnet_available() -> bool:
    """Check if dotnet CLI is available in PATH."""
    return shutil.which("dotnet") is not None


def _get_game_path(cli_ctx: CLIContext) -> Path | None:
    """Get the game installation path from environment or config.

    Checks ERENSHOR_GAME_PATH environment variable first, then falls back
    to variant game files path.
    """
    # Check environment variable first
    env_path = os.environ.get("ERENSHOR_GAME_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        logger.warning(f"ERENSHOR_GAME_PATH set but path doesn't exist: {env_path}")

    # Fall back to variant config (game files from extract)
    # This might have the DLLs if extraction was done
    variant_config = cli_ctx.config.variants.get(cli_ctx.variant)
    if variant_config:
        game_files = variant_config.resolved_game_files(cli_ctx.repo_root)
        managed_dir = game_files / "Erenshor_Data" / "Managed"
        if managed_dir.exists():
            return game_files

    return None


def _get_managed_dir(game_path: Path) -> Path:
    """Get the Managed directory containing game DLLs."""
    return game_path / "Erenshor_Data" / "Managed"


def _get_bepinex_plugins_dir(game_path: Path) -> Path:
    """Get the BepInEx plugins directory."""
    return game_path / "BepInEx" / "plugins"


def _get_mod_dir(cli_ctx: CLIContext) -> Path:
    """Get the mod source directory."""
    return cli_ctx.repo_root / MOD_DIR


def _get_mod_lib_dir(cli_ctx: CLIContext) -> Path:
    """Get the mod lib directory for game DLLs."""
    return _get_mod_dir(cli_ctx) / "lib"


def _get_mod_output_dir(cli_ctx: CLIContext) -> Path:
    """Get the mod build output directory."""
    return _get_mod_dir(cli_ctx) / "bin" / "Debug" / "netstandard2.1"


def _get_mod_publish_dir(cli_ctx: CLIContext) -> Path:
    """Get the web publish directory for mod downloads."""
    return cli_ctx.repo_root / "src" / "maps" / "static" / "mods"


@app.command()
def setup(ctx: typer.Context) -> None:
    """Copy game DLLs for mod compilation.

    Copies required game assemblies from the game installation to the
    mod's lib directory. These DLLs are needed to compile the mod but
    are not committed to the repository.

    Set ERENSHOR_GAME_PATH environment variable to your game installation,
    or run 'erenshor extract download' first.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Setup[/bold cyan]", border_style="cyan"))
    console.print()

    # Find game path
    game_path = _get_game_path(cli_ctx)
    if not game_path:
        console.print("[red]Error: Game path not found[/red]")
        console.print()
        console.print("Set ERENSHOR_GAME_PATH environment variable to your game installation:")
        console.print("  export ERENSHOR_GAME_PATH='/path/to/Erenshor'")
        console.print()
        console.print("Or run 'uv run erenshor extract download' to download game files.")
        raise typer.Exit(1)

    managed_dir = _get_managed_dir(game_path)
    if not managed_dir.exists():
        console.print(f"[red]Error: Managed directory not found: {managed_dir}[/red]")
        raise typer.Exit(1)

    lib_dir = _get_mod_lib_dir(cli_ctx)
    lib_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]Source: {managed_dir}[/dim]")
    console.print(f"[dim]Target: {lib_dir}[/dim]")
    console.print()

    # Copy each required DLL
    missing = []
    for dll_name in REQUIRED_DLLS:
        source = managed_dir / dll_name
        target = lib_dir / dll_name

        if not source.exists():
            console.print(f"  [red]\u2717[/red] {dll_name} - not found")
            missing.append(dll_name)
            continue

        shutil.copy2(source, target)
        console.print(f"  [green]\u2713[/green] {dll_name}")

    console.print()

    if missing:
        console.print(f"[yellow]Warning: {len(missing)} DLL(s) not found[/yellow]")
        raise typer.Exit(1)

    console.print("[green]Setup complete![/green]")
    console.print()


@app.command()
def build(ctx: typer.Context) -> None:
    """Build the companion mod.

    Compiles the InteractiveMapCompanion mod using dotnet build.
    Requires game DLLs to be present in lib/ directory (run setup first).
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Build[/bold cyan]", border_style="cyan"))
    console.print()

    if not _check_dotnet_available():
        console.print("[red]Error: dotnet CLI not found in PATH[/red]")
        console.print("Install .NET SDK from https://dotnet.microsoft.com/")
        raise typer.Exit(1)

    mod_dir = _get_mod_dir(cli_ctx)
    if not mod_dir.exists():
        console.print(f"[red]Error: Mod directory not found: {mod_dir}[/red]")
        raise typer.Exit(1)

    lib_dir = _get_mod_lib_dir(cli_ctx)
    if not any(lib_dir.glob("*.dll")):
        console.print("[red]Error: No DLLs in lib/ directory[/red]")
        console.print("Run 'uv run erenshor mod setup' first.")
        raise typer.Exit(1)

    console.print(f"[dim]Building: {mod_dir}[/dim]")
    console.print()

    # Run dotnet build
    result = subprocess.run(
        ["dotnet", "build", "--configuration", "Debug"],
        cwd=mod_dir,
        check=False,
    )

    if result.returncode != 0:
        console.print()
        console.print("[red]Build failed![/red]")
        raise typer.Exit(result.returncode)

    console.print()
    console.print("[green]Build successful![/green]")
    console.print()


@app.command()
def deploy(ctx: typer.Context) -> None:
    """Build and deploy mod to BepInEx plugins.

    Builds the mod and copies the output DLL and dependencies to the
    BepInEx plugins folder in the game installation.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Deploy[/bold cyan]", border_style="cyan"))
    console.print()

    # First build
    console.print("[bold]Building mod...[/bold]")
    build_ctx = ctx
    try:
        build(build_ctx)
    except typer.Exit as e:
        if e.exit_code != 0:
            raise

    # Find game path for deployment
    game_path = _get_game_path(cli_ctx)
    if not game_path:
        console.print("[red]Error: Game path not found for deployment[/red]")
        console.print("Set ERENSHOR_GAME_PATH environment variable.")
        raise typer.Exit(1)

    plugins_dir = _get_bepinex_plugins_dir(game_path)
    if not plugins_dir.parent.exists():
        console.print(f"[red]Error: BepInEx not installed at {plugins_dir.parent}[/red]")
        console.print("Install BepInEx to your game first.")
        raise typer.Exit(1)

    plugins_dir.mkdir(parents=True, exist_ok=True)

    output_dir = _get_mod_output_dir(cli_ctx)
    if not output_dir.exists():
        console.print(f"[red]Error: Build output not found: {output_dir}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print("[bold]Deploying to BepInEx...[/bold]")
    console.print(f"[dim]Target: {plugins_dir}[/dim]")
    console.print()

    # Copy mod DLL (now contains all dependencies merged via ILRepack)
    mod_dll = output_dir / "InteractiveMapCompanion.dll"
    if not mod_dll.exists():
        console.print(f"[red]Error: Mod DLL not found: {mod_dll}[/red]")
        raise typer.Exit(1)

    target = plugins_dir / "InteractiveMapCompanion.dll"
    shutil.copy2(mod_dll, target)

    # Get file size for user feedback
    size_bytes = mod_dll.stat().st_size
    size_kb = size_bytes / 1024
    console.print(f"  [green]\u2713[/green] InteractiveMapCompanion.dll ({size_kb:.1f} KB)")

    console.print()
    console.print("[green]Deploy complete![/green]")
    console.print("[dim]Note: All dependencies are merged into InteractiveMapCompanion.dll via ILRepack[/dim]")
    console.print()


@app.command()
def publish(ctx: typer.Context) -> None:
    """Build and publish mod to website download directory.

    Builds the mod and copies the output DLL to the maps website's static
    directory for public download. Run this before building/deploying the
    maps website to include the latest mod version.

    Note: The static/mods directory is gitignored, so DLLs are not committed
    to the repository. You must run this command before deploying the website.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Publish[/bold cyan]", border_style="cyan"))
    console.print()

    # First build
    console.print("[bold]Building mod...[/bold]")
    build_ctx = ctx
    try:
        build(build_ctx)
    except typer.Exit as e:
        if e.exit_code != 0:
            raise

    output_dir = _get_mod_output_dir(cli_ctx)
    mod_dll = output_dir / "InteractiveMapCompanion.dll"
    if not mod_dll.exists():
        console.print(f"[red]Error: Mod DLL not found: {mod_dll}[/red]")
        raise typer.Exit(1)

    publish_dir = _get_mod_publish_dir(cli_ctx)
    publish_dir.mkdir(parents=True, exist_ok=True)

    console.print()
    console.print("[bold]Publishing to website...[/bold]")
    console.print(f"[dim]Target: {publish_dir}[/dim]")
    console.print()

    target = publish_dir / "InteractiveMapCompanion.dll"
    shutil.copy2(mod_dll, target)

    # Get file size for user feedback
    size_bytes = mod_dll.stat().st_size
    size_kb = size_bytes / 1024
    console.print(f"  [green]\u2713[/green] InteractiveMapCompanion.dll ({size_kb:.1f} KB)")

    console.print()
    console.print("[green]Publish complete![/green]")
    console.print("[dim]Next steps:[/dim]")
    console.print("[dim]  1. Commit the updated DLL: git add src/maps/static/mods/[/dim]")
    console.print("[dim]  2. Deploy the maps website to make the new version available[/dim]")
    console.print()


@app.command()
def launch(ctx: typer.Context) -> None:
    """Launch the game.

    Starts Erenshor. On macOS with CrossOver, uses the CROSSOVER_BOTTLE
    environment variable to launch via CrossOver.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Launch Game[/bold cyan]", border_style="cyan"))
    console.print()

    game_path = _get_game_path(cli_ctx)
    if not game_path:
        console.print("[red]Error: Game path not found[/red]")
        console.print("Set ERENSHOR_GAME_PATH environment variable.")
        raise typer.Exit(1)

    # Check for CrossOver on macOS
    crossover_bottle = os.environ.get("CROSSOVER_BOTTLE")
    if sys.platform == "darwin" and crossover_bottle:
        # Launch via CrossOver
        exe_path = game_path / "Erenshor.exe"
        if not exe_path.exists():
            console.print(f"[red]Error: Game executable not found: {exe_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[dim]Launching via CrossOver bottle: {crossover_bottle}[/dim]")
        console.print(f"[dim]Executable: {exe_path}[/dim]")
        console.print()

        # Use open command with CrossOver
        subprocess.run(
            [
                "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine",
                "--bottle",
                crossover_bottle,
                str(exe_path),
            ],
            check=False,
        )
    else:
        # Direct launch (Windows or Linux with Wine)
        exe_path = game_path / "Erenshor.exe"
        if not exe_path.exists():
            console.print(f"[red]Error: Game executable not found: {exe_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[dim]Launching: {exe_path}[/dim]")
        console.print()

        if sys.platform == "win32":
            subprocess.Popen([str(exe_path)])
        else:
            console.print("[yellow]Warning: Direct launch on this platform may not work[/yellow]")
            console.print("Set CROSSOVER_BOTTLE for macOS or use Wine on Linux.")
            subprocess.Popen(["wine", str(exe_path)])

    console.print("[green]Game launched![/green]")
    console.print()
