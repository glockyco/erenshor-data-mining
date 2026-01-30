#!/usr/bin/env python3
"""One-time migration: Normalize mapping.json stable keys to colon format.

This script migrates character stable keys from the legacy pipe delimiter format
(character:name|scene|x|y|z) to the current colon format (character:name:scene:x:y:z).

Context:
- Jan 18, 2026: Changed delimiter from | to : (commit 9e8eb77f)
- mapping.json last updated Nov 14, 2025 (has 73 pipe-formatted entries)
- This creates duplicate registry entries causing wiki save failures

Usage:
    uv run python scripts/migrate_mapping_json.py [--dry-run]
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

MAPPING_FILE = Path("mapping.json")
BACKUP_SUFFIX = ".backup"


def migrate_stable_key(stable_key: str) -> str:
    """Convert pipe delimiters to colons and normalize to lowercase.

    Args:
        stable_key: Stable key in format "entity_type:component1|component2|..."

    Returns:
        Normalized key: "entity_type:component1:component2:..."

    Examples:
        >>> migrate_stable_key("character:Stoneman Seeker (1)|Blight|438.18|43.30|180.65")
        'character:stoneman seeker (1):blight:438.18:43.30:180.65'

        >>> migrate_stable_key("character:dire wolf")  # No change needed
        'character:dire wolf'
    """
    return stable_key.lower().replace("|", ":")


def main(dry_run: bool = False) -> None:
    """Migrate mapping.json stable keys from pipe to colon format."""

    # Load mapping.json
    print(f"Loading {MAPPING_FILE}...")
    with open(MAPPING_FILE) as f:
        data = json.load(f)

    # Track changes
    migrated_keys = {}
    unchanged = []

    # Migrate each rule
    for old_key, rule_data in data["rules"].items():
        new_key = migrate_stable_key(old_key)

        if old_key != new_key:
            migrated_keys[old_key] = new_key
        else:
            unchanged.append(old_key)

    # Report
    print(f"\nMigration Summary:")
    print(f"  Total rules: {len(data['rules'])}")
    print(f"  Migrated: {len(migrated_keys)}")
    print(f"  Unchanged: {len(unchanged)}")

    if migrated_keys:
        print(f"\nSample migrations (first 5):")
        for old, new in list(migrated_keys.items())[:5]:
            print(f"  {old}")
            print(f"  → {new}")

    if dry_run:
        print("\n[DRY RUN] No changes written")
        return

    # Create backup
    backup_path = MAPPING_FILE.with_suffix(MAPPING_FILE.suffix + BACKUP_SUFFIX)
    shutil.copy2(MAPPING_FILE, backup_path)
    print(f"\nBackup created: {backup_path}")

    # Rebuild rules with migrated keys
    new_rules = {}
    for old_key, rule_data in data["rules"].items():
        new_key = migrated_keys.get(old_key, old_key)
        new_rules[new_key] = rule_data

    # Update data
    data["rules"] = new_rules
    data["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Write back
    with open(MAPPING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Trailing newline

    print(f"\nMigration complete: {MAPPING_FILE}")
    print(f"\nNext steps:")
    print(f"  1. Verify changes: git diff {MAPPING_FILE}")
    print(f"  2. Rebuild registries: rm variants/*/wiki/registry.db")
    print(f"  3. Rebuild: uv run erenshor registry rebuild")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
