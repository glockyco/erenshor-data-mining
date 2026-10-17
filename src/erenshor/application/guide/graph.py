"""In-memory entity graph.

Wraps a node dict + edge list + adjacency indexes. Built by
``graph_builder.build_graph`` and consumed by the serializers. Furnishing
characters are grouped before indexing, by object and furniture set, so room
copies share quest interactions without mixing set-specific vendor stock.
Spawn nodes retain the furniture item and room slot for availability checks.
After indexing, only explicit graph overrides may add edges.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import astuple, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemUse

    from .schema import Edge, EdgeType, Gate, Node, NodeType, SubjectKind


class EntityGraph:
    """Directed multigraph of game entities and their relationships.

    Usage::

        graph = EntityGraph()
        graph.add_node(Node(key="quest:anglerring", ...))
        graph.add_edge(Edge(source="quest:anglerring", target="item:...", ...))
        graph.build_indexes()  # call once after all nodes/edges added

        graph.get_node("quest:anglerring")
        graph.out_edges("quest:anglerring", EdgeType.REQUIRES_ITEM)
    """

    __slots__ = (
        "_edges",
        "_entries",
        "_gates",
        "_gates_by_subject",
        "_in",
        "_nodes",
        "_out",
        "_quest_db_names",
        "encounters",
        "quest_uses",
        "source_exclusions",
        "source_facts",
        "source_uses",
        "zone_line_destination_contexts",
    )

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)
        self._gates: list[Gate] = []
        self._gates_by_subject: dict[tuple[SubjectKind, str, str | None], list[Gate]] = defaultdict(list)
        # Gates can name quests that the guide leaves out, such as hidden marker quests.
        self._quest_db_names: dict[str, str] = {}
        # Targets that only some zone lines into their scene reach, by target key.
        self._entries: dict[str, list[str]] = defaultdict(list)
        self.source_facts: dict[str, ItemAcquisition | ItemUse] = {}
        self.source_exclusions: dict[str, str] = {}
        self.source_uses: dict[str, list[ItemUse]] = {}
        self.quest_uses: dict[tuple[str, str], list[ItemUse]] = {}
        self.encounters: dict[str, list[dict[str, object]]] = {
            family: []
            for family in (
                "encounter_placements",
                "encounter_conditions",
                "encounter_completions",
                "encounter_event_conditions",
            )
        }
        self.zone_line_destination_contexts: dict[str, dict[str, object]] = {}

    # -- Mutation (build phase) --

    def add_node(self, node: Node) -> None:
        """Add a node.  Duplicate keys raise ``ValueError``."""
        if node.key in self._nodes:
            raise ValueError(f"duplicate node key: {node.key!r}")
        self._nodes[node.key] = node

    def add_edge(self, edge: Edge) -> None:
        """Append an edge.  Nodes need not exist yet."""
        self._edges.append(edge)

    def add_gate(self, gate: Gate) -> None:
        """Add a gate. Gates on one subject combine with AND."""
        self._gates.append(gate)
        self._gates_by_subject[(gate.subject_kind, gate.subject_key, gate.item_key)].append(gate)

    def add_quest_db_name(self, quest_key: str, db_name: str) -> None:
        """Record the DB name of a quest that a gate names."""
        self._quest_db_names[quest_key] = db_name

    def add_entry(self, target_key: str, zone_line_key: str) -> None:
        """Record a zone line that reaches a target which other lines into its scene do not."""
        self._entries[target_key].append(zone_line_key)

    def entries_for(self, target_key: str) -> list[str]:
        return self._entries.get(target_key, [])

    def group_furnishing_characters(self) -> None:
        """Collapse room copies, keeping set-specific stock and every spawn."""
        from .schema import EdgeType, NodeType, SubjectKind

        spawns: dict[str, list[Node]] = defaultdict(list)
        for edge in self._edges:
            if edge.type == EdgeType.HAS_SPAWN and edge.target in self._nodes:
                spawns[edge.source].append(self._nodes[edge.target])
        members: dict[tuple[str, str], list[str]] = defaultdict(list)
        sets: dict[str, set[str]] = defaultdict(set)
        for key, placements in spawns.items():
            if self._nodes[key].type != NodeType.CHARACTER or not all(p.furniture_item_key for p in placements):
                continue
            item_keys = {p.furniture_item_key for p in placements}
            if len(item_keys) != 1:
                raise ValueError(f"furnishing character {key!r} has multiple furniture sets")
            item_key = next(iter(item_keys))
            assert item_key is not None
            object_key = re.sub(r":[^:]+:-?\d+(?:\.\d+)?:-?\d+(?:\.\d+)?:-?\d+(?:\.\d+)?(?::\d+)?$", "", key)
            members[(object_key, item_key)].append(key)
            sets[object_key].add(item_key)
        replacements: dict[str, str] = {}
        for (object_key, item_key), keys in sorted(members.items()):
            group_key = object_key if len(sets[object_key]) == 1 else f"{object_key}@{item_key}"
            member = self._nodes[sorted(keys)[0]]
            existing = self._nodes.get(group_key)
            self._nodes[group_key] = replace(
                existing or member,
                key=group_key,
                zone=member.zone,
                zone_key=member.zone_key,
                scene=member.scene,
                x=member.x,
                y=member.y,
                z=member.z,
            )
            for key in keys:
                replacements[key] = group_key
        deduped: dict[tuple[object, ...], Edge] = {}
        for edge in self._edges:
            rewritten = replace(
                edge,
                source=replacements.get(edge.source, edge.source),
                target=replacements.get(edge.target, edge.target),
            )
            deduped[astuple(rewritten)] = rewritten
        self._edges = list(deduped.values())
        gates: dict[Gate, None] = {}
        for gate in self._gates:
            renamed = gate
            if gate.subject_kind in (SubjectKind.CHARACTER, SubjectKind.VENDOR_ITEM):
                renamed = replace(gate, subject_key=replacements.get(gate.subject_key, gate.subject_key))
            gates[renamed] = None
        self._gates = []
        self._gates_by_subject = defaultdict(list)
        for gate in gates:
            self.add_gate(gate)
        for key, group_key in replacements.items():
            if key != group_key:
                del self._nodes[key]
                if key in self._entries:
                    self._entries[group_key].extend(self._entries.pop(key))

    def is_furnishing_character(self, key: str) -> bool:
        from .schema import EdgeType, NodeType

        node = self._nodes.get(key)
        if node is None or node.type != NodeType.CHARACTER:
            return False
        spawns = self.out_edges(key, EdgeType.HAS_SPAWN)
        return bool(spawns) and all(self._nodes[e.target].furniture_item_key for e in spawns)

    def prefer_ungated_targets(self, keys: list[str]) -> list[str]:
        ungated = [key for key in keys if not self.is_furnishing_character(key)]
        return ungated or keys

    def build_indexes(self) -> None:
        """Build outgoing/incoming adjacency lists from the edge list.

        Call exactly once after all nodes and edges are added.  Clears
        any prior index state so it is safe to call if edges were added
        in multiple passes.
        """
        self._out = defaultdict(list)
        self._in = defaultdict(list)
        for edge in self._edges:
            self._out[edge.source].append(edge)
            self._in[edge.target].append(edge)

    # -- Read (query phase) --

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_node(self, key: str) -> Node | None:
        return self._nodes.get(key)

    def has_node(self, key: str) -> bool:
        return key in self._nodes

    def all_nodes(self) -> Iterable[Node]:
        return self._nodes.values()

    def all_edges(self) -> Iterable[Edge]:
        return iter(self._edges)

    def nodes_of_type(self, node_type: NodeType) -> Iterable[Node]:
        """Yield all nodes of a given type.  Linear scan — fine at our scale."""
        for node in self._nodes.values():
            if node.type == node_type:
                yield node

    def all_gates(self) -> Iterable[Gate]:
        return iter(self._gates)

    def gates_for(self, kind: SubjectKind, key: str, item_key: str | None = None) -> list[Gate]:
        return self._gates_by_subject.get((kind, key, item_key), [])

    def quest_db_name(self, quest_key: str) -> str:
        """DB name of a quest that a gate names, which the game's state is keyed by."""
        node = self._nodes.get(quest_key)
        if node is not None and node.db_name:
            return node.db_name
        if quest_key not in self._quest_db_names:
            raise ValueError(f"no DB name for quest {quest_key!r}")
        return self._quest_db_names[quest_key]

    def out_edges(self, key: str, edge_type: EdgeType | None = None) -> list[Edge]:
        """Outgoing edges from ``key``, optionally filtered by type."""
        edges = self._out.get(key, [])
        if edge_type is not None:
            return [e for e in edges if e.type == edge_type]
        return edges

    def in_edges(self, key: str, edge_type: EdgeType | None = None) -> list[Edge]:
        """Incoming edges to ``key``, optionally filtered by type."""
        edges = self._in.get(key, [])
        if edge_type is not None:
            return [e for e in edges if e.type == edge_type]
        return edges
