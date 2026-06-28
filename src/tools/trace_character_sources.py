#!/usr/bin/env python3
"""Trace character prefab sources through scene and prefab YAML.

For each character, reads the prefab GUID from the clean DB's
characters.guid column and searches for it across scene (.unity)
and prefab (.prefab) files. Scene hits mean the character is directly
placed in the world. Prefab hits mean it's nested inside another
prefab (which itself may be script-instantiated). No hits means the
character is dead/unused content.

C# scripts do not contain prefab GUIDs — script-instantiation evidence
comes from the dynamic spawn catalog (allowed fields) and the
DynamicCharacterSpawns/CharacterChainedSpawns tables.

Usage:
    uv run python src/tools/trace_character_sources.py [--variant playtest]
    uv run python src/tools/trace_character_sources.py --stable-key character:faith
    uv run python src/tools/trace_character_sources.py --only-excluded
    uv run python src/tools/trace_character_sources.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TraceResult(TypedDict):
    stable_key: str
    display_name: str
    guid: str | None
    scene_refs: list[str]
    prefab_refs: list[str]
    has_dynamic_spawn: bool
    has_chained_spawn: bool
    verdict: str
    is_excluded: bool
    loot_count: int
    has_dialog: bool
    vendor_count: int
    spawn_count: int
    all_spawns_disabled: bool


class MappingRule(TypedDict, total=False):
    display_name: str
    is_wiki_generated: int
    is_map_visible: int


def find_clean_db(variant: str) -> Path:
    return REPO_ROOT / "variants" / variant / f"erenshor-{variant}.sqlite"


def find_unity_assets(variant: str) -> Path:
    return REPO_ROOT / "variants" / variant / "unity" / "ExportedProject" / "Assets"


def load_excluded_rules() -> dict[str, MappingRule]:
    mapping_path = REPO_ROOT / "mapping.json"
    if not mapping_path.exists():
        return {}
    with mapping_path.open() as f:
        data = json.load(f)
    rules = data.get("rules", {})
    return {
        k: v
        for k, v in rules.items()
        if k.startswith("character:") and v.get("is_wiki_generated") == 0 and v.get("is_map_visible") == 0
    }


def query_characters(
    db: sqlite3.Connection,
    stable_keys: list[str] | None,
) -> list[dict[str, object]]:
    """Fetch character rows with content and spawn info."""
    if stable_keys:
        placeholders = ",".join("?" * len(stable_keys))
        sql = f"""
            SELECT c.stable_key, c.display_name, c.guid, c.is_prefab,
                   c.has_dialog,
                   (SELECT COUNT(*) FROM loot_drops ld
                    WHERE ld.character_stable_key = c.stable_key) AS loot_count,
                   (SELECT COUNT(*) FROM character_vendor_items cvi
                    WHERE cvi.character_stable_key = c.stable_key) AS vendor_count,
                   (SELECT COUNT(*) FROM character_spawns cs
                    WHERE cs.character_stable_key = c.stable_key) AS spawn_count,
                   (SELECT COUNT(CASE WHEN cs.is_enabled = 0 THEN 1 END)
                    FROM character_spawns cs
                    WHERE cs.character_stable_key = c.stable_key) AS disabled_count
            FROM characters c
            WHERE c.stable_key IN ({placeholders})
            ORDER BY c.display_name, c.stable_key
        """
        rows = db.execute(sql, tuple(stable_keys)).fetchall()
    else:
        sql = """
            SELECT c.stable_key, c.display_name, c.guid, c.is_prefab,
                   c.has_dialog,
                   (SELECT COUNT(*) FROM loot_drops ld
                    WHERE ld.character_stable_key = c.stable_key) AS loot_count,
                   (SELECT COUNT(*) FROM character_vendor_items cvi
                    WHERE cvi.character_stable_key = c.stable_key) AS vendor_count,
                   (SELECT COUNT(*) FROM character_spawns cs
                    WHERE cs.character_stable_key = c.stable_key) AS spawn_count,
                   (SELECT COUNT(CASE WHEN cs.is_enabled = 0 THEN 1 END)
                    FROM character_spawns cs
                    WHERE cs.character_stable_key = c.stable_key) AS disabled_count
            FROM characters c
            ORDER BY c.display_name, c.stable_key
        """
        rows = db.execute(sql).fetchall()
    return [dict(r) for r in rows]


def check_spawn_tables(db: sqlite3.Connection, stable_key: str) -> tuple[bool, bool]:
    """Check if character has a dynamic spawn or chained spawn record."""
    dyn = db.execute(
        "SELECT 1 FROM character_spawns WHERE character_stable_key = ? AND source_script IS NOT NULL LIMIT 1",
        (stable_key,),
    ).fetchone()
    chained = db.execute(
        """SELECT 1 FROM character_chained_spawns
           WHERE parent_stable_key = ? OR child_stable_key = ? LIMIT 1""",
        (stable_key, stable_key),
    ).fetchone()
    return bool(dyn), bool(chained)


def build_guid_index(
    guids: set[str],
    assets_dir: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Walk scene and prefab files once, recording which GUIDs appear where.

    Returns (scene_guid_map, prefab_guid_map) where each maps
    guid -> list of file basenames.
    """
    scene_map: dict[str, list[str]] = {g: [] for g in guids}
    prefab_map: dict[str, list[str]] = {g: [] for g in guids}
    guid_set = guids

    # Walk scenes
    scenes_dir = assets_dir / "Scenes"
    if scenes_dir.exists():
        for f in scenes_dir.glob("*.unity"):
            try:
                content = f.read_text()
            except OSError:
                continue
            for g in guid_set:
                if g in content:
                    scene_map[g].append(f.name)

    # Walk prefabs
    prefabs_dir = assets_dir / "Resources"
    if prefabs_dir.exists():
        for f in prefabs_dir.rglob("*.prefab"):
            try:
                content = f.read_text()
            except OSError:
                continue
            for g in guid_set:
                if g in content:
                    prefab_map[g].append(f.name)

    return scene_map, prefab_map


def trace_character(
    row: dict[str, object],
    has_dynamic: bool,
    has_chained: bool,
    is_excluded: bool,
    scene_map: dict[str, list[str]],
    prefab_map: dict[str, list[str]],
) -> TraceResult:
    guid = row.get("guid")
    guid_str = str(guid) if guid else None
    sp_raw = row.get("spawn_count")
    dis_raw = row.get("disabled_count")
    spawn_count = int(sp_raw) if isinstance(sp_raw, int) else 0
    disabled_count = int(dis_raw) if isinstance(dis_raw, int) else 0

    scene_refs: list[str] = scene_map.get(guid_str, []) if guid_str else []
    prefab_refs: list[str] = prefab_map.get(guid_str, []) if guid_str else []

    # Determine verdict
    if spawn_count > 0 and disabled_count == spawn_count:
        verdict = "initially_disabled_spawns"
    elif spawn_count > 0:
        verdict = "has_enabled_spawns"
    elif scene_refs:
        verdict = "scene_serialized_reference"
    elif has_dynamic or has_chained:
        verdict = "script_spawned"
    elif prefab_refs:
        verdict = "serialized_reference"
    elif guid:
        verdict = "dead"
    else:
        verdict = "no_guid"

    loot_raw = row.get("loot_count")
    vend_raw = row.get("vendor_count")

    return TraceResult(
        stable_key=str(row["stable_key"]),
        display_name=str(row["display_name"]),
        guid=str(guid) if guid else None,
        scene_refs=scene_refs,
        prefab_refs=prefab_refs,
        has_dynamic_spawn=has_dynamic,
        has_chained_spawn=has_chained,
        verdict=verdict,
        is_excluded=is_excluded,
        loot_count=int(loot_raw) if isinstance(loot_raw, int) else 0,
        has_dialog=bool(row.get("has_dialog")),
        vendor_count=int(vend_raw) if isinstance(vend_raw, int) else 0,
        spawn_count=spawn_count,
        all_spawns_disabled=spawn_count > 0 and disabled_count == spawn_count,
    )


def print_results(results: list[TraceResult]) -> None:
    by_verdict: dict[str, list[TraceResult]] = {}
    for r in results:
        by_verdict.setdefault(r["verdict"], []).append(r)

    print(f"{'=' * 70}")
    print("CHARACTER SOURCE TRACING")
    print(f"{'=' * 70}")
    print(f"Total characters traced: {len(results)}")
    print()

    # Order: most interesting first
    verdict_order = [
        "scene_serialized_reference",
        "has_enabled_spawns",
        "script_spawned",
        "serialized_reference",
        "initially_disabled_spawns",
        "dead",
        "no_guid",
    ]

    for verdict in verdict_order:
        items = by_verdict.get(verdict, [])
        if not items:
            continue
        print(f"--- {verdict} ({len(items)}) ---")
        for r in items:
            content_flags: list[str] = []
            if r["loot_count"] > 0:
                content_flags.append(f"loot={r['loot_count']}")
            if r["has_dialog"]:
                content_flags.append("dialog")
            if r["vendor_count"] > 0:
                content_flags.append(f"vendor={r['vendor_count']}")
            flag_str = ", ".join(content_flags) if content_flags else "no content"

            print(f"  {r['display_name']:40s} | {r['stable_key']}")
            print(f"    {flag_str} | excluded={'yes' if r['is_excluded'] else 'no'}")
            if r["scene_refs"]:
                print(f"    scenes: {r['scene_refs'][:5]}")
            if r["prefab_refs"]:
                print(f"    nested in prefabs: {r['prefab_refs'][:3]}")
            if r["has_dynamic_spawn"]:
                print("    dynamic spawn: yes")
            if r["has_chained_spawn"]:
                print("    chained spawn: yes")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="playtest")
    parser.add_argument("--stable-key", help="Trace a single character")
    parser.add_argument("--only-excluded", action="store_true")
    parser.add_argument(
        "--verdict",
        help="Only show characters with this verdict (e.g. has_enabled_spawns, dead)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    db_path = find_clean_db(args.variant)
    if not db_path.exists():
        print(f"Error: clean DB not found: {db_path}", file=sys.stderr)
        return 1

    assets_dir = find_unity_assets(args.variant)
    if not assets_dir.exists():
        print(f"Error: Unity assets not found: {assets_dir}", file=sys.stderr)
        return 1

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    excluded_rules = load_excluded_rules()

    if args.stable_key:
        chars = query_characters(db, [args.stable_key])
    elif args.only_excluded:
        chars = query_characters(db, sorted(excluded_rules.keys()))
    else:
        chars = query_characters(db, None)

    # Collect all GUIDs for one-pass indexing
    all_guids: set[str] = set()
    for row in chars:
        g = row.get("guid")
        if g:
            all_guids.add(str(g))

    print(f"Building GUID index for {len(all_guids)} GUIDs...", file=sys.stderr)
    scene_map, prefab_map = build_guid_index(all_guids, assets_dir)
    print("Index complete.", file=sys.stderr)

    results: list[TraceResult] = []
    for i, row in enumerate(chars):
        sk = str(row["stable_key"])
        has_dyn, has_chained = check_spawn_tables(db, sk)
        result = trace_character(
            row,
            has_dyn,
            has_chained,
            sk in excluded_rules,
            scene_map,
            prefab_map,
        )
        results.append(result)
        if (i + 1) % 50 == 0:
            print(f"  ...traced {i + 1}/{len(chars)}", file=sys.stderr)

    db.close()

    if args.verdict:
        results = [r for r in results if r["verdict"] == args.verdict]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_results(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
