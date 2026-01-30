#!/usr/bin/env python3
"""Fix mapping.json entries to have explicit display_name and image_name values.

For non-excluded entities:
- Sets display_name to wiki_page_name if missing
- Sets image_name to display_name if missing

Excluded entities (wiki_page_name=None) are left unchanged.
"""

import json
from pathlib import Path


def fix_mapping_json(mapping_path: Path) -> tuple[int, int, int]:
    """Fix display_name and image_name values in mapping.json.

    Returns:
        Tuple of (total_entries, fixed_display_name, fixed_image_name)
    """
    with mapping_path.open() as f:
        data = json.load(f)

    rules = data.get("rules", {})
    total = len(rules)
    fixed_display = 0
    fixed_image = 0

    for stable_key, rule in rules.items():
        wiki_page_name = rule.get("wiki_page_name")
        display_name = rule.get("display_name")
        image_name = rule.get("image_name")

        # Skip excluded entities (wiki_page_name is None)
        if wiki_page_name is None:
            continue

        # Fix entries with wiki_page_name but no display_name
        if display_name is None:
            rule["display_name"] = wiki_page_name
            fixed_display += 1
            print(f"Fixed display_name: {stable_key}")
            print(f'  Set: "{wiki_page_name}"')

        # Fix entries with wiki_page_name but no image_name
        # Use the (now fixed) display_name as default for image_name
        if image_name is None:
            rule["image_name"] = rule["display_name"]
            fixed_image += 1
            print(f"Fixed image_name: {stable_key}")
            print(f'  Set: "{rule["display_name"]}"')

    # Write back
    with mapping_path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return total, fixed_display, fixed_image


if __name__ == "__main__":
    mapping_file = Path(__file__).parent.parent / "mapping.json"

    if not mapping_file.exists():
        print(f"Error: {mapping_file} not found")
        exit(1)

    print(f"Making all override fields explicit in {mapping_file}")
    print()

    total, fixed_display, fixed_image = fix_mapping_json(mapping_file)

    print()
    print(f"Summary:")
    print(f"  Total entries: {total}")
    print(f"  Fixed display_name: {fixed_display}")
    print(f"  Fixed image_name: {fixed_image}")
    print(f"  Total fixes: {fixed_display + fixed_image}")

    if fixed_display > 0 or fixed_image > 0:
        print()
        print("✓ mapping.json has been updated")
        print("  Review the changes with: git diff mapping.json")
    else:
        print()
        print("✓ No changes needed - all entries are explicit")
