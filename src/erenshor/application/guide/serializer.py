"""Serialize an EntityGraph to JSON.

Output format:
{
    "_version": 6,
    "_node_count": N,
    "_edge_count": N,
    "_nodes": [ { "key": "...", "type": "...", ... }, ... ],
    "_edges": [ { "s": "...", "t": "...", "type": "...", ... }, ... ]
}

_nodes is an array (not dict) for faster streaming parse on the C# side.
Each node has ``key`` as a field.  _edges use short keys ``s``/``t`` for
source/target to save space.

Non-default, non-None fields are emitted.  Default booleans (False) and
default values are omitted to keep the JSON compact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph import EntityGraph
    from .schema import Edge, Node

GRAPH_VERSION = 6


def graph_to_dict(graph: EntityGraph) -> dict[str, Any]:
    """Convert an EntityGraph to a JSON-serializable dict."""
    return {
        "_version": GRAPH_VERSION,
        "_node_count": graph.node_count,
        "_edge_count": graph.edge_count,
        "_nodes": [_serialize_node(n) for n in graph.all_nodes()],
        "_edges": [_serialize_edge(e) for e in graph.all_edges()],
    }


def graph_to_json(graph: EntityGraph, path: Path) -> None:
    """Serialize an EntityGraph to a JSON file."""
    data = graph_to_dict(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Node serialization
# ---------------------------------------------------------------------------

# Fields with these default values are omitted from JSON
_NODE_DEFAULTS: dict[str, Any] = {
    "night_spawn": False,
    "is_enabled": True,
    "repeatable": False,
    "disabled": False,
    "stackable": False,
    "is_unique": False,
    "template": False,
    "is_vendor": False,
    "is_friendly": False,
    "invulnerable": False,
    "is_rare": False,
    "is_trigger_spawn": False,
    "respawns": True,
    "is_dungeon": False,
    "implicit": False,
}

# Fields that are always included (identity)
_NODE_ALWAYS = {"key", "type", "display_name"}

# Fields to skip entirely (internal, not serialized)
_NODE_SKIP: set[str] = set()


def _serialize_node(node: Node) -> dict[str, Any]:
    """Serialize a Node to a dict, omitting None and default values."""
    result: dict[str, Any] = {}
    result["key"] = node.key
    result["type"] = node.type.value

    for field_name in node.__dataclass_fields__:
        if field_name in ("key", "type") or field_name in _NODE_SKIP:
            continue
        value = getattr(node, field_name)
        if value is None:
            continue
        # Omit default booleans / values
        if field_name in _NODE_DEFAULTS and value == _NODE_DEFAULTS[field_name]:
            continue
        result[field_name] = value
    return result


# ---------------------------------------------------------------------------
# Edge serialization
# ---------------------------------------------------------------------------

_EDGE_DEFAULTS: dict[str, Any] = {
    "negated": False,
}


def _serialize_edge(edge: Edge) -> dict[str, Any]:
    """Serialize an Edge to a dict with short keys s/t for source/target."""
    result: dict[str, Any] = {
        "s": edge.source,
        "t": edge.target,
        "type": edge.type.value,
    }
    for field_name in edge.__dataclass_fields__:
        if field_name in ("source", "target", "type"):
            continue
        value = getattr(edge, field_name)
        if value is None:
            continue
        if field_name in _EDGE_DEFAULTS and value == _EDGE_DEFAULTS[field_name]:
            continue
        result[field_name] = value
    return result
