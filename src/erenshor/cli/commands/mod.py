"""Mod commands for companion mod development.

This module provides commands for building and deploying companion mods:
- Copying game DLLs for compilation
- Building mods with dotnet
- Deploying to BepInEx plugins folder
- Publishing to Thunderstore
- Launching the game
"""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from rich.console import Console
from rich.panel import Panel

from erenshor.application.mods import local_workflow, release
from erenshor.application.mods.artifacts import format_artifact_issues
from erenshor.application.mods.catalog import LoaderName, lookup_mod

if TYPE_CHECKING:
    from ..context import CLIContext


BuildLoader = Literal["default", "bepinex", "lunaris", "all"]
DeployLoader = Literal["default", "bepinex", "lunaris"]

app = typer.Typer(
    name="mod",
    help="Build and deploy companion mods",
    no_args_is_help=True,
)

console = Console()

CROSSOVER_BOTTLES_ROOT = Path.home() / "Library/Application Support/CrossOver/Bottles"
CROSSOVER_START = Path("/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/cxstart")
LOADER_PROXY_CANDIDATES: dict[LoaderName, tuple[str, ...]] = {
    "bepinex": (
        "winhttp.bepinex.dll",
        "winhttp.bepinex-backup.dll",
        "winhttp.dll.bepinex-backup",
    ),
    "lunaris": ("winhttp.lunaris.dll",),
}


@app.command()
def setup(
    ctx: typer.Context,
    mod: Annotated[str | None, typer.Option("--mod", help="Set up one mod (or all if not specified)")] = None,
    loader: Annotated[
        BuildLoader,
        typer.Option("--loader", help="Set up target: default, bepinex, lunaris, or all"),
    ] = "all",
) -> None:
    """Provision mod compilation references."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print(Panel.fit("[bold cyan]Mod Setup[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        result = local_workflow.setup_mods(cli_ctx, mod, loader=loader)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[dim]Source: {local_workflow.managed_dir(result.game_path)}[/dim]")
    console.print()
    console.print("[green]Setup complete![/green]")
    console.print()


@app.command(name="dev-setup")
def dev_setup(ctx: typer.Context) -> None:
    """Install development tools for mod hot reload and config editing.

    Downloads and installs:
    - ScriptEngine: press F6 in game to reload mods from BepInEx/scripts/
    - ConfigurationManager: press F1 in game to edit mod config values

    Also creates the BepInEx/scripts/ directory for hot reload.

    Safe to run multiple times (idempotent). Requires BepInEx installed.
    Run 'erenshor mod setup' first to copy game DLLs.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Dev Setup[/bold cyan]", border_style="cyan"))
    console.print()

    game_path = local_workflow.get_game_path(cli_ctx)
    if not game_path:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        console.print("Install the selected Steam app or set [variants.<name>] game_install.")
        raise typer.Exit(1)

    bepinex_dir = game_path / "BepInEx"
    if not bepinex_dir.exists():
        console.print(f"[red]Error: BepInEx not installed at {bepinex_dir}[/red]")
        console.print("Install BepInEx to your game first.")
        raise typer.Exit(1)

    plugins_dir = local_workflow.bepinex_plugins_dir(game_path)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = local_workflow.bepinex_scripts_dir(game_path)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    import tempfile

    dev_tools = cli_ctx.config.global_.bepinex_dev_tools
    if dev_tools is None:
        console.print("[red]Error: [global.bepinex_dev_tools] not configured in config.toml[/red]")
        raise typer.Exit(1)

    tools = [
        ("ScriptEngine", dev_tools.script_engine_url, "ScriptEngine.dll"),
        ("ConfigurationManager", dev_tools.config_manager_url, "ConfigurationManager.dll"),
    ]

    for name, url, check_dll in tools:
        # Check if already installed
        if (plugins_dir / check_dll).exists():
            console.print(f"  [dim]\u2713 {name} already installed[/dim]")
            continue

        console.print(f"  Downloading {name}...")
        try:
            req = Request(url, headers={"User-Agent": "erenshor-cli"})
            with urlopen(req, timeout=30) as resp:
                zip_data = resp.read()
        except (HTTPError, URLError, TimeoutError) as e:
            console.print(f"  [red]\u2717 Failed to download {name}: {e}[/red]")
            continue

        # Extract DLL(s) from zip into plugins/
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / f"{name}.zip"
            zip_path.write_bytes(zip_data)
            with zipfile.ZipFile(zip_path) as zf:
                for entry in zf.namelist():
                    if entry.endswith(".dll"):
                        dll_filename = Path(entry).name
                        target = plugins_dir / dll_filename
                        target.write_bytes(zf.read(entry))
                        console.print(f"  [green]\u2713[/green] {dll_filename}")

    console.print()
    console.print("[green]Dev setup complete![/green]")
    console.print()
    console.print("[bold]Development workflow:[/bold]")
    console.print("  1. [cyan]erenshor mod build --mod <id>[/cyan]")
    console.print("  2. [cyan]erenshor mod deploy --mod <id> --scripts[/cyan]")
    console.print("  3. Press [bold]F6[/bold] in game to hot reload")
    console.print("  4. Press [bold]F1[/bold] in game to edit config values")
    console.print()


@app.command()
def build(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Build specific mod (or all if not specified)"),
    loader: Annotated[
        BuildLoader,
        typer.Option("--loader", help="Build target: default, bepinex, lunaris, or all"),
    ] = "default",
) -> None:
    """Build companion mods for one loader target or all loader targets."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print(Panel.fit("[bold cyan]Mod Build[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        result = local_workflow.build_mods(cli_ctx, mod, loader=loader, runner=subprocess.run)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    if result.failed:
        console.print(f"[red]Build failed for: {', '.join(result.failed)}[/red]")
        raise typer.Exit(1)
    if result.artifact_issues:
        console.print("[red]Artifact verification failed:[/red]")
        for diagnostic in format_artifact_issues(result.artifact_issues).splitlines():
            console.print(f"  ✗ {diagnostic}", style="red", markup=False)
        raise typer.Exit(1)
    console.print("[green]Build complete![/green]")
    console.print()


@app.command()
def status(ctx: typer.Context) -> None:
    """Show native loader availability and the active loader for one variant."""
    cli_ctx: CLIContext = ctx.obj
    game_path = local_workflow.get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)
    console.print()
    console.print(Panel.fit("[bold cyan]Mod Loader Status[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()
    try:
        active, loaders = local_workflow.loader_status(game_path)
        active_label = active or "none"
        style = "green" if active in {"bepinex", "lunaris"} else "yellow"
        console.print(f"Active loader: [{style}]{active_label}[/{style}]")
        for loader_name, source in loaders:
            availability = f"available ({source.name})" if source is not None else "not installed"
            console.print(f"  {loader_name}: {availability}")
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print()


@app.command()
def activate(
    ctx: typer.Context,
    loader: Annotated[LoaderName, typer.Option("--loader", help="Native loader to activate")],
) -> None:
    """Activate BepInEx or Lunaris for the selected game variant."""
    cli_ctx: CLIContext = ctx.obj
    game_path = local_workflow.get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)
    console.print()
    console.print(Panel.fit("[bold cyan]Activate Mod Loader[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()
    try:
        changed = local_workflow.activate_loader(game_path, loader)
        if changed:
            console.print(f"[green]Activated {loader}.[/green] Restart the game before testing.")
        else:
            console.print(f"[dim]{loader} is already active.[/dim]")
        active, loaders = local_workflow.loader_status(game_path)
        active_label = active or "none"
        style = "green" if active in {"bepinex", "lunaris"} else "yellow"
        console.print(f"Active loader: [{style}]{active_label}[/{style}]")
        for loader_name, source in loaders:
            availability = f"available ({source.name})" if source is not None else "not installed"
            console.print(f"  {loader_name}: {availability}")
    except (OSError, ValueError, RuntimeError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print()


@app.command()
def deploy(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Deploy specific mod (or all if not specified)"),
    loader: Annotated[
        DeployLoader,
        typer.Option("--loader", help="Deploy target: default, bepinex, or lunaris"),
    ] = "default",
    scripts: bool = typer.Option(False, "--scripts", help="Deploy to BepInEx/scripts/ for hot reload (BepInEx only)"),
) -> None:
    """Build and deploy mods to an explicit loader directory."""
    cli_ctx: CLIContext = ctx.obj
    game_path = local_workflow.get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)
    console.print()
    console.print(Panel.fit("[bold cyan]Mod Deploy[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print()
    try:
        selection = local_workflow.plan_deploy(mod, loader, game_path, scripts=scripts)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print("[bold]Building mods...[/bold]")
    try:
        build_result = local_workflow.build_mods(cli_ctx, mod, loader=loader, runner=subprocess.run)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    if build_result.failed:
        console.print(f"[red]Build failed for: {', '.join(build_result.failed)}[/red]")
        raise typer.Exit(1)
    if build_result.artifact_issues:
        console.print("[red]Artifact verification failed:[/red]")
        for diagnostic in format_artifact_issues(build_result.artifact_issues).splitlines():
            console.print(f"  ✗ {diagnostic}", style="red", markup=False)
        raise typer.Exit(1)
    try:
        plan = local_workflow.prepare_deploy(
            cli_ctx,
            selection,
            manifest_parser=release.parse_thunderstore_manifest,
        )
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print()
    console.print("[bold]Deploying...[/bold]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()
    try:
        for mod_id, selected_loader in plan.targets:
            definition = lookup_mod(mod_id)
            _target_dir, deploy_label, _copy_pdb = local_workflow.deploy_target_dir(
                selected_loader, game_path, scripts=scripts
            )
            console.print(f"[bold]{definition.display_name} ({selected_loader}) → {deploy_label}[/bold]")
        result = local_workflow.deploy_mods(plan)
    except (OSError, ValueError, RuntimeError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    for file in result.copied:
        size_kb = file.source.stat().st_size / 1024
        console.print(f"  [green]✓[/green] {file.target.relative_to(game_path)} ({size_kb:.1f} KB)")
    for path in result.removed_conflicts:
        console.print(f"  [dim]removed stale {path.name} from {path.parent}[/dim]")
    action = "Activated" if result.loader_changed else "Already active"
    console.print()
    console.print(f"[green]{action}: {plan.target_loader}[/green]")
    console.print("[green]Deploy complete![/green]")
    console.print("[dim]Restart the game before testing a newly selected loader.[/dim]")
    console.print()


@app.command()
def thunderstore(
    ctx: typer.Context,
    mod: str | None = typer.Option(
        None,
        "--mod",
        help="Publish one mod; omit only with --dry-run to package all public mods",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build the package but don't upload"),
) -> None:
    """Package and optionally publish BepInEx mods to Thunderstore."""
    cli_ctx: CLIContext = ctx.obj
    token = os.environ.get("TCLI_AUTH_TOKEN", "")
    console.print()
    console.print(Panel.fit("[bold cyan]Thunderstore Publish[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        plan = release.plan_thunderstore(
            cli_ctx,
            mod,
            dry_run=dry_run,
            token=token,
            tcli_available=release.check_tcli_available,
            version_lookup=release.get_thunderstore_version,
        )
        for planned in plan.releases:
            console.print(f"[bold]{lookup_mod(planned.mod_id).display_name}[/bold]")
            console.print(f"  Version: [cyan]{planned.version}[/cyan]")
        built_plan = release.build_thunderstore(
            cli_ctx,
            plan,
            build_client=local_workflow.build_mods,
            runner=subprocess.run,
        )
        packages = release.package_thunderstore(built_plan, runner=subprocess.run)
        for package in packages:
            console.print(f"  [green]✓ Package validated[/green] [dim]{package.path}[/dim]")
        if dry_run:
            console.print()
            console.print("[yellow]Dry run — not uploading.[/yellow]")
            console.print()
            return
        published = release.publish_thunderstore(packages, token, runner=subprocess.run)
        for package in published:
            manifest = package.release.manifest
            console.print(
                f"  [green]✓ Published {manifest.namespace}-{manifest.name}-{package.release.version}[/green]"
            )
            console.print(f"  [dim]https://thunderstore.io/c/erenshor/p/{manifest.namespace}/{manifest.name}/[/dim]")
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print()
    console.print("[green]Thunderstore publish complete![/green]")
    console.print()


@app.command()
def vault(
    ctx: typer.Context,
    mod: str | None = typer.Option(
        None, "--mod", help="Build a specific Vault mod (default: all mods with a vault/ listing)"
    ),
) -> None:
    """Build a native Lunaris mod for an Erenshor Vault release."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print(Panel.fit("[bold cyan]Erenshor Vault Release[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        plan = release.plan_vault(cli_ctx, mod, version_lookup=release.get_vault_version)
        if not plan.releases:
            console.print("[yellow]No mods have a vault/vault.toml listing.[/yellow]")
            raise typer.Exit(0)
        for planned in plan.releases:
            definition = lookup_mod(planned.mod_id)
            console.print(f"[bold]{definition.display_name}[/bold]")
            console.print(f"  Version: [cyan]{planned.version}[/cyan]  (mod_ref: {planned.listing.mod_ref})")
            if planned.changelog_version != planned.version:
                console.print(
                    f"  [yellow]⚠ CHANGELOG.md leads with v{planned.changelog_version or '(none)'}; "
                    f"expected v{planned.version}. Update it before uploading.[/yellow]"
                )
        result = release.build_vault(
            cli_ctx,
            plan,
            build_client=local_workflow.build_mods,
            runner=subprocess.run,
        )
        for planned in result.plan.releases:
            console.print(f"  [green]✓[/green] {planned.dll}")
            console.print()
            console.print("  [bold]Upload (manual until the Vault write API ships):[/bold]")
            console.print(
                f"    1. erenshorvault.app -> new version for '{planned.listing.mod_ref}', "
                f"version [cyan]{planned.version}[/cyan]"
            )
            console.print(f"    2. Main file: {planned.dll.name}  (no asset files)")
            console.print("    3. Changelog: the top entry of vault/CHANGELOG.md")
            console.print()
    except typer.Exit:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print("[green]Vault release prepared![/green]")
    console.print()


@app.command()
def launch(ctx: typer.Context) -> None:
    """Launch the selected game through Steam."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print(Panel.fit("[bold cyan]Launch Game[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        plan = local_workflow.plan_launch(cli_ctx)
        if plan.crossover_bottle is not None:
            console.print(f"[dim]Launching through Steam in CrossOver bottle: {plan.crossover_bottle}[/dim]")
            console.print(f"[dim]Steam URL: {plan.command[-1]}[/dim]")
        else:
            console.print(f"[dim]Executable: {plan.game_path / 'Erenshor.exe'}[/dim]")
        console.print()
        local_workflow.launch_game(cli_ctx)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
