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
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Literal, NotRequired, TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from ..context import CLIContext


LoaderName = Literal["bepinex", "lunaris"]
BuildLoader = Literal["default", "bepinex", "lunaris", "all"]
DeployLoader = Literal["default", "bepinex", "lunaris"]


class ModInfo(TypedDict):
    dir: str
    name: str
    dll_name: str
    loaders: list[LoaderName]
    default_loader: LoaderName
    public: bool
    thunderstore: NotRequired[str]
    bepinex_dlls: NotRequired[list[str]]
    lunaris_dlls: NotRequired[list[str]]


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

# Mod registry - all companion mods in the project. Every mod has native build
# targets for both loaders; ``default_loader`` preserves the current install
# path used by website/default deploys.
MODS: dict[str, ModInfo] = {
    "interactive-map-companion": {
        "dir": "src/mods/InteractiveMapCompanion",
        "name": "Interactive Map Companion",
        "dll_name": "InteractiveMapCompanion.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "bepinex",
        "public": True,
        "thunderstore": "WoW_Much/InteractiveMapCompanion",
        # Harmony ships with BepInEx, not with the game — copy from BepInEx/core/
        "bepinex_dlls": ["0Harmony.dll"],
        "lunaris_dlls": ["Newtonsoft.Json.dll", "0Harmony.dll"],
    },
    "interactive-maps-companion": {
        "dir": "src/mods/InteractiveMapsCompanion",
        "name": "Interactive Maps Companion",
        "dll_name": "InteractiveMapsCompanion.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "bepinex",
        "public": False,
        "lunaris_dlls": ["Newtonsoft.Json.dll"],
    },
    "justice-for-f7": {
        "dir": "src/mods/JusticeForF7",
        "name": "Justice for F7",
        "dll_name": "JusticeForF7.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "lunaris",
        "public": True,
        "thunderstore": "WoW_Much/JusticeForF7",
        "lunaris_dlls": ["0Harmony.dll"],
    },
    "sprint": {
        "dir": "src/mods/Sprint",
        "name": "Sprint",
        "dll_name": "Sprint.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "lunaris",
        "public": True,
        "thunderstore": "WoW_Much/Sprint",
        "lunaris_dlls": ["0Harmony.dll"],
    },
    "map-tile-capture": {
        "dir": "src/mods/MapTileCapture",
        "name": "Map Tile Capture",
        "dll_name": "MapTileCapture.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "bepinex",
        "public": False,
        "bepinex_dlls": ["0Harmony.dll"],
        "lunaris_dlls": ["Newtonsoft.Json.dll", "0Harmony.dll"],
    },
    "adventure-guide": {
        "dir": "src/mods/AdventureGuide",
        "name": "Adventure Guide",
        "dll_name": "AdventureGuide.dll",
        "loaders": ["bepinex", "lunaris"],
        "default_loader": "lunaris",
        "public": True,
        "thunderstore": "WoW_Much/AdventureGuide",
        "bepinex_dlls": ["0Harmony.dll"],
        "lunaris_dlls": [
            "ImGui.NET.dll",
            "Newtonsoft.Json.dll",
            "System.Numerics.Vectors.dll",
            "0Harmony.dll",
        ],
    },
}

# Required DLLs to copy from game
REQUIRED_DLLS = [
    "Assembly-CSharp.dll",
    "UnityEngine.dll",
    "UnityEngine.CoreModule.dll",
    "UnityEngine.InputLegacyModule.dll",
    "UnityEngine.IMGUIModule.dll",
    "UnityEngine.UIModule.dll",
    "UnityEngine.UI.dll",
    "UnityEngine.TextRenderingModule.dll",
    "UnityEngine.AIModule.dll",
    "UnityEngine.PhysicsModule.dll",
    "Unity.TextMeshPro.dll",
    "com.rlabrecque.steamworks.net.dll",
]

FORBIDDEN_RUNTIME_DLLS = frozenset(
    [*(dll.casefold() for dll in REQUIRED_DLLS), "bepinex.dll", "lunaris.dll", "0harmony.dll"]
)


def _check_dotnet_available() -> bool:
    """Check if dotnet CLI is available in PATH."""
    return shutil.which("dotnet") is not None


def _read_steam_install_dir(manifest: Path) -> str | None:
    """Read ``installdir`` from a Steam ACF manifest."""
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.debug(f"Could not read Steam manifest {manifest}: {exc}")
        return None

    for line in lines:
        if '"installdir"' not in line:
            continue
        parts = line.split('"')
        if len(parts) >= 4 and parts[3]:
            return parts[3]
    return None


def _discover_crossover_game_path(app_id: str) -> Path | None:
    """Find one Steam app inside the selected or only matching CrossOver bottle."""
    if sys.platform != "darwin":
        return None

    bottle_name = os.environ.get("CROSSOVER_BOTTLE")
    if bottle_name:
        bottle_dirs = [CROSSOVER_BOTTLES_ROOT / bottle_name]
    elif CROSSOVER_BOTTLES_ROOT.is_dir():
        bottle_dirs = sorted(path for path in CROSSOVER_BOTTLES_ROOT.iterdir() if path.is_dir())
    else:
        return None

    matches: list[Path] = []
    for bottle_dir in bottle_dirs:
        steamapps = bottle_dir / "drive_c/Program Files (x86)/Steam/steamapps"
        manifest = steamapps / f"appmanifest_{app_id}.acf"
        install_dir = _read_steam_install_dir(manifest) if manifest.is_file() else None
        if install_dir:
            candidate = steamapps / "common" / install_dir
            if (candidate / "Erenshor_Data" / "Managed").is_dir():
                matches.append(candidate)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(
            f"Steam app {app_id} is installed in multiple CrossOver bottles; "
            "set CROSSOVER_BOTTLE or the variant's game_install"
        )
    return None


def _crossover_bottle_for_path(game_path: Path) -> str | None:
    """Return the CrossOver bottle containing a discovered game path."""
    try:
        relative = game_path.resolve().relative_to(CROSSOVER_BOTTLES_ROOT.resolve())
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def _read_game_app_id(game_path: Path) -> str | None:
    app_id_file = game_path / "steam_appid.txt"
    try:
        app_id = app_id_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return app_id or None


def _get_game_path(cli_ctx: CLIContext, *, allow_extracted: bool = False) -> Path | None:
    """Resolve the selected variant's runnable game installation.

    A per-variant ``game_install`` is authoritative. Standard CrossOver Steam
    installs are then discovered by the selected variant's app ID. The legacy
    process-wide environment override and extracted ``game_files`` remain
    fallbacks for non-standard and build-only environments.
    """
    variant_config = cli_ctx.config.variants.get(cli_ctx.variant)
    if variant_config:
        resolve_install = getattr(variant_config, "resolved_game_install", None)
        configured = cast("Path | None", resolve_install(cli_ctx.repo_root)) if resolve_install else None
        if configured is not None:
            if configured.exists():
                return configured
            logger.warning(f"Configured game_install does not exist: {configured}")
            return None

        discovered = _discover_crossover_game_path(variant_config.app_id)
        if discovered is not None:
            return discovered

    env_path = os.environ.get("ERENSHOR_GAME_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            expected_app_id = variant_config.app_id if variant_config else None
            actual_app_id = _read_game_app_id(path)
            if expected_app_id is None or actual_app_id is None or actual_app_id == expected_app_id:
                return path
            logger.warning(
                f"Ignoring ERENSHOR_GAME_PATH for Steam app {actual_app_id}; "
                f"variant {cli_ctx.variant!r} requires app {expected_app_id}"
            )
        else:
            logger.warning(f"ERENSHOR_GAME_PATH set but path doesn't exist: {env_path}")

    if allow_extracted and variant_config:
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


def _get_lunaris_plugins_dir(game_path: Path) -> Path:
    """Get the native Lunaris plugins directory (next to Erenshor.exe)."""
    return game_path / "plugins"


def _get_bepinex_scripts_dir(game_path: Path) -> Path:
    """Get the BepInEx scripts directory (for ScriptEngine hot reload)."""
    return game_path / "BepInEx" / "scripts"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _loader_proxy_sources(game_path: Path) -> dict[LoaderName, Path]:
    """Resolve one unambiguous saved WinHTTP proxy for each installed loader."""
    sources: dict[LoaderName, Path] = {}
    for loader, names in LOADER_PROXY_CANDIDATES.items():
        candidates = [game_path / name for name in names if (game_path / name).exists()]
        for candidate in candidates:
            if not candidate.is_file() or candidate.is_symlink():
                raise ValueError(f"{loader} loader proxy is not a regular file: {candidate}")
        digests = {_file_sha256(candidate) for candidate in candidates}
        if len(digests) > 1:
            joined = ", ".join(str(path) for path in candidates)
            raise ValueError(f"conflicting {loader} loader proxies: {joined}")
        if candidates:
            sources[loader] = candidates[0]
    return sources


def _detect_active_loader(game_path: Path, sources: dict[LoaderName, Path]) -> LoaderName | Literal["unknown"] | None:
    """Identify the root WinHTTP proxy by exact content, without guessing."""
    active_proxy = game_path / "winhttp.dll"
    if not active_proxy.exists():
        return None
    if not active_proxy.is_file() or active_proxy.is_symlink():
        raise ValueError(f"active loader proxy is not a regular file: {active_proxy}")

    active_digest = _file_sha256(active_proxy)
    matches: list[LoaderName] = [loader for loader, source in sources.items() if _file_sha256(source) == active_digest]
    if len(matches) == 1:
        return matches[0]
    return "unknown"


def _validate_loader_activation(
    game_path: Path, loader: LoaderName
) -> tuple[dict[LoaderName, Path], LoaderName | None]:
    sources = _loader_proxy_sources(game_path)
    source = sources.get(loader)
    if source is None:
        expected = ", ".join(LOADER_PROXY_CANDIDATES[loader])
        raise ValueError(f"{loader} loader proxy not found in {game_path}; expected one of: {expected}")

    active = _detect_active_loader(game_path, sources)
    if active == "unknown":
        raise ValueError(
            f"refusing to replace unrecognized {game_path / 'winhttp.dll'}; "
            "restore it with the BepInEx or Lunaris installer first"
        )
    return sources, active


def _activate_loader(game_path: Path, loader: LoaderName) -> bool:
    """Atomically select one installed native loader's WinHTTP proxy."""
    sources, active = _validate_loader_activation(game_path, loader)
    source = sources[loader]
    if active == loader:
        return False

    import tempfile

    descriptor, temporary_name = tempfile.mkstemp(prefix=".erenshor-winhttp-", suffix=".tmp", dir=game_path)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(game_path / "winhttp.dll")
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()

    if _detect_active_loader(game_path, sources) != loader:
        raise RuntimeError(f"failed to activate {loader} loader")
    return True


def _print_loader_status(game_path: Path) -> None:
    sources = _loader_proxy_sources(game_path)
    active = _detect_active_loader(game_path, sources)
    active_label = active or "none"
    style = "green" if active in {"bepinex", "lunaris"} else "yellow"
    console.print(f"Active loader: [{style}]{active_label}[/{style}]")
    loaders: tuple[LoaderName, ...] = ("bepinex", "lunaris")
    for loader in loaders:
        source = sources.get(loader)
        availability = f"available ({source.name})" if source is not None else "not installed"
        console.print(f"  {loader}: {availability}")


def _get_mod_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    """Get the mod source directory."""
    if mod_id not in MODS:
        raise ValueError(f"Unknown mod: {mod_id}")
    return cli_ctx.repo_root / MODS[mod_id]["dir"]


def _get_mod_lib_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    """Get the mod lib directory for game DLLs."""
    return _get_mod_dir(cli_ctx, mod_id) / "lib"


def _get_mod_loader_lib_dir(cli_ctx: CLIContext, mod_id: str, loader: LoaderName) -> Path:
    """Get the isolated reference directory for a loader target."""
    if loader not in MODS[mod_id]["loaders"]:
        raise ValueError(f"{mod_id} does not support the {loader} loader")
    return _get_mod_lib_dir(cli_ctx, mod_id) / loader


def _get_mod_output_dir(
    cli_ctx: CLIContext,
    mod_id: str,
    loader: LoaderName,
    *,
    configuration: str = "Debug",
) -> Path:
    """Get the isolated build output directory for a loader target."""
    if loader not in MODS[mod_id]["loaders"]:
        raise ValueError(f"{mod_id} does not support the {loader} loader")
    return _get_mod_dir(cli_ctx, mod_id) / "bin" / configuration / "netstandard2.1" / loader


def _get_mod_publish_dir(cli_ctx: CLIContext) -> Path:
    """Get the web publish directory for mod downloads."""
    return cli_ctx.repo_root / "src" / "maps" / "static" / "mods"


@dataclass(frozen=True)
class DeployFile:
    source: Path
    target: Path


def _get_deploy_files(
    cli_ctx: CLIContext,
    mod_id: str,
    loader: LoaderName,
    game_path: Path,
    *,
    scripts: bool,
) -> tuple[DeployFile, ...]:
    """Resolve the complete runtime file set for one native deployment."""
    mod_info = MODS[mod_id]
    mod_dir = _get_mod_dir(cli_ctx, mod_id)
    manifest_path = mod_dir / "thunderstore.toml"
    thunderstore_id = mod_info.get("thunderstore")
    if loader == "bepinex" and not scripts and manifest_path.is_file() and thunderstore_id:
        namespace, name = thunderstore_id.split("/", 1)
        manifest = _parse_thunderstore_manifest(
            manifest_path,
            mod_dir,
            cli_ctx.repo_root,
            expected_namespace=namespace,
            expected_name=name,
        )
        manifest_files = tuple(
            DeployFile(
                source=copy.source,
                target=game_path / "BepInEx" / Path(*copy.target.parts) / copy.source.name,
            )
            for copy in manifest.copies
        )
        if not any(file.source.name == mod_info["dll_name"] for file in manifest_files):
            raise ValueError(f"Thunderstore manifest does not deploy {mod_info['dll_name']}")
        return manifest_files

    target_dir, _, copy_pdb = _get_deploy_target_dir(loader, game_path, scripts=scripts)
    output_dir = _get_mod_output_dir(cli_ctx, mod_id, loader)
    dll_name = mod_info["dll_name"]
    files = [DeployFile(output_dir / dll_name, target_dir / dll_name)]
    if copy_pdb:
        pdb_name = dll_name.replace(".dll", ".pdb")
        pdb = output_dir / pdb_name
        if pdb.is_file():
            files.append(DeployFile(pdb, target_dir / pdb_name))
    return tuple(files)


def _conflicting_deploy_paths(
    game_path: Path,
    mod_id: str,
    loader: LoaderName,
    deployed: tuple[DeployFile, ...],
) -> tuple[Path, ...]:
    """Find known copies that would load the same BepInEx plugin twice."""
    if loader != "bepinex":
        return ()

    mod_info = MODS[mod_id]
    dll_name = mod_info["dll_name"]
    pdb_name = dll_name.replace(".dll", ".pdb")
    plugins = _get_bepinex_plugins_dir(game_path)
    candidates = {
        plugins / dll_name,
        plugins / pdb_name,
        _get_bepinex_scripts_dir(game_path) / dll_name,
        _get_bepinex_scripts_dir(game_path) / pdb_name,
    }
    thunderstore_id = mod_info.get("thunderstore")
    if thunderstore_id:
        package_name = thunderstore_id.split("/", 1)[1]
        candidates.add(plugins / package_name / dll_name)
        candidates.add(plugins / package_name / pdb_name)

    targets = {file.target for file in deployed}
    return tuple(sorted(candidates - targets))


def _remove_conflicting_deploy_paths(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if not path.exists():
            continue
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"conflicting mod deploy path is not a regular file: {path}")
        path.unlink()
        console.print(f"  [dim]removed stale {path.name} from {path.parent}[/dim]")


def _get_deploy_target_dir(loader: LoaderName, game_path: Path, *, scripts: bool) -> tuple[Path, str, bool]:
    """Return the deploy target directory, a human label, and PDB behavior."""
    if loader == "lunaris":
        if scripts:
            raise ValueError("--scripts is only supported for BepInEx mods")
        return _get_lunaris_plugins_dir(game_path), "Lunaris plugins", False

    if loader != "bepinex":
        raise ValueError(f"Unsupported deploy loader: {loader}")
    if scripts:
        return _get_bepinex_scripts_dir(game_path), "BepInEx/scripts (hot reload)", True
    return _get_bepinex_plugins_dir(game_path), "BepInEx/plugins", False


def _resolve_mod_targets(
    mod: str | None,
    loader: str,
    *,
    allow_all: bool,
) -> list[tuple[str, LoaderName]]:
    """Resolve a CLI loader target into deterministic ``(mod, loader)`` pairs."""
    valid_loaders = {"default", "bepinex", "lunaris"}
    if allow_all:
        valid_loaders.add("all")
    if loader not in valid_loaders:
        choices = ", ".join(sorted(valid_loaders))
        raise ValueError(f"Unsupported loader target {loader!r}; choose {choices}")

    mod_ids = [mod] if mod else list(MODS)
    if mod and mod not in MODS:
        raise ValueError(f"Unknown mod: {mod}")

    targets: list[tuple[str, LoaderName]] = []
    for mod_id in mod_ids:
        mod_info = MODS[mod_id]
        selected: list[LoaderName]
        if loader == "all":
            selected = list(mod_info["loaders"])
        elif loader == "default":
            selected = [mod_info["default_loader"]]
        else:
            selected = [cast("LoaderName", loader)]

        for selected_loader in selected:
            if selected_loader not in mod_info["loaders"]:
                raise ValueError(f"{mod_id} does not support the {selected_loader} loader")
            targets.append((mod_id, selected_loader))
    return targets


def _resolve_build_targets(mod: str | None, loader: str) -> list[tuple[str, LoaderName]]:
    """Resolve build targets, including the ``all`` expansion."""
    return _resolve_mod_targets(mod, loader, allow_all=True)


def _resolve_deploy_targets(mod: str | None, loader: str) -> list[tuple[str, LoaderName]]:
    """Resolve deploy targets; deployment intentionally has no ``all`` target."""
    return _resolve_mod_targets(mod, loader, allow_all=False)


def _find_lunaris_dll(game_path: Path, lunaris_lib_dir: Path | None) -> Path | None:
    """Locate Lunaris.dll for native Lunaris plugin compilation.

    Resolution order: the ERENSHOR_LUNARIS_DLL override, the game install, then
    the configured Lunaris build directory.
    """
    env_path = os.environ.get("ERENSHOR_LUNARIS_DLL")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    candidates = [game_path / "Lunaris.dll"]
    if lunaris_lib_dir is not None:
        candidates.append(lunaris_lib_dir / "Lunaris.dll")
    return next((c for c in candidates if c.is_file()), None)


def _find_lunaris_shared_lib(dll_name: str, lib_dir: Path | None) -> Path | None:
    """Locate a Lunaris-provided compile library in the resolved lib directory.

    Lunaris ships these libraries (ImGui.NET, Newtonsoft.Json, 0Harmony, ...) in a
    single LunarisLibs.zip, so they are sourced only from the resolved Lunaris lib
    directory -- never scavenged from the game or BepInEx install, whose copies may
    be absent (ImGui.NET) or a different version than Lunaris loads at runtime.
    """
    if lib_dir is None:
        return None
    source = lib_dir / dll_name
    return source if source.is_file() else None


def _configured_lunaris_lib_dir(configured_dir: Path | None) -> Path | None:
    """Resolve the Lunaris compile-library directory from env or config.

    The ERENSHOR_LUNARIS_LIB_DIR environment variable overrides the configured
    ``[global.mods] lunaris_lib_dir``. Returns ``None`` when neither is set.
    """
    env_dir = os.environ.get("ERENSHOR_LUNARIS_LIB_DIR")
    if env_dir:
        return Path(env_dir)
    return configured_dir


def _ensure_lunaris_libs_cached(repo_root: Path, libs_url: str) -> Path:
    """Download and extract LunarisLibs.zip into a cached lib directory.

    Lunaris ships its compile libraries in a single LunarisLibs.zip. When neither
    ERENSHOR_LUNARIS_LIB_DIR nor ``[global.mods] lunaris_lib_dir`` is set, fetch that
    archive once and cache the extracted DLLs under ``.erenshor/cache`` so that
    ``mod setup`` works without manual setup. Extraction is atomic, so an interrupted
    download never leaves a half-populated cache.
    """
    import io
    import tempfile
    import zipfile

    cache_dir = repo_root / ".erenshor" / "cache" / "lunaris-libs"
    if cache_dir.is_dir() and any(cache_dir.glob("*.dll")):
        return cache_dir

    console.print(f"  Downloading Lunaris libraries from {libs_url} ...")
    req = Request(libs_url, headers={"User-Agent": "erenshor-cli"})
    try:
        with urlopen(req, timeout=60) as resp:
            zip_data = resp.read()
    except (HTTPError, URLError, TimeoutError) as e:
        console.print(f"  [red]✗[/red] Failed to download Lunaris libraries: {e}")
        console.print("  Set [global.mods] lunaris_lib_dir or ERENSHOR_LUNARIS_LIB_DIR instead.")
        raise typer.Exit(1) from e

    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir.parent) as tmp:
        staging = Path(tmp) / "lunaris-libs"
        staging.mkdir()
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for entry in zf.namelist():
                if entry.endswith(".dll"):
                    (staging / Path(entry).name).write_bytes(zf.read(entry))
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        staging.replace(cache_dir)

    console.print(f"  [green]✓[/green] Lunaris libraries cached at {cache_dir}")
    return cache_dir


def _build_mods_internal(
    cli_ctx: CLIContext,
    mod: str | None = None,
    version: str | None = None,
    *,
    loader: BuildLoader = "default",
    skip_ilrepack: bool = False,
) -> None:
    """Build selected loader targets for one or all mods."""
    try:
        targets = _resolve_build_targets(mod, loader)
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc

    if not _check_dotnet_available():
        console.print("[red]Error: dotnet CLI not found in PATH[/red]")
        console.print("Install .NET SDK from https://dotnet.microsoft.com/")
        raise typer.Exit(1)

    failed: list[str] = []
    for mod_id, target_loader in targets:
        mod_dir = _get_mod_dir(cli_ctx, mod_id)
        if not mod_dir.exists():
            console.print(f"[red]Error: Mod directory not found: {mod_dir}[/red]")
            raise typer.Exit(1)

        lib_dir = _get_mod_lib_dir(cli_ctx, mod_id)
        if not any(lib_dir.glob("*.dll")):
            console.print(f"[red]Error: No DLLs in {mod_id}/lib/ directory[/red]")
            console.print("Run 'uv run erenshor mod setup' first.")
            raise typer.Exit(1)

        console.print(f"[bold]{MODS[mod_id]['name']} ({target_loader})[/bold]")
        console.print(f"[dim]{mod_dir}[/dim]")
        console.print()

        build_cmd: list[str] = [
            "dotnet",
            "build",
            "--configuration",
            "Debug",
            f"-p:ModLoader={target_loader}",
        ]
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
            failed.append(f"{mod_id} ({target_loader})")
        else:
            console.print("[green]✓ Build successful[/green]")
            console.print()

    if failed:
        console.print(f"[red]Build failed for: {', '.join(failed)}[/red]")
        raise typer.Exit(1)

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
    """Provision mod compilation references.

    Copies required game assemblies and isolated BepInEx/Lunaris references into
    every mod's lib tree. These DLLs are needed to compile native targets but are
    not committed to the repository.

    The selected variant resolves a configured runnable install, its matching
    CrossOver Steam app, the legacy ERENSHOR_GAME_PATH override, then extracted
    game files.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Setup[/bold cyan]", border_style="cyan"))
    console.print()

    # Setup may source compile references from extracted game files when no
    # runnable installation is available.
    game_path = _get_game_path(cli_ctx, allow_extracted=True)
    if not game_path:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        console.print()
        console.print("Install the selected Steam app or set [variants.<name>] game_install.")
        console.print("For legacy scripts, ERENSHOR_GAME_PATH remains a fallback.")
        raise typer.Exit(1)

    managed_dir = _get_managed_dir(game_path)
    if not managed_dir.exists():
        console.print(f"[red]Error: Managed directory not found: {managed_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Source: {managed_dir}[/dim]")
    console.print()

    bepinex_core_dir = game_path / "BepInEx" / "core"

    mods_cfg = cli_ctx.config.global_.mods
    configured_lunaris_dir = mods_cfg.resolved_lunaris_lib_dir(cli_ctx.repo_root) if mods_cfg.lunaris_lib_dir else None
    lunaris_lib_dir = _configured_lunaris_lib_dir(configured_lunaris_dir) or _ensure_lunaris_libs_cached(
        cli_ctx.repo_root, mods_cfg.lunaris_libs_url
    )

    # Provision common game references once and keep each loader's references in
    # its own directory. In particular, BepInEx and Lunaris ship different
    # 0Harmony.dll assemblies and must never overwrite one another.
    for mod_id, mod_info in MODS.items():
        lib_dir = _get_mod_lib_dir(cli_ctx, mod_id)
        lib_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[bold]{mod_info['name']}[/bold]")
        missing: list[str] = []

        for dll_name in REQUIRED_DLLS:
            source = managed_dir / dll_name
            target = lib_dir / dll_name
            if not source.exists():
                missing.append(dll_name)
                console.print(f"  [red]✗[/red] {dll_name} (not found in game)")
            else:
                shutil.copy2(source, target)
                console.print(f"  [green]✓[/green] {dll_name}")

        for target_loader in mod_info["loaders"]:
            loader_lib_dir = _get_mod_loader_lib_dir(cli_ctx, mod_id, target_loader)
            loader_lib_dir.mkdir(parents=True, exist_ok=True)

            if target_loader == "lunaris":
                lunaris_dll = _find_lunaris_dll(game_path, lunaris_lib_dir)
                if lunaris_dll is None:
                    missing.append("Lunaris.dll")
                    console.print(
                        "  [red]✗[/red] Lunaris.dll (set [global.mods] lunaris_lib_dir or ERENSHOR_LUNARIS_DLL)"
                    )
                else:
                    shutil.copy2(lunaris_dll, loader_lib_dir / "Lunaris.dll")
                    console.print(f"  [green]✓[/green] Lunaris.dll (from {lunaris_dll.parent})")

            loader_dlls: list[str] = (
                mod_info.get("lunaris_dlls", []) if target_loader == "lunaris" else mod_info.get("bepinex_dlls", [])
            )
            for dll_name in loader_dlls:
                loader_source: Path | None
                if target_loader == "lunaris":
                    loader_source = _find_lunaris_shared_lib(dll_name, lunaris_lib_dir)
                    source_label = "Lunaris"
                else:
                    loader_source = bepinex_core_dir / dll_name
                    source_label = "BepInEx"

                target = loader_lib_dir / dll_name
                if loader_source is None or not loader_source.exists():
                    missing.append(dll_name)
                    console.print(f"  [red]✗[/red] {dll_name} (loader reference unavailable)")
                else:
                    shutil.copy2(loader_source, target)
                    console.print(f"  [green]✓[/green] {dll_name} (from {source_label})")

        if missing:
            console.print(f"[red]Error: Missing DLLs: {', '.join(missing)}[/red]")
            raise typer.Exit(1)

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

    game_path = _get_game_path(cli_ctx)
    if not game_path:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        console.print("Install the selected Steam app or set [variants.<name>] game_install.")
        raise typer.Exit(1)

    bepinex_dir = game_path / "BepInEx"
    if not bepinex_dir.exists():
        console.print(f"[red]Error: BepInEx not installed at {bepinex_dir}[/red]")
        console.print("Install BepInEx to your game first.")
        raise typer.Exit(1)

    plugins_dir = _get_bepinex_plugins_dir(game_path)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = _get_bepinex_scripts_dir(game_path)
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

    _build_mods_internal(cli_ctx, mod, loader=loader)

    console.print("[green]Build complete![/green]")
    console.print()


@app.command()
def status(ctx: typer.Context) -> None:
    """Show native loader availability and the active loader for one variant."""
    cli_ctx: CLIContext = ctx.obj
    game_path = _get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Loader Status[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()
    try:
        _print_loader_status(game_path)
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
    game_path = _get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(Panel.fit("[bold cyan]Activate Mod Loader[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()
    try:
        changed = _activate_loader(game_path, loader)
        if changed:
            console.print(f"[green]Activated {loader}.[/green] Restart the game before testing.")
        else:
            console.print(f"[dim]{loader} is already active.[/dim]")
        _print_loader_status(game_path)
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

    try:
        targets = _resolve_deploy_targets(mod, loader)
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc
    target_loaders: set[LoaderName] = {target_loader for _, target_loader in targets}
    if len(target_loaders) != 1:
        console.print(
            "[red]Error: default deployment spans both native loaders; "
            "choose --loader bepinex or --loader lunaris[/red]"
        )
        raise typer.Exit(1)
    target_loader = next(iter(target_loaders))
    if scripts and target_loader != "bepinex":
        console.print("[red]Error: --scripts is only supported for BepInEx mods[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Deploy[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Variant: {cli_ctx.variant}[/dim]")
    console.print()

    game_path = _get_game_path(cli_ctx)
    if game_path is None:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)
    try:
        _validate_loader_activation(game_path, target_loader)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc

    console.print("[bold]Building mods...[/bold]")
    _build_mods_internal(cli_ctx, mod, loader=loader)

    try:
        deploy_files = {
            mod_id: _get_deploy_files(cli_ctx, mod_id, selected_loader, game_path, scripts=scripts)
            for mod_id, selected_loader in targets
        }
        conflicting_files = {
            mod_id: _conflicting_deploy_paths(game_path, mod_id, selected_loader, deploy_files[mod_id])
            for mod_id, selected_loader in targets
        }
        for files in deploy_files.values():
            for file in files:
                _require_regular_file(file.source, "mod deploy input")
        for paths in conflicting_files.values():
            for path in paths:
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise ValueError(f"conflicting mod deploy path is not a regular file: {path}")
    except (OSError, ValueError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from exc

    console.print()
    console.print("[bold]Deploying...[/bold]")
    console.print(f"[dim]Install: {game_path}[/dim]")
    console.print()

    for mod_id, selected_loader in targets:
        _, deploy_label, _ = _get_deploy_target_dir(selected_loader, game_path, scripts=scripts)
        console.print(f"[bold]{MODS[mod_id]['name']} ({selected_loader}) → {deploy_label}[/bold]")
        try:
            _remove_conflicting_deploy_paths(conflicting_files[mod_id])
        except (OSError, ValueError) as exc:
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1) from exc
        for file in deploy_files[mod_id]:
            file.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file.source, file.target)
            size_kb = file.source.stat().st_size / 1024
            console.print(f"  [green]✓[/green] {file.target.relative_to(game_path)} ({size_kb:.1f} KB)")

    try:
        changed = _activate_loader(game_path, target_loader)
    except (OSError, ValueError, RuntimeError) as exc:
        console.print(f"[red]Error activating {target_loader}: {exc}[/red]")
        raise typer.Exit(1) from exc

    console.print()
    action = "Activated" if changed else "Already active"
    console.print(f"[green]{action}: {target_loader}[/green]")
    console.print("[green]Deploy complete![/green]")
    console.print("[dim]Restart the game before testing a newly selected loader.[/dim]")
    console.print()


@app.command()
def publish(
    ctx: typer.Context,
    mod: str | None = typer.Option(None, "--mod", help="Publish specific mod (or all if not specified)"),
) -> None:
    """Stage configured default-loader builds for website download.

    Builds each selected mod's configured default target and copies its output
    DLL to the maps website's static directory. Run this before building or
    deploying the maps website to include the latest downloadable versions.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Mod Publish[/bold cyan]", border_style="cyan"))
    console.print()

    targets = _resolve_deploy_targets(mod, "default")
    console.print("[bold]Building mods...[/bold]")
    _build_mods_internal(cli_ctx, mod, loader="default")

    publish_dir = _get_mod_publish_dir(cli_ctx)
    publish_dir.mkdir(parents=True, exist_ok=True)

    console.print()
    console.print("[bold]Publishing to website...[/bold]")
    console.print(f"[dim]Target: {publish_dir}[/dim]")
    console.print()

    for mod_id, target_loader in targets:
        output_dir = _get_mod_output_dir(cli_ctx, mod_id, target_loader)
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


def _is_forbidden_runtime_dll(name: str) -> bool:
    return name.casefold() in FORBIDDEN_RUNTIME_DLLS


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
        if _is_forbidden_runtime_dll(source.name):
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
        if _is_forbidden_runtime_dll(path.name):
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
        if mod not in MODS:
            console.print(f"[red]Error: Unknown mod: {mod}[/red]")
            raise typer.Exit(1)
        if not MODS[mod].get("public") or "thunderstore" not in MODS[mod]:
            console.print(f"[red]Error: {mod} is not configured for Thunderstore[/red]")
            raise typer.Exit(1)
        selected = [mod]
    else:
        selected = [mod_id for mod_id, info in MODS.items() if info.get("public") and "thunderstore" in info]

    releases: list[ThunderstoreRelease] = []
    # Preflight every release, including version lookups, before any build starts.
    for mod_id in selected:
        mod_info = MODS[mod_id]
        ts_id = mod_info.get("thunderstore")
        if not ts_id or ts_id.count("/") != 1:
            console.print(f"[red]Error: invalid Thunderstore id for {mod_id}[/red]")
            raise typer.Exit(1)
        namespace, name = ts_id.split("/", 1)
        mod_dir = _get_mod_dir(cli_ctx, mod_id).resolve(strict=False)
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
        console.print(f"[bold]{MODS[release.mod_id]['name']}[/bold]")
        console.print(f"  Version: [cyan]{release.version}[/cyan]")
        console.print("[bold]Building...[/bold]")
        try:
            _require_unchanged_inputs(release.static_input_hashes)
            _build_mods_internal(cli_ctx, release.mod_id, version=release.version, loader="bepinex")
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
        namespace, name = (MODS[release.mod_id].get("thunderstore") or "").split("/", 1)
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
        return (_get_mod_dir(cli_ctx, mod_id) / "vault" / "vault.toml").exists()

    if mod:
        if mod not in MODS:
            console.print(f"[red]Error: Unknown mod: {mod}[/red]")
            raise typer.Exit(1)
        if not has_listing(mod):
            console.print(f"[red]Error: {mod} has no vault/vault.toml listing[/red]")
            raise typer.Exit(1)
        eligible = [mod]
    else:
        eligible = [m for m in MODS if has_listing(m)]

    if not eligible:
        console.print("[yellow]No mods have a vault/vault.toml listing.[/yellow]")
        raise typer.Exit(0)

    for mod_id in eligible:
        mod_dir = _get_mod_dir(cli_ctx, mod_id)
        config = tomllib.loads((mod_dir / "vault" / "vault.toml").read_text())
        mod_ref = config["mod"]["mod_ref"]

        console.print(f"[bold]{MODS[mod_id]['name']}[/bold]")
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
        _build_mods_internal(cli_ctx, mod_id, version=version, loader="lunaris")

        dll = _get_mod_output_dir(cli_ctx, mod_id, "lunaris") / MODS[mod_id]["dll_name"]
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
    """Launch the selected game through Steam.

    On macOS, CrossOver handles the selected variant's Steam protocol URL in
    the bottle containing its installation. This preserves Steamworks
    initialization and returns after Steam accepts the launch request.
    """
    cli_ctx: CLIContext = ctx.obj

    console.print()
    console.print(Panel.fit("[bold cyan]Launch Game[/bold cyan]", border_style="cyan"))
    console.print()

    game_path = _get_game_path(cli_ctx)
    if not game_path:
        console.print(f"[red]Error: game installation not found for variant {cli_ctx.variant!r}[/red]")
        console.print("Install the selected Steam app or set [variants.<name>] game_install.")
        raise typer.Exit(1)

    variant_config = cli_ctx.config.variants.get(cli_ctx.variant)
    if variant_config is None or not variant_config.app_id:
        console.print(f"[red]Error: Steam App ID not configured for variant {cli_ctx.variant!r}[/red]")
        raise typer.Exit(1)

    # Check for CrossOver on macOS
    crossover_bottle = os.environ.get("CROSSOVER_BOTTLE") or _crossover_bottle_for_path(game_path)
    if sys.platform == "darwin" and crossover_bottle:
        if not CROSSOVER_START.exists():
            console.print(f"[red]Error: CrossOver launcher not found: {CROSSOVER_START}[/red]")
            raise typer.Exit(1)

        steam_url = f"steam://rungameid/{variant_config.app_id}"
        console.print(f"[dim]Launching through Steam in CrossOver bottle: {crossover_bottle}[/dim]")
        console.print(f"[dim]Steam URL: {steam_url}[/dim]")
        console.print()

        result = subprocess.run(
            [
                str(CROSSOVER_START),
                "--bottle",
                crossover_bottle,
                "--no-wait",
                steam_url,
            ],
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]Error: Steam launch failed with exit code {result.returncode}[/red]")
            raise typer.Exit(1)
    else:
        # Direct launch (Windows or Linux with Wine)
        exe_path = game_path / "Erenshor.exe"
        if not exe_path.exists():
            console.print(f"[red]Error: Game executable not found: {exe_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[dim]Executable: {exe_path}[/dim]")
        console.print()

        subprocess.run([str(exe_path)], check=False)
