"""Node construction for the Adventure Guide entity graph.

This module owns database-backed entity nodes and native activation facts.
The caller controls the shared SQLite connection and scene-to-zone lookup.
"""

from __future__ import annotations

import math
import sqlite3
from typing import TYPE_CHECKING

from .schema import (
    Activation,
    ActivationBounds,
    ActivationOffering,
    ActivationRef,
    ActivationSite,
    ActivationSpawn,
    ActivationVector,
    Node,
    NodeType,
)

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
    _add_native_activations(conn, graph)
    _add_mining_node_nodes(conn, graph, scene_to_zone)
    _add_water_nodes(conn, graph, scene_to_zone)
    _add_forge_nodes(conn, graph, scene_to_zone)
    _add_item_bag_nodes(conn, graph, scene_to_zone)
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
        SELECT q.stable_key, q.db_name, q.display_name, q.step_note,
               qv.quest_desc, qv.xp_on_complete, qv.gold_on_complete,
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
                step_note=r["step_note"],
                xp_reward=r["xp_on_complete"],
                gold_reward=r["gold_on_complete"],
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
        SELECT stable_key, id, display_name, item_level, stackable, is_unique,
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
                game_id=r["id"],
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
               my_world_faction_stable_key, is_enabled, encounter_tier
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
                encounter_tier=r["encounter_tier"],
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
               cs.furniture_item_stable_key, cs.furniture_slot,
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
                furniture_item_key=r["furniture_item_stable_key"],
                furniture_slot=r["furniture_slot"],
            )
        )


def _activation_site(row: sqlite3.Row) -> ActivationSite | None:
    fields = (
        "event_x",
        "event_y",
        "event_z",
        "trigger_bounds_center_x",
        "trigger_bounds_center_y",
        "trigger_bounds_center_z",
        "trigger_bounds_extents_x",
        "trigger_bounds_extents_y",
        "trigger_bounds_extents_z",
    )
    values = tuple(row[field] for field in fields)
    if all(value is None for value in values):
        return None
    if any(value is None or not math.isfinite(value) for value in values):
        raise ValueError("native activation has an incomplete or nonfinite site")
    if any(value < 0 for value in values[6:]):
        raise ValueError("native activation has negative trigger extents")
    return ActivationSite(
        values[0],
        values[1],
        values[2],
        ActivationBounds(
            ActivationVector(values[3], values[4], values[5]),
            ActivationVector(values[6], values[7], values[8]),
        ),
    )


def _add_native_activations(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Bind exported controller facts to exact spawned placements."""
    rows = conn.execute(
        """SELECT * FROM character_spawns
           WHERE source_script IN ('VithArena', 'MalarothFeed', 'Chessboard')
           ORDER BY source_script, scene, spawn_point_stable_key, character_stable_key"""
    ).fetchall()
    controllers: dict[str, Activation] = {}
    bindings: dict[str, list[ActivationRef]] = {}
    bound: set[tuple[str, int, str, str]] = set()

    def offering(
        item_key: str, spawns: tuple[ActivationSpawn, ...], reward: str | None = None, *, random: bool = False
    ) -> ActivationOffering:
        item = graph.get_node(item_key)
        if item is None or item.type != NodeType.ITEM:
            raise ValueError(f"native activation references missing offering item {item_key!r}")
        if not spawns:
            raise ValueError(f"native activation offering {item_key!r} has no spawned characters")
        for character in [*(spawn.character for spawn in spawns), *([reward] if reward else [])]:
            node = graph.get_node(character)
            if node is None or node.type != NodeType.CHARACTER:
                raise ValueError(f"native activation references missing character {character!r}")
        return ActivationOffering(item_key, item.display_name, spawns, reward, random)

    def bind(row: sqlite3.Row, key: str, index: int, role: str) -> None:
        placement = graph.get_node(row["spawn_point_stable_key"])
        if placement is None or placement.type != NodeType.SPAWN_POINT or not placement.scene:
            raise ValueError(f"native activation has unbound controller placement {row['spawn_point_stable_key']!r}")
        ref = ActivationRef(key, index, role)
        refs = bindings.setdefault(placement.key, [])
        if ref not in refs:
            refs.append(ref)
        bound.add((key, index, role, row["character_stable_key"]))

    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'arena_rounds'").fetchone():
        rounds = conn.execute("SELECT * FROM arena_rounds ORDER BY scene, arena_object_name, round_index").fetchall()
        arena_groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rounds:
            arena_groups.setdefault((row["scene"], row["arena_object_name"]), []).append(row)
        enemies: dict[str, dict[str, int]] = {}
        sequences: set[tuple[str, int]] = set()
        round_keys = {row["stable_key"] for row in rounds}
        for row in conn.execute("SELECT * FROM arena_round_enemies ORDER BY arena_round_stable_key, sequence_index"):
            round_key = row["arena_round_stable_key"]
            sequence = row["sequence_index"]
            if round_key not in round_keys or not isinstance(sequence, int) or sequence < 0:
                raise ValueError(f"invalid native arena enemy binding {round_key!r}")
            if (round_key, sequence) in sequences:
                raise ValueError(f"duplicate native arena enemy sequence {round_key!r}: {sequence}")
            sequences.add((round_key, sequence))
            counts = enemies.setdefault(round_key, {})
            character = row["enemy_character_stable_key"]
            counts[character] = counts.get(character, 0) + 1
        for (scene, object_name), group in arena_groups.items():
            if not scene or not object_name or len({r["round_index"] for r in group}) != len(group):
                raise ValueError("native arena has missing identity or duplicate round index")
            key = f"activation:VithArena:{scene}:{object_name}"
            site = _activation_site(group[0])
            display = group[0]["event_display_name"]
            if site is None:
                raise ValueError(f"native arena {key!r} has no site")
            offers = []
            for row in group:
                if _activation_site(row) != site or row["event_display_name"] != display:
                    raise ValueError(f"native arena {key!r} has conflicting sites")
                offers.append(
                    offering(
                        row["coin_item_stable_key"],
                        tuple(
                            ActivationSpawn(character, count)
                            for character, count in enemies.get(row["stable_key"], {}).items()
                        ),
                        row["award_chest_character_stable_key"],
                    )
                )
            controllers[key] = Activation("VithArena", scene, display, site, tuple(offers))

    trigger_groups: dict[tuple[str, str, ActivationSite | None], list[sqlite3.Row]] = {}
    sited: dict[tuple[str, str], set[bool]] = {}
    for row in rows:
        script, scene = row["source_script"], row["scene"]
        if not scene:
            raise ValueError("native activation placement has no scene")
        if script == "VithArena":
            matches = []
            for key, controller in controllers.items():
                if controller.scene != scene:
                    continue
                for index, offer in enumerate(controller.offerings):
                    if row["character_stable_key"] in {spawn.character for spawn in offer.spawns}:
                        matches.append((key, index, "spawn"))
                    if row["character_stable_key"] == offer.reward:
                        matches.append((key, index, "reward"))
            if not matches or len({key for key, _, _ in matches}) != 1:
                raise ValueError(f"unbound or ambiguous native arena placement {row['spawn_point_stable_key']!r}")
            for key, index, role in matches:
                bind(row, key, index, role)
        else:
            site = _activation_site(row)
            sited.setdefault((script, scene), set()).add(site is not None)
            trigger_groups.setdefault((script, scene, site), []).append(row)
    if any(len(values) > 1 for values in sited.values()):
        raise ValueError("native controller mixes sited and site-less placements")
    for (script, scene, site), group in trigger_groups.items():
        key = f"activation:{script}:{scene}"
        if site is not None:
            key += f":{site.x:.2f}:{site.y:.2f}:{site.z:.2f}"
        if key in controllers:
            raise ValueError(f"ambiguous native activation site identity {key!r}")
        if len({row["event_display_name"] for row in group}) != 1:
            raise ValueError(f"native activation {key!r} has conflicting display names")
        by_item: dict[str, list[sqlite3.Row]] = {}
        for row in group:
            item = row["trigger_item_stable_key"]
            if not item:
                raise ValueError(f"unbound native controller placement {row['spawn_point_stable_key']!r}: no offering")
            by_item.setdefault(item, []).append(row)
        offers = []
        for index, item in enumerate(sorted(by_item)):
            characters = sorted({row["character_stable_key"] for row in by_item[item]})
            # code-fact: chessboard.faceless_choices
            # Multiple exported Faceless targets are alternatives, not six simultaneous spawns.
            offers.append(
                offering(item, tuple(ActivationSpawn(char, 1) for char in characters), random=len(characters) > 1)
            )
            for row in by_item[item]:
                bind(row, key, index, "spawn")
        controllers[key] = Activation(script, scene, group[0]["event_display_name"], site, tuple(offers))
    for key, controller in controllers.items():
        for index, offer in enumerate(controller.offerings):
            expected = [("spawn", spawn.character) for spawn in offer.spawns]
            if offer.reward is not None:
                expected.append(("reward", offer.reward))
            for role, character in expected:
                if (key, index, role, character) not in bound:
                    raise ValueError(f"native activation character has no bound placement: {key!r} {character!r}")
        graph.add_node(
            Node(
                key,
                NodeType.LOCATION,
                controller.display_name or controller.script,
                scene=controller.scene,
                activation=controller,
            )
        )
    for key, refs in bindings.items():
        placement = graph.get_node(key)
        assert placement is not None
        placement.activations = tuple(refs)


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
