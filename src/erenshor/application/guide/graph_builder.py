"""Build the entity graph from the clean SQLite database.

The public entry points here own database lifecycle and phase ordering. Node
construction, edge construction, and derived graph metadata live in cohesive
modules so the pipeline has one implementation for each responsibility.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .edge_builder import build_edges
from .graph import EntityGraph
from .graph_validation import (
    _denormalize_quest_metadata,
    _denormalize_zone_and_source_levels,
)
from .node_builder import _build_scene_to_zone, build_nodes


def build_graph(db_path: Path) -> EntityGraph:
    """Build the full entity graph from the clean SQLite DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        graph = EntityGraph()
        scene_to_zone = _build_scene_to_zone(conn)
        build_nodes(conn, graph, scene_to_zone)
        build_edges(conn, graph, scene_to_zone)

        # Quest metadata denormalization runs later, after graph overrides are
        # merged, so that manual unlock/gate edges affect level estimation.
        graph.build_indexes()
        _denormalize_zone_and_source_levels(conn, graph)
        return graph
    finally:
        conn.close()


def denormalize_quest_metadata(graph: EntityGraph, db_path: Path) -> None:
    """Backfill quest zone and level metadata after override edges are merged."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _denormalize_quest_metadata(conn, graph)
    finally:
        conn.close()


__all__ = ["build_graph", "denormalize_quest_metadata"]
