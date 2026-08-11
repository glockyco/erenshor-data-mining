"""Application workflows for local companion-mod development.

The workflow owns deterministic target selection, loader planning, filesystem
operations, and process-independent build/deploy decisions.  The CLI supplies
presentation and the process runner at its boundary.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loguru import logger

from erenshor.application.mods.artifacts import (
    REQUIRED_DLLS,
    format_artifact_issues,
    verify_built_mod_artifacts,
)
from erenshor.application.mods.catalog import LoaderName, artifact_specs, iter_mods, lookup_mod

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

BuildLoader = Literal["default", "bepinex", "lunaris", "all"]
DeployLoader = Literal["default", "bepinex", "lunaris"]
ProcessRunner = Callable[..., Any]

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


@dataclass(frozen=True, slots=True)
class BuildPlan:
    mod_id: str
    loader: LoaderName
    cwd: Path
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuildResult:
    targets: tuple[tuple[str, LoaderName], ...]
    failed: tuple[str, ...] = ()
    artifact_issues: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class DeployFile:
    source: Path
    target: Path


@dataclass(frozen=True, slots=True)
class DeploySelection:
    game_path: Path
    targets: tuple[tuple[str, LoaderName], ...]
    target_loader: LoaderName
    scripts: bool


@dataclass(frozen=True, slots=True)
class DeployPlan:
    game_path: Path
    targets: tuple[tuple[str, LoaderName], ...]
    target_loader: LoaderName
    files: tuple[tuple[str, tuple[DeployFile, ...]], ...]
    conflicts: tuple[tuple[str, tuple[Path, ...]], ...]
    scripts: bool

    def files_for(self, mod_id: str) -> tuple[DeployFile, ...]:
        return dict(self.files)[mod_id]

    def conflicts_for(self, mod_id: str) -> tuple[Path, ...]:
        return dict(self.conflicts)[mod_id]


@dataclass(frozen=True, slots=True)
class DeployResult:
    copied: tuple[DeployFile, ...]
    removed_conflicts: tuple[Path, ...]
    loader_changed: bool


@dataclass(frozen=True, slots=True)
class SetupResult:
    game_path: Path


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    command: tuple[str, ...]
    game_path: Path
    crossover_bottle: str | None


def _read_steam_install_dir(manifest: Path) -> str | None:
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


def discover_crossover_game_path(app_id: str) -> Path | None:
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


def crossover_bottle_for_path(game_path: Path) -> str | None:
    try:
        relative = game_path.resolve().relative_to(CROSSOVER_BOTTLES_ROOT.resolve())
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def _read_game_app_id(game_path: Path) -> str | None:
    try:
        app_id = (game_path / "steam_appid.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return app_id or None


def get_game_path(cli_ctx: CLIContext, *, allow_extracted: bool = False) -> Path | None:
    variant_config = cli_ctx.config.variants.get(cli_ctx.variant)
    if variant_config:
        resolve_install = getattr(variant_config, "resolved_game_install", None)
        configured = cast("Path | None", resolve_install(cli_ctx.repo_root)) if resolve_install else None
        if configured is not None:
            if configured.exists():
                return configured
            logger.warning(f"Configured game_install does not exist: {configured}")
            return None
        discovered = discover_crossover_game_path(variant_config.app_id)
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
        if (game_files / "Erenshor_Data" / "Managed").exists():
            return game_files
    return None


def managed_dir(game_path: Path) -> Path:
    return game_path / "Erenshor_Data" / "Managed"


def bepinex_plugins_dir(game_path: Path) -> Path:
    return game_path / "BepInEx" / "plugins"


def lunaris_plugins_dir(game_path: Path) -> Path:
    return game_path / "plugins"


def bepinex_scripts_dir(game_path: Path) -> Path:
    return game_path / "BepInEx" / "scripts"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def loader_proxy_sources(game_path: Path) -> dict[LoaderName, Path]:
    sources: dict[LoaderName, Path] = {}
    for loader, names in LOADER_PROXY_CANDIDATES.items():
        candidates = [game_path / name for name in names if (game_path / name).exists()]
        for candidate in candidates:
            if not candidate.is_file() or candidate.is_symlink():
                raise ValueError(f"{loader} loader proxy is not a regular file: {candidate}")
        digests = {file_sha256(candidate) for candidate in candidates}
        if len(digests) > 1:
            joined = ", ".join(str(path) for path in candidates)
            raise ValueError(f"conflicting {loader} loader proxies: {joined}")
        if candidates:
            sources[loader] = candidates[0]
    return sources


def detect_active_loader(game_path: Path, sources: dict[LoaderName, Path]) -> LoaderName | Literal["unknown"] | None:
    active_proxy = game_path / "winhttp.dll"
    if not active_proxy.exists():
        return None
    if not active_proxy.is_file() or active_proxy.is_symlink():
        raise ValueError(f"active loader proxy is not a regular file: {active_proxy}")
    active_digest = file_sha256(active_proxy)
    matches = [loader for loader, source in sources.items() if file_sha256(source) == active_digest]
    if len(matches) == 1:
        return matches[0]
    return "unknown"


def validate_loader_activation(game_path: Path, loader: LoaderName) -> tuple[dict[LoaderName, Path], LoaderName | None]:
    sources = loader_proxy_sources(game_path)
    source = sources.get(loader)
    if source is None:
        expected = ", ".join(LOADER_PROXY_CANDIDATES[loader])
        raise ValueError(f"{loader} loader proxy not found in {game_path}; expected one of: {expected}")
    active = detect_active_loader(game_path, sources)
    if active == "unknown":
        raise ValueError(
            f"refusing to replace unrecognized {game_path / 'winhttp.dll'}; "
            "restore it with the BepInEx or Lunaris installer first"
        )
    return sources, active


def activate_loader(game_path: Path, loader: LoaderName) -> bool:
    sources, active = validate_loader_activation(game_path, loader)
    source = sources[loader]
    if active == loader:
        return False
    descriptor, temporary_name = tempfile.mkstemp(prefix=".erenshor-winhttp-", suffix=".tmp", dir=game_path)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(game_path / "winhttp.dll")
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
    if detect_active_loader(game_path, sources) != loader:
        raise RuntimeError(f"failed to activate {loader} loader")
    return True


def loader_status(
    game_path: Path,
) -> tuple[LoaderName | Literal["unknown"] | None, tuple[tuple[LoaderName, Path | None], ...]]:
    sources = loader_proxy_sources(game_path)
    loaders: tuple[LoaderName, ...] = ("bepinex", "lunaris")
    return detect_active_loader(game_path, sources), tuple((loader, sources.get(loader)) for loader in loaders)


def mod_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    try:
        definition = lookup_mod(mod_id)
    except KeyError as exc:
        raise ValueError(f"Unknown mod: {mod_id}") from exc
    return cli_ctx.repo_root / definition.directory


def mod_lib_dir(cli_ctx: CLIContext, mod_id: str) -> Path:
    return mod_dir(cli_ctx, mod_id) / "lib"


def mod_loader_lib_dir(cli_ctx: CLIContext, mod_id: str, loader: LoaderName) -> Path:
    definition = lookup_mod(mod_id)
    if loader not in definition.loaders:
        raise ValueError(f"{mod_id} does not support the {loader} loader")
    return mod_lib_dir(cli_ctx, mod_id) / loader


def mod_output_dir(cli_ctx: CLIContext, mod_id: str, loader: LoaderName, *, configuration: str = "Debug") -> Path:
    definition = lookup_mod(mod_id)
    if loader not in definition.loaders:
        raise ValueError(f"{mod_id} does not support the {loader} loader")
    return mod_dir(cli_ctx, mod_id) / "bin" / configuration / "netstandard2.1" / loader


def resolve_targets(mod: str | None, loader: str, *, allow_all: bool) -> list[tuple[str, LoaderName]]:
    valid_loaders = {"default", "bepinex", "lunaris"}
    if allow_all:
        valid_loaders.add("all")
    if loader not in valid_loaders:
        raise ValueError(f"Unsupported loader target {loader!r}; choose {', '.join(sorted(valid_loaders))}")
    mod_ids = [mod] if mod else [definition.mod_id for definition in iter_mods()]
    if mod:
        try:
            lookup_mod(mod)
        except KeyError as exc:
            raise ValueError(f"Unknown mod: {mod}") from exc
    targets: list[tuple[str, LoaderName]] = []
    for mod_id in mod_ids:
        definition = lookup_mod(mod_id)
        if loader == "all":
            selected = list(definition.loaders)
        elif loader == "default":
            selected = [definition.default_loader]
        else:
            selected = [cast("LoaderName", loader)]
        for selected_loader in selected:
            if selected_loader not in definition.loaders:
                raise ValueError(f"{mod_id} does not support the {selected_loader} loader")
            targets.append((mod_id, selected_loader))
    return targets


def resolve_build_targets(mod: str | None, loader: str) -> list[tuple[str, LoaderName]]:
    return resolve_targets(mod, loader, allow_all=True)


def resolve_deploy_targets(mod: str | None, loader: str) -> list[tuple[str, LoaderName]]:
    return resolve_targets(mod, loader, allow_all=False)


def find_lunaris_dll(game_path: Path, lunaris_lib_dir: Path | None) -> Path | None:
    env_path = os.environ.get("ERENSHOR_LUNARIS_DLL")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    candidates = [game_path / "Lunaris.dll"]
    if lunaris_lib_dir is not None:
        candidates.append(lunaris_lib_dir / "Lunaris.dll")
    return next((c for c in candidates if c.is_file()), None)


def find_lunaris_shared_lib(dll_name: str, lib_dir: Path | None) -> Path | None:
    if lib_dir is None:
        return None
    source = lib_dir / dll_name
    return source if source.is_file() else None


def configured_lunaris_lib_dir(configured_dir: Path | None) -> Path | None:
    env_dir = os.environ.get("ERENSHOR_LUNARIS_LIB_DIR")
    return Path(env_dir) if env_dir else configured_dir


def ensure_lunaris_libs_cached(repo_root: Path, libs_url: str) -> Path:
    cache_dir = repo_root / ".erenshor" / "cache" / "lunaris-libs"
    if cache_dir.is_dir() and any(cache_dir.glob("*.dll")):
        return cache_dir
    req = Request(libs_url, headers={"User-Agent": "erenshor-cli"})
    try:
        with urlopen(req, timeout=60) as resp:
            zip_data = resp.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"Failed to download Lunaris libraries: {exc}. "
            "Set [global.mods] lunaris_lib_dir or ERENSHOR_LUNARIS_LIB_DIR instead."
        ) from exc
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir.parent) as tmp:
        staging = Path(tmp) / "lunaris-libs"
        staging.mkdir()
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            for entry in archive.namelist():
                if entry.endswith(".dll"):
                    (staging / Path(entry).name).write_bytes(archive.read(entry))
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        staging.replace(cache_dir)
    return cache_dir


def setup_mods(
    cli_ctx: CLIContext,
    mod: str | None = None,
    *,
    loader: BuildLoader = "all",
) -> SetupResult:
    targets = resolve_build_targets(mod, loader)
    game_path = get_game_path(cli_ctx, allow_extracted=True)
    if not game_path:
        raise ValueError(f"game installation not found for variant {cli_ctx.variant!r}")
    source_dir = managed_dir(game_path)
    if not source_dir.exists():
        raise ValueError(f"Managed directory not found: {source_dir}")
    bepinex_core_dir = game_path / "BepInEx" / "core"
    lunaris_lib_dir: Path | None = None
    if any(target_loader == "lunaris" for _, target_loader in targets):
        mods_cfg = cli_ctx.config.global_.mods
        configured = mods_cfg.resolved_lunaris_lib_dir(cli_ctx.repo_root) if mods_cfg.lunaris_lib_dir else None
        lunaris_lib_dir = configured_lunaris_lib_dir(configured) or ensure_lunaris_libs_cached(
            cli_ctx.repo_root, mods_cfg.lunaris_libs_url
        )
    selected_mod_ids = dict.fromkeys(mod_id for mod_id, _ in targets)
    for mod_id in selected_mod_ids:
        definition = lookup_mod(mod_id)
        selected_loaders = tuple(target_loader for target_mod, target_loader in targets if target_mod == mod_id)
        lib_dir = mod_lib_dir(cli_ctx, mod_id)
        lib_dir.mkdir(parents=True, exist_ok=True)
        missing: list[str] = []
        for dll_name in REQUIRED_DLLS:
            source = source_dir / dll_name
            if not source.exists():
                missing.append(dll_name)
            else:
                shutil.copy2(source, lib_dir / dll_name)
        for target_loader in selected_loaders:
            loader_lib_dir = mod_loader_lib_dir(cli_ctx, mod_id, target_loader)
            loader_lib_dir.mkdir(parents=True, exist_ok=True)
            if target_loader == "lunaris":
                lunaris_dll = find_lunaris_dll(game_path, lunaris_lib_dir)
                if lunaris_dll is None:
                    missing.append("Lunaris.dll")
                else:
                    shutil.copy2(lunaris_dll, loader_lib_dir / "Lunaris.dll")
            loader_dlls = definition.lunaris_dlls if target_loader == "lunaris" else definition.bepinex_dlls
            for dll_name in loader_dlls:
                loader_source = (
                    find_lunaris_shared_lib(dll_name, lunaris_lib_dir)
                    if target_loader == "lunaris"
                    else bepinex_core_dir / dll_name
                )
                if loader_source is None or not loader_source.exists():
                    missing.append(dll_name)
                else:
                    shutil.copy2(loader_source, loader_lib_dir / dll_name)
        if missing:
            raise ValueError(f"Missing DLLs: {', '.join(missing)}")
    return SetupResult(game_path)


def check_dotnet_available() -> bool:
    return shutil.which("dotnet") is not None


def plan_builds(
    cli_ctx: CLIContext,
    mod: str | None = None,
    version: str | None = None,
    *,
    loader: BuildLoader = "default",
    skip_ilrepack: bool = False,
) -> tuple[BuildPlan, ...]:
    plans: list[BuildPlan] = []
    for mod_id, target_loader in resolve_build_targets(mod, loader):
        source_dir = mod_dir(cli_ctx, mod_id)
        if not source_dir.exists():
            raise ValueError(f"Mod directory not found: {source_dir}")
        if not any(mod_lib_dir(cli_ctx, mod_id).glob("*.dll")):
            raise ValueError(f"No DLLs in {mod_id}/lib/ directory")
        command = ["dotnet", "build", "--configuration", "Debug", f"-p:ModLoader={target_loader}"]
        if version:
            command.append(f"-p:ModVersion={version}")
        if skip_ilrepack:
            command.append("-p:SkipILRepack=true")
        plans.append(BuildPlan(mod_id, target_loader, source_dir, tuple(command)))
    return tuple(plans)


def build_mods(
    cli_ctx: CLIContext,
    mod: str | None = None,
    version: str | None = None,
    *,
    loader: BuildLoader = "default",
    skip_ilrepack: bool = False,
    runner: ProcessRunner = subprocess.run,
) -> BuildResult:
    resolve_build_targets(mod, loader)
    if not check_dotnet_available():
        raise RuntimeError("dotnet CLI not found in PATH")
    plans = plan_builds(cli_ctx, mod, version, loader=loader, skip_ilrepack=skip_ilrepack)
    failed: list[str] = []
    for plan in plans:
        result = runner(list(plan.command), cwd=plan.cwd, check=False)
        if result.returncode != 0:
            failed.append(f"{plan.mod_id} ({plan.loader})")
    if failed:
        return BuildResult(tuple((plan.mod_id, plan.loader) for plan in plans), tuple(failed))
    issues = verify_built_mod_artifacts(
        cli_ctx.repo_root, artifact_specs(), [(plan.mod_id, plan.loader) for plan in plans]
    )
    return BuildResult(tuple((plan.mod_id, plan.loader) for plan in plans), artifact_issues=tuple(issues))


def deploy_target_dir(loader: LoaderName, game_path: Path, *, scripts: bool) -> tuple[Path, str, bool]:
    if loader == "lunaris":
        if scripts:
            raise ValueError("--scripts is only supported for BepInEx mods")
        return lunaris_plugins_dir(game_path), "Lunaris plugins", False
    if loader != "bepinex":
        raise ValueError(f"Unsupported deploy loader: {loader}")
    if scripts:
        return bepinex_scripts_dir(game_path), "BepInEx/scripts (hot reload)", True
    return bepinex_plugins_dir(game_path), "BepInEx/plugins", False


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} is not a regular file: {path}")


def deploy_files(
    cli_ctx: CLIContext,
    mod_id: str,
    loader: LoaderName,
    game_path: Path,
    *,
    scripts: bool,
    manifest_parser: Callable[..., Any] | None = None,
) -> tuple[DeployFile, ...]:
    definition = lookup_mod(mod_id)
    source_mod_dir = mod_dir(cli_ctx, mod_id)
    manifest_path = source_mod_dir / "thunderstore.toml"
    if (
        loader == "bepinex"
        and not scripts
        and manifest_path.is_file()
        and definition.thunderstore_id
        and manifest_parser is not None
    ):
        namespace, name = definition.thunderstore_id.split("/", 1)
        manifest = manifest_parser(
            manifest_path, source_mod_dir, cli_ctx.repo_root, expected_namespace=namespace, expected_name=name
        )
        manifest_files = tuple(
            DeployFile(copy.source, game_path / "BepInEx" / Path(*copy.target.parts) / copy.source.name)
            for copy in manifest.copies
        )
        if not any(file.source.name == definition.dll_name for file in manifest_files):
            raise ValueError(f"Thunderstore manifest does not deploy {definition.dll_name}")
        return manifest_files
    target_dir, _, copy_pdb = deploy_target_dir(loader, game_path, scripts=scripts)
    output_dir = mod_output_dir(cli_ctx, mod_id, loader)
    runtime_files = [DeployFile(output_dir / definition.dll_name, target_dir / definition.dll_name)]
    if copy_pdb:
        pdb = output_dir / definition.dll_name.replace(".dll", ".pdb")
        if pdb.is_file():
            runtime_files.append(DeployFile(pdb, target_dir / pdb.name))
    return tuple(runtime_files)


def conflicting_deploy_paths(
    game_path: Path, mod_id: str, loader: LoaderName, deployed: tuple[DeployFile, ...]
) -> tuple[Path, ...]:
    if loader != "bepinex":
        return ()
    definition = lookup_mod(mod_id)
    dll_name = definition.dll_name
    pdb_name = dll_name.replace(".dll", ".pdb")
    plugins = bepinex_plugins_dir(game_path)
    candidates = {
        plugins / dll_name,
        plugins / pdb_name,
        bepinex_scripts_dir(game_path) / dll_name,
        bepinex_scripts_dir(game_path) / pdb_name,
    }
    if definition.thunderstore_id:
        package_name = definition.thunderstore_id.split("/", 1)[1]
        candidates.update({plugins / package_name / dll_name, plugins / package_name / pdb_name})
    targets = {file.target for file in deployed}
    return tuple(sorted(candidates - targets))


def plan_deploy(
    mod: str | None,
    loader: str,
    game_path: Path,
    *,
    scripts: bool,
) -> DeploySelection:
    targets = tuple(resolve_deploy_targets(mod, loader))
    target_loaders = {target_loader for _, target_loader in targets}
    if len(target_loaders) != 1:
        raise ValueError("default deployment spans both native loaders; choose --loader bepinex or --loader lunaris")
    target_loader = next(iter(target_loaders))
    if scripts and target_loader != "bepinex":
        raise ValueError("--scripts is only supported for BepInEx mods")
    validate_loader_activation(game_path, target_loader)
    return DeploySelection(game_path, targets, target_loader, scripts)


def prepare_deploy(
    cli_ctx: CLIContext,
    selection: DeploySelection,
    *,
    manifest_parser: Callable[..., Any] | None = None,
) -> DeployPlan:
    files = tuple(
        (
            mod_id,
            deploy_files(
                cli_ctx,
                mod_id,
                selected_loader,
                selection.game_path,
                scripts=selection.scripts,
                manifest_parser=manifest_parser,
            ),
        )
        for mod_id, selected_loader in selection.targets
    )
    conflicts = tuple(
        (mod_id, conflicting_deploy_paths(selection.game_path, mod_id, selected_loader, mod_files))
        for (mod_id, selected_loader), (_name, mod_files) in zip(selection.targets, files, strict=True)
    )
    for _mod_id, mod_files in files:
        for file in mod_files:
            _require_regular_file(file.source, "mod deploy input")
    for _mod_id, paths in conflicts:
        for path in paths:
            if path.exists() and (not path.is_file() or path.is_symlink()):
                raise ValueError(f"conflicting mod deploy path is not a regular file: {path}")
    return DeployPlan(
        selection.game_path,
        selection.targets,
        selection.target_loader,
        files,
        conflicts,
        selection.scripts,
    )


def deploy_mods(plan: DeployPlan) -> DeployResult:
    copied: list[DeployFile] = []
    removed: list[Path] = []
    for mod_id, _loader in plan.targets:
        for path in plan.conflicts_for(mod_id):
            if path.exists():
                path.unlink()
                removed.append(path)
        for file in plan.files_for(mod_id):
            file.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file.source, file.target)
            copied.append(file)
    return DeployResult(tuple(copied), tuple(removed), activate_loader(plan.game_path, plan.target_loader))


def plan_launch(cli_ctx: CLIContext) -> LaunchPlan:
    game_path = get_game_path(cli_ctx)
    if not game_path:
        raise ValueError(f"game installation not found for variant {cli_ctx.variant!r}")
    variant_config = cli_ctx.config.variants.get(cli_ctx.variant)
    if variant_config is None or not variant_config.app_id:
        raise ValueError(f"Steam App ID not configured for variant {cli_ctx.variant!r}")
    bottle = os.environ.get("CROSSOVER_BOTTLE") or crossover_bottle_for_path(game_path)
    if sys.platform == "darwin" and bottle:
        if not CROSSOVER_START.exists():
            raise ValueError(f"CrossOver launcher not found: {CROSSOVER_START}")
        return LaunchPlan(
            (str(CROSSOVER_START), "--bottle", bottle, "--no-wait", f"steam://rungameid/{variant_config.app_id}"),
            game_path,
            bottle,
        )
    executable = game_path / "Erenshor.exe"
    if not executable.exists():
        raise ValueError(f"Game executable not found: {executable}")
    return LaunchPlan((str(executable),), game_path, None)


def launch_game(cli_ctx: CLIContext, *, runner: ProcessRunner = subprocess.run) -> LaunchPlan:
    plan = plan_launch(cli_ctx)
    result = runner(list(plan.command), check=False)
    if plan.crossover_bottle is not None and result.returncode != 0:
        raise RuntimeError(f"Steam launch failed with exit code {result.returncode}")
    return plan


__all__ = [
    "CROSSOVER_BOTTLES_ROOT",
    "CROSSOVER_START",
    "LOADER_PROXY_CANDIDATES",
    "REQUIRED_DLLS",
    "BuildPlan",
    "BuildResult",
    "DeployFile",
    "DeployPlan",
    "DeployResult",
    "DeploySelection",
    "LaunchPlan",
    "SetupResult",
    "activate_loader",
    "bepinex_plugins_dir",
    "bepinex_scripts_dir",
    "build_mods",
    "check_dotnet_available",
    "configured_lunaris_lib_dir",
    "conflicting_deploy_paths",
    "crossover_bottle_for_path",
    "deploy_files",
    "deploy_mods",
    "deploy_target_dir",
    "detect_active_loader",
    "discover_crossover_game_path",
    "ensure_lunaris_libs_cached",
    "file_sha256",
    "find_lunaris_dll",
    "find_lunaris_shared_lib",
    "get_game_path",
    "launch_game",
    "loader_proxy_sources",
    "loader_status",
    "lunaris_plugins_dir",
    "managed_dir",
    "mod_dir",
    "mod_lib_dir",
    "mod_loader_lib_dir",
    "mod_output_dir",
    "plan_builds",
    "plan_deploy",
    "plan_launch",
    "prepare_deploy",
    "resolve_build_targets",
    "resolve_deploy_targets",
    "setup_mods",
    "validate_loader_activation",
]


def format_build_artifact_issues(result: BuildResult) -> str:
    return format_artifact_issues(result.artifact_issues)
