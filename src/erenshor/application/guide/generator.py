"""Quest guide generator.

Queries the processed SQLite database and builds QuestGuide entries
for every quest. Handles:
- Identity and description from quest_variants
- Acquisition and completion sources from junction tables
- Required items with quantity and drop/vendor sources
- Quest chain links (previous/next)
- Quest type inference from completion methods
- Step auto-generation for simple quest types
- Flags and rewards
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import median

from loguru import logger

from .schema import (
    AcquisitionSource,
    BagSource,
    ChainGroup,
    ChainLink,
    CompletionSource,
    CraftingSource,
    DropSource,
    FactionEffect,
    FishingSource,
    GuideOutput,
    LevelEstimate,
    LevelFactor,
    MiningSource,
    QuestFlags,
    QuestGuide,
    QuestRewardSource,
    QuestStep,
    QuestType,
    RequiredItemInfo,
    Rewards,
    SpawnPoint,
    VendorSource,
    ZoneInfo,
    ZoneLine,
)


def generate(db_path: Path) -> GuideOutput:
    """Generate quest guide with lookup tables for all quests in the database.

    Args:
        db_path: Path to the processed SQLite database.

    Returns:
        GuideOutput with lookup tables and quest entries.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Build lookup tables
        zone_lookup = _fetch_zone_lookup(conn)
        character_spawns = _fetch_character_spawns(conn)
        zone_lines = _fetch_zone_lines(conn)
        chain_groups = _compute_chain_groups(conn)

        # Build quest entries
        guides = _build_all_guides(conn, zone_lookup)
        logger.info(f"Generated {len(guides)} quest guide entries")

        return GuideOutput(
            version=2,
            zone_lookup=zone_lookup,
            character_spawns=character_spawns,
            zone_lines=zone_lines,
            chain_groups=chain_groups,
            quests=guides,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _build_all_guides(conn: sqlite3.Connection, zone_lookup: dict[str, ZoneInfo]) -> list[QuestGuide]:
    """Build QuestGuide for every quest in the database."""
    quests = conn.execute(
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

    # Pre-fetch all relationship data into lookup dicts to avoid N+1 queries
    acquisition_map = _fetch_acquisition_sources(conn)
    completion_map = _fetch_completion_sources(conn)
    required_items_map = _fetch_required_items(conn)
    drop_sources_map = _fetch_drop_sources(conn)
    vendor_sources_map = _fetch_vendor_sources(conn)
    faction_effects_map = _fetch_faction_effects(conn)
    chain_next_map = _fetch_chain_next(conn)
    chain_prev_map = _fetch_chain_prev(conn)
    also_completes_map = _fetch_also_completes(conn)
    completed_by_map = _fetch_completed_by(conn)
    prerequisites_map = _fetch_prerequisites(conn)
    # NPC zone lookup for zone_context inference
    npc_zones = _fetch_npc_zones(conn)
    # Reward item names
    item_names = _fetch_item_names(conn)
    # Quest names for chain links
    quest_names = {row["stable_key"]: row["display_name"] for row in quests}
    # Shout keywords
    shout_keywords = _fetch_shout_keywords(conn)
    # Obtainability sources for required items
    fishing_map = _fetch_fishing_sources(conn)
    mining_map = _fetch_mining_sources(conn)
    bag_map = _fetch_bag_sources(conn)
    crafting_map = _fetch_crafting_sources(conn)
    quest_reward_map = _fetch_quest_reward_sources(conn)
    # Character levels for level estimation (enemies only)
    char_levels = {
        row["stable_key"]: row["level"]
        for row in conn.execute(
            "SELECT stable_key, level FROM characters WHERE level > 0 AND is_friendly = 0"
        ).fetchall()
    }
    # Character name → zone for step level estimation (all characters)
    char_name_zones = _fetch_char_name_zones(conn)
    # Reverse lookup: zone display_name → ZoneInfo
    zone_by_display = {zi.display_name: zi for zi in zone_lookup.values()}

    guides: list[QuestGuide] = []
    for quest in quests:
        sk = quest["stable_key"]
        variant_rn = quest["resource_name"]

        acquisition = acquisition_map.get(sk, [])
        completion = completion_map.get(sk, [])
        required_items = _build_required_items(
            variant_rn,
            required_items_map,
            drop_sources_map,
            vendor_sources_map,
            item_names,
            fishing_map,
            mining_map,
            bag_map,
            crafting_map,
            quest_reward_map,
            exclude_quest_sk=sk,
        )
        rewards = _build_rewards(
            quest, chain_next_map, also_completes_map, faction_effects_map, item_names, quest_names
        )
        chain = _build_chain(sk, chain_next_map, chain_prev_map, also_completes_map, completed_by_map, quest_names)
        flags = _build_flags(quest)
        quest_type = _infer_quest_type(completion, required_items)
        zone_context = _infer_zone_context(sk, acquisition, completion, npc_zones)
        prerequisites = prerequisites_map.get(sk, [])

        steps = _generate_steps(
            quest_type, acquisition, completion, required_items, zone_context, quest_names, shout_keywords, sk
        )

        # Per-step level estimates, then derive quest level as max of steps
        for step in steps:
            step.level_estimate = _compute_step_level(
                step, required_items, zone_by_display, char_levels, char_name_zones
            )
        level_estimate = _compute_quest_level(steps)

        guide = QuestGuide(
            db_name=quest["db_name"],
            stable_key=sk,
            display_name=quest["display_name"],
            description=quest["quest_desc"] or None,
            quest_type=quest_type,
            zone_context=zone_context,
            acquisition=acquisition,
            prerequisites=prerequisites,
            steps=steps,
            required_items=required_items,
            completion=completion,
            rewards=rewards,
            chain=chain,
            flags=flags,
            level_estimate=level_estimate,
        )
        guides.append(guide)

    return guides


# ---------------------------------------------------------------------------
# Data fetchers -- bulk queries into lookup dicts
# ---------------------------------------------------------------------------


def _fetch_acquisition_sources(conn: sqlite3.Connection) -> dict[str, list[AcquisitionSource]]:
    rows = conn.execute(
        """
        SELECT qas.quest_stable_key, qas.method, qas.source_type,
               qas.source_stable_key, qas.note,
               COALESCE(c.display_name, i.display_name, z.display_name, qv.quest_name) AS source_name
        FROM quest_acquisition_sources qas
        LEFT JOIN characters c
            ON c.stable_key = qas.source_stable_key AND qas.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qas.source_stable_key AND qas.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qas.source_stable_key AND qas.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qas.source_stable_key AND qas.source_type = 'quest'
        WHERE c.stable_key IS NULL OR c.is_map_visible = 1
        """
    ).fetchall()
    result: dict[str, list[AcquisitionSource]] = {}
    for row in rows:
        src = AcquisitionSource(
            method=row["method"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_stable_key=row["source_stable_key"],
            note=row["note"],
        )
        result.setdefault(row["quest_stable_key"], []).append(src)
    return result


def _fetch_completion_sources(conn: sqlite3.Connection) -> dict[str, list[CompletionSource]]:
    rows = conn.execute(
        """
        SELECT qcs.quest_stable_key, qcs.method, qcs.source_type,
               qcs.source_stable_key, qcs.note,
               COALESCE(c.display_name, i.display_name, z.display_name, qv.quest_name) AS source_name
        FROM quest_completion_sources qcs
        LEFT JOIN characters c
            ON c.stable_key = qcs.source_stable_key AND qcs.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qcs.source_stable_key AND qcs.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qcs.source_stable_key AND qcs.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qcs.source_stable_key AND qcs.source_type = 'quest'
        WHERE c.stable_key IS NULL OR c.is_map_visible = 1
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
            note=row["note"],
        )
        # Deduplicate by (method, source_name) — same NPC may have
        # multiple stable keys for different placements
        existing = result.setdefault(quest_sk, [])
        if not any(e.method == src.method and e.source_name == src.source_name for e in existing):
            existing.append(src)
    return result


def _fetch_required_items(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Returns {variant_resource_name: [{item_stable_key, quantity}]}."""
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


def _fetch_drop_sources(conn: sqlite3.Connection) -> dict[str, list[DropSource]]:
    """Returns {item_stable_key: [DropSource]}."""
    rows = conn.execute(
        """
        SELECT DISTINCT ld.item_stable_key, c.display_name AS character_name,
               c.stable_key AS character_stable_key, z.display_name AS zone_name
        FROM loot_drops ld
        JOIN characters c ON c.stable_key = ld.character_stable_key
        LEFT JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
        LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
        GROUP BY ld.item_stable_key, c.stable_key
        """
    ).fetchall()
    result: dict[str, list[DropSource]] = {}
    for row in rows:
        ds = DropSource(
            character_name=row["character_name"],
            character_stable_key=row["character_stable_key"],
            zone_name=row["zone_name"],
        )
        result.setdefault(row["item_stable_key"], []).append(ds)
    return result


def _fetch_vendor_sources(conn: sqlite3.Connection) -> dict[str, list[VendorSource]]:
    """Returns {item_stable_key: [VendorSource]}."""
    rows = conn.execute(
        """
        SELECT DISTINCT cvi.item_stable_key, c.display_name AS character_name,
               c.stable_key AS character_stable_key, z.display_name AS zone_name
        FROM character_vendor_items cvi
        JOIN characters c ON c.stable_key = cvi.character_stable_key
        LEFT JOIN character_spawns cs ON cs.character_stable_key = c.stable_key
        LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
        GROUP BY cvi.item_stable_key, c.stable_key
        """
    ).fetchall()
    result: dict[str, list[VendorSource]] = {}
    for row in rows:
        vs = VendorSource(
            character_name=row["character_name"],
            character_stable_key=row["character_stable_key"],
            zone_name=row["zone_name"],
        )
        result.setdefault(row["item_stable_key"], []).append(vs)
    return result


def _fetch_faction_effects(conn: sqlite3.Connection) -> dict[str, list[FactionEffect]]:
    """Returns {variant_resource_name: [FactionEffect]}."""
    rows = conn.execute(
        """
        SELECT qfa.quest_variant_resource_name, f.display_name, f.stable_key, qfa.modifier_value
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
    """Returns {quest_stable_key: next_quest_stable_key} from AssignNewQuestOnComplete."""
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key, qv.assign_new_quest_on_complete_stable_key
        FROM quest_variants qv
        WHERE qv.assign_new_quest_on_complete_stable_key IS NOT NULL
          AND qv.assign_new_quest_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()
    return {row["quest_stable_key"]: row["assign_new_quest_on_complete_stable_key"] for row in rows}


def _fetch_chain_prev(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Returns {quest_stable_key: [previous_quest_stable_keys]} (reverse of chain_next)."""
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
    """Returns {variant_resource_name: [completed_quest_stable_keys]}."""
    rows = conn.execute("SELECT * FROM quest_complete_other_quests").fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["quest_variant_resource_name"], []).append(row["completed_quest_stable_key"])
    return result


def _fetch_completed_by(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Returns {quest_stable_key: [completing_variant_resource_names]}."""
    rows = conn.execute(
        """
        SELECT qcoq.completed_quest_stable_key, qv.quest_stable_key AS completer_sk
        FROM quest_complete_other_quests qcoq
        JOIN quest_variants qv ON qv.resource_name = qcoq.quest_variant_resource_name
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["completed_quest_stable_key"], []).append(row["completer_sk"])
    return result


def _fetch_prerequisites(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Returns {quest_stable_key: [human-readable prerequisite strings]}.

    Sources: NPCDialog.RequireQuestComplete (dialog gated by quest completion).
    """
    rows = conn.execute(
        """
        SELECT cd.assign_quest_stable_key AS quest_sk,
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
    result: dict[str, list[str]] = {}
    for row in rows:
        prereq = f'Complete "{row["required_quest_name"]}"'
        result.setdefault(row["quest_sk"], []).append(prereq)
    return result


def _fetch_npc_zones(conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {character_stable_key: zone_display_name}."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "character_spawns" not in tables:
        return {}
    rows = conn.execute(
        """
        SELECT cs.character_stable_key, z.display_name
        FROM character_spawns cs
        JOIN zones z ON z.stable_key = cs.zone_stable_key
        GROUP BY cs.character_stable_key
        """
    ).fetchall()
    return {row["character_stable_key"]: row["display_name"] for row in rows}


def _fetch_char_name_zones(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Returns {character_display_name: [zone_display_names]}.

    Maps character display names to all zones they spawn in. Used for
    talk/turn_in/shout steps where we need the zone of a target NPC
    referenced by display name. The caller picks the lowest-median zone.
    """
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "character_spawns" not in tables:
        return {}
    rows = conn.execute(
        """
        SELECT c.display_name, z.display_name AS zone_name
        FROM character_spawns cs
        JOIN characters c ON c.stable_key = cs.character_stable_key
        JOIN zones z ON z.stable_key = cs.zone_stable_key
        GROUP BY c.display_name, z.display_name
        """
    ).fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["display_name"], []).append(row["zone_name"])
    return result


def _fetch_item_names(conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {item_stable_key: display_name}."""
    rows = conn.execute("SELECT stable_key, display_name FROM items").fetchall()
    return {row["stable_key"]: row["display_name"] for row in rows}


def _fetch_shout_keywords(conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {character_stable_key: shout_keyword}."""
    rows = conn.execute(
        """
        SELECT stable_key, shout_trigger_keyword
        FROM characters
        WHERE shout_trigger_keyword IS NOT NULL AND shout_trigger_keyword != ''
        """
    ).fetchall()
    return {row["stable_key"]: row["shout_trigger_keyword"] for row in rows}


# ---------------------------------------------------------------------------
# Builders -- assemble sub-schemas from pre-fetched data
# ---------------------------------------------------------------------------


def _build_required_items(
    variant_rn: str,
    required_items_map: dict[str, list[dict]],
    drop_sources_map: dict[str, list[DropSource]],
    vendor_sources_map: dict[str, list[VendorSource]],
    item_names: dict[str, str],
    fishing_map: dict[str, list[FishingSource]],
    mining_map: dict[str, list[MiningSource]],
    bag_map: dict[str, list[BagSource]],
    crafting_map: dict[str, list[CraftingSource]],
    quest_reward_map: dict[str, list[QuestRewardSource]],
    exclude_quest_sk: str = "",
) -> list[RequiredItemInfo]:
    items = required_items_map.get(variant_rn, [])
    result = []
    for item in items:
        isk = item["item_stable_key"]
        result.append(
            RequiredItemInfo(
                item_name=item_names.get(isk, isk),
                item_stable_key=isk,
                quantity=item["quantity"],
                drop_sources=drop_sources_map.get(isk, []),
                vendor_sources=vendor_sources_map.get(isk, []),
                fishing_sources=fishing_map.get(isk, []),
                mining_sources=mining_map.get(isk, []),
                bag_sources=bag_map.get(isk, []),
                crafting_sources=crafting_map.get(isk, []),
                quest_reward_sources=[
                    qr for qr in quest_reward_map.get(isk, []) if qr.quest_stable_key != exclude_quest_sk
                ],
            )
        )
    return result


def _build_rewards(
    quest: sqlite3.Row,
    chain_next_map: dict[str, str],
    also_completes_map: dict[str, list[str]],
    faction_effects_map: dict[str, list[FactionEffect]],
    item_names: dict[str, str],
    quest_names: dict[str, str],
) -> Rewards:
    sk = quest["stable_key"]
    variant_rn = quest["resource_name"]
    item_sk = quest["item_on_complete_stable_key"]
    next_sk = chain_next_map.get(sk)
    achievements = []
    if quest["set_achievement_on_get"]:
        achievements.append(quest["set_achievement_on_get"])
    if quest["set_achievement_on_finish"]:
        achievements.append(quest["set_achievement_on_finish"])

    also_complete_sks = also_completes_map.get(variant_rn, [])
    also_complete_names = [quest_names.get(csk, csk) for csk in also_complete_sks]

    unlock_sk = quest["unlock_item_for_vendor_stable_key"]

    return Rewards(
        xp=quest["xp_on_complete"] or 0,
        gold=quest["gold_on_complete"] or 0,
        item_name=item_names.get(item_sk) if item_sk else None,
        item_stable_key=item_sk,
        next_quest_name=quest_names.get(next_sk) if next_sk else None,
        next_quest_stable_key=next_sk,
        also_completes=also_complete_names,
        vendor_unlock_item=item_names.get(unlock_sk) if unlock_sk else None,
        achievements=achievements,
        faction_effects=faction_effects_map.get(variant_rn, []),
    )


def _build_chain(
    sk: str,
    chain_next_map: dict[str, str],
    chain_prev_map: dict[str, list[str]],
    also_completes_map: dict[str, list[str]],
    completed_by_map: dict[str, list[str]],
    quest_names: dict[str, str],
) -> list[ChainLink]:
    links: list[ChainLink] = []
    for prev_sk in chain_prev_map.get(sk, []):
        links.append(
            ChainLink(quest_name=quest_names.get(prev_sk, prev_sk), quest_stable_key=prev_sk, relationship="previous")
        )
    next_sk = chain_next_map.get(sk)
    if next_sk:
        links.append(
            ChainLink(quest_name=quest_names.get(next_sk, next_sk), quest_stable_key=next_sk, relationship="next")
        )
    for completer_sk in completed_by_map.get(sk, []):
        links.append(
            ChainLink(
                quest_name=quest_names.get(completer_sk, completer_sk),
                quest_stable_key=completer_sk,
                relationship="completed_by",
            )
        )
    return links


def _build_flags(quest: sqlite3.Row) -> QuestFlags:
    return QuestFlags(
        repeatable=bool(quest["repeatable"]),
        disabled=bool(quest["disable_quest"]),
        disabled_text=quest["disable_text"] or None,
        kill_turn_in_holder=bool(quest["kill_turn_in_holder"]),
        destroy_turn_in_holder=bool(quest["destroy_turn_in_holder"]),
        drop_invuln_on_holder=bool(quest["drop_invuln_on_holder"]),
        once_per_spawn_instance=bool(quest["once_per_spawn_instance"]),
    )


# ---------------------------------------------------------------------------
# Quest type inference
# ---------------------------------------------------------------------------


def _infer_quest_type(
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
) -> str:
    methods = {c.method for c in completion}

    if len(methods) == 0:
        return QuestType.SCRIPTED.value
    if len(methods) > 1 and "scripted" not in methods:
        return QuestType.HYBRID.value

    method = next(iter(methods))

    # item_turnin with required items is a fetch quest
    if method == "item_turnin" and required_items:
        return QuestType.FETCH.value

    method_to_type = {
        "item_turnin": QuestType.FETCH,  # no required items, still fetch
        "death": QuestType.KILL,
        "talk": QuestType.DIALOG,
        "zone": QuestType.ZONE_TRIGGER,
        "shout": QuestType.SHOUT,
        "read": QuestType.ITEM_READ,
        "scripted": QuestType.SCRIPTED,
        "chain": QuestType.CHAIN,
    }
    return method_to_type.get(method, QuestType.SCRIPTED).value


# ---------------------------------------------------------------------------
# Zone context inference
# ---------------------------------------------------------------------------


def _infer_zone_context(
    sk: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    npc_zones: dict[str, str],
) -> str | None:
    # Try acquisition NPC zones first (where you GET the quest)
    for acq in acquisition:
        if acq.source_stable_key and acq.source_type == "character":
            zone = npc_zones.get(acq.source_stable_key)
            if zone:
                return zone
        if acq.source_type == "zone" and acq.zone_name:
            return acq.zone_name

    # Then completion NPC zones
    for comp in completion:
        if comp.source_stable_key and comp.source_type == "character":
            zone = npc_zones.get(comp.source_stable_key)
            if zone:
                return zone
        if comp.source_type == "zone" and comp.zone_name:
            return comp.zone_name

    return None


# ---------------------------------------------------------------------------
# Step auto-generation
# ---------------------------------------------------------------------------

# Step auto-generation uses a closure for ordering, not module-level state.


def _generate_steps(
    quest_type: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
    zone_context: str | None,
    quest_names: dict[str, str],
    shout_keywords: dict[str, str],
    quest_sk: str,
) -> list[QuestStep]:
    """Auto-generate quest steps based on quest type and available data."""
    order = 0

    def step(action: str, description: str, **kwargs) -> QuestStep:
        nonlocal order
        order += 1
        return QuestStep(order=order, action=action, description=description, **kwargs)

    giver = _find_giver(acquisition)

    generators = {
        QuestType.FETCH.value: lambda: _steps_fetch(step, giver, required_items, completion, zone_context, acquisition),
        QuestType.KILL.value: lambda: _steps_kill(step, giver, completion),
        QuestType.DIALOG.value: lambda: _steps_dialog(step, giver, completion),
        QuestType.ZONE_TRIGGER.value: lambda: _steps_zone_trigger(step, giver, completion),
        QuestType.SHOUT.value: lambda: _steps_shout(step, giver, completion, shout_keywords),
        QuestType.ITEM_READ.value: lambda: _steps_item_read(step, acquisition, completion),
    }
    gen = generators.get(quest_type)
    # Scripted, chain, hybrid -- can't auto-generate
    return gen() if gen else []


def _find_giver(acquisition: list[AcquisitionSource]) -> AcquisitionSource | None:
    """Find the primary quest giver (dialog NPC) from acquisition sources."""
    for acq in acquisition:
        if acq.method == "dialog":
            return acq
    return None


StepFactory = type  # type alias for the closure


def _steps_fetch(step, giver, required_items, completion, zone_context, acquisition):
    steps = []
    # For item_read quests, first step is obtaining and reading the item
    item_read_acq = next((a for a in acquisition if a.method == "item_read"), None)
    if item_read_acq and item_read_acq.source_name:
        steps.append(
            step(
                "read",
                f"Obtain and read {item_read_acq.source_name}.",
                target_name=item_read_acq.source_name,
                target_type="item",
            )
        )
    elif giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
            )
        )
    for ri in required_items:
        desc = f"Collect {ri.item_name}"
        if ri.quantity > 1:
            desc = f"Collect {ri.quantity}x {ri.item_name}"
        steps.append(
            step(
                "collect",
                desc + ".",
                target_name=ri.item_name,
                target_type="item",
                quantity=ri.quantity,
            )
        )
    # Turn-in step
    turnin_npc = _find_turnin_npc(completion)
    if turnin_npc:
        steps.append(
            step(
                "turn_in",
                f"Turn in items to {turnin_npc.source_name}.",
                target_name=turnin_npc.source_name,
                target_type="character",
                zone_name=turnin_npc.zone_name or zone_context,
            )
        )
    return steps


def _steps_kill(step, giver, completion):
    steps = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "death" and comp.source_name:
            steps.append(
                step(
                    "kill",
                    f"Defeat {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                )
            )
    return steps


def _steps_dialog(step, giver, completion):
    steps = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "talk" and comp.source_name:
            # Don't duplicate if completer is the same as giver
            if giver and comp.source_stable_key == giver.source_stable_key:
                continue
            steps.append(
                step(
                    "talk",
                    f"Speak to {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                )
            )
    return steps


def _steps_zone_trigger(step, giver, completion):
    steps = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "zone" and comp.source_name:
            steps.append(
                step(
                    "travel",
                    f"Travel to {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="zone",
                    zone_name=comp.source_name,
                )
            )
    return steps


def _steps_shout(step, giver, completion, shout_keywords):
    steps = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "shout" and comp.source_stable_key:
            keyword = shout_keywords.get(comp.source_stable_key, "")
            desc = f'Shout "{keyword}" near {comp.source_name}.' if keyword else f"Shout near {comp.source_name}."
            steps.append(
                step(
                    "shout",
                    desc,
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                    keyword=keyword or None,
                )
            )
    return steps


def _steps_item_read(step, acquisition, completion):
    steps = []
    # First step: obtain and read the quest-starting item
    for acq in acquisition:
        if acq.method == "item_read" and acq.source_name:
            steps.append(
                step(
                    "read",
                    f"Obtain and read {acq.source_name}.",
                    target_name=acq.source_name,
                    target_type="item",
                )
            )
            break  # only one starting item
    # Remaining steps from completion sources (collect items, kill targets, etc.)
    for comp in completion:
        if comp.method == "read" and comp.source_name:
            # Don't duplicate the starting item read step
            if any(s.target_name == comp.source_name for s in steps):
                continue
            steps.append(
                step(
                    "read",
                    f"Read {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="item",
                )
            )
    return steps


def _find_turnin_npc(completion: list[CompletionSource]) -> CompletionSource | None:
    for comp in completion:
        if comp.method == "item_turnin":
            return comp
    return None


# ---------------------------------------------------------------------------
# Lookup table fetchers
# ---------------------------------------------------------------------------


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
        WHERE c.is_friendly = 0 AND c.level > 0
        """
    ).fetchall()
    # Group levels by zone
    zone_meta: dict[str, dict] = {}
    zone_levels: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        scene = row["scene_name"]
        if scene not in zone_meta:
            zone_meta[scene] = {"stable_key": row["stable_key"], "display_name": row["display_name"]}
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


def _fetch_character_spawns(conn: sqlite3.Connection) -> dict[str, list[SpawnPoint]]:
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
               zl.destination_zone_stable_key, z.display_name AS dest_display,
               zl.landing_position_x, zl.landing_position_y, zl.landing_position_z
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


def _fetch_fishing_sources(conn: sqlite3.Connection) -> dict[str, list[FishingSource]]:
    """Return fishing sources keyed by item_stable_key."""
    rows = conn.execute(
        """
        SELECT wf.item_stable_key, wf.water_stable_key, w.scene, wf.drop_chance,
               z.display_name AS zone_name
        FROM water_fishables wf
        JOIN waters w ON wf.water_stable_key = w.stable_key
        LEFT JOIN zones z ON z.scene_name = w.scene
        """
    ).fetchall()
    result: dict[str, list[FishingSource]] = {}
    for row in rows:
        fs = FishingSource(
            water_stable_key=row["water_stable_key"],
            zone_name=row["zone_name"],
            drop_chance=row["drop_chance"],
        )
        result.setdefault(row["item_stable_key"], []).append(fs)
    return result


def _fetch_mining_sources(conn: sqlite3.Connection) -> dict[str, list[MiningSource]]:
    """Return mining sources keyed by item_stable_key."""
    rows = conn.execute(
        """
        SELECT mni.item_stable_key, mni.mining_node_stable_key, mn.scene,
               mni.drop_chance, z.display_name AS zone_name
        FROM mining_node_items mni
        JOIN mining_nodes mn ON mni.mining_node_stable_key = mn.stable_key
        LEFT JOIN zones z ON z.scene_name = mn.scene
        """
    ).fetchall()
    result: dict[str, list[MiningSource]] = {}
    for row in rows:
        ms = MiningSource(
            node_stable_key=row["mining_node_stable_key"],
            zone_name=row["zone_name"],
            drop_chance=row["drop_chance"],
        )
        result.setdefault(row["item_stable_key"], []).append(ms)
    return result


def _fetch_bag_sources(conn: sqlite3.Connection) -> dict[str, list[BagSource]]:
    """Return item bag (world pickup) sources keyed by item_stable_key."""
    rows = conn.execute(
        """
        SELECT ib.item_stable_key, ib.scene, ib.x, ib.y, ib.z, ib.respawns,
               z.display_name AS zone_name
        FROM item_bags ib
        LEFT JOIN zones z ON z.scene_name = ib.scene
        WHERE ib.item_stable_key IS NOT NULL
        """
    ).fetchall()
    result: dict[str, list[BagSource]] = {}
    for row in rows:
        bs = BagSource(
            zone_name=row["zone_name"],
            x=row["x"],
            y=row["y"],
            z=row["z"],
            respawns=bool(row["respawns"]),
        )
        result.setdefault(row["item_stable_key"], []).append(bs)
    return result


def _fetch_crafting_sources(conn: sqlite3.Connection) -> dict[str, list[CraftingSource]]:
    """Return crafting recipe sources keyed by reward_item_stable_key."""
    rows = conn.execute(
        """
        SELECT cr.reward_item_stable_key, cr.recipe_item_stable_key,
               i.display_name AS recipe_name
        FROM crafting_rewards cr
        JOIN items i ON cr.recipe_item_stable_key = i.stable_key
        """
    ).fetchall()
    result: dict[str, list[CraftingSource]] = {}
    for row in rows:
        cs = CraftingSource(
            recipe_item_name=row["recipe_name"],
            recipe_item_stable_key=row["recipe_item_stable_key"],
        )
        result.setdefault(row["reward_item_stable_key"], []).append(cs)
    return result


def _fetch_quest_reward_sources(conn: sqlite3.Connection) -> dict[str, list[QuestRewardSource]]:
    """Return quest reward sources keyed by item_stable_key."""
    rows = conn.execute(
        """
        SELECT qv.item_on_complete_stable_key, q.display_name AS quest_name,
               q.stable_key AS quest_stable_key
        FROM quest_variants qv
        JOIN quests q ON qv.quest_stable_key = q.stable_key
        WHERE qv.item_on_complete_stable_key IS NOT NULL
        """
    ).fetchall()
    result: dict[str, list[QuestRewardSource]] = {}
    for row in rows:
        qrs = QuestRewardSource(
            quest_name=row["quest_name"],
            quest_stable_key=row["quest_stable_key"],
        )
        result.setdefault(row["item_on_complete_stable_key"], []).append(qrs)
    return result


def _compute_chain_groups(conn: sqlite3.Connection) -> list[ChainGroup]:
    """Walk assign_new_quest_on_complete chains and return ordered ChainGroups.

    Finds root quests (no predecessor), walks each chain forward, and
    produces a ChainGroup with quests ordered by chain position.
    """
    rows = conn.execute(
        """
        SELECT qv.quest_stable_key, qv.assign_new_quest_on_complete_stable_key,
               q.display_name, q.db_name
        FROM quest_variants qv
        JOIN quests q ON qv.quest_stable_key = q.stable_key
        WHERE qv.assign_new_quest_on_complete_stable_key IS NOT NULL
          AND qv.assign_new_quest_on_complete_stable_key != ''
        GROUP BY qv.quest_stable_key
        HAVING MIN(qv.quest_db_index)
        """
    ).fetchall()
    # Build adjacency: sk -> next_sk, and record metadata
    next_map: dict[str, str] = {}
    meta: dict[str, dict] = {}  # sk -> {display_name, db_name}
    children: set[str] = set()
    for row in rows:
        sk = row["quest_stable_key"]
        next_sk = row["assign_new_quest_on_complete_stable_key"]
        next_map[sk] = next_sk
        meta[sk] = {"display_name": row["display_name"], "db_name": row["db_name"]}
        children.add(next_sk)
    # We also need db_names for quests that are only children (end of chain)
    # Fetch any missing metadata
    missing = children - set(meta.keys())
    if missing:
        placeholders = ",".join("?" for _ in missing)
        child_rows = conn.execute(
            f"SELECT stable_key, display_name, db_name FROM quests WHERE stable_key IN ({placeholders})",
            list(missing),
        ).fetchall()
        for row in child_rows:
            meta[row["stable_key"]] = {"display_name": row["display_name"], "db_name": row["db_name"]}
    # Roots: quests in next_map that are not children of any other quest
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
        # Append the final quest in the chain (it's a child, not in next_map)
        if current and current in meta and current not in seen:
            db_names.append(meta[current]["db_name"])
        chain_name = meta[root]["display_name"] if root in meta else root
        groups.append(ChainGroup(name=chain_name, quests=db_names))
    return groups


def _compute_step_level(
    step: QuestStep,
    required_items: list[RequiredItemInfo],
    zone_by_display: dict[str, ZoneInfo],
    char_levels: dict[str, int],
    char_name_zones: dict[str, list[str]],
) -> LevelEstimate | None:
    """Estimate the recommended level for a single quest step.

    For collect/read steps: minimum across all obtainability paths
    (enemy level for drops, zone median for vendors/fishing/mining/bags).
    For talk/turn_in/shout: zone median where the target NPC lives.
    For travel: zone median of the destination.
    """
    factors: list[LevelFactor] = []

    if step.action in ("talk", "turn_in", "shout"):
        _add_npc_zone_factor(step.target_name, char_name_zones, zone_by_display, factors)

    elif step.action == "travel":
        zone_name = step.zone_name or step.target_name
        if zone_name:
            zi = zone_by_display.get(zone_name)
            if zi and zi.level_median is not None:
                factors.append(LevelFactor(source="zone_median", name=zone_name, level=zi.level_median))

    elif step.action in ("collect", "read") and step.target_name:
        item = next(
            (ri for ri in required_items if ri.item_name.lower() == step.target_name.lower()),
            None,
        )
        if item:
            _add_obtainability_factors(item, zone_by_display, char_levels, factors)

    if not factors:
        return None
    # Deduplicate factors by (source, name, level)
    seen: set[tuple[str, str | None, int]] = set()
    unique: list[LevelFactor] = []
    for f in factors:
        key = (f.source, f.name, f.level)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    recommended = min(f.level for f in unique)
    return LevelEstimate(recommended=recommended, factors=unique)


def _compute_quest_level(steps: list[QuestStep]) -> LevelEstimate | None:
    """Derive quest-level estimate as max of per-step levels.

    Each step's recommended level is the easiest path through that step.
    The quest level is the hardest step (you can't skip it).
    Factors reference the controlling step for transparency.
    """
    step_levels: list[tuple[QuestStep, int]] = []
    for step in steps:
        if step.level_estimate and step.level_estimate.recommended is not None:
            step_levels.append((step, step.level_estimate.recommended))
    if not step_levels:
        return None
    max_step, max_level = max(step_levels, key=lambda t: t[1])
    factors = [
        LevelFactor(
            source=f"step_{max_step.order}",
            name=max_step.description,
            level=max_level,
        )
    ]
    return LevelEstimate(recommended=max_level, factors=factors)


def _add_npc_zone_factor(
    npc_name: str | None,
    char_name_zones: dict[str, list[str]],
    zone_by_display: dict[str, ZoneInfo],
    factors: list[LevelFactor],
) -> None:
    """Add a zone median factor for an NPC referenced by display name.

    When an NPC spawns in multiple zones, adds the zone with the lowest
    median level (easiest zone to reach them in).
    """
    if not npc_name:
        return
    zones = char_name_zones.get(npc_name)
    if not zones:
        return
    best_zi: ZoneInfo | None = None
    for zone_name in zones:
        zi = zone_by_display.get(zone_name)
        if zi and zi.level_median is not None and (best_zi is None or zi.level_median < best_zi.level_median):
            best_zi = zi
    if best_zi and best_zi.level_median is not None:
        factors.append(LevelFactor(source="zone_median", name=best_zi.display_name, level=best_zi.level_median))


def _add_obtainability_factors(
    item: RequiredItemInfo,
    zone_by_display: dict[str, ZoneInfo],
    char_levels: dict[str, int],
    factors: list[LevelFactor],
) -> None:
    """Collect level factors from all obtainability sources for an item.

    Drop sources use the enemy's actual level. All other sources use the
    zone median of the source location. Each source becomes a factor so
    the user can see all options.
    """
    for ds in item.drop_sources:
        level = char_levels.get(ds.character_stable_key)
        if level:
            factors.append(LevelFactor(source="enemy_level", name=ds.character_name, level=level))

    for vs in item.vendor_sources:
        if vs.zone_name:
            zi = zone_by_display.get(vs.zone_name)
            if zi and zi.level_median is not None:
                factors.append(
                    LevelFactor(
                        source="vendor_zone", name=f"{vs.character_name} ({vs.zone_name})", level=zi.level_median
                    )
                )

    for fs in item.fishing_sources:
        if fs.zone_name:
            zi = zone_by_display.get(fs.zone_name)
            if zi and zi.level_median is not None:
                factors.append(LevelFactor(source="fishing_zone", name=fs.zone_name, level=zi.level_median))

    for ms in item.mining_sources:
        if ms.zone_name:
            zi = zone_by_display.get(ms.zone_name)
            if zi and zi.level_median is not None:
                factors.append(LevelFactor(source="mining_zone", name=ms.zone_name, level=zi.level_median))

    for bs in item.bag_sources:
        if bs.zone_name:
            zi = zone_by_display.get(bs.zone_name)
            if zi and zi.level_median is not None:
                factors.append(LevelFactor(source="pickup_zone", name=bs.zone_name, level=zi.level_median))


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def guides_to_json(guides: list[QuestGuide]) -> list[dict]:
    """Convert QuestGuide list to JSON-serializable dicts.

    Strips None values and empty lists/dicts for compact output.
    """
    return [_strip_empty(asdict(g)) for g in guides]


def _strip_empty(d: dict) -> dict:
    """Recursively remove None values, empty strings, empty lists, and default-valued dicts."""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, list):
            if not v:
                continue
            cleaned = [_strip_empty(item) if isinstance(item, dict) else item for item in v]
            result[k] = cleaned
        elif isinstance(v, dict):
            cleaned = _strip_empty(v)
            if cleaned:
                result[k] = cleaned
        elif isinstance(v, str) and not v:
            continue
        elif isinstance(v, bool):
            # Only include True flags (False is default)
            if v:
                result[k] = v
        elif isinstance(v, int) and v == 0 and k not in ("order", "quantity"):
            continue
        else:
            result[k] = v
    return result
