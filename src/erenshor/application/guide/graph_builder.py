"""Build the entity graph from the clean SQLite database.

The public entry points here own database lifecycle and phase ordering. Node
construction, edge construction, and derived graph metadata live in cohesive
modules so the pipeline has one implementation for each responsibility.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository

from .canonical_sources import add_canonical_sources
from .edge_builder import build_edges
from .encounter_contexts import read_encounter_contexts, read_zone_line_destination_contexts
from .graph import EntityGraph
from .graph_validation import (
    _denormalize_quest_metadata,
    _denormalize_zone_and_source_levels,
)
from .node_builder import _build_scene_to_zone, build_nodes
from .schema import AtomKind, Gate, GateAtom, SubjectKind


def build_graph(db_path: Path) -> EntityGraph:
    """Build the full entity graph from the clean SQLite DB."""
    with DatabaseConnection(db_path, read_only=True) as database, database.connect() as conn:
        graph = EntityGraph()
        graph.encounters = read_encounter_contexts(conn)
        for row in conn.execute("SELECT stable_key, db_name FROM quests"):
            graph.add_quest_db_name(row["stable_key"], row["db_name"])
        scene_to_zone = _build_scene_to_zone(conn)
        build_nodes(conn, graph, scene_to_zone)
        build_edges(conn, graph, scene_to_zone)
        add_canonical_sources(ItemProvenanceRepository(database), conn, graph)
        graph.group_furnishing_characters()
        for placement in graph.encounters["encounter_placements"]:
            member = str(placement["member_spawn_stable_key"])
            if not graph.has_node(member):
                raise ValueError(f"Encounter placement absent from guide: {member}")
            atoms = []
            for state in graph.encounters["encounter_conditions"]:
                if state["encounter_key"] != placement["encounter_key"]:
                    continue
                if state["state_scope"] == "account":
                    atoms.append(
                        GateAtom(
                            AtomKind.ACCOUNT_STATE,
                            str(state["state_key"]),
                            actor="account",
                            value=str(state["required_value"]),
                            phase="availability",
                            scope=member,
                        )
                    )
                else:
                    kind = AtomKind.QUEST_DONE if state["required_value"] == "true" else AtomKind.QUEST_NOT_DONE
                    atoms.append(GateAtom(kind, str(state["state_key"])))
            graph.add_gate(Gate(SubjectKind.SPAWN_POINT, member, str(placement["encounter_key"]), (tuple(atoms),)))
        graph.zone_line_destination_contexts = read_zone_line_destination_contexts(conn, graph)

        # Overrides can affect the quest's gate and level metadata.
        graph.build_indexes()
        _denormalize_zone_and_source_levels(conn, graph)
        return graph


def denormalize_quest_metadata(graph: EntityGraph, db_path: Path) -> None:
    """Backfill quest zone and level metadata after override edges are merged."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _denormalize_zone_and_source_levels(conn, graph)
        _denormalize_quest_metadata(conn, graph)
    finally:
        conn.close()


def excluded_quest_db_names(db_path: Path) -> list[str]:
    """DB names of the game quests that the mapping keeps out of the guide.

    The graph holds only quests with ``is_map_visible = 1``; these are the rest.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT db_name FROM quests WHERE is_map_visible = 0 AND db_name IS NOT NULL")
        return sorted(str(row[0]) for row in rows)
    finally:
        conn.close()


__all__ = ["build_graph", "denormalize_quest_metadata", "excluded_quest_db_names"]
