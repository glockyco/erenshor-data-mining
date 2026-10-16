"""Load guide-only nodes, edges, and gates from graph_overrides.toml.

The file holds what the guide needs and no game data states, such as the
Reliquary planning table as a pickup and scripted quest relationships. Facts
that every consumer needs belong in the clean database instead: corrections
in mapping.json and what doors guard in barriers.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph import EntityGraph

from .schema import AtomKind, Edge, EdgeType, Gate, GateAtom, Node, NodeType, SubjectKind


def merge_overrides(graph: EntityGraph, overrides_path: Path) -> None:
    """Merge manual nodes, edges, and gates from a TOML file into the graph.

    Silently skips if the file does not exist.
    """
    if not overrides_path.exists():
        return

    text = overrides_path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    for node_data in data.get("nodes", []):
        node = _parse_node(node_data)
        if not graph.has_node(node.key):
            graph.add_node(node)

    for edge_data in data.get("edges", []):
        edge = _parse_edge(edge_data)
        graph.add_edge(edge)

    for gate_data in data.get("gates", []):
        graph.add_gate(_parse_gate(gate_data))


def _parse_node(data: dict[str, Any]) -> Node:
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


def _parse_edge(data: dict[str, Any]) -> Edge:
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


def _parse_gate(data: dict[str, Any]) -> Gate:
    """Parse a gate: groups of atoms, any group of which opens it."""
    groups = data["groups"]
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"override gate on {data.get('subject')!r} needs at least one group")
    return Gate(
        subject_kind=SubjectKind(data["subject_kind"]),
        subject_key=data["subject"],
        gate=data["gate"],
        groups=tuple(
            tuple(GateAtom(AtomKind(atom["kind"]), atom["ref"], atom.get("slot")) for atom in group) for group in groups
        ),
        item_key=data.get("item"),
    )
