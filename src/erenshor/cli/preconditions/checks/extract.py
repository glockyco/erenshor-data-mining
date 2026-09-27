"""Preflight inputs shared by extraction report and IDE commands."""

from __future__ import annotations

from typing import Any

from erenshor.cli.preconditions.base import PreconditionResult
from erenshor.infrastructure.config.paths import PathResolutionError
from erenshor.infrastructure.csproj_generator import UnityPaths
from erenshor.infrastructure.steam.installation import GameInstallationError, find_game_installation


def comparison_databases(context: dict[str, Any]) -> PreconditionResult:
    """Require both configured, distinct variants and their clean databases."""
    variants = context["config"].variants
    base = context["base_variant"]
    new = context["new_variant"]
    for name in (base, new):
        if name not in variants:
            return PreconditionResult(False, "comparison_databases", f"Unknown variant '{name}'")
    if base == new:
        return PreconditionResult(False, "comparison_databases", "Base and new variants must be different")
    for name, label in ((base, "Old"), (new, "New")):
        path = variants[name].resolved_database(context["repo_root"])
        if not path.is_file():
            return PreconditionResult(
                False, "comparison_databases", f"{label} database not found for variant '{name}': {path}"
            )
    return PreconditionResult(True, "comparison_databases", "Both comparison databases are available")


def ide_sources(context: dict[str, Any]) -> PreconditionResult:
    """Require a usable Unity Editor and DLLs for each extracted variant."""
    repo_root = context["repo_root"]
    try:
        editor_path = context["config"].global_.unity.resolved_path(repo_root)
        UnityPaths.from_executable(editor_path)
    except (FileNotFoundError, PathResolutionError) as error:
        return PreconditionResult(False, "ide_sources", "Unity Editor is required for IDE setup", str(error))

    for name, variant in context["config"].variants.items():
        scripts_dir = variant.resolved_unity_project(repo_root) / "ExportedProject/Assets/Scripts/Assembly-CSharp"
        if not scripts_dir.is_dir():
            continue
        try:
            managed_dir = find_game_installation(name, variant.app_id).managed_dir
        except GameInstallationError as error:
            return PreconditionResult(False, "ide_sources", f"{name}: game installation unavailable", str(error))
        plugins_dir = variant.resolved_unity_project(repo_root) / "ExportedProject/Assets/Plugins"
        has_managed_dll = any(path.name != "Assembly-CSharp.dll" for path in managed_dir.glob("*.dll"))
        if not has_managed_dll and not any(plugins_dir.glob("*.dll")):
            return PreconditionResult(False, "ide_sources", f"{name}: No DLLs found in {managed_dir} or {plugins_dir}")
    return PreconditionResult(True, "ide_sources", "IDE generation sources are available")
