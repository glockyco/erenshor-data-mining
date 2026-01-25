#!/usr/bin/env python3
"""Validate mod metadata JSON structure and content.

Verifies that generated metadata has correct structure, all required fields,
and valid version/date formats. Used in pre-commit hooks and CI pipeline to
catch configuration issues early.

Exit codes:
  0: Metadata valid
  1: Validation failed (missing files, invalid structure, etc.)

Usage:
  uv run python3 scripts/validate-mods-metadata.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


def validate_version_format(version: str) -> bool:
    """Validate version format: YYYY.M.D.{decimal_hash}.

    Args:
        version: Version string to validate

    Returns:
        True if version matches CalVer format
    """
    # CalVer format: YYYY.M.D.{decimal_hash}
    # Example: 2026.1.25.2690525247
    pattern = r"^\d{4}\.\d{1,2}\.\d{1,2}\.\d+$"
    return bool(re.match(pattern, version))


def validate_url_format(url: str) -> bool:
    """Validate download/gif URL format.

    Args:
        url: URL to validate

    Returns:
        True if URL is absolute path or has valid scheme
    """
    # Allow empty strings, absolute paths /..., and http(s) URLs
    if not url:  # Allow empty gif URLs
        return True
    if url.startswith("/"):  # Absolute path
        return True
    if url.startswith("http://") or url.startswith("https://"):
        return True
    return False


def validate_metadata_structure(metadata: dict) -> tuple[bool, list[str]]:
    """Validate metadata JSON structure.

    Args:
        metadata: Parsed metadata dictionary

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check root structure
    if not isinstance(metadata, dict):
        errors.append("Root element must be an object")
        return False, errors

    if "mods" not in metadata:
        errors.append("Missing required 'mods' array")
        return False, errors

    if not isinstance(metadata["mods"], list):
        errors.append("'mods' must be an array")
        return False, errors

    if len(metadata["mods"]) == 0:
        errors.append("'mods' array must contain at least one mod")
        return False, errors

    # Validate each mod entry
    required_fields = {
        "id": str,
        "name": str,
        "displayName": str,
        "description": str,
        "status": str,
        "port": int,
        "version": str,
        "downloadUrl": str,
        "gifUrl": str,
        "releaseDate": str,
        "features": list,
    }

    for idx, mod in enumerate(metadata["mods"]):
        mod_id = mod.get("id", f"[mod {idx}]")

        if not isinstance(mod, dict):
            errors.append(f"Mod {mod_id}: must be an object")
            continue

        # Check required fields
        for field, field_type in required_fields.items():
            if field not in mod:
                errors.append(f"Mod {mod_id}: missing required field '{field}'")
                continue

            if not isinstance(mod[field], field_type):
                errors.append(
                    f"Mod {mod_id}: field '{field}' must be {field_type.__name__}, got {type(mod[field]).__name__}"
                )

        # Validate version format
        version = mod.get("version")
        if version and not validate_version_format(version):
            errors.append(f"Mod {mod_id}: invalid version format '{version}' (expected YYYY.M.D.{{decimal_hash}})")

        # Validate status value
        status = mod.get("status")
        if status and status not in ("current", "legacy"):
            errors.append(f"Mod {mod_id}: invalid status '{status}' (must be 'current' or 'legacy')")

        # Validate URLs
        for url_field in ("downloadUrl", "gifUrl"):
            url = mod.get(url_field)
            if url and not validate_url_format(url):
                errors.append(f"Mod {mod_id}: invalid {url_field} format '{url}'")

        # Validate features list
        features = mod.get("features")
        if features:
            if not all(isinstance(f, str) for f in features):
                errors.append(f"Mod {mod_id}: all features must be strings")

    return len(errors) == 0, errors


def load_metadata(metadata_file: Path) -> tuple[bool, dict | None, str]:
    """Load and parse metadata JSON file.

    Args:
        metadata_file: Path to metadata JSON file

    Returns:
        Tuple of (success, metadata_dict, error_message)
    """
    if not metadata_file.exists():
        return False, None, f"Metadata file not found: {metadata_file}"

    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
        return True, metadata, ""
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON in {metadata_file}: {e}"
    except IOError as e:
        return False, None, f"Failed to read {metadata_file}: {e}"


def main() -> None:
    """Main entry point."""
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

    # Check config file exists
    config_file = repo_root / "src/mods/mods-config.yaml"
    if not config_file.exists():
        print(f"error: Config file not found: {config_file}", file=sys.stderr)
        sys.exit(1)

    # Load config to get mod count for context
    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
        expected_mods = len(config.get("mods", {}))
    except (yaml.YAMLError, IOError) as e:
        print(f"error: Failed to parse config: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate source metadata file
    source_file = repo_root / "src/mods/mods-metadata.json"
    success, metadata, error = load_metadata(source_file)
    if not success:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    is_valid, errors = validate_metadata_structure(metadata)
    if not is_valid:
        print("error: Metadata structure invalid:", file=sys.stderr)
        for error_msg in errors:
            print(f"  - {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Verify expected mod count
    actual_mods = len(metadata.get("mods", []))
    if actual_mods != expected_mods:
        print(
            f"error: Expected {expected_mods} mods from config, but found {actual_mods} in metadata",
            file=sys.stderr,
        )
        sys.exit(1)

    # Print validation results
    print(f"✓ Metadata valid: {source_file.relative_to(repo_root)}")
    for mod in metadata.get("mods", []):
        status_str = f"[{mod['status'].upper()}]" if mod["status"] != "current" else "[CURRENT]"
        print(f"  - {mod['displayName']} v{mod['version']} {status_str}")
    print()


if __name__ == "__main__":
    main()
