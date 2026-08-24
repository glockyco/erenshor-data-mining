from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from erenshor.application.mods import local_workflow
from erenshor.application.mods.artifacts import REQUIRED_DLLS


def _ctx(tmp_path: Path) -> SimpleNamespace:
    game = tmp_path / "game"
    variant = SimpleNamespace(
        app_id="2382520",
        resolved_game_install=lambda _root: game,
        resolved_game_files=lambda _root: game,
    )
    config = SimpleNamespace(
        variants={"main": variant},
        global_=SimpleNamespace(mods=SimpleNamespace(lunaris_lib_dir=str(tmp_path), lunaris_libs_url="unused")),
    )
    return SimpleNamespace(config=config, variant="main", repo_root=tmp_path)


def test_target_selection_is_ordered_and_loader_specific() -> None:
    assert local_workflow.resolve_build_targets(None, "default") == [
        ("interactive-map-companion", "bepinex"),
        ("justice-for-f7", "lunaris"),
        ("sprint", "lunaris"),
        ("map-tile-capture", "bepinex"),
        ("adventure-guide", "lunaris"),
    ]
    assert local_workflow.resolve_build_targets("sprint", "all") == [
        ("sprint", "bepinex"),
        ("sprint", "lunaris"),
    ]
    with pytest.raises(ValueError, match="Unsupported loader target"):
        local_workflow.resolve_deploy_targets("sprint", "all")


def test_build_injects_runner_and_preserves_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    mod_dir = tmp_path / "src/mods/Sprint"
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / REQUIRED_DLLS[0]).write_bytes(b"reference")
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(local_workflow, "verify_built_mod_artifacts", lambda *_args: ())

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    result = local_workflow.build_mods(
        ctx,
        "sprint",
        version="1.2.3",
        loader="lunaris",
        skip_ilrepack=True,
        runner=runner,
    )

    assert result.failed == ()
    assert calls == [
        (
            [
                "dotnet",
                "build",
                "--configuration",
                "Debug",
                "-p:ModLoader=lunaris",
                "-p:ModVersion=1.2.3",
                "-p:SkipILRepack=true",
            ],
            {"cwd": mod_dir, "check": False},
        )
    ]


def test_build_failure_skips_artifact_verification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    mod_dir = tmp_path / "src/mods/Sprint"
    (mod_dir / "lib").mkdir(parents=True)
    (mod_dir / "lib" / REQUIRED_DLLS[0]).write_bytes(b"reference")
    verified = []
    monkeypatch.setattr(local_workflow, "check_dotnet_available", lambda: True)
    monkeypatch.setattr(local_workflow, "verify_built_mod_artifacts", lambda *_args: verified.append(True) or ())

    result = local_workflow.build_mods(
        ctx,
        "sprint",
        loader="lunaris",
        runner=lambda args, **kwargs: subprocess.CompletedProcess(args, 7),
    )

    assert result.failed == ("sprint (lunaris)",)
    assert verified == []


def test_deploy_preflight_precedes_build_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _ctx(tmp_path)
    game_path = tmp_path / "game"
    game_path.mkdir()
    monkeypatch.setattr(local_workflow, "validate_loader_activation", lambda *_args: ({}, None))

    selection = local_workflow.plan_deploy("sprint", "lunaris", game_path, scripts=False)

    assert selection.targets == (("sprint", "lunaris"),)
    with pytest.raises(ValueError, match="mod deploy input is not a regular file"):
        local_workflow.prepare_deploy(ctx, selection)

    output = tmp_path / "src/mods/Sprint/bin/Debug/netstandard2.1/lunaris/Sprint.dll"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"plugin")

    plan = local_workflow.prepare_deploy(ctx, selection)
    assert plan.files_for("sprint") == (local_workflow.DeployFile(output, game_path / "plugins/Sprint.dll"),)


def test_launch_plan_and_runner_are_injected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    game = tmp_path / "game"
    game.mkdir(parents=True)
    executable = game / "Erenshor.exe"
    executable.touch()
    monkeypatch.setattr(local_workflow.sys, "platform", "linux")
    calls: list[tuple[Path, list[str], Path | None]] = []

    class FakeSession:
        def __init__(self, record_path: Path) -> None:
            self.record_path = record_path

        def run(self, command: list[str], *, cwd: Path | None = None) -> int:
            calls.append((self.record_path, command, cwd))
            return 0

    plan = local_workflow.launch_game(ctx, session_factory=FakeSession)

    assert plan.command == (str(executable),)
    assert calls == [(tmp_path / ".agent/state/game-session.json", [str(executable)], game)]
