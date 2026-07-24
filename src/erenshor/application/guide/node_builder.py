"""Node construction for the Adventure Guide entity graph.

This module owns database-backed node builders and guide-only workflow facts.
The caller controls the shared SQLite connection and scene-to-zone lookup.
"""

from __future__ import annotations

import math
import sqlite3
from typing import TYPE_CHECKING

from .schema import Edge, EdgeType, Node, NodeType, WorkflowCycle, WorkflowTarget

if TYPE_CHECKING:
    from .graph import EntityGraph


def build_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """Add every entity node in the established deterministic order."""
    _add_quest_nodes(conn, graph)
    _add_item_nodes(conn, graph)
    _add_character_nodes(conn, graph, scene_to_zone)
    _add_zone_nodes(conn, graph)
    _add_zone_line_nodes(conn, graph, scene_to_zone)
    _add_spawn_point_nodes(conn, graph, scene_to_zone)
    _add_mining_node_nodes(conn, graph, scene_to_zone)
    _add_water_nodes(conn, graph, scene_to_zone)
    _add_forge_nodes(conn, graph, scene_to_zone)
    _add_item_bag_nodes(conn, graph, scene_to_zone)
    _add_recipe_nodes(conn, graph)
    _add_door_nodes(conn, graph, scene_to_zone)
    _add_faction_nodes(conn, graph)
    _add_spell_nodes(conn, graph)
    _add_skill_nodes(conn, graph)
    _add_teleport_nodes(conn, graph, scene_to_zone)
    _add_achievement_trigger_nodes(conn, graph, scene_to_zone)
    _add_secret_passage_nodes(conn, graph, scene_to_zone)
    _add_wishing_well_nodes(conn, graph, scene_to_zone)
    _add_treasure_location_nodes(conn, graph, scene_to_zone)
    _add_book_nodes(conn, graph)
    _add_class_nodes(conn, graph)
    _add_stance_nodes(conn, graph)
    _add_ascension_nodes(conn, graph)
    _add_guide_workflow_nodes_and_edges(conn, graph, scene_to_zone)


def _build_scene_to_zone(conn: sqlite3.Connection) -> dict[str, str]:
    """Map scene name → zone stable key for scene→zone resolution."""
    rows = conn.execute("SELECT stable_key, scene_name FROM zones WHERE scene_name IS NOT NULL")
    return {r["scene_name"]: r["stable_key"] for r in rows}


def _zone_display(conn: sqlite3.Connection) -> dict[str, str]:
    """Map zone stable key → display name."""
    rows = conn.execute("SELECT stable_key, display_name FROM zones")
    return {r["stable_key"]: r["display_name"] for r in rows}


def _resolve_zone(scene: str | None, scene_to_zone: dict[str, str]) -> str | None:
    """Resolve a scene name to a zone stable key, or None."""
    if scene is None:
        return None
    return scene_to_zone.get(scene)


def _zone_display_name(
    zone_key: str | None,
    zone_displays: dict[str, str],
    fallback: str | None = None,
) -> str | None:
    """Resolve zone key to display name, with optional fallback."""
    if zone_key is not None:
        name = zone_displays.get(zone_key)
        if name is not None:
            return name
    return fallback


# ---------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------


def _add_quest_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    # Determine which quests are implicitly completable (no acquisition source).
    # A quest with no row in quest_acquisition_sources AND no 'giver' role in
    # quest_character_roles can be completed without formal acceptance.
    explicit_quests: set[str] = set()
    for r in conn.execute("SELECT DISTINCT quest_stable_key FROM quest_acquisition_sources"):
        explicit_quests.add(r["quest_stable_key"])
    for r in conn.execute("SELECT DISTINCT quest_stable_key FROM quest_character_roles WHERE role = 'giver'"):
        explicit_quests.add(r["quest_stable_key"])

    # Some quests have multiple variants (e.g., Disarming the Sivakayans has
    # sword/sceptre variants).  Pick the primary variant per quest: the one
    # whose resource_name sorts first alphabetically.
    rows = conn.execute("""
        SELECT q.stable_key, q.db_name, q.display_name,
               qv.quest_desc, qv.xp_on_complete, qv.gold_on_complete,
               qv.item_on_complete_stable_key,
               qv.assign_new_quest_on_complete_stable_key,
               qv.repeatable, qv.disable_quest, qv.disable_text,
               qv.kill_turn_in_holder, qv.destroy_turn_in_holder,
               qv.drop_invuln_on_holder, qv.once_per_spawn_instance
        FROM quests q
        LEFT JOIN quest_variants qv ON qv.quest_stable_key = q.stable_key
            AND qv.resource_name = (
                SELECT MIN(qv2.resource_name)
                FROM quest_variants qv2
                WHERE qv2.quest_stable_key = q.stable_key
            )
        WHERE q.is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.QUEST,
                display_name=r["display_name"],
                db_name=r["db_name"],
                description=r["quest_desc"],
                xp_reward=r["xp_on_complete"],
                gold_reward=r["gold_on_complete"],
                reward_item_key=r["item_on_complete_stable_key"],
                repeatable=bool(r["repeatable"]),
                disabled=bool(r["disable_quest"]),
                disabled_text=r["disable_text"],
                implicit=r["stable_key"] not in explicit_quests,
                kill_turn_in_holder=bool(r["kill_turn_in_holder"]) if r["kill_turn_in_holder"] else False,
                destroy_turn_in_holder=bool(r["destroy_turn_in_holder"]) if r["destroy_turn_in_holder"] else False,
                drop_invuln_on_holder=bool(r["drop_invuln_on_holder"]) if r["drop_invuln_on_holder"] else False,
                once_per_spawn_instance=bool(r["once_per_spawn_instance"]) if r["once_per_spawn_instance"] else False,
            )
        )


def _add_item_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, item_level, stackable, is_unique,
               template, teach_spell_stable_key, assign_quest_on_read_stable_key,
               complete_on_read_stable_key, lore
        FROM items
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ITEM,
                display_name=r["display_name"],
                item_level=r["item_level"],
                stackable=bool(r["stackable"]),
                is_unique=bool(r["is_unique"]),
                template=bool(r["template"]),
                description=r["lore"],
            )
        )


def _add_character_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT stable_key, display_name, scene, x, y, z,
               level, is_vendor, is_friendly, invulnerable,
               my_world_faction_stable_key, is_enabled
        FROM characters
        WHERE is_map_visible = 1
    """)
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.CHARACTER,
                display_name=r["display_name"],
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                level=r["level"],
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_vendor=bool(r["is_vendor"]),
                is_friendly=bool(r["is_friendly"]),
                invulnerable=bool(r["invulnerable"]),
                faction_key=r["my_world_faction_stable_key"],
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
            )
        )


def _add_zone_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, scene_name, is_dungeon
        FROM zones
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ZONE,
                display_name=r["display_name"],
                scene=r["scene_name"],
                is_dungeon=bool(r["is_dungeon"]),
            )
        )


def _add_zone_line_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT zl.stable_key, zl.scene, zl.x, zl.y, zl.z,
               zl.is_enabled, zl.display_text,
               zl.destination_zone_stable_key,
               zl.landing_position_x, zl.landing_position_y, zl.landing_position_z,
               z.display_name AS dest_display
        FROM zone_lines zl
        LEFT JOIN zones z ON z.stable_key = zl.destination_zone_stable_key
    """)
    for r in rows:
        zone_key = _resolve_zone(r["scene"], scene_to_zone)
        # Display name: "Zone A → Zone B" or fallback to display_text
        dest = r["dest_display"] or "?"
        src_display = _zone_display_name(zone_key, zone_displays, r["scene"])
        display = f"{src_display} → {dest}"
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ZONE_LINE,
                display_name=display,
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=r["scene"],
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
                destination_zone_key=r["destination_zone_stable_key"],
                destination_display=dest,
                landing_x=r["landing_position_x"],
                landing_y=r["landing_position_y"],
                landing_z=r["landing_position_z"],
            )
        )


def _add_spawn_point_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT cs.spawn_point_stable_key, cs.character_stable_key,
               cs.scene, cs.x, cs.y, cs.z, cs.is_enabled,
               cs.night_spawn, cs.spawn_chance, cs.is_rare,
               cs.is_directly_placed, cs.is_trigger_spawn,
               cs.source_script,
               cs.zone_stable_key,
               c.display_name AS char_display
        FROM character_spawns cs
        JOIN characters c ON c.stable_key = cs.character_stable_key
        WHERE COALESCE(cs.is_map_visible, 1) = 1 AND cs.spawn_point_stable_key IS NOT NULL
        ORDER BY cs.spawn_point_stable_key, cs.source_script
    """)
    seen: set[str] = set()
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        if sp_key in seen:
            continue
        seen.add(sp_key)
        scene = r["scene"]
        zone_key = r["zone_stable_key"] or _resolve_zone(scene, scene_to_zone)
        # Respawn delay: average of the four spawn_delay columns
        graph.add_node(
            Node(
                key=sp_key,
                type=NodeType.SPAWN_POINT,
                display_name=r["char_display"],
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
                night_spawn=bool(r["night_spawn"]),
                spawn_chance=r["spawn_chance"],
                is_rare=bool(r["is_rare"]),
                is_directly_placed=bool(r["is_directly_placed"]),
                source_script=r["source_script"],
                is_trigger_spawn=bool(r["is_trigger_spawn"]),
            )
        )


def _add_mining_node_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, npc_name, respawn_time FROM mining_nodes")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.MINING_NODE,
                display_name=r["npc_name"] or "Mining Node",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                respawn_time=r["respawn_time"],
            )
        )


def _add_water_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM waters")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.WATER,
                display_name="Fishing",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_forge_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM forges")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.FORGE,
                display_name=f"Forge ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_item_bag_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT ib.stable_key, ib.scene, ib.x, ib.y, ib.z,
               ib.item_stable_key, ib.respawns, ib.respawn_timer,
               i.display_name AS item_display
        FROM item_bags ib
        LEFT JOIN items i ON i.stable_key = ib.item_stable_key
    """)
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        item_name = r["item_display"] or "Item"
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ITEM_BAG,
                display_name=f"{item_name} (pickup)",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                respawns=bool(r["respawns"]) if r["respawns"] is not None else True,
                respawn_time=r["respawn_timer"],
            )
        )


def _add_recipe_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Add recipe nodes for template items that are crafting bases."""
    rows = conn.execute("""
        SELECT DISTINCT cr.recipe_item_stable_key, i.display_name
        FROM crafting_recipes cr
        JOIN items i ON i.stable_key = cr.recipe_item_stable_key
    """)
    for r in rows:
        key = f"recipe:{r['recipe_item_stable_key']}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.RECIPE,
                display_name=f"Recipe: {r['display_name']}",
            )
        )


def _add_door_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, key_item_stable_key FROM doors")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.DOOR,
                display_name=f"Door ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                key_item_key=r["key_item_stable_key"],
            )
        )


def _add_faction_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, default_value, refname FROM factions")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.FACTION,
                display_name=r["display_name"],
                default_value=r["default_value"],
                refname=r["refname"],
            )
        )


def _add_spell_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, required_level, spell_desc
        FROM spells
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SPELL,
                display_name=r["display_name"],
                level=r["required_level"],
                description=r["spell_desc"],
            )
        )


def _add_skill_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, skill_desc FROM skills WHERE is_map_visible = 1")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SKILL,
                display_name=r["display_name"],
                description=r["skill_desc"],
            )
        )


def _add_teleport_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, teleport_item_stable_key FROM teleports")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.TELEPORT,
                display_name=f"Teleport ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                teleport_item_key=r["teleport_item_stable_key"],
            )
        )


def _add_achievement_trigger_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, achievement_name FROM achievement_triggers")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ACHIEVEMENT_TRIGGER,
                display_name=r["achievement_name"] or "Achievement",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                achievement_name=r["achievement_name"],
            )
        )


def _add_secret_passage_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute(
        """
        SELECT stable_key, scene, x, y, z, object_name
        FROM secret_passages
        WHERE is_excluded = 0
        """
    )
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SECRET_PASSAGE,
                display_name=r["object_name"] or "Secret Passage",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_wishing_well_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM wishing_wells")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.WISHING_WELL,
                display_name=f"Wishing Well ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_treasure_location_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM treasure_locations")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.TREASURE_LOCATION,
                display_name=f"Treasure ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_book_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Add one node per distinct book title."""
    rows = conn.execute("SELECT DISTINCT book_title FROM books")
    for r in rows:
        title = r["book_title"]
        key = f"book:{title}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.BOOK,
                display_name=title,
                book_title=title,
            )
        )


def _add_class_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT class_name, display_name FROM classes")
    for r in rows:
        key = f"class:{r['class_name']}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.CLASS,
                display_name=r["display_name"] or r["class_name"],
            )
        )


def _add_stance_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, stance_desc FROM stances WHERE is_map_visible = 1")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.STANCE,
                display_name=r["display_name"],
                description=r["stance_desc"],
            )
        )


def _add_ascension_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, skill_name, skill_desc FROM ascensions")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ASCENSION,
                display_name=r["skill_name"] or r["stable_key"],
                description=r["skill_desc"],
            )
        )


def _require_finite(value: object, field: str, key: str) -> float:
    if value is None:
        raise ValueError(f"{key!r} has missing {field}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key!r} has invalid {field}: {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{key!r} has non-finite {field}: {value!r}")
    return result


def _add_guide_workflow_nodes_and_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """Build guide-only repeatable workflows from exported source facts."""
    zone_displays = _zone_display(conn)
    known_db_names = {node.db_name for node in graph.all_nodes() if node.db_name is not None}

    def table_exists(name: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,),
            ).fetchone()
            is not None
        )

    def add_location(
        *,
        location_key: str,
        display_name: str,
        scene: str | None,
        zone_key: str | None,
        x: object,
        y: object,
        z: object,
        bounds: tuple[object, object, object, object, object, object],
    ) -> None:
        if graph.has_node(location_key):
            raise ValueError(f"guide location key collides with existing node: {location_key!r}")
        if not scene or not display_name:
            raise ValueError(f"{location_key!r} has missing scene or display name")
        center_x, center_y, center_z, extent_x, extent_y, extent_z = bounds
        extents = tuple(
            _require_finite(value, field, location_key)
            for value, field in zip(
                (extent_x, extent_y, extent_z),
                ("trigger_bounds_extents_x", "trigger_bounds_extents_y", "trigger_bounds_extents_z"),
                strict=True,
            )
        )
        if any(value <= 0 for value in extents):
            raise ValueError(f"{location_key!r} has non-positive trigger bounds extents")
        graph.add_node(
            Node(
                key=location_key,
                type=NodeType.LOCATION,
                display_name=display_name or location_key,
                scene=scene,
                zone_key=zone_key or _resolve_zone(scene, scene_to_zone),
                zone=_zone_display_name(zone_key or _resolve_zone(scene, scene_to_zone), zone_displays),
                x=_require_finite(x, "event_x", location_key),
                y=_require_finite(y, "event_y", location_key),
                z=_require_finite(z, "event_z", location_key),
                guide_only=True,
                trigger_bounds_center_x=_require_finite(center_x, "trigger_bounds_center_x", location_key),
                trigger_bounds_center_y=_require_finite(center_y, "trigger_bounds_center_y", location_key),
                trigger_bounds_center_z=_require_finite(center_z, "trigger_bounds_center_z", location_key),
                trigger_bounds_extents_x=extents[0],
                trigger_bounds_extents_y=extents[1],
                trigger_bounds_extents_z=extents[2],
            )
        )

    def add_workflow(
        *,
        quest_key: str,
        display_name: str,
        db_name: str,
        trigger_item_key: str,
        trigger_mode: str,
        location_key: str,
        targets: list[WorkflowTarget],
        reward_container_key: str | None,
        reset_evidence: str,
    ) -> None:
        if reset_evidence not in {"reward_container_consumed", "targets_defeated"}:
            raise ValueError(f"{quest_key!r} has invalid reset evidence {reset_evidence!r}")
        if (reward_container_key is None) != (reset_evidence == "targets_defeated"):
            raise ValueError(f"{quest_key!r} has inconsistent reward container and reset evidence")
        if db_name in known_db_names:
            raise ValueError(f"guide quest db name collides with existing node: {db_name!r}")
        if not display_name:
            raise ValueError(f"{quest_key!r} has missing workflow display name")
        if not trigger_mode:
            raise ValueError(f"{quest_key!r} has missing trigger_mode")
        if not targets:
            raise ValueError(f"{quest_key!r} has no workflow targets")
        if any(target.quantity <= 0 for target in targets):
            raise ValueError(f"{quest_key!r} has non-positive target quantity")
        for key, expected_type in [
            (trigger_item_key, NodeType.ITEM),
            (location_key, NodeType.LOCATION),
            *[(target.stable_key, NodeType.CHARACTER) for target in targets],
        ]:
            node = graph.get_node(key)
            if node is None or node.type != expected_type:
                raise ValueError(f"{quest_key!r} references missing or invalid {expected_type.value} node {key!r}")
        if reward_container_key is not None:
            reward = graph.get_node(reward_container_key)
            if reward is None or reward.type != NodeType.CHARACTER:
                raise ValueError(
                    f"{quest_key!r} references missing or invalid reward container {reward_container_key!r}"
                )
        if graph.has_node(quest_key):
            raise ValueError(f"guide quest key collides with existing node: {quest_key!r}")
        graph.add_node(
            Node(
                key=quest_key,
                type=NodeType.QUEST,
                display_name=display_name or quest_key,
                db_name=db_name,
                implicit=True,
                repeatable=True,
                guide_only=True,
                workflow_cycle=WorkflowCycle(
                    trigger_item_stable_key=trigger_item_key,
                    trigger_item_quantity=1,
                    trigger_mode=trigger_mode,
                    location_stable_key=location_key,
                    targets=targets,
                    reward_container_stable_key=reward_container_key,
                    reset_evidence=reset_evidence,
                ),
            )
        )
        known_db_names.add(db_name)
        graph.add_edge(Edge(source=quest_key, target=trigger_item_key, type=EdgeType.REQUIRES_ITEM, quantity=1))
        graph.add_edge(Edge(source=quest_key, target=location_key, type=EdgeType.STEP_GO_TO, ordinal=0))
        for ordinal, target in enumerate(targets, start=1):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=target.stable_key,
                    type=EdgeType.STEP_KILL,
                    ordinal=ordinal,
                    quantity=target.quantity,
                )
            )
        if reward_container_key is not None:
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=reward_container_key,
                    type=EdgeType.STEP_LOOT,
                    ordinal=len(targets) + 1,
                )
            )

    if table_exists("arena_rounds"):
        arena_rows = conn.execute(
            """SELECT stable_key, scene, round_index, coin_item_stable_key,
                      award_chest_character_stable_key, trigger_mode, event_display_name,
                      event_x, event_y, event_z, trigger_bounds_center_x,
                      trigger_bounds_center_y, trigger_bounds_center_z,
                      trigger_bounds_extents_x, trigger_bounds_extents_y,
                      trigger_bounds_extents_z
               FROM arena_rounds ORDER BY round_index, stable_key"""
        ).fetchall()
        enemy_rows = (
            conn.execute(
                """SELECT arena_round_stable_key, sequence_index, enemy_character_stable_key
                   FROM arena_round_enemies ORDER BY arena_round_stable_key, sequence_index"""
            ).fetchall()
            if table_exists("arena_round_enemies")
            else []
        )
        rounds: dict[str, sqlite3.Row] = {}
        for row in arena_rows:
            key = row["stable_key"]
            if not key or key in rounds:
                raise ValueError(f"arena round stable key is missing or duplicated: {key!r}")
            rounds[key] = row
        enemies: dict[str, list[tuple[int, str]]] = {}
        for row in enemy_rows:
            key = row["arena_round_stable_key"]
            if key not in rounds:
                raise ValueError(f"arena enemies reference unknown round: {key!r}")
            sequence = row["sequence_index"]
            if not isinstance(sequence, int) or sequence < 0:
                raise ValueError(f"arena round {key!r} has invalid sequence index {sequence!r}")
            if any(existing[0] == sequence for existing in enemies.setdefault(key, [])):
                raise ValueError(f"arena round {key!r} repeats sequence index {sequence}")
            enemies[key].append((sequence, row["enemy_character_stable_key"]))
        for key, row in rounds.items():
            sequence_rows = sorted(enemies.get(key, []))
            if not sequence_rows:
                raise ValueError(f"arena round {key!r} has no enemies")
            grouped: dict[str, int] = {}
            order: list[str] = []
            for _, enemy_key in sequence_rows:
                if not enemy_key:
                    raise ValueError(f"arena round {key!r} has missing enemy")
                enemy_node = graph.get_node(enemy_key)
                if enemy_node is None or enemy_node.type != NodeType.CHARACTER:
                    raise ValueError(
                        f"arena round {key!r} references missing or invalid enemy character node {enemy_key!r}"
                    )
                if enemy_key not in grouped:
                    order.append(enemy_key)
                grouped[enemy_key] = grouped.get(enemy_key, 0) + 1
            location_key = f"guide-location:arena:{key}"
            add_location(
                location_key=location_key,
                display_name=row["event_display_name"],
                scene=row["scene"],
                zone_key=None,
                x=row["event_x"],
                y=row["event_y"],
                z=row["event_z"],
                bounds=tuple(
                    row[field]
                    for field in (
                        "trigger_bounds_center_x",
                        "trigger_bounds_center_y",
                        "trigger_bounds_center_z",
                        "trigger_bounds_extents_x",
                        "trigger_bounds_extents_y",
                        "trigger_bounds_extents_z",
                    )
                ),
            )
            add_workflow(
                quest_key=f"guide-quest:arena:{key}",
                display_name=f"{row['event_display_name']} - Round {row['round_index']}",
                db_name=f"guide.arena.{key}",
                trigger_item_key=row["coin_item_stable_key"],
                trigger_mode=row["trigger_mode"],
                location_key=location_key,
                targets=[WorkflowTarget(enemy_key, grouped[enemy_key]) for enemy_key in order],
                reward_container_key=row["award_chest_character_stable_key"],
                reset_evidence="reward_container_consumed",
            )

    if table_exists("character_spawns"):
        trigger_rows = conn.execute(
            """SELECT character_stable_key, spawn_point_stable_key, zone_stable_key, scene,
                      event_x, event_y, event_z, trigger_item_stable_key, trigger_mode,
                      event_display_name, trigger_bounds_center_x, trigger_bounds_center_y,
                      trigger_bounds_center_z, trigger_bounds_extents_x,
                      trigger_bounds_extents_y, trigger_bounds_extents_z
               FROM character_spawns
               WHERE trigger_item_stable_key IS NOT NULL OR trigger_mode IS NOT NULL
                  OR event_x IS NOT NULL OR event_y IS NOT NULL OR event_z IS NOT NULL
               ORDER BY spawn_point_stable_key, character_stable_key"""
        ).fetchall()
        grouped_rows: dict[str, list[sqlite3.Row]] = {}
        for row in trigger_rows:
            spawn_key = row["spawn_point_stable_key"]
            if not spawn_key:
                raise ValueError("trigger spawn row has no spawn point stable key")
            grouped_rows.setdefault(spawn_key, []).append(row)
        for spawn_key, rows in grouped_rows.items():
            first = rows[0]
            fact_fields = (
                "zone_stable_key",
                "scene",
                "event_x",
                "event_y",
                "event_z",
                "trigger_item_stable_key",
                "trigger_mode",
                "event_display_name",
                "trigger_bounds_center_x",
                "trigger_bounds_center_y",
                "trigger_bounds_center_z",
                "trigger_bounds_extents_x",
                "trigger_bounds_extents_y",
                "trigger_bounds_extents_z",
            )
            facts = tuple(first[field] for field in fact_fields)
            for row in rows[1:]:
                if tuple(row[field] for field in fact_fields) != facts:
                    raise ValueError(f"conflicting duplicate trigger rows for {spawn_key!r}")
            target_counts: dict[str, int] = {}
            for row in rows:
                target_key = row["character_stable_key"]
                if not target_key:
                    raise ValueError(f"trigger {spawn_key!r} has missing target")
                target_counts[target_key] = target_counts.get(target_key, 0) + 1
            location_key = f"guide-location:trigger:{spawn_key}"
            add_location(
                location_key=location_key,
                display_name=first["event_display_name"],
                scene=first["scene"],
                zone_key=first["zone_stable_key"],
                x=first["event_x"],
                y=first["event_y"],
                z=first["event_z"],
                bounds=tuple(
                    first[field]
                    for field in (
                        "trigger_bounds_center_x",
                        "trigger_bounds_center_y",
                        "trigger_bounds_center_z",
                        "trigger_bounds_extents_x",
                        "trigger_bounds_extents_y",
                        "trigger_bounds_extents_z",
                    )
                ),
            )
            target_nodes: list[Node] = []
            for target_key in sorted(target_counts):
                target_node = graph.get_node(target_key)
                if target_node is None or target_node.type != NodeType.CHARACTER:
                    raise ValueError(f"trigger {spawn_key!r} references missing or invalid target")
                target_nodes.append(target_node)
            target_display = " / ".join(node.display_name for node in target_nodes)
            add_workflow(
                quest_key=f"guide-quest:trigger:{spawn_key}",
                db_name=f"guide.trigger.{spawn_key}",
                trigger_item_key=first["trigger_item_stable_key"],
                trigger_mode=first["trigger_mode"],
                display_name=target_display,
                location_key=location_key,
                targets=[WorkflowTarget(key, target_counts[key]) for key in sorted(target_counts)],
                reward_container_key=None,
                reset_evidence="targets_defeated",
            )
