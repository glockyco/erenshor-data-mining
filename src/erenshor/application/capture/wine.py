"""Paths that the game, which runs in CrossOver, and this machine both understand."""

from __future__ import annotations

from pathlib import Path


def wine_path(path: Path) -> str:
    """Convert a macOS absolute path to a Wine Z:\\ path for CrossOver."""
    absolute = str(path.resolve())
    # CrossOver/Wine maps Z:\ to the macOS root filesystem
    return "Z:" + absolute.replace("/", "\\")


def from_wine_path(path: str) -> Path:
    """Convert a Wine Z:\\ path back to a macOS Path."""
    if path.startswith(("Z:", "z:")):
        return Path(path[2:].replace("\\", "/"))
    # Already a POSIX path
    return Path(path)
