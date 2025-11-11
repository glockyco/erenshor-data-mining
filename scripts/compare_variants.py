#!/usr/bin/env python3
"""Compare two Erenshor database variants to identify new content.

This script compares two SQLite databases (typically main vs playtest or playtest vs demo)
and generates a comprehensive markdown report of all new content additions.

Usage:
    python scripts/compare_variants.py main playtest
    python scripts/compare_variants.py playtest demo
    python scripts/compare_variants.py --help
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def get_db_path(variant_or_path: str) -> Path:
    """Get the database path for a variant or return path if it's already a path.

    Args:
        variant_or_path: Either a variant name (main/playtest/demo) or a direct path to a database file

    Returns:
        Path to the database file
    """
    # Check if it's already a path (contains / or ends with .sqlite)
    if "/" in variant_or_path or variant_or_path.endswith(".sqlite"):
        return Path(variant_or_path)

    # Otherwise treat as variant name
    repo_root = Path(__file__).parent.parent
    return repo_root / "variants" / variant_or_path / f"erenshor-{variant_or_path}.sqlite"


def get_build_id(variant_or_path: str) -> str:
    """Get the build ID from the most recent backup directory or from path.

    Args:
        variant_or_path: Either a variant name or a database path

    Returns:
        Build ID string or "Unknown"
    """
    try:
        # If it's a path, try to extract build ID from the path
        if "/" in variant_or_path or variant_or_path.endswith(".sqlite"):
            path = Path(variant_or_path)
            # Look for backup-NNNNNNNN pattern in path
            for part in path.parts:
                if part.startswith("backup-"):
                    return part.replace("backup-", "")
            return "Current"

        # Otherwise, get from most recent backup directory for variant
        repo_root = Path(__file__).parent.parent
        backup_dir = repo_root / "variants" / variant_or_path / "backups"

        if not backup_dir.exists():
            return "Unknown"

        # Find the most recent build-* or backup-* directory
        build_dirs = sorted(backup_dir.glob("backup-*"), reverse=True)
        if build_dirs:
            # Extract build ID from directory name (e.g., "backup-20611000" -> "20611000")
            build_id = build_dirs[0].name.replace("backup-", "")
            return build_id

        return "Unknown"
    except Exception:
        return "Unknown"


def get_counts(db_path: Path) -> dict[str, int]:
    """Get entity counts from database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    counts = {}
    tables = [
        ("Items", "Items"),
        ("Spells", "Spells"),
        ("Skills", "Skills"),
        ("Characters", "Characters"),
        ("Quests", "Quests"),
        ("Zones", "Zones"),
    ]

    for name, table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[name] = cursor.fetchone()[0]

    conn.close()
    return counts


def compare_items(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find new items in new_db compared to base_db."""
    conn = sqlite3.connect(str(new_db))
    cursor = conn.cursor()

    cursor.execute(f"ATTACH DATABASE '{base_db}' AS base")

    cursor.execute("""
        SELECT
            ItemName,
            RequiredSlot,
            ItemLevel,
            Lore
        FROM Items
        WHERE ResourceName NOT IN (SELECT ResourceName FROM base.Items)
        ORDER BY RequiredSlot, ItemLevel, ItemName
    """)

    results = []
    for row in cursor.fetchall():
        # Clean up text: normalize whitespace
        lore = row[3]
        if lore:
            # Replace newlines with spaces, then collapse multiple spaces
            lore = " ".join(lore.split())

        results.append(
            {
                "name": row[0],
                "slot": row[1],
                "level": row[2],
                "lore": lore,
            }
        )

    conn.close()
    return results


def compare_spells(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find new spells in new_db compared to base_db."""
    conn = sqlite3.connect(str(new_db))
    cursor = conn.cursor()

    cursor.execute(f"ATTACH DATABASE '{base_db}' AS base")

    cursor.execute("""
        SELECT
            SpellName,
            Type,
            SpellDesc
        FROM Spells
        WHERE ResourceName NOT IN (SELECT ResourceName FROM base.Spells)
        ORDER BY Type, SpellName
    """)

    results = []
    for row in cursor.fetchall():
        # Clean up text: normalize whitespace
        desc = row[2]
        if desc:
            desc = " ".join(desc.split())

        results.append(
            {
                "name": row[0],
                "type": row[1],
                "desc": desc,
            }
        )

    conn.close()
    return results


def compare_characters(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find new characters in new_db compared to base_db."""
    conn = sqlite3.connect(str(new_db))
    cursor = conn.cursor()

    cursor.execute(f"ATTACH DATABASE '{base_db}' AS base")

    cursor.execute("""
        SELECT
            ch.NPCName,
            ch.Level,
            ch.IsNPC,
            ch.IsVendor,
            ch.EffectiveHP,
            ch.StableKey,
            COALESCE(za_spawn.ZoneName, za_direct.ZoneName) as ZoneName
        FROM Characters ch
        -- Try to get zone from spawn point first
        LEFT JOIN SpawnPointCharacters spc ON spc.CharacterStableKey = ch.StableKey
        LEFT JOIN SpawnPoints sp ON sp.Id = spc.SpawnPointId
        LEFT JOIN Coordinates c_spawn ON c_spawn.SpawnPointId = sp.Id
        LEFT JOIN Zones za_spawn ON za_spawn.SceneName = c_spawn.Scene
        -- Fall back to direct coordinate if no spawn point
        LEFT JOIN Coordinates c_direct ON c_direct.Id = ch.CoordinateId
        LEFT JOIN Zones za_direct ON za_direct.SceneName = c_direct.Scene
        WHERE ch.ObjectName NOT IN (SELECT ObjectName FROM base.Characters)
        GROUP BY ch.StableKey
        ORDER BY ch.IsNPC DESC, ch.Level, ch.NPCName
    """)

    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "name": row[0],
                "level": row[1],
                "is_npc": bool(row[2]),
                "is_vendor": bool(row[3]),
                "hp": row[4],
                "zone": row[6],
            }
        )

    conn.close()
    return results


def compare_quests(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find new quests in new_db compared to base_db."""
    conn = sqlite3.connect(str(new_db))
    cursor = conn.cursor()

    cursor.execute(f"ATTACH DATABASE '{base_db}' AS base")

    cursor.execute("""
        SELECT
            qv.QuestName,
            qv.XPonComplete,
            qv.GoldOnComplete,
            SUBSTR(qv.QuestDesc, 1, 150) as DescPreview
        FROM Quests q
        LEFT JOIN QuestVariants qv ON qv.QuestStableKey = q.StableKey
        WHERE q.DBName NOT IN (SELECT DBName FROM base.Quests)
        ORDER BY qv.QuestName
    """)

    results = []
    for row in cursor.fetchall():
        # Clean up text: normalize whitespace
        desc = row[3]
        if desc:
            desc = " ".join(desc.split())

        results.append(
            {
                "name": row[0],
                "xp": row[1],
                "gold": row[2],
                "desc": desc,
            }
        )

    conn.close()
    return results


def compare_zones(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find new zones in new_db compared to base_db."""
    conn = sqlite3.connect(str(new_db))
    cursor = conn.cursor()

    cursor.execute(f"ATTACH DATABASE '{base_db}' AS base")

    cursor.execute("""
        SELECT
            ZoneName,
            SceneName
        FROM Zones
        WHERE SceneName NOT IN (SELECT SceneName FROM base.Zones)
        ORDER BY ZoneName
    """)

    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "name": row[0],
                "scene": row[1],
            }
        )

    conn.close()
    return results


def format_items_section(items: list[dict[str, Any]]) -> str:
    """Format items section for markdown."""
    if not items:
        return "_No new items found._\n"

    output = []
    # Sort by level (descending), then by name
    for item in sorted(items, key=lambda x: (-(x["level"] or 0), x["name"])):
        slot = item["slot"] or "General"
        level = item["level"] or 0
        lore = item["lore"] or "No description"
        output.append(f'- **{item["name"]}** ({slot}, Level {level}) - "{lore}"\n')

    output.append("\n")
    return "".join(output)


def format_spells_section(spells: list[dict[str, Any]]) -> str:
    """Format spells section for markdown."""
    if not spells:
        return "_No new spells found._\n"

    output = []
    # Sort by name
    for spell in sorted(spells, key=lambda x: x["name"]):
        spell_type = spell["type"] or "Other"
        desc = spell["desc"] or "No description"
        output.append(f'- **{spell["name"]}** ({spell_type}) - "{desc}"\n')

    output.append("\n")
    return "".join(output)


def format_characters_section(characters: list[dict[str, Any]]) -> str:
    """Format characters section for markdown."""
    if not characters:
        return "_No new characters found._\n"

    output = []
    # Sort by level (descending), then by name alphabetically
    for char in sorted(characters, key=lambda x: (-(x["level"] or 0), x["name"])):
        hp_str = f"{char['hp']:,}" if char["hp"] else "Unknown"
        vendor_str = " [Vendor]" if char["is_vendor"] else ""
        zone_str = f" - {char['zone']}" if char.get("zone") else ""
        output.append(f"- **{char['name']}** (Level {char['level']}, {hp_str} HP){vendor_str}{zone_str}\n")

    output.append("\n")
    return "".join(output)


def format_quests_section(quests: list[dict[str, Any]]) -> str:
    """Format quests section for markdown."""
    if not quests:
        return "_No new quests found._\n"

    output = []
    for quest in sorted(quests, key=lambda x: x["name"]):
        gold_str = f", {quest['gold']} Gold" if quest["gold"] > 0 else ""
        output.append(f"- **{quest['name']}** ({quest['xp']:,} XP{gold_str}) - {quest['desc']}...\n")

    output.append("\n")
    return "".join(output)


def format_zones_section(zones: list[dict[str, Any]]) -> str:
    """Format zones section for markdown."""
    if not zones:
        return "_No new zones found._\n"

    output = []
    for zone in sorted(zones, key=lambda x: x["name"]):
        output.append(f"- **{zone['name']}** (Scene: {zone['scene']})\n")

    output.append("\n")
    return "".join(output)


def generate_report(base_variant: str, new_variant: str, output_path: Path | None = None) -> str:
    """Generate a complete comparison report."""
    base_db = get_db_path(base_variant)
    new_db = get_db_path(new_variant)

    if not base_db.exists():
        print(f"Error: Old database not found: {base_db}", file=sys.stderr)
        sys.exit(1)

    if not new_db.exists():
        print(f"Error: New database not found: {new_db}", file=sys.stderr)
        sys.exit(1)

    # Get metadata
    base_build = get_build_id(base_variant)
    new_build = get_build_id(new_variant)
    base_counts = get_counts(base_db)
    new_counts = get_counts(new_db)

    # Compare content
    new_items = compare_items(base_db, new_db)
    new_spells = compare_spells(base_db, new_db)
    new_characters = compare_characters(base_db, new_db)
    new_quests = compare_quests(base_db, new_db)
    new_zones = compare_zones(base_db, new_db)

    # Generate markdown
    report = []
    report.append(f"# Erenshor: {new_variant.title()} vs {base_variant.title()} Comparison\n")
    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Old Variant**: {base_variant} (Build {base_build})\n")
    report.append(f"**New Variant**: {new_variant} (Build {new_build})\n")
    report.append("\n---\n\n")

    # Summary table (order matches report sections)
    report.append("## Summary Statistics\n\n")
    report.append("| Category | Old Count | New Count | Difference |\n")
    report.append("|----------|-----------|-----------|------------|\n")

    for category in ["Zones", "Items", "Spells", "Characters", "Quests", "Skills"]:
        base_count = base_counts[category]
        new_count = new_counts[category]
        diff = new_count - base_count
        sign = "+" if diff > 0 else ""
        report.append(f"| {category} | {base_count:,} | {new_count:,} | {sign}{diff} |\n")

    report.append("\n---\n\n")

    # New zones
    if new_zones:
        report.append(f"## New Zones ({len(new_zones)})\n\n")
        report.append(format_zones_section(new_zones))
        report.append("---\n\n")

    # New items
    if new_items:
        report.append(f"## New Items ({len(new_items)})\n\n")
        report.append(format_items_section(new_items))
        report.append("---\n\n")

    # New spells
    if new_spells:
        report.append(f"## New Spells ({len(new_spells)})\n\n")
        report.append(format_spells_section(new_spells))
        report.append("---\n\n")

    # New characters
    if new_characters:
        report.append(f"## New Characters/NPCs ({len(new_characters)})\n\n")
        report.append(format_characters_section(new_characters))
        report.append("---\n\n")

    # New quests
    if new_quests:
        report.append(f"## New Quests ({len(new_quests)})\n\n")
        report.append(format_quests_section(new_quests))
        report.append("---\n\n")

    report_text = "".join(report)

    # Write to file if output path specified
    if output_path:
        output_path.write_text(report_text)
        print(f"Report written to: {output_path}")

    return report_text


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare two Erenshor database variants to identify new content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare main vs playtest
  python scripts/compare_variants.py main playtest

  # Compare playtest vs demo
  python scripts/compare_variants.py playtest demo

  # Output to specific file
  python scripts/compare_variants.py main playtest -o changes.md
        """,
    )

    parser.add_argument(
        "base_variant",
        help="Old variant to compare against (variant name or path to .sqlite file)",
    )

    parser.add_argument(
        "new_variant",
        help="New variant to compare (variant name or path to .sqlite file)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path (default: {new_variant}_vs_{base_variant}.md)",
    )

    parser.add_argument(
        "--print",
        action="store_true",
        help="Print report to stdout instead of file",
    )

    args = parser.parse_args()

    if args.base_variant == args.new_variant:
        print("Error: Old and new variants must be different", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.print:
        output_path = None
    elif args.output:
        output_path = args.output
    else:
        output_path = Path(f"{args.new_variant}_vs_{args.base_variant}.md")

    # Generate report
    report = generate_report(args.base_variant, args.new_variant, output_path)

    # Print to stdout if requested
    if args.print:
        print(report)


if __name__ == "__main__":
    main()
