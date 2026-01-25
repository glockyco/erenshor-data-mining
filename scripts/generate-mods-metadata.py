#!/usr/bin/env python3
"""Generate mod metadata JSON from mod configuration and git data.

Reads mod configuration from src/mods/mods-config.yaml and generates
metadata JSON files with version and release date info from git commit
history. Outputs to both:
- src/mods/mods-metadata.json (source of truth, versioned in git)
- src/maps/static/mods-metadata.json (website static files)

Version is derived from the last commit touching each mod using CalVer
format (YYYY.M.D.{DECIMAL_HASH}) without dirty markers. This ensures
stable, reproducible metadata that accurately reflects released versions.

Usage:
  uv run python3 scripts/generate-mods-metadata.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def get_mod_version(mod_id: str, mod_dir: Path) -> str:
    """Get the stable version for a mod from git commit history.

    Version is based on the last commit touching the mod, using CalVer format
    (YYYY.M.D.{DECIMAL_HASH}). No dirty markers are included to ensure stable,
    reproducible version strings that reflect actual released versions.

    Args:
        mod_id: Mod identifier (e.g., 'interactive-map-companion')
        mod_dir: Path to mod directory

    Returns:
        Version string in YYYY.M.D.{DECIMAL_HASH} format
    """
    try:
        # Get commit date in ISO format (YYYY-MM-DD)
        date_result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", str(mod_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        date_str = date_result.stdout.strip()

        # Get commit hash (short form, 7 chars)
        hash_result = subprocess.run(
            ["git", "log", "-1", "--format=%h", str(mod_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        hash_str = hash_result.stdout.strip()

        if not date_str or not hash_str:
            return "0.0.0-unknown"

        # Convert YYYY-MM-DD to YYYY.M.D (remove leading zeros)
        year, month, day = date_str.split("-")
        date_formatted = f"{year}.{int(month)}.{int(day)}"

        # Convert hex hash to decimal for version compatibility
        hash_decimal = int(hash_str, 16)

        return f"{date_formatted}.{hash_decimal}"
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"error: Failed to generate version for {mod_id}: {e}", file=sys.stderr)
        return "0.0.0-unknown"


def get_mod_release_date(mod_dir: Path) -> str:
    """Get the release date (commit date) for a mod directory.

    Args:
        mod_dir: Path to mod directory

    Returns:
        ISO 8601 datetime string with timezone
    """
    try:
        # Get the commit date with timezone in ISO format
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", str(mod_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # Fallback to current time if git fails
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_mod_config(config_file: Path) -> dict:
    """Load mod configuration from YAML file.

    Args:
        config_file: Path to mods-config.yaml

    Returns:
        Dictionary with mod configuration
    """
    with open(config_file) as f:
        config = yaml.safe_load(f)
    return config


def generate_metadata(repo_root: Path, config: dict) -> dict:
    """Generate complete mod metadata.

    Args:
        repo_root: Repository root directory
        config: Mod configuration from YAML

    Returns:
        Dictionary with metadata for all mods
    """
    metadata = {"mods": []}

    for mod_id, mod_config in config.get("mods", {}).items():
        # Determine mod directory path
        if "interactive-map-companion" in mod_id:
            mod_dir = repo_root / "src/mods/InteractiveMapCompanion"
        else:
            mod_dir = repo_root / "src/mods/InteractiveMapsCompanion"

        # Get version and release date from git
        version = get_mod_version(mod_id, mod_dir)
        release_date = get_mod_release_date(mod_dir)

        # Build mod metadata entry
        mod_metadata = {
            "id": mod_id,
            "name": mod_config.get("internal_name", "Unknown"),
            "displayName": mod_config.get("display_name", "Unknown"),
            "description": mod_config.get("description", ""),
            "status": mod_config.get("status", "current"),
            "port": mod_config.get("port", 18584),
            "version": version,
            "downloadUrl": f"/mods/{mod_config.get('dll_name', 'Unknown.dll')}",
            "gifUrl": mod_config.get("gif_url", ""),
            "releaseDate": release_date,
            "features": mod_config.get("features", []),
        }

        # Add deprecation notice if present
        if "deprecation_notice" in mod_config:
            mod_metadata["deprecationNotice"] = mod_config["deprecation_notice"]

        metadata["mods"].append(mod_metadata)

    # Sort by status (current first, then legacy)
    metadata["mods"].sort(key=lambda m: (m["status"] != "current", m["id"]))

    return metadata


def main() -> None:
    """Main entry point."""
    # Find repository root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("error: Not in a git repository", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    config_file = repo_root / "src/mods/mods-config.yaml"
    if not config_file.exists():
        print(f"error: Config file not found: {config_file}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_mod_config(config_file)
    except yaml.YAMLError as e:
        print(f"error: Failed to parse config YAML: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate metadata
    metadata = generate_metadata(repo_root, config)

    # Write metadata to both source and website locations
    output_files = [
        repo_root / "src/mods/mods-metadata.json",
        repo_root / "src/maps/static/mods-metadata.json",
    ]

    for output_file in output_files:
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(metadata, f, indent=2)
            f.write("\n")  # Add trailing newline for POSIX compliance

    # Print summary
    mod_count = len(metadata["mods"])
    print(f"✓ Generated metadata for {mod_count} mod(s)")
    for output_file in output_files:
        print(f"  → {output_file}")
    for mod in metadata["mods"]:
        status_str = f"[{mod['status'].upper()}]" if mod["status"] != "current" else "[CURRENT]"
        print(f"  - {mod['displayName']} v{mod['version']} {status_str}")


if __name__ == "__main__":
    main()
