"""Maps commands for interactive map website.

This module provides commands for building and deploying the interactive maps:
- Building the maps website from game data
- Deploying maps to hosting platform
- Validating map data and assets
"""

import typer

app = typer.Typer(
    name="maps",
    help="Build and deploy the interactive maps website",
    no_args_is_help=True,
)
