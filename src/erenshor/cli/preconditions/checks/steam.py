"""Steam/game file precondition checks.

Check functions for Steam credentials and game file availability.
These checks ensure game files are present before attempting
extraction operations.
"""

from pathlib import Path

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

    This is a basic check that looks for credential-related environment
    variables. Actual validation happens during SteamCMD execution.

    Args:
        context: Check context (credentials checked via environment).

    Returns:
        PreconditionResult indicating success or failure.
    """
    import os

    # Check for Steam credentials in environment
    steam_user = os.environ.get("STEAM_USERNAME")
    steam_pass = os.environ.get("STEAM_PASSWORD")

    if not steam_user:
        return PreconditionResult(
            passed=False,
            check_name="steam_credentials_exist",
            message="Steam credentials not configured",
            detail="Missing STEAM_USERNAME environment variable\nSet credentials: export STEAM_USERNAME=your_username\nSteamCMD requires valid Steam account credentials",
        )

    if not steam_pass:
        return PreconditionResult(
            passed=False,
            check_name="steam_credentials_exist",
            message="Steam credentials incomplete",
            detail="Missing STEAM_PASSWORD environment variable\nSet credentials: export STEAM_PASSWORD=your_password\nSteamCMD requires both username and password",
        )

    # Don't expose actual credentials in output
    user_preview = steam_user[:3] + "***" if len(steam_user) > 3 else "***"

    return PreconditionResult(
        passed=True,
        check_name="steam_credentials_exist",
        message=f"Steam credentials configured (user: {user_preview})",
    )
