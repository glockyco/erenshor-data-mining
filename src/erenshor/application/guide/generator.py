"""Entity graph generator — thin orchestrator.

Builds the entity graph from the clean SQLite DB, merges manual
overrides, and returns the graph for serialization.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .graph_builder import build_graph
from .graph_overrides import merge_overrides

if TYPE_CHECKING:
    from .graph import EntityGraph


def generate(db_path: Path, overrides_path: Path | None = None) -> EntityGraph:
    """Build the full entity graph from DB + optional overrides."""
    graph = build_graph(db_path)
    if overrides_path:
        merge_overrides(graph, overrides_path)
    return graph
