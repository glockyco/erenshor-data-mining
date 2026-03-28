"""In-memory entity graph.

Wraps a node dict + edge list + adjacency indexes.  Built by
``graph_builder.build_graph`` and consumed by the serializer.  Immutable
after ``build_indexes()`` is called.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
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
