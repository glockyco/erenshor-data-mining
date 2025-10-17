"""Extract commands for data extraction pipeline.

This module provides commands for managing the data extraction pipeline:
- Downloading game files from Steam via SteamCMD
- Extracting Unity projects via AssetRipper
- Exporting game data to SQLite via Unity batch mode
"""

import typer

from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.steam import game_files_exist, steam_credentials_exist
from erenshor.cli.preconditions.checks.unity import editor_scripts_linked, unity_project_exists, unity_version_matches

app = typer.Typer(
    name="extract",
    help="Extract game data from Steam, AssetRipper, and Unity",
    no_args_is_help=True,
)


@app.command()
def full(
    ctx: typer.Context,
    skip_download: bool = typer.Option(
        False,
        "--skip-download",
        help="Skip download step (use existing game files)",
    ),
    skip_rip: bool = typer.Option(
        False,
        "--skip-rip",
        help="Skip AssetRipper extraction step (use existing Unity project)",
    ),
    skip_export: bool = typer.Option(
        False,
        "--skip-export",
        help="Skip Unity export step (use existing database)",
    ),
) -> None:
    """Run full extraction pipeline (download → rip → export).

    This command orchestrates the complete data extraction process:
    1. Downloads game files from Steam via SteamCMD
    2. Extracts Unity project from game files via AssetRipper
    3. Exports game data to SQLite via Unity batch mode

    Steps can be skipped if data already exists.
    """
    typer.echo("Not yet implemented: extract full")


@app.command()
@require_preconditions(steam_credentials_exist)
def download(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-download even if files exist",
    ),
) -> None:
    """Download game files from Steam via SteamCMD.

    Downloads the Erenshor game files for the selected variant
    using SteamCMD. Requires valid Steam credentials and game
    ownership.
    """
    typer.echo("Not yet implemented: extract download")


@app.command()
@require_preconditions(game_files_exist)
def rip(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-extraction even if Unity project exists",
    ),
) -> None:
    """Extract Unity project from game files via AssetRipper.

    Uses AssetRipper to decompile the Erenshor game files into
    a Unity project structure. This allows access to game assets
    and ScriptableObjects for data mining.
    """
    typer.echo("Not yet implemented: extract rip")


@app.command()
@require_preconditions(
    unity_project_exists,
    editor_scripts_linked,
    unity_version_matches,
)
def export(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-export even if database is up-to-date",
    ),
) -> None:
    """Export data to SQLite via Unity batch mode.

    Runs Unity Editor in batch mode to scan game assets and
    export data to SQLite database. Uses custom Unity Editor
    scripts to extract items, NPCs, quests, spells, and more.
    """
    typer.echo("Not yet implemented: extract export")
