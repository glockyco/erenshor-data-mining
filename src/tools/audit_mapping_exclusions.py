#!/usr/bin/env python3
"""Audit mapping.json exclusions and the chat knowledge base for false positives.

Iterates all character rules with is_wiki_generated=0 / is_map_visible=0
and reports content evidence (loot, dialog, vendor items, spawns,
treasure_chest) per stable_key. Characters with content that are
currently excluded are potential false positives — they may belong on
the wiki even if they lack a spawn (map visibility is a separate
question).

It also lists each excluded prefab without a spawn whose object name a
placed character carries under another name. A built scene keeps no link
to the prefab of a placed character, so such a prefab can look unused
while the game places a renamed copy of it.

Usage:
    uv run python src/tools/audit_mapping_exclusions.py [--variant playtest]
    uv run python src/tools/audit_mapping_exclusions.py --json
    uv run python src/tools/audit_mapping_exclusions.py --only-content

The chat sections compare the knowledge base of simulated-player chat with
the characters. They list each name that chat says without being asked and
that no wiki-visible character carries, what chat says about each unused
page of content-lifecycle.json, and the entries that disagree with the
current game data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from erenshor.application.wiki.chat_knowledge import ChatKnowledge, load_chat_knowledge, normalize_chat_name
from erenshor.application.wiki.lifecycle import ContentLifecycle, load_content_lifecycle

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


class RenamedCopy(TypedDict):
    prefab_stable_key: str
    prefab_name: str
    object_name: str
    stable_key: str
    name: str
    scene: str | None
    is_wiki_generated: int


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


def find_renamed_copies(db: sqlite3.Connection, excluded_keys: list[str]) -> list[RenamedCopy]:
    """List placed characters that share the object name of an excluded, unspawned prefab under another name."""
    if not excluded_keys:
        return []
    placeholders = ",".join("?" * len(excluded_keys))
    rows = db.execute(
        f"""
        SELECT
            prefab.stable_key AS prefab_stable_key,
            prefab.npc_name AS prefab_name,
            prefab.object_name,
            placed.stable_key,
            placed.npc_name AS name,
            placed.scene,
            placed.is_wiki_generated
        FROM characters prefab
        JOIN characters placed
            ON placed.object_name = prefab.object_name
            AND placed.is_prefab = 0
            AND placed.npc_name IS NOT prefab.npc_name
        WHERE prefab.stable_key IN ({placeholders})
            AND prefab.is_prefab = 1
            AND NOT EXISTS (
                SELECT 1 FROM character_spawns cs WHERE cs.character_stable_key = prefab.stable_key
            )
        ORDER BY prefab.npc_name, prefab.stable_key, placed.npc_name, placed.stable_key
        """,
        excluded_keys,
    ).fetchall()
    return [
        {
            "prefab_stable_key": r["prefab_stable_key"],
            "prefab_name": r["prefab_name"],
            "object_name": r["object_name"],
            "stable_key": r["stable_key"],
            "name": r["name"],
            "scene": r["scene"],
            "is_wiki_generated": r["is_wiki_generated"],
        }
        for r in rows
    ]


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


class PlacedCopy(TypedDict):
    stable_key: str
    name: str
    scene: str | None


class UnclaimedChatName(TypedDict):
    name: str
    zone: str | None
    level: int
    prefab_keys: list[str]
    placed_copies: list[PlacedCopy]
    lifecycle_state: str | None


def find_unclaimed_chat_names(
    db: sqlite3.Connection, knowledge: ChatKnowledge, lifecycle: ContentLifecycle
) -> list[UnclaimedChatName]:
    """List the names chat says unprompted that no wiki-visible character, rename, or split covers."""
    carried: set[str] = set()
    for npc_name, display_name in db.execute(
        "SELECT npc_name, display_name FROM characters WHERE is_wiki_generated = 1"
    ):
        carried.update(normalize_chat_name(name) for name in (npc_name, display_name) if name)
    recorded = {normalize_chat_name(title) for title in (*lifecycle.renames, *lifecycle.splits)}
    page_states = {normalize_chat_name(title): page.state for title, page in lifecycle.pages.items()}
    object_names = dict(db.execute("SELECT stable_key, object_name FROM characters WHERE is_prefab = 1"))
    placed: dict[str, list[PlacedCopy]] = defaultdict(list)
    for stable_key, object_name, npc_name, scene in db.execute(
        "SELECT stable_key, object_name, npc_name, scene FROM characters WHERE is_prefab = 0 ORDER BY stable_key"
    ):
        placed[object_name].append({"stable_key": stable_key, "name": npc_name, "scene": scene})

    result: list[UnclaimedChatName] = []
    for entry in knowledge.entries:
        name = normalize_chat_name(entry.npc_name)
        if not entry.named_unprompted or name in carried or name in recorded:
            continue
        result.append(
            {
                "name": entry.npc_name,
                "zone": entry.zone_name,
                "level": entry.level,
                "prefab_keys": list(entry.character_keys),
                "placed_copies": [
                    copy for key in entry.character_keys for copy in placed.get(object_names.get(key, ""), [])
                ],
                "lifecycle_state": page_states.get(name),
            }
        )
    return result


class ChatMention(TypedDict):
    name: str
    zone: str | None
    unprompted: bool
    items_named_as_source: list[str]


class UnusedPageChat(TypedDict):
    title: str
    stable_key: str | None
    mentions: list[ChatMention]


def describe_unused_pages(knowledge: ChatKnowledge, lifecycle: ContentLifecycle) -> list[UnusedPageChat]:
    """Say for each unused page what chat says about its character."""
    result: list[UnusedPageChat] = []
    for title, page in sorted(lifecycle.pages.items()):
        if page.state != "unused":
            continue
        entries = knowledge.entries_for_character(page.stable_key) if page.stable_key else ()
        result.append(
            {
                "title": title,
                "stable_key": page.stable_key,
                "mentions": [
                    {
                        "name": entry.npc_name,
                        "zone": entry.zone_name,
                        "unprompted": entry.named_unprompted,
                        "items_named_as_source": list(knowledge.items_named_as_source(entry)),
                    }
                    for entry in entries
                ],
            }
        )
    return result


def find_knowledge_drift(db: sqlite3.Connection, knowledge: ChatKnowledge) -> dict[str, list[dict[str, object]]]:
    """List the entries that disagree with the current game data of their characters.

    The zone is hand-written text, so it is not compared.
    """
    prefabs_by_name: dict[str, list[dict[str, object]]] = defaultdict(list)
    boss_xp: dict[str, float] = {}
    for stable_key, object_name, npc_name, level, multiplier in db.execute(
        "SELECT stable_key, object_name, npc_name, level, boss_xp_multiplier FROM characters WHERE is_prefab = 1"
    ):
        prefabs_by_name[npc_name].append({"stable_key": stable_key, "object_name": object_name, "level": level})
        boss_xp[stable_key] = float(multiplier or 0)
    loot: dict[str, set[str]] = defaultdict(set)
    for character_key, item_name in db.execute(
        "SELECT l.character_stable_key, i.item_name FROM loot_drops l JOIN items i ON i.stable_key = l.item_stable_key"
    ):
        loot[character_key].add(item_name)
    world_drops = {
        name
        for (name,) in db.execute(
            "SELECT i.item_name FROM special_world_drops w JOIN items i ON i.stable_key = w.item_stable_key"
        )
    }

    drift: dict[str, list[dict[str, object]]] = {
        "stale_prefab_files": [],
        "missing_drops": [],
        "extra_drops": [],
        "boss_flag": [],
        "prefabs_without_entry": [],
    }
    for entry in knowledge.entries:
        if not entry.character_keys:
            drift["stale_prefab_files"].append(
                {
                    "name": entry.npc_name,
                    "prefab_path": entry.prefab_path,
                    "same_name_prefabs": prefabs_by_name.get(entry.npc_name, []),
                }
            )
            continue
        keys = list(entry.character_keys)
        current = set().union(*(loot[key] for key in keys))
        listed = set(entry.drops)
        missing = sorted(current - world_drops - listed)
        if missing:
            drift["missing_drops"].append({"name": entry.npc_name, "keys": keys, "items": missing})
        extra = sorted(listed - current - world_drops)
        if extra:
            drift["extra_drops"].append({"name": entry.npc_name, "keys": keys, "items": extra})
        # code-fact: character.boss_consider_threshold
        unique = any(boss_xp[key] > 1 for key in keys)
        if entry.is_boss != unique:
            drift["boss_flag"].append({"name": entry.npc_name, "keys": keys, "entry": entry.is_boss, "game": unique})
    for stable_key, npc_name in db.execute(
        "SELECT stable_key, npc_name FROM characters WHERE is_prefab = 1 AND is_wiki_generated = 1 "
        "AND stable_key NOT IN (SELECT character_stable_key FROM knowledge_entry_characters) ORDER BY stable_key"
    ):
        drift["prefabs_without_entry"].append({"stable_key": stable_key, "name": npc_name})
    return drift


def _print_chat_sections(
    unclaimed: list[UnclaimedChatName],
    unused_pages: list[UnusedPageChat],
    drift: dict[str, list[dict[str, object]]],
) -> None:
    print(f"--- Chat names that no wiki-visible character carries ({len(unclaimed)}) ---")
    print("  Chat says these without being asked. Record a rename, a split, or an unused page.")
    for name in unclaimed:
        state = f" | recorded {name['lifecycle_state']} page" if name["lifecycle_state"] else ""
        print(f"  {name['name']:40s} | {name['zone']} | level {name['level']}{state}")
        print(f"    prefabs: {', '.join(name['prefab_keys']) or 'none'}")
        for copy in name["placed_copies"]:
            print(f"    placed as {copy['name']} in {copy['scene'] or '?'} | {copy['stable_key']}")
    print()

    print(f"--- What chat says about unused pages ({len(unused_pages)}) ---")
    for page in unused_pages:
        if not page["mentions"]:
            print(f"  {page['title']:40s} | no knowledge entry")
        for mention in page["mentions"]:
            states = []
            if mention["unprompted"]:
                states.append(f"named without being asked ({mention['zone']})")
            if mention["items_named_as_source"]:
                states.append("named as the source of " + ", ".join(mention["items_named_as_source"]))
            print(f"  {page['title']:40s} | {'; '.join(states) or 'named only when asked'}")
    print()

    print("--- Knowledge base drift (the zone text is not compared) ---")
    labels = {
        "stale_prefab_files": "Entries whose stored prefab file no longer exists",
        "missing_drops": "Entries that lack drops their characters now have",
        "extra_drops": "Entries that list drops their characters no longer give",
        "boss_flag": "Entries whose boss flag differs from BossXp > 1",
        "prefabs_without_entry": "Wiki-visible prefabs without an entry",
    }
    for kind, label in labels.items():
        rows = drift[kind]
        print(f"  {label} ({len(rows)})")
        for row in rows:
            details = {key: value for key, value in row.items() if key != "name"}
            print(f"    {row['name']} | {json.dumps(details, default=str)}")
    print()


def print_report(
    evidence: list[ExclusionEvidence],
    missing_from_db: list[tuple[str, str | None]],
    renamed_copies: list[RenamedCopy],
    chat_sections: tuple[list[UnclaimedChatName], list[UnusedPageChat], dict[str, list[dict[str, object]]]],
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

    if renamed_copies:
        print(f"--- Excluded prefabs placed under another name ({len(renamed_copies)}) ---")
        print("  Record a rename or a split in content-lifecycle.json when a wiki page names the prefab.")
        for copy in renamed_copies:
            visibility = "" if copy["is_wiki_generated"] else " (not on the wiki)"
            print(f"  {copy['prefab_name']:40s} | {copy['prefab_stable_key']}")
            print(f"    placed as {copy['name']} in {copy['scene'] or '?'}{visibility} | {copy['stable_key']}")
        print()

    _print_chat_sections(*chat_sections)


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
    renamed_copies = find_renamed_copies(db, excluded_keys)
    knowledge = load_chat_knowledge(db)
    lifecycle = load_content_lifecycle(REPO_ROOT / "content-lifecycle.json")
    unclaimed = find_unclaimed_chat_names(db, knowledge, lifecycle)
    unused_pages = describe_unused_pages(knowledge, lifecycle)
    drift = find_knowledge_drift(db, knowledge)

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
                    "renamed_copies": renamed_copies,
                    "chat": {"unclaimed_names": unclaimed, "unused_pages": unused_pages, "drift": drift},
                    "summary": {
                        "total_rules": len(excluded_keys),
                        "found_in_db": len(evidence),
                        "missing_from_db": len(missing_from_db),
                        "with_content": sum(1 for e in evidence if has_content(e)),
                        "renamed_copies": len(renamed_copies),
                        "unclaimed_chat_names": len(unclaimed),
                    },
                },
                indent=2,
                default=str,
            )
        )
    else:
        print_report(evidence, missing_from_db, renamed_copies, (unclaimed, unused_pages, drift))

    return 0


if __name__ == "__main__":
    sys.exit(main())
