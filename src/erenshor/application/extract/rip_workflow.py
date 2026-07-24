"""Application workflow for acquiring and preparing a ripped Unity project.

The CLI resolves configuration and presents the operation.  This module owns the
filesystem transaction around the AssetRipper adapter so it can be exercised
without Typer, Rich, or a configured checkout.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from loguru import logger

if TYPE_CHECKING:
    from erenshor.infrastructure.export_profile import ExportProfileRecorder

REQUIRED_UPM_PACKAGES: dict[str, str] = {
    "com.unity.nuget.newtonsoft-json": "3.2.1",
}


class AssetRipperAdapter(Protocol):
    """The AssetRipper surface required by :class:`RipWorkflow`."""

    def extract(
        self,
        source_dir: Path,
        target_dir: Path,
        log_dir: Path,
        profile: ExportProfileRecorder | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class RipRequest:
    """Resolved paths and options for one fresh Unity-project rip."""

    source_dir: Path
    unity_project_dir: Path
    logs_dir: Path
    editor_source: Path
    packages_source: Path
    profile: ExportProfileRecorder | None = None


@dataclass(frozen=True, slots=True)
class RipResult:
    """Observable results of preparing a ripped Unity project."""

    unity_project_dir: Path
    restored_upm_dependencies: tuple[str, ...] = ()
    added_upm_dependencies: tuple[str, ...] = ()


class RipWorkflow:
    """Acquire and prepare a fresh AssetRipper Unity project."""

    def __init__(self, assetripper: AssetRipperAdapter) -> None:
        self._assetripper = assetripper

    def run(self, request: RipRequest) -> RipResult:
        """Perform the rip and all deterministic post-processing.

        Existing user UPM dependencies are captured before the old project is
        removed.  AssetRipper then writes a new project, after which the Editor
        scripts link, package copies, and manifest dependencies are restored.
        Exceptions are intentionally allowed to propagate to the CLI boundary.
        """
        prior_user_deps = self._snapshot_user_deps(request.unity_project_dir)
        if prior_user_deps:
            logger.info(f"Snapshotted {len(prior_user_deps)} user-added UPM deps to restore after rip")

        if request.unity_project_dir.exists() or request.unity_project_dir.is_symlink():
            logger.info(f"Removing old Unity project: {request.unity_project_dir}")
            self._remove_path(request.unity_project_dir)

        logger.info(f"Extracting Unity project: source={request.source_dir}, target={request.unity_project_dir}")
        self._assetripper.extract(
            source_dir=request.source_dir,
            target_dir=request.unity_project_dir,
            log_dir=request.logs_dir,
            profile=request.profile,
        )

        editor_target = request.unity_project_dir / "ExportedProject" / "Assets" / "Editor"
        self._replace_editor_link(editor_target, request.editor_source)

        packages_target = request.unity_project_dir / "ExportedProject" / "Assets" / "Packages"
        if request.packages_source.exists():
            logger.info(f"Copying NuGet packages: {request.packages_source} -> {packages_target}")
            shutil.copytree(request.packages_source, packages_target, dirs_exist_ok=True)
        else:
            logger.warning(f"Packages directory not found: {request.packages_source}")

        restored, added = self._restore_manifest(request.unity_project_dir, prior_user_deps)
        logger.info(f"Unity project extraction complete: {request.unity_project_dir}")
        return RipResult(
            unity_project_dir=request.unity_project_dir,
            restored_upm_dependencies=restored,
            added_upm_dependencies=added,
        )

    @staticmethod
    def _snapshot_user_deps(unity_project_dir: Path) -> dict[str, str]:
        manifest_path = unity_project_dir / "ExportedProject" / "Packages" / "manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as error:
            logger.warning(f"Could not parse existing manifest, treating as empty: {error}")
            return {}
        deps: dict[str, str] = manifest.get("dependencies", {})
        return {key: value for key, value in deps.items() if not key.startswith("com.unity.modules.")}

    @staticmethod
    def _restore_manifest(
        unity_project_dir: Path,
        prior_user_deps: dict[str, str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        manifest_path = unity_project_dir / "ExportedProject" / "Packages" / "manifest.json"
        if not manifest_path.exists():
            logger.warning(f"Packages/manifest.json not found after rip: {manifest_path}")
            return (), ()

        manifest = json.loads(manifest_path.read_text())
        deps: dict[str, str] = manifest.setdefault("dependencies", {})
        restored = {key: value for key, value in prior_user_deps.items() if key not in deps}
        deps.update(restored)
        required_added = {key: value for key, value in REQUIRED_UPM_PACKAGES.items() if key not in deps}
        deps.update(required_added)

        if restored:
            logger.info(f"Restored user-added UPM deps: {sorted(restored)}")
        if required_added:
            logger.info(f"Added required UPM deps: {sorted(required_added)}")

        RipWorkflow._atomic_write_json(manifest_path, manifest)
        return tuple(sorted(restored)), tuple(sorted(required_added))

    @staticmethod
    def _atomic_write_json(path: Path, value: object) -> None:
        """Replace a manifest atomically and remove the temporary file on failure."""
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(json.dumps(value, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _replace_editor_link(target: Path, source: Path) -> None:
        if not source.exists() or not source.is_dir():
            raise FileNotFoundError(f"Editor scripts directory does not exist: {source}")

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            if target.resolve() == source.resolve():
                logger.info(f"Editor scripts symlink already valid: {target} -> {source}")
                return
            target.unlink()
        elif target.exists():
            RipWorkflow._remove_path(target)

        logger.info(f"Creating Editor scripts symlink: {target} -> {source}")
        target.symlink_to(source, target_is_directory=True)
        if not target.is_symlink() or target.resolve() != source.resolve():
            raise OSError(f"Editor scripts symlink validation failed: {target} -> {source}")

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
