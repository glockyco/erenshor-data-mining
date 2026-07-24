"""Compare clean databases for two configured Erenshor variants."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def get_build_id(backups_dir: Path) -> str:
    """Return the latest recorded backup build ID for a variant."""
    try:
        if not backups_dir.exists():
            return "Unknown"

        build_dirs = sorted(backups_dir.glob("backup-*"), reverse=True)
        if build_dirs:
            return build_dirs[0].name.removeprefix("backup-")

        return "Unknown"
    except OSError:
        return "Unknown"


def _attach_base(connection: sqlite3.Connection, base_db: Path) -> None:
    """Attach the base database without interpolating a filesystem path."""
    connection.execute("ATTACH DATABASE ? AS base", (str(base_db),))


def get_counts(db_path: Path) -> dict[str, int]:
    """Get the entity counts shown in the comparison summary."""
    tables = (
        ("Items", "items"),
        ("Spells", "spells"),
        ("Skills", "skills"),
        ("Characters", "characters"),
        ("Quests", "quests"),
        ("Zones", "zones"),
    )
    with sqlite3.connect(db_path) as connection:
        return {name: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for name, table in tables}


def compare_items(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find items present in the new database but not the base database."""
    with sqlite3.connect(new_db) as connection:
        _attach_base(connection, base_db)
        rows = connection.execute(
            """
            SELECT display_name, required_slot, item_level, lore
            FROM items
            WHERE resource_name NOT IN (SELECT resource_name FROM base.items)
            ORDER BY required_slot, item_level, display_name
            """
        ).fetchall()

    results = []
    for name, slot, level, lore in rows:
        results.append(
            {
                "name": name,
                "slot": slot,
                "level": level,
                "lore": " ".join(lore.split()) if lore else lore,
            }
        )
    return results


def compare_spells(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find spells present in the new database but not the base database."""
    with sqlite3.connect(new_db) as connection:
        _attach_base(connection, base_db)
        rows = connection.execute(
            """
            SELECT display_name, type, spell_desc
            FROM spells
            WHERE resource_name NOT IN (SELECT resource_name FROM base.spells)
            ORDER BY type, display_name
            """
        ).fetchall()

    results = []
    for name, spell_type, desc in rows:
        results.append(
            {
                "name": name,
                "type": spell_type,
                "desc": " ".join(desc.split()) if desc else desc,
            }
        )
    return results


def compare_characters(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find characters present in the new database but not the base database."""
    with sqlite3.connect(new_db) as connection:
        _attach_base(connection, base_db)
        rows = connection.execute(
            """
            SELECT
                ch.display_name,
                ch.level,
                ch.is_npc,
                ch.is_vendor,
                ch.effective_hp,
                ch.stable_key,
                z.zone_name
            FROM characters ch
            LEFT JOIN character_spawns cs ON cs.character_stable_key = ch.stable_key
            LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
            WHERE ch.object_name NOT IN (SELECT object_name FROM base.characters)
            GROUP BY ch.stable_key
            ORDER BY ch.is_npc DESC, ch.level, ch.display_name
            """
        ).fetchall()

    return [
        {
            "name": row[0],
            "level": row[1],
            "is_npc": bool(row[2]),
            "is_vendor": bool(row[3]),
            "hp": row[4],
            "zone": row[6],
        }
        for row in rows
    ]


def compare_quests(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find quests present in the new database but not the base database."""
    with sqlite3.connect(new_db) as connection:
        _attach_base(connection, base_db)
        rows = connection.execute(
            """
            SELECT
                qv.quest_name,
                qv.xp_on_complete,
                qv.gold_on_complete,
                SUBSTR(qv.quest_desc, 1, 150) AS desc_preview
            FROM quests q
            LEFT JOIN quest_variants qv ON qv.quest_stable_key = q.stable_key
            WHERE q.db_name NOT IN (SELECT db_name FROM base.quests)
            ORDER BY qv.quest_name
            """
        ).fetchall()

    return [
        {
            "name": row[0],
            "xp": row[1],
            "gold": row[2],
            "desc": " ".join(row[3].split()) if row[3] else row[3],
        }
        for row in rows
    ]


def compare_zones(base_db: Path, new_db: Path) -> list[dict[str, Any]]:
    """Find zones present in the new database but not the base database."""
    with sqlite3.connect(new_db) as connection:
        _attach_base(connection, base_db)
        rows = connection.execute(
            """
            SELECT zone_name, scene_name
            FROM zones
            WHERE scene_name NOT IN (SELECT scene_name FROM base.zones)
            ORDER BY zone_name
            """
        ).fetchall()

    return [{"name": row[0], "scene": row[1]} for row in rows]


def format_items_section(items: list[dict[str, Any]]) -> str:
    """Format the items section of a comparison report."""
    if not items:
        return "_No new items found._\n"

    output = []
    for item in sorted(items, key=lambda value: (-(value["level"] or 0), value["name"])):
        slot = item["slot"] or "General"
        level = item["level"] or 0
        lore = item["lore"] or "No description"
        output.append(f'- **{item["name"]}** ({slot}, Level {level}) - "{lore}"\n')
    output.append("\n")
    return "".join(output)


def format_spells_section(spells: list[dict[str, Any]]) -> str:
    """Format the spells section of a comparison report."""
    if not spells:
        return "_No new spells found._\n"

    output = []
    for spell in sorted(spells, key=lambda value: value["name"]):
        spell_type = spell["type"] or "Other"
        desc = spell["desc"] or "No description"
        output.append(f'- **{spell["name"]}** ({spell_type}) - "{desc}"\n')
    output.append("\n")
    return "".join(output)


def format_characters_section(characters: list[dict[str, Any]]) -> str:
    """Format the characters section of a comparison report."""
    if not characters:
        return "_No new characters found._\n"

    output = []
    for character in sorted(characters, key=lambda value: (-(value["level"] or 0), value["name"])):
        hp_str = f"{character['hp']:,}" if character["hp"] else "Unknown"
        vendor_str = " [Vendor]" if character["is_vendor"] else ""
        zone_str = f" - {character['zone']}" if character.get("zone") else ""
        output.append(f"- **{character['name']}** (Level {character['level']}, {hp_str} HP){vendor_str}{zone_str}\n")
    output.append("\n")
    return "".join(output)


def format_quests_section(quests: list[dict[str, Any]]) -> str:
    """Format the quests section of a comparison report."""
    if not quests:
        return "_No new quests found._\n"

    output = []
    for quest in sorted(quests, key=lambda value: value["name"]):
        gold_str = f", {quest['gold']} Gold" if quest["gold"] > 0 else ""
        output.append(f"- **{quest['name']}** ({quest['xp']:,} XP{gold_str}) - {quest['desc']}...\n")
    output.append("\n")
    return "".join(output)


def format_zones_section(zones: list[dict[str, Any]]) -> str:
    """Format the zones section of a comparison report."""
    if not zones:
        return "_No new zones found._\n"

    output = []
    for zone in sorted(zones, key=lambda value: value["name"]):
        output.append(f"- **{zone['name']}** (Scene: {zone['scene']})\n")
    output.append("\n")
    return "".join(output)


def generate_report(
    base_variant: str,
    new_variant: str,
    base_db: Path,
    new_db: Path,
    base_build: str,
    new_build: str,
    *,
    output_path: Path | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Generate and optionally write a complete variant comparison report."""
    base_counts = get_counts(base_db)
    new_counts = get_counts(new_db)
    new_items = compare_items(base_db, new_db)
    new_spells = compare_spells(base_db, new_db)
    new_characters = compare_characters(base_db, new_db)
    new_quests = compare_quests(base_db, new_db)
    new_zones = compare_zones(base_db, new_db)

    report = [
        f"# Erenshor: {new_variant.title()} vs {base_variant.title()} Comparison\n",
        f"\n**Generated**: {(generated_at or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**Old Variant**: {base_variant} (Build {base_build})\n",
        f"**New Variant**: {new_variant} (Build {new_build})\n",
        "\n---\n\n",
        "## Summary Statistics\n\n",
        "| Category | Old Count | New Count | Difference |\n",
        "|----------|-----------|-----------|------------|\n",
    ]

    for category in ("Zones", "Items", "Spells", "Characters", "Quests", "Skills"):
        base_count = base_counts[category]
        new_count = new_counts[category]
        difference = new_count - base_count
        sign = "+" if difference > 0 else ""
        report.append(f"| {category} | {base_count:,} | {new_count:,} | {sign}{difference} |\n")

    report.extend(("\n---\n\n",))
    if new_zones:
        report.extend((f"## New Zones ({len(new_zones)})\n\n", format_zones_section(new_zones), "---\n\n"))
    if new_items:
        report.extend((f"## New Items ({len(new_items)})\n\n", format_items_section(new_items), "---\n\n"))
    if new_spells:
        report.extend((f"## New Spells ({len(new_spells)})\n\n", format_spells_section(new_spells), "---\n\n"))
    if new_characters:
        report.extend(
            (
                f"## New Characters/NPCs ({len(new_characters)})\n\n",
                format_characters_section(new_characters),
                "---\n\n",
            )
        )
    if new_quests:
        report.extend((f"## New Quests ({len(new_quests)})\n\n", format_quests_section(new_quests), "---\n\n"))

    report_text = "".join(report)
    if output_path is not None:
        output_path.write_text(report_text, encoding="utf-8")
    return report_text
