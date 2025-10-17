"""Extract commands for data extraction pipeline.

This module provides commands for managing the data extraction pipeline:
- Downloading game files from Steam via SteamCMD
- Extracting Unity projects via AssetRipper
- Exporting game data to SQLite via Unity batch mode
"""

import typer

app = typer.Typer(
    name="extract",
    help="Extract game data from Steam, AssetRipper, and Unity",
    no_args_is_help=True,
)
