#!/usr/bin/env python3
"""Audit spawn coverage: find orphan characters after extract build.

Runs the orphan audit SQL from skill://auditing-spawn-coverage against
the clean DB. Orphans are characters with no spawn row, no covering
dedup sibling, and no summoning spell. Each orphan is categorized and
cross-referenced against mapping.json to show which already have
exclusion rules vs which need investigation.

Usage:
    uv run python src/tools/audit_spawn_coverage.py [--variant playtest]
    uv run python src/tools/audit_spawn_coverage.py --json
    uv run python src/tools/audit_spawn_coverage.py --include-disabled
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# TypedDicts for SQLite result rows
# ---------------------------------------------------------------------------


class OrphanRow(TypedDict):
    display_name: str
    stable_key: str
    is_prefab: int | None
    is_npc: int | None
    has_stats: int | None
    has_dialog: int | None
    is_vendor: int | None
    treasure_chest: int | None
    loot_count: int
    vendor_count: int


class DisabledRow(TypedDict):
    stable_key: str
    display_name: str
    scene: str | None
    spawn_count: int
    disabled_count: int
    enabled_count: int


class MappingRule(TypedDict, total=False):
    display_name: str
    wiki_page_name: str | None
    image_name: str
    is_wiki_generated: int
    is_map_visible: int
    mapping_type: str
    reason: str | None


class OrphanWithRule(OrphanRow):
    mapping_rule: MappingRule | None
    is_excluded: bool


# ---------------------------------------------------------------------------
# DB and mapping helpers
# ---------------------------------------------------------------------------


def find_clean_db(variant: str) -> Path:
    return REPO_ROOT / "variants" / variant / f"erenshor-{variant}.sqlite"


def load_mapping_rules() -> dict[str, MappingRule]:
    mapping_path = REPO_ROOT / "mapping.json"
    if not mapping_path.exists():
        return {}
    with mapping_path.open() as f:
        data = json.load(f)
    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("mapping.json 'rules' must be an object")
    return {k: v for k, v in rules.items() if k.startswith("character:")}


def query_orphans(db: sqlite3.Connection) -> list[OrphanRow]:
    """Return true orphans: no spawn, no covering dedup sibling, no spell summon."""
    rows = db.execute(
        """
        WITH no_spawn AS (
          SELECT c.stable_key, c.display_name, c.is_prefab, c.is_npc,
                 c.has_stats, c.has_dialog, c.is_vendor, c.treasure_chest
          FROM characters c
          LEFT JOIN (SELECT DISTINCT character_stable_key FROM character_spawns) s
            ON s.character_stable_key = c.stable_key
          WHERE s.character_stable_key IS NULL
        )
        SELECT ns.display_name, ns.stable_key, ns.is_prefab, ns.is_npc,
               ns.has_stats, ns.has_dialog, ns.is_vendor, ns.treasure_chest,
               (SELECT COUNT(*) FROM loot_drops ld
                WHERE ld.character_stable_key = ns.stable_key) AS loot_count,
               (SELECT COUNT(*) FROM character_vendor_items cvi
                WHERE cvi.character_stable_key = ns.stable_key) AS vendor_count
        FROM no_spawn ns
        LEFT JOIN character_deduplications d ON d.member_stable_key = ns.stable_key
        WHERE (
                d.group_key IS NULL
                OR NOT EXISTS (
                  SELECT 1 FROM character_spawns sp
                  JOIN character_deduplications d2
                    ON d2.member_stable_key = sp.character_stable_key
                  WHERE d2.group_key = d.group_key
                )
              )
          AND NOT EXISTS (
                SELECT 1 FROM spells sp
                WHERE sp.pet_to_summon_stable_key = ns.stable_key
              )
          AND NOT EXISTS (
                SELECT 1 FROM treasure_chest_possible_spawns tcps
                WHERE tcps.chest_character_stable_key = ns.stable_key
              )
        ORDER BY ns.display_name, ns.stable_key
        """
    ).fetchall()
    return [dict(r) for r in rows]  # type: ignore[misc]


def query_disabled(db: sqlite3.Connection) -> list[DisabledRow]:
    """Return characters where ALL spawn rows are disabled (is_enabled=0)."""
    rows = db.execute(
        """
        SELECT c.stable_key, c.display_name, c.scene,
               COUNT(cs.spawn_point_stable_key) AS spawn_count,
               SUM(CASE WHEN cs.is_enabled = 0 THEN 1 ELSE 0 END) AS disabled_count,
               SUM(CASE WHEN cs.is_enabled = 1 THEN 1 ELSE 0 END) AS enabled_count
        FROM characters c
        JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
        GROUP BY c.stable_key, c.display_name, c.scene
        HAVING enabled_count = 0 AND disabled_count > 0
        ORDER BY c.display_name, c.stable_key
        """
    ).fetchall()
    return [dict(r) for r in rows]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------


def categorize_orphans(
    orphans: list[OrphanRow],
    mapping_rules: dict[str, MappingRule],
) -> tuple[dict[str, list[OrphanWithRule]], list[OrphanWithRule]]:
    """Split orphans into categories for reporting."""
    categories: dict[str, list[OrphanWithRule]] = {
        "already_excluded": [],
        "has_loot": [],
        "has_dialog": [],
        "has_vendor_items": [],
        "is_treasure_chest": [],
        "is_prefab_only": [],
        "other": [],
    }
    enriched_orphans: list[OrphanWithRule] = []
    for o in orphans:
        sk = o["stable_key"]
        rule = mapping_rules.get(sk)
        is_excluded = bool(rule and rule.get("is_wiki_generated") == 0 and rule.get("is_map_visible") == 0)
        enriched: OrphanWithRule = {**o, "mapping_rule": rule, "is_excluded": is_excluded}
        enriched_orphans.append(enriched)

        if is_excluded:
            categories["already_excluded"].append(enriched)
        elif o["loot_count"] > 0:
            categories["has_loot"].append(enriched)
        elif o["has_dialog"]:
            categories["has_dialog"].append(enriched)
        elif o["vendor_count"] > 0:
            categories["has_vendor_items"].append(enriched)
        elif o["treasure_chest"]:
            categories["is_treasure_chest"].append(enriched)
        elif o["is_prefab"]:
            categories["is_prefab_only"].append(enriched)
        else:
            categories["other"].append(enriched)
    return categories, enriched_orphans


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    orphans: list[OrphanWithRule],
    disabled: list[DisabledRow],
    categories: dict[str, list[OrphanWithRule]],
) -> None:
    total = len(orphans)
    excluded = len(categories["already_excluded"])
    needs_investigation = total - excluded

    print(f"{'=' * 70}")
    print("SPAWN COVERAGE AUDIT")
    print(f"{'=' * 70}")
    print(f"Total true orphans:          {total}")
    print(f"  Already excluded (mapping): {excluded}")
    print(f"  Needs investigation:        {needs_investigation}")
    print(f"Characters with all spawns disabled: {len(disabled)}")
    print()

    for cat_name, items in categories.items():
        if cat_name == "already_excluded" or not items:
            continue
        print(f"--- {cat_name} ({len(items)}) ---")
        for o in items:
            flags: list[str] = []
            if o["loot_count"] > 0:
                flags.append(f"loot={o['loot_count']}")
            if o["has_dialog"]:
                flags.append("dialog")
            if o["vendor_count"] > 0:
                flags.append(f"vendor={o['vendor_count']}")
            if o["treasure_chest"]:
                flags.append("treasure_chest")
            if o["is_prefab"]:
                flags.append("prefab")
            flag_str = ", ".join(flags) if flags else "no content flags"
            print(f"  {o['display_name']:40s} | {o['stable_key']}")
            print(f"    {flag_str}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="playtest")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Also report characters with all spawns disabled",
    )
    args = parser.parse_args()

    db_path = find_clean_db(args.variant)
    if not db_path.exists():
        print(f"Error: clean DB not found: {db_path}", file=sys.stderr)
        print(
            f"Run 'uv run erenshor -V {args.variant} extract build' first.",
            file=sys.stderr,
        )
        return 1

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    orphans = query_orphans(db)
    disabled = query_disabled(db) if args.include_disabled else []
    mapping_rules = load_mapping_rules()
    categories, enriched_orphans = categorize_orphans(orphans, mapping_rules)

    if args.json:
        print(
            json.dumps(
                {
                    "orphans": orphans,
                    "disabled": disabled,
                    "summary": {
                        "total_orphans": len(orphans),
                        "already_excluded": len(categories["already_excluded"]),
                        "needs_investigation": len(orphans) - len(categories["already_excluded"]),
                        "disabled_count": len(disabled),
                    },
                },
                indent=2,
                default=str,
            )
        )
    else:
        print_report(enriched_orphans, disabled, categories)
        if args.include_disabled and disabled:
            print(f"--- all spawns disabled ({len(disabled)}) ---")
            for d in disabled:
                print(
                    f"  {d['display_name']:40s} | {d['stable_key'][:50]:50s} "
                    f"| spawns={d['spawn_count']} scene={d['scene']}"
                )

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
