"""Quest guide data repository — single-pass data acquisition layer.

Extracts all SQL queries into ``load_quest_data`` which returns a
:class:`QuestDataContext` containing every lookup map the assembler needs.

Key improvement over v2: item obtainability is unified into
``list[ItemSource]`` with inline levels, zone aggregation, and spawn/node
counts.  No parallel factor lists or per-source-type dataclasses.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from .schema import (
    AcquisitionSource,
    ChainGroup,
    CompletionSource,
    FactionEffect,
    ItemSource,
    Prerequisite,
    SpawnPoint,
    ZoneInfo,
    ZoneLine,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data context
# ---------------------------------------------------------------------------


@dataclass
class QuestDataContext:
    """All pre-fetched data needed by the quest guide assembler."""

    quests: list[sqlite3.Row] = field(default_factory=list)
    acquisition: dict[str, list[AcquisitionSource]] = field(default_factory=dict)
    completion: dict[str, list[CompletionSource]] = field(default_factory=dict)
    item_sources: dict[str, list[ItemSource]] = field(default_factory=dict)
    required_items_map: dict[str, list[dict]] = field(default_factory=dict)
    faction_effects: dict[str, list[FactionEffect]] = field(default_factory=dict)
    chain_next: dict[str, str] = field(default_factory=dict)
    chain_prev: dict[str, list[str]] = field(default_factory=dict)
    also_completes: dict[str, list[str]] = field(default_factory=dict)
    completed_by: dict[str, list[str]] = field(default_factory=dict)
    prerequisites: dict[str, list[Prerequisite]] = field(default_factory=dict)
    npc_zones: dict[str, str] = field(default_factory=dict)
    char_name_zones: dict[str, list[str]] = field(default_factory=dict)
    item_names: dict[str, str] = field(default_factory=dict)
    quest_names: dict[str, str] = field(default_factory=dict)
    shout_keywords: dict[str, str] = field(default_factory=dict)
    char_levels: dict[str, int] = field(default_factory=dict)
    zone_lookup: dict[str, ZoneInfo] = field(default_factory=dict)
    zone_by_display: dict[str, ZoneInfo] = field(default_factory=dict)
    character_spawns: dict[str, list[SpawnPoint]] = field(default_factory=dict)
    zone_lines: list[ZoneLine] = field(default_factory=list)
    chain_groups: list[ChainGroup] = field(default_factory=list)
    reward_items: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_quest_data(db_path: Path) -> QuestDataContext:
    """Open *db_path* read-only and return a fully populated context."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return _load(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Internal orchestration
# ---------------------------------------------------------------------------


def _load(conn: sqlite3.Connection) -> QuestDataContext:
    quests = _fetch_quests(conn)
    zone_lookup = _fetch_zone_lookup(conn)
    zone_by_display = {zi.display_name: zi for zi in zone_lookup.values()}

    ctx = QuestDataContext(
        quests=quests,
        acquisition=_fetch_acquisition_sources(conn),
        completion=_fetch_completion_sources(conn),
        required_items_map=_fetch_required_items(conn),
        faction_effects=_fetch_faction_effects(conn),
        chain_next=_fetch_chain_next(conn),
        chain_prev=_fetch_chain_prev(conn),
        also_completes=_fetch_also_completes(conn),
        completed_by=_fetch_completed_by(conn),
        prerequisites=_fetch_prerequisites(conn),
        npc_zones=_fetch_npc_zones(conn),
        char_name_zones=_fetch_char_name_zones(conn),
        item_names=_fetch_item_names(conn),
        quest_names={row["stable_key"]: row["display_name"] for row in quests},
        shout_keywords=_fetch_shout_keywords(conn),
        char_levels=_fetch_char_levels(conn),
        zone_lookup=zone_lookup,
        zone_by_display=zone_by_display,
        character_spawns=_fetch_character_spawns(conn),
        zone_lines=_fetch_zone_lines(conn),
        chain_groups=_compute_chain_groups(conn),
        reward_items=_fetch_reward_items(conn),
        item_sources=_build_item_sources(conn, zone_by_display),
    )

    log.info(
        "Loaded quest data: %d quests, %d items with sources, %d zones, %d chain groups",
        len(ctx.quests),
        len(ctx.item_sources),
        len(ctx.zone_lookup),
        len(ctx.chain_groups),
    )
    return ctx


# ---------------------------------------------------------------------------
# Fetch helpers — each runs one (or very few) SQL queries
# ---------------------------------------------------------------------------


def _fetch_quests(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT q.stable_key, q.db_name, q.display_name,
               qv.quest_desc, qv.resource_name,
               qv.xp_on_complete, qv.gold_on_complete,
               qv.item_on_complete_stable_key,
               qv.assign_new_quest_on_complete_stable_key,
               qv.unlock_item_for_vendor_stable_key,
               qv.set_achievement_on_get, qv.set_achievement_on_finish,
               qv.repeatable, qv.disable_quest, qv.disable_text,
               qv.kill_turn_in_holder, qv.destroy_turn_in_holder,
               qv.drop_invuln_on_holder, qv.once_per_spawn_instance
        FROM quests q
        JOIN quest_variants qv ON q.stable_key = qv.quest_stable_key
        GROUP BY q.stable_key
        HAVING MIN(qv.quest_db_index)
        ORDER BY q.display_name COLLATE NOCASE
        """
    ).fetchall()


def _fetch_acquisition_sources(
    conn: sqlite3.Connection,
) -> dict[str, list[AcquisitionSource]]:
    rows = conn.execute(
        """
        SELECT qas.quest_stable_key, qas.method, qas.source_type,
               qas.source_stable_key, qas.note,
               COALESCE(c.display_name, i.display_name, z.display_name,
                        qv.quest_name) AS source_name,
               cd.keywords AS keyword
        FROM quest_acquisition_sources qas
        LEFT JOIN characters c
            ON c.stable_key = qas.source_stable_key AND qas.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qas.source_stable_key AND qas.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qas.source_stable_key AND qas.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qas.source_stable_key AND qas.source_type = 'quest'
        LEFT JOIN character_dialogs cd
            ON cd.character_stable_key = qas.source_stable_key
            AND cd.assign_quest_stable_key = qas.quest_stable_key
            AND cd.keywords IS NOT NULL AND cd.keywords != ''
        WHERE c.stable_key IS NULL OR c.is_map_visible = 1
        GROUP BY qas.quest_stable_key, qas.source_stable_key
        """
    ).fetchall()
    result: dict[str, list[AcquisitionSource]] = {}
    for row in rows:
        src = AcquisitionSource(
            method=row["method"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_stable_key=row["source_stable_key"],
            keyword=row["keyword"],
            note=row["note"],
        )
        result.setdefault(row["quest_stable_key"], []).append(src)
    return result


def _fetch_completion_sources(
    conn: sqlite3.Connection,
) -> dict[str, list[CompletionSource]]:
    rows = conn.execute(
        """
        SELECT qcs.quest_stable_key, qcs.method, qcs.source_type,
               qcs.source_stable_key, qcs.note,
               COALESCE(c.display_name, i.display_name, z.display_name,
                        qv.quest_name) AS source_name,
               cd.keywords AS keyword
        FROM quest_completion_sources qcs
        LEFT JOIN characters c
            ON c.stable_key = qcs.source_stable_key AND qcs.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qcs.source_stable_key AND qcs.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qcs.source_stable_key AND qcs.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qcs.source_stable_key AND qcs.source_type = 'quest'
        LEFT JOIN character_dialogs cd
            ON cd.character_stable_key = qcs.source_stable_key
            AND cd.complete_quest_stable_key = qcs.quest_stable_key
            AND cd.keywords IS NOT NULL AND cd.keywords != ''
        WHERE c.stable_key IS NULL OR c.is_map_visible = 1
        GROUP BY qcs.quest_stable_key, qcs.source_stable_key
        """
    ).fetchall()
    result: dict[str, list[CompletionSource]] = {}
    for row in rows:
        quest_sk = row["quest_stable_key"]
        src = CompletionSource(
            method=row["method"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_stable_key=row["source_stable_key"],
            keyword=row["keyword"],
            note=row["note"],
        )
        # Deduplicate by (method, source_name) — same NPC may have
        # multiple stable keys for different placements.
        existing = result.setdefault(quest_sk, [])
        if not any(e.method == src.method and e.source_name == src.source_name for e in existing):
            existing.append(src)
    return result


def _fetch_required_items(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Return ``{variant_resource_name: [{item_stable_key, quantity}]}``."""
    rows = conn.execute(
        """
        SELECT qri.quest_variant_resource_name, qri.item_stable_key, qri.quantity
        FROM quest_required_items qri
        """
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["quest_variant_resource_name"], []).append(
            {"item_stable_key": row["item_stable_key"], "quantity": row["quantity"]}
        )
    return result


def _fetch_faction_effects(
    conn: sqlite3.Connection,
) -> dict[str, list[FactionEffect]]:
    """Return ``{variant_resource_name: [FactionEffect]}``."""
    rows = conn.execute(
        """
        SELECT qfa.quest_variant_resource_name,
               f.display_name, f.stable_key, qfa.modifier_value
        FROM quest_faction_affects qfa
        JOIN factions f ON f.stable_key = qfa.faction_stable_key
        """
    ).fetchall()
    result: dict[str, list[FactionEffect]] = {}
    for row in rows:
        fe = FactionEffect(
            faction_name=row["display_name"],
            faction_stable_key=row["stable_key"],
            amount=row["modifier_value"],
        )
        result.setdefault(row["quest_variant_resource_name"], []).append(fe)
    return result


def _fetch_chain_next(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``{quest_sk: next_quest_sk}``."""
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key,
               qv.assign_new_quest_on_complete_stable_key
        FROM quest_variants qv
        WHERE qv.assign_new_quest_on_complete_stable_key IS NOT NULL
          AND qv.assign_new_quest_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()
    return {row["quest_stable_key"]: row["assign_new_quest_on_complete_stable_key"] for row in rows}


def _fetch_chain_prev(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return ``{quest_sk: [previous_quest_sks]}`` (reverse of chain_next)."""
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key AS prev_sk,
               qv.assign_new_quest_on_complete_stable_key AS this_sk
        FROM quest_variants qv
        WHERE qv.assign_new_quest_on_complete_stable_key IS NOT NULL
          AND qv.assign_new_quest_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["this_sk"], []).append(row["prev_sk"])
    return result


def _fetch_also_completes(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return ``{variant_resource_name: [completed_quest_sks]}``."""
    rows = conn.execute("SELECT * FROM quest_complete_other_quests").fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["quest_variant_resource_name"], []).append(row["completed_quest_stable_key"])
    return result


def _fetch_completed_by(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return ``{quest_sk: [completing_quest_sks]}``."""
    rows = conn.execute(
        """
        SELECT qcoq.completed_quest_stable_key,
               qv.quest_stable_key AS completer_sk
        FROM quest_complete_other_quests qcoq
        JOIN quest_variants qv
            ON qv.resource_name = qcoq.quest_variant_resource_name
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["completed_quest_stable_key"], []).append(row["completer_sk"])
    return result


def _fetch_prerequisites(
    conn: sqlite3.Connection,
) -> dict[str, list[Prerequisite]]:
    """Return ``{quest_sk: [Prerequisite]}`` from dialog gate data."""
    rows = conn.execute(
        """
        SELECT cd.assign_quest_stable_key AS quest_sk,
               cd.required_quest_stable_key,
               q.display_name AS required_quest_name
        FROM character_dialogs cd
        JOIN quests q ON q.stable_key = cd.required_quest_stable_key
        WHERE cd.assign_quest_stable_key IS NOT NULL
          AND cd.assign_quest_stable_key != ''
          AND cd.required_quest_stable_key IS NOT NULL
          AND cd.required_quest_stable_key != ''
        GROUP BY cd.assign_quest_stable_key, cd.required_quest_stable_key
        """
    ).fetchall()
    result: dict[str, list[Prerequisite]] = {}
    for row in rows:
        prereq = Prerequisite(
            type="quest",
            quest_key=row["required_quest_stable_key"],
            quest_name=row["required_quest_name"],
        )
        result.setdefault(row["quest_sk"], []).append(prereq)
    return result


def _fetch_npc_zones(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``{character_sk: zone_display_name}``."""
    if not _table_exists(conn, "character_spawns"):
        return {}
    rows = conn.execute(
        """
        SELECT cs.character_stable_key, z.display_name
        FROM character_spawns cs
        JOIN characters c ON c.stable_key = cs.character_stable_key
        JOIN zones z ON z.stable_key = cs.zone_stable_key
        WHERE c.is_map_visible = 1
        GROUP BY cs.character_stable_key
        """
    ).fetchall()
    return {row["character_stable_key"]: row["display_name"] for row in rows}


def _fetch_char_name_zones(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return ``{character_display_name: [zone_display_names]}``."""
    if not _table_exists(conn, "character_spawns"):
        return {}
    rows = conn.execute(
        """
        SELECT c.display_name, z.display_name AS zone_name
        FROM character_spawns cs
        JOIN characters c ON c.stable_key = cs.character_stable_key
        JOIN zones z ON z.stable_key = cs.zone_stable_key
        WHERE c.is_map_visible = 1
        GROUP BY c.display_name, z.display_name
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["display_name"], []).append(row["zone_name"])
    return result


def _fetch_item_names(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``{item_sk: display_name}``."""
    rows = conn.execute("SELECT stable_key, display_name FROM items").fetchall()
    return {row["stable_key"]: row["display_name"] for row in rows}


def _fetch_shout_keywords(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``{character_sk: shout_keyword}``."""
    rows = conn.execute(
        """
        SELECT stable_key, shout_trigger_keyword
        FROM characters
        WHERE shout_trigger_keyword IS NOT NULL
          AND shout_trigger_keyword != ''
        """
    ).fetchall()
    return {row["stable_key"]: row["shout_trigger_keyword"] for row in rows}


def _fetch_char_levels(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{character_sk: level}`` for non-friendly characters with level > 0."""
    rows = conn.execute(
        "SELECT stable_key, level FROM characters WHERE level > 0 AND is_friendly = 0 AND is_map_visible = 1"
    ).fetchall()
    return {row["stable_key"]: row["level"] for row in rows}


def _fetch_zone_lookup(conn: sqlite3.Connection) -> dict[str, ZoneInfo]:
    """Build zone lookup keyed by scene_name with mob level statistics.

    Only non-friendly characters with level > 0 contribute to level stats.
    """
    rows = conn.execute(
        """
        SELECT z.stable_key, z.scene_name, z.display_name, c.level
        FROM zones z
        JOIN character_spawns cs ON cs.zone_stable_key = z.stable_key
        JOIN characters c ON cs.character_stable_key = c.stable_key
        WHERE c.is_friendly = 0 AND c.level > 0 AND c.is_map_visible = 1
        """
    ).fetchall()
    zone_meta: dict[str, dict] = {}
    zone_levels: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        scene = row["scene_name"]
        if scene not in zone_meta:
            zone_meta[scene] = {
                "stable_key": row["stable_key"],
                "display_name": row["display_name"],
            }
        zone_levels[scene].append(row["level"])
    result: dict[str, ZoneInfo] = {}
    for scene, levels in zone_levels.items():
        meta = zone_meta[scene]
        result[scene] = ZoneInfo(
            stable_key=meta["stable_key"],
            display_name=meta["display_name"],
            level_min=min(levels),
            level_max=max(levels),
            level_median=int(median(levels)),
        )
    return result


def _fetch_character_spawns(
    conn: sqlite3.Connection,
) -> dict[str, list[SpawnPoint]]:
    """Return all character spawn points keyed by character_stable_key."""
    rows = conn.execute(
        """
        SELECT character_stable_key, scene, x, y, z
        FROM character_spawns
        WHERE x IS NOT NULL
        """
    ).fetchall()
    result: dict[str, list[SpawnPoint]] = {}
    for row in rows:
        sp = SpawnPoint(scene=row["scene"], x=row["x"], y=row["y"], z=row["z"])
        result.setdefault(row["character_stable_key"], []).append(sp)
    return result


def _fetch_zone_lines(conn: sqlite3.Connection) -> list[ZoneLine]:
    """Return all zone transition points with destination display names."""
    rows = conn.execute(
        """
        SELECT zl.scene, zl.x, zl.y, zl.z,
               zl.destination_zone_stable_key,
               z.display_name AS dest_display,
               zl.landing_position_x, zl.landing_position_y,
               zl.landing_position_z
        FROM zone_lines zl
        LEFT JOIN zones z ON zl.destination_zone_stable_key = z.stable_key
        """
    ).fetchall()
    return [
        ZoneLine(
            scene=row["scene"],
            x=row["x"],
            y=row["y"],
            z=row["z"],
            destination_zone_key=row["destination_zone_stable_key"] or "",
            destination_display=row["dest_display"] or "",
            landing_x=row["landing_position_x"],
            landing_y=row["landing_position_y"],
            landing_z=row["landing_position_z"],
        )
        for row in rows
    ]


def _fetch_reward_items(conn: sqlite3.Connection) -> dict[str, str]:
    """Return ``{quest_sk: reward_item_sk}`` for implicit prereq detection."""
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key, qv.item_on_complete_stable_key
        FROM quest_variants qv
        WHERE qv.item_on_complete_stable_key IS NOT NULL
          AND qv.item_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()
    return {row["quest_stable_key"]: row["item_on_complete_stable_key"] for row in rows}


def _compute_chain_groups(conn: sqlite3.Connection) -> list[ChainGroup]:
    """Walk assign_new_quest_on_complete chains and return ordered groups.

    Finds root quests (no predecessor), walks each chain forward, and
    produces a ChainGroup with quests ordered by chain position.
    """
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key,
               qv.assign_new_quest_on_complete_stable_key,
               q.display_name, q.db_name
        FROM quest_variants qv
        JOIN quests q ON qv.quest_stable_key = q.stable_key
        WHERE qv.assign_new_quest_on_complete_stable_key IS NOT NULL
          AND qv.assign_new_quest_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()

    next_map: dict[str, str] = {}
    meta: dict[str, dict] = {}
    children: set[str] = set()
    for row in rows:
        sk = row["quest_stable_key"]
        next_sk = row["assign_new_quest_on_complete_stable_key"]
        next_map[sk] = next_sk
        meta[sk] = {"display_name": row["display_name"], "db_name": row["db_name"]}
        children.add(next_sk)

    # Fetch metadata for chain-terminal quests not in next_map
    missing = children - set(meta.keys())
    if missing:
        placeholders = ",".join("?" for _ in missing)
        child_rows = conn.execute(
            f"SELECT stable_key, display_name, db_name FROM quests WHERE stable_key IN ({placeholders})",
            list(missing),
        ).fetchall()
        for row in child_rows:
            meta[row["stable_key"]] = {
                "display_name": row["display_name"],
                "db_name": row["db_name"],
            }

    roots = [sk for sk in next_map if sk not in children]
    groups: list[ChainGroup] = []
    for root in roots:
        db_names: list[str] = []
        current: str | None = root
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current in meta:
                db_names.append(meta[current]["db_name"])
            current = next_map.get(current)
        # Append the final quest in the chain (child-only, not in next_map)
        if current and current in meta and current not in seen:
            db_names.append(meta[current]["db_name"])
        chain_name = meta[root]["display_name"] if root in meta else root
        groups.append(ChainGroup(name=chain_name, quests=db_names))
    return groups


# ---------------------------------------------------------------------------
# Unified item sources
# ---------------------------------------------------------------------------


def _build_item_sources(
    conn: sqlite3.Connection,
    zone_by_display: dict[str, ZoneInfo],
) -> dict[str, list[ItemSource]]:
    """Build unified ``{item_sk: [ItemSource]}`` from all obtainability queries.

    Sources are sorted by level ascending per item, with ``None``-level
    entries at the end.
    """
    sources: dict[str, list[ItemSource]] = defaultdict(list)

    _add_drop_sources(conn, sources)
    _add_vendor_sources(conn, sources, zone_by_display)
    _add_fishing_sources(conn, sources, zone_by_display)
    _add_mining_sources(conn, sources, zone_by_display)
    _add_bag_sources(conn, sources, zone_by_display)
    _add_crafting_sources(conn, sources)
    _add_quest_reward_sources(conn, sources)

    # Sort each item's sources: levelled ascending, then None-level at end
    for _item_sk, item_list in sources.items():
        item_list.sort(key=_source_sort_key)

    return dict(sources)


def _source_sort_key(src: ItemSource) -> tuple[int, int]:
    """Sort key: (0, level) for sources with a level, (1, 0) for None."""
    if src.level is not None:
        return (0, src.level)
    return (1, 0)


def _add_drop_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
) -> None:
    """Drop sources with per-(character, zone) spawn counts and character level."""
    rows = conn.execute(
        """
        SELECT ld.item_stable_key,
               c.display_name AS character_name,
               c.level,
               z.display_name AS zone_name,
               COUNT(cs.rowid) AS spawn_count
        FROM loot_drops ld
        JOIN characters c ON c.stable_key = ld.character_stable_key
        LEFT JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
        LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
        WHERE c.is_map_visible = 1
        GROUP BY ld.item_stable_key, c.stable_key, z.stable_key
        """
    ).fetchall()
    for row in rows:
        level = row["level"] if row["level"] and row["level"] > 0 else None
        out[row["item_stable_key"]].append(
            ItemSource(
                type="drop",
                name=row["character_name"],
                zone=row["zone_name"],
                level=level,
                spawn_count=row["spawn_count"] if row["zone_name"] else None,
            )
        )


def _add_vendor_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
    zone_by_display: dict[str, ZoneInfo],
) -> None:
    """Vendor sources deduplicated by (character_name, zone), level = zone median."""
    rows = conn.execute(
        """
        SELECT DISTINCT cvi.item_stable_key,
               c.display_name AS character_name,
               z.display_name AS zone_name
        FROM character_vendor_items cvi
        JOIN characters c ON c.stable_key = cvi.character_stable_key
        LEFT JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
        LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
        WHERE c.is_map_visible = 1
        GROUP BY cvi.item_stable_key, c.display_name, z.display_name
        """
    ).fetchall()
    for row in rows:
        zone_name = row["zone_name"]
        zi = zone_by_display.get(zone_name) if zone_name else None
        out[row["item_stable_key"]].append(
            ItemSource(
                type="vendor",
                name=row["character_name"],
                zone=zone_name,
                level=zi.level_median if zi else None,
            )
        )


def _add_fishing_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
    zone_by_display: dict[str, ZoneInfo],
) -> None:
    """Fishing sources aggregated to one entry per (item, zone) with node_count."""
    rows = conn.execute(
        """
        SELECT wf.item_stable_key,
               z.display_name AS zone_name,
               COUNT(*) AS node_count
        FROM water_fishables wf
        JOIN waters w ON wf.water_stable_key = w.stable_key
        LEFT JOIN zones z ON z.scene_name = w.scene
        GROUP BY wf.item_stable_key, z.display_name
        """
    ).fetchall()
    for row in rows:
        zone_name = row["zone_name"]
        zi = zone_by_display.get(zone_name) if zone_name else None
        out[row["item_stable_key"]].append(
            ItemSource(
                type="fishing",
                zone=zone_name,
                level=zi.level_median if zi else None,
                node_count=row["node_count"],
            )
        )


def _add_mining_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
    zone_by_display: dict[str, ZoneInfo],
) -> None:
    """Mining sources aggregated to one entry per (item, zone) with node_count."""
    rows = conn.execute(
        """
        SELECT mni.item_stable_key,
               z.display_name AS zone_name,
               COUNT(*) AS node_count
        FROM mining_node_items mni
        JOIN mining_nodes mn ON mni.mining_node_stable_key = mn.stable_key
        LEFT JOIN zones z ON z.scene_name = mn.scene
        GROUP BY mni.item_stable_key, z.display_name
        """
    ).fetchall()
    for row in rows:
        zone_name = row["zone_name"]
        zi = zone_by_display.get(zone_name) if zone_name else None
        out[row["item_stable_key"]].append(
            ItemSource(
                type="mining",
                zone=zone_name,
                level=zi.level_median if zi else None,
                node_count=row["node_count"],
            )
        )


def _add_bag_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
    zone_by_display: dict[str, ZoneInfo],
) -> None:
    """Pickup/bag sources aggregated to one entry per (item, zone) with node_count."""
    rows = conn.execute(
        """
        SELECT ib.item_stable_key,
               z.display_name AS zone_name,
               COUNT(*) AS node_count
        FROM item_bags ib
        LEFT JOIN zones z ON z.scene_name = ib.scene
        WHERE ib.item_stable_key IS NOT NULL
        GROUP BY ib.item_stable_key, z.display_name
        """
    ).fetchall()
    for row in rows:
        zone_name = row["zone_name"]
        zi = zone_by_display.get(zone_name) if zone_name else None
        out[row["item_stable_key"]].append(
            ItemSource(
                type="pickup",
                zone=zone_name,
                level=zi.level_median if zi else None,
                node_count=row["node_count"],
            )
        )


def _add_crafting_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
) -> None:
    """Crafting recipe sources — no level (item-level, not zone-level)."""
    rows = conn.execute(
        """
        SELECT cr.reward_item_stable_key,
               i.display_name AS recipe_name
        FROM crafting_rewards cr
        JOIN items i ON cr.recipe_item_stable_key = i.stable_key
        """
    ).fetchall()
    for row in rows:
        out[row["reward_item_stable_key"]].append(ItemSource(type="crafting", name=row["recipe_name"]))


def _add_quest_reward_sources(
    conn: sqlite3.Connection,
    out: dict[str, list[ItemSource]],
) -> None:
    """Quest reward sources — level filled in later by the levels phase."""
    rows = conn.execute(
        """
        SELECT qv.item_on_complete_stable_key,
               q.display_name AS quest_name,
               q.stable_key AS quest_stable_key
        FROM quest_variants qv
        JOIN quests q ON qv.quest_stable_key = q.stable_key
        WHERE qv.item_on_complete_stable_key IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        out[row["item_on_complete_stable_key"]].append(
            ItemSource(
                type="quest_reward",
                name=row["quest_name"],
                quest_key=row["quest_stable_key"],
            )
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None
