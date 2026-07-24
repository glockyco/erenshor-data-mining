"""Mod commands for companion mod development.

This module provides commands for building and deploying companion mods:
- Copying game DLLs for compilation
- Building mods with dotnet
- Deploying to BepInEx plugins folder
- Publishing to Thunderstore
- Launching the game
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from rich.console import Console
from rich.panel import Panel

from erenshor.application.mods import local_workflow
from erenshor.application.mods.artifacts import (
    format_artifact_issues,
    is_forbidden_runtime_dll,
)
from erenshor.application.mods.catalog import LoaderName, iter_mods, lookup_mod, public_mods

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

VAULT_API_BASE = "https://erenshorvault.app/api"


@app.command()
def setup(ctx: typer.Context) -> None:
    """Provision mod compilation references."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print(Panel.fit("[bold cyan]Mod Setup[/bold cyan]", border_style="cyan"))
    console.print()
    try:
        result = local_workflow.setup_mods(cli_ctx)
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
    import zipfile

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
            manifest_parser=_parse_thunderstore_manifest,
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


@dataclass(frozen=True)
class ThunderstoreCopy:
    source: Path
    target: PurePosixPath
    package_path: PurePosixPath


@dataclass(frozen=True)
class ThunderstoreManifest:
    path: Path
    namespace: str
    name: str
    icon: Path
    readme: Path
    changelog: Path
    outdir: Path
    copies: tuple[ThunderstoreCopy, ...]
    static_input_paths: tuple[Path, ...]
    input_paths: tuple[Path, ...]
    allowed_package_names: frozenset[str]


@dataclass(frozen=True)
class ThunderstoreRelease:
    mod_id: str
    mod_dir: Path
    manifest: ThunderstoreManifest
    version: str
    static_input_hashes: tuple[tuple[Path, str], ...] = ()
    input_hashes: tuple[tuple[Path, str], ...] = ()


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (ValueError, FileNotFoundError):
        return False
    return True


def _resolve_manifest_file(raw: object, *, mod_dir: Path, repo_root: Path, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"{label} must be a relative path")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError(f"{label} must be a relative path")
    unresolved = mod_dir / candidate
    if unresolved.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = unresolved.resolve(strict=False)
    if not _path_within(resolved, repo_root):
        raise ValueError(f"{label} is outside the repository")
    return resolved


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} is not a regular file: {path}")


def _parse_thunderstore_manifest(
    manifest_path: Path,
    mod_dir: Path,
    repo_root: Path,
    *,
    expected_namespace: str | None = None,
    expected_name: str | None = None,
) -> ThunderstoreManifest:
    """Parse and validate one Thunderstore manifest without requiring build outputs."""
    if manifest_path.is_symlink():
        raise ValueError("Thunderstore manifest must not be a symlink")
    manifest_path = manifest_path.resolve(strict=False)
    mod_dir = mod_dir.resolve(strict=True)
    repo_root = repo_root.resolve(strict=True)
    if not _path_within(manifest_path, mod_dir) or not _path_within(manifest_path, repo_root):
        raise ValueError("Thunderstore manifest must be inside the mod and repository")
    _require_regular_file(manifest_path, "Thunderstore manifest")
    try:
        with manifest_path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid Thunderstore TOML: {exc}") from exc

    package = data.get("package")
    build = data.get("build")
    if not isinstance(package, dict) or not isinstance(build, dict):
        raise ValueError("Thunderstore TOML requires [package] and [build] tables")
    namespace = package.get("namespace")
    name = package.get("name")
    if not isinstance(namespace, str) or not namespace or not isinstance(name, str) or not name:
        raise ValueError("Thunderstore package namespace and name are required")
    if expected_namespace is not None and namespace != expected_namespace:
        raise ValueError(f"manifest namespace is {namespace!r}, expected {expected_namespace!r}")
    if expected_name is not None and name != expected_name:
        raise ValueError(f"manifest name is {name!r}, expected {expected_name!r}")

    icon = _resolve_manifest_file(build.get("icon"), mod_dir=mod_dir, repo_root=repo_root, label="build.icon")
    readme = _resolve_manifest_file(build.get("readme"), mod_dir=mod_dir, repo_root=repo_root, label="build.readme")
    changelog = _resolve_manifest_file(
        build.get("changelog"), mod_dir=mod_dir, repo_root=repo_root, label="build.changelog"
    )
    outdir = _resolve_manifest_file(build.get("outdir"), mod_dir=mod_dir, repo_root=repo_root, label="build.outdir")
    if outdir.exists() and (not outdir.is_dir() or outdir.is_symlink()):
        raise ValueError(f"build.outdir is not a directory: {outdir}")
    for label, path in (("build.icon", icon), ("build.readme", readme), ("build.changelog", changelog)):
        _require_regular_file(path, label)

    copies_raw = build.get("copy", [])
    if not isinstance(copies_raw, list):
        raise ValueError("build.copy must be an array of tables")
    copies: list[ThunderstoreCopy] = []
    package_names: set[str] = {"manifest.json", "icon.png", "README.md", "CHANGELOG.md"}
    for index, entry in enumerate(copies_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"build.copy[{index}] must be a table")
        source = _resolve_manifest_file(
            entry.get("source"), mod_dir=mod_dir, repo_root=repo_root, label=f"build.copy[{index}].source"
        )
        if source.exists() and (not source.is_file() or source.is_symlink()):
            raise ValueError(f"build.copy[{index}].source is not a regular file: {source}")
        if is_forbidden_runtime_dll(source.name):
            raise ValueError(f"build.copy[{index}].source is a game/runtime DLL: {source.name}")
        source_relative = source.relative_to(repo_root)
        if source_relative.parts and source_relative.parts[0] == "variants":
            raise ValueError(f"build.copy[{index}].source must not use variant game assets")
        target_raw = entry.get("target")
        if not isinstance(target_raw, str) or not target_raw or "\\" in target_raw:
            raise ValueError(f"build.copy[{index}].target must be a relative POSIX path")
        if target_raw.startswith("/") or ":" in target_raw:
            raise ValueError(f"build.copy[{index}].target must be a relative POSIX path")
        target_parts = target_raw.rstrip("/").split("/")
        if any(part in {"", ".", ".."} for part in target_parts):
            raise ValueError(f"build.copy[{index}].target must be a normalized relative POSIX path")
        target = PurePosixPath(target_raw.rstrip("/"))
        if not target.parts or any(part in {"", ".", ".."} for part in target.parts):
            raise ValueError(f"build.copy[{index}].target must be a normalized relative POSIX path")
        package_path = target / source.name
        package_name = package_path.as_posix()
        if package_name in package_names:
            raise ValueError(f"duplicate Thunderstore package path: {package_name}")
        package_names.add(package_name)
        copies.append(ThunderstoreCopy(source, target, package_path))

    static_input_paths = (manifest_path, icon, readme, changelog)
    input_paths = static_input_paths + tuple(copy.source for copy in copies)
    return ThunderstoreManifest(
        path=manifest_path,
        namespace=namespace,
        name=name,
        icon=icon,
        readme=readme,
        changelog=changelog,
        outdir=outdir,
        copies=tuple(copies),
        static_input_paths=static_input_paths,
        input_paths=input_paths,
        allowed_package_names=frozenset(package_names),
    )


def _hash_paths(paths: tuple[Path, ...]) -> tuple[tuple[Path, str], ...]:
    hashes: list[tuple[Path, str]] = []
    for path in paths:
        _require_regular_file(path, "Thunderstore build input")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes.append((path, digest.hexdigest()))
    return tuple(hashes)


def _hash_release_inputs(manifest: ThunderstoreManifest) -> tuple[tuple[Path, str], ...]:
    """Hash the manifest and every declared build input after a successful build."""
    return _hash_paths(manifest.input_paths)


def _require_unchanged_inputs(hashes: tuple[tuple[Path, str], ...]) -> None:
    current = dict(_hash_paths(tuple(path for path, _ in hashes)))
    for path, expected in hashes:
        if current.get(path) != expected:
            raise ValueError(f"Thunderstore input changed during release: {path}")


def _thunderstore_package_path(manifest: ThunderstoreManifest, version: str) -> Path:
    return manifest.outdir / f"{manifest.namespace}-{manifest.name}-{version}.zip"


def _remove_stale_thunderstore_package(manifest: ThunderstoreManifest, version: str) -> None:
    package = _thunderstore_package_path(manifest, version)
    if package.is_symlink() or (package.exists() and not package.is_file()):
        raise ValueError(f"expected package output is not a regular file: {package}")
    package.unlink(missing_ok=True)


def _locate_thunderstore_package(manifest: ThunderstoreManifest, version: str) -> Path:
    expected = _thunderstore_package_path(manifest, version)
    matches = [path for path in manifest.outdir.glob(expected.name) if path.is_file() and not path.is_symlink()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one package ZIP {expected.name} in {manifest.outdir}")
    package = matches[0].resolve(strict=True)
    if not _path_within(package, manifest.outdir):
        raise ValueError("Thunderstore package is outside its configured output directory")
    return package


def _include_thunderstore_changelog(package: Path, manifest: ThunderstoreManifest) -> None:
    """Add the declared changelog that current tcli versions omit."""
    changelog_name = "CHANGELOG.md"
    changelog = manifest.changelog.read_bytes()
    try:
        with zipfile.ZipFile(package, mode="a") as archive:
            matching_entries = [info for info in archive.infolist() if info.filename == changelog_name]
            if len(matching_entries) > 1:
                raise ValueError("package contains duplicate CHANGELOG.md entries")
            if matching_entries:
                if archive.read(changelog_name) != changelog:
                    raise ValueError("package CHANGELOG.md does not match build.changelog")
                return

            info = zipfile.ZipInfo(changelog_name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, changelog, compress_type=zipfile.ZIP_DEFLATED)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"could not add Thunderstore changelog: {exc}") from exc


def _validate_thunderstore_package(package: Path, manifest: ThunderstoreManifest) -> None:
    if not _path_within(package, manifest.outdir):
        raise ValueError("Thunderstore package is outside its configured output directory")
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid Thunderstore package ZIP: {exc}") from exc
    names: list[str] = []
    for info in infos:
        name = info.filename
        if not name or "\\" in name or name.startswith("/"):
            raise ValueError(f"invalid package path: {name!r}")
        path = PurePosixPath(name)
        if any(part in {"", ".", ".."} for part in path.parts) or info.is_dir() or name.endswith("/"):
            raise ValueError(f"invalid package entry: {name!r}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink is not allowed in package: {name}")
        if is_forbidden_runtime_dll(path.name):
            raise ValueError(f"game/runtime DLL is not allowed in package: {name}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("package contains duplicate entries")
    actual = set(names)
    allowed = set(manifest.allowed_package_names)
    if actual - allowed:
        raise ValueError(f"package contains unexpected entries: {', '.join(sorted(actual - allowed))}")
    required = {"manifest.json", "icon.png", "README.md", "CHANGELOG.md"} | {
        copy.package_path.as_posix() for copy in manifest.copies
    }
    missing = required - actual
    if missing:
        raise ValueError(f"package is missing entries: {', '.join(sorted(missing))}")
    try:
        with zipfile.ZipFile(package) as archive:
            packaged_changelog = archive.read("CHANGELOG.md")
        declared_changelog = manifest.changelog.read_bytes()
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"could not verify Thunderstore changelog: {exc}") from exc
    if packaged_changelog != declared_changelog:
        raise ValueError("package CHANGELOG.md does not match build.changelog")


def _next_calver_revision(date_prefix: str, latest_version: str | None) -> str:
    """Next CalVer version for ``date_prefix`` (YYYY.MDD.R).

    Increments the revision when ``latest_version`` already uses today's date
    prefix; otherwise starts at revision 0.
    """
    revision = 0
    if latest_version and latest_version.startswith(f"{date_prefix}."):
        with contextlib.suppress(IndexError, ValueError):
            revision = int(latest_version.split(".")[2]) + 1
    return f"{date_prefix}.{revision}"


def _latest_calver_for_prefix(versions: list[str], date_prefix: str) -> str | None:
    """Highest ``YYYY.MDD.R`` version matching ``date_prefix``, or None.

    Order-independent: selects by maximum revision rather than list position,
    since registry responses do not guarantee ordering.
    """

    def revision(version: str) -> int:
        try:
            return int(version.split(".")[2])
        except (IndexError, ValueError):
            return -1

    matching = [v for v in versions if v.startswith(f"{date_prefix}.")]
    return max(matching, key=revision) if matching else None


def _get_vault_version(mod_ref: str) -> str:
    """Compute the next Erenshor Vault version (YYYY.MDD.R) for a mod.

    Queries the Vault for published versions and increments the revision when
    today's date prefix already exists. Returns revision 0 when the mod has no
    versions yet or the lookup fails.
    """
    now = datetime.now(UTC)
    date_prefix = f"{now.year}.{now.month}{now.day:02d}"
    url = f"{VAULT_API_BASE}/mods/{mod_ref}/versions"
    request = Request(url, headers={"User-Agent": "erenshor-cli/1.0"})
    versions: list[str] = []
    try:
        with urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read())
        versions = [str(v["version"]) for v in data.get("versions", []) if v.get("version")]
    except (HTTPError, URLError, json.JSONDecodeError, KeyError, TypeError):
        pass
    return _next_calver_revision(date_prefix, _latest_calver_for_prefix(versions, date_prefix))


def _get_thunderstore_version(namespace: str, name: str) -> str:
    """Compute the next Thunderstore version, failing on lookup/API errors."""
    now = datetime.now(UTC)
    date_prefix = f"{now.year}.{now.month}{now.day:02d}"
    url = f"https://thunderstore.io/api/experimental/package/{namespace}/{name}/"
    request = Request(url, headers={"User-Agent": "erenshor-cli/1.0"})
    try:
        with urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, dict) or not isinstance(data.get("latest"), dict):
            raise ValueError("response has no latest package record")
        latest_version = data["latest"].get("version_number")
        if not isinstance(latest_version, str) or not latest_version.strip():
            raise ValueError("response has no version_number")
        parts = latest_version.split(".")
        if (
            len(parts) != 3
            or len(parts[0]) != 4
            or len(parts[1]) not in {3, 4}
            or any(not part.isdigit() for part in parts)
        ):
            raise ValueError(f"invalid version_number: {latest_version!r}")
        month = int(parts[1][:-2])
        day = int(parts[1][-2:])
        if not 1 <= month <= 12 or not 1 <= day <= 31:
            raise ValueError(f"invalid version_number: {latest_version!r}")
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(f"Thunderstore version lookup failed for {namespace}/{name}: {exc}") from exc
    return _next_calver_revision(date_prefix, latest_version)


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
    mod: str | None = typer.Option(
        None,
        "--mod",
        help="Publish one mod; omit only with --dry-run to package all public mods",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build the package but don't upload"),
) -> None:
    """Package and optionally publish BepInEx mods to Thunderstore.

    Builds each selected mod's BepInEx target, packages it with tcli, and
    validates the resulting archive. A dry run may omit --mod to package all
    four public mods without uploading. A real upload requires exactly one
    public --mod and a non-placeholder TCLI_AUTH_TOKEN from the environment or
    repository-local .env file.

    Version is auto-computed as YYYY.MDD.R (CalVer). The revision R
    increments if a version with today's date already exists on Thunderstore.

    tcli is required (install with: dotnet tool install -g tcli).
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

    if not _check_tcli_available():
        console.print("[red]Error: tcli not found[/red]")
        console.print("Install with: dotnet tool install -g tcli")
        raise typer.Exit(1)

    token = os.environ.get("TCLI_AUTH_TOKEN", "")
    if not dry_run and mod is None:
        console.print("[red]Error: real Thunderstore publishing requires exactly one --mod[/red]")
        raise typer.Exit(1)
    placeholder_tokens = {"your_token_here", "your-token-here", "changeme"}
    if not dry_run and (not token.strip() or token.strip().lower() in placeholder_tokens):
        console.print("[red]Error: TCLI_AUTH_TOKEN is missing or still a placeholder[/red]")
        raise typer.Exit(1)

    if mod is not None:
        try:
            definition = lookup_mod(mod)
        except KeyError:
            console.print(f"[red]Error: Unknown mod: {mod}[/red]")
            raise typer.Exit(1) from None
        if not definition.public or definition.thunderstore_id is None:
            console.print(f"[red]Error: {mod} is not configured for Thunderstore[/red]")
            raise typer.Exit(1)
        selected = [mod]
    else:
        selected = [definition.mod_id for definition in public_mods() if definition.thunderstore_id is not None]

    releases: list[ThunderstoreRelease] = []
    # Preflight every release, including version lookups, before any build starts.
    for mod_id in selected:
        definition = lookup_mod(mod_id)
        ts_id = definition.thunderstore_id
        if not ts_id or ts_id.count("/") != 1:
            console.print(f"[red]Error: invalid Thunderstore id for {mod_id}[/red]")
            raise typer.Exit(1)
        namespace, name = ts_id.split("/", 1)
        mod_dir = local_workflow.mod_dir(cli_ctx, mod_id).resolve(strict=False)
        manifest_path = mod_dir / "thunderstore.toml"
        try:
            manifest = _parse_thunderstore_manifest(
                manifest_path,
                mod_dir,
                cli_ctx.repo_root,
                expected_namespace=namespace,
                expected_name=name,
            )
            version = _get_thunderstore_version(namespace, name)
            static_hashes = _hash_paths(manifest.static_input_paths)
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        releases.append(
            ThunderstoreRelease(
                mod_id,
                mod_dir,
                manifest,
                version,
                static_input_hashes=static_hashes,
            )
        )

    built_releases: list[ThunderstoreRelease] = []
    for release in releases:
        console.print()
        console.print(f"[bold]{lookup_mod(release.mod_id).display_name}[/bold]")
        console.print(f"  Version: [cyan]{release.version}[/cyan]")
        console.print("[bold]Building...[/bold]")
        try:
            _require_unchanged_inputs(release.static_input_hashes)
            local_workflow.build_mods(
                cli_ctx, release.mod_id, version=release.version, loader="bepinex", runner=subprocess.run
            )
            _require_unchanged_inputs(release.static_input_hashes)
            hashes = _hash_release_inputs(release.manifest)
        except (OSError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        built_releases.append(
            ThunderstoreRelease(
                release.mod_id,
                release.mod_dir,
                release.manifest,
                release.version,
                static_input_hashes=release.static_input_hashes,
                input_hashes=hashes,
            )
        )

    # Package and validate every release before any upload.
    packages: list[tuple[ThunderstoreRelease, Path, tuple[tuple[Path, str], ...]]] = []
    for release in built_releases:
        console.print("  [dim]Building package...[/dim]")
        try:
            _require_unchanged_inputs(release.input_hashes)
            _remove_stale_thunderstore_package(release.manifest, release.version)
        except (OSError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        try:
            result = subprocess.run(
                [
                    "tcli",
                    "build",
                    "--package-version",
                    release.version,
                    "--config-path",
                    str(release.manifest.path),
                ],
                cwd=release.mod_dir,
                check=False,
            )
        except OSError as exc:
            console.print(f"  [red]✗ Could not run tcli build: {exc}[/red]")
            raise typer.Exit(1) from exc
        if result.returncode != 0:
            console.print("  [red]✗ Package build failed[/red]")
            raise typer.Exit(1)
        try:
            _require_unchanged_inputs(release.input_hashes)
            package = _locate_thunderstore_package(release.manifest, release.version)
            _include_thunderstore_changelog(package, release.manifest)
            _validate_thunderstore_package(package, release.manifest)
            package_hashes = _hash_paths((package,))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        packages.append((release, package, package_hashes))
        console.print(f"  [green]✓ Package validated[/green] [dim]{package}[/dim]")

    if dry_run:
        console.print()
        console.print("[yellow]Dry run — not uploading.[/yellow]")
        console.print()
        return

    for release, package, package_hashes in packages:
        try:
            _require_unchanged_inputs(release.input_hashes)
            _require_unchanged_inputs(package_hashes)
        except (OSError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        namespace, name = (lookup_mod(release.mod_id).thunderstore_id or "").split("/", 1)
        try:
            result = subprocess.run(
                [
                    "tcli",
                    "publish",
                    "--file",
                    str(package),
                    "--config-path",
                    str(release.manifest.path),
                ],
                cwd=release.mod_dir,
                check=False,
                env={**os.environ, "TCLI_AUTH_TOKEN": token},
            )
        except OSError as exc:
            console.print(f"  [red]✗ Could not run tcli publish: {exc}[/red]")
            raise typer.Exit(1) from exc
        if result.returncode != 0:
            console.print("  [red]✗ Publish failed[/red]")
            raise typer.Exit(1)
        console.print(f"  [green]✓ Published {namespace}-{name}-{release.version}[/green]")
        console.print(f"  [dim]https://thunderstore.io/c/erenshor/p/{namespace}/{name}/[/dim]")

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
    """Build a native Lunaris mod for an Erenshor Vault release.

    Derives the next version (YYYY.MDD.R) from the Vault so the patch revision is
    never hand-edited, and bakes it into the DLL's PluginInfo.Version. That value
    flows to the [LunarisPlugin] attribute Lunaris compares for updates, so the
    installed version matches what is published (otherwise Lunaris shows a
    perpetual "update available"). Verifies vault/CHANGELOG.md leads with the
    same version.

    The Vault write API is not available yet, so this prepares the release:
    upload the built DLL at erenshorvault.app with the printed version and
    changelog. Automated upload slots in here once the Vault PAT API ships.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Erenshor Vault Release[/bold cyan]", border_style="cyan"))
    console.print()

    def has_listing(mod_id: str) -> bool:
        return (local_workflow.mod_dir(cli_ctx, mod_id) / "vault" / "vault.toml").exists()

    if mod:
        try:
            lookup_mod(mod)
        except KeyError:
            console.print(f"[red]Error: Unknown mod: {mod}[/red]")
            raise typer.Exit(1) from None
        if not has_listing(mod):
            console.print(f"[red]Error: {mod} has no vault/vault.toml listing[/red]")
            raise typer.Exit(1)
        eligible = [mod]
    else:
        eligible = [definition.mod_id for definition in iter_mods() if has_listing(definition.mod_id)]

    if not eligible:
        console.print("[yellow]No mods have a vault/vault.toml listing.[/yellow]")
        raise typer.Exit(0)

    for mod_id in eligible:
        mod_dir = local_workflow.mod_dir(cli_ctx, mod_id)
        config = tomllib.loads((mod_dir / "vault" / "vault.toml").read_text())
        mod_ref = config["mod"]["mod_ref"]

        definition = lookup_mod(mod_id)
        console.print(f"[bold]{definition.display_name}[/bold]")
        version = _get_vault_version(mod_ref)
        console.print(f"  Version: [cyan]{version}[/cyan]  (mod_ref: {mod_ref})")

        changelog = (mod_dir / "vault" / "CHANGELOG.md").read_text()
        headings = [ln for ln in changelog.splitlines() if ln.startswith("## v")]
        top = headings[0].removeprefix("## v").strip() if headings else ""
        if top != version:
            console.print(
                f"  [yellow]⚠ CHANGELOG.md leads with v{top or '(none)'}; expected v{version}. "
                f"Update it before uploading.[/yellow]"
            )

        console.print("[bold]Building...[/bold]")
        local_workflow.build_mods(cli_ctx, mod_id, version=version, loader="lunaris", runner=subprocess.run)

        dll = local_workflow.mod_output_dir(cli_ctx, mod_id, "lunaris") / definition.dll_name
        console.print(f"  [green]✓[/green] {dll}")
        console.print()
        console.print("  [bold]Upload (manual until the Vault write API ships):[/bold]")
        console.print(f"    1. erenshorvault.app -> new version for '{mod_ref}', version [cyan]{version}[/cyan]")
        console.print(f"    2. Main file: {dll.name}  (no asset files)")
        console.print("    3. Changelog: the top entry of vault/CHANGELOG.md")
        console.print()

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
        local_workflow.launch_game(cli_ctx, runner=subprocess.run)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
