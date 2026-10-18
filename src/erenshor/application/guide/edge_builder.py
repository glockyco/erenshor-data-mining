"""Edge construction for the Adventure Guide entity graph.

Each builder maps one relationship family from the clean database into graph
edges. The orchestration function below preserves the historical build order.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import TYPE_CHECKING

from erenshor.application.processor.gates import SHIVER_MEET_ALL

from .schema import AtomKind, Edge, EdgeType, Gate, GateAtom, NodeType, SubjectKind

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
    _add_quest_chain_edges(conn, graph)
    _add_quest_also_completes_edges(conn, graph)
    _add_quest_faction_edges(conn, graph)
    _add_gates(conn, graph)
    _add_target_entries(conn, graph)
    _add_quest_step_edges(conn, graph)
    _add_quest_dialog_prerequisite_edges(conn, graph)
    _add_character_spawn_edges(conn, graph)
    _add_character_faction_edges(conn, graph)
    _add_spawn_point_protector_edges(conn, graph)
    _add_zone_line_connect_edges(conn, graph)
    _add_zone_connect_edges(conn, graph, scene_to_zone)
    _add_zone_contain_edges(conn, graph, scene_to_zone)
    _add_item_quest_edges(conn, graph)
    _add_item_spell_edges(conn, graph)


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


def _add_quest_chain_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Quest chains from completion grants and canonical scripted acquisitions."""
    rows = conn.execute("""
        SELECT quest_stable_key, assign_new_quest_on_complete_stable_key
        FROM quest_variants
        WHERE assign_new_quest_on_complete_stable_key IS NOT NULL
        UNION
        SELECT source_stable_key AS quest_stable_key,
               quest_stable_key AS assign_new_quest_on_complete_stable_key
        FROM quest_acquisition_sources
        WHERE method = 'quest_chain' AND source_type = 'quest' AND source_stable_key IS NOT NULL
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


def _add_target_entries(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Zone lines that alone reach a target, from target_entries."""
    rows = conn.execute("SELECT target_stable_key, zone_line_stable_key FROM target_entries ORDER BY 1, 2")
    for target, line in rows:
        graph.add_entry(target, line)


def _add_gates(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Gates from gate_conditions, with the DB names of the quests they name."""
    rows = conn.execute("""
        SELECT subject_kind, subject_stable_key, item_stable_key, gate, group_index,
               atom_kind, atom_stable_key, atom_slot, atom_quantity
        FROM gate_conditions
        ORDER BY subject_kind, subject_stable_key, item_stable_key, gate, group_index,
                 atom_kind, atom_stable_key, atom_slot
    """)
    groups: dict[tuple[str, str, str | None, str], dict[int, list[GateAtom]]] = defaultdict(lambda: defaultdict(list))
    quest_keys: set[str] = set()
    for r in rows:
        atom_kind = AtomKind(r["atom_kind"])
        instruction = (
            _planning_slot_instruction(conn, r["subject_stable_key"], r["atom_slot"], r["atom_stable_key"])
            if atom_kind == AtomKind.PLANNING_SLOT_ITEM
            else None
        )
        atom = GateAtom(
            atom_kind,
            r["atom_stable_key"],
            r["atom_slot"],
            instruction,
            quantity=r["atom_quantity"] if r["atom_quantity"] is not None else 1,
        )
        if atom.kind in (AtomKind.QUEST_DONE, AtomKind.QUEST_NOT_DONE):
            quest_keys.add(atom.ref)
        subject = (r["subject_kind"], r["subject_stable_key"], r["item_stable_key"], r["gate"])
        groups[subject][r["group_index"]].append(atom)
    for (kind, subject_key, item_key, gate), by_index in groups.items():
        graph.add_gate(
            Gate(
                subject_kind=SubjectKind(kind),
                subject_key=subject_key,
                gate=gate,
                groups=tuple(tuple(by_index[index]) for index in sorted(by_index)),
                item_key=item_key,
            )
        )
    db_names = dict(conn.execute("SELECT stable_key, db_name FROM quests WHERE db_name IS NOT NULL"))
    for key in sorted(quest_keys):
        if key not in db_names:
            raise ValueError(f"gate names quest {key!r}, which has no DB name")
        graph.add_quest_db_name(key, db_names[key])


def _planning_slot_instruction(conn: sqlite3.Connection, line: str, slot: str, item: str) -> str:
    rows = conn.execute(
        """
        SELECT p.slot_kind, i.display_name AS item_name, z.display_name AS destination_name
        FROM planning_portal_slots p
        JOIN zone_lines l ON l.stable_key = p.zone_line_stable_key
        JOIN zones z ON z.stable_key = l.destination_zone_stable_key
        JOIN items i ON i.stable_key = ?
        WHERE p.zone_line_stable_key = ? AND p.slot = ?
        """,
        (item, line, slot),
    ).fetchall()
    if len(rows) != 1 or not rows[0]["item_name"] or not rows[0]["destination_name"]:
        raise ValueError(f"Missing or ambiguous planning-slot instruction: {line}.{slot}")
    row = rows[0]
    if row["slot_kind"] == "dedicated":
        return f"Place {row['item_name']} in the planning-table slot for {row['destination_name']}."
    if row["slot_kind"] == "rune":
        return f"Place {row['item_name']} in a rune slot on your planning table."
    raise ValueError(f"Unknown planning-slot role {row['slot_kind']!r} for {line}.{slot}")


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
        # The event finishes only after every keeper conversation.
        if not acquisition and quest_key == SHIVER_MEET_ALL:
            continue
        if len(targets) > 1:
            group = f"{prefix}:{quest_key}"
            for target_key in targets:
                groups[(quest_key, target_key)] = group
    return groups


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
