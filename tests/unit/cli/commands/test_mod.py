"""Behavioral tests for loader-targeted mod CLI infrastructure."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from erenshor.cli.commands import mod as mod_command
from erenshor.cli.commands.mod import MODS, REQUIRED_DLLS


def _ctx(
    tmp_path: Path,
    *,
    variant: str = "main",
    game_paths: dict[str, Path] | None = None,
    mods_config: Any | None = None,
) -> SimpleNamespace:
    """Build the smallest CLI context needed by mod command helpers."""
    paths = game_paths or {variant: tmp_path / variant}
    variants = {
        name: SimpleNamespace(resolved_game_files=lambda _root, path=path: path) for name, path in paths.items()
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


def test_registry_inventory_declares_all_loader_targets_and_public_surface() -> None:
    assert set(MODS) == {
        "adventure-guide",
        "interactive-map-companion",
        "interactive-maps-companion",
        "justice-for-f7",
        "map-tile-capture",
        "sprint",
    }
    assert {mod_id for mod_id, info in MODS.items() if info["public"]} == {
        "adventure-guide",
        "interactive-map-companion",
        "justice-for-f7",
        "sprint",
    }
    assert all(info["loaders"] == ["bepinex", "lunaris"] for info in MODS.values())
    assert {mod_id: info["default_loader"] for mod_id, info in MODS.items()} == {
        "adventure-guide": "lunaris",
        "interactive-map-companion": "bepinex",
        "interactive-maps-companion": "bepinex",
        "justice-for-f7": "lunaris",
        "map-tile-capture": "bepinex",
        "sprint": "lunaris",
    }


def test_build_target_resolution_is_deterministic_for_default_and_all() -> None:
    assert mod_command._resolve_build_targets(None, "default") == [
        ("interactive-map-companion", "bepinex"),
        ("interactive-maps-companion", "bepinex"),
        ("justice-for-f7", "lunaris"),
        ("sprint", "lunaris"),
        ("map-tile-capture", "bepinex"),
        ("adventure-guide", "lunaris"),
    ]
    targets = mod_command._resolve_build_targets("sprint", "all")
    assert targets == [("sprint", "bepinex"), ("sprint", "lunaris")]
    assert mod_command._resolve_deploy_targets("adventure-guide", "default") == [("adventure-guide", "lunaris")]


def test_target_resolution_rejects_invalid_and_unsupported_loader() -> None:
    with pytest.raises(ValueError, match="Unsupported loader target"):
        mod_command._resolve_build_targets("sprint", "invalid")
    with pytest.raises(ValueError, match="all"):
        mod_command._resolve_deploy_targets("sprint", "all")

    original = MODS["sprint"]["loaders"]
    MODS["sprint"]["loaders"] = ["lunaris"]
    try:
        with pytest.raises(ValueError, match="does not support"):
            mod_command._resolve_build_targets("sprint", "bepinex")
        assert mod_command._resolve_build_targets("sprint", "all") == [("sprint", "lunaris")]
    finally:
        MODS["sprint"]["loaders"] = original


def test_build_rejects_unsupported_target_before_dotnet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    original = MODS["sprint"]["loaders"]
    MODS["sprint"]["loaders"] = ["lunaris"]
    monkeypatch.setattr(
        mod_command,
        "_check_dotnet_available",
        lambda: pytest.fail("dotnet availability must not be checked"),
    )
    try:
        with pytest.raises(typer.Exit):
            mod_command._build_mods_internal(ctx, "sprint", loader="bepinex")
    finally:
        MODS["sprint"]["loaders"] = original


def test_output_paths_are_isolated_by_loader(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path).obj
    bepinex = mod_command._get_mod_output_dir(ctx, "sprint", "bepinex")
    lunaris = mod_command._get_mod_output_dir(ctx, "sprint", "lunaris")
    assert bepinex == tmp_path / "src/mods/Sprint/bin/Debug/netstandard2.1/bepinex"
    assert lunaris == tmp_path / "src/mods/Sprint/bin/Debug/netstandard2.1/lunaris"
    assert bepinex != lunaris


def test_dotnet_build_receives_loader_property(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / MODS["sprint"]["dir"]
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / "Assembly-CSharp.dll").write_bytes(b"reference")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(mod_command, "_check_dotnet_available", lambda: True)
    monkeypatch.setattr(mod_command.subprocess, "run", fake_run)
    mod_command._build_mods_internal(ctx, "sprint", loader="lunaris")

    assert calls[0][0] == [
        "dotnet",
        "build",
        "--configuration",
        "Debug",
        "-p:ModLoader=lunaris",
    ]


def test_deploy_target_routing_and_scripts_guard(tmp_path: Path) -> None:
    assert mod_command._get_deploy_target_dir("bepinex", tmp_path, scripts=False) == (
        tmp_path / "BepInEx/plugins",
        "BepInEx/plugins",
        False,
    )
    assert mod_command._get_deploy_target_dir("bepinex", tmp_path, scripts=True) == (
        tmp_path / "BepInEx/scripts",
        "BepInEx/scripts (hot reload)",
        True,
    )
    assert mod_command._get_deploy_target_dir("lunaris", tmp_path, scripts=False) == (
        tmp_path / "plugins",
        "Lunaris plugins",
        False,
    )
    with pytest.raises(ValueError, match="BepInEx"):
        mod_command._get_deploy_target_dir("lunaris", tmp_path, scripts=True)


@pytest.mark.parametrize("variant", ["main", "playtest", "demo"])
def test_game_path_uses_selected_variant(variant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ERENSHOR_GAME_PATH", raising=False)
    game = tmp_path / variant
    (game / "Erenshor_Data" / "Managed").mkdir(parents=True)
    ctx = _ctx(tmp_path, variant=variant, game_paths={variant: game}).obj
    assert mod_command._get_game_path(ctx) == game


def test_game_path_environment_override_has_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configured = tmp_path / "playtest"
    (configured / "Erenshor_Data" / "Managed").mkdir(parents=True)
    environment = tmp_path / "environment"
    environment.mkdir()
    ctx = _ctx(tmp_path, variant="playtest", game_paths={"playtest": configured}).obj
    monkeypatch.setenv("ERENSHOR_GAME_PATH", str(environment))
    assert mod_command._get_game_path(ctx) == environment


def test_deploy_routes_explicit_loader_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    game = tmp_path / "game"
    output = mod_command._get_mod_output_dir(ctx, "sprint", "bepinex")
    output.mkdir(parents=True)
    (output / "Sprint.dll").write_bytes(b"bepinex")
    calls: list[str] = []
    monkeypatch.setattr(mod_command, "_get_game_path", lambda _ctx: game)
    monkeypatch.setattr(
        mod_command,
        "_build_mods_internal",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"]),
    )

    mod_command.deploy(ctx=SimpleNamespace(obj=ctx), mod="sprint", loader="bepinex", scripts=False)

    assert calls == ["bepinex"]
    assert (game / "BepInEx" / "plugins" / "Sprint.dll").read_bytes() == b"bepinex"


def test_deploy_rejects_scripts_for_default_lunaris_before_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        mod_command,
        "_build_mods_internal",
        lambda *_args, **_kwargs: pytest.fail("invalid deploy must not build"),
    )
    with pytest.raises(typer.Exit):
        mod_command.deploy(ctx, mod="sprint", loader="default", scripts=True)


def test_website_publish_uses_each_mod_default_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    output = mod_command._get_mod_output_dir(ctx, "sprint", "lunaris")
    output.mkdir(parents=True)
    (output / "Sprint.dll").write_bytes(b"default")
    metadata = tmp_path / "src/maps/static/mods-metadata.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("{}\n")
    calls: list[str] = []
    monkeypatch.setattr(
        mod_command,
        "_build_mods_internal",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"]),
    )

    mod_command.publish(SimpleNamespace(obj=ctx), mod="sprint")

    assert calls == ["default"]
    assert (tmp_path / "src/maps/static/mods/Sprint.dll").read_bytes() == b"default"


def test_thunderstore_build_is_explicitly_bepinex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / MODS["interactive-map-companion"]["dir"]
    mod_dir.mkdir(parents=True)
    (mod_dir / "thunderstore.toml").write_text("[package]\n")
    (mod_dir / "thunderstore").mkdir()
    (mod_dir / "thunderstore" / "icon.png").write_bytes(b"icon")
    calls: list[str] = []
    monkeypatch.setattr(mod_command, "_check_tcli_available", lambda: True)
    monkeypatch.setattr(mod_command, "_get_thunderstore_version", lambda *_args: "2026.716.0")
    monkeypatch.setattr(
        mod_command,
        "_build_mods_internal",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"]),
    )
    monkeypatch.setattr(
        mod_command.subprocess,
        "run",
        lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
    )

    mod_command.thunderstore(SimpleNamespace(obj=ctx), mod="interactive-map-companion", dry_run=True)

    assert calls == ["bepinex"]


def test_vault_build_is_explicitly_lunaris(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path).obj
    mod_dir = tmp_path / MODS["sprint"]["dir"]
    vault_dir = mod_dir / "vault"
    vault_dir.mkdir(parents=True)
    (vault_dir / "vault.toml").write_text('[mod]\nmod_ref = "sprint"\n')
    (vault_dir / "CHANGELOG.md").write_text("## v2026.716.0\n")
    calls: list[str] = []
    monkeypatch.setattr(mod_command, "_get_vault_version", lambda _ref: "2026.716.0")
    monkeypatch.setattr(
        mod_command,
        "_build_mods_internal",
        lambda _ctx, mod=None, **kwargs: calls.append(kwargs["loader"]),
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

    for _mod_id, mod_info in MODS.items():
        lib_dir = tmp_path / mod_info["dir"] / "lib"
        assert all((lib_dir / dll_name).exists() for dll_name in REQUIRED_DLLS)
        assert (lib_dir / "lunaris" / "Lunaris.dll").read_bytes() == b"lunaris"
    assert (
        tmp_path / MODS["interactive-map-companion"]["dir"] / "lib/bepinex/0Harmony.dll"
    ).read_bytes() == b"bepinex harmony"
    assert (
        tmp_path / MODS["interactive-map-companion"]["dir"] / "lib/lunaris/0Harmony.dll"
    ).read_bytes() == b"lunaris harmony"
    assert (tmp_path / MODS["sprint"]["dir"] / "lib/lunaris/0Harmony.dll").read_bytes() == b"lunaris harmony"
    assert (tmp_path / MODS["adventure-guide"]["dir"] / "lib/lunaris/ImGui.NET.dll").read_bytes() == b"ImGui.NET.dll"


def test_lunaris_shared_lib_sourced_only_from_resolved_lib_dir(tmp_path: Path) -> None:
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "ImGui.NET.dll").write_bytes(b"stub")
    assert mod_command._find_lunaris_shared_lib("ImGui.NET.dll", lib_dir) == lib_dir / "ImGui.NET.dll"
    assert mod_command._find_lunaris_shared_lib("Newtonsoft.Json.dll", None) is None


def test_configured_lunaris_lib_dir_prefers_env_over_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_dir = tmp_path / "env"
    config_dir = tmp_path / "config"
    monkeypatch.setenv("ERENSHOR_LUNARIS_LIB_DIR", str(env_dir))
    assert mod_command._configured_lunaris_lib_dir(config_dir) == env_dir
    monkeypatch.delenv("ERENSHOR_LUNARIS_LIB_DIR")
    assert mod_command._configured_lunaris_lib_dir(config_dir) == config_dir
    assert mod_command._configured_lunaris_lib_dir(None) is None


def test_ensure_lunaris_libs_cached_extracts_and_reuses_dlls(tmp_path: Path) -> None:
    archive = tmp_path / "LunarisLibs.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ImGui.NET.dll", b"imgui")
        zf.writestr("README.txt", b"ignored")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cache_dir = mod_command._ensure_lunaris_libs_cached(repo_root, archive.as_uri())
    assert (cache_dir / "ImGui.NET.dll").read_bytes() == b"imgui"
    assert not (cache_dir / "README.txt").exists()
    (cache_dir / "ImGui.NET.dll").write_bytes(b"cached")
    assert mod_command._ensure_lunaris_libs_cached(repo_root, "https://invalid.invalid/missing.zip") == cache_dir
    assert (cache_dir / "ImGui.NET.dll").read_bytes() == b"cached"


def test_next_calver_revision_handles_day_boundary_and_revision() -> None:
    assert mod_command._next_calver_revision("2026.716", None) == "2026.716.0"
    assert mod_command._next_calver_revision("2026.716", "2026.715.3") == "2026.716.0"
    assert mod_command._next_calver_revision("2026.716", "2026.716.4") == "2026.716.5"
    assert mod_command._latest_calver_for_prefix(["2026.716.0", "2026.716.2", "2026.716.1"], "2026.716") == "2026.716.2"
