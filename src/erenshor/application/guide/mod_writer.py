"""Offline assembler for the legacy AdventureGuide mod wrapper.

The graph is the source of semantics and ``CompiledData`` supplies the dense
indexes and precomputed item source sites.  No database access belongs here:
the output is a deliberately boring, deterministic compatibility view.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

from .compiler import CompiledData, edge_type_byte, node_type_byte
from .schema import Edge, EdgeType, Node, NodeType

if TYPE_CHECKING:
    from .graph import EntityGraph


def build_mod_guide(graph: EntityGraph, compiled: CompiledData) -> dict[str, Any]:
    """Build the stable, depth-one JSON shape consumed by the C# mod."""
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

    # Build the frequently used reverse indexes once.  In particular, item
    # source and unlock assembly must not repeatedly walk the whole graph.
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]] = defaultdict(list)
    outgoing_unlocks: dict[tuple[EdgeType, str], list[Edge]] = defaultdict(list)
    incoming_chain: dict[str, list[Edge]] = defaultdict(list)
    for edge in graph.all_edges():
        if edge.source not in nodes or edge.target not in nodes:
            continue
        if edge.type in (EdgeType.UNLOCKS_CHARACTER, EdgeType.UNLOCKS_ZONE_LINE):
            incoming_unlocks[(edge.type, edge.target)].append(edge)
            outgoing_unlocks[(edge.type, edge.source)].append(edge)
        elif edge.type in (EdgeType.CHAINS_TO, EdgeType.ALSO_COMPLETES):
            incoming_chain[edge.target].append(edge)

    result: dict[str, Any] = {
        "_version": 5,
        "_zone_lookup": _zone_lookup(nodes),
        "_character_spawns": _character_spawns(graph, nodes),
        "_zone_lines": _zone_lines(graph, nodes, incoming_unlocks, db_names),
        "_chain_groups": _chain_groups(quests, graph, nodes, db_names),
        "_character_quest_unlocks": _character_unlocks(nodes, incoming_unlocks, db_names),
        "quests": [
            _quest_entry(
                quest,
                graph,
                nodes,
                compiled,
                compiled_nodes,
                reward_by_item,
                incoming_unlocks,
                outgoing_unlocks,
                incoming_chain,
                db_names,
            )
            for quest in quests
        ],
    }
    return cast("dict[str, Any]", _sanitize(result))


def serialize_mod_guide(graph: EntityGraph, compiled: CompiledData) -> str:
    """Build and compactly serialize the legacy wrapper deterministically."""
    return json.dumps(build_mod_guide(graph, compiled), separators=(",", ":"), allow_nan=False)


def _validate_quest_identity(quests: list[Node]) -> None:
    seen: set[str] = set()
    for quest in quests:
        if not quest.key or not quest.db_name:
            raise ValueError(f"malformed quest identity: {quest.key!r}")
        if quest.db_name in seen:
            raise ValueError(f"duplicate quest db_name: {quest.db_name!r}")
        seen.add(quest.db_name)


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
    references = [
        *compiled.quest_node_ids,
        *compiled.item_node_ids,
        *compiled.zone_node_ids,
        *compiled.infeasible_node_ids,
    ]
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
                if position.spawn_id not in nodes:
                    raise ValueError(f"dangling compiled spawn id: {position.spawn_id}")
    return compiled.edges


def _reward_edges_by_item(compiled_edges: list[Any]) -> dict[int, list[Any]]:
    result: dict[int, list[Any]] = defaultdict(list)
    rewards_type = edge_type_byte(EdgeType.REWARDS_ITEM)
    for edge in compiled_edges:
        if edge.edge_type == rewards_type:
            result[edge.target_id].append(edge)
    return result


def _required_coordinate(node: Node, axis: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid {axis} coordinate for node {node.key!r}")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(f"invalid {axis} coordinate for node {node.key!r}")
    return cast("int | float", value)


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


def _character_spawns(graph: EntityGraph, nodes: dict[str, Node]) -> dict[str, list[dict[str, Any]]]:
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
            value = {
                "scene": spawn.scene,
                "x": x,
                "y": y,
                "z": z,
                "night_spawn": bool(spawn.night_spawn),
            }
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


def _zone_lines(
    graph: EntityGraph,
    nodes: dict[str, Node],
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]],
    db_names: dict[str, str | None],
) -> list[dict[str, Any]]:
    result: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for line in nodes.values():
        if line.type != NodeType.ZONE_LINE or not line.scene:
            continue
        x = _required_coordinate(line, "x", line.x)
        y = _required_coordinate(line, "y", line.y)
        z = _required_coordinate(line, "z", line.z)
        value: dict[str, Any] = {
            "scene": line.scene,
            "x": x,
            "y": y,
            "z": z,
            "is_enabled": bool(line.is_enabled),
        }
        _put_if(value, "destination_zone_key", line.destination_zone_key)
        _put_if(value, "destination_display", line.destination_display)
        _put_if(value, "landing_x", line.landing_x)
        _put_if(value, "landing_y", line.landing_y)
        _put_if(value, "landing_z", line.landing_z)
        groups = _unlock_groups(incoming_unlocks.get((EdgeType.UNLOCKS_ZONE_LINE, line.key), []), db_names)
        if groups:
            value["required_quest_groups"] = groups
        key = (line.scene, _number(x), _number(y), _number(z), line.key)
        result.append((key, value))
    result.sort(key=lambda pair: pair[0])
    return [value for _, value in result]


def _character_unlocks(
    nodes: dict[str, Node],
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]],
    db_names: dict[str, str | None],
) -> dict[str, list[list[str]]]:
    result: dict[str, list[list[str]]] = {}
    for character in sorted(
        (node for node in nodes.values() if node.type == NodeType.CHARACTER), key=lambda node: node.key
    ):
        groups = _unlock_groups(incoming_unlocks.get((EdgeType.UNLOCKS_CHARACTER, character.key), []), db_names)
        if groups:
            result[character.key] = groups
    return result


def _unlock_groups(edges: list[Edge], db_names: dict[str, str | None]) -> list[list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        db_name = db_names.get(edge.source)
        if db_name:
            grouped[edge.group or "__ungrouped__"].add(db_name)
    return [sorted(values) for _, values in sorted(grouped.items(), key=lambda pair: pair[0]) if values]


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
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]],
    outgoing_unlocks: dict[tuple[EdgeType, str], list[Edge]],
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
    prerequisites.extend(_implicit_character_prerequisites(graph, quest, nodes, incoming_unlocks))
    prerequisites = _dedupe_prerequisites(prerequisites)
    completion = _completion(graph, quest, nodes, required_items)
    steps = _steps(graph, quest, nodes, required_items, completion, compiled, compiled_nodes)
    rewards = _rewards(quest, graph, nodes, outgoing_unlocks, incoming_unlocks, db_names)
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
        sources = _item_sources_with_rewards(compiled, item_id, compiled_nodes, reward_by_item, quest.key)
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


def _implicit_character_prerequisites(
    graph: EntityGraph,
    quest: Node,
    nodes: dict[str, Node],
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    targets: list[Node] = []
    for edge_type in (EdgeType.ASSIGNED_BY, EdgeType.COMPLETED_BY):
        for edge in graph.out_edges(quest.key, edge_type):
            target = nodes.get(edge.target)
            if target is not None and target.type == NodeType.CHARACTER:
                targets.append(target)
    for character in targets:
        unlock_edges = incoming_unlocks.get((EdgeType.UNLOCKS_CHARACTER, character.key), [])
        grouped: dict[str, list[Edge]] = defaultdict(list)
        for edge in unlock_edges:
            grouped[edge.group or "__ungrouped__"].append(edge)
        if not grouped:
            continue
        smallest = min(
            grouped.values(),
            key=lambda edges: (len(edges), sorted(edge.source for edge in edges)),
        )
        for edge in smallest:
            prerequisite = nodes.get(edge.source)
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
    candidates: dict[str, Edge] = {}
    candidate_rank: dict[str, tuple[int, int, str]] = {}
    edge_groups = (
        (0, EdgeType.REQUIRES_ITEM),
        (1, EdgeType.STEP_READ),
        (2, EdgeType.COMPLETED_BY),
    )
    for rank, edge_type in edge_groups:
        for edge in graph.out_edges(quest.key, edge_type):
            item = nodes.get(edge.target)
            if item is None or item.type != NodeType.ITEM:
                continue
            ordinal = edge.ordinal if edge.ordinal is not None else 2**31
            sort_key = (rank, ordinal, edge.target)
            if item.key not in candidate_rank or sort_key < candidate_rank[item.key]:
                candidates[item.key] = edge
                candidate_rank[item.key] = sort_key

    result: list[tuple[str, dict[str, Any]]] = []
    for item_key in sorted(candidates):
        edge = candidates[item_key]
        item = nodes[item_key]
        value: dict[str, Any] = {
            "item_name": item.display_name,
            "item_stable_key": item.key,
            "quantity": edge.quantity if edge.type == EdgeType.REQUIRES_ITEM and edge.quantity is not None else 1,
        }
        _put_if(value, "or_group", edge.group)
        item_id = _compiled_id(compiled, item.key)
        if item_id not in compiled_nodes:
            raise ValueError(f"dangling compiled node id for key: {item.key!r}")
        sources = _item_sources_with_rewards(compiled, item_id, compiled_nodes, reward_by_item, quest.key)
        if sources:
            value["sources"] = sources
        result.append((item.key, value))
    return [value for _, value in result]


def _item_sources(compiled: CompiledData, item_id: int, compiled_nodes: dict[int, Any]) -> list[dict[str, Any]]:
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
        _put_if(value, "level", source.level if source.level > 0 else None)
        if edge_type != EdgeType.PRODUCES:
            value["source_key"] = source.key
        else:
            value["recipe_key"] = source.key
        if edge_type == EdgeType.DROPS_ITEM:
            value["spawn_count"] = len(site.positions)
        result.append(value)
    return result


def _item_sources_with_rewards(
    compiled: CompiledData,
    item_id: int,
    compiled_nodes: dict[int, Any],
    reward_by_item: dict[int, list[Any]],
    exclude_quest_key: str,
) -> list[dict[str, Any]]:
    sources = _item_sources(compiled, item_id, compiled_nodes)
    for reward in reward_by_item.get(item_id, []):
        source_node = compiled_nodes[reward.source_id]
        if source_node.key == exclude_quest_key:
            continue
        source = {"type": "quest_reward", "name": source_node.display_name, "quest_key": source_node.key}
        _put_if(source, "level", source_node.level if source_node.level > 0 else None)
        sources.append(source)
    sources.sort(
        key=lambda source: (
            source.get("level") is None,
            source.get("level", 0),
            source.get("type", ""),
            source.get("name", ""),
            source.get("source_key", ""),
        )
    )
    return sources


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
    result.sort(key=lambda item: item[0])
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
            if target.level is None or target.level <= 0:
                return None
            return {
                "recommended": target.level,
                "factors": [{"source": "zone", "name": target.zone or target.display_name, "level": target.level}],
            }
        if target.type != NodeType.ITEM or action not in {"collect", "read"}:
            return None
        item = required_by_key.get(target.key)
        sources = item.get("sources", []) if item is not None else source_cache.get(target.key)
        if sources is None:
            item_id = _compiled_id(compiled, target.key)
            if item_id not in compiled_nodes:
                raise ValueError(f"dangling compiled node id for key: {target.key!r}")
            sources = _item_sources(compiled, item_id, compiled_nodes)
            source_cache[target.key] = sources
        return _item_level_estimate(sources)

    for edge in graph.out_edges(quest.key, EdgeType.ASSIGNED_BY):
        target = nodes.get(edge.target)
        if target is None or target.type not in {NodeType.CHARACTER, NodeType.ITEM}:
            continue
        action = "talk" if target.type == NodeType.CHARACTER else "read"
        step = _step_value(action, target, edge.keyword, edge.group)
        _put_if(step, "level_estimate", level_for(target, action))
        entries.append((edge.ordinal if edge.ordinal is not None else -1000000, sequence, step))
        sequence += 1
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
        _put_if(step, "level_estimate", level_for(nodes[item["item_stable_key"]], "collect"))
        entries.append((-500000, sequence, step))
        sequence += 1
    step_types = {
        EdgeType.STEP_TALK: "talk",
        EdgeType.STEP_KILL: "kill",
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
            step = _step_value(action, target, edge.keyword, edge.group)
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
    for order, (_, _, step_payload) in enumerate(entries, 1):
        step_payload["order"] = order
        ordered_step = {"order": step_payload.pop("order"), **step_payload}
        result.append(ordered_step)
    return result


def _item_level_estimate(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    factors: set[tuple[str, str, int]] = set()
    for source in sources:
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


def _step_value(action: str, target: Node, keyword: str | None, or_group: str | None = None) -> dict[str, Any]:
    if action == "talk":
        description = f'Say "{keyword}" to {target.display_name}.' if keyword else f"Speak to {target.display_name}."
    elif action == "kill":
        description = f"Defeat {target.display_name}."
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
    return value


def _rewards(
    quest: Node,
    graph: EntityGraph,
    nodes: dict[str, Node],
    outgoing_unlocks: dict[tuple[EdgeType, str], list[Edge]],
    incoming_unlocks: dict[tuple[EdgeType, str], list[Edge]],
    db_names: dict[str, str | None],
) -> dict[str, Any]:
    value: dict[str, Any] = {"xp": quest.xp_reward or 0, "gold": quest.gold_reward or 0}
    if quest.reward_item_key:
        item = nodes.get(quest.reward_item_key)
        if item:
            value["item_name"] = item.display_name
            value["item_stable_key"] = item.key
    vendor_unlocks: dict[tuple[str, str], dict[str, str]] = {}
    for edge in graph.out_edges(quest.key, EdgeType.UNLOCKS_VENDOR_ITEM):
        item = nodes.get(edge.target)
        vendor = nodes.get(edge.note) if edge.note else None
        if item is None or vendor is None:
            continue
        pair = (item.key, vendor.key)
        vendor_unlocks[pair] = {"item_name": item.display_name, "vendor_name": vendor.display_name}
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
    for edge in outgoing_unlocks.get((EdgeType.UNLOCKS_ZONE_LINE, quest.key), []):
        line = nodes.get(edge.target)
        if line is None:
            continue
        entry: dict[str, Any] = {
            "from_zone": line.zone or "",
            "to_zone": line.destination_display or line.destination_zone_key or "",
        }
        group = edge.group
        if group:
            same_group: list[str] = []
            for unlock in incoming_unlocks.get((EdgeType.UNLOCKS_ZONE_LINE, line.key), []):
                if unlock.group != group:
                    continue
                name = db_names.get(unlock.source)
                if name is not None and name != quest.db_name:
                    same_group.append(name)
            if same_group:
                entry["co_requirements"] = sorted(set(same_group))
        unlocked_lines.append(entry)
    if unlocked_lines:
        unlocked_lines.sort(
            key=lambda item: (item["from_zone"], item["to_zone"], tuple(item.get("co_requirements", [])))
        )
        value["unlocked_zone_lines"] = unlocked_lines
    unlocked_chars = []
    for edge in outgoing_unlocks.get((EdgeType.UNLOCKS_CHARACTER, quest.key), []):
        character = nodes.get(edge.target)
        if character is not None:
            entry = {"name": character.display_name}
            _put_if(entry, "zone", character.zone)
            unlocked_chars.append(entry)
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
    return {NodeType.CHARACTER: "character", NodeType.ITEM: "item", NodeType.ZONE: "zone", NodeType.QUEST: "quest"}.get(
        node.type, node.type.value
    )


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
