#!/usr/bin/env python3
"""Fix mapping.json issues after migration.

Fixes two confirmed issues:
1. Duplicate key collisions - restore correct Priel Note entries
2. Phantom entries - remove 14 entries that don't exist in game DB

Usage:
    uv run python scripts/fix_mapping_issues.py [--dry-run]
"""

import json
from datetime import datetime, timezone
from pathlib import Path

MAPPING_FILE = Path("mapping.json")

# Entries to fix (duplicates that lost good data)
ENTRIES_TO_FIX = {
    "item:gen - priel note": {
        "wiki_page_name": "Priel Note",
        "display_name": "Priel Note (1)",
        "image_name": "Priel Note",
        "mapping_type": "custom",
        "reason": "Distinguish the two different 'Priel Note' items",
    },
    "item:gen - priel note 1": {
        "wiki_page_name": "Priel Note",
        "display_name": "Priel Note (2)",
        "image_name": "Priel Note",
        "mapping_type": "custom",
        "reason": "Distinguish the two different 'Priel Note' items",
    },
}

# Phantom entries to remove (don't exist in game DB)
PHANTOM_ENTRIES = [
    # Coordinate mismatches (Y-coordinate precision: -0.00 vs 0.00, or X/Z off by 0.01)
    "character:shambler (1):ripperportal:271.18:-0.00:430.42",
    "character:shambler (2):ripperportal:330.21:-0.00:436.74",
    "character:shambler (3):ripperportal:331.21:-0.00:430.46",
    "character:shambler (4):ripperportal:368.18:-0.00:433.52",
    "character:shambler (5):ripperportal:409.08:-0.00:433.71",
    "character:shambler (7):ripperportal:219.72:-0.00:436.41",
    "character:nightmarian knight (2):fernallaportal:171.04:1.34:517.64",  # X: 171.04 vs 171.05
    "character:stoneman seeker (4):blight:424.01:43.30:156.29",  # X: 424.01 vs 424.02
    "character:sm_prop_furnace_01:prielplateau:205.24:15.59:215.01",  # Z: 215.01 vs 215.02
    # Removed game content
    "character:sm_prop_furnace_01:summerevent:174.65:11.60:144.57",  # SummerEvent zone removed
    # Wrong suffix format (_0 doesn't exist in game, should be no suffix or :1)
    "character:sivakayan cleric_0",
    "character:sivakayan raider_0",
    "character:sivakayan reaver_0",
    # Prefab that doesn't exist (elder variant exists, not base)
    "character:grassland ogre",
]


def main(dry_run: bool = False) -> None:
    """Fix mapping.json issues."""

    # Load mapping.json
    print(f"Loading {MAPPING_FILE}...")
    with open(MAPPING_FILE) as f:
        data = json.load(f)

    original_count = len(data["rules"])

    # Fix duplicate key collisions
    fixed_count = 0
    for key, correct_data in ENTRIES_TO_FIX.items():
        if key in data["rules"]:
            current = data["rules"][key]
            if current != correct_data:
                print(f"\nFixing duplicate collision: {key}")
                print(f"  Before: display_name={current.get('display_name')!r}")
                print(f"  After:  display_name={correct_data['display_name']!r}")
                data["rules"][key] = correct_data
                fixed_count += 1

    # Remove phantom entries
    removed_count = 0
    print(f"\nRemoving phantom entries (don't exist in game DB):")
    for key in PHANTOM_ENTRIES:
        if key in data["rules"]:
            entry = data["rules"][key]
            print(f"  - {key}")
            print(f"    → maps to: {entry['wiki_page_name']}")
            del data["rules"][key]
            removed_count += 1
        else:
            print(f"  ! {key} (already removed)")

    final_count = len(data["rules"])

    # Summary
    print(f"\nSummary:")
    print(f"  Original entries: {original_count}")
    print(f"  Fixed collisions:  {fixed_count}")
    print(f"  Removed phantoms:  {removed_count}")
    print(f"  Final entries:     {final_count}")
    print(f"  Net change:        {final_count - original_count:+d}")

    if dry_run:
        print("\n[DRY RUN] No changes written")
        return

    # Update metadata
    data["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Write back
    with open(MAPPING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Trailing newline

    print(f"\nFixed: {MAPPING_FILE}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
