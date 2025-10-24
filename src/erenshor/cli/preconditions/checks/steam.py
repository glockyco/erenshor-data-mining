"""Steam/game file precondition checks.

Check functions for Steam credentials and game file availability.
These checks ensure game files are present before attempting
extraction operations.
"""

from pathlib import Path
from typing import Any

from ..base import PreconditionResult


def game_files_exist(context: dict[str, Any]) -> PreconditionResult:
    """Check if game files directory exists.

    Verifies that game files have been downloaded from Steam.

    Args:
        context: Check context containing 'game_dir' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    game_dir = Path(context["game_dir"])

    if not game_dir.exists():
        return PreconditionResult(
            passed=False,
            check_name="game_files_exist",
            message="Game files not found",
            detail=f"Missing: {game_dir}\nRun 'erenshor extract download' to download game files via SteamCMD",
        )

    if not game_dir.is_dir():
        return PreconditionResult(
            passed=False,
            check_name="game_files_exist",
            message="Game files path is not a directory",
            detail=f"Expected directory: {game_dir}",
        )

    # Check if directory has content (not empty)
    try:
        has_files = any(game_dir.iterdir())
        if not has_files:
            return PreconditionResult(
                passed=False,
                check_name="game_files_exist",
                message="Game files directory is empty",
                detail=f"Directory exists but has no files: {game_dir}\nRun 'erenshor extract download' to download",
            )
    except PermissionError:
        return PreconditionResult(
            passed=False,
            check_name="game_files_exist",
            message="Cannot access game files directory",
            detail=f"Permission denied: {game_dir}",
        )

    return PreconditionResult(
        passed=True,
        check_name="game_files_exist",
        message=f"Game files present: {game_dir.name}",
    )


def steam_credentials_exist(context: dict[str, Any]) -> PreconditionResult:
    """Check if Steam credentials are configured.

    Checks if Steam credentials are present in the configuration system.
    Credentials are loaded from config.toml (defaults) or .erenshor/config.local.toml
    (user overrides). Store sensitive credentials in config.local.toml only.

    Args:
        context: Check context containing 'config' key with loaded configuration.

    Returns:
        PreconditionResult indicating success or failure.
    """
    config = context.get("config")
    if not config:
        return PreconditionResult(
            passed=False,
            check_name="steam_credentials_exist",
            message="Configuration not available",
            detail="Config must be loaded before checking Steam credentials",
        )

    steam_config = config.global_.steam
    steam_user = steam_config.username

    if not steam_user:
        return PreconditionResult(
            passed=False,
            check_name="steam_credentials_exist",
            message="Steam username not configured",
            detail=(
                "Missing Steam username in configuration\n"
                "Add to .erenshor/config.local.toml:\n"
                "[global.steam]\n"
                'username = "your_steam_username"\n\n'
                "Note: Password is NOT stored in config for security.\n"
                "SteamCMD will prompt for password on first run and cache login tokens."
            ),
        )

    # Don't expose actual credentials in output
    user_preview = steam_user[:3] + "***" if len(steam_user) > 3 else "***"

    return PreconditionResult(
        passed=True,
        check_name="steam_credentials_exist",
        message=f"Steam username configured (user: {user_preview})",
    )
