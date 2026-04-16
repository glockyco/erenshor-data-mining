"""Compiled guide data model and graph-to-binary compilation entrypoints.

The compiler converts the dynamic :mod:`erenshor.application.guide.graph`
representation into dense integer-indexed structures that are cheap to serialize
and cheap for the C# runtime to load.

This module starts with the plain data model. Analysis and serialization helpers
are added incrementally by later tasks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from .schema import Edge, EdgeType, Node, NodeType

if TYPE_CHECKING:
    from .graph import EntityGraph


class NodeFlags(IntEnum):
    """Packed bitflags emitted for nodes in the binary format."""

    IS_FRIENDLY = 1 << 0
    IS_VENDOR = 1 << 1
    NIGHT_SPAWN = 1 << 2
    IMPLICIT = 1 << 3
    REPEATABLE = 1 << 4
    DISABLED = 1 << 5
    IS_DIRECTLY_PLACED = 1 << 6
    IS_ENABLED = 1 << 7
    INVULNERABLE = 1 << 8
    IS_RARE = 1 << 9
    IS_TRIGGER_SPAWN = 1 << 10


class EdgeFlags(IntEnum):
    """Packed bitflags emitted for edges in the binary format."""

    NEGATED = 1 << 0
    HAS_GROUP = 1 << 1
    HAS_QUANTITY = 1 << 2
    HAS_KEYWORD = 1 << 3
    HAS_CHANCE = 1 << 4


@dataclass(slots=True)
class CompiledNode:
    """Node record stored in the compiled guide before binary encoding."""

    node_id: int
    key: str
    node_type: int
    display_name: str
    scene: str | None
    x: float = math.nan
    y: float = math.nan
    z: float = math.nan
    flags: int = 0
    level: int = 0
    zone_key: str | None = None
    db_name: str | None = None
    description: str | None = None
    keyword: str | None = None
    zone_display: str | None = None
    xp_reward: int = 0
    gold_reward: int = 0
    reward_item_key: str | None = None
    disabled_text: str | None = None
    key_item_key: str | None = None
    destination_zone_key: str | None = None
    destination_display: str | None = None


@dataclass(slots=True)
class CompiledEdge:
    """Edge record stored in the compiled guide before binary encoding."""

    source_id: int
    target_id: int
    edge_type: int
    flags: int = 0
    group: str | None = None
    ordinal: int = 0
    quantity: int = 0
    keyword: str | None = None
    chance: int = 0
    note: str | None = None
    amount: int = 0


@dataclass(slots=True)
class SpawnPosition:
    spawn_id: int
    x: float
    y: float
    z: float


@dataclass(slots=True)
class SourceSite:
    source_id: int
    source_type: int
    edge_type: int
    direct_item_id: int = 0
    scene: str | None = None
    positions: list[SpawnPosition] = field(default_factory=list)
    keyword: str | None = None


@dataclass(slots=True)
class UnlockCondition:
    source_id: int
    check_type: int
    group: int = 0


@dataclass(slots=True)
class UnlockPredicate:
    target_id: int
    conditions: list[UnlockCondition] = field(default_factory=list)
    group_count: int = 0
    semantics: int = 0


@dataclass(slots=True)
class StepSpec:
    step_type: int
    target_id: int
    ordinal: int = 0


@dataclass(slots=True)
class ItemRequirement:
    item_id: int
    qty: int
    group: int = 0


@dataclass(slots=True)
class QuestSpec:
    """Precomputed quest-level structure consumed by the runtime.

    The compiler stores both dense quest-index references and raw node IDs where
    that improves downstream access patterns. Fields are intentionally simple so
    the binary writer can serialize them directly without additional mapping.
    """

    quest_id: int
    quest_index: int
    prereq_quest_ids: list[int] = field(default_factory=list)
    prereq_quest_indices: list[int] = field(default_factory=list)
    required_items: list[ItemRequirement] = field(default_factory=list)
    steps: list[StepSpec] = field(default_factory=list)
    giver_node_ids: list[int] = field(default_factory=list)
    completer_node_ids: list[int] = field(default_factory=list)
    chains_to_ids: list[int] = field(default_factory=list)
    is_implicit: bool = False
    is_infeasible: bool = False
    display_name: str = ""


@dataclass(slots=True)
class QuestGiverBlueprint:
    quest_id: int
    character_id: int
    position_id: int
    interaction_type: int = 0
    keyword: str | None = None
    required_quest_db_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QuestCompletionBlueprint:
    quest_id: int
    character_id: int
    position_id: int
    interaction_type: int = 0
    keyword: str | None = None


@dataclass(slots=True)
class CompiledData:
    """All precomputed guide data ready for binary serialization.

    The structure intentionally keeps both record-oriented views (`nodes` /
    `edges`) and flattened lookup tables (`node_keys`, `node_levels`, dense
    inverse indices) because the integration tests and later C# loader both need
    them.
    """

    nodes: list[CompiledNode] = field(default_factory=list)
    edges: list[CompiledEdge] = field(default_factory=list)

    node_keys: list[str] = field(default_factory=list)
    node_levels: list[int] = field(default_factory=list)
    node_key_to_id: dict[str, int] = field(default_factory=dict)
    node_quest_index: list[int] = field(default_factory=list)
    node_item_index: list[int] = field(default_factory=list)

    quest_node_ids: list[int] = field(default_factory=list)
    item_node_ids: list[int] = field(default_factory=list)

    forward_adjacency: list[list[int]] = field(default_factory=list)
    reverse_adjacency: list[list[int]] = field(default_factory=list)

    quest_specs: list[QuestSpec] = field(default_factory=list)
    item_sources: list[list[SourceSite]] = field(default_factory=list)
    unlock_predicates: list[UnlockPredicate] = field(default_factory=list)

    topo_order: list[int] = field(default_factory=list)
    item_to_quest_indices: list[list[int]] = field(default_factory=list)
    quest_to_dependent_quest_indices: list[list[int]] = field(default_factory=list)

    zone_node_ids: list[int] = field(default_factory=list)
    zone_adjacency: list[list[int]] = field(default_factory=list)
    zone_line_ids: list[list[int]] = field(default_factory=list)

    giver_blueprints: list[QuestGiverBlueprint] = field(default_factory=list)
    completion_blueprints: list[QuestCompletionBlueprint] = field(default_factory=list)

    infeasible_node_ids: set[int] = field(default_factory=set)

    @property
    def topological_order(self) -> list[int]:
        """Alias used by the architecture plan and future C# loader tests."""

        return self.topo_order


_NODE_TYPE_ORDER = list(NodeType)
_EDGE_TYPE_ORDER = list(EdgeType)


def node_type_byte(node_type: NodeType) -> int:
    """Stable ordinal used in the binary format for :class:`NodeType`."""

    return _NODE_TYPE_ORDER.index(node_type)


def edge_type_byte(edge_type: EdgeType) -> int:
    """Stable ordinal used in the binary format for :class:`EdgeType`."""

    return _EDGE_TYPE_ORDER.index(edge_type)


def compile_graph(graph: EntityGraph) -> CompiledData:
    """Compile an :class:`EntityGraph` into :class:`CompiledData`."""

    compiled = CompiledData()
    _compile_nodes(graph, compiled)
    _compile_edges(graph, compiled)
    _assign_dense_indices(compiled)
    _compile_topology(compiled)
    _compile_quest_specs(compiled)
    _compile_item_sources(compiled)
    _compile_unlock_predicates(compiled)
    _compile_reverse_dependencies(compiled)
    _compile_zones(compiled)
    _compile_blueprints(graph, compiled)
    return compiled


def _compile_nodes(graph: EntityGraph, compiled: CompiledData) -> None:
    nodes = sorted(graph.all_nodes(), key=lambda node: node.key)
    compiled.node_keys = [node.key for node in nodes]
    compiled.node_key_to_id = {key: idx for idx, key in enumerate(compiled.node_keys)}
    compiled.nodes = [
        CompiledNode(
            node_id=compiled.node_key_to_id[node.key],
            key=node.key,
            node_type=node_type_byte(node.type),
            display_name=node.display_name,
            scene=node.scene,
            x=node.x if node.x is not None else math.nan,
            y=node.y if node.y is not None else math.nan,
            z=node.z if node.z is not None else math.nan,
            flags=_node_flags(node),
            level=max(node.level or 0, 0),
            zone_key=node.zone_key,
            db_name=node.db_name,
            description=node.description,
            keyword=node.keyword,
            zone_display=node.zone,
            xp_reward=node.xp_reward or 0,
            gold_reward=node.gold_reward or 0,
            reward_item_key=node.reward_item_key,
            disabled_text=node.disabled_text,
            key_item_key=node.key_item_key,
            destination_zone_key=node.destination_zone_key,
            destination_display=node.destination_display,
        )
        for node in nodes
    ]
    compiled.node_levels = [node.level for node in compiled.nodes]
    compiled.node_quest_index = [-1] * len(compiled.nodes)
    compiled.node_item_index = [-1] * len(compiled.nodes)
    compiled.forward_adjacency = [[] for _ in compiled.nodes]
    compiled.reverse_adjacency = [[] for _ in compiled.nodes]


def _node_flags(node: Node) -> int:
    flags = 0
    if node.is_friendly:
        flags |= NodeFlags.IS_FRIENDLY
    if node.is_vendor:
        flags |= NodeFlags.IS_VENDOR
    if node.night_spawn:
        flags |= NodeFlags.NIGHT_SPAWN
    if node.implicit:
        flags |= NodeFlags.IMPLICIT
    if node.repeatable:
        flags |= NodeFlags.REPEATABLE
    if node.disabled:
        flags |= NodeFlags.DISABLED
    if node.is_directly_placed:
        flags |= NodeFlags.IS_DIRECTLY_PLACED
    if node.is_enabled:
        flags |= NodeFlags.IS_ENABLED
    if node.invulnerable:
        flags |= NodeFlags.INVULNERABLE
    if node.is_rare:
        flags |= NodeFlags.IS_RARE
    if node.is_trigger_spawn:
        flags |= NodeFlags.IS_TRIGGER_SPAWN
    return flags


def _compile_edges(graph: EntityGraph, compiled: CompiledData) -> None:
    compiled.edges = []
    for edge in graph.all_edges():
        source_id = compiled.node_key_to_id.get(edge.source)
        target_id = compiled.node_key_to_id.get(edge.target)
        if source_id is None or target_id is None:
            continue
        compiled_edge = CompiledEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type_byte(edge.type),
            flags=_edge_flags(edge),
            group=edge.group,
            ordinal=edge.ordinal or 0,
            quantity=edge.quantity or 0,
            keyword=edge.keyword,
            chance=round((edge.chance or 0.0) * 1000),
            note=edge.note,
            amount=edge.amount or 0,
        )
        edge_id = len(compiled.edges)
        compiled.edges.append(compiled_edge)
        compiled.forward_adjacency[source_id].append(edge_id)
        compiled.reverse_adjacency[target_id].append(edge_id)


def _edge_flags(edge: Edge) -> int:
    flags = 0
    if edge.negated:
        flags |= EdgeFlags.NEGATED
    if edge.group:
        flags |= EdgeFlags.HAS_GROUP
    if edge.quantity is not None:
        flags |= EdgeFlags.HAS_QUANTITY
    if edge.keyword:
        flags |= EdgeFlags.HAS_KEYWORD
    if edge.chance is not None:
        flags |= EdgeFlags.HAS_CHANCE
    return flags


def _assign_dense_indices(compiled: CompiledData) -> None:
    compiled.quest_node_ids = [
        node.node_id for node in compiled.nodes if node.node_type == node_type_byte(NodeType.QUEST)
    ]
    compiled.item_node_ids = [
        node.node_id for node in compiled.nodes if node.node_type == node_type_byte(NodeType.ITEM)
    ]
    for qi, node_id in enumerate(compiled.quest_node_ids):
        compiled.node_quest_index[node_id] = qi
    for ii, node_id in enumerate(compiled.item_node_ids):
        compiled.node_item_index[node_id] = ii


def _compile_topology(compiled: CompiledData) -> None:
    quest_count = len(compiled.quest_node_ids)
    in_degree = [0] * quest_count
    dependents: list[list[int]] = [[] for _ in range(quest_count)]
    requires_quest = edge_type_byte(EdgeType.REQUIRES_QUEST)

    for quest_index, quest_node_id in enumerate(compiled.quest_node_ids):
        seen_prereqs: set[int] = set()
        for edge_id in compiled.forward_adjacency[quest_node_id]:
            edge = compiled.edges[edge_id]
            if edge.edge_type != requires_quest:
                continue
            prereq_index = compiled.node_quest_index[edge.target_id]
            if prereq_index == -1 or prereq_index in seen_prereqs:
                continue
            seen_prereqs.add(prereq_index)
            in_degree[quest_index] += 1
            dependents[prereq_index].append(quest_index)

    from collections import deque

    queue = deque(index for index, degree in enumerate(in_degree) if degree == 0)
    topo_order: list[int] = []
    while queue:
        quest_index = queue.popleft()
        topo_order.append(quest_index)
        for dependent in dependents[quest_index]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(topo_order) < quest_count:
        seen = set(topo_order)
        for quest_index in range(quest_count):
            if quest_index in seen:
                continue
            topo_order.append(quest_index)
            compiled.infeasible_node_ids.add(compiled.quest_node_ids[quest_index])

    compiled.topo_order = topo_order


def _compile_quest_specs(compiled: CompiledData) -> None:
    compiled.quest_specs = []
    step_types = {
        edge_type_byte(EdgeType.STEP_TALK),
        edge_type_byte(EdgeType.STEP_KILL),
        edge_type_byte(EdgeType.STEP_TRAVEL),
        edge_type_byte(EdgeType.STEP_SHOUT),
        edge_type_byte(EdgeType.STEP_READ),
    }
    requires_quest = edge_type_byte(EdgeType.REQUIRES_QUEST)
    requires_item = {edge_type_byte(EdgeType.REQUIRES_ITEM), edge_type_byte(EdgeType.REQUIRES_MATERIAL)}
    assigned_by = edge_type_byte(EdgeType.ASSIGNED_BY)
    completed_by = edge_type_byte(EdgeType.COMPLETED_BY)
    chains_to = edge_type_byte(EdgeType.CHAINS_TO)

    for quest_index, quest_node_id in enumerate(compiled.quest_node_ids):
        node = compiled.nodes[quest_node_id]
        spec = QuestSpec(
            quest_id=quest_node_id,
            quest_index=quest_index,
            is_implicit=bool(node.flags & NodeFlags.IMPLICIT),
            is_infeasible=quest_node_id in compiled.infeasible_node_ids,
            display_name=node.display_name,
        )
        for edge_id in compiled.forward_adjacency[quest_node_id]:
            edge = compiled.edges[edge_id]
            if edge.edge_type == requires_quest:
                spec.prereq_quest_ids.append(edge.target_id)
                prereq_index = compiled.node_quest_index[edge.target_id]
                if prereq_index != -1:
                    spec.prereq_quest_indices.append(prereq_index)
            elif edge.edge_type in requires_item:
                spec.required_items.append(ItemRequirement(item_id=edge.target_id, qty=edge.quantity or 1, group=0))
            elif edge.edge_type in step_types:
                spec.steps.append(StepSpec(step_type=edge.edge_type, target_id=edge.target_id, ordinal=edge.ordinal))
            elif edge.edge_type == assigned_by:
                spec.giver_node_ids.append(edge.target_id)
            elif edge.edge_type == completed_by:
                spec.completer_node_ids.append(edge.target_id)
            elif edge.edge_type == chains_to:
                spec.chains_to_ids.append(edge.target_id)
        compiled.quest_specs.append(spec)


def _compile_item_sources(compiled: CompiledData) -> None:
    source_edge_types = {
        edge_type_byte(EdgeType.DROPS_ITEM),
        edge_type_byte(EdgeType.SELLS_ITEM),
        edge_type_byte(EdgeType.GIVES_ITEM),
        edge_type_byte(EdgeType.YIELDS_ITEM),
        edge_type_byte(EdgeType.CONTAINS),
        edge_type_byte(EdgeType.PRODUCES),
    }
    has_spawn = edge_type_byte(EdgeType.HAS_SPAWN)
    gives_item = edge_type_byte(EdgeType.GIVES_ITEM)
    compiled.item_sources = [[] for _ in compiled.item_node_ids]

    for item_index, item_node_id in enumerate(compiled.item_node_ids):
        sources: list[SourceSite] = []
        for edge_id in compiled.reverse_adjacency[item_node_id]:
            edge = compiled.edges[edge_id]
            if edge.edge_type not in source_edge_types:
                continue
            source_node = compiled.nodes[edge.source_id]
            positions: list[SpawnPosition] = []
            for source_edge_id in compiled.forward_adjacency[edge.source_id]:
                source_edge = compiled.edges[source_edge_id]
                if source_edge.edge_type != has_spawn:
                    continue
                spawn_node = compiled.nodes[source_edge.target_id]
                positions.append(
                    SpawnPosition(
                        spawn_id=spawn_node.node_id,
                        x=spawn_node.x,
                        y=spawn_node.y,
                        z=spawn_node.z,
                    )
                )
            if not positions and not math.isnan(source_node.x):
                positions.append(
                    SpawnPosition(
                        spawn_id=source_node.node_id,
                        x=source_node.x,
                        y=source_node.y,
                        z=source_node.z,
                    )
                )
            sources.append(
                SourceSite(
                    source_id=edge.source_id,
                    source_type=source_node.node_type,
                    edge_type=edge.edge_type,
                    direct_item_id=0,
                    scene=source_node.scene,
                    positions=positions,
                    keyword=edge.keyword if edge.edge_type == gives_item else None,
                )
            )
        compiled.item_sources[item_index] = sources


def _compile_unlock_predicates(compiled: CompiledData) -> None:
    unlock_target_edge_types = {
        edge_type_byte(EdgeType.UNLOCKS_CHARACTER),
        edge_type_byte(EdgeType.UNLOCKS_ZONE_LINE),
        edge_type_byte(EdgeType.UNLOCKS_VENDOR_ITEM),
        edge_type_byte(EdgeType.UNLOCKS_DOOR),
    }
    gated_by_quest = edge_type_byte(EdgeType.GATED_BY_QUEST)
    item_type = node_type_byte(NodeType.ITEM)
    door_type = node_type_byte(NodeType.DOOR)
    predicates: dict[int, list[UnlockCondition]] = {}

    for edge in compiled.edges:
        if edge.edge_type in unlock_target_edge_types:
            target_id = edge.target_id
            source_id = edge.source_id
        elif edge.edge_type == gated_by_quest:
            target_id = edge.source_id
            source_id = edge.target_id
        else:
            continue
        group = 1 if edge.group else 0
        # check_type 0 = quest completion, 1 = item possession.
        # Door nodes are transparent: resolve to their key item so the condition
        # evaluates as item possession rather than the opaque door check.
        if compiled.nodes[source_id].node_type == door_type:
            key_item_key = compiled.nodes[source_id].key_item_key
            if key_item_key is not None and key_item_key in compiled.node_key_to_id:
                source_id = compiled.node_key_to_id[key_item_key]
                check_type = 1
            else:
                # No key item recorded; fall through to safe default (evaluate as blocked).
                check_type = 0
        elif compiled.nodes[source_id].node_type == item_type:
            check_type = 1
        else:
            # Other source types (zone_line, etc.) default to 0.
            check_type = 0
        predicates.setdefault(target_id, []).append(
            UnlockCondition(source_id=source_id, check_type=check_type, group=group)
        )

    compiled.unlock_predicates = [
        UnlockPredicate(
            target_id=target_id,
            conditions=conditions,
            group_count=max((condition.group for condition in conditions), default=0),
            semantics=1 if any(condition.group for condition in conditions) else 0,
        )
        for target_id, conditions in sorted(predicates.items())
    ]


def _compile_reverse_dependencies(compiled: CompiledData) -> None:
    compiled.item_to_quest_indices = [[] for _ in compiled.item_node_ids]
    compiled.quest_to_dependent_quest_indices = [[] for _ in compiled.quest_node_ids]

    for spec in compiled.quest_specs:
        for requirement in spec.required_items:
            item_index = compiled.node_item_index[requirement.item_id]
            if item_index != -1:
                compiled.item_to_quest_indices[item_index].append(spec.quest_index)
        for prereq_index in spec.prereq_quest_indices:
            compiled.quest_to_dependent_quest_indices[prereq_index].append(spec.quest_index)


def _compile_zones(compiled: CompiledData) -> None:
    compiled.zone_node_ids = [
        node.node_id for node in compiled.nodes if node.node_type == node_type_byte(NodeType.ZONE)
    ]
    compiled.zone_adjacency = [[] for _ in compiled.zone_node_ids]
    compiled.zone_line_ids = [[] for _ in compiled.zone_node_ids]


def _compile_blueprints(graph: EntityGraph, compiled: CompiledData) -> None:
    compiled.giver_blueprints = []
    compiled.completion_blueprints = []

    for quest_node in graph.nodes_of_type(NodeType.QUEST):
        if quest_node.db_name is None:
            continue
        quest_id = compiled.node_key_to_id[quest_node.key]
        required_quest_db_names = _collect_required_quest_db_names(graph, quest_node.key)

        for edge in graph.out_edges(quest_node.key, EdgeType.ASSIGNED_BY):
            character_node = graph.get_node(edge.target)
            if character_node is None:
                continue
            character_id = compiled.node_key_to_id[character_node.key]
            interaction_type, keyword = _build_interaction(edge)
            for position_key, _scene in _enumerate_scene_targets(graph, character_node):
                compiled.giver_blueprints.append(
                    QuestGiverBlueprint(
                        quest_id=quest_id,
                        character_id=character_id,
                        position_id=compiled.node_key_to_id[position_key],
                        interaction_type=interaction_type,
                        keyword=keyword,
                        required_quest_db_names=required_quest_db_names,
                    )
                )

        for edge in graph.out_edges(quest_node.key, EdgeType.COMPLETED_BY):
            target_node = graph.get_node(edge.target)
            if target_node is None:
                continue
            target_id = compiled.node_key_to_id[target_node.key]
            interaction_type, keyword = _build_interaction(edge)
            for position_key, _scene in _enumerate_scene_targets(graph, target_node):
                compiled.completion_blueprints.append(
                    QuestCompletionBlueprint(
                        quest_id=quest_id,
                        character_id=target_id,
                        position_id=compiled.node_key_to_id[position_key],
                        interaction_type=interaction_type,
                        keyword=keyword,
                    )
                )


def _collect_required_quest_db_names(graph: EntityGraph, quest_key: str) -> list[str]:
    required: list[str] = []
    for edge in graph.out_edges(quest_key, EdgeType.REQUIRES_QUEST):
        prerequisite = graph.get_node(edge.target)
        if prerequisite and prerequisite.db_name:
            required.append(prerequisite.db_name)
    return required


def _enumerate_scene_targets(graph: EntityGraph, node: Node) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if node.type != NodeType.CHARACTER:
        if node.scene:
            targets.append((node.key, node.scene))
        return targets

    spawn_targets: list[tuple[str, str]] = []
    for edge in graph.out_edges(node.key, EdgeType.HAS_SPAWN):
        spawn_node = graph.get_node(edge.target)
        if spawn_node and spawn_node.scene:
            spawn_targets.append((spawn_node.key, spawn_node.scene))
    if spawn_targets:
        return spawn_targets
    if node.scene:
        targets.append((node.key, node.scene))
    return targets


def _build_interaction(edge: Edge) -> tuple[int, str | None]:
    if edge.keyword:
        return (1, edge.keyword)
    return (0, None)


def _first_spawn_or_self(compiled: CompiledData, node_id: int) -> int:
    has_spawn = edge_type_byte(EdgeType.HAS_SPAWN)
    for edge_id in compiled.forward_adjacency[node_id]:
        edge = compiled.edges[edge_id]
        if edge.edge_type == has_spawn:
            return edge.target_id
    return node_id
