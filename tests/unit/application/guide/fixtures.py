"""Small graph builders shared by synthetic guide tests."""

from __future__ import annotations

from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import Edge, Node, NodeType


def build_graph(*nodes: Node, edges: list[Edge] | None = None) -> EntityGraph:
    """Build and index a graph from the supplied synthetic entities."""
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    graph.build_indexes()
    return graph


def quest_node(key: str, db_name: str | None = None, **kwargs: object) -> Node:
    """Build a quest node with the stable synthetic-test defaults."""
    return Node(
        key=key,
        type=NodeType.QUEST,
        display_name=kwargs.pop("display_name", key),
        db_name=db_name,
        **kwargs,
    )


def item_node(key: str, name: str | None = None, **kwargs: object) -> Node:
    """Build an item node with an optional display name."""
    return Node(key=key, type=NodeType.ITEM, display_name=name or key, **kwargs)


def character_node(key: str, name: str | None = None, **kwargs: object) -> Node:
    """Build a character node with an optional display name."""
    return Node(key=key, type=NodeType.CHARACTER, display_name=name or key, **kwargs)


def spawn_node(
    key: str,
    *,
    scene: str = "Forest",
    zone_key: str = "zone:forest",
    x: float = 10.0,
    y: float = 20.0,
    z: float = 30.0,
    **kwargs: object,
) -> Node:
    """Build a positioned synthetic spawn point."""
    return Node(
        key=key,
        type=NodeType.SPAWN_POINT,
        display_name=key,
        scene=scene,
        zone_key=zone_key,
        x=x,
        y=y,
        z=z,
        **kwargs,
    )
