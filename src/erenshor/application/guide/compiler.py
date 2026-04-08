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

from .schema import EdgeType, NodeType

if TYPE_CHECKING:
    from .graph import EntityGraph


class SectionId(IntEnum):
    """Binary section identifiers.

    These IDs are written to the section directory and must remain stable once
    the binary format ships.
    """

    STRING_TABLE = 0
    NODE_TABLE = 1
    EDGE_TABLE = 2
    FORWARD_ADJACENCY = 3
    REVERSE_ADJACENCY = 4
    QUEST_SPECS = 5
    ITEM_SOURCE_INDEX = 6
    UNLOCK_PREDICATES = 7
    TOPOLOGICAL_ORDER = 8
    REVERSE_DEPS = 9
    ZONE_CONNECTIVITY = 10
    QUEST_GIVER_BLUEPRINTS = 11
    QUEST_COMPLETION_BLUEPRINTS = 12
    FEASIBILITY = 13


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


def compile_graph(_graph: EntityGraph) -> CompiledData:
    """Compile an :class:`EntityGraph` into :class:`CompiledData`.

    The actual structural analysis lands in the next task. The placeholder keeps
    the public module shape honest for test-first development.
    """

    raise NotImplementedError("compile_graph is implemented in the next phase of the plan")
