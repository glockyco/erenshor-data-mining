#!/usr/bin/env python3
"""Generate mod version from git using CalVer format.

Format: YYYY.M.D.{COMMIT_HASH_AS_DECIMAL}

Example:
  $ python3 scripts/generate-mod-version.py src/mods/InteractiveMapCompanion
  2026.1.25.1705838412

For Release builds, fails if working tree has uncommitted changes.
For Debug builds, appends -dirty-{timestamp} if tree is dirty.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_git_info(mod_dir: Path) -> tuple[str, str] | None:
    """Get git commit date and hash for a directory.

    Args:
        mod_dir: Path to mod directory (relative to repo root)

    Returns:
        Tuple of (date_YYYY.M.D, commit_hash_hex) or None if git fails
    """
    try:
        # Get commit date in ISO format (YYYY-MM-DD)
        date_str = subprocess.run(
            ["git", "log", "-1", "--format=%cs", mod_dir],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Get commit hash (short form, 7 chars)
        hash_str = subprocess.run(
            ["git", "log", "-1", "--format=%h", mod_dir],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if not date_str or not hash_str:
            return None

        # Convert YYYY-MM-DD to YYYY.M.D (remove leading zeros)
        year, month, day = date_str.split("-")
        date_formatted = f"{year}.{int(month)}.{int(day)}"

        return (date_formatted, hash_str)
    except (subprocess.CalledProcessError, ValueError):
        return None


def check_dirty_tree(mod_dir: Path) -> bool:
    """Check if working tree has uncommitted changes.

    Args:
        mod_dir: Path to mod directory

    Returns:
        True if tree has uncommitted changes, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", mod_dir],
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def convert_hash_to_decimal(hash_hex: str) -> int:
    """Convert hex commit hash to decimal for System.Version compatibility.

    Args:
        hash_hex: Hex commit hash (e.g., 'a52c0c32')

    Returns:
        Decimal representation as int
    """
    return int(hash_hex, 16)


def get_version(mod_dir: Path, config: str = "Debug") -> str:
    """Generate version for a mod.

    Args:
        mod_dir: Path to mod directory (relative to repo root)
        config: Build configuration (Debug or Release)

    Returns:
        Version string in format YYYY.M.D.{DECIMAL_HASH}
    """
    git_info = get_git_info(mod_dir)

    if not git_info:
        # Fallback if git fails
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d%H%M%S")
        return f"0.0.0-{timestamp}"

    date_formatted, hash_hex = git_info

    # Convert hash to decimal
    hash_decimal = convert_hash_to_decimal(hash_hex)
    version = f"{date_formatted}.{hash_decimal}"

    # Check for uncommitted changes
    is_dirty = check_dirty_tree(mod_dir)

    if is_dirty:
        if config == "Release":
            # Release builds must have clean working tree
            print(
                f"error: Cannot build Release with uncommitted changes in {mod_dir}",
                file=sys.stderr,
            )
            print("Commit or stash your changes first.", file=sys.stderr)
            sys.exit(1)

        # Debug builds: append dirty marker
        now = datetime.now(timezone.utc)
        dirty_timestamp = now.strftime("%Y%m%d-%H%M%S")
        version = f"{version}-dirty-{dirty_timestamp}"

    return version


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: generate-mod-version.py <mod_dir> [Debug|Release]", file=sys.stderr)
        sys.exit(1)

    mod_dir = Path(sys.argv[1])
    config = sys.argv[2] if len(sys.argv) > 2 else "Debug"

    version = get_version(mod_dir, config)
    print(version)


if __name__ == "__main__":
    main()
