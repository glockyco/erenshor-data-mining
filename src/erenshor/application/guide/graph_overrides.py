"""Load manual nodes and edges from graph_overrides.toml.

Custom scripted relationships (Evadne/brazier, ward bosses, doors, etc.)
cannot be auto-detected from DB data.  This module reads a TOML file
with manual node and edge definitions and merges them into the graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .graph import EntityGraph

from .schema import Edge, EdgeType, Node, NodeType


def merge_overrides(graph: EntityGraph, overrides_path: Path) -> None:
    """Merge manual nodes and edges from a TOML file into the graph.

    Silently skips if the file does not exist.  This lets the pipeline
    run without overrides during early development.
    """
    if not overrides_path.exists():
        return

    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    text = overrides_path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    for node_data in data.get("nodes", []):
        node = _parse_node(node_data)
        if not graph.has_node(node.key):
            graph.add_node(node)

    for edge_data in data.get("edges", []):
        edge = _parse_edge(edge_data)
        graph.add_edge(edge)


def _parse_node(data: dict) -> Node:
    """Parse a node dict from TOML into a Node."""
    return Node(
        key=data["key"],
        type=NodeType(data["type"]),
        display_name=data["display_name"],
        x=data.get("x"),
        y=data.get("y"),
        z=data.get("z"),
        scene=data.get("scene"),
        db_name=data.get("db_name"),
        description=data.get("description"),
        level=data.get("level"),
        zone=data.get("zone"),
        zone_key=data.get("zone_key"),
        keyword=data.get("keyword"),
    )


def _parse_edge(data: dict) -> Edge:
    """Parse an edge dict from TOML into an Edge."""
    return Edge(
        source=data["source"],
        target=data["target"],
        type=EdgeType(data["type"]),
        group=data.get("group"),
        ordinal=data.get("ordinal"),
        negated=data.get("negated", False),
        quantity=data.get("quantity"),
        keyword=data.get("keyword"),
        note=data.get("note"),
        chance=data.get("chance"),
        amount=data.get("amount"),
        slot=data.get("slot"),
    )
