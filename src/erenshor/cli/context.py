"""CLI context management.

This module provides the CLIContext dataclass that holds shared state
for all CLI commands. The context is passed through Typer's dependency
injection system (ctx.obj) and contains configuration, variant selection,
dry-run mode, and other global state.
"""

from dataclasses import dataclass
from pathlib import Path

from erenshor.infrastructure.config.schema import Config


@dataclass
class CLIContext:
    """Context passed to all CLI commands.

    This context holds the loaded configuration, variant selection,
    dry-run flag, and repository root path. It is created during
    CLI initialization and passed to all command handlers.

    Attributes:
        config: Loaded configuration from TOML files.
        variant: Selected variant name (main, playtest, demo).
        dry_run: If True, commands should show what they would do
            without making actual changes.
        repo_root: Path to repository root directory.
    """

    config: Config
    variant: str
    dry_run: bool
    repo_root: Path
