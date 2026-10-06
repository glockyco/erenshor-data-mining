"""Preflight failures retain their cause and stop state-changing commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import typer

from erenshor.cli.commands import eval as eval_command
from erenshor.cli.commands import images
from erenshor.cli.commands import mod as mod_command
from erenshor.cli.preconditions.checks.capture import capture_config, captured_masters
from erenshor.cli.preconditions.checks.eval import eval_source
from erenshor.cli.preconditions.checks.inputs import (
    game_installation,
    program_available,
    required_path,
    wiki_credentials,
)
from erenshor.cli.preconditions.checks.mod import (
    dev_tools_configured,
    launch_installation,
    mod_references,
    mod_setup_source,
)


def test_required_path_names_missing_input_and_accepts_directory(tmp_path: Path) -> None:
    check = required_path("images_dir", "current", kind="directory")
    context = {"images_dir": tmp_path}
    assert str(tmp_path / "current") in str(check(context))
    assert not check(context).passed
    (tmp_path / "current").mkdir()
    assert check(context).passed


def test_program_check_names_absent_program_and_passes_when_resolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    check = program_available("pnpm")
    assert not check({}).passed
    assert "pnpm" in str(check({}))
    monkeypatch.setattr("shutil.which", lambda _name: "/nix/bin/pnpm")
    assert check({}).passed


def test_wiki_credentials_require_both_values_unless_preview() -> None:
    credentials = SimpleNamespace(bot_username="bot", bot_password="")
    context = {"config": SimpleNamespace(global_=SimpleNamespace(mediawiki=credentials)), "dry_run": False}
    assert not wiki_credentials(context).passed
    assert "credentials" in str(wiki_credentials(context))
    credentials.bot_password = "secret"
    assert wiki_credentials(context).passed
    credentials.bot_password = ""
    context["dry_run"] = True
    assert wiki_credentials(context).passed


def test_game_installation_preserves_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from erenshor.infrastructure.steam.installation import GameInstallationError

    def fail(_ctx: object) -> None:
        raise GameInstallationError("ambiguous bottles: A and B")

    monkeypatch.setattr("erenshor.application.mods.local_workflow.get_game_path", fail)
    context = {"cli_ctx": object(), "variant": "main"}
    result = game_installation(context)
    assert not result.passed and "ambiguous bottles: A and B" in str(result)
    monkeypatch.setattr("erenshor.application.mods.local_workflow.get_game_path", lambda _ctx: Path("/game"))
    assert game_installation(context).passed


def test_capture_config_names_missing_file_and_accepts_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "src/lib/data/zone-capture-config.json"
    context = {"maps_source_dir": tmp_path, "zones": None}
    assert not capture_config(context).passed
    assert str(path) in str(capture_config(context))
    path.parent.mkdir(parents=True)
    path.write_text('{"One": {"captureVariants": ["clear"]}}')
    assert capture_config(context).passed


def test_capture_masters_require_all_selected_masters(tmp_path: Path) -> None:
    path = tmp_path / "maps/src/lib/data/zone-capture-config.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"One": {"captureVariants": ["clear"]}}')
    context = {"repo_root": tmp_path, "maps_source_dir": tmp_path / "maps", "zones": None}
    result = captured_masters(context)
    assert not result.passed and "One/clear" in str(result)
    master = tmp_path / "One.png"
    master.write_bytes(b"image")
    state_path = tmp_path / ".erenshor/capture-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"zones": {"One": {"clear": {"masterPath": "One.png"}}}}')
    assert captured_masters(context).passed


def test_images_process_rejects_missing_textures_before_legacy_migration(
    cli_context: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    variant = cli_context.config.variants[cli_context.variant]
    unity = variant.resolved_unity_project(cli_context.repo_root)
    legacy = unity.parent / "images/processed"
    legacy.mkdir(parents=True)
    monkeypatch.setattr(images, "ImageRegistry", Mock(side_effect=AssertionError("work started")))
    with pytest.raises(typer.Exit) as error:
        images.process(SimpleNamespace(obj=cli_context), force=False)
    assert error.value.exit_code == 1
    assert "Texture2D" in capsys.readouterr().out
    assert legacy.is_dir()
    assert not (legacy.parent / "current").exists()


def test_mod_setup_source_names_missing_managed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game = tmp_path / "game"
    monkeypatch.setattr("erenshor.application.mods.local_workflow.get_game_path", lambda *_args, **_kwargs: game)
    context = {"cli_ctx": object(), "variant": "main", "mod": "sprint", "loader": "lunaris"}
    assert not mod_setup_source(context).passed
    assert str(game / "Erenshor_Data/Managed") in str(mod_setup_source(context))
    (game / "Erenshor_Data/Managed").mkdir(parents=True)
    from erenshor.application.mods.artifacts import REQUIRED_DLLS

    for name in REQUIRED_DLLS:
        (game / "Erenshor_Data/Managed" / name).write_bytes(b"reference")
    assert mod_setup_source(context).passed


def test_mod_references_require_selected_build_inputs(tmp_path: Path) -> None:
    context = {"cli_ctx": SimpleNamespace(repo_root=tmp_path), "mod": "sprint", "loader": "bepinex"}
    assert not mod_references(context).passed
    assert str(tmp_path / "src/mods/Sprint") in str(mod_references(context))
    mod_dir = tmp_path / "src/mods/Sprint/lib"
    mod_dir.mkdir(parents=True)
    (mod_dir / "Assembly-CSharp.dll").write_bytes(b"reference")
    assert mod_references(context).passed


def test_dev_tools_preflight_refuses_missing_config_before_creating_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "game"
    (game / "BepInEx").mkdir(parents=True)
    monkeypatch.setattr("erenshor.application.mods.local_workflow.get_game_path", lambda _ctx: game)
    config = SimpleNamespace(global_=SimpleNamespace(bepinex_dev_tools=None))
    context = {"cli_ctx": object(), "variant": "main", "config": config}
    assert not dev_tools_configured(context).passed
    assert "bepinex_dev_tools" in str(dev_tools_configured(context))
    config.global_.bepinex_dev_tools = object()
    assert dev_tools_configured(context).passed


def test_launch_inspection_skips_installation_only_when_not_launching(monkeypatch: pytest.MonkeyPatch) -> None:
    from erenshor.infrastructure.steam.installation import GameInstallationError

    def absent(_ctx: object) -> Path:
        raise GameInstallationError("Variant 'demo' (Steam app 2522260) is not installed")

    monkeypatch.setattr("erenshor.application.mods.local_workflow.get_game_path", absent)
    context = {"cli_ctx": object(), "variant": "demo", "recover": False, "inspect_pid": None}
    assert not launch_installation(context).passed
    assert "demo" in str(launch_installation(context))
    context["recover"] = True
    assert launch_installation(context).passed


def test_mod_build_stops_before_compiler_when_references_missing(
    cli_context: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(mod_command.local_workflow, "build_mods", Mock(side_effect=AssertionError("build started")))
    with pytest.raises(typer.Exit) as error:
        mod_command.build(SimpleNamespace(obj=cli_context), mod="unknown", loader="bepinex")
    assert error.value.exit_code == 1
    assert "unknown" in capsys.readouterr().out


def test_eval_source_requires_one_input_and_reports_missing_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.cs"
    context = {"code": None, "file": None}
    assert not eval_source(context).passed
    context["file"] = source
    assert not eval_source(context).passed
    assert str(source) in str(eval_source(context))
    source.write_text("1 + 1")
    assert eval_source(context).passed
    context["code"] = "2 + 2"
    assert not eval_source(context).passed


def test_eval_run_missing_file_stops_before_game_request(
    tmp_path: Path, cli_context: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(eval_command, "_run", Mock(side_effect=AssertionError("connected to game")))
    source = tmp_path / "missing.cs"
    with pytest.raises(typer.Exit) as error:
        eval_command.run(SimpleNamespace(obj=cli_context), code=None, file=source, json_output=False, timeout=100)
    assert error.value.exit_code == 1
    assert source.name in capsys.readouterr().out
