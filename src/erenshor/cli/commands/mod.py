"""Mod commands for companion mod development.

This module provides commands for building and deploying companion mods:
- Copying game DLLs for compilation
- Building mods with dotnet
- Deploying to BepInEx plugins folder
- Publishing to website download directory
- Publishing to Thunderstore
- Generating mod metadata
- Launching the game
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from ..context import CLIContext


class ModInfo(TypedDict):
    dir: str
    name: str
    dll_name: str
    thunderstore: NotRequired[str]
    bepinex_dlls: NotRequired[list[str]]


app = typer.Typer(
    name="mod",
    help="Build and deploy companion mods",
    no_args_is_help=True,
)

console = Console()

# Mod registry - all companion mods in the project
MODS: dict[str, ModInfo] = {
    "interactive-map-companion": {
        "dir": "src/mods/InteractiveMapCompanion",
        "name": "Interactive Map Companion",
        "dll_name": "InteractiveMapCompanion.dll",
        "thunderstore": "WoW_Much/InteractiveMapCompanion",
        # Harmony ships with BepInEx, not with the game — copy from BepInEx/core/
        "bepinex_dlls": ["0Harmony.dll"],
    },
    "interactive-maps-companion": {
        "dir": "src/mods/InteractiveMapsCompanion",
        "name": "Interactive Maps Companion",
        "dll_name": "InteractiveMapsCompanion.dll",
    },
    "justice-for-f7": {
        "dir": "src/mods/JusticeForF7",
        "name": "Justice for F7",
        "dll_name": "JusticeForF7.dll",
        "thunderstore": "WoW_Much/JusticeForF7",
    },
    "sprint": {
        "dir": "src/mods/Sprint",
        "name": "Sprint",
        "dll_name": "Sprint.dll",
        "thunderstore": "WoW_Much/Sprint",
    },
}

# Required DLLs to copy from game
REQUIRED_DLLS = [
    "Assembly-CSharp.dll",
    "UnityEngine.dll",
    "UnityEngine.CoreModule.dll",
    "UnityEngine.InputLegacyModule.dll",
    "UnityEngine.UIModule.dll",
    "UnityEngine.UI.dll",
    "Unity.TextMeshPro.dll",
    "com.rlabrecque.steamworks.net.dll",
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


def _get_mod_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    """Get the mod source directory."""
    if mod_id not in MODS:
        raise ValueError(f"Unknown mod: {mod_id}")
    return cli_ctx.repo_root / MODS[mod_id]["dir"]


def _get_mod_lib_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    """Get the mod lib directory for game DLLs."""
    return _get_mod_dir(cli_ctx, mod_id) / "lib"


def _get_mod_output_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    """Get the mod build output directory."""
    return _get_mod_dir(cli_ctx, mod_id) / "bin" / "Debug" / "netstandard2.1"


def _get_mod_publish_dir(cli_ctx: CLIContext) -> Path:
    """Get the web publish directory for mod downloads."""
    return cli_ctx.repo_root / "src" / "maps" / "static" / "mods"


def _build_mods_internal(
    cli_ctx: CLIContext,
    mod: str | None = None,
    version: str | None = None,
    *,
    skip_ilrepack: bool = False,
) -> None:
    """Internal helper to build mods.

    Builds specified mod or all mods, generating metadata. Raises typer.Exit
    if build fails. Used by both build command and other commands that need
    to build mods as a prerequisite.

    If version is provided, it is passed to dotnet build via -p:ModVersion,
    overriding the git-derived version from generate-mod-version.py.

    If skip_ilrepack is True, passes -p:SkipILRepack=true to produce
    separate DLLs instead of a single merged assembly. Used for
    Thunderstore packaging where reviewers need to inspect individual DLLs.
    """
    if not _check_dotnet_available():
        console.print("[red]Error: dotnet CLI not found in PATH[/red]")
        console.print("Install .NET SDK from https://dotnet.microsoft.com/")
        raise typer.Exit(1)

    # Determine which mods to build
    mods_to_build = [mod] if mod else list(MODS.keys())
    if mod and mod not in MODS:
        console.print(f"[red]Error: Unknown mod: {mod}[/red]")
        console.print(f"Available mods: {', '.join(MODS.keys())}")
        raise typer.Exit(1)

    failed = []
    for mod_id in mods_to_build:
        mod_dir = _get_mod_dir(cli_ctx, mod_id)
        if not mod_dir.exists():
            console.print(f"[red]Error: Mod directory not found: {mod_dir}[/red]")
            raise typer.Exit(1)

        lib_dir = _get_mod_lib_dir(cli_ctx, mod_id)
        if not any(lib_dir.glob("*.dll")):
            console.print(f"[red]Error: No DLLs in {mod_id}/lib/ directory[/red]")
            console.print("Run 'uv run erenshor mod setup' first.")
            raise typer.Exit(1)

        console.print(f"[bold]{MODS[mod_id]['name']}[/bold]")
        console.print(f"[dim]{mod_dir}[/dim]")
        console.print()

        # Run dotnet build
        build_cmd: list[str] = ["dotnet", "build", "--configuration", "Debug"]
        if version:
            build_cmd.append(f"-p:ModVersion={version}")
        if skip_ilrepack:
            build_cmd.append("-p:SkipILRepack=true")
        result = subprocess.run(
            build_cmd,
            cwd=mod_dir,
            check=False,
        )

        if result.returncode != 0:
            console.print("[red]✗ Build failed[/red]")
            console.print()
            failed.append(mod_id)
        else:
            console.print("[green]✓ Build successful[/green]")
            console.print()

    if failed:
        console.print(f"[red]Build failed for: {', '.join(failed)}[/red]")
        raise typer.Exit(1)

    # Generate metadata after all mods built
    console.print("[bold]Generating mod metadata...[/bold]")
    result = subprocess.run(
        ["uv", "run", "python3", "scripts/generate-mods-metadata.py"],
        cwd=cli_ctx.repo_root,
        check=False,
    )

    if result.returncode != 0:
        console.print("[red]Warning: Metadata generation failed[/red]")
        console.print()
    else:
        console.print()


@app.command()
def setup(ctx: typer.Context) -> None:
    """Copy game DLLs for mod compilation.

    Copies required game assemblies from the game installation to the
    mods' lib directories. These DLLs are needed to compile the mods but
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

    console.print(f"[dim]Source: {managed_dir}[/dim]")
    console.print()

    bepinex_core_dir = game_path / "BepInEx" / "core"

    # Copy DLLs to all mod lib directories
    for mod_id, mod_info in MODS.items():
        lib_dir = _get_mod_lib_dir(cli_ctx, mod_id)
        lib_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[bold]{mod_info['name']}[/bold]")

        missing = []
        for dll_name in REQUIRED_DLLS:
            source = managed_dir / dll_name
            target = lib_dir / dll_name
            if not source.exists():
                missing.append(dll_name)
                console.print(f"  [red]✗[/red] {dll_name} (not found in game)")
            else:
                shutil.copy2(source, target)
                console.print(f"  [green]✓[/green] {dll_name}")

        for dll_name in mod_info.get("bepinex_dlls", []):
            source = bepinex_core_dir / dll_name
            target = lib_dir / dll_name
            if not source.exists():
                missing.append(dll_name)
                console.print(f"  [red]✗[/red] {dll_name} (not found in BepInEx/core)")
            else:
                shutil.copy2(source, target)
                console.print(f"  [green]✓[/green] {dll_name} (from BepInEx)")

        if missing:
            console.print(f"[red]Error: Missing DLLs: {', '.join(missing)}[/red]")
            raise typer.Exit(1)

        console.print()

    console.print("[green]Setup complete![/green]")
    console.print()


@app.command()
def build(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Build specific mod (or all if not specified)"),
) -> None:
    """Build companion mods.

    Compiles the companion mods using dotnet build.
    Requires game DLLs to be present in lib/ directories (run setup first).

    By default, builds all mods. Use --mod to build a specific one.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Build[/bold cyan]", border_style="cyan"))
    console.print()

    _build_mods_internal(cli_ctx, mod)

    console.print("[green]Build complete![/green]")
    console.print()


@app.command()
def deploy(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Deploy specific mod (or all if not specified)"),
) -> None:
    """Build and deploy mods to BepInEx plugins.

    Builds mods and copies the output DLLs to the BepInEx plugins folder
    in the game installation.

    By default, deploys all mods. Use --mod to deploy a specific one.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Deploy[/bold cyan]", border_style="cyan"))
    console.print()

    # First build all mods
    console.print("[bold]Building mods...[/bold]")
    _build_mods_internal(cli_ctx, mod)

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

    console.print()
    console.print("[bold]Deploying to BepInEx...[/bold]")
    console.print(f"[dim]Target: {plugins_dir}[/dim]")
    console.print()

    # Determine which mods to deploy
    mods_to_deploy = [mod] if mod else list(MODS.keys())

    for mod_id in mods_to_deploy:
        output_dir = _get_mod_output_dir(cli_ctx, mod_id)
        if not output_dir.exists():
            console.print(f"[red]Error: Build output not found: {output_dir}[/red]")
            raise typer.Exit(1)

        dll_name = MODS[mod_id]["dll_name"]
        mod_dll = output_dir / dll_name
        if not mod_dll.exists():
            console.print(f"[red]Error: Mod DLL not found: {mod_dll}[/red]")
            raise typer.Exit(1)

        target = plugins_dir / dll_name
        shutil.copy2(mod_dll, target)

        # Get file size for user feedback
        size_bytes = mod_dll.stat().st_size
        size_kb = size_bytes / 1024
        console.print(f"  [green]✓[/green] {dll_name} ({size_kb:.1f} KB)")

    console.print()
    console.print("[green]Deploy complete![/green]")
    console.print("[dim]Note: All dependencies are merged into DLLs via ILRepack[/dim]")
    console.print()


@app.command()
def publish(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Publish specific mod (or all if not specified)"),
) -> None:
    """Build and publish mods to website download directory.

    Builds mods and copies the output DLLs to the maps website's static
    directory for public download. Run this before building/deploying the
    maps website to include the latest mod versions.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Publish[/bold cyan]", border_style="cyan"))
    console.print()

    # First build all mods
    console.print("[bold]Building mods...[/bold]")
    _build_mods_internal(cli_ctx, mod)

    publish_dir = _get_mod_publish_dir(cli_ctx)
    publish_dir.mkdir(parents=True, exist_ok=True)

    console.print()
    console.print("[bold]Publishing to website...[/bold]")
    console.print(f"[dim]Target: {publish_dir}[/dim]")
    console.print()

    # Determine which mods to publish
    mods_to_publish = [mod] if mod else list(MODS.keys())

    for mod_id in mods_to_publish:
        output_dir = _get_mod_output_dir(cli_ctx, mod_id)
        dll_name = MODS[mod_id]["dll_name"]
        mod_dll = output_dir / dll_name
        if not mod_dll.exists():
            console.print(f"[red]Error: Mod DLL not found: {mod_dll}[/red]")
            raise typer.Exit(1)

        target = publish_dir / dll_name
        shutil.copy2(mod_dll, target)

        # Get file size for user feedback
        size_bytes = mod_dll.stat().st_size
        size_kb = size_bytes / 1024
        console.print(f"  [green]✓[/green] {dll_name} ({size_kb:.1f} KB)")

    # Verify metadata is present
    metadata_file = cli_ctx.repo_root / "src" / "maps" / "static" / "mods-metadata.json"
    if not metadata_file.exists():
        console.print(f"[red]Error: Metadata file not found: {metadata_file}[/red]")
        console.print("[dim]This should have been created by the build step.[/dim]")
        raise typer.Exit(1)

    console.print()
    console.print(f"[green]✓[/green] Metadata synced: {metadata_file}")
    console.print()
    console.print("[green]Publish complete![/green]")
    console.print(f"[dim]Ready for website deployment: DLLs and metadata in {publish_dir.parent}[/dim]")
    console.print()


def _get_thunderstore_version(namespace: str, name: str) -> str:
    """Compute the next Thunderstore version in YYYY.MDD.R format.

    Queries the Thunderstore API for the latest published version. If
    the latest version has the same YYYY.MDD prefix as today, increments
    the revision. Otherwise starts at revision 0.
    """
    now = datetime.now(UTC)
    date_prefix = f"{now.year}.{now.month}{now.day:02d}"

    # Query Thunderstore for latest version
    url = f"https://thunderstore.io/api/experimental/package/{namespace}/{name}/"
    request = Request(url, headers={"User-Agent": "erenshor-cli/1.0"})
    latest_version = None
    try:
        with urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read())
            latest_version = data.get("latest", {}).get("version_number")
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        pass

    revision = 0
    if latest_version and latest_version.startswith(f"{date_prefix}."):
        with contextlib.suppress(IndexError, ValueError):
            revision = int(latest_version.split(".")[2]) + 1

    return f"{date_prefix}.{revision}"


def _check_tcli_available() -> bool:
    """Check if tcli (Thunderstore CLI) is available in PATH."""
    # tcli may be in dotnet tools dir which isn't always in PATH
    dotnet_tools = Path.home() / ".dotnet" / "tools"
    path_env = os.environ.get("PATH", "")
    if str(dotnet_tools) not in path_env:
        os.environ["PATH"] = f"{path_env}{os.pathsep}{dotnet_tools}"
    return shutil.which("tcli") is not None


@app.command()
def thunderstore(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Publish specific mod (or all Thunderstore-enabled mods)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build the package but don't upload"),
) -> None:
    """Build and publish mods to Thunderstore.

    Builds the mod, packages it with tcli, and uploads to Thunderstore.
    Only mods with a 'thunderstore' key in the MODS registry are eligible.

    Version is auto-computed as YYYY.MDD.R (CalVer). The revision R
    increments if a version with today's date already exists on Thunderstore.

    Requires tcli (dotnet tool install -g tcli) and TCLI_AUTH_TOKEN in .env.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Thunderstore Publish[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Check prerequisites
    if not _check_tcli_available():
        console.print("[red]Error: tcli not found[/red]")
        console.print("Install with: dotnet tool install -g tcli")
        raise typer.Exit(1)

    token = os.environ.get("TCLI_AUTH_TOKEN", "")
    if not dry_run and (not token or token == "your_token_here"):
        console.print("[red]Error: TCLI_AUTH_TOKEN not set[/red]")
        console.print("Set it in .env (see .env for instructions).")
        raise typer.Exit(1)

    # Find eligible mods
    if mod:
        if mod not in MODS:
            console.print(f"[red]Error: Unknown mod: {mod}[/red]")
            raise typer.Exit(1)
        if "thunderstore" not in MODS[mod]:
            console.print(f"[red]Error: {mod} is not configured for Thunderstore[/red]")
            raise typer.Exit(1)
        eligible = [mod]
    else:
        eligible = [m for m in MODS if "thunderstore" in MODS[m]]

    if not eligible:
        console.print("[yellow]No mods configured for Thunderstore publishing.[/yellow]")
        raise typer.Exit(0)

    # Build and publish each mod
    for mod_id in eligible:
        mod_config = MODS[mod_id]
        ts_id = mod_config.get("thunderstore", "")  # presence guaranteed by eligible filter
        namespace, name = ts_id.split("/")
        mod_dir = _get_mod_dir(cli_ctx, mod_id)

        # Check thunderstore.toml exists
        ts_toml = mod_dir / "thunderstore.toml"
        if not ts_toml.exists():
            console.print(f"[red]Error: {ts_toml} not found[/red]")
            raise typer.Exit(1)

        # Check icon exists
        icon_path = mod_dir / "thunderstore" / "icon.png"
        if not icon_path.exists():
            console.print(f"[red]Error: {icon_path} not found[/red]")
            raise typer.Exit(1)

        # Compute version
        console.print()
        console.print(f"[bold]{mod_config['name']}[/bold]")
        version = _get_thunderstore_version(namespace, name)
        console.print(f"  Version: [cyan]{version}[/cyan]")

        # Build with this version baked into the DLL
        # Skip ILRepack so reviewers can inspect individual DLLs
        console.print("[bold]Building...[/bold]")
        _build_mods_internal(cli_ctx, mod_id, version=version, skip_ilrepack=True)

        if dry_run:
            # Build package only
            console.print("  [dim]Building package (dry run)...[/dim]")
            result = subprocess.run(
                [
                    "tcli",
                    "build",
                    "--package-version",
                    version,
                    "--config-path",
                    str(ts_toml),
                ],
                cwd=mod_dir,
                check=False,
            )
            if result.returncode != 0:
                console.print("  [red]✗ Package build failed[/red]")
                raise typer.Exit(1)

            build_dir = mod_dir / "thunderstore" / "build"
            console.print("  [green]✓ Package built[/green]")
            console.print(f"  [dim]Output: {build_dir}[/dim]")
            console.print()
            console.print("[yellow]Dry run — not uploading.[/yellow]")
        else:
            # Build and publish
            console.print("  [dim]Publishing...[/dim]")
            result = subprocess.run(
                [
                    "tcli",
                    "publish",
                    "--package-version",
                    version,
                    "--token",
                    token,
                    "--config-path",
                    str(ts_toml),
                ],
                cwd=mod_dir,
                check=False,
            )
            if result.returncode != 0:
                console.print("  [red]✗ Publish failed[/red]")
                raise typer.Exit(1)

            console.print(f"  [green]✓ Published {namespace}-{name}-{version}[/green]")
            console.print(f"  [dim]https://thunderstore.io/c/erenshor/p/{namespace}/{name}/[/dim]")

    console.print()
    console.print("[green]Thunderstore publish complete![/green]")
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

        console.print(f"[dim]Executable: {exe_path}[/dim]")
        console.print()

        subprocess.run([str(exe_path)], check=False)
