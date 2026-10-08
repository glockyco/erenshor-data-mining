from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.graph_validation import _best_interaction_zone_key, _estimate_quest_level
from erenshor.application.guide.mod_writer import build_mod_guide
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


def _member(graph: EntityGraph, key: str, item: str, slot: str) -> None:
    graph.add_node(Node(key, NodeType.CHARACTER, "Golem", zone_key="zone:reliquary"))
    spawn = "spawn:" + key
    graph.add_node(
        Node(
            spawn,
            NodeType.SPAWN_POINT,
            "Golem",
            scene="Reliquary",
            x=1,
            y=2,
            z=3,
            furniture_item_key=item,
            furniture_slot=slot,
        )
    )
    graph.add_edge(Edge(key, spawn, EdgeType.HAS_SPAWN))
    graph.add_edge(Edge("quest:test", key, EdgeType.COMPLETED_BY))


def test_single_set_group_merges_prefab_and_deduplicates_edges() -> None:
    graph = EntityGraph()
    graph.add_node(Node("character:golem", NodeType.CHARACTER, "Golem"))
    graph.add_edge(Edge("quest:test", "character:golem", EdgeType.COMPLETED_BY))
    _member(graph, "character:golem:reliquary:1.00:2.00:3.00", "item:smithy", "L1")
    _member(graph, "character:golem:reliquary:4.00:2.00:3.00:2", "item:smithy", "R4")
    graph.group_furnishing_characters()
    graph.build_indexes()
    assert [n.key for n in graph.nodes_of_type(NodeType.CHARACTER)] == ["character:golem"]
    assert len(graph.out_edges("character:golem", EdgeType.HAS_SPAWN)) == 2
    assert len(graph.out_edges("quest:test", EdgeType.COMPLETED_BY)) == 1


def test_multiple_sets_preserve_distinct_vendor_stock() -> None:
    graph = EntityGraph()
    _member(graph, "character:vendor:reliquary:1:2:3", "item:stone", "L1")
    _member(graph, "character:vendor:reliquary:4:2:3", "item:wood", "R1")
    graph.add_edge(Edge("character:vendor:reliquary:1:2:3", "item:exclusive", EdgeType.SELLS_ITEM))
    graph.group_furnishing_characters()
    graph.build_indexes()
    assert {n.key for n in graph.nodes_of_type(NodeType.CHARACTER)} == {
        "character:vendor@item:stone",
        "character:vendor@item:wood",
    }
    assert graph.out_edges("character:vendor@item:stone", EdgeType.SELLS_ITEM)[0].target == "item:exclusive"
    assert not graph.out_edges("character:vendor@item:wood", EdgeType.SELLS_ITEM)


def test_ungated_zone_level_and_completion_preferred_and_spawn_fields_emitted() -> None:
    graph = EntityGraph()
    quest = Node("quest:test", NodeType.QUEST, "Test", db_name="TEST")
    graph.add_node(quest)
    graph.add_node(Node("item:smithy", NodeType.ITEM, "Smithy Set"))
    _member(graph, "character:golem:reliquary:1:2:3", "item:smithy", "L1")
    graph.add_node(Node("character:world", NodeType.CHARACTER, "World", zone_key="zone:world"))
    graph.add_edge(Edge(quest.key, "character:world", EdgeType.COMPLETED_BY))
    graph.group_furnishing_characters()
    graph.build_indexes()
    zones = {"character:golem": "zone:reliquary", "character:world": "zone:world"}
    medians = {"zone:reliquary": 1, "zone:world": 20}
    assert _best_interaction_zone_key(["character:golem", "character:world"], graph, zones, medians) == "zone:world"
    assert _estimate_quest_level(quest, graph, medians, {}, zones, {}, {}) == 20
    guide = build_mod_guide(graph, compile_graph(graph))
    assert guide["_furniture_sets"] == {"item:smithy": {"display_name": "Smithy Set"}}
    spawn = guide["_character_spawns"]["character:golem"][0]
    assert spawn["furniture_item_stable_key"] == "item:smithy"
    assert spawn["furniture_slot"] == "L1"
    assert guide["quests"][0]["completion"][0]["source_stable_key"] == "character:world"
