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
    from .schema import Edge, EdgeType, Node, NodeType


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

    __slots__ = ("_edges", "_in", "_nodes", "_out")

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)

    # -- Mutation (build phase) --

    def add_node(self, node: Node) -> None:
        """Add a node.  Duplicate keys raise ``ValueError``."""
        if node.key in self._nodes:
            raise ValueError(f"duplicate node key: {node.key!r}")
        self._nodes[node.key] = node

    def add_edge(self, edge: Edge) -> None:
        """Append an edge.  Nodes need not exist yet."""
        self._edges.append(edge)

    def group_furnishing_characters(self) -> None:
        """Collapse room copies, keeping set-specific stock and every spawn."""
        from .schema import EdgeType, NodeType

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
        for key, group_key in replacements.items():
            if key != group_key:
                del self._nodes[key]

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
