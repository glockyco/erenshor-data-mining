"""Behavioral tests for loader-targeted mod CLI infrastructure."""

from __future__ import annotations

import stat
import subprocess
import zipfile
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
import typer

from erenshor.application.mods import local_workflow, release
from erenshor.application.mods.artifacts import REQUIRED_DLLS, ArtifactIssue, ModArtifactSpec
from erenshor.application.mods.catalog import artifact_specs, iter_mods, lookup_mod, public_mods
from erenshor.application.process_session import ProcessIdentity
from erenshor.cli.commands import mod as mod_command

_DISCOVER_CROSSOVER_GAME_PATH = local_workflow.discover_crossover_game_path


def _mod(mod_id: str):
    return lookup_mod(mod_id)


def _ctx(
    tmp_path: Path,
    *,
    variant: str = "main",
    game_paths: dict[str, Path] | None = None,
    game_installs: dict[str, Path | None] | None = None,
    mods_config: Any | None = None,
) -> SimpleNamespace:
    """Build the smallest CLI context needed by mod command helpers."""
    paths = game_paths or {variant: tmp_path / variant}
    installs = game_installs or {}
    app_ids = {"main": "2382520", "playtest": "3090030", "demo": "2522260"}
    variants = {
        name: SimpleNamespace(
            app_id=app_ids.get(name, "0"),
            resolved_game_files=lambda _root, path=path: path,
            resolved_game_install=lambda _root, path=installs.get(name): path,
        )
        for name, path in paths.items()
    }
    if mods_config is None:
        mods_config = SimpleNamespace(
            lunaris_lib_dir=None,
            lunaris_libs_url="https://invalid.invalid/LunarisLibs.zip",
        )
    config = SimpleNamespace(
        variants=variants,
        global_=SimpleNamespace(mods=mods_config),
    )
    cli_ctx = SimpleNamespace(config=config, variant=variant, repo_root=tmp_path)
    return SimpleNamespace(obj=cli_ctx)


@pytest.fixture(autouse=True)
def _disable_workstation_crossover_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must never resolve or modify the developer's real game install."""
    monkeypatch.setattr(local_workflow, "discover_crossover_game_path", lambda _app_id: None)


def test_registry_inventory_declares_all_loader_targets_and_public_surface() -> None:
    definitions = tuple(iter_mods())
    assert tuple(definition.mod_id for definition in definitions) == (
        "interactive-map-companion",
        "justice-for-f7",
        "sprint",
        "map-tile-capture",
        "adventure-guide",
    )
    assert {definition.mod_id for definition in public_mods()} == {
        "adventure-guide",
        "interactive-map-companion",
        "justice-for-f7",
        "sprint",
    }
    assert all(definition.loaders == ("bepinex", "lunaris") for definition in definitions)
    assert {definition.mod_id: definition.default_loader for definition in definitions} == {
        "adventure-guide": "lunaris",
        "interactive-map-companion": "bepinex",
        "justice-for-f7": "lunaris",
        "map-tile-capture": "bepinex",
        "sprint": "lunaris",
    }


def test_artifact_specs_are_exactly_derived_from_ordered_catalog() -> None:
    assert artifact_specs() == (
        ModArtifactSpec(
            "interactive-map-companion",
            Path("src/mods/InteractiveMapCompanion"),
            "Interactive Map Companion",
            "InteractiveMapCompanion.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/InteractiveMapCompanion",
            ("InteractiveMapCompanion.dll",),
        ),
        ModArtifactSpec(
            "justice-for-f7",
            Path("src/mods/JusticeForF7"),
            "Justice for F7",
            "JusticeForF7.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/JusticeForF7",
            ("JusticeForF7.dll",),
        ),
        ModArtifactSpec(
            "sprint",
            Path("src/mods/Sprint"),
            "Sprint",
            "Sprint.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/Sprint",
            ("Sprint.dll",),
        ),
        ModArtifactSpec(
            "map-tile-capture",
            Path("src/mods/MapTileCapture"),
            "Map Tile Capture",
            "MapTileCapture.dll",
            ("bepinex", "lunaris"),
            False,
            None,
        ),
        ModArtifactSpec(
            "adventure-guide",
            Path("src/mods/AdventureGuide"),
            "Adventure Guide",
            "AdventureGuide.dll",
            ("bepinex", "lunaris"),
            True,
            "WoW_Much/AdventureGuide",
            (
                "AdventureGuide.dll",
                "ImGui.NET.dll",
                "Newtonsoft.Json.dll",
                "System.Numerics.Vectors.dll",
                "System.Runtime.CompilerServices.Unsafe.dll",
                "cimgui.dll",
            ),
        ),
    )


def test_build_target_resolution_is_deterministic_for_default_and_all() -> None:
    assert local_workflow.resolve_build_targets(None, "default") == [
        ("interactive-map-companion", "bepinex"),
        ("justice-for-f7", "lunaris"),
        ("sprint", "lunaris"),
        ("map-tile-capture", "bepinex"),
        ("adventure-guide", "lunaris"),
    ]
    targets = local_workflow.resolve_build_targets("sprint", "all")
    assert targets == [("sprint", "bepinex"), ("sprint", "lunaris")]
    assert local_workflow.resolve_deploy_targets("adventure-guide", "default") == [("adventure-guide", "lunaris")]


def test_target_resolution_rejects_invalid_and_unsupported_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="Unsupported loader target"):
        local_workflow.resolve_build_targets("sprint", "invalid")
    with pytest.raises(ValueError, match="all"):
        local_workflow.resolve_deploy_targets("sprint", "all")

    changed = tuple(
        replace(definition, loaders=("lunaris",)) if definition.mod_id == "sprint" else definition
        for definition in iter_mods()
    )
    changed_by_id = {definition.mod_id: definition for definition in changed}
    monkeypatch.setattr(local_workflow, "lookup_mod", changed_by_id.__getitem__)
    monkeypatch.setattr(local_workflow, "iter_mods", lambda: iter(changed))
    with pytest.raises(ValueError, match="does not support"):
        local_workflow.resolve_build_targets("sprint", "bepinex")
    assert local_workflow.resolve_build_targets("sprint", "all") == [("sprint", "lunaris")]


def test_catalog_definitions_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        _mod("sprint").loaders = ("lunaris",)


def test_output_paths_are_isolated_by_loader(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path).obj
    bepinex = local_workflow.mod_output_dir(ctx, "sprint", "bepinex")
    lunaris = local_workflow.mod_output_dir(ctx, "sprint", "lunaris")
    assert bepinex == tmp_path / "src/mods/Sprint/bin/Debug/netstandard2.1/bepinex"
    assert lunaris == tmp_path / "src/mods/Sprint/bin/Debug/netstandard2.1/lunaris"
    assert bepinex != lunaris


def test_dotnet_build_receives_loader_property(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / _mod("sprint").directory
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / "Assembly-CSharp.dll").write_bytes(b"reference")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(local_workflow, "verify_built_mod_artifacts", lambda *_args: ())
    monkeypatch.setattr(mod_command.subprocess, "run", fake_run)
    local_workflow.build_mods(ctx, "sprint", loader="lunaris", runner=mod_command.subprocess.run)

    assert calls[0][0] == [
        "dotnet",
        "build",
        "--configuration",
        "Debug",
        "-p:ModLoader=lunaris",
    ]


def test_built_verifier_receives_exact_resolved_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    targets = [("sprint", "lunaris"), ("justice-for-f7", "bepinex")]
    for mod_id, _loader in targets:
        mod_dir = tmp_path / _mod(mod_id).directory
        (mod_dir / "lib").mkdir(parents=True)
        (mod_dir / "lib" / "Assembly-CSharp.dll").write_bytes(b"reference")

    forwarded: list[tuple[str, str]] = []
    monkeypatch.setattr(local_workflow, "resolve_build_targets", lambda *_args: targets)
    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    monkeypatch.setattr(
        local_workflow,
        "verify_built_mod_artifacts",
        lambda _root, _specs, received: forwarded.extend(received) or (),
    )

    local_workflow.build_mods(ctx, loader="all", runner=mod_command.subprocess.run)

    assert forwarded == targets


def test_built_artifact_failure_exits_before_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / _mod("sprint").directory
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / "Assembly-CSharp.dll").write_bytes(b"reference")
    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    monkeypatch.setattr(
        local_workflow,
        "verify_built_mod_artifacts",
        lambda *_args: (ArtifactIssue("sprint", "built-output-dll", "missing"),),
    )

    result = local_workflow.build_mods(ctx, "sprint", loader="lunaris", runner=mod_command.subprocess.run)

    assert result.artifact_issues == (ArtifactIssue("sprint", "built-output-dll", "missing"),)


def test_failed_build_does_not_run_built_verifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / _mod("sprint").directory
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / "Assembly-CSharp.dll").write_bytes(b"reference")
    verification_calls: list[object] = []
    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    monkeypatch.setattr(
        local_workflow,
        "verify_built_mod_artifacts",
        lambda *_args: verification_calls.append(True) or (),
    )

    result = local_workflow.build_mods(ctx, "sprint", loader="lunaris", runner=mod_command.subprocess.run)

    assert result.failed == ("sprint (lunaris)",)
    assert verification_calls == []


def test_deploy_target_routing_and_scripts_guard(tmp_path: Path) -> None:
    assert local_workflow.deploy_target_dir("bepinex", tmp_path, scripts=False) == (
        tmp_path / "BepInEx/plugins",
        "BepInEx/plugins",
        False,
    )
    assert local_workflow.deploy_target_dir("bepinex", tmp_path, scripts=True) == (
        tmp_path / "BepInEx/scripts",
        "BepInEx/scripts (hot reload)",
        True,
    )
    assert local_workflow.deploy_target_dir("lunaris", tmp_path, scripts=False) == (
        tmp_path / "plugins",
        "Lunaris plugins",
        False,
    )
    with pytest.raises(ValueError, match="BepInEx"):
        local_workflow.deploy_target_dir("lunaris", tmp_path, scripts=True)


@pytest.mark.parametrize("variant", ["main", "playtest", "demo"])
def test_game_path_uses_selected_variant(variant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ERENSHOR_GAME_PATH", raising=False)
    game = tmp_path / variant
    (game / "Erenshor_Data" / "Managed").mkdir(parents=True)
    ctx = _ctx(tmp_path, variant=variant, game_paths={variant: game}).obj
    assert local_workflow.get_game_path(ctx, allow_extracted=True) == game


def test_game_path_configured_variant_install_precedes_global_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "playtest-install"
    configured.mkdir()
    environment = tmp_path / "main-install"
    environment.mkdir()
    ctx = _ctx(
        tmp_path,
        variant="playtest",
        game_paths={"playtest": tmp_path / "extracted"},
        game_installs={"playtest": configured},
    ).obj
    monkeypatch.setenv("ERENSHOR_GAME_PATH", str(environment))

    assert local_workflow.get_game_path(ctx) == configured


@pytest.mark.parametrize(
    ("variant", "app_id", "install_dir"),
    [
        ("main", "2382520", "Erenshor"),
        ("playtest", "3090030", "Erenshor Playtest"),
        ("demo", "2522260", "Erenshor Demo"),
    ],
)
def test_crossover_discovery_uses_selected_steam_app(
    variant: str,
    app_id: str,
    install_dir: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bottles = tmp_path / "Bottles"
    steamapps = bottles / "QA" / "drive_c/Program Files (x86)/Steam/steamapps"
    game = steamapps / "common" / install_dir
    (game / "Erenshor_Data" / "Managed").mkdir(parents=True)
    manifest = steamapps / f"appmanifest_{app_id}.acf"
    manifest.write_text(f'"AppState"\n{{\n\t"installdir"\t\t"{install_dir}"\n}}\n')
    monkeypatch.setattr(local_workflow, "CROSSOVER_BOTTLES_ROOT", bottles)
    monkeypatch.setattr(local_workflow.sys, "platform", "darwin")
    monkeypatch.setenv("CROSSOVER_BOTTLE", "QA")

    assert _DISCOVER_CROSSOVER_GAME_PATH(app_id) == game


def test_game_path_environment_override_has_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configured = tmp_path / "playtest"
    (configured / "Erenshor_Data" / "Managed").mkdir(parents=True)
    environment = tmp_path / "environment"
    environment.mkdir()
    ctx = _ctx(tmp_path, variant="playtest", game_paths={"playtest": configured}).obj
    monkeypatch.setenv("ERENSHOR_GAME_PATH", str(environment))
    assert local_workflow.get_game_path(ctx) == environment


def _write_loader_proxies(game: Path, *, active: str = "lunaris") -> None:
    game.mkdir(parents=True, exist_ok=True)
    (game / "winhttp.bepinex-backup.dll").write_bytes(b"bepinex-proxy")
    (game / "winhttp.lunaris.dll").write_bytes(b"lunaris-proxy")
    (game / "winhttp.dll").write_bytes(f"{active}-proxy".encode())


def test_loader_activation_switches_in_place_and_is_idempotent(tmp_path: Path) -> None:
    game = tmp_path / "game"
    _write_loader_proxies(game)

    sources = local_workflow.loader_proxy_sources(game)
    assert local_workflow.detect_active_loader(game, sources) == "lunaris"
    assert local_workflow.activate_loader(game, "bepinex") is True
    assert (game / "winhttp.dll").read_bytes() == b"bepinex-proxy"
    assert (game / "winhttp.lunaris.dll").read_bytes() == b"lunaris-proxy"
    assert local_workflow.activate_loader(game, "bepinex") is False
    assert local_workflow.activate_loader(game, "lunaris") is True
    assert (game / "winhttp.dll").read_bytes() == b"lunaris-proxy"


def test_loader_activation_refuses_unknown_active_proxy(tmp_path: Path) -> None:
    game = tmp_path / "game"
    _write_loader_proxies(game)
    active = game / "winhttp.dll"
    active.write_bytes(b"unrelated-winhttp-proxy")

    with pytest.raises(ValueError, match="unrecognized"):
        local_workflow.activate_loader(game, "bepinex")

    assert active.read_bytes() == b"unrelated-winhttp-proxy"


def test_loader_activation_rejects_conflicting_saved_proxies(tmp_path: Path) -> None:
    game = tmp_path / "game"
    _write_loader_proxies(game)
    (game / "winhttp.dll.bepinex-backup").write_bytes(b"different-bepinex-proxy")

    with pytest.raises(ValueError, match="conflicting bepinex"):
        local_workflow.activate_loader(game, "bepinex")


def test_game_path_rejects_environment_override_for_another_steam_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main = tmp_path / "main"
    main.mkdir()
    (main / "steam_appid.txt").write_text("2382520\n")
    ctx = _ctx(tmp_path, variant="demo", game_paths={"demo": tmp_path / "demo"}).obj
    monkeypatch.setenv("ERENSHOR_GAME_PATH", str(main))

    assert local_workflow.get_game_path(ctx) is None


def test_deploy_routes_explicit_loader_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    game = tmp_path / "game"
    _write_loader_proxies(game)
    output = local_workflow.mod_output_dir(ctx, "sprint", "bepinex")
    output.mkdir(parents=True)
    (output / "Sprint.dll").write_bytes(b"bepinex")
    calls: list[str] = []
    monkeypatch.setattr(local_workflow, "get_game_path", lambda _ctx: game)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"])
        or local_workflow.BuildResult(((mod or "sprint", kwargs["loader"]),)),
    )

    mod_command.deploy(ctx=SimpleNamespace(obj=ctx), mod="sprint", loader="bepinex", scripts=False)

    assert calls == ["bepinex"]
    assert (game / "BepInEx" / "plugins" / "Sprint.dll").read_bytes() == b"bepinex"
    assert (game / "winhttp.dll").read_bytes() == b"bepinex-proxy"


def test_bepinex_deploy_uses_thunderstore_runtime_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    game = tmp_path / "game"
    _write_loader_proxies(game)
    stale = game / "BepInEx/plugins/AdventureGuide.dll"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale-plugin")
    mod_dir = tmp_path / _mod("adventure-guide").directory
    output = mod_dir / "bin/Debug/netstandard2.1/bepinex"
    output.mkdir(parents=True)
    (output / "AdventureGuide.dll").write_bytes(b"plugin")
    (output / "ImGui.NET.dll").write_bytes(b"imgui")
    thunderstore = mod_dir / "thunderstore"
    thunderstore.mkdir()
    (thunderstore / "icon.png").write_bytes(b"icon")
    (thunderstore / "README.md").write_text("# Fixture\n")
    (thunderstore / "CHANGELOG.md").write_text("# Changelog\n")
    (mod_dir / "thunderstore.toml").write_text(
        """[package]
namespace = "WoW_Much"
name = "AdventureGuide"

[build]
icon = "./thunderstore/icon.png"
readme = "./thunderstore/README.md"
changelog = "./thunderstore/CHANGELOG.md"
outdir = "./thunderstore/build"

[[build.copy]]
source = "./bin/Debug/netstandard2.1/bepinex/AdventureGuide.dll"
target = "plugins/AdventureGuide/"

[[build.copy]]
source = "./bin/Debug/netstandard2.1/bepinex/ImGui.NET.dll"
target = "plugins/AdventureGuide/"
"""
    )
    monkeypatch.setattr(local_workflow, "get_game_path", lambda _ctx: game)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: local_workflow.BuildResult((("adventure-guide", "bepinex"),)),
    )

    mod_command.deploy(
        ctx=SimpleNamespace(obj=ctx),
        mod="adventure-guide",
        loader="bepinex",
        scripts=False,
    )

    deployed = game / "BepInEx/plugins/AdventureGuide"
    assert (deployed / "AdventureGuide.dll").read_bytes() == b"plugin"
    assert (deployed / "ImGui.NET.dll").read_bytes() == b"imgui"
    assert not stale.exists()
    assert (game / "winhttp.dll").read_bytes() == b"bepinex-proxy"


def test_deploy_rejects_mixed_default_loaders_before_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: pytest.fail("mixed deploy must not build"),
    )

    with pytest.raises(typer.Exit):
        mod_command.deploy(ctx, mod=None, loader="default", scripts=False)


def test_deploy_rejects_scripts_for_default_lunaris_before_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: pytest.fail("invalid deploy must not build"),
    )
    with pytest.raises(typer.Exit):
        mod_command.deploy(ctx, mod="sprint", loader="default", scripts=True)


PUBLIC_THUNDERSTORE_IDS = {
    "adventure-guide": "WoW_Much/AdventureGuide",
    "interactive-map-companion": "WoW_Much/InteractiveMapCompanion",
    "sprint": "WoW_Much/Sprint",
    "justice-for-f7": "WoW_Much/JusticeForF7",
}


def _write_fixture_file(path: Path, content: bytes | str = b"fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)
    return path


def _thunderstore_fixture(
    tmp_path: Path,
    mod_id: str = "sprint",
    *,
    icon: str = "./vault/icon.png",
    source: str | None = None,
    target: str | None = None,
    outdir: str = "./thunderstore/build",
    readme: str = "./thunderstore/README.md",
    changelog: str = "./thunderstore/CHANGELOG.md",
) -> tuple[Path, Path, Path]:
    """Create a small manifest and all declared regular-file inputs."""
    definition = _mod(mod_id)
    mod_dir = tmp_path / definition.directory
    manifest_path = mod_dir / "thunderstore.toml"
    source = source or f"./bin/Debug/netstandard2.1/bepinex/{definition.dll_name}"
    target = target or f"plugins/{definition.dll_name[:-4]}/"

    def write_declared(raw: str, content: bytes | str) -> None:
        candidate = (mod_dir / raw.removeprefix("./")).resolve(strict=False)
        if candidate.is_relative_to(mod_dir.resolve()):
            _write_fixture_file(candidate, content)

    source_path = (mod_dir / source.removeprefix("./")).resolve(strict=False)
    write_declared(source, b"compiled dll")
    write_declared(icon, b"icon")
    write_declared(readme, "# Fixture\n")
    write_declared(changelog, "# Changelog\n")
    namespace, name = PUBLIC_THUNDERSTORE_IDS.get(mod_id, "WoW_Much/Fixture").split("/")

    def toml_string(raw: str) -> str:
        return raw.replace("\\", "\\\\").replace('"', '\\"')

    manifest = f"""[package]
namespace = "{namespace}"
name = "{name}"

[build]
icon = "{toml_string(icon)}"
readme = "{toml_string(readme)}"
changelog = "{toml_string(changelog)}"
outdir = "{toml_string(outdir)}"

[[build.copy]]
source = "{toml_string(source)}"
target = "{toml_string(target)}"
"""
    _write_fixture_file(manifest_path, manifest)
    outdir_path = (mod_dir / outdir.removeprefix("./")).resolve(strict=False)
    if outdir_path.is_relative_to(mod_dir.resolve()):
        outdir_path.mkdir(parents=True, exist_ok=True)
    return mod_dir, manifest_path, source_path


def _valid_package(
    manifest: Any,
    version: str,
    *,
    names: set[str] | None = None,
    symlink_name: str | None = None,
) -> Path:
    package_path = manifest.outdir / f"{manifest.namespace}-{manifest.name}-{version}.zip"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    entries = names or (set(manifest.allowed_package_names) - {"CHANGELOG.md"})
    with zipfile.ZipFile(package_path, "w") as archive:
        for name in entries:
            if name == symlink_name:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, "target")
            else:
                archive.writestr(name, b"package")
    return package_path


def _tcli_runner(
    manifests: dict[str, Any],
    calls: list[tuple[list[str], dict[str, Any]]],
    *,
    build_returncode: int = 0,
    publish_returncode: int = 0,
    after_build: Any | None = None,
) -> Any:
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        config_path = str(args[-1])
        if args[1] == "build":
            if build_returncode == 0:
                _valid_package(manifests[config_path], args[3])
                if after_build is not None:
                    after_build(manifests[config_path])
            return subprocess.CompletedProcess(args, build_returncode)
        return subprocess.CompletedProcess(args, publish_returncode)

    return run


def _prepare_thunderstore_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mod_ids: list[str],
    *,
    version: str = "2099.101.0",
) -> tuple[
    SimpleNamespace,
    dict[str, Any],
    list[tuple[str, str, dict[str, Any]]],
    list[tuple[list[str], dict[str, Any]]],
]:
    ctx = _ctx(tmp_path).obj
    manifests: dict[str, Any] = {}
    for mod_id in mod_ids:
        _mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, mod_id)
        manifests[str(manifest_path)] = release.parse_thunderstore_manifest(
            manifest_path,
            manifest_path.parent,
            tmp_path,
            expected_namespace="WoW_Much",
            expected_name=PUBLIC_THUNDERSTORE_IDS[mod_id].split("/", 1)[1],
        )

    monkeypatch.setattr(release, "check_tcli_available", lambda: True)
    monkeypatch.setattr(release, "get_thunderstore_version", lambda _namespace, _name: version)
    builds: list[tuple[str, str, dict[str, Any]]] = []

    def build(_ctx: Any, mod: str | None = None, **kwargs: Any) -> None:
        kwargs.pop("runner", None)
        builds.append((mod or "", kwargs.pop("loader", ""), kwargs))

    monkeypatch.setattr(local_workflow, "build_mods", build)
    subprocess_calls: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        _tcli_runner(manifests, subprocess_calls),
    )
    return SimpleNamespace(obj=ctx), manifests, builds, subprocess_calls


def test_thunderstore_registry_has_exact_public_ids() -> None:
    assert {
        definition.mod_id: definition.thunderstore_id
        for definition in iter_mods()
        if definition.thunderstore_id is not None
    } == (PUBLIC_THUNDERSTORE_IDS)


def test_internal_mod_rejected_before_build_or_tcli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    monkeypatch.setattr(release, "check_tcli_available", lambda: True)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: pytest.fail("built internal mod"),
    )
    monkeypatch.setattr(mod_command.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("ran tcli"))

    with pytest.raises(typer.Exit):
        mod_command.thunderstore(SimpleNamespace(obj=ctx), mod="map-tile-capture", dry_run=True)


def test_real_upload_requires_exactly_one_mod_and_non_placeholder_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _ctx(tmp_path).obj
    monkeypatch.setattr(release, "check_tcli_available", lambda: True)
    monkeypatch.setenv("TCLI_AUTH_TOKEN", "valid-sentinel")
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: pytest.fail("built unexpectedly"),
    )
    monkeypatch.setattr(mod_command.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("ran tcli"))

    with pytest.raises(typer.Exit):
        mod_command.thunderstore(SimpleNamespace(obj=ctx), mod=None, dry_run=False)
    monkeypatch.setenv("TCLI_AUTH_TOKEN", "your_token_here")
    with pytest.raises(typer.Exit):
        mod_command.thunderstore(SimpleNamespace(obj=ctx), mod="sprint", dry_run=False)


def test_tcli_missing_is_rejected_before_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    monkeypatch.setattr(release, "check_tcli_available", lambda: False)
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda *_args, **_kwargs: pytest.fail("built unexpectedly"),
    )

    with pytest.raises(typer.Exit):
        mod_command.thunderstore(SimpleNamespace(obj=ctx), mod="sprint", dry_run=True)


def test_dry_run_builds_all_public_mods_and_never_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, _manifests, builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, list(PUBLIC_THUNDERSTORE_IDS))
    mod_command.thunderstore(ctx, mod=None, dry_run=True)

    expected = [definition.mod_id for definition in public_mods() if definition.thunderstore_id is not None]
    assert [mod_id for mod_id, _loader, _kwargs in builds] == expected
    assert all(loader == "bepinex" for _mod_id, loader, _kwargs in builds)
    assert [args[1] for args, _kwargs in calls] == ["build"] * 4


def test_all_selected_releases_are_preflighted_before_any_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _ctx(tmp_path).obj
    for mod_id in PUBLIC_THUNDERSTORE_IDS:
        _thunderstore_fixture(tmp_path, mod_id)
    bad_manifest = tmp_path / _mod("sprint").directory / "thunderstore.toml"
    bad_manifest.write_text(bad_manifest.read_text().replace("./vault/icon.png", "./missing.png"))
    builds: list[str] = []
    monkeypatch.setattr(release, "check_tcli_available", lambda: True)
    monkeypatch.setattr(release, "get_thunderstore_version", lambda *_args: "2099.101.0")
    monkeypatch.setattr(local_workflow, "build_mods", lambda _ctx, mod=None, **_kwargs: builds.append(mod or ""))
    monkeypatch.setattr(mod_command.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("ran tcli"))

    with pytest.raises(typer.Exit):
        mod_command.thunderstore(SimpleNamespace(obj=ctx), mod=None, dry_run=True)
    assert builds == []


def test_manifest_is_toml_driven_and_reuses_vault_icon(tmp_path: Path) -> None:
    mod_dir, manifest_path, source = _thunderstore_fixture(tmp_path, "adventure-guide")
    manifest = release.parse_thunderstore_manifest(
        manifest_path,
        mod_dir,
        tmp_path,
        expected_namespace="WoW_Much",
        expected_name="AdventureGuide",
    )

    assert manifest.icon == mod_dir / "vault/icon.png"
    assert manifest.readme == mod_dir / "thunderstore/README.md"
    assert manifest.changelog == mod_dir / "thunderstore/CHANGELOG.md"
    assert manifest.outdir == mod_dir / "thunderstore/build"
    assert manifest.copies[0].source == source
    assert str(manifest.copies[0].package_path) == "plugins/AdventureGuide/AdventureGuide.dll"
    assert {manifest.icon, manifest.readme, manifest.changelog, source} <= set(manifest.input_paths)
    assert {
        "manifest.json",
        "icon.png",
        "README.md",
        "CHANGELOG.md",
        "plugins/AdventureGuide/AdventureGuide.dll",
    } <= set(manifest.allowed_package_names)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("icon", "../../../../outside.png"),
        ("readme", "../../../../outside.md"),
        ("changelog", "../../../../outside.md"),
        ("outdir", "../../../../outside"),
        ("copy_source", "../../../../outside.dll"),
        ("copy_target", "../escape/"),
        ("copy_target", "/absolute/"),
        ("copy_target", "plugins\\Sprint\\Sprint.dll"),
    ],
)
def test_manifest_rejects_path_escape_and_non_posix_copy_targets(tmp_path: Path, field: str, value: str) -> None:
    fixture_kwargs: dict[str, str] = {}
    if field == "copy_source":
        fixture_kwargs["source"] = value
    elif field == "copy_target":
        fixture_kwargs["target"] = value
    else:
        fixture_kwargs[field] = value
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint", **fixture_kwargs)
    with pytest.raises((ValueError, RuntimeError)):
        release.parse_thunderstore_manifest(
            manifest_path,
            mod_dir,
            tmp_path,
            expected_namespace="WoW_Much",
            expected_name="Sprint",
        )


def test_hash_release_inputs_covers_manifest_and_every_declared_asset(tmp_path: Path) -> None:
    mod_dir, manifest_path, source = _thunderstore_fixture(tmp_path, "sprint")
    manifest = release.parse_thunderstore_manifest(
        manifest_path,
        mod_dir,
        tmp_path,
        expected_namespace="WoW_Much",
        expected_name="Sprint",
    )
    initial = dict(release.hash_release_inputs(manifest))
    assert set(initial) == set(manifest.input_paths)
    (mod_dir / "vault/icon.png").write_bytes(b"changed icon")
    changed = dict(release.hash_release_inputs(manifest))
    assert changed[mod_dir / "vault/icon.png"] != initial[mod_dir / "vault/icon.png"]
    assert changed[source] == initial[source]


def test_manifest_rejects_directory_copy_source(tmp_path: Path) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint", source="./bin/source-dir")
    source_path = mod_dir / "bin/source-dir"
    source_path.unlink()
    source_path.mkdir(parents=True)
    with pytest.raises((ValueError, RuntimeError)):
        release.parse_thunderstore_manifest(
            manifest_path,
            mod_dir,
            tmp_path,
            expected_namespace="WoW_Much",
            expected_name="Sprint",
        )


@pytest.mark.parametrize(
    "dll_name",
    [
        "Assembly-CSharp.dll",
        "UnityEngine.CoreModule.dll",
        "com.rlabrecque.steamworks.net.dll",
        "BepInEx.dll",
        "Lunaris.dll",
        "0Harmony.dll",
    ],
)
def test_manifest_rejects_proprietary_runtime_copy_sources(tmp_path: Path, dll_name: str) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(
        tmp_path,
        "sprint",
        source=f"./bin/Debug/netstandard2.1/bepinex/{dll_name}",
    )
    with pytest.raises(ValueError, match="game/runtime DLL"):
        release.parse_thunderstore_manifest(
            manifest_path,
            mod_dir,
            tmp_path,
            expected_namespace="WoW_Much",
            expected_name="Sprint",
        )


def test_manifest_rejects_symlinked_copy_source(tmp_path: Path) -> None:
    mod_dir, manifest_path, source = _thunderstore_fixture(tmp_path, "sprint")
    source.unlink()
    linked = tmp_path / "linked.dll"
    linked.write_bytes(b"outside")
    source.symlink_to(linked)
    with pytest.raises((ValueError, RuntimeError)):
        release.parse_thunderstore_manifest(
            manifest_path,
            mod_dir,
            tmp_path,
            expected_namespace="WoW_Much",
            expected_name="Sprint",
        )


class _FixedDate(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return cls(2099, 1, 1, tzinfo=tz)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_thunderstore_version_uses_latest_version_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "datetime", _FixedDate)
    monkeypatch.setattr(
        release,
        "urlopen",
        lambda *_args, **_kwargs: _Response(b'{"latest":{"version_number":"2099.101.3"}}'),
    )
    assert release.get_thunderstore_version("WoW_Much", "Sprint") == "2099.101.4"


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError("https://example.invalid", 503, "unavailable", {}, None),
        URLError("offline"),
        TimeoutError("timed out"),
    ],
)
def test_thunderstore_version_network_http_and_timeout_failures(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    monkeypatch.setattr(release, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(failure))
    with pytest.raises((ValueError, RuntimeError)):
        release.get_thunderstore_version("WoW_Much", "Sprint")


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"{}",
        b'{"latest":{}}',
        b'{"latest":{"version_number":"not-a-version"}}',
        b'{"latest":{"version_number":"2099.1332.0"}}',
    ],
)
def test_thunderstore_version_malformed_or_missing_latest_fails(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    monkeypatch.setattr(release, "urlopen", lambda *_args, **_kwargs: _Response(payload))
    with pytest.raises((ValueError, RuntimeError)):
        release.get_thunderstore_version("WoW_Much", "Sprint")


def test_exact_bepinex_build_and_tcli_argv_and_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, manifests, builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    token = "sentinel-token-not-for-output"
    monkeypatch.setenv("TCLI_AUTH_TOKEN", token)
    mod_command.thunderstore(ctx, mod="sprint", dry_run=False)

    assert builds == [("sprint", "bepinex", {"version": "2099.101.0"})]
    manifest_path = next(iter(manifests))
    mod_dir = tmp_path / _mod("sprint").directory
    assert calls[0] == (
        ["tcli", "build", "--package-version", "2099.101.0", "--config-path", manifest_path],
        {"cwd": mod_dir, "check": False},
    )
    package_path = mod_dir / "thunderstore" / "build" / "WoW_Much-Sprint-2099.101.0.zip"
    with zipfile.ZipFile(package_path) as archive:
        assert archive.read("CHANGELOG.md") == b"# Changelog\n"
    publish_args, publish_kwargs = calls[1]
    assert publish_args == [
        "tcli",
        "publish",
        "--file",
        str(package_path),
        "--config-path",
        manifest_path,
    ]
    assert publish_kwargs["cwd"] == mod_dir
    assert publish_kwargs["check"] is False
    assert publish_kwargs["env"]["TCLI_AUTH_TOKEN"] == token
    assert token not in publish_args


def test_real_sprint_publishes_once_after_validated_zip_without_printing_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _manifests, builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    token = "sentinel-auth-token"
    monkeypatch.setenv("TCLI_AUTH_TOKEN", token)
    mod_command.thunderstore(ctx, mod="sprint", dry_run=False)

    assert len(builds) == 1
    assert [args[1] for args, _kwargs in calls] == ["build", "publish"]
    assert token not in capsys.readouterr().out


def test_static_input_changed_during_build_aborts_before_tcli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, manifests, builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    manifest = manifests[next(iter(manifests))]

    def build_and_mutate(_ctx: Any, mod: str | None = None, **kwargs: Any) -> None:
        kwargs.pop("runner", None)
        builds.append((mod or "", kwargs.pop("loader", ""), kwargs))
        manifest.readme.write_text("changed during mod build")

    monkeypatch.setattr(local_workflow, "build_mods", build_and_mutate)

    with pytest.raises(typer.Exit):
        mod_command.thunderstore(ctx, mod="sprint", dry_run=True)

    assert builds == [("sprint", "bepinex", {"version": "2099.101.0"})]
    assert calls == []


def test_changed_input_aborts_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, manifests, builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    token = "sentinel-auth-token"
    monkeypatch.setenv("TCLI_AUTH_TOKEN", token)
    source = next(path for path in manifests[next(iter(manifests))].input_paths if path.name == "Sprint.dll")

    def mutate(_manifest: Any) -> None:
        source.write_bytes(b"changed after package build")

    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        _tcli_runner(manifests, calls, after_build=mutate),
    )
    with pytest.raises(typer.Exit):
        mod_command.thunderstore(ctx, mod="sprint", dry_run=False)
    assert [args[1] for args, _kwargs in calls] == ["build"]
    assert builds == [("sprint", "bepinex", {"version": "2099.101.0"})]


@pytest.mark.parametrize("build_returncode", [1, 7])
def test_tcli_build_nonzero_aborts_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, build_returncode: int
) -> None:
    ctx, manifests, _builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    monkeypatch.setenv("TCLI_AUTH_TOKEN", "sentinel-auth-token")
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        _tcli_runner(manifests, calls, build_returncode=build_returncode),
    )
    with pytest.raises(typer.Exit):
        mod_command.thunderstore(ctx, mod="sprint", dry_run=False)
    assert [args[1] for args, _kwargs in calls] == ["build"]


def test_tcli_launch_error_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, _manifests, _builds, _calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("tcli disappeared")),
    )
    with pytest.raises(typer.Exit):
        mod_command.thunderstore(ctx, mod="sprint", dry_run=True)


def test_tcli_publish_nonzero_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx, manifests, _builds, calls = _prepare_thunderstore_command(tmp_path, monkeypatch, ["sprint"])
    monkeypatch.setenv("TCLI_AUTH_TOKEN", "sentinel-auth-token")
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        _tcli_runner(manifests, calls, publish_returncode=1),
    )
    with pytest.raises(typer.Exit):
        mod_command.thunderstore(ctx, mod="sprint", dry_run=False)
    assert [args[1] for args, _kwargs in calls] == ["build", "publish"]


def test_package_validation_requires_matching_declared_changelog(tmp_path: Path) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint")
    manifest = release.parse_thunderstore_manifest(
        manifest_path, mod_dir, tmp_path, expected_namespace="WoW_Much", expected_name="Sprint"
    )
    package = _valid_package(manifest, "2099.101.0")

    with pytest.raises(ValueError, match=r"missing entries: CHANGELOG\.md"):
        release.validate_thunderstore_package(package, manifest)

    release.include_thunderstore_changelog(package, manifest)
    release.include_thunderstore_changelog(package, manifest)
    release.validate_thunderstore_package(package, manifest)

    mismatched = _valid_package(
        manifest,
        "2099.101.0",
        names=set(manifest.allowed_package_names),
    )
    with pytest.raises(ValueError, match=r"does not match build\.changelog"):
        release.validate_thunderstore_package(mismatched, manifest)


@pytest.mark.parametrize(
    "bad_names",
    [
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "extra.txt"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "Assembly-CSharp.dll"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "UnityEngine.CoreModule.dll"},
        {
            "manifest.json",
            "icon.png",
            "README.md",
            "plugins/Sprint/Sprint.dll",
            "com.rlabrecque.steamworks.net.dll",
        },
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "BepInEx.dll"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "0Harmony.dll"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "Lunaris.dll"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "../escape.txt"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "/absolute.txt"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "plugins\\Sprint\\bad.dll"},
        {"manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll", "plugins/"},
        {"manifest.json", "icon.png", "README.md"},
    ],
)
def test_package_zip_allowlist_rejects_extra_proprietary_traversal_and_missing_entries(
    tmp_path: Path, bad_names: set[str]
) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint")
    manifest = release.parse_thunderstore_manifest(
        manifest_path, mod_dir, tmp_path, expected_namespace="WoW_Much", expected_name="Sprint"
    )
    package = _valid_package(manifest, "2099.101.0", names=bad_names)
    with pytest.raises((ValueError, RuntimeError)):
        release.validate_thunderstore_package(package, manifest)


def test_package_zip_allowlist_rejects_symlinks_and_duplicate_entries(tmp_path: Path) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint")
    manifest = release.parse_thunderstore_manifest(
        manifest_path, mod_dir, tmp_path, expected_namespace="WoW_Much", expected_name="Sprint"
    )
    package = _valid_package(
        manifest,
        "2099.101.0",
        symlink_name="plugins/Sprint/Sprint.dll",
    )
    with pytest.raises((ValueError, RuntimeError)):
        release.validate_thunderstore_package(package, manifest)

    duplicate = manifest.outdir / "duplicate.zip"
    expected = ["manifest.json", "icon.png", "README.md", "plugins/Sprint/Sprint.dll"]
    with zipfile.ZipFile(duplicate, "w") as archive:
        for name in expected:
            archive.writestr(name, b"package")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("README.md", b"duplicate")
    with pytest.raises((ValueError, RuntimeError)):
        release.validate_thunderstore_package(duplicate, manifest)


def test_package_zip_location_requires_exact_single_expected_zip(tmp_path: Path) -> None:
    mod_dir, manifest_path, _source = _thunderstore_fixture(tmp_path, "sprint")
    manifest = release.parse_thunderstore_manifest(
        manifest_path, mod_dir, tmp_path, expected_namespace="WoW_Much", expected_name="Sprint"
    )
    expected = manifest.outdir / "WoW_Much-Sprint-2099.101.0.zip"
    expected.write_bytes(b"not-a-zip")
    assert release.locate_thunderstore_package(manifest, "2099.101.0") == expected
    with pytest.raises((ValueError, RuntimeError)):
        release.validate_thunderstore_package(expected, manifest)
    expected.unlink()
    with pytest.raises((ValueError, RuntimeError)):
        release.locate_thunderstore_package(manifest, "2099.101.0")


def test_vault_build_is_explicitly_lunaris(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / _mod("sprint").directory
    vault_dir = mod_dir / "vault"
    vault_dir.mkdir(parents=True)
    (vault_dir / "vault.toml").write_text('[mod]\nmod_ref = "sprint"\n')
    (vault_dir / "CHANGELOG.md").write_text("## v2026.716.0\n")
    calls: list[str] = []
    monkeypatch.setattr(release, "get_vault_version", lambda _ref: "2026.716.0")
    monkeypatch.setattr(
        local_workflow,
        "build_mods",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"])
        or local_workflow.BuildResult(((mod or "sprint", kwargs["loader"]),)),
    )

    mod_command.vault(SimpleNamespace(obj=ctx), mod="sprint")

    assert calls == ["lunaris"]


def test_setup_provisions_union_of_loader_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game = tmp_path / "game"
    managed = game / "Erenshor_Data" / "Managed"
    managed.mkdir(parents=True)
    for dll_name in REQUIRED_DLLS:
        (managed / dll_name).write_bytes(b"game")
    (game / "BepInEx" / "core").mkdir(parents=True)
    (game / "BepInEx" / "core" / "0Harmony.dll").write_bytes(b"bepinex harmony")

    lunaris_lib = tmp_path / "lunaris-libs"
    lunaris_lib.mkdir()
    (lunaris_lib / "Lunaris.dll").write_bytes(b"lunaris")
    (lunaris_lib / "0Harmony.dll").write_bytes(b"lunaris harmony")
    for dll_name in ("ImGui.NET.dll", "Newtonsoft.Json.dll", "System.Numerics.Vectors.dll"):
        (lunaris_lib / dll_name).write_bytes(dll_name.encode())
    mods_config = SimpleNamespace(
        lunaris_lib_dir=str(lunaris_lib),
        lunaris_libs_url="https://invalid.invalid/LunarisLibs.zip",
        resolved_lunaris_lib_dir=lambda _root: lunaris_lib,
    )
    ctx = _ctx(tmp_path, game_paths={"main": game}, mods_config=mods_config)
    monkeypatch.setenv("ERENSHOR_GAME_PATH", str(game))

    mod_command.setup(ctx)

    for definition in iter_mods():
        lib_dir = tmp_path / definition.directory / "lib"
        assert all((lib_dir / dll_name).exists() for dll_name in REQUIRED_DLLS)
        assert (lib_dir / "lunaris" / "Lunaris.dll").read_bytes() == b"lunaris"
    assert (
        tmp_path / _mod("interactive-map-companion").directory / "lib/bepinex/0Harmony.dll"
    ).read_bytes() == b"bepinex harmony"
    assert (
        tmp_path / _mod("interactive-map-companion").directory / "lib/lunaris/0Harmony.dll"
    ).read_bytes() == b"lunaris harmony"
    assert (tmp_path / _mod("sprint").directory / "lib/lunaris/0Harmony.dll").read_bytes() == b"lunaris harmony"
    assert (tmp_path / _mod("adventure-guide").directory / "lib/lunaris/ImGui.NET.dll").read_bytes() == b"ImGui.NET.dll"


def test_setup_can_provision_one_bepinex_target_without_lunaris(tmp_path: Path) -> None:
    game = tmp_path / "game"
    managed = game / "Erenshor_Data" / "Managed"
    managed.mkdir(parents=True)
    for dll_name in REQUIRED_DLLS:
        (managed / dll_name).write_bytes(b"game")
    bepinex_core = game / "BepInEx" / "core"
    bepinex_core.mkdir(parents=True)
    (bepinex_core / "0Harmony.dll").write_bytes(b"bepinex harmony")
    ctx = _ctx(tmp_path, game_paths={"main": game})

    mod_command.setup(ctx, mod="map-tile-capture", loader="bepinex")

    lib_dir = tmp_path / _mod("map-tile-capture").directory / "lib"
    assert all((lib_dir / dll_name).exists() for dll_name in REQUIRED_DLLS)
    assert (lib_dir / "bepinex" / "0Harmony.dll").read_bytes() == b"bepinex harmony"
    assert not (lib_dir / "lunaris").exists()
    assert not (tmp_path / _mod("sprint").directory / "lib").exists()


def test_lunaris_shared_lib_sourced_only_from_resolved_lib_dir(tmp_path: Path) -> None:
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "ImGui.NET.dll").write_bytes(b"stub")
    assert local_workflow.find_lunaris_shared_lib("ImGui.NET.dll", lib_dir) == lib_dir / "ImGui.NET.dll"
    assert local_workflow.find_lunaris_shared_lib("Newtonsoft.Json.dll", None) is None


def test_configured_lunaris_lib_dir_prefers_env_over_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_dir = tmp_path / "env"
    config_dir = tmp_path / "config"
    monkeypatch.setenv("ERENSHOR_LUNARIS_LIB_DIR", str(env_dir))
    assert local_workflow.configured_lunaris_lib_dir(config_dir) == env_dir
    monkeypatch.delenv("ERENSHOR_LUNARIS_LIB_DIR")
    assert local_workflow.configured_lunaris_lib_dir(config_dir) == config_dir
    assert local_workflow.configured_lunaris_lib_dir(None) is None


def test_ensure_lunaris_libs_cached_extracts_and_reuses_dlls(tmp_path: Path) -> None:
    archive = tmp_path / "LunarisLibs.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ImGui.NET.dll", b"imgui")
        zf.writestr("README.txt", b"ignored")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cache_dir = local_workflow.ensure_lunaris_libs_cached(repo_root, archive.as_uri())
    assert (cache_dir / "ImGui.NET.dll").read_bytes() == b"imgui"
    assert not (cache_dir / "README.txt").exists()
    (cache_dir / "ImGui.NET.dll").write_bytes(b"cached")
    assert local_workflow.ensure_lunaris_libs_cached(repo_root, "https://invalid.invalid/missing.zip") == cache_dir
    assert (cache_dir / "ImGui.NET.dll").read_bytes() == b"cached"


def test_launch_uses_crossover_steam_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game = tmp_path / "game"
    game.mkdir()
    crossover_start = tmp_path / "cxstart"
    crossover_start.touch()
    ctx = _ctx(tmp_path, game_installs={"main": game})
    calls: list[tuple[list[str], bool]] = []

    monkeypatch.delenv("CROSSOVER_BOTTLE", raising=False)
    monkeypatch.setattr(local_workflow.sys, "platform", "darwin")
    monkeypatch.setattr(local_workflow, "CROSSOVER_START", crossover_start)
    monkeypatch.setattr(local_workflow, "crossover_bottle_for_path", lambda _path: "Steam")
    monkeypatch.setattr(
        local_workflow,
        "launch_game",
        lambda cli_ctx: calls.append((list(local_workflow.plan_launch(cli_ctx).command), False))
        or local_workflow.plan_launch(cli_ctx),
    )

    mod_command.launch(ctx)

    assert calls == [
        (
            [
                str(crossover_start),
                "--bottle",
                "Steam",
                "--wait-children",
                "steam://rungameid/2382520",
            ],
            False,
        )
    ]


def test_launch_recovery_does_not_start_another_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    recovered: list[object] = []
    monkeypatch.setattr(
        local_workflow,
        "recover_game_session",
        lambda cli_ctx: recovered.append(cli_ctx) or True,
    )
    monkeypatch.setattr(
        local_workflow,
        "launch_game",
        lambda _cli_ctx: pytest.fail("recovery must not launch a game"),
    )

    mod_command.launch(ctx, recover=True)

    assert recovered == [ctx.obj]


def test_launch_inspects_unowned_pid_without_signaling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _ctx(tmp_path)
    identity = ProcessIdentity(41, 42, "Mon Aug 24 21:00:00 2026", "/usr/bin/example")
    monkeypatch.setattr(mod_command, "read_process_identity", lambda _pid: identity)
    monkeypatch.setattr(
        local_workflow,
        "launch_game",
        lambda _cli_ctx: pytest.fail("inspection must not launch a game"),
    )

    mod_command.launch(ctx, inspect_pid=41)

    output = capsys.readouterr().out
    assert "PID: 41" in output
    assert "Process group: 42" in output
    assert "No signal was sent" in output


def test_launch_applies_native_proxy_override_for_active_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "game"
    game.mkdir()
    executable = game / "Erenshor.exe"
    executable.write_bytes(b"game")
    (game / "winhttp.dll").write_bytes(b"bepinex proxy")
    (game / "winhttp.bepinex.dll").write_bytes(b"bepinex proxy")
    crossover_start = tmp_path / "cxstart"
    crossover_start.touch()
    ctx = _ctx(tmp_path, game_installs={"main": game})

    monkeypatch.delenv("CROSSOVER_BOTTLE", raising=False)
    monkeypatch.setattr(local_workflow.sys, "platform", "darwin")
    monkeypatch.setattr(local_workflow, "CROSSOVER_START", crossover_start)
    monkeypatch.setattr(local_workflow, "crossover_bottle_for_path", lambda _path: "Steam")

    plan = local_workflow.plan_launch(ctx.obj)

    assert plan.command == (
        str(crossover_start),
        "--bottle",
        "Steam",
        "--dll",
        "winhttp=n,b",
        "--wait-children",
        "--workdir",
        str(game),
        str(executable),
    )


def test_next_calver_revision_handles_day_boundary_and_revision() -> None:
    assert release.next_calver_revision("2026.716", None) == "2026.716.0"
    assert release.next_calver_revision("2026.716", "2026.715.3") == "2026.716.0"
    assert release.next_calver_revision("2026.716", "2026.716.4") == "2026.716.5"
    assert release.latest_calver_for_prefix(["2026.716.0", "2026.716.2", "2026.716.1"], "2026.716") == "2026.716.2"
