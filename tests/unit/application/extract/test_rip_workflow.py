from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erenshor.application.extract import RipRequest, RipWorkflow


class FakeAssetRipper:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[Path, Path, Path]] = []

    def extract(self, source_dir: Path, target_dir: Path, log_dir: Path, profile: object = None) -> None:
        self.calls.append((source_dir, target_dir, log_dir))
        if self.fail is not None:
            raise self.fail
        exported = target_dir / "ExportedProject"
        (exported / "Assets" / "Editor").mkdir(parents=True)
        (exported / "Packages").mkdir(parents=True)
        (exported / "Packages" / "manifest.json").write_text(
            json.dumps({"dependencies": {"com.unity.modules.audio": "1.0"}})
        )


def _request(tmp_path: Path, *, profile: object = None) -> RipRequest:
    game = tmp_path / "game" / "Erenshor_Data"
    game.mkdir(parents=True)
    editor = tmp_path / "editor"
    editor.mkdir()
    packages = tmp_path / "packages"
    packages.mkdir()
    (packages / "Newtonsoft.Json.dll").write_bytes(b"dll")
    return RipRequest(
        source_dir=game,
        unity_project_dir=tmp_path / "unity",
        logs_dir=tmp_path / "logs",
        editor_source=editor,
        packages_source=packages,
        profile=profile,  # type: ignore[arg-type]
    )


def test_rip_workflow_replaces_project_and_prepares_outputs(tmp_path: Path) -> None:
    request = _request(tmp_path)
    old_manifest = request.unity_project_dir / "ExportedProject" / "Packages" / "manifest.json"
    old_manifest.parent.mkdir(parents=True)
    old_manifest.write_text(json.dumps({"dependencies": {"com.unity.modules.audio": "1.0", "com.example.tool": "2.0"}}))
    (request.unity_project_dir / "old-marker").write_text("remove me")

    ripper = FakeAssetRipper()
    result = RipWorkflow(ripper).run(request)

    assert ripper.calls == [(request.source_dir, request.unity_project_dir, request.logs_dir)]
    assert not (request.unity_project_dir / "old-marker").exists()
    assert (request.unity_project_dir / "ExportedProject" / "Assets" / "Editor").is_symlink()
    assert (
        request.unity_project_dir / "ExportedProject" / "Assets" / "Editor"
    ).resolve() == request.editor_source.resolve()
    assert (
        request.unity_project_dir / "ExportedProject" / "Assets" / "Packages" / "Newtonsoft.Json.dll"
    ).read_bytes() == b"dll"

    manifest = json.loads(old_manifest.read_text())
    assert manifest["dependencies"]["com.example.tool"] == "2.0"
    assert manifest["dependencies"]["com.unity.nuget.newtonsoft-json"] == "3.2.1"
    assert result.restored_upm_dependencies == ("com.example.tool",)
    assert result.added_upm_dependencies == ("com.unity.nuget.newtonsoft-json",)
    assert not list(request.unity_project_dir.rglob("*.tmp"))


def test_rip_workflow_propagates_assetripper_failure_after_cleanup(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.unity_project_dir.mkdir()
    (request.unity_project_dir / "old-marker").write_text("remove me")
    failure = RuntimeError("AssetRipper failed")
    ripper = FakeAssetRipper(fail=failure)

    with pytest.raises(RuntimeError, match="AssetRipper failed"):
        RipWorkflow(ripper).run(request)

    assert not request.unity_project_dir.exists()
    assert ripper.calls == [(request.source_dir, request.unity_project_dir, request.logs_dir)]


def test_rip_workflow_rejects_missing_editor_source(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request = RipRequest(
        source_dir=request.source_dir,
        unity_project_dir=request.unity_project_dir,
        logs_dir=request.logs_dir,
        editor_source=tmp_path / "missing-editor",
        packages_source=request.packages_source,
    )

    with pytest.raises(FileNotFoundError, match="Editor scripts directory"):
        RipWorkflow(MagicMock()).run(request)


def test_rip_workflow_rejects_missing_packages_source(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request = RipRequest(
        source_dir=request.source_dir,
        unity_project_dir=request.unity_project_dir,
        logs_dir=request.logs_dir,
        editor_source=request.editor_source,
        packages_source=tmp_path / "missing-packages",
    )

    # Continuing would produce a project whose export scripts cannot compile.
    with pytest.raises(FileNotFoundError, match="Editor NuGet packages not found"):
        RipWorkflow(FakeAssetRipper()).run(request)
