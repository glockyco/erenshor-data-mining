"""Load guide-only content and reviewed preparation wording.

Shared game facts belong in the clean database. Authored source notes refine
player instructions without changing availability and are checked against the
current release mechanism and referenced items.
"""

from __future__ import annotations

import sqlite3
import tomllib
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph import EntityGraph

from .schema import AtomKind, Edge, EdgeType, Gate, GateAtom, Node, NodeType, SubjectKind


def merge_overrides(graph: EntityGraph, overrides_path: Path, *, db_path: Path | None = None) -> None:
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

    notes = data.get("source_notes", [])
    if notes:
        if db_path is None:
            raise ValueError("Source preparation notes require the clean database for validation")
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            for entry in notes:
                _merge_source_note(graph, conn, entry)


def _merge_source_note(graph: EntityGraph, conn: sqlite3.Connection, entry: dict[str, Any]) -> None:
    """Replace presentation text only when its underlying release still exists."""
    if set(entry) - {"source", "mechanism", "text", "items"}:
        raise ValueError(f"Unknown source preparation note fields: {entry!r}")
    source, mechanism, text = (entry.get(key) for key in ("source", "mechanism", "text"))
    if not all(isinstance(value, str) and value.strip() for value in (source, mechanism, text)):
        raise ValueError(f"Source preparation note needs source, mechanism and text: {entry!r}")
    items = entry.get("items", [])
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ValueError(f"Invalid preparation item references for {source}")
    for item in items:
        item_node = graph.get_node(item)
        if item_node is None or item_node.type != NodeType.ITEM:
            raise ValueError(f"Preparation note references missing item: {item}")
    mechanisms = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT mechanism FROM character_damage_releases"
            " WHERE character_stable_key = ? AND can_release = 1 AND controller_enabled = 1",
            (source,),
        )
    }
    if mechanisms != {mechanism}:
        raise ValueError(f"Preparation mechanism changed for {source}: {sorted(mechanisms)}")
    edges = [edge for edge in graph.all_edges() if edge.source == source and edge.type == EdgeType.DROPS_ITEM]
    if not edges or any(not edge.note for edge in edges):
        raise ValueError(f"Preparation note has no supported drop instructions to replace: {source}")
    for edge in edges:
        edge.note = text


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
