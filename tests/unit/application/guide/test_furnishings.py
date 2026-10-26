from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.graph_validation import _best_interaction_zone_key, _estimate_quest_level
from erenshor.application.guide.mod_writer import build_mod_guide
from erenshor.application.guide.schema import AtomKind, Edge, EdgeType, Gate, GateAtom, Node, NodeType, SubjectKind


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
    graph.add_gate(
        Gate(SubjectKind.SPAWN_POINT, spawn, "furnishing", ((GateAtom(AtomKind.ROOM_FURNISHED, item, slot),),))
    )


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


def test_ungated_zone_level_and_completion_preferred_and_furnishing_condition_emitted() -> None:
    graph = EntityGraph()
    quest = Node("quest:test", NodeType.QUEST, "Test", db_name="TEST")
    graph.add_node(quest)
    graph.add_node(Node("item:smithy", NodeType.ITEM, "Smithy Set", game_id="123"))
    _member(graph, "character:golem:reliquary:1:2:3", "item:smithy", "L1")
    graph.add_node(Node("character:world", NodeType.CHARACTER, "World", zone_key="zone:world"))
    graph.add_edge(Edge(quest.key, "character:world", EdgeType.COMPLETED_BY))
    graph.group_furnishing_characters()
    graph.build_indexes()
    zones = {"character:golem": "zone:reliquary", "character:world": "zone:world"}
    medians = {"zone:reliquary": 1, "zone:world": 20}
    assert _best_interaction_zone_key(["character:golem", "character:world"], graph, zones, medians) == "zone:world"
    assert _estimate_quest_level(quest, graph, medians, {}, zones, quest_levels={}, item_cache={}) == 20
    guide = build_mod_guide(graph, compile_graph(graph))
    assert guide["_furniture_sets"] == {"item:smithy": {"display_name": "Smithy Set"}}
    spawn = guide["_character_spawns"]["character:golem"][0]
    assert guide["_conditions"][spawn["condition"]] == [
        [{"kind": "room_furnished", "ref": "item:smithy", "slot": "L1"}]
    ]
    assert guide["_gate_items"]["item:smithy"]["game_id"] == "123"
    assert guide["quests"][0]["completion"][0]["source_stable_key"] == "character:world"


def test_grouped_character_activity_stays_on_each_original_placement() -> None:
    graph = EntityGraph()
    graph.add_node(Node("quest:test", NodeType.QUEST, "Test", db_name="TEST"))
    graph.add_node(Node("quest:claim", NodeType.QUEST, "Claim", db_name="CLAIM"))
    graph.add_quest_db_name("quest:claim", "CLAIM")
    graph.add_node(Node("item:smithy", NodeType.ITEM, "Smithy Set", game_id="123"))
    for index, slot in enumerate(("L1", "R4")):
        key = f"character:golem:reliquary:{index}:2:3"
        _member(graph, key, "item:smithy", slot)
        graph.add_gate(
            Gate(
                SubjectKind.CHARACTER,
                key,
                "activation:hierarchy",
                (
                    (
                        GateAtom(AtomKind.QUEST_DONE, "quest:claim"),
                        GateAtom(AtomKind.ROOM_FURNISHED, "item:smithy", slot),
                    ),
                ),
            )
        )

    graph.group_furnishing_characters()
    graph.build_indexes()
    assert not graph.gates_for(SubjectKind.CHARACTER, "character:golem")
    guide = build_mod_guide(graph, compile_graph(graph))
    entries = guide["_character_spawns"]["character:golem"]
    assert len(entries) == 2
    conditions = [guide["_conditions"][entry["condition"]] for entry in entries]
    assert conditions == [
        [
            [
                {"kind": "quest_done", "ref": "CLAIM"},
                {"kind": "room_furnished", "ref": "item:smithy", "slot": slot},
            ]
        ]
        for slot in ("L1", "R4")
    ]
