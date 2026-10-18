"""Assemble ``quest-guide.json``, the quest data that AdventureGuide embeds.

The graph is the source of semantics and ``CompiledData`` supplies the dense
indexes, the precomputed item source sites, and the combined gate conditions.
No database access belongs here: the output is a deterministic view of them.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemUse, is_actionable_acquisition

from .compiler import CompiledData, Condition, edge_type_byte, node_type_byte
from .schema import AtomKind, Edge, EdgeType, GateAtom, Node, NodeType, SubjectKind

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .graph import EntityGraph

# Steps that fight their character target; see _interaction_level.
_COMBAT_ACTIONS = frozenset({"kill", "loot"})
_BACKGROUND_SOURCE_TYPES = frozenset({"world_drop", "common_world_item", "fishing_bonus", "treasure_chest"})
# Sources whose character is only reached, never fought; see _interaction_level.
_INTERACTION_SOURCE_TYPES = frozenset({"vendor", "dialog_give"})
# Buying an item, being handed it or picking it up beats a random drop unless
# it takes more than this many levels more than the easiest other source.
_GUARANTEED_SOURCE_TYPES = frozenset({"vendor", "dialog_give", "pickup"})
_GUARANTEED_LEVEL_MARGIN = 5


def build_mod_guide(
    graph: EntityGraph, compiled: CompiledData, excluded_quest_db_names: Iterable[str] = ()
) -> dict[str, Any]:
    """Build the stable JSON shape consumed by the C# mod.

    ``excluded_quest_db_names`` names game quests the mapping keeps out of the
    guide on purpose, such as unobtainable placeholders. The mod lists every
    game quest the guide lacks as a stub; it skips these.
    """
    nodes = {node.key: node for node in graph.all_nodes()}
    quests = sorted(
        (node for node in nodes.values() if node.type == NodeType.QUEST),
        key=lambda node: (node.db_name or "", node.key),
    )
    _validate_quest_identity(quests)
    db_names = {node.key: node.db_name for node in quests}
    compiled_nodes = _compiled_nodes(compiled)
    _validate_compiled_references(compiled, compiled_nodes)
    compiled_edges = _compiled_edges(compiled, compiled_nodes)
    reward_by_item = _reward_edges_by_item(compiled_edges)

    incoming_chain: dict[str, list[Edge]] = defaultdict(list)
    for edge in graph.all_edges():
        if edge.source not in nodes or edge.target not in nodes:
            continue
        if edge.type in (EdgeType.CHAINS_TO, EdgeType.ALSO_COMPLETES):
            incoming_chain[edge.target].append(edge)

    zone_lines = _ordered_zone_lines(nodes)
    line_index = {line.key: index for index, line in enumerate(zone_lines)}
    result: dict[str, Any] = {
        "_version": 8,
        "_zone_lookup": _zone_lookup(nodes),
        "_conditions": [_condition_payload(graph, condition) for condition in compiled.conditions],
        "_gate_items": _gate_items(graph, nodes, compiled, compiled_nodes, reward_by_item),
        "_activations": {key: asdict(value) for key, value in sorted(compiled.activations.items())},
        "_character_spawns": _character_spawns(graph, nodes, compiled, line_index),
        # Respawn timers can be limited to spawn points that can spawn a boss or an elite.
        "_encounter_tiers": {
            node.key: node.encounter_tier
            for node in sorted(nodes.values(), key=lambda node: node.key)
            if node.type == NodeType.CHARACTER and node.encounter_tier in ("boss", "elite")
        },
        "_furniture_sets": {
            key: {"display_name": nodes[key].display_name}
            for key in sorted({node.furniture_item_key for node in nodes.values() if node.furniture_item_key})
        },
        "_zone_lines": [_zone_line(line, compiled) for line in zone_lines],
        "_chain_groups": _chain_groups(quests, graph, nodes, db_names),
        "_excluded_quests": _excluded_quests(excluded_quest_db_names, db_names),
        "quests": [
            _quest_entry(
                quest,
                graph,
                nodes,
                compiled,
                compiled_nodes,
                reward_by_item,
                incoming_chain,
                db_names,
            )
            for quest in quests
        ],
    }
    _normalize_source_tables(result, compiled)
    quest_keys = {
        atom.reference_stable_key
        for key in (*result["_source_facts"], *result["_item_uses"])
        for fact in (compiled.source_facts[key],)
        for atom in (*fact.conditions, *(atom for location in fact.locations for atom in location.conditions))
        if atom.predicate in {"quest_done", "quest_not_done"} and atom.reference_stable_key is not None
    }
    quest_keys.update(
        str(row["state_key"])
        for family in ("encounter_conditions", "encounter_completions", "encounter_event_conditions")
        for row in compiled.encounters.get(family, [])
        if row["state_scope"] == "character"
    )
    result["_quest_state_keys"] = {key: graph.quest_db_name(key) for key in sorted(quest_keys) if key is not None}
    result["_encounters"] = compiled.encounters
    result["_zone_line_destination_contexts"] = compiled.zone_line_destination_contexts
    return cast("dict[str, Any]", _sanitize(result))


def serialize_mod_guide(graph: EntityGraph, compiled: CompiledData, excluded_quest_db_names: Iterable[str] = ()) -> str:
    """Build and compactly serialize the quest data deterministically."""
    return json.dumps(build_mod_guide(graph, compiled, excluded_quest_db_names), separators=(",", ":"), allow_nan=False)


def _excluded_quests(excluded_quest_db_names: Iterable[str], db_names: dict[str, str | None]) -> list[str]:
    excluded = sorted(set(excluded_quest_db_names))
    included = {name for name in db_names.values() if name}
    overlap = sorted(set(excluded) & included)
    if overlap:
        raise ValueError(f"quests both excluded and in the guide: {overlap}")
    return excluded


def _validate_quest_identity(quests: list[Node]) -> None:
    seen_keys: set[str] = set()
    seen_db_names: set[str] = set()
    for quest in quests:
        if not quest.key or not quest.db_name:
            raise ValueError(f"malformed quest identity: {quest.key!r}")
        if quest.key in seen_keys:
            raise ValueError(f"duplicate quest stable key: {quest.key!r}")
        if quest.db_name in seen_db_names:
            raise ValueError(f"duplicate quest db_name: {quest.db_name!r}")
        seen_keys.add(quest.key)
        seen_db_names.add(quest.db_name)


def _compiled_nodes(compiled: CompiledData) -> dict[int, Any]:
    result: dict[int, Any] = {}
    known_types = {node_type_byte(node_type) for node_type in NodeType}
    for node in compiled.nodes:
        if node.node_id in result:
            raise ValueError(f"duplicate compiled node id: {node.node_id}")
        if node.node_type not in known_types:
            raise ValueError(f"unknown compiled node type: {node.node_type}")
        result[node.node_id] = node
    return result


def _validate_compiled_references(compiled: CompiledData, nodes: dict[int, Any]) -> None:
    references = [*compiled.quest_node_ids, *compiled.item_node_ids]
    for node_id in references:
        if node_id not in nodes:
            raise ValueError(f"dangling compiled node id: {node_id}")
    for key, node_id in compiled.node_key_to_id.items():
        if node_id not in nodes:
            raise ValueError(f"dangling compiled key index: {key!r}->{node_id}")


def _compiled_edges(compiled: CompiledData, nodes: dict[int, Any]) -> list[Any]:
    known_edge_types = {edge_type_byte(edge_type) for edge_type in EdgeType}
    for edge in compiled.edges:
        if edge.edge_type not in known_edge_types:
            raise ValueError(f"unknown compiled edge type: {edge.edge_type}")
        if edge.source_id not in nodes or edge.target_id not in nodes:
            raise ValueError(f"dangling compiled edge id: {edge.source_id}->{edge.target_id}")
    # References in compiler-produced indexes are IDs, not list positions.
    for node_id, edge_ids in enumerate(compiled.forward_adjacency):
        if node_id not in nodes:
            continue
        for edge_id in edge_ids:
            if edge_id < 0 or edge_id >= len(compiled.edges):
                raise ValueError(f"dangling compiled adjacency edge id: {edge_id}")
    for site_group in compiled.item_sources:
        for site in site_group:
            if site.source_id not in nodes:
                raise ValueError(f"dangling compiled source id: {site.source_id}")
            for position in site.positions:
                if position.spawn_id is not None and position.spawn_id not in nodes:
                    raise ValueError(f"dangling compiled spawn id: {position.spawn_id}")
    return compiled.edges


def _reward_edges_by_item(compiled_edges: list[Any]) -> dict[int, list[Any]]:
    result: dict[int, list[Any]] = defaultdict(list)
    rewards_type = edge_type_byte(EdgeType.REWARDS_ITEM)
    for edge in compiled_edges:
        if edge.edge_type == rewards_type:
            result[edge.target_id].append(edge)
    return result


def _required_number(key: str, field: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid {field} for node {key!r}")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(f"invalid {field} for node {key!r}")
    return cast("int | float", value)


def _required_coordinate(node: Node, axis: str, value: Any) -> int | float:
    return _required_number(node.key, f"{axis} coordinate", value)


def _zone_lookup(nodes: dict[str, Node]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    zones = sorted(
        (node for node in nodes.values() if node.type == NodeType.ZONE),
        key=lambda node: (node.scene or "", node.key),
    )
    for zone in zones:
        if not zone.scene:
            continue
        entry: dict[str, Any] = {"display_name": zone.display_name, "stable_key": zone.key}
        _put_if(entry, "level_min", zone.level_min)
        _put_if(entry, "level_max", zone.level_max)
        # The graph currently does not carry a median; never invent one.
        result.setdefault(zone.scene, entry)
    return result


def _character_spawns(
    graph: EntityGraph, nodes: dict[str, Node], compiled: CompiledData, line_index: dict[str, int]
) -> dict[str, list[dict[str, Any]]]:
    """Placements by character. ``entries`` indexes ``_zone_lines``: the only
    lines into the scene that reach the placement."""
    result: dict[str, list[dict[str, Any]]] = {}
    for character in sorted(
        (node for node in nodes.values() if node.type == NodeType.CHARACTER),
        key=lambda node: node.key,
    ):
        positions: list[tuple[str, dict[str, Any]]] = []
        for edge in graph.out_edges(character.key, EdgeType.HAS_SPAWN):
            spawn = nodes.get(edge.target)
            if spawn is None or spawn.type != NodeType.SPAWN_POINT:
                continue
            if not spawn.scene:
                continue
            x = _required_coordinate(spawn, "x", spawn.x)
            y = _required_coordinate(spawn, "y", spawn.y)
            z = _required_coordinate(spawn, "z", spawn.z)
            value: dict[str, Any] = {
                "stable_key": spawn.key,
                "scene": spawn.scene,
                "x": x,
                "y": y,
                "z": z,
                "night_spawn": bool(spawn.night_spawn),
                "is_directly_placed": bool(spawn.is_directly_placed),
            }
            _put_if(value, "source_script", spawn.source_script)
            if refs := compiled.placement_activations.get(spawn.key):
                value["activations"] = [asdict(ref) for ref in refs]
            _put_if(
                value,
                "condition",
                compiled.condition_by_subject.get((SubjectKind.CHARACTER, character.key, spawn.key)),
            )
            entries = sorted(
                {line_index[line] for line in (*graph.entries_for(character.key), *graph.entries_for(spawn.key))}
            )
            if entries:
                value["entries"] = entries
            positions.append((spawn.key, value))
        if positions:
            positions.sort(
                key=lambda pair: (
                    pair[1]["scene"],
                    _number(pair[1]["x"]),
                    _number(pair[1]["y"]),
                    _number(pair[1]["z"]),
                    pair[0],
                )
            )
            result[character.key] = [value for _, value in positions]

    return result


def _ordered_zone_lines(nodes: dict[str, Node]) -> list[Node]:
    """Zone lines in the order of ``_zone_lines``, which placements index."""
    lines = [node for node in nodes.values() if node.type == NodeType.ZONE_LINE and node.scene]
    return sorted(
        lines,
        key=lambda line: (
            line.scene,
            _number(_required_coordinate(line, "x", line.x)),
            _number(_required_coordinate(line, "y", line.y)),
            _number(_required_coordinate(line, "z", line.z)),
            line.key,
        ),
    )


def _zone_line(line: Node, compiled: CompiledData) -> dict[str, Any]:
    value: dict[str, Any] = {"stable_key": line.key, "scene": line.scene, "x": line.x, "y": line.y, "z": line.z}
    _put_if(value, "destination_zone_key", line.destination_zone_key)
    _put_if(value, "destination_display", line.destination_display)
    _put_if(value, "landing_x", line.landing_x)
    _put_if(value, "landing_y", line.landing_y)
    _put_if(value, "landing_z", line.landing_z)
    _put_if(value, "condition", compiled.condition_by_subject.get((SubjectKind.ZONE_LINE, line.key, None)))
    if line.key in compiled.zone_line_destination_contexts:
        for field in ("destination_zone_key", "destination_display", "landing_x", "landing_y", "landing_z"):
            value.pop(field, None)
    return value


def _condition_payload(graph: EntityGraph, condition: Condition) -> list[list[dict[str, str | int]]]:
    """A condition as groups of atoms. A quest atom names the quest's DB name,
    which the game's quest state uses, and every other atom a stable key."""
    return [[_atom_payload(graph, atom) for atom in group] for group in condition]


def _atom_payload(graph: EntityGraph, atom: GateAtom) -> dict[str, str | int]:
    value: dict[str, str | int]
    if atom.kind in (AtomKind.QUEST_DONE, AtomKind.QUEST_NOT_DONE):
        value = {"kind": atom.kind.value, "ref": graph.quest_db_name(atom.ref)}
    else:
        value = {"kind": atom.kind.value, "ref": atom.ref}
    if atom.slot is not None:
        value["slot"] = atom.slot
    if atom.kind == AtomKind.ENCOUNTER_WON and atom.quantity > 1:
        value["quantity"] = atom.quantity
    if atom.kind == AtomKind.PLANNING_SLOT_ITEM:
        if not atom.instruction or not atom.instruction.strip():
            raise ValueError(f"Planning-slot atom has no instruction: {atom.ref}.{atom.slot}")
        value["instruction"] = atom.instruction
    if atom.kind == AtomKind.ACCOUNT_STATE:
        if (
            atom.ref != "account_state:reliquary_claimed"
            or atom.actor != "account"
            or atom.value not in {"true", "false"}
            or atom.phase != "availability"
            or not atom.scope
        ):
            raise ValueError(f"Invalid account availability atom: {atom}")
        value.update(actor=atom.actor, value=atom.value, phase=atom.phase, scope=atom.scope)
    return value


def _gate_items(
    graph: EntityGraph,
    nodes: dict[str, Node],
    compiled: CompiledData,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
) -> dict[str, dict[str, Any]]:
    """Items referenced by conditions or activations, with game IDs and sources.

    The keyring holds game item IDs. Navigation to a missing key or item uses
    the sources. door_zones names the zones of the doors a key opens, so the
    guide can say why a key is needed.
    """
    keys = sorted(
        {
            atom.ref
            for condition in compiled.conditions
            for group in condition
            for atom in group
            if atom.kind
            in (
                AtomKind.ITEM_HELD,
                AtomKind.KEY_HELD,
                AtomKind.ROOM_FURNISHED,
                AtomKind.PLANNING_SLOT_ITEM,
            )
        }
    )
    keys = sorted(
        set(keys)
        | {
            atom.reference_stable_key
            for fact in _selected_facts(compiled)
            for atom in (*fact.conditions, *(atom for location in fact.locations for atom in location.conditions))
            if atom.phase == "availability"
            and atom.predicate in {"item_held", "key_held", "room_furnished"}
            and atom.reference_stable_key is not None
        }
        | {
            offering.item_stable_key
            for activation in compiled.activations.values()
            for offering in activation.offerings
        }
    )
    zone_by_scene = {
        node.scene.lower(): node.display_name for node in nodes.values() if node.type == NodeType.ZONE and node.scene
    }
    door_zones: dict[str, set[str]] = defaultdict(set)
    for gate in graph.all_gates():
        if not gate.gate.startswith("door:"):
            continue
        zone = zone_by_scene.get(gate.gate.split(":")[1])
        for group in gate.groups:
            for atom in group:
                if atom.kind == AtomKind.KEY_HELD and zone is not None:
                    door_zones[atom.ref].add(zone)
    result: dict[str, dict[str, Any]] = {}
    for key in keys:
        item = nodes.get(key)
        if item is None or item.type != NodeType.ITEM or not item.game_id:
            raise ValueError(
                f"a condition or activation names {key!r}, which is not an item of the guide with a game ID"
            )
        value: dict[str, Any] = {"name": item.display_name, "game_id": item.game_id}
        if door_zones.get(key):
            value["door_zones"] = sorted(door_zones[key])
        sources = _item_sources_with_rewards(
            compiled, _compiled_id(compiled, key), compiled_nodes, reward_by_item, "", graph, nodes
        )
        if sources:
            value["sources"] = sources
        result[key] = value
    return result


def _chain_groups(
    quests: list[Node], graph: EntityGraph, nodes: dict[str, Node], db_names: dict[str, str | None]
) -> list[dict[str, Any]]:
    next_edges: dict[str, list[str]] = defaultdict(list)
    incoming: set[str] = set()
    for quest in quests:
        for edge in graph.out_edges(quest.key, EdgeType.CHAINS_TO):
            if edge.target in nodes and nodes[edge.target].type == NodeType.QUEST:
                next_edges[quest.key].append(edge.target)
                incoming.add(edge.target)
    for _key, targets in next_edges.items():
        targets.sort(key=lambda target: (db_names.get(target) or "", target))
    roots = sorted((key for key in next_edges if key not in incoming), key=lambda key: (db_names.get(key) or "", key))
    groups: list[dict[str, Any]] = []
    visited: set[str] = set()
    for root in roots + sorted(next_edges):
        if root in visited:
            continue
        path: list[str] = []
        stack = [root]
        while stack:
            current = stack.pop(0)
            if current in visited:
                continue
            visited.add(current)
            path.append(current)
            stack[0:0] = next_edges.get(current, [])
        if len(path) > 1:
            path_db = [db_names[key] for key in path if db_names.get(key)]
            groups.append({"name": nodes[root].display_name, "quests": path_db})
    groups.sort(key=lambda group: (group["name"], tuple(group["quests"])))
    return groups


def _quest_entry(
    quest: Node,
    graph: EntityGraph,
    nodes: dict[str, Node],
    compiled: CompiledData,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
    incoming_chain: dict[str, list[Edge]],
    db_names: dict[str, str | None],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "db_name": quest.db_name,
        "stable_key": quest.key,
        "display_name": quest.display_name,
    }
    _put_if(result, "description", quest.description)
    _put_if(result, "quest_type", _quest_type(graph, quest, nodes))
    _put_if(result, "acceptance", "implicit" if quest.implicit else "explicit")
    zone = quest.zone
    if zone is None:
        zone = _infer_zone(graph, quest, nodes)
    _put_if(result, "zone_context", zone)

    acquisition = _acquisition(graph, quest, nodes)
    required_items = _required_items(graph, quest, nodes, compiled, compiled_nodes, reward_by_item)
    prerequisites = _prerequisites(graph, quest, nodes)
    prerequisites.extend(_implicit_item_prerequisites(quest, required_items, nodes))
    prerequisites.extend(
        _implicit_acquisition_item_prerequisites(graph, quest, nodes, compiled, compiled_nodes, reward_by_item)
    )
    prerequisites.extend(_implicit_character_prerequisites(graph, quest, nodes))
    prerequisites = _dedupe_prerequisites(prerequisites)
    completion = _completion(graph, quest, nodes, required_items)
    steps = _steps(graph, quest, nodes, required_items, completion, compiled, compiled_nodes)
    rewards = _rewards(quest, graph, nodes)
    chain = _chain(graph, quest, nodes, incoming_chain, db_names)
    flags = _flags(quest)
    for key, value in (
        ("acquisition", acquisition),
        ("prerequisites", prerequisites),
        ("steps", steps),
        ("required_items", required_items),
        ("completion", completion),
        ("rewards", rewards),
        ("chain", chain),
        ("flags", flags),
    ):
        if value or key in {"rewards", "flags"}:
            result[key] = value
    if quest.level is not None:
        result["level_estimate"] = {"recommended": quest.level}
    return result


def _acquisition(graph: EntityGraph, quest: Node, nodes: dict[str, Node]) -> list[dict[str, Any]]:
    result: list[tuple[int, str, dict[str, Any]]] = []
    for edge in graph.out_edges(quest.key, EdgeType.ASSIGNED_BY):
        target = nodes.get(edge.target)
        if target is None:
            continue
        method = (
            edge.note
            if edge.note in {"dialog", "item_read", "zone_entry", "quest_chain", "partial_turnin", "scripted"}
            else None
        )
        if method is None:
            method = {
                NodeType.CHARACTER: "dialog",
                NodeType.ITEM: "item_read",
                NodeType.ZONE: "zone_entry",
                NodeType.QUEST: "quest_chain",
            }.get(target.type, "scripted")
        value: dict[str, Any] = {
            "method": method,
            "source_name": target.display_name,
            "source_type": _source_type(target),
            "source_stable_key": target.key,
        }
        _put_if(value, "zone_name", target.zone)
        _put_if(value, "keyword", edge.keyword)
        _put_if(value, "note", edge.note if edge.note and edge.note != method else None)
        result.append((edge.ordinal if edge.ordinal is not None else 2**31, target.key, value))
    result.sort(key=lambda item: (item[0], item[1]))
    return [value for _, _, value in result]


def _prerequisites(graph: EntityGraph, quest: Node, nodes: dict[str, Node]) -> list[dict[str, Any]]:
    result = []
    for edge in graph.out_edges(quest.key, EdgeType.REQUIRES_QUEST):
        target = nodes.get(edge.target)
        if target is None or not target.db_name:
            continue
        result.append({"type": "quest", "quest_key": target.key, "quest_name": target.display_name})
    result.sort(key=lambda item: (item["quest_key"], item["quest_name"]))
    return result


def _implicit_item_prerequisites(
    quest: Node, required_items: list[dict[str, Any]], nodes: dict[str, Node]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for required in required_items:
        result.extend(_item_reward_prerequisites(quest, required["item_name"], required.get("sources", []), nodes))
    return result


def _implicit_acquisition_item_prerequisites(
    graph: EntityGraph,
    quest: Node,
    nodes: dict[str, Node],
    compiled: CompiledData,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    acquisition_edges = sorted(
        graph.out_edges(quest.key, EdgeType.ASSIGNED_BY),
        key=lambda edge: (
            edge.ordinal if edge.ordinal is not None else 2**31,
            edge.target,
            edge.group or "",
            edge.keyword or "",
            edge.note or "",
        ),
    )
    for edge in acquisition_edges:
        item = nodes.get(edge.target)
        if item is None or item.type != NodeType.ITEM:
            continue
        item_id = _compiled_id(compiled, item.key)
        if item_id not in compiled_nodes:
            raise ValueError(f"dangling compiled node id for key: {item.key!r}")
        sources = _item_sources_with_rewards(compiled, item_id, compiled_nodes, reward_by_item, quest.key, graph, nodes)
        result.extend(_item_reward_prerequisites(quest, item.display_name, sources, nodes))
    return result


def _item_reward_prerequisites(
    quest: Node, item_name: str, sources: list[dict[str, Any]], nodes: dict[str, Node]
) -> list[dict[str, Any]]:
    reward_sources = [source for source in sources if source.get("type") == "quest_reward"]
    if not reward_sources or len(reward_sources) != len(sources):
        return []
    result: list[dict[str, Any]] = []
    for source in reward_sources:
        key = source.get("quest_key")
        rewarding = nodes.get(key) if isinstance(key, str) else None
        if rewarding is None or rewarding.key == quest.key or not rewarding.db_name:
            continue
        result.append(
            {
                "type": "quest",
                "quest_key": rewarding.key,
                "quest_name": rewarding.display_name,
                "item": item_name,
            }
        )
    return result


def _dedupe_prerequisites(prerequisites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for prerequisite in prerequisites:
        key = prerequisite["quest_key"]
        current = deduped.get(key)
        if current is None:
            deduped[key] = prerequisite
        elif "item" not in current and "item" in prerequisite:
            current["item"] = prerequisite["item"]
    return [deduped[key] for key in sorted(deduped)]


def _implicit_character_prerequisites(graph: EntityGraph, quest: Node, nodes: dict[str, Node]) -> list[dict[str, Any]]:
    """Quests that make a giver or turn-in character appear, from the easiest group of each gate."""
    result: list[dict[str, Any]] = []
    targets: list[Node] = []
    for edge_type in (EdgeType.ASSIGNED_BY, EdgeType.COMPLETED_BY):
        for edge in graph.out_edges(quest.key, edge_type):
            target = nodes.get(edge.target)
            if target is not None and target.type == NodeType.CHARACTER:
                targets.append(target)
    for character in targets:
        for gate in graph.gates_for(SubjectKind.CHARACTER, character.key):
            quest_groups = [
                sorted(atom.ref for atom in group if atom.kind == AtomKind.QUEST_DONE) for group in gate.groups
            ]
            if not quest_groups or not all(quest_groups):
                continue
            for quest_key in min(quest_groups, key=lambda keys: (len(keys), keys)):
                prerequisite = nodes.get(quest_key)
                if prerequisite is None or prerequisite.key == quest.key or not prerequisite.db_name:
                    continue
                result.append(
                    {
                        "type": "quest",
                        "quest_key": prerequisite.key,
                        "quest_name": prerequisite.display_name,
                        "note": f"{character.display_name} spawns after quest completion",
                    }
                )
    return result


def _required_items(
    graph: EntityGraph,
    quest: Node,
    nodes: dict[str, Node],
    compiled: CompiledData,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    canonical_items: set[str] = set()
    for (quest_key, item_key), uses in sorted(compiled.quest_uses.items()):
        if quest_key != quest.key:
            continue
        canonical_items.add(item_key)
        grouped: dict[tuple[str | None, str | None], list[ItemUse]] = {}
        for use in sorted(uses, key=lambda use: use.use_key):
            grouped.setdefault((use.variant_key, _requested_quality(use)), []).append(use)
        for (variant, quality), members in grouped.items():
            canonical_item = nodes[item_key]
            total = 0
            for use in members:
                quantity = use.quantity_min
                if (
                    quantity is None
                    or isinstance(quantity, bool)
                    or not math.isfinite(quantity)
                    or quantity < 0
                    or use.quantity_kind != "exact"
                    or use.quantity_max != quantity
                    or int(quantity) != quantity
                ):
                    raise ValueError(f"Quest requirement has no integer quantity: {use.use_key}")
                total += int(quantity)
            value: dict[str, Any] = {
                "item_name": canonical_item.display_name,
                "item_stable_key": item_key,
                "use_keys": [use.use_key for use in members],
                "quantity": total,
            }
            _put_if(value, "variant_key", variant)
            _put_if(value, "output_quality", quality)
            sources = _canonical_item_sources(compiled, item_key, nodes, quest.key, frozenset(), quality)
            if sources:
                value["sources"] = sources
            result.append(value)
    for edge_type in (EdgeType.REQUIRES_ITEM, EdgeType.STEP_READ, EdgeType.COMPLETED_BY):
        for edge in graph.out_edges(quest.key, edge_type):
            item = nodes.get(edge.target)
            if item is None or item.type != NodeType.ITEM or item.key in canonical_items:
                continue
            canonical_items.add(item.key)
            value = {
                "item_name": item.display_name,
                "item_stable_key": item.key,
                "quantity": edge.quantity if edge.quantity is not None else 1,
            }
            _put_if(value, "or_group", edge.group)
            sources = _item_sources_with_rewards(
                compiled, _compiled_id(compiled, item.key), compiled_nodes, reward_by_item, quest.key, graph, nodes
            )
            if sources:
                value["sources"] = sources
            result.append(value)
    return sorted(
        result,
        key=lambda row: (
            row.get("variant_key", ""),
            row["item_stable_key"],
            row.get("output_quality", ""),
            row.get("or_group", ""),
        ),
    )


def _with_source_conditions(sources: list[dict[str, Any]], item: Node, compiled: CompiledData) -> list[dict[str, Any]]:
    """Add buy instructions, and the conditions of vendor stock and pickups."""
    result: list[dict[str, Any]] = []
    for source in sources:
        value = dict(source)
        source_key = source.get("source_key")
        if source.get("type") == "vendor":
            value["instruction"] = f"Buy {item.display_name}."
            if isinstance(source_key, str):
                subject = (SubjectKind.VENDOR_ITEM, source_key, item.key)
                _put_if(value, "condition", compiled.condition_by_subject.get(subject))
        elif source.get("type") == "pickup" and isinstance(source_key, str):
            _put_if(value, "condition", compiled.condition_by_subject.get((SubjectKind.ITEM_BAG, source_key, None)))
        result.append(value)
    return result


def _interaction_level(node: Node) -> int | None:
    """Level for talking to, trading with or turning in to a character.

    None of these fights the character, so its own level means nothing
    there: a level 35 quest giver in Hidden Hills, level 99 ritual braziers.
    They use the level of reaching it. Kill and loot steps and drops keep
    the character's own level.
    """
    return node.place_level


def _item_sources_with_rewards(
    compiled: CompiledData,
    item_id: int,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
    exclude_quest_key: str,
    graph: EntityGraph,
    nodes: dict[str, Node],
    visiting: frozenset[int] = frozenset(),
) -> list[dict[str, Any]]:
    sources = _canonical_item_sources(compiled, compiled_nodes[item_id].key, nodes, exclude_quest_key, frozenset())
    for authored in _authored_item_sources(compiled, item_id, compiled_nodes, nodes):
        matches = [
            source
            for source in sources
            if source.get("type") == authored.get("type") and source.get("source_key") == authored.get("source_key")
        ]
        if matches:
            for source in matches:
                if authored.get("instruction"):
                    source["instruction"] = authored["instruction"]
        else:
            sources.append(authored)
    for reward in reward_by_item.get(item_id, []):
        if reward.provenance_key is not None:
            continue
        rewarding = compiled_nodes[reward.source_id]
        if rewarding.key != exclude_quest_key:
            sources.append({"type": "quest_reward", "name": rewarding.display_name, "quest_key": rewarding.key})
    visiting = visiting | {item_id}
    for edge_id in compiled.reverse_adjacency[item_id]:
        edge = compiled.edges[edge_id]
        if edge.provenance_key is not None or edge.edge_type != edge_type_byte(EdgeType.CREATES_ITEM):
            continue
        if edge.source_id in visiting:
            continue
        used = compiled_nodes[edge.source_id]
        value = {
            "type": "item_use",
            "name": used.display_name,
            "source_key": used.key,
            "instruction": f"Use {used.display_name}.",
            "children": _item_sources_with_rewards(
                compiled, edge.source_id, compiled_nodes, reward_by_item, exclude_quest_key, graph, nodes, visiting
            ),
        }
        _put_if(value, "level", used.obtainability_level)
        sources.append(value)
    sources = _with_source_conditions(sources, nodes[compiled_nodes[item_id].key], compiled)
    _sort_sources(sources)
    return sources


def _sort_sources(sources: list[dict[str, Any]]) -> None:
    """Order sources by level, guaranteed ones first when within reach.

    The first source is where navigation goes when no source is in the
    player's zone. A vendor, giver or pickup comes before random drops
    unless it takes more than _GUARANTEED_LEVEL_MARGIN levels more than the
    easiest other source. Random pools and chests always come last.
    """
    other_levels = [
        source["level"]
        for source in sources
        if source.get("type") not in _GUARANTEED_SOURCE_TYPES
        and source.get("type") not in _BACKGROUND_SOURCE_TYPES
        and source.get("level") is not None
    ]
    reach = min(other_levels) + _GUARANTEED_LEVEL_MARGIN if other_levels else None

    def key(source: dict[str, Any]) -> tuple[bool, bool, bool, int, str, str, str, float, float, float, str, str]:
        level = source.get("level")
        preferred = (
            source.get("type") in _GUARANTEED_SOURCE_TYPES and level is not None and (reach is None or level <= reach)
        )
        return (
            source.get("type") in _BACKGROUND_SOURCE_TYPES,
            not preferred,
            level is None,
            level or 0,
            source.get("type", ""),
            source.get("name", ""),
            source.get("source_key", ""),
            source.get("chance", -1),
            source.get("day_chance", -1),
            source.get("night_chance", -1),
            source.get("time_restriction", ""),
            source.get("keyword", ""),
        )

    sources.sort(key=key)


def _completion(
    graph: EntityGraph, quest: Node, nodes: dict[str, Node], required_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result: list[tuple[str, dict[str, Any]]] = []
    step_kill = {edge.target for edge in graph.out_edges(quest.key, EdgeType.STEP_KILL)}
    step_talk = {edge.target: edge for edge in graph.out_edges(quest.key, EdgeType.STEP_TALK)}
    step_shout = {edge.target: edge for edge in graph.out_edges(quest.key, EdgeType.STEP_SHOUT)}
    for edge in graph.out_edges(quest.key, EdgeType.COMPLETED_BY):
        target = nodes.get(edge.target)
        if target is None:
            continue
        if edge.note in {"item_turnin", "talk", "zone", "read", "shout", "death", "scripted", "chain"}:
            method = edge.note
        elif target.key in step_kill:
            method = "death"
        elif target.key in step_shout:
            method = "shout"
        elif target.type == NodeType.CHARACTER:
            method = "item_turnin" if required_items else "talk"
        elif target.type == NodeType.ZONE:
            method = "zone"
        elif target.type == NodeType.ITEM:
            method = "read"
        elif target.type == NodeType.QUEST:
            method = "chain"
        else:
            method = "scripted"
        value: dict[str, Any] = {
            "method": method,
            "source_name": target.display_name,
            "source_type": _source_type(target),
            "source_stable_key": target.key,
        }
        _put_if(value, "zone_name", target.zone)
        source_edge = step_talk.get(target.key) or step_shout.get(target.key)
        _put_if(value, "keyword", source_edge.keyword if source_edge else edge.keyword)
        _put_if(value, "note", edge.note)
        _put_if(value, "or_group", edge.group)
        result.append((target.key, value))
    result.sort(key=lambda item: (graph.is_furnishing_character(item[0]), item[0]))
    return [value for _, value in result]


def _steps(
    graph: EntityGraph,
    quest: Node,
    nodes: dict[str, Node],
    required_items: list[dict[str, Any]],
    completion: list[dict[str, Any]],
    compiled: CompiledData,
    compiled_nodes: dict[int, Any],
) -> list[dict[str, Any]]:
    entries: list[tuple[int, int, dict[str, Any]]] = []
    sequence = 0
    required_by_key = {item["item_stable_key"]: item for item in required_items}
    source_cache: dict[str, list[dict[str, Any]]] = {}

    def level_for(target: Node, action: str) -> dict[str, Any] | None:
        if target.type in {NodeType.CHARACTER, NodeType.ZONE}:
            level = target.level
            if target.type == NodeType.CHARACTER and action not in _COMBAT_ACTIONS:
                level = _interaction_level(target)
            if level is None or level <= 0:
                # A zone without hostiles has no level; still name the
                # character's zone.
                if target.type == NodeType.CHARACTER and target.zone:
                    return {"factors": [{"source": "zone", "name": target.zone}]}
                return None
            return {
                "recommended": level,
                "factors": [{"source": "zone", "name": target.zone or target.display_name, "level": level}],
            }
        if target.type != NodeType.ITEM or action not in {"collect", "read"}:
            return None
        item = required_by_key.get(target.key)
        sources = item.get("sources", []) if item is not None else source_cache.get(target.key)
        if sources is None:
            item_id = _compiled_id(compiled, target.key)
            if item_id not in compiled_nodes:
                raise ValueError(f"dangling compiled node id for key: {target.key!r}")
            sources = _item_sources_with_rewards(compiled, item_id, compiled_nodes, {}, quest.key, graph, nodes)
            source_cache[target.key] = sources
        return _item_level_estimate(sources)

    for edge in graph.out_edges(quest.key, EdgeType.ASSIGNED_BY):
        target = nodes.get(edge.target)
        if target is None or target.type not in {NodeType.CHARACTER, NodeType.ITEM}:
            continue
        action = "talk" if target.type == NodeType.CHARACTER else "read"
        step = _step_value(action, target, edge.keyword, edge.group, edge.quantity)
        _put_if(step, "level_estimate", level_for(target, action))
        entries.append((edge.ordinal if edge.ordinal is not None else -1000000, sequence, step))
        sequence += 1
    acquisition_step_count = sequence
    for item in required_items:
        step = {
            "action": "collect",
            "description": f"Collect {item['quantity']}x {item['item_name']}."
            if item["quantity"] > 1
            else f"Collect {item['item_name']}.",
            "target_name": item["item_name"],
            "target_type": "item",
            "target_key": item["item_stable_key"],
            "quantity": item["quantity"],
        }
        _put_if(step, "or_group", item.get("or_group"))
        _put_if(step, "requirement_variant", item.get("variant_key"))
        _put_if(step, "output_quality", item.get("output_quality"))
        _put_if(step, "level_estimate", level_for(nodes[item["item_stable_key"]], "collect"))
        entries.append((-500000, sequence, step))
        sequence += 1
    step_types = {
        EdgeType.STEP_TALK: "talk",
        EdgeType.STEP_TURN_IN: "turn_in",
        EdgeType.STEP_BUY: "buy",
        EdgeType.STEP_KILL: "kill",
        EdgeType.STEP_LOOT: "loot",
        EdgeType.STEP_TRAVEL: "travel",
        EdgeType.STEP_SHOUT: "shout",
        EdgeType.STEP_READ: "read",
    }
    for edge_type, action in step_types.items():
        for edge in graph.out_edges(quest.key, edge_type):
            target = nodes.get(edge.target)
            if target is None:
                continue
            if any(entry[2].get("target_key") == target.key and entry[2].get("action") == action for entry in entries):
                continue
            step = _step_value(action, target, edge.keyword, edge.group, edge.quantity)
            _put_if(step, "level_estimate", level_for(target, action))
            entries.append((edge.ordinal if edge.ordinal is not None else 0, sequence, step))
            sequence += 1
    for item in completion:
        completion_action = {
            "item_turnin": "turn_in",
            "talk": "talk",
            "death": "kill",
            "zone": "travel",
            "shout": "shout",
            "read": "read",
            "chain": "complete_quest",
        }.get(item["method"])
        source_key = item.get("source_stable_key")
        target = nodes.get(source_key) if isinstance(source_key, str) else None
        if (
            completion_action
            and target is not None
            and not any(
                entry[2].get("target_key") == target.key and entry[2].get("action") == completion_action
                for entry in entries
            )
        ):
            step = _step_value(completion_action, target, item.get("keyword"), item.get("or_group"))
            _put_if(step, "level_estimate", level_for(target, completion_action))
            entries.append((1000000, sequence, step))
            sequence += 1
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    result: list[dict[str, Any]] = []
    step_note = quest.step_note
    for order, (_, sequence_index, step_payload) in enumerate(entries, 1):
        if step_note and sequence_index >= acquisition_step_count:
            step_payload["description"] = f"{step_payload['description']} {step_note}"
            step_note = None
        step_payload["order"] = order
        ordered_step = {"order": step_payload.pop("order"), **step_payload}
        result.append(ordered_step)
    return result


def _item_level_estimate(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    factors: set[tuple[str, str, int]] = set()
    for source in sources:
        if source.get("type") in _BACKGROUND_SOURCE_TYPES:
            continue
        level = source.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level <= 0:
            continue
        source_type = source.get("type")
        if not isinstance(source_type, str):
            continue
        name = source.get("name") or source.get("zone")
        if not isinstance(name, str):
            name = ""
        factors.add((source_type, name, level))
    if not factors:
        return None
    ordered = sorted(factors)
    return {
        "recommended": min(level for _, _, level in ordered),
        "factors": [{"source": source, "name": name, "level": level} for source, name, level in ordered],
    }


def _step_value(
    action: str,
    target: Node,
    keyword: str | None,
    or_group: str | None = None,
    quantity: int | None = None,
) -> dict[str, Any]:
    if action == "talk":
        description = f'Say "{keyword}" to {target.display_name}.' if keyword else f"Speak to {target.display_name}."
    elif action == "buy":
        description = f"Buy {target.display_name}."
    elif action == "kill":
        quantity_prefix = f"{quantity}x " if quantity is not None and quantity > 1 else ""
        description = f"Defeat {quantity_prefix}{target.display_name}."
    elif action == "loot":
        description = f"Loot {target.display_name}."
    elif action == "travel":
        description = f"Travel to {target.display_name}."
    elif action == "shout":
        description = (
            f'Shout "{keyword}" near {target.display_name}.' if keyword else f"Shout near {target.display_name}."
        )
    elif action == "read":
        description = f"Read {target.display_name}."
    elif action == "turn_in":
        description = f"Turn in items to {target.display_name}."
    elif action == "complete_quest":
        description = f"Complete {target.display_name}."
    else:
        description = target.display_name
    value: dict[str, Any] = {
        "action": action,
        "description": description,
        "target_name": target.display_name,
        "target_type": _source_type(target),
        "target_key": target.key,
    }
    _put_if(value, "zone_name", target.zone)
    _put_if(value, "keyword", keyword)
    _put_if(value, "or_group", or_group)
    _put_if(value, "quantity", quantity)
    return value


def _rewards(quest: Node, graph: EntityGraph, nodes: dict[str, Node]) -> dict[str, Any]:
    value: dict[str, Any] = {"xp": quest.xp_reward or 0, "gold": quest.gold_reward or 0}
    rewards = sorted(
        {edge.target for edge in graph.out_edges(quest.key, EdgeType.REWARDS_ITEM) if edge.target in nodes}
    )
    if not rewards and not graph.source_facts and quest.reward_item_key in nodes:
        rewards = [quest.reward_item_key]
    if len(rewards) == 1:
        reward_item = nodes[rewards[0]]
        value["item_name"] = reward_item.display_name
        value["item_stable_key"] = reward_item.key
    elif rewards:
        value["items"] = [{"item_stable_key": key, "item_name": nodes[key].display_name} for key in rewards]
    # What completing the quest opens: the groups of the gates that need it.
    done = GateAtom(AtomKind.QUEST_DONE, quest.key)
    opened = [(gate, group) for gate in graph.all_gates() for group in gate.groups if done in group]
    vendor_unlocks: dict[tuple[str, str], dict[str, str]] = {}
    for gate, _ in opened:
        if gate.subject_kind != SubjectKind.VENDOR_ITEM or gate.item_key is None:
            continue
        item = nodes.get(gate.item_key)
        vendor = nodes.get(gate.subject_key)
        if item is None or vendor is None:
            continue
        vendor_unlocks[(item.key, vendor.key)] = {"item_name": item.display_name, "vendor_name": vendor.display_name}
    if len(vendor_unlocks) > 1:
        raise ValueError(f"quest {quest.key!r} unlocks multiple distinct vendors")
    if vendor_unlocks:
        value["vendor_unlock"] = next(iter(vendor_unlocks.values()))
    chains = [nodes[e.target] for e in graph.out_edges(quest.key, EdgeType.CHAINS_TO) if e.target in nodes]
    if chains:
        chains.sort(key=lambda node: (node.db_name or "", node.key))
        value["next_quest_name"] = chains[0].display_name
        value["next_quest_stable_key"] = chains[0].key
    also = sorted(
        (
            nodes[e.target].db_name
            for e in graph.out_edges(quest.key, EdgeType.ALSO_COMPLETES)
            if e.target in nodes and nodes[e.target].db_name
        ),
        key=str,
    )
    if also:
        value["also_completes"] = also
    unlocked_lines = []
    unlocked_chars = []
    for gate, group in opened:
        target = nodes.get(gate.subject_key)
        if target is None:
            continue
        if gate.subject_kind == SubjectKind.ZONE_LINE:
            entry: dict[str, Any] = {
                "from_zone": target.zone or "",
                "to_zone": target.destination_display or target.destination_zone_key or "",
            }
            others = sorted(
                {graph.quest_db_name(atom.ref) for atom in group if atom.kind == AtomKind.QUEST_DONE and atom != done}
            )
            if others:
                entry["co_requirements"] = others
            unlocked_lines.append(entry)
        elif gate.subject_kind == SubjectKind.CHARACTER:
            entry = {"name": target.display_name}
            _put_if(entry, "zone", target.zone)
            unlocked_chars.append(entry)
    if unlocked_lines:
        unlocked_lines.sort(
            key=lambda item: (item["from_zone"], item["to_zone"], tuple(item.get("co_requirements", [])))
        )
        value["unlocked_zone_lines"] = unlocked_lines
    if unlocked_chars:
        unlocked_chars.sort(key=lambda item: (item["name"], item.get("zone", "")))
        value["unlocked_characters"] = unlocked_chars
    faction: list[dict[str, Any]] = []
    for edge in graph.out_edges(quest.key, EdgeType.AFFECTS_FACTION):
        target = nodes.get(edge.target)
        if target:
            faction.append(
                {"faction_name": target.display_name, "faction_stable_key": target.key, "amount": edge.amount or 0}
            )
    if faction:
        faction.sort(key=lambda item: item["faction_stable_key"])
        value["faction_effects"] = faction
    return value


def _chain(
    graph: EntityGraph,
    quest: Node,
    nodes: dict[str, Node],
    incoming_chain: dict[str, list[Edge]],
    db_names: dict[str, str | None],
) -> list[dict[str, Any]]:
    result = []
    for edge in incoming_chain.get(quest.key, []):
        target = nodes.get(edge.source)
        if target:
            relationship = "previous" if edge.type == EdgeType.CHAINS_TO else "completed_by"
            result.append(
                {"quest_name": target.display_name, "quest_stable_key": target.key, "relationship": relationship}
            )
    for edge in graph.out_edges(quest.key, EdgeType.CHAINS_TO):
        target = nodes.get(edge.target)
        if target:
            result.append({"quest_name": target.display_name, "quest_stable_key": target.key, "relationship": "next"})
    result.sort(key=lambda item: (item["relationship"], item["quest_stable_key"]))
    return result


def _flags(quest: Node) -> dict[str, Any]:
    value = {
        "repeatable": bool(quest.repeatable),
        "disabled": bool(quest.disabled),
        "kill_turn_in_holder": bool(quest.kill_turn_in_holder),
        "destroy_turn_in_holder": bool(quest.destroy_turn_in_holder),
        "drop_invuln_on_holder": bool(quest.drop_invuln_on_holder),
        "once_per_spawn_instance": bool(quest.once_per_spawn_instance),
    }
    _put_if(value, "disabled_text", quest.disabled_text)
    return value


def _quest_type(graph: EntityGraph, quest: Node, nodes: dict[str, Node]) -> str | None:
    methods: list[str] = []
    if graph.out_edges(quest.key, EdgeType.REQUIRES_ITEM):
        methods.append("fetch")
    for edge_type, method in (
        (EdgeType.STEP_KILL, "kill"),
        (EdgeType.STEP_TALK, "dialog"),
        (EdgeType.STEP_TRAVEL, "zone_trigger"),
        (EdgeType.STEP_SHOUT, "shout"),
        (EdgeType.STEP_READ, "item_read"),
    ):
        if graph.out_edges(quest.key, edge_type):
            methods.append(method)
    if not methods:
        for edge in graph.out_edges(quest.key, EdgeType.COMPLETED_BY):
            target = nodes.get(edge.target)
            if target is None:
                continue
            if target.type == NodeType.CHARACTER:
                methods.append("fetch" if graph.out_edges(quest.key, EdgeType.REQUIRES_ITEM) else "dialog")
            elif target.type == NodeType.ZONE:
                methods.append("zone_trigger")
            elif target.type == NodeType.ITEM:
                methods.append("item_read")
            elif target.type == NodeType.QUEST:
                methods.append("chain")
    if not methods:
        return "unknown"
    return methods[0] if len(set(methods)) == 1 else "hybrid"


def _infer_zone(graph: EntityGraph, quest: Node, nodes: dict[str, Node]) -> str | None:
    for edge_type in (EdgeType.ASSIGNED_BY, EdgeType.COMPLETED_BY):
        for edge in graph.out_edges(quest.key, edge_type):
            target = nodes.get(edge.target)
            if target and target.zone:
                return target.zone
    return None


def _source_type(node: Node) -> str:
    return {
        NodeType.CHARACTER: "character",
        NodeType.ITEM: "item",
        NodeType.ZONE: "zone",
        NodeType.QUEST: "quest",
        NodeType.LOCATION: "location",
    }.get(node.type, node.type.value)


def _compiled_id(compiled: CompiledData, key: str) -> int:
    node_id = compiled.node_key_to_id.get(key)
    if node_id is None:
        raise ValueError(f"dangling compiled node key: {key!r}")
    return node_id


def _put_if(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _number(value: Any) -> float:
    return (
        value
        if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value))
        else float("inf")
    )


def _sanitize(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _requested_quality(use: ItemUse) -> str | None:
    values = {
        atom.value
        for atom in use.conditions
        if atom.predicate == "quality" and atom.phase in {"availability", "operation_input"} and atom.value is not None
    }
    if len(values) > 1:
        raise ValueError(f"Ambiguous requested quality: {use.use_key}")
    return next(iter(values), None)


def _canonical_item_sources(
    compiled: CompiledData,
    item_key: str,
    nodes: dict[str, Node],
    exclude_quest_key: str,
    visiting: frozenset[str],
    requested_quality: str | None = None,
) -> list[dict[str, Any]]:
    """Expand source choices by path, retaining exact native acquisition and use identities."""
    if item_key in visiting:
        return []
    visiting = visiting | {item_key}
    result: list[dict[str, Any]] = []
    types = {
        "character_drop": "drop",
        "vendor": "vendor",
        "dialog": "dialog_give",
        "crafting": "crafting",
        "quest_reward": "quest_reward",
        "mining": "mining",
        "fishing": "fishing",
        "item_bag": "pickup",
        "item_drop": "item_use",
        "spell_created": "item_use",
        "item_conversion": "item_use",
        "common_world_item": "common_world_item",
        "special_world_drop": "world_drop",
        "fishing_bonus": "fishing_bonus",
        "starting_class": "starting_class",
        "auction_house": "auction_house",
        "ui_grant": "ui_grant",
    }
    names = {
        "common_world_item": "Any enemy with common drops",
        "special_world_drop": "Any enemy",
        "fishing_bonus": "Any fishing catch",
        "starting_class": "Starting equipment",
        "auction_house": "Auction house",
        "ui_grant": "Native interface",
    }
    for fact in sorted(compiled.acquisitions_by_item.get(item_key, ()), key=lambda fact: fact.acquisition_key):
        if not is_actionable_acquisition(fact):
            continue
        if fact.kind not in types:
            raise ValueError(f"unsupported canonical acquisition kind: {fact.kind}")
        if fact.kind == "quest_reward" and fact.source_stable_key == exclude_quest_key:
            continue
        qualities = {
            atom.value
            for atom in fact.conditions
            if atom.predicate == "quality" and atom.phase == "operation_outcome" and atom.value is not None
        }
        if requested_quality is not None and qualities and requested_quality not in qualities:
            continue
        if len(qualities) > 1:
            raise ValueError(f"Ambiguous produced quality: {fact.acquisition_key}")
        source_key = fact.source_copy_stable_key or fact.source_stable_key
        metadata = compiled.source_metadata.get(fact.acquisition_key)
        source = nodes.get(source_key) if source_key is not None else None
        if source is None and metadata is not None:
            source = nodes.get(metadata.source)
        name = source.display_name if source is not None else names.get(fact.kind, nodes[item_key].display_name)
        locations = fact.locations or (None,)
        for location in locations:
            value: dict[str, Any] = {
                "type": types[fact.kind],
                "name": name,
                "acquisition_key": fact.acquisition_key,
                "item_stable_key": item_key,
            }
            _put_if(value, "source_key", source_key)
            _put_if(value, "quantity", fact.quantity_min)
            _put_if(value, "output_quality", next(iter(qualities), None))
            _put_if(value, "chance", fact.probability_min)
            _put_if(value, "chance_max", fact.probability_max)
            if fact.kind == "special_world_drop":
                minimum = next(
                    (
                        math.ceil(atom.minimum) if atom.minimum_inclusive else math.floor(atom.minimum) + 1
                        for atom in fact.conditions
                        if atom.predicate == "actor_level" and atom.actor == "enemy" and atom.minimum is not None
                    ),
                    None,
                )
                _put_if(value, "level", minimum)
            if fact.kind == "quest_reward":
                value["quest_key"] = fact.source_stable_key
            if fact.kind == "crafting" and fact.mechanic != "remove_blessing":
                value["recipe_key"] = f"recipe:{fact.source_stable_key}"
            if source is not None:
                level = _interaction_level(source) if value["type"] in _INTERACTION_SOURCE_TYPES else source.level
                _put_if(value, "level", level if level is not None and level > 0 else None)
            if metadata is not None:
                _put_if(value, "keyword", metadata.keyword)
                _put_if(value, "instruction", metadata.note)
            if fact.kind == "vendor":
                value["instruction"] = f"Buy {nodes[item_key].display_name}."
            if fact.kind in {"item_drop", "spell_created", "item_conversion"}:
                value["instruction"] = f"Use {name}."
            if fact.kind == "crafting" and fact.mechanic == "remove_blessing":
                value["type"] = "item_use"
                value["instruction"] = f"Use {name} with eligible equipment and forge fuel to remove its blessing."
                value["operation_use_keys"] = [
                    use.use_key for use in compiled.source_uses.get(fact.acquisition_key, ())
                ]
            period = next((atom.value for atom in fact.conditions if atom.predicate == "time_of_day"), None)
            _put_if(value, "time_restriction", period)
            if fact.kind == "fishing" and period in {"day", "night"}:
                value[f"{period}_chance"] = fact.probability_min
                value["night_chance" if period == "day" else "day_chance"] = 0
            if location is not None:
                value["location_key"] = location.location_key
                _put_if(value, "scene", location.scene)
                zone = nodes.get(location.zone_stable_key) if location.zone_stable_key is not None else None
                _put_if(value, "zone", zone.display_name if zone is not None else None)
                for axis in ("x", "y", "z"):
                    _put_if(value, axis, getattr(location, axis))
                if location.entry_zone_line_keys:
                    value["entry_zone_line_keys"] = list(location.entry_zone_line_keys)
                if location.relation == "possible_treasure":
                    value.update(
                        type="treasure_chest",
                        name="Treasure map chest",
                        instruction="Read a Treasure Map and dig at the marked spot.",
                    )
                    _put_if(value, "level", location.player_level_min)
                    _put_if(value, "level_max", location.player_level_max)
            children = []
            for use in sorted(compiled.source_uses.get(fact.acquisition_key, ()), key=lambda use: use.use_key):
                # Equipment and fuel choices are alternatives, not an AND list.
                # Their full phaseful records remain referenced as preparation.
                if fact.mechanic == "remove_blessing" and use.mechanic != "blessing_removal_material":
                    continue
                ingredient = nodes.get(use.item_stable_key)
                if ingredient is None:
                    raise ValueError(f"Canonical operation input missing: {use.use_key}")
                child: dict[str, Any] = {
                    "type": "ingredient",
                    "name": ingredient.display_name,
                    "item_stable_key": ingredient.key,
                    "use_key": use.use_key,
                    "quantity": use.quantity_min if use.quantity_min is not None else 1,
                    "children": _canonical_item_sources(
                        compiled, ingredient.key, nodes, exclude_quest_key, visiting, _requested_quality(use)
                    ),
                }
                child_id = compiled.node_key_to_id[ingredient.key]
                authored = _authored_item_sources(
                    compiled, child_id, {node.node_id: node for node in compiled.nodes}, nodes
                )
                child["children"].extend(_with_source_conditions(authored, ingredient, compiled))
                _sort_sources(child["children"])
                _put_if(child, "output_quality", _requested_quality(use))
                children.append(child)
            if children:
                value["children"] = children
            result.append(value)
    _sort_sources(result)
    return result


def _normalize_source_tables(result: dict[str, Any], compiled: CompiledData) -> None:
    """Emit each referenced typed record once, keeping evidence strictly offline."""
    acquisition_keys: set[str] = set()
    use_keys: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if "acquisition_key" in value:
                acquisition_keys.add(value["acquisition_key"])
            if "use_key" in value:
                use_keys.add(value["use_key"])
            use_keys.update(value.get("use_keys", ()))
            use_keys.update(value.get("operation_use_keys", ()))
            for member in value.values():
                visit(member)
        elif isinstance(value, list):
            for member in value:
                visit(member)

    visit(result)
    # An input's outcome is a real canonical reference even when a quality filter hid its source choice.
    for key in sorted(use_keys):
        use = compiled.source_facts.get(key)
        if not isinstance(use, ItemUse):
            raise ValueError(f"Missing canonical use: {key}")
        if use.outcome_key is not None:
            acquisition_keys.add(use.outcome_key)
    facts = {}
    for key in sorted(acquisition_keys):
        fact = compiled.source_facts.get(key)
        if not isinstance(fact, ItemAcquisition):
            raise ValueError(f"Missing canonical acquisition: {key}")
        facts[key] = {name: value for name, value in asdict(fact).items() if name != "evidence"}
    uses = {
        key: {name: value for name, value in asdict(compiled.source_facts[key]).items() if name != "evidence"}
        for key in sorted(use_keys)
    }
    result["_source_facts"] = facts
    result["_item_uses"] = uses


def _authored_item_sources(
    compiled: CompiledData, item_id: int, compiled_nodes: dict[int, Any], nodes: dict[str, Node]
) -> list[dict[str, Any]]:
    if item_id < 0 or item_id >= len(compiled.node_item_index):
        raise ValueError(f"dangling compiled item id: {item_id}")
    item_index = compiled.node_item_index[item_id]
    if item_index < 0:
        return []
    if item_index >= len(compiled.item_sources):
        raise ValueError(f"dangling compiled item index: {item_index}")
    result: list[dict[str, Any]] = []
    type_map = {
        EdgeType.DROPS_ITEM: "drop",
        EdgeType.SELLS_ITEM: "vendor",
        EdgeType.GIVES_ITEM: "dialog_give",
        EdgeType.CONTAINS: "pickup",
        EdgeType.PRODUCES: "crafting",
    }
    yield_type_map = {
        node_type_byte(NodeType.WATER): "fishing",
        node_type_byte(NodeType.ITEM_BAG): "pickup",
        node_type_byte(NodeType.MINING_NODE): "mining",
    }
    edge_types = {edge_type_byte(edge_type): edge_type for edge_type in EdgeType}
    for site in compiled.item_sources[item_index]:
        if site.provenance_key is not None:
            continue
        source = compiled_nodes[site.source_id]
        edge_type = edge_types.get(site.edge_type)
        if edge_type == EdgeType.YIELDS_ITEM:
            source_type = yield_type_map.get(source.node_type)
            if source_type is None:
                raise ValueError(f"unsupported yielding source node: {source.key!r}")
        elif edge_type in type_map:
            source_type = type_map[edge_type]
        else:
            continue
        value: dict[str, Any] = {"type": source_type, "name": source.display_name}
        _put_if(value, "zone", source.zone_display)
        _put_if(value, "scene", site.scene)
        level = source.level
        if source_type in _INTERACTION_SOURCE_TYPES and source.key in nodes:
            level = _interaction_level(nodes[source.key])
        _put_if(value, "level", level if level is not None and level > 0 else None)
        if edge_type != EdgeType.PRODUCES:
            value["source_key"] = source.key
        else:
            value["recipe_key"] = source.key
        _put_if(value, "chance", site.chance)
        _put_if(value, "day_chance", site.day_chance)
        _put_if(value, "night_chance", site.night_chance)
        _put_if(value, "time_restriction", site.time_restriction)
        _put_if(value, "keyword", site.keyword)
        if edge_type == EdgeType.DROPS_ITEM:
            _put_if(value, "instruction", site.note)
            value["spawn_count"] = len(site.positions)
        if source_type == "pickup":
            _put_if(value, "instruction", source.description)
        result.append(value)
    result.extend(
        {key: value for key, value in asdict(source).items() if value is not None and key != "provenance_key"}
        for source in compiled_nodes[item_id].background_sources
    )
    return result


def _selected_facts(compiled: CompiledData) -> Iterable[ItemAcquisition | ItemUse]:
    for facts in compiled.acquisitions_by_item.values():
        yield from facts
    for uses in compiled.source_uses.values():
        yield from uses
    for uses in compiled.quest_uses.values():
        yield from uses
