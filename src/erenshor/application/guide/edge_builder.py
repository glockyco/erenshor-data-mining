"""Edge construction for the Adventure Guide entity graph.

Each builder maps one relationship family from the clean database into graph
edges. The orchestration function below preserves the historical build order.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .schema import Edge, EdgeType, NodeType

if TYPE_CHECKING:
    from .graph import EntityGraph


def build_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """Add every relationship edge in the established deterministic order."""
    _add_quest_acquisition_edges(conn, graph)
    _add_quest_completion_edges(conn, graph)
    _add_quest_required_item_edges(conn, graph)
    _add_quest_chain_edges(conn, graph)
    _add_quest_also_completes_edges(conn, graph)
    _add_quest_reward_edges(conn, graph)
    _add_quest_faction_edges(conn, graph)
    _add_quest_unlock_zone_line_edges(conn, graph)
    _add_quest_unlock_character_edges(conn, graph)
    _add_quest_step_edges(conn, graph)
    _add_quest_dialog_prerequisite_edges(conn, graph)
    _add_character_drop_edges(conn, graph)
    _add_character_vendor_edges(conn, graph)
    _add_vendor_quest_unlock_edges(conn, graph)
    _add_character_dialog_give_edges(conn, graph)
    _add_character_spawn_edges(conn, graph)
    _add_character_faction_edges(conn, graph)
    _add_spawn_point_gate_edges(conn, graph)
    _add_spawn_point_stop_edges(conn, graph)
    _add_spawn_point_protector_edges(conn, graph)
    _add_zone_line_connect_edges(conn, graph)
    _add_zone_connect_edges(conn, graph, scene_to_zone)
    _add_zone_contain_edges(conn, graph, scene_to_zone)
    _add_mining_yield_edges(conn, graph)
    _add_water_yield_edges(conn, graph)
    _add_item_bag_yield_edges(conn, graph)
    _add_crafting_edges(conn, graph)
    _add_item_craft_edges(conn, graph)
    _add_item_quest_edges(conn, graph)
    _add_item_spell_edges(conn, graph)
    _add_item_door_edges(conn, graph)


def _add_quest_acquisition_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → source (ASSIGNED_BY) from quest_acquisition_sources + quest_character_roles.

    Handles all 6 acquisition methods:
    - dialog: NPC gives quest via conversation (keyword)
    - item_read: reading an item assigns the quest
    - zone_entry: entering a zone assigns the quest
    - quest_chain: completing another quest assigns this one
    - partial_turnin: partial item turn-in assigns the quest
    - scripted: hardcoded game event assigns the quest

    Quests with no acquisition source are implicitly completable:
    the player can walk up and complete them without formal acceptance.
    """
    alternative_groups = _quest_source_alternative_groups(conn, graph, acquisition=True)
    rows = conn.execute("""
        SELECT quest_stable_key, method, source_type, source_stable_key, note
        FROM quest_acquisition_sources
    """)
    seen: set[tuple[str, str | None]] = set()
    for r in rows:
        quest_key = r["quest_stable_key"]
        target_key = r["source_stable_key"]
        method = r["method"]

        # Skip if nodes don't exist in graph
        if not graph.has_node(quest_key):
            continue
        if target_key and not graph.has_node(target_key):
            continue

        pair = (quest_key, target_key)
        if pair in seen:
            continue
        seen.add(pair)

        # Determine keyword for dialog-based assignments
        keyword = None
        if method == "dialog" and target_key:
            keyword = _find_dialog_keyword(conn, target_key, quest_key, "assign")

        if target_key:
            # For non-dialog methods, store the method as note so the C#
            # side knows the assignment mechanism (quest_chain, partial_turnin, etc.)
            note = r["note"]
            if not note and method != "dialog":
                note = method
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=target_key,
                    type=EdgeType.ASSIGNED_BY,
                    keyword=keyword,
                    group=alternative_groups.get((quest_key, target_key)),
                    note=note,
                )
            )

    # Giver role fallback: quest_character_roles 'giver' entries that
    # don't already have an acquisition source edge.
    rows = conn.execute("""
        SELECT quest_stable_key, character_stable_key
        FROM quest_character_roles
        WHERE role = 'giver'
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["character_stable_key"]
        pair = (quest_key, char_key)
        if pair in seen:
            continue
        seen.add(pair)
        if not graph.has_node(quest_key) or not graph.has_node(char_key):
            continue
        keyword = _find_dialog_keyword(conn, char_key, quest_key, "assign")
        graph.add_edge(
            Edge(
                source=quest_key,
                target=char_key,
                type=EdgeType.ASSIGNED_BY,
                group=alternative_groups.get((quest_key, char_key)),
                keyword=keyword,
            )
        )


def _add_quest_completion_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → character/zone/item (COMPLETED_BY) from quest_completion_sources."""
    alternative_groups = _quest_source_alternative_groups(conn, graph, acquisition=False)
    rows = conn.execute("""
        SELECT DISTINCT quest_stable_key, method, source_type, source_stable_key, note
        FROM quest_completion_sources
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        target = r["source_stable_key"]
        if not quest_key or not target:
            continue
        pair = (quest_key, target)
        if not graph.has_node(quest_key) or not graph.has_node(target):
            continue
        keyword = None
        if r["source_type"] == "character" and r["method"] in {"item_turnin", "talk"}:
            keyword = _find_dialog_keyword(conn, target, quest_key, "complete")

        graph.add_edge(
            Edge(
                source=quest_key,
                target=target,
                type=EdgeType.COMPLETED_BY,
                group=alternative_groups.get(pair),
                keyword=keyword,
                note=r["note"],
            )
        )


def _add_quest_required_item_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (REQUIRES_ITEM) from quest_required_items.

    For multi-variant quests (same quest_stable_key, different variants),
    items from different variants are OR-grouped: the player needs any
    one variant's items, not all variants' items.  Items within the same
    variant are AND (all required).  Single-variant quests get no group
    (unconditional).
    """
    rows = conn.execute("""
        SELECT qri.quest_variant_resource_name, qri.item_stable_key, qri.quantity,
               qv.quest_stable_key
        FROM quest_required_items qri
        JOIN quest_variants qv ON qv.resource_name = qri.quest_variant_resource_name
    """)
    # Check which quests have multiple distinct variants (count resource_names,
    # not rows — a single variant with N items must not be treated as N variants).
    variant_resource_names: dict[str, set[str]] = {}
    for r in rows:
        qk = r["quest_stable_key"]
        variant_resource_names.setdefault(qk, set()).add(r["quest_variant_resource_name"])
    is_multi_variant = {qk: len(names) > 1 for qk, names in variant_resource_names.items()}

    # Re-execute to iterate (sqlite3 cursors are single-pass)
    rows = conn.execute("""
        SELECT qri.quest_variant_resource_name, qri.item_stable_key, qri.quantity,
               qv.quest_stable_key
        FROM quest_required_items qri
        JOIN quest_variants qv ON qv.resource_name = qri.quest_variant_resource_name
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        item_key = r["item_stable_key"]
        if not graph.has_node(quest_key) or not graph.has_node(item_key):
            continue
        # Use variant resource_name as group only for genuinely multi-variant quests.
        group = r["quest_variant_resource_name"] if is_multi_variant.get(quest_key) else None
        graph.add_edge(
            Edge(
                source=quest_key,
                target=item_key,
                type=EdgeType.REQUIRES_ITEM,
                quantity=r["quantity"],
                group=group,
            )
        )


def _add_quest_chain_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (CHAINS_TO) from quest_variants.assign_new_quest_on_complete_stable_key."""
    rows = conn.execute("""
        SELECT quest_stable_key, assign_new_quest_on_complete_stable_key
        FROM quest_variants
        WHERE assign_new_quest_on_complete_stable_key IS NOT NULL
    """)
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["assign_new_quest_on_complete_stable_key"]
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.CHAINS_TO))


def _add_quest_also_completes_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (ALSO_COMPLETES) from quest_complete_other_quests."""
    rows = conn.execute("""
        SELECT qv.quest_stable_key, qcoq.completed_quest_stable_key
        FROM quest_complete_other_quests qcoq
        JOIN quest_variants qv ON qv.resource_name = qcoq.quest_variant_resource_name
    """)
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["completed_quest_stable_key"]
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.ALSO_COMPLETES))


def _add_quest_reward_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (REWARDS_ITEM) from quest_variants.item_on_complete_stable_key.

    When different variants of the same quest reward different items, each edge
    carries group=resource_name so the renderer can show per-variant outcomes.
    When all variants give the same item (or only one variant has a reward),
    a single ungrouped edge is emitted instead.
    """
    rows = conn.execute("""
        SELECT quest_stable_key, resource_name, item_on_complete_stable_key
        FROM quest_variants
        WHERE item_on_complete_stable_key IS NOT NULL
    """).fetchall()

    # Group by quest: {quest_key: {resource_name: item_key}}
    by_quest: dict[str, dict[str, str]] = {}
    for r in rows:
        by_quest.setdefault(r["quest_stable_key"], {})[r["resource_name"]] = r["item_on_complete_stable_key"]

    for quest_key, variant_rewards in by_quest.items():
        if not graph.has_node(quest_key):
            continue
        distinct_items = set(variant_rewards.values())
        if len(distinct_items) <= 1:
            # All variants give the same item — one ungrouped edge, no duplication.
            item_key = next(iter(distinct_items))
            if graph.has_node(item_key):
                graph.add_edge(Edge(source=quest_key, target=item_key, type=EdgeType.REWARDS_ITEM))
        else:
            # Different rewards per variant — group each edge by variant so the
            # renderer can show which recipe produces which item.
            for resource_name, item_key in variant_rewards.items():
                if graph.has_node(item_key):
                    graph.add_edge(
                        Edge(source=quest_key, target=item_key, type=EdgeType.REWARDS_ITEM, group=resource_name)
                    )


def _add_quest_faction_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → faction (AFFECTS_FACTION) from quest_faction_affects.

    Deduplicated across variants: same (quest, faction) only emits once.
    """
    rows = conn.execute("""
        SELECT DISTINCT qv.quest_stable_key, qfa.faction_stable_key, qfa.modifier_value
        FROM quest_faction_affects qfa
        JOIN quest_variants qv ON qv.resource_name = qfa.quest_variant_resource_name
    """)
    seen: set[tuple[str, str]] = set()
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["faction_stable_key"]
        pair = (src, tgt)
        if pair in seen:
            continue
        seen.add(pair)
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(
            Edge(
                source=src,
                target=tgt,
                type=EdgeType.AFFECTS_FACTION,
                amount=r["modifier_value"],
            )
        )


def _add_quest_unlock_zone_line_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → zone_line (UNLOCKS_ZONE_LINE) from zone_line_quest_unlocks.

    Uses unlock_group for AND/OR semantics: edges in the same group are
    AND (all quests in the group must be complete), different groups are
    OR (any complete group unlocks the zone line).
    """
    rows = conn.execute("""
        SELECT zone_line_stable_key, unlock_group, quest_db_name
        FROM zone_line_quest_unlocks
    """)
    # quest_db_name needs resolution to stable_key
    db_to_key = _quest_dbname_to_key(conn)
    for r in rows:
        zl_key = r["zone_line_stable_key"]
        quest_key = db_to_key.get(r["quest_db_name"])
        if not quest_key or not graph.has_node(zl_key) or not graph.has_node(quest_key):
            continue
        # Edge goes from quest → zone_line (completing quest unlocks zone line)
        graph.add_edge(
            Edge(
                source=quest_key,
                target=zl_key,
                type=EdgeType.UNLOCKS_ZONE_LINE,
                group=str(r["unlock_group"]),
            )
        )


def _add_quest_unlock_character_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → character (UNLOCKS_CHARACTER) from character_quest_unlocks."""
    rows = conn.execute("""
        SELECT character_stable_key, unlock_group, quest_db_name
        FROM character_quest_unlocks
    """)
    db_to_key = _quest_dbname_to_key(conn)
    for r in rows:
        char_key = r["character_stable_key"]
        quest_key = db_to_key.get(r["quest_db_name"])
        if not quest_key or not graph.has_node(char_key) or not graph.has_node(quest_key):
            continue
        graph.add_edge(
            Edge(
                source=quest_key,
                target=char_key,
                type=EdgeType.UNLOCKS_CHARACTER,
                group=str(r["unlock_group"]),
            )
        )


def _add_quest_step_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Build step edges from various game data sources.

    Step edges encode the quest walkthrough: talk to NPC, kill NPC,
    travel to zone, shout at NPC, read item.  Sources:
    - Kill: characters.quest_complete_on_death
    - Travel: zones.complete_quest_on_enter_stable_key
    - Read: items.complete_on_read_stable_key
    - Talk: quest_completion_sources (method='talk')
    - Shout: characters.shout_trigger_quest_stable_key
    """
    completion_groups = _quest_source_alternative_groups(conn, graph, acquisition=False)

    # Travel steps from zone-triggered quests
    rows = conn.execute("""
        SELECT stable_key, complete_quest_on_enter_stable_key,
               complete_second_quest_on_enter_stable_key
        FROM zones
        WHERE complete_quest_on_enter_stable_key IS NOT NULL
           OR complete_second_quest_on_enter_stable_key IS NOT NULL
    """)
    for r in rows:
        zone_key = r["stable_key"]
        for col in ("complete_quest_on_enter_stable_key", "complete_second_quest_on_enter_stable_key"):
            quest_key = r[col]
            if quest_key and graph.has_node(quest_key) and graph.has_node(zone_key):
                graph.add_edge(
                    Edge(
                        source=quest_key,
                        target=zone_key,
                        type=EdgeType.STEP_TRAVEL,
                        group=completion_groups.get((quest_key, zone_key)),
                    )
                )

    # Read steps from items that complete quests
    rows = conn.execute("""
        SELECT stable_key, complete_on_read_stable_key
        FROM items
        WHERE complete_on_read_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        quest_key = r["complete_on_read_stable_key"]
        if graph.has_node(item_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=item_key,
                    group=completion_groups.get((quest_key, item_key)),
                    type=EdgeType.STEP_READ,
                )
            )

    # Kill steps from characters.quest_complete_on_death
    rows = conn.execute("""
        SELECT stable_key, quest_complete_on_death
        FROM characters
        WHERE quest_complete_on_death IS NOT NULL
    """)
    for r in rows:
        char_key = r["stable_key"]
        quest_key = r["quest_complete_on_death"]
        if graph.has_node(char_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    group=completion_groups.get((quest_key, char_key)),
                    type=EdgeType.STEP_KILL,
                )
            )

    # Talk steps from quest_completion_sources where method is 'talk'
    rows = conn.execute("""
        SELECT quest_stable_key, source_stable_key
        FROM quest_completion_sources
        WHERE method = 'talk' AND source_type = 'character'
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["source_stable_key"]
        if not quest_key or not char_key:
            continue
        if graph.has_node(quest_key) and graph.has_node(char_key):
            keyword = _find_dialog_keyword(conn, char_key, quest_key, "complete")
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    type=EdgeType.STEP_TALK,
                    keyword=keyword,
                    group=completion_groups.get((quest_key, char_key)),
                )
            )

    # Shout steps from characters with shout_trigger_quest_stable_key
    rows = conn.execute("""
        SELECT stable_key, shout_trigger_quest_stable_key, shout_trigger_keyword
        FROM characters
        WHERE shout_trigger_quest_stable_key IS NOT NULL
              AND shout_trigger_quest_stable_key != ''
    """)
    for r in rows:
        char_key = r["stable_key"]
        quest_key = r["shout_trigger_quest_stable_key"]
        if graph.has_node(char_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    type=EdgeType.STEP_SHOUT,
                    keyword=r["shout_trigger_keyword"],
                )
            )


def _add_quest_dialog_prerequisite_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (REQUIRES_QUEST) from character_dialogs.required_quest_stable_key."""
    rows = conn.execute("""
        SELECT required_quest_stable_key, complete_quest_stable_key
        FROM character_dialogs
        WHERE required_quest_stable_key IS NOT NULL
          AND complete_quest_stable_key IS NOT NULL
    """)
    for r in rows:
        src = r["complete_quest_stable_key"]
        tgt = r["required_quest_stable_key"]
        if src == tgt:
            continue
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.REQUIRES_QUEST))


def _add_character_drop_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (DROPS_ITEM) from loot_drops."""
    rows = conn.execute("""
        SELECT character_stable_key, item_stable_key, drop_probability
        FROM loot_drops
    """)
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["item_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["item_stable_key"],
                type=EdgeType.DROPS_ITEM,
                chance=r["drop_probability"],
            )
        )


def _add_character_vendor_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (SELLS_ITEM) from character_vendor_items."""
    rows = conn.execute("SELECT character_stable_key, item_stable_key FROM character_vendor_items")
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["item_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["item_stable_key"],
                type=EdgeType.SELLS_ITEM,
            )
        )


def _add_vendor_quest_unlock_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (UNLOCKS_VENDOR_ITEM) for quest-unlocked vendor inventory.

    Also emits a SELLS_ITEM edge from vendor → item so the item appears in
    obtainability chains.
    """
    rows = conn.execute("""
        SELECT cvqu.character_stable_key,
               cvqu.quest_stable_key,
               qv.unlock_item_for_vendor_stable_key
        FROM character_vendor_quest_unlocks cvqu
        JOIN quest_variants qv ON qv.quest_stable_key = cvqu.quest_stable_key
            AND qv.resource_name = (
                SELECT MIN(qv2.resource_name)
                FROM quest_variants qv2
                WHERE qv2.quest_stable_key = cvqu.quest_stable_key
            )
        WHERE qv.unlock_item_for_vendor_stable_key IS NOT NULL
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["character_stable_key"]
        item_key = r["unlock_item_for_vendor_stable_key"]
        if not graph.has_node(quest_key) or not graph.has_node(item_key):
            continue
        # Quest → item: shown in rewards section with vendor name from note
        graph.add_edge(
            Edge(
                source=quest_key,
                target=item_key,
                type=EdgeType.UNLOCKS_VENDOR_ITEM,
                note=char_key,  # vendor character key for display name lookup
            )
        )
        # Vendor → item: for item obtainability chains
        if graph.has_node(char_key):
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=item_key,
                    type=EdgeType.SELLS_ITEM,
                )
            )


def _add_character_dialog_give_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (GIVES_ITEM) from character_dialogs.give_item_stable_key."""
    rows = conn.execute("""
        SELECT character_stable_key, give_item_stable_key, keywords
        FROM character_dialogs
        WHERE give_item_stable_key IS NOT NULL
    """)
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["give_item_stable_key"]):
            continue
        # keywords is comma-separated; take first as the primary keyword
        keywords = r["keywords"]
        keyword = keywords.split(",")[0].strip() if keywords else None
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["give_item_stable_key"],
                type=EdgeType.GIVES_ITEM,
                keyword=keyword,
            )
        )


def _add_character_spawn_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character ↔ spawn_point edges.

    character → spawn_point (HAS_SPAWN)
    spawn_point → character (SPAWNS_CHARACTER)
    character → zone (SPAWNS_IN) — one edge per distinct zone
    """
    rows = conn.execute("""
        SELECT character_stable_key, spawn_point_stable_key,
               zone_stable_key, spawn_chance, is_rare
        FROM character_spawns
        WHERE COALESCE(is_map_visible, 1) = 1 AND spawn_point_stable_key IS NOT NULL
    """)
    char_zones: dict[str, set[str]] = {}
    for r in rows:
        char_key = r["character_stable_key"]
        sp_key = r["spawn_point_stable_key"]
        zone_key = r["zone_stable_key"]

        if graph.has_node(char_key) and graph.has_node(sp_key):
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=sp_key,
                    type=EdgeType.HAS_SPAWN,
                )
            )
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=char_key,
                    type=EdgeType.SPAWNS_CHARACTER,
                    chance=r["spawn_chance"],
                )
            )

        # Track zones for SPAWNS_IN dedup
        if zone_key and graph.has_node(char_key) and graph.has_node(zone_key):
            char_zones.setdefault(char_key, set()).add(zone_key)

    for char_key, zones in char_zones.items():
        for zone_key in sorted(zones):
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=zone_key,
                    type=EdgeType.SPAWNS_IN,
                )
            )


def _add_character_faction_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → faction (BELONGS_TO_FACTION) from characters.my_world_faction_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, my_world_faction_stable_key
        FROM characters
        WHERE my_world_faction_stable_key IS NOT NULL AND is_map_visible = 1
    """)
    for r in rows:
        if not graph.has_node(r["stable_key"]) or not graph.has_node(r["my_world_faction_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["stable_key"],
                target=r["my_world_faction_stable_key"],
                type=EdgeType.BELONGS_TO_FACTION,
            )
        )


def _add_spawn_point_gate_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """spawn_point → quest (GATED_BY_QUEST) from character_spawns.spawn_upon_quest_complete_stable_key."""
    rows = conn.execute("""
        SELECT DISTINCT spawn_point_stable_key, spawn_upon_quest_complete_stable_key
        FROM character_spawns
        WHERE spawn_upon_quest_complete_stable_key IS NOT NULL AND spawn_point_stable_key IS NOT NULL
    """)
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        quest_key = r["spawn_upon_quest_complete_stable_key"]
        if graph.has_node(sp_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=quest_key,
                    type=EdgeType.GATED_BY_QUEST,
                )
            )


def _add_spawn_point_stop_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """spawn_point → quest (STOPS_AFTER_QUEST) from spawn_point_stop_quests."""
    rows = conn.execute("SELECT spawn_point_stable_key, quest_stable_key FROM spawn_point_stop_quests")
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        quest_key = r["quest_stable_key"]
        if graph.has_node(sp_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=quest_key,
                    type=EdgeType.STOPS_AFTER_QUEST,
                )
            )


def _add_spawn_point_protector_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → character (PROTECTS) from character_spawns.protector_stable_key."""
    rows = conn.execute("""
        SELECT DISTINCT character_stable_key, protector_stable_key
        FROM character_spawns
        WHERE protector_stable_key IS NOT NULL
    """)
    for r in rows:
        protector = r["protector_stable_key"]
        protected = r["character_stable_key"]
        if graph.has_node(protector) and graph.has_node(protected):
            graph.add_edge(
                Edge(
                    source=protector,
                    target=protected,
                    type=EdgeType.PROTECTS,
                )
            )


def _add_zone_line_connect_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """zone_line → zone (CONNECTS_ZONES) for the destination zone."""
    rows = conn.execute("""
        SELECT stable_key, destination_zone_stable_key
        FROM zone_lines
        WHERE destination_zone_stable_key IS NOT NULL
    """)
    for r in rows:
        zl_key = r["stable_key"]
        zone_key = r["destination_zone_stable_key"]
        if graph.has_node(zl_key) and graph.has_node(zone_key):
            graph.add_edge(
                Edge(
                    source=zl_key,
                    target=zone_key,
                    type=EdgeType.CONNECTS_ZONES,
                )
            )


def _add_zone_connect_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """zone → zone (CONNECTS_TO) derived from zone lines.

    If zone A has a zone line whose destination is zone B, then A connects_to B.
    Deduplicated: only one edge per (source_zone, dest_zone) pair.
    """
    rows = conn.execute("""
        SELECT zl.scene, zl.destination_zone_stable_key
        FROM zone_lines zl
        WHERE zl.destination_zone_stable_key IS NOT NULL
    """)
    seen: set[tuple[str, str]] = set()
    for r in rows:
        dest_zone = r["destination_zone_stable_key"]
        src_zone = scene_to_zone.get(r["scene"] or "")
        if not src_zone or src_zone == dest_zone:
            continue
        pair = (src_zone, dest_zone)
        if pair in seen:
            continue
        seen.add(pair)
        if graph.has_node(src_zone) and graph.has_node(dest_zone):
            graph.add_edge(
                Edge(
                    source=src_zone,
                    target=dest_zone,
                    type=EdgeType.CONNECTS_TO,
                )
            )


def _add_zone_contain_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """zone → resource nodes (CONTAINS) inferred from scene→zone mapping.

    Connects zones to their mining nodes, waters, forges, and item bags.
    """
    for node in graph.all_nodes():
        if (
            node.type in (NodeType.MINING_NODE, NodeType.WATER, NodeType.FORGE, NodeType.ITEM_BAG)
            and node.zone_key
            and graph.has_node(node.zone_key)
        ):
            graph.add_edge(
                Edge(
                    source=node.zone_key,
                    target=node.key,
                    type=EdgeType.CONTAINS,
                )
            )


def _add_mining_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """mining_node → item (YIELDS_ITEM) from mining_node_items."""
    rows = conn.execute("SELECT mining_node_stable_key, item_stable_key, drop_chance FROM mining_node_items")
    for r in rows:
        if graph.has_node(r["mining_node_stable_key"]) and graph.has_node(r["item_stable_key"]):
            graph.add_edge(
                Edge(
                    source=r["mining_node_stable_key"],
                    target=r["item_stable_key"],
                    type=EdgeType.YIELDS_ITEM,
                    chance=r["drop_chance"],
                )
            )


def _add_water_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """water → item (YIELDS_ITEM) from water_fishables, deduplicated per (water, item)."""
    rows = conn.execute("SELECT water_stable_key, item_stable_key, type, drop_chance FROM water_fishables")
    # Group by (water, item) to merge day/night entries.
    pairs: dict[tuple[str, str], dict[str, float | None]] = {}
    for r in rows:
        key = (r["water_stable_key"], r["item_stable_key"])
        if key not in pairs:
            pairs[key] = {}
        pairs[key][r["type"]] = r["drop_chance"]

    for (water_key, item_key), types in pairs.items():
        if not (graph.has_node(water_key) and graph.has_node(item_key)):
            continue

        has_day = "DayFishable" in types
        has_night = "NightFishable" in types
        if has_day and has_night:
            time_restriction = None
            chance = max(c for c in types.values() if c is not None) if any(types.values()) else None
        elif has_day:
            time_restriction = "day"
            chance = types.get("DayFishable")
        else:
            time_restriction = "night"
            chance = types.get("NightFishable")

        graph.add_edge(
            Edge(
                source=water_key,
                target=item_key,
                type=EdgeType.YIELDS_ITEM,
                chance=chance,
                time_restriction=time_restriction,
            )
        )


def _add_item_bag_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item_bag → item (YIELDS_ITEM) from item_bags.item_stable_key."""
    rows = conn.execute("SELECT stable_key, item_stable_key FROM item_bags WHERE item_stable_key IS NOT NULL")
    for r in rows:
        if graph.has_node(r["stable_key"]) and graph.has_node(r["item_stable_key"]):
            graph.add_edge(
                Edge(
                    source=r["stable_key"],
                    target=r["item_stable_key"],
                    type=EdgeType.YIELDS_ITEM,
                )
            )


def _add_crafting_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """recipe → item (REQUIRES_MATERIAL) + recipe → item (PRODUCES) from crafting tables."""
    # Materials
    rows = conn.execute("""
        SELECT recipe_item_stable_key, material_slot, material_item_stable_key, material_quantity
        FROM crafting_recipes
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["material_item_stable_key"]
        if graph.has_node(recipe_key) and graph.has_node(item_key):
            graph.add_edge(
                Edge(
                    source=recipe_key,
                    target=item_key,
                    type=EdgeType.REQUIRES_MATERIAL,
                    quantity=r["material_quantity"],
                    slot=r["material_slot"],
                )
            )

    # Mold (template item): the template is consumed on a successful craft.
    # Smithing.DoSuccess() clears Template.MyItem just like the ingredients,
    # confirming it is an ingredient. Its key is derived by stripping "recipe:"
    # from the recipe key — that naming convention is enforced by _add_recipe_nodes.
    # Slot 0 is reserved for the template; ingredient slots come from the DB.
    for recipe_node in graph.nodes_of_type(NodeType.RECIPE):
        template_key = recipe_node.key[len("recipe:") :]
        if graph.has_node(template_key):
            graph.add_edge(
                Edge(
                    source=recipe_node.key,
                    target=template_key,
                    type=EdgeType.REQUIRES_MATERIAL,
                    quantity=1,
                    slot=0,
                )
            )

    # Products
    rows = conn.execute("""
        SELECT recipe_item_stable_key, reward_slot, reward_item_stable_key, reward_quantity
        FROM crafting_rewards
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["reward_item_stable_key"]
        if graph.has_node(recipe_key) and graph.has_node(item_key):
            graph.add_edge(
                Edge(
                    source=recipe_key,
                    target=item_key,
                    type=EdgeType.PRODUCES,
                    quantity=r["reward_quantity"],
                    slot=r["reward_slot"],
                )
            )


def _add_item_craft_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → recipe (CRAFTED_FROM) — reverse link from product to recipe."""
    rows = conn.execute("""
        SELECT recipe_item_stable_key, reward_item_stable_key
        FROM crafting_rewards
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["reward_item_stable_key"]
        if graph.has_node(item_key) and graph.has_node(recipe_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=recipe_key,
                    type=EdgeType.CRAFTED_FROM,
                )
            )


def _add_item_quest_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → quest (ASSIGNS_QUEST / COMPLETES_QUEST) from items table."""
    rows = conn.execute("""
        SELECT stable_key, assign_quest_on_read_stable_key, complete_on_read_stable_key
        FROM items
        WHERE assign_quest_on_read_stable_key IS NOT NULL
           OR complete_on_read_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        if r["assign_quest_on_read_stable_key"]:
            quest_key = r["assign_quest_on_read_stable_key"]
            if graph.has_node(item_key) and graph.has_node(quest_key):
                graph.add_edge(
                    Edge(
                        source=item_key,
                        target=quest_key,
                        type=EdgeType.ASSIGNS_QUEST,
                    )
                )
        if r["complete_on_read_stable_key"]:
            quest_key = r["complete_on_read_stable_key"]
            if graph.has_node(item_key) and graph.has_node(quest_key):
                graph.add_edge(
                    Edge(
                        source=item_key,
                        target=quest_key,
                        type=EdgeType.COMPLETES_QUEST,
                    )
                )


def _add_item_spell_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → spell (TEACHES_SPELL) from items.teach_spell_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, teach_spell_stable_key
        FROM items
        WHERE teach_spell_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        spell_key = r["teach_spell_stable_key"]
        if graph.has_node(item_key) and graph.has_node(spell_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=spell_key,
                    type=EdgeType.TEACHES_SPELL,
                )
            )


def _add_item_door_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → door (UNLOCKS_DOOR) from doors.key_item_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, key_item_stable_key
        FROM doors
        WHERE key_item_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["key_item_stable_key"]
        door_key = r["stable_key"]
        if graph.has_node(item_key) and graph.has_node(door_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=door_key,
                    type=EdgeType.UNLOCKS_DOOR,
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _quest_source_alternative_groups(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    *,
    acquisition: bool,
) -> dict[tuple[str, str], str]:
    """Index grouped alternatives among valid quest source targets.

    Source rows are deduplicated by ``(quest, target)`` before counting, and
    rows whose quest or target node is absent are ignored.  The returned index
    contains only quests with multiple distinct valid targets, so a missing
    lookup means the edge should remain ungrouped.
    """
    table = "quest_acquisition_sources" if acquisition else "quest_completion_sources"
    targets_by_quest: dict[str, set[str]] = {}
    rows = conn.execute(f"""
        SELECT quest_stable_key, source_stable_key
        FROM {table}
    """)
    for row in rows:
        quest_key = row["quest_stable_key"]
        target_key = row["source_stable_key"]
        if not quest_key or not target_key or not graph.has_node(quest_key) or not graph.has_node(target_key):
            continue
        targets_by_quest.setdefault(quest_key, set()).add(target_key)

    if acquisition:
        rows = conn.execute("""
            SELECT quest_stable_key, character_stable_key
            FROM quest_character_roles
            WHERE role = 'giver'
        """)
        for row in rows:
            quest_key = row["quest_stable_key"]
            target_key = row["character_stable_key"]
            if quest_key and target_key and graph.has_node(quest_key) and graph.has_node(target_key):
                targets_by_quest.setdefault(quest_key, set()).add(target_key)

    prefix = "acquisition" if acquisition else "completion"
    groups: dict[tuple[str, str], str] = {}
    for quest_key, targets in targets_by_quest.items():
        if len(targets) > 1:
            group = f"{prefix}:{quest_key}"
            for target_key in targets:
                groups[(quest_key, target_key)] = group
    return groups


def _quest_dbname_to_key(conn: sqlite3.Connection) -> dict[str, str]:
    """Map quest db_name → stable_key."""
    rows = conn.execute("SELECT stable_key, db_name FROM quests WHERE db_name IS NOT NULL")
    return {r["db_name"]: r["stable_key"] for r in rows}


def _find_dialog_keyword(
    conn: sqlite3.Connection,
    character_key: str,
    quest_key: str,
    role: str,
) -> str | None:
    """Find the dialog keyword a player says to trigger quest assign/complete.

    Searches character_dialogs for a dialog entry that references the quest.
    """
    if role == "assign":
        row = conn.execute(
            "SELECT keywords FROM character_dialogs WHERE character_stable_key = ? AND assign_quest_stable_key = ?",
            (character_key, quest_key),
        ).fetchone()
    elif role == "complete":
        row = conn.execute(
            "SELECT keywords FROM character_dialogs WHERE character_stable_key = ? AND complete_quest_stable_key = ?",
            (character_key, quest_key),
        ).fetchone()
    else:
        return None

    if row and row["keywords"]:
        keywords: str = row["keywords"]
        return keywords.split(",")[0].strip()
    return None
