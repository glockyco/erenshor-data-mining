"""Dense compiled form of the guide entity graph.

The compiler converts the dynamic :mod:`erenshor.application.guide.graph`
representation into integer-indexed structures. :mod:`.mod_writer` reads them
to assemble ``quest-guide.json``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from .schema import BackgroundSource, Edge, EdgeType, Node, NodeType, WorkflowCycle

if TYPE_CHECKING:
    from .graph import EntityGraph


class NodeFlags(IntEnum):
    """Packed bitflags of compiled nodes."""

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
    GUIDE_ONLY = 1 << 11


class EdgeFlags(IntEnum):
    """Packed bitflags of compiled edges."""

    NEGATED = 1 << 0
    HAS_GROUP = 1 << 1
    HAS_QUANTITY = 1 << 2
    HAS_KEYWORD = 1 << 3
    HAS_CHANCE = 1 << 4


@dataclass(slots=True)
class CompiledNode:
    """Node record of the compiled guide."""

    node_id: int
    key: str
    node_type: int
    display_name: str
    scene: str | None
    x: float = math.nan
    y: float = math.nan
    z: float = math.nan
    trigger_bounds_center_x: float = math.nan
    trigger_bounds_center_y: float = math.nan
    trigger_bounds_center_z: float = math.nan
    trigger_bounds_extents_x: float = math.nan
    trigger_bounds_extents_y: float = math.nan
    trigger_bounds_extents_z: float = math.nan
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
    workflow_cycle: WorkflowCycle | None = None
    background_sources: list[BackgroundSource] = field(default_factory=list)
    obtainability_level: int | None = None


@dataclass(slots=True)
class CompiledEdge:
    """Edge record of the compiled guide."""

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
class WorkflowTargetSpec:
    target_id: int
    quantity: int


@dataclass(slots=True)
class WorkflowCycleSpec:
    trigger_item_id: int
    trigger_item_quantity: int
    trigger_mode: str
    location_id: int
    targets: list[WorkflowTargetSpec] = field(default_factory=list)
    reward_container_id: int | None = None
    reset_evidence: str = "targets_defeated"


@dataclass(slots=True)
class QuestSpec:
    """Quest-level structure that the writer validates and reads workflows from."""

    quest_id: int
    quest_index: int
    workflow_cycle: WorkflowCycleSpec | None = None
    is_guide_only: bool = False


@dataclass(slots=True)
class CompiledData:
    """All precomputed guide data that :mod:`.mod_writer` reads."""

    nodes: list[CompiledNode] = field(default_factory=list)
    edges: list[CompiledEdge] = field(default_factory=list)

    node_keys: list[str] = field(default_factory=list)
    node_key_to_id: dict[str, int] = field(default_factory=dict)
    node_item_index: list[int] = field(default_factory=list)

    quest_node_ids: list[int] = field(default_factory=list)
    item_node_ids: list[int] = field(default_factory=list)

    forward_adjacency: list[list[int]] = field(default_factory=list)
    reverse_adjacency: list[list[int]] = field(default_factory=list)

    quest_specs: list[QuestSpec] = field(default_factory=list)
    item_sources: list[list[SourceSite]] = field(default_factory=list)
    unlock_predicates: list[UnlockPredicate] = field(default_factory=list)


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
    _compile_quest_specs(compiled)
    _compile_item_sources(compiled)
    _compile_unlock_predicates(compiled)
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
            trigger_bounds_center_x=node.trigger_bounds_center_x
            if node.trigger_bounds_center_x is not None
            else math.nan,
            trigger_bounds_center_y=node.trigger_bounds_center_y
            if node.trigger_bounds_center_y is not None
            else math.nan,
            trigger_bounds_center_z=node.trigger_bounds_center_z
            if node.trigger_bounds_center_z is not None
            else math.nan,
            trigger_bounds_extents_x=node.trigger_bounds_extents_x
            if node.trigger_bounds_extents_x is not None
            else math.nan,
            trigger_bounds_extents_y=node.trigger_bounds_extents_y
            if node.trigger_bounds_extents_y is not None
            else math.nan,
            trigger_bounds_extents_z=node.trigger_bounds_extents_z
            if node.trigger_bounds_extents_z is not None
            else math.nan,
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
            workflow_cycle=node.workflow_cycle,
            background_sources=node.background_sources,
            obtainability_level=node.obtainability_level,
        )
        for node in nodes
    ]
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
    if node.guide_only:
        flags |= NodeFlags.GUIDE_ONLY
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
    for ii, node_id in enumerate(compiled.item_node_ids):
        compiled.node_item_index[node_id] = ii


def _workflow_cycle_spec(compiled: CompiledData, node: CompiledNode) -> WorkflowCycleSpec | None:
    cycle = node.workflow_cycle
    if cycle is None:
        return None

    def node_id(key: str, label: str, expected_type: NodeType | None = None) -> int:
        if key not in compiled.node_key_to_id:
            raise ValueError(f"workflow {node.key!r} references missing {label} node {key!r}")
        result = compiled.node_key_to_id[key]
        if expected_type is not None and compiled.nodes[result].node_type != node_type_byte(expected_type):
            raise ValueError(f"workflow {node.key!r} references invalid {label} node {key!r}")
        return result

    if cycle.trigger_item_quantity <= 0:
        raise ValueError(f"workflow {node.key!r} has non-positive trigger quantity")
    if not cycle.trigger_mode:
        raise ValueError(f"workflow {node.key!r} has missing trigger mode")
    if cycle.reset_evidence not in {"reward_container_consumed", "targets_defeated"}:
        raise ValueError(f"workflow {node.key!r} has invalid reset evidence {cycle.reset_evidence!r}")
    if (cycle.reward_container_stable_key is None) != (cycle.reset_evidence == "targets_defeated"):
        raise ValueError(f"workflow {node.key!r} has inconsistent reward container and reset evidence")
    target_keys = [target.stable_key for target in cycle.targets]
    if len(set(target_keys)) != len(target_keys):
        raise ValueError(f"workflow {node.key!r} has duplicate targets")
    targets = [
        WorkflowTargetSpec(
            target_id=node_id(target.stable_key, "target", NodeType.CHARACTER),
            quantity=target.quantity,
        )
        for target in cycle.targets
    ]
    if not targets or any(target.quantity <= 0 for target in targets):
        raise ValueError(f"workflow {node.key!r} has invalid targets")
    reward_id = (
        node_id(cycle.reward_container_stable_key, "reward container", NodeType.CHARACTER)
        if cycle.reward_container_stable_key is not None
        else None
    )
    location_id = node_id(cycle.location_stable_key, "location", NodeType.LOCATION)
    location = compiled.nodes[location_id]
    location_values = (
        location.x,
        location.y,
        location.z,
        location.trigger_bounds_center_x,
        location.trigger_bounds_center_y,
        location.trigger_bounds_center_z,
        location.trigger_bounds_extents_x,
        location.trigger_bounds_extents_y,
        location.trigger_bounds_extents_z,
    )
    if not all(math.isfinite(value) for value in location_values):
        raise ValueError(f"workflow {node.key!r} has non-finite location metadata")
    if any(value <= 0 for value in location_values[-3:]):
        raise ValueError(f"workflow {node.key!r} has non-positive location extents")
    return WorkflowCycleSpec(
        trigger_item_id=node_id(cycle.trigger_item_stable_key, "trigger item", NodeType.ITEM),
        trigger_item_quantity=cycle.trigger_item_quantity,
        trigger_mode=cycle.trigger_mode,
        location_id=location_id,
        targets=targets,
        reward_container_id=reward_id,
        reset_evidence=cycle.reset_evidence,
    )


def _compile_quest_specs(compiled: CompiledData) -> None:
    compiled.quest_specs = []
    for quest_index, quest_node_id in enumerate(compiled.quest_node_ids):
        node = compiled.nodes[quest_node_id]
        guide_only = bool(node.flags & NodeFlags.GUIDE_ONLY)
        if guide_only != (node.workflow_cycle is not None):
            raise ValueError(f"quest {node.key!r} has inconsistent guide-only workflow descriptor")
        if guide_only and not (node.flags & NodeFlags.IMPLICIT and node.flags & NodeFlags.REPEATABLE):
            raise ValueError(f"guide-only quest {node.key!r} must be implicit and repeatable")
        compiled.quest_specs.append(
            QuestSpec(
                quest_id=quest_node_id,
                quest_index=quest_index,
                is_guide_only=guide_only,
                workflow_cycle=_workflow_cycle_spec(compiled, node),
            )
        )


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
    group_ids_by_target: dict[int, dict[str, int]] = {}

    for edge in compiled.edges:
        if edge.edge_type in unlock_target_edge_types:
            target_id = edge.target_id
            source_id = edge.source_id
        elif edge.edge_type == gated_by_quest:
            target_id = edge.source_id
            source_id = edge.target_id
        else:
            continue
        if edge.group:
            group_ids = group_ids_by_target.setdefault(target_id, {})
            group = group_ids.setdefault(edge.group, len(group_ids) + 1)
        else:
            group = 0
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
