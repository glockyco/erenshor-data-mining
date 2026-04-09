"""Unit tests for the new guide compiler data model."""

from __future__ import annotations

import math

from erenshor.application.guide.compiler import (
    CompiledData,
    CompiledEdge,
    CompiledNode,
    EdgeFlags,
    ItemRequirement,
    NodeFlags,
    QuestCompletionBlueprint,
    QuestGiverBlueprint,
    QuestSpec,
    SourceSite,
    SpawnPosition,
    StepSpec,
    UnlockCondition,
    UnlockPredicate,
    compile_graph,
    edge_type_byte,
)
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


def _graph(*nodes: Node, edges: list[Edge] | None = None) -> EntityGraph:
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    graph.build_indexes()
    return graph


def _quest(key: str, db_name: str | None = None) -> Node:
    return Node(key=key, type=NodeType.QUEST, display_name=key, db_name=db_name)


def _item(key: str) -> Node:
    return Node(key=key, type=NodeType.ITEM, display_name=key)


def _char(key: str, *, scene: str = "Forest", x: float = 1.0, y: float = 2.0, z: float = 3.0) -> Node:
    return Node(
        key=key,
        type=NodeType.CHARACTER,
        display_name=key,
        scene=scene,
        x=x,
        y=y,
        z=z,
    )


def _spawn(key: str, *, scene: str = "Forest", zone_key: str = "zone:forest") -> Node:
    return Node(
        key=key,
        type=NodeType.SPAWN_POINT,
        display_name=key,
        scene=scene,
        zone_key=zone_key,
        x=10.0,
        y=20.0,
        z=30.0,
    )


def test_compiled_data_defaults_are_empty() -> None:
    data = CompiledData()

    assert data.nodes == []
    assert data.edges == []
    assert data.quest_node_ids == []
    assert data.item_node_ids == []
    assert data.topo_order == []
    assert data.infeasible_node_ids == set()
    assert data.node_key_to_id == {}


def test_compiled_node_preserves_nan_positions() -> None:
    node = CompiledNode(
        node_id=7,
        key="quest:a",
        node_type=0,
        display_name="Quest A",
        scene=None,
        x=math.nan,
        y=math.nan,
        z=math.nan,
        flags=NodeFlags.IMPLICIT,
        level=0,
        zone_key=None,
        db_name="QUESTA",
    )

    assert node.node_id == 7
    assert math.isnan(node.x)
    assert math.isnan(node.y)
    assert math.isnan(node.z)
    assert node.flags == NodeFlags.IMPLICIT
    assert node.db_name == "QUESTA"


def test_nested_compiled_types_round_trip() -> None:
    step = StepSpec(step_type=3, target_id=11, ordinal=2)
    req = ItemRequirement(item_id=22, qty=5, group=1)
    pred = UnlockPredicate(
        target_id=33,
        conditions=[UnlockCondition(source_id=44, check_type=0, group=2)],
        group_count=2,
        semantics=1,
    )
    source = SourceSite(
        source_id=55,
        source_type=2,
        edge_type=18,
        direct_item_id=0,
        scene=None,
        positions=[SpawnPosition(spawn_id=66, x=1.0, y=2.0, z=3.0)],
    )
    edge = CompiledEdge(
        source_id=1,
        target_id=2,
        edge_type=3,
        flags=EdgeFlags.HAS_GROUP,
        group="and-a",
        ordinal=0,
        quantity=2,
        keyword=None,
        chance=1000,
    )
    spec = QuestSpec(
        quest_id=77,
        quest_index=4,
        prereq_quest_ids=[9],
        required_items=[req],
        steps=[step],
        giver_node_ids=[12],
        completer_node_ids=[13],
        chains_to_ids=[14],
        is_implicit=True,
        is_infeasible=False,
    )
    data = CompiledData(
        edges=[edge],
        quest_specs=[spec],
        unlock_predicates=[pred],
        item_sources=[[source]],
    )

    assert data.edges[0].group == "and-a"
    assert data.quest_specs[0].required_items[0].qty == 5
    assert data.unlock_predicates[0].conditions[0].source_id == 44
    assert data.item_sources[0][0].positions[0].spawn_id == 66


def test_compile_graph_assigns_dense_node_ids_in_key_order() -> None:
    compiled = compile_graph(_graph(_quest("quest:b"), _item("item:a"), _quest("quest:a")))

    assert compiled.node_keys == ["item:a", "quest:a", "quest:b"]
    assert compiled.node_key_to_id == {"item:a": 0, "quest:a": 1, "quest:b": 2}
    assert compiled.quest_node_ids == [1, 2]
    assert compiled.item_node_ids == [0]
    assert compiled.node_quest_index == [-1, 0, 1]
    assert compiled.node_item_index == [0, -1, -1]


def test_compile_graph_builds_topo_order_and_marks_cycles_infeasible() -> None:
    graph = _graph(
        _quest("quest:a"),
        _quest("quest:b"),
        _quest("quest:c"),
        edges=[
            Edge(source="quest:a", target="quest:b", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:b", target="quest:c", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:c", target="quest:a", type=EdgeType.REQUIRES_QUEST),
        ],
    )

    compiled = compile_graph(graph)

    assert compiled.topo_order == [0, 1, 2]
    assert compiled.infeasible_node_ids == {0, 1, 2}
    assert all(spec.is_infeasible for spec in compiled.quest_specs)


def test_compile_graph_builds_quest_specs_and_sources() -> None:
    graph = _graph(
        _quest("quest:a", db_name="QUESTA"),
        _quest("quest:b", db_name="QUESTB"),
        _item("item:x"),
        _char("char:giver"),
        _char("char:mob"),
        _spawn("spawn:mob:1"),
        edges=[
            Edge(source="quest:a", target="quest:b", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:a", target="item:x", type=EdgeType.REQUIRES_ITEM, quantity=3),
            Edge(source="quest:a", target="char:giver", type=EdgeType.ASSIGNED_BY),
            Edge(source="char:mob", target="item:x", type=EdgeType.DROPS_ITEM, chance=0.25),
            Edge(source="char:mob", target="spawn:mob:1", type=EdgeType.HAS_SPAWN),
        ],
    )

    compiled = compile_graph(graph)
    quest_a_id = compiled.node_key_to_id["quest:a"]
    quest_b_id = compiled.node_key_to_id["quest:b"]
    item_x_id = compiled.node_key_to_id["item:x"]
    giver_id = compiled.node_key_to_id["char:giver"]
    mob_id = compiled.node_key_to_id["char:mob"]
    spawn_id = compiled.node_key_to_id["spawn:mob:1"]

    spec = compiled.quest_specs[compiled.node_quest_index[quest_a_id]]
    assert spec.quest_id == quest_a_id
    assert spec.prereq_quest_ids == [quest_b_id]
    assert spec.prereq_quest_indices == [compiled.node_quest_index[quest_b_id]]
    assert spec.required_items == [ItemRequirement(item_id=item_x_id, qty=3, group=0)]
    assert spec.giver_node_ids == [giver_id]

    item_index = compiled.node_item_index[item_x_id]
    source = compiled.item_sources[item_index][0]
    assert source.source_id == mob_id
    assert source.positions == [SpawnPosition(spawn_id=spawn_id, x=10.0, y=20.0, z=30.0)]


def test_compile_graph_builds_unlock_predicates_and_reverse_deps() -> None:
    graph = _graph(
        _quest("quest:unlock", db_name="UNLOCK"),
        _quest("quest:needs", db_name="NEEDS"),
        _char("char:vendor"),
        _item("item:key"),
        edges=[
            Edge(source="quest:unlock", target="char:vendor", type=EdgeType.UNLOCKS_CHARACTER, group="route-a"),
            Edge(source="quest:needs", target="quest:unlock", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:needs", target="item:key", type=EdgeType.REQUIRES_ITEM, quantity=1),
        ],
    )

    compiled = compile_graph(graph)
    vendor_id = compiled.node_key_to_id["char:vendor"]
    unlock_id = compiled.node_key_to_id["quest:unlock"]
    needs_id = compiled.node_key_to_id["quest:needs"]
    key_id = compiled.node_key_to_id["item:key"]

    assert compiled.unlock_predicates == [
        UnlockPredicate(
            target_id=vendor_id,
            conditions=[UnlockCondition(source_id=unlock_id, check_type=0, group=1)],
            group_count=1,
            semantics=1,
        )
    ]
    unlock_qi = compiled.node_quest_index[unlock_id]
    needs_qi = compiled.node_quest_index[needs_id]
    key_ii = compiled.node_item_index[key_id]
    assert compiled.quest_to_dependent_quest_indices[unlock_qi] == [needs_qi]
    assert compiled.item_to_quest_indices[key_ii] == [needs_qi]


def test_compile_graph_builds_real_giver_blueprints_with_required_prereqs() -> None:
    graph = _graph(
        _quest("quest:pre", db_name="PREQ"),
        _quest("quest:root", db_name="ROOT"),
        _char("char:giver", scene="Town", x=1.0, y=2.0, z=3.0),
        _spawn("spawn:giver:1", scene="Town"),
        edges=[
            Edge(source="quest:root", target="quest:pre", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:root", target="char:giver", type=EdgeType.ASSIGNED_BY, keyword="hail"),
            Edge(source="char:giver", target="spawn:giver:1", type=EdgeType.HAS_SPAWN),
        ],
    )

    compiled = compile_graph(graph)
    quest_root_id = compiled.node_key_to_id["quest:root"]
    giver_id = compiled.node_key_to_id["char:giver"]
    spawn_id = compiled.node_key_to_id["spawn:giver:1"]

    assert compiled.giver_blueprints == [
        QuestGiverBlueprint(
            quest_id=quest_root_id,
            character_id=giver_id,
            position_id=spawn_id,
            interaction_type=1,
            keyword="hail",
            required_quest_db_names=["PREQ"],
        )
    ]


def test_compile_graph_builds_real_completion_blueprints() -> None:
    graph = _graph(
        _quest("quest:root", db_name="ROOT"),
        _char("char:turnin", scene="Town", x=4.0, y=5.0, z=6.0),
        _spawn("spawn:turnin:1", scene="Town"),
        edges=[
            Edge(source="quest:root", target="char:turnin", type=EdgeType.COMPLETED_BY, keyword="done"),
            Edge(source="char:turnin", target="spawn:turnin:1", type=EdgeType.HAS_SPAWN),
        ],
    )

    compiled = compile_graph(graph)
    quest_root_id = compiled.node_key_to_id["quest:root"]
    turnin_id = compiled.node_key_to_id["char:turnin"]
    spawn_id = compiled.node_key_to_id["spawn:turnin:1"]

    assert compiled.completion_blueprints == [
        QuestCompletionBlueprint(
            quest_id=quest_root_id,
            character_id=turnin_id,
            position_id=spawn_id,
            interaction_type=1,
            keyword="done",
        )
    ]


def test_compile_graph_preserves_runtime_metadata() -> None:
    graph = _graph(
        Node(
            key="door:crypt",
            type=NodeType.DOOR,
            display_name="Crypt Door",
            scene="Crypt",
            key_item_key="item:key",
        ),
        Node(
            key="faction:wardens",
            type=NodeType.FACTION,
            display_name="Wardens",
        ),
        _item("item:key"),
        Node(
            key="quest:root",
            type=NodeType.QUEST,
            display_name="Quest Root",
            db_name="ROOT",
            description="Recover the key.",
            level=12,
            zone="Starter Coast",
            zone_key="zone:starter",
            keyword="hail",
            xp_reward=120,
            gold_reward=34,
            reward_item_key="item:key",
            repeatable=True,
            disabled=True,
            disabled_text="Night only",
        ),
        Node(
            key="zone:line:depths",
            type=NodeType.ZONE_LINE,
            display_name="Ancient Tunnel",
            scene="StarterScene",
            zone="Starter Coast",
            zone_key="zone:starter",
            destination_zone_key="zone:depths",
            destination_display="Sunken Depths",
            x=1.0,
            y=2.0,
            z=3.0,
        ),
        edges=[
            Edge(source="quest:root", target="item:key", type=EdgeType.REWARDS_ITEM, note="char:vendor", amount=5),
            Edge(source="quest:root", target="zone:line:depths", type=EdgeType.UNLOCKS_ZONE_LINE),
            Edge(source="quest:root", target="faction:wardens", type=EdgeType.AFFECTS_FACTION, amount=25),
        ],
    )

    compiled = compile_graph(graph)
    quest = compiled.nodes[compiled.node_key_to_id["quest:root"]]
    door = compiled.nodes[compiled.node_key_to_id["door:crypt"]]
    zone_line = compiled.nodes[compiled.node_key_to_id["zone:line:depths"]]
    reward_edge = next(
        edge
        for edge in compiled.edges
        if edge.source_id == compiled.node_key_to_id["quest:root"]
        and edge.target_id == compiled.node_key_to_id["item:key"]
        and edge.edge_type == edge_type_byte(EdgeType.REWARDS_ITEM)
    )
    faction_edge = next(
        edge
        for edge in compiled.edges
        if edge.source_id == compiled.node_key_to_id["quest:root"]
        and edge.target_id == compiled.node_key_to_id["faction:wardens"]
    )

    assert quest.description == "Recover the key."
    assert quest.keyword == "hail"
    assert quest.xp_reward == 120
    assert quest.gold_reward == 34
    assert quest.reward_item_key == "item:key"
    assert quest.disabled_text == "Night only"
    assert quest.zone_display == "Starter Coast"
    assert door.key_item_key == "item:key"
    assert zone_line.destination_zone_key == "zone:depths"
    assert zone_line.destination_display == "Sunken Depths"
    assert reward_edge.note == "char:vendor"
    assert reward_edge.amount == 5
    assert faction_edge.amount == 25
