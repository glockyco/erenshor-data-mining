"""Reusable precondition check functions.

This package provides check functions organized by domain:
- database: Database existence, validity, content checks
- filesystem: File and directory existence checks
- unity: Unity project and editor script checks
- steam: Steam/game file checks

Check functions are simple, reusable, and composable. Import the ones
you need and use them with the @require_preconditions decorator.

Example:
    from erenshor.cli.preconditions import require_preconditions
    from erenshor.cli.preconditions.checks.database import (
        database_exists,
        database_valid,
    )
    from erenshor.cli.preconditions.checks.unity import unity_project_exists

    @require_preconditions(
        database_exists,
        database_valid,
        unity_project_exists,
    )
    def export_command(ctx: typer.Context):
        pass
"""

# Import all check functions for convenient access
from .database import database_exists, database_has_items, database_valid
from .filesystem import directory_exists, directory_writable, file_exists
from .steam import game_files_exist, steam_credentials_exist
from .unity import editor_scripts_linked, unity_project_exists, unity_version_matches

__all__ = [
    "database_exists",
    "database_has_items",
    "database_valid",
    "directory_exists",
    "directory_writable",
    "editor_scripts_linked",
    "file_exists",
    "game_files_exist",
    "steam_credentials_exist",
    "unity_project_exists",
    "unity_version_matches",
]
