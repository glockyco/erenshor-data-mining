"""Unity precondition checks.

Check functions for Unity project structure, editor scripts,
and Unity installation.
"""

from pathlib import Path
from typing import Any

from ..base import PreconditionResult


def unity_project_exists(context: dict[str, Any]) -> PreconditionResult:
    """Check if Unity project directory exists and is valid.

    A valid Unity project has an Assets directory and ProjectSettings.

    Args:
        context: Check context containing 'unity_project' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    unity_dir = Path(context["unity_project"])

    if not unity_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Unity project not found",
            detail=f"Missing: {unity_dir}\nRun 'erenshor extract rip' to create Unity project via AssetRipper",
        )

    if not unity_dir.is_dir():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Unity project path is not a directory",
            detail=f"Expected directory: {unity_dir}",
        )

    # Check for Assets directory
    exported_project = unity_dir / "ExportedProject"
    assets_dir = exported_project / "Assets"
    if not assets_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Invalid Unity project: no Assets directory",
            detail=f"Missing Assets directory in: {exported_project}\nProject may be corrupted",
        )

    # Check for ProjectSettings (another indicator of Unity project)
    project_settings = exported_project / "ProjectSettings"
    if not project_settings.exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_project_exists",
            message="Invalid Unity project: no ProjectSettings",
            detail=f"Missing ProjectSettings directory in: {exported_project}\nProject may be incomplete",
        )

    return PreconditionResult(
        passed=True,
        check_name="unity_project_exists",
        message=f"Unity project valid: {unity_dir.name}",
    )


def editor_scripts_linked(context: dict[str, Any]) -> PreconditionResult:
    """Check if Editor scripts are properly symlinked.

    The Editor scripts must be symlinked from src/Assets/Editor
    to the Unity project's ExportedProject/Assets/Editor directory.

    Args:
        context: Check context containing 'unity_project' and 'repo_root' keys.

    Returns:
        PreconditionResult indicating success or failure.
    """
    unity_dir = Path(context["unity_project"])
    repo_root = Path(context["repo_root"])

    editor_dir = unity_dir / "ExportedProject" / "Assets" / "Editor"
    source_editor_dir = repo_root / "src" / "Assets" / "Editor"

    if not editor_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="editor_scripts_linked",
            message="Editor scripts not linked",
            detail=f"Missing: {editor_dir}\nRun 'erenshor symlink create' to create symlink",
        )

    # Check if it's a symlink
    if not editor_dir.is_symlink():
        return PreconditionResult(
            passed=False,
            check_name="editor_scripts_linked",
            message="Editor directory exists but is not a symlink",
            detail=(
                f"Expected symlink to: {source_editor_dir}\n"
                f"Found regular directory: {editor_dir}\n"
                "Manually remove and run 'erenshor symlink create'"
            ),
        )

    # Check if symlink points to correct location
    try:
        link_target = editor_dir.resolve()
        if link_target != source_editor_dir.resolve():
            return PreconditionResult(
                passed=False,
                check_name="editor_scripts_linked",
                message="Editor symlink points to wrong location",
                detail=f"Expected: {source_editor_dir}\nActual: {link_target}\nRun 'erenshor symlink create' to fix",
            )
    except (OSError, RuntimeError) as e:
        return PreconditionResult(
            passed=False,
            check_name="editor_scripts_linked",
            message="Editor symlink is broken",
            detail=f"Error resolving symlink: {e}\nRun 'erenshor symlink create' to fix",
        )

    return PreconditionResult(
        passed=True,
        check_name="editor_scripts_linked",
        message="Editor scripts properly linked",
    )


def unity_version_matches(context: dict[str, Any]) -> PreconditionResult:
    """Check if Unity version matches configured version.

    This is a warning-level check - Unity might work with different
    versions, but the configured version is recommended.

    Args:
        context: Check context containing 'config' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    config = context["config"]
    unity_config = config.global_.unity

    # Get configured Unity path
    repo_root = Path(context["repo_root"])
    unity_path = unity_config.resolved_path(repo_root, validate=False)

    if not unity_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="unity_version_matches",
            message="Unity not found at configured path",
            detail=(
                f"Missing: {unity_path}\n"
                f"Expected version: {unity_config.version}\n"
                "Configure correct path in config.toml"
            ),
        )

    # Check if version is in the path (Unity Hub structure)
    expected_version = unity_config.version
    if expected_version not in str(unity_path):
        return PreconditionResult(
            passed=False,
            check_name="unity_version_matches",
            message="Unity version mismatch",
            detail=(
                f"Expected version {expected_version} not found in path: {unity_path}\n"
                f"Game requires exact Unity version {expected_version}"
            ),
        )

    return PreconditionResult(
        passed=True,
        check_name="unity_version_matches",
        message=f"Unity version matches: {expected_version}",
    )
