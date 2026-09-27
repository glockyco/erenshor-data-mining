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

    assert ripper.calls == [(request.source_dir, _staging_dir(request), request.logs_dir)]
    assert not _staging_dir(request).exists()
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


def _old_project(request: RipRequest, dependencies: object) -> Path:
    manifest = request.unity_project_dir / "ExportedProject" / "Packages" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"dependencies": dependencies}))
    (request.unity_project_dir / "old-marker").write_text("keep me until the rip succeeds")
    return manifest


def _staging_dir(request: RipRequest) -> Path:
    return request.unity_project_dir.with_name(f".{request.unity_project_dir.name}.rip")


def test_failed_rip_keeps_the_old_project_and_its_user_dependencies(tmp_path: Path) -> None:
    request = _request(tmp_path)
    old_manifest = _old_project(request, {"com.example.tool": "2.0"})
    ripper = FakeAssetRipper(fail=RuntimeError("AssetRipper failed"))

    with pytest.raises(RuntimeError, match="AssetRipper failed"):
        RipWorkflow(ripper).run(request)

    assert (request.unity_project_dir / "old-marker").exists()
    assert json.loads(old_manifest.read_text()) == {"dependencies": {"com.example.tool": "2.0"}}
    assert not _staging_dir(request).exists()
    assert ripper.calls == [(request.source_dir, _staging_dir(request), request.logs_dir)]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "Unity package manifest is unreadable"),
        ('{"dependencies": ["com.example.tool"]}', "no dependencies object"),
        (None, "Unity package manifest not found"),
    ],
)
def test_unreadable_old_manifest_stops_the_rip_before_anything_changes(
    tmp_path: Path, content: str | None, message: str
) -> None:
    request = _request(tmp_path)
    manifest = request.unity_project_dir / "ExportedProject" / "Packages" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    if content is not None:
        manifest.write_text(content)
    ripper = FakeAssetRipper()

    with pytest.raises((FileNotFoundError, ValueError), match=message) as error:
        RipWorkflow(ripper).run(request)

    assert str(manifest) in str(error.value)
    assert ripper.calls == []
    assert manifest.parent.is_dir()
    if content is not None:
        assert manifest.read_text() == content


def test_rip_without_a_manifest_fails_and_keeps_the_old_project(tmp_path: Path) -> None:
    request = _request(tmp_path)
    _old_project(request, {})

    class RipperWithoutManifest(FakeAssetRipper):
        def extract(self, source_dir: Path, target_dir: Path, log_dir: Path, profile: object = None) -> None:
            super().extract(source_dir, target_dir, log_dir, profile)
            (target_dir / "ExportedProject" / "Packages" / "manifest.json").unlink()

    with pytest.raises(FileNotFoundError, match="Unity package manifest not found"):
        RipWorkflow(RipperWithoutManifest()).run(request)

    assert (request.unity_project_dir / "old-marker").exists()
    assert not _staging_dir(request).exists()


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
