#!/usr/bin/env python3
"""
Zone Discrepancy Report Generator

Compares the game's ZoneThisLootIsFrom data (from KnowledgeDatabaseHolder.asset)
against spawn-point-inferred zones from our SQLite database.

Outputs markdown tables:
1. MISSING - Game has empty ZoneThisLootIsFrom
2. MISMATCH - Game zone differs from spawn zones (real issues)
3. KNOWN MAPPING - Game uses different name but maps to our zone (not a bug)
4. MATCH - Game zone exactly matches spawn zones
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Known zone name mappings: game_zone -> our_zone
# These are intentional naming differences, not bugs
ZONE_NAME_MAPPINGS: dict[str, str] = {
    # Shortened names in game
    "Duskenlight": "The Duskenlight Coast",
    "Elderstone Mines": "The Elderstone Mines",
    "Jaws": "Jaws of Sivakaya",
    "Krakengard": "Old Krakengard",
    "Loomingwood": "Loomingwood Forest",
    "Silkengrass": "Silkengrass Meadowlands",
    "Willowwatch": "Willowwatch Ridge",
    # Missing apostrophe
    "Malaroth Nesting Grounds": "Malaroth's Nesting Grounds",
    # Extra/missing "The"
    "The Braxonian Desert": "Braxonian Desert",
    "The Island Tomb": "Island Tomb",
    "The Reliquary Hall": "Reliquary Hall",
    "Blight": "The Blight",
    # Portal names - game uses specific names, we use generic "Mysterious Portal"
    "Dusken Portal": "Mysterious Portal",
    "Ripper Portal": "Mysterious Portal",
    "The Fernallan Portal": "Mysterious Portal",
    # Time-based variants map to base zone
    "Blacksalt Strand at night time": "Blacksalt Strand",
    "Vitheo's Watch, at night time": "Vitheo's Watch",
    # Dark variant
    "Dark Azynthi's Garden": "Azynthi's Garden",
}

# Multi-zone values: game_zone -> list of zones that should all be present
MULTI_ZONE_VALUES: dict[str, list[str]] = {
    "Hidden Hills or Stowaway's Step": ["Hidden Hills", "Stowaway's Step"],
}


@dataclass
class KnowledgeEntry:
    """Entry from the game's KnowledgeDatabaseHolder.asset"""

    npc_name: str
    prefab_path: str
    zone: str
    level: int
    is_boss: bool


@dataclass
class SpawnZoneInfo:
    """Spawn zone info from our database"""

    zones: list[str]


def parse_knowledge_database_asset(asset_path: Path) -> list[KnowledgeEntry]:
    """Parse the KnowledgeDatabaseHolder.asset YAML file."""
    content = asset_path.read_text(encoding="utf-8")

    entries = []
    current_entry: dict[str, str | int | bool | None] = {}

    for line in content.split("\n"):
        line = line.rstrip()

        # New entry starts with "  - NPCName:"
        if line.startswith("  - NPCName:"):
            # Save previous entry if exists
            if current_entry and "npc_name" in current_entry:
                entries.append(_create_entry(current_entry))
            current_entry = {"npc_name": line.split("NPCName:")[1].strip()}

        elif line.startswith("    PrefabPath:"):
            current_entry["prefab_path"] = line.split("PrefabPath:")[1].strip()

        elif line.startswith("    ZoneThisLootIsFrom:"):
            zone_value = line.split("ZoneThisLootIsFrom:")[1].strip()
            current_entry["zone"] = zone_value

        elif line.startswith("    Level:"):
            level_str = line.split("Level:")[1].strip()
            current_entry["level"] = int(level_str) if level_str else 0

        elif line.startswith("    IsBoss:"):
            boss_str = line.split("IsBoss:")[1].strip()
            current_entry["is_boss"] = boss_str == "1"

    # Don't forget the last entry
    if current_entry and "npc_name" in current_entry:
        entries.append(_create_entry(current_entry))

    return entries


def _create_entry(data: dict[str, str | int | bool | None]) -> KnowledgeEntry:
    """Create a KnowledgeEntry from parsed data."""
    npc_name = data.get("npc_name")
    prefab_path = data.get("prefab_path")
    zone = data.get("zone")
    level = data.get("level")
    is_boss = data.get("is_boss")

    return KnowledgeEntry(
        npc_name=str(npc_name) if npc_name else "",
        prefab_path=str(prefab_path) if prefab_path else "",
        zone=str(zone) if zone else "",
        level=int(level) if level else 0,
        is_boss=bool(is_boss) if is_boss else False,
    )


def get_spawn_zones(db_path: Path) -> dict[str, SpawnZoneInfo]:
    """Query database for spawn zone info, keyed by lowercase ObjectName."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT
        LOWER(c.object_name) as object_name,
        GROUP_CONCAT(DISTINCT z.zone_name ORDER BY z.zone_name) as zones
    FROM characters c
    LEFT JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
    LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
    WHERE c.object_name IS NOT NULL
    GROUP BY LOWER(c.object_name)
    """

    cursor.execute(query)
    results = {}
    for row in cursor.fetchall():
        object_name, zones_str = row
        zones = zones_str.split(",") if zones_str else []
        results[object_name] = SpawnZoneInfo(zones=zones)

    conn.close()
    return results


def get_boss_prefabs(db_path: Path) -> set[str]:
    """Get set of lowercase ObjectNames for characters with BossXpMultiplier > 1."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT LOWER(object_name)
    FROM characters
    WHERE boss_xp_multiplier > 1 AND object_name IS NOT NULL
    """

    cursor.execute(query)
    results = {row[0] for row in cursor.fetchall()}

    conn.close()
    return results


def extract_prefab_name(prefab_path: str) -> str:
    """Extract prefab name from path like 'NPCs/Brittle Skeelton'."""
    if prefab_path.startswith("NPCs/"):
        return prefab_path[5:]
    return prefab_path


def zones_match_exact(game_zone: str, spawn_zones: list[str]) -> bool:
    """Check if game zone exactly matches any of the spawn zones."""
    if not game_zone or not spawn_zones:
        return False
    return game_zone in spawn_zones


def zones_match_mapped(game_zone: str, spawn_zones: list[str]) -> str | None:
    """Check if game zone maps to any spawn zone via known mappings.

    Returns the mapped zone name if found, None otherwise.
    """
    if not game_zone or not spawn_zones:
        return None

    mapped_zone = ZONE_NAME_MAPPINGS.get(game_zone)
    if mapped_zone and mapped_zone in spawn_zones:
        return mapped_zone

    return None


def zones_match_multi(game_zone: str, spawn_zones: list[str]) -> bool:
    """Check if a multi-zone game value matches spawn zones.

    For values like "Hidden Hills or Stowaway's Step", checks that ALL
    mentioned zones are present in the spawn zones.
    """
    if not game_zone or not spawn_zones:
        return False

    required_zones = MULTI_ZONE_VALUES.get(game_zone)
    if not required_zones:
        return False

    # All required zones must be present in spawn zones
    return all(zone in spawn_zones for zone in required_zones)


def format_markdown_table(entries: list[tuple[KnowledgeEntry, str]], title: str) -> str:
    """Format entries as a fixed-width text table for readability."""
    if not entries:
        return f"## {title}\n\nNo entries.\n"

    # Column widths
    col_npc = 35
    col_prefab = 45
    col_lvl = 3
    col_loottable = 35
    col_spawn = 50

    def truncate(s: str, width: int) -> str:
        if len(s) > width:
            return s[: width - 2] + ".."
        return s

    header = (
        f"{'NPC Name':<{col_npc}} "
        f"{'Prefab Path':<{col_prefab}} "
        f"{'Lvl':>{col_lvl}} "
        f"{'LootTable Zone':<{col_loottable}} "
        f"{'Spawn Zone(s)':<{col_spawn}}"
    )
    separator = "-" * len(header)

    lines = [
        f"## {title}",
        "",
        f"**Count: {len(entries)}**",
        "",
        "```",
        header,
        separator,
    ]

    for entry, spawn_zones_str in entries:
        npc_name = truncate(entry.npc_name or "(empty)", col_npc)
        prefab_path = truncate(entry.prefab_path or "(empty)", col_prefab)
        level = entry.level
        loottable_zone = truncate(entry.zone or "(empty)", col_loottable)
        spawn_zones = truncate(spawn_zones_str or "(none)", col_spawn)

        lines.append(
            f"{npc_name:<{col_npc}} "
            f"{prefab_path:<{col_prefab}} "
            f"{level:>{col_lvl}} "
            f"{loottable_zone:<{col_loottable}} "
            f"{spawn_zones:<{col_spawn}}"
        )

    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def format_mapping_table(mappings_used: dict[str, int]) -> str:
    """Format the zone name mappings table."""
    lines = [
        "## Zone Name Mappings",
        "",
        "These are known naming differences between the game's `ZoneThisLootIsFrom` and our zone names.",
        "Entries using these mappings are considered correct (not mismatches).",
        "",
        "| Game Zone | Our Zone | Count |",
        "|-----------|----------|-------|",
    ]

    for game_zone, our_zone in sorted(ZONE_NAME_MAPPINGS.items()):
        count = mappings_used.get(game_zone, 0)
        if count > 0:
            lines.append(f"| {game_zone} | {our_zone} | {count} |")

    lines.append("")
    return "\n".join(lines)


def main():
    # Paths
    project_root = Path(__file__).parent.parent
    asset_path = project_root / "variants/main/unity/ExportedProject/Assets/MonoBehaviour/KnowledgeDatabaseHolder.asset"
    db_path = project_root / "variants/main/erenshor-main.sqlite"

    if not asset_path.exists():
        print(f"Error: Asset file not found: {asset_path}")
        return 1

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    # Parse game asset
    print(f"Parsing {asset_path}...")
    knowledge_entries = parse_knowledge_database_asset(asset_path)
    print(f"  Found {len(knowledge_entries)} entries")

    # Get spawn zone data
    print(f"Querying {db_path}...")
    spawn_zones_map = get_spawn_zones(db_path)
    print(f"  Found spawn data for {len(spawn_zones_map)} characters")

    # Get boss prefabs for sorting
    boss_prefabs = get_boss_prefabs(db_path)
    print(f"  Found {len(boss_prefabs)} boss characters")

    # Categorize entries
    missing: list[tuple[KnowledgeEntry, str]] = []
    mismatch: list[tuple[KnowledgeEntry, str]] = []
    match: list[tuple[KnowledgeEntry, str]] = []
    unverifiable: list[tuple[KnowledgeEntry, str]] = []

    mappings_used: dict[str, int] = {}

    for entry in knowledge_entries:
        prefab_name = extract_prefab_name(entry.prefab_path)
        prefab_name_lower = prefab_name.lower()

        spawn_info = spawn_zones_map.get(prefab_name_lower)
        spawn_zones_str = ", ".join(spawn_info.zones) if spawn_info else ""
        spawn_zones_list = spawn_info.zones if spawn_info else []

        if not entry.zone:
            # Missing zone in game data
            missing.append((entry, spawn_zones_str))
        elif not spawn_info or not spawn_zones_list:
            # No spawn data to verify against
            unverifiable.append((entry, spawn_zones_str))
        elif zones_match_exact(entry.zone, spawn_zones_list):
            # Exact match
            match.append((entry, spawn_zones_str))
        elif zones_match_multi(entry.zone, spawn_zones_list):
            # Multi-zone value matches (e.g., "Hidden Hills or Stowaway's Step")
            match.append((entry, spawn_zones_str))
        elif zones_match_mapped(entry.zone, spawn_zones_list):
            # Known mapping match
            match.append((entry, spawn_zones_str))
            mappings_used[entry.zone] = mappings_used.get(entry.zone, 0) + 1
        else:
            # Real mismatch - game says X, spawns say Y
            mismatch.append((entry, spawn_zones_str))

    # Sort each category: bosses first, then by NPC name, then prefab path
    def sort_key(item: tuple[KnowledgeEntry, str]) -> tuple[int, str, str]:
        entry = item[0]
        prefab_name = extract_prefab_name(entry.prefab_path).lower()
        is_boss = prefab_name in boss_prefabs
        # 0 for bosses (first), 1 for non-bosses
        return (0 if is_boss else 1, entry.npc_name.lower(), entry.prefab_path.lower())

    for lst in [missing, mismatch, match, unverifiable]:
        lst.sort(key=sort_key)

    # Generate report
    report_lines = [
        "# Zone Discrepancy Report",
        "",
        "Comparison of game's `ZoneThisLootIsFrom` data against spawn-point-inferred zones.",
        "",
        f"- **Missing**: {len(missing)} entries with empty LootTable zone",
        f"- **Mismatch**: {len(mismatch)} entries where zones don't match (potential bugs)",
        f"- **Match**: {len(match)} entries where zones match",
        f"- **Unverifiable**: {len(unverifiable)} entries with no spawn data to verify",
        "",
    ]

    report_lines.append(format_markdown_table(missing, "Missing Zone Data"))
    report_lines.append(format_markdown_table(mismatch, "Zone Mismatch (Potential Bugs)"))
    report_lines.append(format_mapping_table(mappings_used))
    report_lines.append(format_markdown_table(match, "Zone Match"))
    report_lines.append(format_markdown_table(unverifiable, "Unverifiable (No Spawn Data)"))

    report = "\n".join(report_lines)

    # Output
    output_path = project_root / "scripts/zone_discrepancy_report.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {output_path}")

    # Also print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Missing:      {len(missing):>4} entries with empty LootTable zone")
    print(f"Mismatch:     {len(mismatch):>4} entries where zones don't match (potential bugs)")
    print(f"Match:        {len(match):>4} entries where zones match")
    print(f"Unverifiable: {len(unverifiable):>4} entries with no spawn data to verify")

    return 0


if __name__ == "__main__":
    exit(main())
