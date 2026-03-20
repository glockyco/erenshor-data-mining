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
from dataclasses import asdict
from pathlib import Path

from loguru import logger

from .schema import (
    AcquisitionSource,
    ChainLink,
    CompletionSource,
    DropSource,
    FactionEffect,
    QuestFlags,
    QuestGuide,
    QuestStep,
    QuestType,
    RequiredItemInfo,
    Rewards,
    VendorSource,
)


def generate(db_path: Path) -> list[QuestGuide]:
    """Generate quest guide entries for all quests in the database.

    Args:
        db_path: Path to the processed SQLite database.

    Returns:
        List of QuestGuide entries, one per unique quest.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        guides = _build_all_guides(conn)
        logger.info(f"Generated {len(guides)} quest guide entries")
        return guides
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _build_all_guides(conn: sqlite3.Connection) -> list[QuestGuide]:
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

    guides: list[QuestGuide] = []
    for quest in quests:
        sk = quest["stable_key"]
        variant_rn = quest["resource_name"]

        acquisition = acquisition_map.get(sk, [])
        completion = completion_map.get(sk, [])
        required_items = _build_required_items(
            variant_rn, required_items_map, drop_sources_map, vendor_sources_map, item_names
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
               COALESCE(c.display_name, i.display_name, z.display_name, qv.quest_name) AS source_name,
               COALESCE(sz.display_name, '') AS zone_name
        FROM quest_acquisition_sources qas
        LEFT JOIN characters c
            ON c.stable_key = qas.source_stable_key AND qas.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qas.source_stable_key AND qas.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qas.source_stable_key AND qas.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qas.source_stable_key AND qas.source_type = 'quest'
        LEFT JOIN character_spawns cs
            ON cs.character_stable_key = qas.source_stable_key AND qas.source_type = 'character'
        LEFT JOIN zones sz ON sz.stable_key = cs.zone_stable_key
        GROUP BY qas.quest_stable_key, qas.method, qas.source_stable_key
        """
    ).fetchall()
    result: dict[str, list[AcquisitionSource]] = {}
    for row in rows:
        src = AcquisitionSource(
            method=row["method"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_stable_key=row["source_stable_key"],
            zone_name=row["zone_name"] or None,
            note=row["note"],
        )
        result.setdefault(row["quest_stable_key"], []).append(src)
    return result


def _fetch_completion_sources(conn: sqlite3.Connection) -> dict[str, list[CompletionSource]]:
    rows = conn.execute(
        """
        SELECT qcs.quest_stable_key, qcs.method, qcs.source_type,
               qcs.source_stable_key, qcs.note,
               COALESCE(c.display_name, i.display_name, z.display_name, qv.quest_name) AS source_name,
               COALESCE(sz.display_name, '') AS zone_name
        FROM quest_completion_sources qcs
        LEFT JOIN characters c
            ON c.stable_key = qcs.source_stable_key AND qcs.source_type = 'character'
        LEFT JOIN items i
            ON i.stable_key = qcs.source_stable_key AND qcs.source_type = 'item'
        LEFT JOIN zones z
            ON z.stable_key = qcs.source_stable_key AND qcs.source_type = 'zone'
        LEFT JOIN quest_variants qv
            ON qv.quest_stable_key = qcs.source_stable_key AND qcs.source_type = 'quest'
        LEFT JOIN character_spawns cs
            ON cs.character_stable_key = qcs.source_stable_key AND qcs.source_type = 'character'
        LEFT JOIN zones sz ON sz.stable_key = cs.zone_stable_key
        GROUP BY qcs.quest_stable_key, qcs.method, qcs.source_stable_key
        """
    ).fetchall()
    result: dict[str, list[CompletionSource]] = {}
    for row in rows:
        src = CompletionSource(
            method=row["method"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_stable_key=row["source_stable_key"],
            zone_name=row["zone_name"] or None,
            note=row["note"],
        )
        result.setdefault(row["quest_stable_key"], []).append(src)
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
        QuestType.FETCH.value: lambda: _steps_fetch(step, giver, required_items, completion, zone_context),
        QuestType.KILL.value: lambda: _steps_kill(step, giver, completion),
        QuestType.DIALOG.value: lambda: _steps_dialog(step, giver, completion),
        QuestType.ZONE_TRIGGER.value: lambda: _steps_zone_trigger(step, giver, completion),
        QuestType.SHOUT.value: lambda: _steps_shout(step, giver, completion, shout_keywords),
        QuestType.ITEM_READ.value: lambda: _steps_item_read(step, completion),
    }
    gen = generators.get(quest_type)
    # Scripted, chain, hybrid -- can't auto-generate
    return gen() if gen else []


def _find_giver(acquisition: list[AcquisitionSource]) -> AcquisitionSource | None:
    """Find the primary quest giver from acquisition sources."""
    for acq in acquisition:
        if acq.method == "dialog":
            return acq
    # Fall back to any acquisition source
    return acquisition[0] if acquisition else None


StepFactory = type  # type alias for the closure


def _steps_fetch(step, giver, required_items, completion, zone_context):
    steps = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name or zone_context,
            )
        )
    for ri in required_items:
        desc = f"Collect {ri.item_name}"
        if ri.quantity > 1:
            desc = f"Collect {ri.quantity}x {ri.item_name}"
        if ri.drop_sources:
            names = ", ".join(sorted({ds.character_name for ds in ri.drop_sources[:3]}))
            desc += f" (drops from {names})"
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


def _steps_item_read(step, completion):
    steps = []
    for comp in completion:
        if comp.method == "read" and comp.source_name:
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
