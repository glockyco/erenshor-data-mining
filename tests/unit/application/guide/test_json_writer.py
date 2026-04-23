"""Unit tests for JSON serialization of compiled guide data."""

from __future__ import annotations

import json

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.json_writer import serialize
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


def _graph(*nodes: Node, edges: list[Edge] | None = None) -> EntityGraph:
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    graph.build_indexes()
    return graph


def _quest(key: str, db_name: str | None = None, **kwargs: object) -> Node:
    return Node(key=key, type=NodeType.QUEST, display_name=key, db_name=db_name, **kwargs)


def _item(key: str) -> Node:
    return Node(key=key, type=NodeType.ITEM, display_name=key)


EXPECTED_TOP_LEVEL_KEYS = {
    "nodes",
    "edges",
    "node_keys",
    "node_levels",
    "node_key_to_id",
    "node_quest_index",
    "node_item_index",
    "quest_node_ids",
    "item_node_ids",
    "forward_adjacency",
    "reverse_adjacency",
    "quest_specs",
    "item_sources",
    "unlock_predicates",
    "topo_order",
    "quest_to_dependent_quest_indices",
    "zone_node_ids",
    "zone_adjacency",
    "zone_line_ids",
    "giver_blueprints",
    "completion_blueprints",
    "infeasible_node_ids",
}


def test_serialize_produces_valid_json_with_expected_keys() -> None:
    graph = _graph(
        _quest("quest:a", db_name="QA"),
        _item("item:x"),
        edges=[Edge(source="quest:a", target="item:x", type=EdgeType.REWARDS_ITEM)],
    )
    compiled = compile_graph(graph)
    text = serialize(compiled)
    data = json.loads(text)

    assert set(data.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert len(data["nodes"]) == 2
    assert len(data["quest_specs"]) == 1


def test_serialize_round_trips_node_metadata() -> None:
    graph = _graph(
        _quest(
            "quest:rich",
            db_name="RICH",
            description="Recover the key.",
            keyword="RICHKW",
            zone="Stormhold",
            xp_reward=500,
            gold_reward=100,
            reward_item_key="item:gold_ring",
            disabled_text="Not yet available.",
        ),
    )
    compiled = compile_graph(graph)
    data = json.loads(serialize(compiled))

    quest_nodes = [n for n in data["nodes"] if n["key"] == "quest:rich"]
    assert len(quest_nodes) == 1
    node = quest_nodes[0]

    assert node["description"] == "Recover the key."
    assert node["keyword"] == "RICHKW"
    assert node["zone_display"] == "Stormhold"
    assert node["xp_reward"] == 500
    assert node["gold_reward"] == 100
    assert node["reward_item_key"] == "item:gold_ring"
    assert node["disabled_text"] == "Not yet available."


def test_serialize_nan_positions_as_null() -> None:
    graph = _graph(_quest("quest:nopos", db_name="NP"))
    compiled = compile_graph(graph)
    data = json.loads(serialize(compiled))

    node = data["nodes"][0]
    assert node["x"] is None
    assert node["y"] is None
    assert node["z"] is None


def test_serialize_round_trips_edge_metadata() -> None:
    graph = _graph(
        _quest("quest:a", db_name="QA"),
        _item("item:x"),
        edges=[
            Edge(
                source="quest:a",
                target="item:x",
                type=EdgeType.REWARDS_ITEM,
                note="rare drop",
                amount=5,
            ),
        ],
    )
    compiled = compile_graph(graph)
    data = json.loads(serialize(compiled))

    edges = data["edges"]
    assert len(edges) == 1
    assert edges[0]["note"] == "rare drop"
    assert edges[0]["amount"] == 5
