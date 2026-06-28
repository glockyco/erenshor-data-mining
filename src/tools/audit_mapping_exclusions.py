#!/usr/bin/env python3
"""Audit mapping.json exclusions for false positives.

Iterates all character rules with is_wiki_generated=0 / is_map_visible=0
and reports content evidence (loot, dialog, vendor items, spawns,
treasure_chest) per stable_key. Characters with content that are
currently excluded are potential false positives — they may belong on
the wiki even if they lack a spawn (map visibility is a separate
question).

Usage:
    uv run python src/tools/audit_mapping_exclusions.py [--variant playtest]
    uv run python src/tools/audit_mapping_exclusions.py --json
    uv run python src/tools/audit_mapping_exclusions.py --only-content
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ExclusionEvidence(TypedDict):
    stable_key: str
    display_name: str
    is_wiki_generated: int
    is_map_visible: int
    is_npc: int | None
    has_stats: int | None
    has_dialog: int | None
    is_vendor: int | None
    treasure_chest: int | None
    is_prefab: int | None
    loot_count: int
    vendor_count: int
    spawn_count: int
    all_spawns_disabled: bool
    mapping_display_name: str | None
    mapping_reason: str | None


class MappingRule(TypedDict, total=False):
    display_name: str
    wiki_page_name: str | None
    image_name: str
    is_wiki_generated: int
    is_map_visible: int
    mapping_type: str
    reason: str | None


def find_clean_db(variant: str) -> Path:
    return REPO_ROOT / "variants" / variant / f"erenshor-{variant}.sqlite"


def load_excluded_rules() -> dict[str, MappingRule]:
    """Return character rules where both wiki and map are off."""
    mapping_path = REPO_ROOT / "mapping.json"
    if not mapping_path.exists():
        return {}
    with mapping_path.open() as f:
        data = json.load(f)
    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("mapping.json 'rules' must be an object")
    return {
        k: v
        for k, v in rules.items()
        if k.startswith("character:") and v.get("is_wiki_generated") == 0 and v.get("is_map_visible") == 0
    }


def query_evidence(
    db: sqlite3.Connection,
    excluded_keys: list[str],
) -> list[ExclusionEvidence]:
    """For each excluded character, gather content evidence from the clean DB."""
    if not excluded_keys:
        return []
    placeholders = ",".join("?" * len(excluded_keys))
    rows = db.execute(
        f"""
        SELECT
            c.stable_key,
            c.display_name,
            c.is_npc,
            c.has_stats,
            c.has_dialog,
            c.is_vendor,
            c.treasure_chest,
            c.is_prefab,
            (SELECT COUNT(*) FROM loot_drops ld
             WHERE ld.character_stable_key = c.stable_key) AS loot_count,
            (SELECT COUNT(*) FROM character_vendor_items cvi
             WHERE cvi.character_stable_key = c.stable_key) AS vendor_count,
            (SELECT COUNT(*) FROM character_spawns cs
             WHERE cs.character_stable_key = c.stable_key) AS spawn_count,
            (SELECT COUNT(CASE WHEN cs.is_enabled = 0 THEN 1 END)
             FROM character_spawns cs
             WHERE cs.character_stable_key = c.stable_key) AS disabled_spawn_count
        FROM characters c
        WHERE c.stable_key IN ({placeholders})
        ORDER BY c.display_name, c.stable_key
        """,
        excluded_keys,
    ).fetchall()

    result: list[ExclusionEvidence] = []
    for r in rows:
        spawn_count = r["spawn_count"] or 0
        disabled_count = r["disabled_spawn_count"] or 0
        result.append(
            {
                "stable_key": r["stable_key"],
                "display_name": r["display_name"],
                "is_wiki_generated": 0,
                "is_map_visible": 0,
                "is_npc": r["is_npc"],
                "has_stats": r["has_stats"],
                "has_dialog": r["has_dialog"],
                "is_vendor": r["is_vendor"],
                "treasure_chest": r["treasure_chest"],
                "is_prefab": r["is_prefab"],
                "loot_count": r["loot_count"] or 0,
                "vendor_count": r["vendor_count"] or 0,
                "spawn_count": spawn_count,
                "all_spawns_disabled": spawn_count > 0 and disabled_count == spawn_count,
                "mapping_display_name": None,
                "mapping_reason": None,
            }
        )
    return result


def enrich_with_mapping(
    evidence: list[ExclusionEvidence],
    excluded_rules: dict[str, MappingRule],
) -> list[ExclusionEvidence]:
    for e in evidence:
        rule = excluded_rules.get(e["stable_key"])
        if rule:
            e["mapping_display_name"] = rule.get("display_name")
            e["mapping_reason"] = rule.get("reason")
    return evidence


def has_content(e: ExclusionEvidence) -> bool:
    return e["loot_count"] > 0 or e["vendor_count"] > 0 or bool(e["has_dialog"]) or e["spawn_count"] > 0


def is_intentional_exclusion(e: ExclusionEvidence) -> bool:
    """Heuristic for exclusions that are likely intentional.

    Pocket vendors/banks/auctions, training dummies, and receptacles are
    placed in the world but disabled — they're UI conveniences, not
    world encounters. This is a heuristic, not a definitive classification;
    each row still needs human review before changing mapping flags.
    """
    name = e["display_name"].lower()
    sk = e["stable_key"].lower()
    is_pocket = "pocket" in name or "a rift" in sk or "a bank rift" in sk
    is_training = "training dummy" in name
    is_receptacle = "receptacle" in name
    is_flame_well = "flame well" in name
    return is_pocket or is_training or is_receptacle or is_flame_well


def _format_flags(e: ExclusionEvidence) -> str:
    flags: list[str] = []
    if e["loot_count"] > 0:
        flags.append(f"loot={e['loot_count']}")
    if e["vendor_count"] > 0:
        flags.append(f"vendor={e['vendor_count']}")
    if e["has_dialog"]:
        flags.append("dialog")
    if e["spawn_count"] > 0:
        flags.append(f"spawns={e['spawn_count']}")
        if e["all_spawns_disabled"]:
            flags.append("ALL_DISABLED")
    if e["treasure_chest"]:
        flags.append("treasure_chest")
    if e["is_prefab"]:
        flags.append("prefab")
    return ", ".join(flags)


def print_report(
    evidence: list[ExclusionEvidence],
    missing_from_db: list[tuple[str, str | None]],
) -> None:
    with_content = [e for e in evidence if has_content(e)]
    no_content = [e for e in evidence if not has_content(e)]

    print(f"{'=' * 70}")
    print("MAPPING EXCLUSION AUDIT")
    print(f"{'=' * 70}")
    print(f"Total excluded rules in mapping.json: {len(evidence) + len(missing_from_db)}")
    print(f"  Found in DB:                    {len(evidence)}")
    print(f"    With content (review needed):   {len(with_content)}")
    print(f"    No content (likely safe):       {len(no_content)}")
    print(f"  Missing from DB (stale rules):   {len(missing_from_db)}")
    print()

    if missing_from_db:
        print(f"--- Missing from DB / stale rules ({len(missing_from_db)}) ---")
        for sk, display_name in missing_from_db:
            print(f"  {display_name or '?':40s} | {sk}")
        print()

    if with_content:
        intentional = [e for e in with_content if is_intentional_exclusion(e)]
        needs_review = [e for e in with_content if not is_intentional_exclusion(e)]

        if needs_review:
            print(f"--- High-risk false positives ({len(needs_review)}) ---")
            for e in needs_review:
                print(f"  {e['display_name']:40s} | {e['stable_key']}")
                print(f"    {_format_flags(e)}")
            print()

        if intentional:
            print(f"--- Likely intentional exclusions ({len(intentional)}) ---")
            for e in intentional:
                print(f"  {e['display_name']:40s} | {e['stable_key']}")
                print(f"    {_format_flags(e)}")
            print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="playtest")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--only-content",
        action="store_true",
        help="Only show excluded characters with content (potential false positives)",
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

    excluded_rules = load_excluded_rules()
    excluded_keys = sorted(excluded_rules.keys())

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    evidence = query_evidence(db, excluded_keys)
    evidence = enrich_with_mapping(evidence, excluded_rules)

    db.close()

    # Detect stale rules: keys in mapping.json but not in the DB
    found_keys = {e["stable_key"] for e in evidence}
    missing_from_db = [(sk, excluded_rules[sk].get("display_name")) for sk in excluded_keys if sk not in found_keys]

    if args.only_content:
        evidence = [e for e in evidence if has_content(e)]

    if args.json:
        print(
            json.dumps(
                {
                    "excluded_in_db": evidence,
                    "missing_from_db": [{"stable_key": sk, "display_name": dn} for sk, dn in missing_from_db],
                    "summary": {
                        "total_rules": len(excluded_keys),
                        "found_in_db": len(evidence),
                        "missing_from_db": len(missing_from_db),
                        "with_content": sum(1 for e in evidence if has_content(e)),
                    },
                },
                indent=2,
                default=str,
            )
        )
    else:
        print_report(evidence, missing_from_db)

    return 0


if __name__ == "__main__":
    sys.exit(main())
