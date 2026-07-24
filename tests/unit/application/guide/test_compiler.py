"""Unit tests for the new guide compiler data model."""

from __future__ import annotations

import math
import sqlite3

import pytest

from erenshor.application.guide.compiler import (
    CompiledData,
    CompiledEdge,
    CompiledNode,
    DetailDependency,
    DetailDependencySemantics,
    DetailGoalKind,
    DetailGoalSpec,
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
    node_type_byte,
)
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType, WorkflowCycle, WorkflowTarget

from .fixtures import build_graph, item_node, quest_node, spawn_node


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


def test_compiler_appends_workflow_enum_values() -> None:
    assert node_type_byte(NodeType.ASCENSION) == 24
    assert node_type_byte(NodeType.LOCATION) == 25
    assert edge_type_byte(EdgeType.STEP_BUY) == 41
    assert edge_type_byte(EdgeType.STEP_GO_TO) == 42
    assert NodeFlags.IS_TRIGGER_SPAWN == 1 << 10
    assert NodeFlags.GUIDE_ONLY == 1 << 11


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
    compiled = compile_graph(build_graph(quest_node("quest:b"), item_node("item:a"), quest_node("quest:a")))

    assert compiled.node_keys == ["item:a", "quest:a", "quest:b"]
    assert compiled.node_key_to_id == {"item:a": 0, "quest:a": 1, "quest:b": 2}
    assert compiled.quest_node_ids == [1, 2]
    assert compiled.item_node_ids == [0]
    assert compiled.node_quest_index == [-1, 0, 1]
    assert compiled.node_item_index == [0, -1, -1]


def test_compile_graph_builds_topo_order_and_marks_cycles_infeasible() -> None:
    graph = build_graph(
        quest_node("quest:a"),
        quest_node("quest:b"),
        quest_node("quest:c"),
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
    graph = build_graph(
        quest_node("quest:a", db_name="QUESTA"),
        quest_node("quest:b", db_name="QUESTB"),
        item_node("item:x"),
        _char("char:giver"),
        _char("char:mob"),
        spawn_node("spawn:mob:1"),
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


def test_compile_graph_builds_unlock_predicates_and_dependent_quest_indices() -> None:
    graph = build_graph(
        quest_node("quest:unlock", db_name="UNLOCK"),
        quest_node("quest:needs", db_name="NEEDS"),
        _char("char:vendor"),
        item_node("item:key"),
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
    assert compiled.quest_to_dependent_quest_indices[unlock_qi] == [needs_qi]


def _find_detail_goal(compiled: CompiledData, kind: DetailGoalKind, node_id: int) -> DetailGoalSpec:
    for goal in compiled.detail_goals:
        if goal.goal_kind == kind and goal.node_id == node_id:
            return goal
    raise AssertionError(f"Missing detail goal {kind!r} for node {node_id}")


def _detail_dependency(compiled: CompiledData, index: int) -> DetailDependency:
    return compiled.detail_dependencies[index]


def _child_goals(compiled: CompiledData, dependency: DetailDependency) -> list[DetailGoalSpec]:
    return [compiled.detail_goals[index] for index in dependency.child_goal_indices]


def test_compile_graph_emits_item_acquisition_detail_dependencies() -> None:
    graph = build_graph(
        quest_node("quest:reward"),
        item_node("item:note"),
        _char("char:mob"),
        edges=[
            Edge(source="char:mob", target="item:note", type=EdgeType.DROPS_ITEM),
            Edge(source="quest:reward", target="item:note", type=EdgeType.REWARDS_ITEM),
        ],
    )

    compiled = compile_graph(graph)
    item_id = compiled.node_key_to_id["item:note"]
    mob_id = compiled.node_key_to_id["char:mob"]
    reward_quest_id = compiled.node_key_to_id["quest:reward"]
    goal = _find_detail_goal(compiled, DetailGoalKind.ACQUIRE_ITEM, item_id)

    assert len(goal.dependency_indices) == 1
    dependency = _detail_dependency(compiled, goal.dependency_indices[0])
    assert dependency == DetailDependency(
        goal_kind=DetailGoalKind.ACQUIRE_ITEM,
        node_id=item_id,
        semantics=DetailDependencySemantics.ANY_OF,
        child_goal_indices=dependency.child_goal_indices,
    )
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependency)] == [
        (DetailGoalKind.UNLOCK_SOURCE, mob_id),
        (DetailGoalKind.COMPLETE_QUEST, reward_quest_id),
    ]


def test_compile_graph_emits_quest_completion_detail_dependencies() -> None:
    graph = build_graph(
        quest_node("quest:pre"),
        quest_node("quest:root"),
        item_node("item:key"),
        _char("char:giver"),
        _char("char:step"),
        _char("char:turnin"),
        edges=[
            Edge(source="quest:root", target="quest:pre", type=EdgeType.REQUIRES_QUEST),
            Edge(source="quest:root", target="item:key", type=EdgeType.REQUIRES_ITEM, quantity=1),
            Edge(source="quest:root", target="char:giver", type=EdgeType.ASSIGNED_BY),
            Edge(source="quest:root", target="char:step", type=EdgeType.STEP_TALK),
            Edge(source="quest:root", target="char:turnin", type=EdgeType.COMPLETED_BY),
        ],
    )

    compiled = compile_graph(graph)
    root_id = compiled.node_key_to_id["quest:root"]
    pre_id = compiled.node_key_to_id["quest:pre"]
    item_id = compiled.node_key_to_id["item:key"]
    giver_id = compiled.node_key_to_id["char:giver"]
    step_id = compiled.node_key_to_id["char:step"]
    turnin_id = compiled.node_key_to_id["char:turnin"]
    goal = _find_detail_goal(compiled, DetailGoalKind.COMPLETE_QUEST, root_id)

    dependencies = [_detail_dependency(compiled, index) for index in goal.dependency_indices]
    assert [dependency.semantics for dependency in dependencies] == [
        DetailDependencySemantics.ALL_OF,
        DetailDependencySemantics.ANY_OF,
        DetailDependencySemantics.ANY_OF,
    ]
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependencies[0])] == [
        (DetailGoalKind.COMPLETE_QUEST, pre_id),
        (DetailGoalKind.ACQUIRE_ITEM, item_id),
        (DetailGoalKind.UNLOCK_SOURCE, step_id),
    ]
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependencies[1])] == [
        (DetailGoalKind.UNLOCK_SOURCE, giver_id)
    ]
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependencies[2])] == [
        (DetailGoalKind.UNLOCK_SOURCE, turnin_id)
    ]


def test_compile_graph_emits_item_action_detail_dependencies() -> None:
    graph = build_graph(
        quest_node("quest:read"),
        item_node("item:note"),
        edges=[
            Edge(source="item:note", target="quest:read", type=EdgeType.ASSIGNS_QUEST),
        ],
    )

    compiled = compile_graph(graph)
    item_id = compiled.node_key_to_id["item:note"]
    goal = _find_detail_goal(compiled, DetailGoalKind.USE_ITEM_ACTION, item_id)

    assert len(goal.dependency_indices) == 1
    dependency = _detail_dependency(compiled, goal.dependency_indices[0])
    assert dependency.semantics == DetailDependencySemantics.ALL_OF
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependency)] == [
        (DetailGoalKind.ACQUIRE_ITEM, item_id)
    ]


def test_compile_graph_emits_item_action_dependencies_for_item_giver_specs() -> None:
    graph = build_graph(
        quest_node("quest:read"),
        item_node("item:note"),
        edges=[
            Edge(source="quest:read", target="item:note", type=EdgeType.ASSIGNED_BY),
        ],
    )

    compiled = compile_graph(graph)
    item_id = compiled.node_key_to_id["item:note"]
    goal = _find_detail_goal(compiled, DetailGoalKind.USE_ITEM_ACTION, item_id)

    assert len(goal.dependency_indices) == 1
    dependency = _detail_dependency(compiled, goal.dependency_indices[0])
    assert dependency.semantics == DetailDependencySemantics.ALL_OF
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependency)] == [
        (DetailGoalKind.ACQUIRE_ITEM, item_id)
    ]


def test_compile_graph_emits_unlock_group_detail_dependencies() -> None:
    graph = build_graph(
        quest_node("quest:a"),
        quest_node("quest:b"),
        item_node("item:key"),
        _char("char:target"),
        edges=[
            Edge(source="quest:a", target="char:target", type=EdgeType.UNLOCKS_CHARACTER, group="route-a"),
            Edge(source="item:key", target="char:target", type=EdgeType.UNLOCKS_CHARACTER, group="route-a"),
            Edge(source="quest:b", target="char:target", type=EdgeType.UNLOCKS_CHARACTER, group="route-b"),
        ],
    )

    compiled = compile_graph(graph)
    target_id = compiled.node_key_to_id["char:target"]
    quest_a_id = compiled.node_key_to_id["quest:a"]
    quest_b_id = compiled.node_key_to_id["quest:b"]
    item_id = compiled.node_key_to_id["item:key"]
    goal = _find_detail_goal(compiled, DetailGoalKind.UNLOCK_SOURCE, target_id)

    dependencies = [_detail_dependency(compiled, index) for index in goal.dependency_indices]
    assert [(dependency.semantics, dependency.unlock_group) for dependency in dependencies] == [
        (DetailDependencySemantics.ALL_OF, 1),
        (DetailDependencySemantics.ALL_OF, 2),
    ]
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependencies[0])] == [
        (DetailGoalKind.COMPLETE_QUEST, quest_a_id),
        (DetailGoalKind.ACQUIRE_ITEM, item_id),
    ]
    assert [(child.goal_kind, child.node_id) for child in _child_goals(compiled, dependencies[1])] == [
        (DetailGoalKind.COMPLETE_QUEST, quest_b_id)
    ]


def test_compile_graph_builds_real_giver_blueprints_with_required_prereqs() -> None:
    graph = build_graph(
        quest_node("quest:pre", db_name="PREQ"),
        quest_node("quest:root", db_name="ROOT"),
        _char("char:giver", scene="Town", x=1.0, y=2.0, z=3.0),
        spawn_node("spawn:giver:1", scene="Town"),
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
    graph = build_graph(
        quest_node("quest:root", db_name="ROOT"),
        _char("char:turnin", scene="Town", x=4.0, y=5.0, z=6.0),
        spawn_node("spawn:turnin:1", scene="Town"),
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


def test_graph_builder_spawn_nodes_preserve_source_script() -> None:
    from erenshor.application.guide.node_builder import _add_spawn_point_nodes

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE zones (stable_key TEXT, display_name TEXT);
            CREATE TABLE characters (stable_key TEXT, display_name TEXT);
            CREATE TABLE character_spawns (
                spawn_point_stable_key TEXT,
                character_stable_key TEXT,
                scene TEXT,
                x REAL,
                y REAL,
                z REAL,
                is_enabled INTEGER,
                night_spawn INTEGER,
                spawn_chance REAL,
                is_rare INTEGER,
                is_directly_placed INTEGER,
                is_trigger_spawn INTEGER,
                source_script TEXT,
                zone_stable_key TEXT,
                is_map_visible INTEGER
            );
            """
        )
        conn.execute("INSERT INTO zones VALUES (?, ?)", ("zone:arena", "Arena"))
        conn.execute("INSERT INTO characters VALUES (?, ?)", ("char:arena", "Arena Champion"))
        conn.execute(
            "INSERT INTO character_spawns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "spawn:arena",
                "char:arena",
                "ArenaScene",
                1,
                2,
                3,
                1,
                0,
                None,
                0,
                1,
                0,
                "VithArenaFight",
                "zone:arena",
                1,
            ),
        )
        graph = EntityGraph()
        _add_spawn_point_nodes(conn, graph, {})

        assert graph.get_node("spawn:arena").source_script == "VithArenaFight"
    finally:
        conn.close()


def test_graph_builder_completion_edges_keep_talk_keywords() -> None:
    from erenshor.application.guide.edge_builder import _add_quest_completion_edges

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE quest_completion_sources (
                quest_stable_key TEXT,
                method TEXT,
                source_type TEXT,
                source_stable_key TEXT,
                note TEXT
            );
            CREATE TABLE character_dialogs (
                character_stable_key TEXT,
                complete_quest_stable_key TEXT,
                keywords TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO quest_completion_sources VALUES (?, ?, ?, ?, ?)",
            ("quest:meetbassle", "talk", "character", "char:bassle", None),
        )
        conn.execute(
            "INSERT INTO character_dialogs VALUES (?, ?, ?)",
            ("char:bassle", "quest:meetbassle", "taking"),
        )

        graph = build_graph(
            quest_node("quest:meetbassle", db_name="ROOT"),
            _char("char:bassle"),
        )
        _add_quest_completion_edges(conn, graph)
        graph.build_indexes()

        edge = graph.out_edges("quest:meetbassle", EdgeType.COMPLETED_BY)[0]
        assert edge.keyword == "taking"
    finally:
        conn.close()


def test_graph_builder_groups_distinct_acquisition_sources() -> None:
    from erenshor.application.guide.edge_builder import _add_quest_acquisition_edges

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE quest_acquisition_sources (
                quest_stable_key TEXT,
                method TEXT,
                source_type TEXT,
                source_stable_key TEXT,
                note TEXT
            );
            CREATE TABLE quest_character_roles (
                quest_stable_key TEXT,
                character_stable_key TEXT,
                role TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO quest_acquisition_sources VALUES (?, ?, ?, ?, ?)",
            [
                ("quest:single", "item_read", "item", "item:single", None),
                ("quest:items", "item_read", "item", "item:a", None),
                ("quest:items", "item_read", "item", "item:b", None),
                ("quest:items", "item_read", "item", "item:a", None),
            ],
        )
        graph = build_graph(
            quest_node("quest:single"),
            quest_node("quest:items"),
            item_node("item:single"),
            item_node("item:a"),
            item_node("item:b"),
        )

        _add_quest_acquisition_edges(conn, graph)
        graph.build_indexes()

        single = graph.out_edges("quest:single", EdgeType.ASSIGNED_BY)
        alternatives = graph.out_edges("quest:items", EdgeType.ASSIGNED_BY)
        assert len(single) == 1
        assert single[0].group is None
        assert len(alternatives) == 2
        assert {edge.target for edge in alternatives} == {"item:a", "item:b"}
        assert len({edge.group for edge in alternatives}) == 1
        assert next(iter(alternatives)).group is not None
    finally:
        conn.close()


def test_graph_builder_groups_completion_sources_and_matching_steps() -> None:
    from erenshor.application.guide.edge_builder import (
        _add_quest_completion_edges,
        _add_quest_step_edges,
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE quest_completion_sources (
                quest_stable_key TEXT,
                method TEXT,
                source_type TEXT,
                source_stable_key TEXT,
                note TEXT
            );
            CREATE TABLE character_dialogs (
                character_stable_key TEXT,
                complete_quest_stable_key TEXT,
                keywords TEXT
            );
            CREATE TABLE zones (
                stable_key TEXT,
                complete_quest_on_enter_stable_key TEXT,
                complete_second_quest_on_enter_stable_key TEXT
            );
            CREATE TABLE items (
                stable_key TEXT,
                complete_on_read_stable_key TEXT
            );
            CREATE TABLE characters (
                stable_key TEXT,
                quest_complete_on_death TEXT,
                shout_trigger_quest_stable_key TEXT,
                shout_trigger_keyword TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO quest_completion_sources VALUES (?, ?, ?, ?, ?)",
            [
                ("quest:single", "talk", "character", "char:single", None),
                ("quest:talkzone", "talk", "character", "char:talk", None),
                ("quest:talkzone", "zone", "zone", "zone:talk", None),
                ("quest:deathread", "death", "character", "char:death", None),
                ("quest:deathread", "read", "item", "item:read", None),
                ("quest:twozone", "zone", "zone", "zone:a", None),
                ("quest:twozone", "zone", "zone", "zone:b", None),
                ("quest:twozone", "zone", "zone", "zone:a", None),
            ],
        )
        conn.execute(
            "INSERT INTO character_dialogs VALUES (?, ?, ?)",
            ("char:talk", "quest:talkzone", "finish"),
        )
        conn.executemany(
            "INSERT INTO zones VALUES (?, ?, ?)",
            [
                ("zone:talk", "quest:talkzone", None),
                ("zone:deathread", None, None),
                ("zone:a", "quest:twozone", None),
                ("zone:b", None, "quest:twozone"),
                ("zone:killonly", None, None),
            ],
        )
        conn.executemany(
            "INSERT INTO items VALUES (?, ?)",
            [
                ("item:read", "quest:deathread"),
            ],
        )
        conn.executemany(
            "INSERT INTO characters (stable_key, quest_complete_on_death) VALUES (?, ?)",
            [
                ("char:single", None),
                ("char:talk", None),
                ("char:death", "quest:deathread"),
                ("char:kill:a", "quest:killonly"),
                ("char:kill:b", "quest:killonly"),
            ],
        )
        graph = build_graph(
            *[
                quest_node(key)
                for key in (
                    "quest:single",
                    "quest:talkzone",
                    "quest:deathread",
                    "quest:twozone",
                    "quest:killonly",
                )
            ],
            _char("char:single"),
            _char("char:talk"),
            _char("char:death"),
            _char("char:kill:a"),
            _char("char:kill:b"),
            item_node("item:read"),
            *[
                Node(key=key, type=NodeType.ZONE, display_name=key)
                for key in ("zone:talk", "zone:a", "zone:b", "zone:killonly")
            ],
        )

        _add_quest_completion_edges(conn, graph)
        _add_quest_step_edges(conn, graph)
        graph.build_indexes()

        single = graph.out_edges("quest:single", EdgeType.COMPLETED_BY)
        assert len(single) == 1
        assert single[0].group is None

        talkzone_group = {
            edge.group for edge in graph.out_edges("quest:talkzone") if edge.target in {"char:talk", "zone:talk"}
        }
        assert len(talkzone_group) == 1
        assert next(iter(talkzone_group)) is not None
        completion_edges = graph.out_edges("quest:talkzone", EdgeType.COMPLETED_BY)
        assert len(completion_edges) == 2
        assert {edge.group for edge in completion_edges} == talkzone_group
        for edge_type in (EdgeType.STEP_TALK, EdgeType.STEP_TRAVEL):
            edges = graph.out_edges("quest:talkzone", edge_type)
            assert len(edges) == 1
            assert edges[0].group == next(iter(talkzone_group))

        deathread_group = {
            edge.group for edge in graph.out_edges("quest:deathread") if edge.target in {"char:death", "item:read"}
        }
        assert len(deathread_group) == 1
        assert next(iter(deathread_group)) is not None
        completion_edges = graph.out_edges("quest:deathread", EdgeType.COMPLETED_BY)
        assert len(completion_edges) == 2
        assert {edge.group for edge in completion_edges} == deathread_group
        for edge_type in (EdgeType.STEP_KILL, EdgeType.STEP_READ):
            edges = graph.out_edges("quest:deathread", edge_type)
            assert len(edges) == 1
            assert edges[0].group == next(iter(deathread_group))

        twozone_groups = {edge.group for edge in graph.out_edges("quest:twozone", EdgeType.COMPLETED_BY)}
        assert len(twozone_groups) == 1
        assert next(iter(twozone_groups)) is not None
        for edge_type in (EdgeType.COMPLETED_BY, EdgeType.STEP_TRAVEL):
            edges = graph.out_edges("quest:twozone", edge_type)
            assert len(edges) == 2
            assert {edge.group for edge in edges} == twozone_groups

        kill_steps = graph.out_edges("quest:killonly", EdgeType.STEP_KILL)
        assert len(kill_steps) == 2
        assert all(edge.group is None for edge in kill_steps)
    finally:
        conn.close()


def test_compile_graph_preserves_runtime_metadata() -> None:
    graph = build_graph(
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
        item_node("item:key"),
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


def test_graph_builder_synthetic_workflows_and_compile() -> None:
    from erenshor.application.guide.node_builder import _add_guide_workflow_nodes_and_edges

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE zones (stable_key TEXT, display_name TEXT);
            CREATE TABLE arena_rounds (
                stable_key TEXT, scene TEXT, round_index INTEGER,
                coin_item_stable_key TEXT, award_chest_character_stable_key TEXT,
                trigger_mode TEXT, event_display_name TEXT,
                event_x REAL, event_y REAL, event_z REAL,
                trigger_bounds_center_x REAL, trigger_bounds_center_y REAL, trigger_bounds_center_z REAL,
                trigger_bounds_extents_x REAL, trigger_bounds_extents_y REAL, trigger_bounds_extents_z REAL
            );
            CREATE TABLE arena_round_enemies (
                arena_round_stable_key TEXT, sequence_index INTEGER, enemy_character_stable_key TEXT
            );
            CREATE TABLE character_spawns (
                character_stable_key TEXT, spawn_point_stable_key TEXT, zone_stable_key TEXT, scene TEXT,
                event_x REAL, event_y REAL, event_z REAL, trigger_item_stable_key TEXT, trigger_mode TEXT,
                event_display_name TEXT, trigger_bounds_center_x REAL, trigger_bounds_center_y REAL,
                trigger_bounds_center_z REAL, trigger_bounds_extents_x REAL, trigger_bounds_extents_y REAL,
                trigger_bounds_extents_z REAL
            );
            """
        )
        conn.execute("INSERT INTO zones VALUES ('zone:arena', 'Arena')")
        conn.execute("INSERT INTO zones VALUES ('zone:malaroth', 'Malaroth')")
        arena_values = [
            (
                f"arena:r{i}",
                "Arena",
                i,
                f"item:coin{i}",
                f"char:chest{i}",
                "proximity_auto_consume",
                "Vitheo's arena",
                554.96,
                34.26,
                519.16,
                554.96,
                34.26,
                519.16,
                7.66,
                9.79,
                7.66,
            )
            for i in range(1, 9)
        ]
        conn.executemany("INSERT INTO arena_rounds VALUES (" + ",".join("?" for _ in range(16)) + ")", arena_values)
        conn.executemany(
            "INSERT INTO arena_round_enemies VALUES (?, ?, ?)",
            [
                ("arena:r1", 0, "char:enemy-a"),
                ("arena:r2", 0, "char:enemy-b"),
                ("arena:r2", 1, "char:enemy-b"),
                ("arena:r2", 2, "char:enemy-c"),
            ]
            + [(f"arena:r{i}", 0, f"char:enemy-{i}") for i in range(3, 9)],
        )
        conn.executemany(
            "INSERT INTO character_spawns VALUES (" + ",".join("?" for _ in range(16)) + ")",
            [
                (
                    "character:shivunax",
                    "trigger:good",
                    "zone:malaroth",
                    "Malaroth",
                    336.06,
                    32.31,
                    673.63,
                    "item:gen - malaroth feed",
                    "proximity_auto_consume",
                    "Malaroth feeding site",
                    336.06,
                    32.31,
                    673.63,
                    18.71,
                    7.37,
                    11.4,
                ),
                (
                    "character:demented malaroth",
                    "trigger:bad",
                    "zone:malaroth",
                    "Malaroth",
                    336.06,
                    32.31,
                    673.63,
                    "item:gen - malaroth feed bad",
                    "proximity_auto_consume",
                    "Malaroth feeding site",
                    336.06,
                    32.31,
                    673.63,
                    18.71,
                    7.37,
                    11.4,
                ),
            ],
        )
        chars = [f"char:enemy-{i}" for i in range(3, 9)] + [
            "char:enemy-a",
            "char:enemy-b",
            "char:enemy-c",
            *[f"char:chest{i}" for i in range(1, 9)],
            "character:shivunax",
            "character:demented malaroth",
        ]
        graph = build_graph(
            *[item_node(f"item:coin{i}") for i in range(1, 9)],
            item_node("item:gen - malaroth feed"),
            item_node("item:gen - malaroth feed bad"),
            *[_char(key) for key in chars],
            quest_node("quest:vithtokenmob1"),
        )
        _add_guide_workflow_nodes_and_edges(conn, graph, {"Arena": "zone:arena", "Malaroth": "zone:malaroth"})
        graph.build_indexes()

        guide_quests = [node for node in graph.nodes_of_type(NodeType.QUEST) if node.guide_only]
        assert len(guide_quests) == 10
        assert {node.db_name for node in guide_quests} == {
            *(f"guide.arena.arena:r{i}" for i in range(1, 9)),
            "guide.trigger.trigger:good",
            "guide.trigger.trigger:bad",
        }
        assert graph.get_node("guide-location:arena:arena:r1").type == NodeType.LOCATION
        assert graph.get_node("guide-location:trigger:trigger:good").display_name == "Malaroth feeding site"
        assert graph.get_node("guide-quest:arena:arena:r2").display_name == "Vitheo's arena - Round 2"
        assert graph.get_node("guide-quest:trigger:trigger:good").display_name == "character:shivunax"
        assert graph.get_node("guide-quest:trigger:trigger:bad").display_name == "character:demented malaroth"
        assert not any(
            graph.out_edges("quest:vithtokenmob1", edge_type)
            for edge_type in (EdgeType.STEP_BUY, EdgeType.STEP_GO_TO, EdgeType.STEP_KILL, EdgeType.STEP_LOOT)
        )
        arena_two = graph.get_node("guide-quest:arena:arena:r2")
        assert arena_two is not None and arena_two.workflow_cycle is not None
        assert [(target.stable_key, target.quantity) for target in arena_two.workflow_cycle.targets] == [
            ("char:enemy-b", 2),
            ("char:enemy-c", 1),
        ]
        assert (
            graph.get_node("guide-quest:trigger:trigger:good").workflow_cycle.targets[0].stable_key
            == "character:shivunax"
        )
        assert (
            graph.get_node("guide-quest:trigger:trigger:bad").workflow_cycle.targets[0].stable_key
            == "character:demented malaroth"
        )
        assert (
            graph.get_node("guide-quest:trigger:trigger:good").workflow_cycle.trigger_item_stable_key
            == "item:gen - malaroth feed"
        )
        assert (
            graph.get_node("guide-quest:trigger:trigger:bad").workflow_cycle.trigger_item_stable_key
            == "item:gen - malaroth feed bad"
        )
        assert len(graph.out_edges("guide-quest:arena:arena:r2", EdgeType.STEP_GO_TO)) == 1
        assert not graph.out_edges("guide-quest:arena:arena:r1", EdgeType.STEP_BUY)

        compiled = compile_graph(graph)
        assert len([spec for spec in compiled.quest_specs if spec.is_guide_only]) == 10
        arena_spec = next(
            spec for spec in compiled.quest_specs if compiled.nodes[spec.quest_id].key.endswith("arena:r2")
        )
        assert arena_spec.workflow_cycle is not None
        assert [target.quantity for target in arena_spec.workflow_cycle.targets] == [2, 1]
        assert all(not spec.is_infeasible for spec in compiled.quest_specs if spec.is_guide_only)
    finally:
        conn.close()


def test_graph_builder_workflows_reject_malformed_trigger_facts() -> None:
    from erenshor.application.guide.node_builder import _add_guide_workflow_nodes_and_edges

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE zones (stable_key TEXT, display_name TEXT);
            CREATE TABLE arena_rounds (
                stable_key TEXT, scene TEXT, round_index INTEGER,
                coin_item_stable_key TEXT, award_chest_character_stable_key TEXT,
                trigger_mode TEXT, event_display_name TEXT,
                event_x REAL, event_y REAL, event_z REAL,
                trigger_bounds_center_x REAL, trigger_bounds_center_y REAL, trigger_bounds_center_z REAL,
                trigger_bounds_extents_x REAL, trigger_bounds_extents_y REAL, trigger_bounds_extents_z REAL
            );
            CREATE TABLE arena_round_enemies (
                arena_round_stable_key TEXT, sequence_index INTEGER, enemy_character_stable_key TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO arena_rounds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "arena:bad",
                "Arena",
                1,
                "item:coin",
                "char:chest",
                "proximity_auto_consume",
                "Bad",
                1.0,
                2.0,
                3.0,
                1.0,
                2.0,
                3.0,
                0.0,
                1.0,
                1.0,
            ),
        )
        conn.execute("INSERT INTO arena_round_enemies VALUES ('arena:bad', 0, 'char:enemy')")
        graph = build_graph(item_node("item:coin"), _char("char:chest"), _char("char:enemy"))
        with pytest.raises(ValueError, match="non-positive trigger bounds"):
            _add_guide_workflow_nodes_and_edges(conn, graph, {"Arena": "zone:arena"})
    finally:
        conn.close()


def test_compile_graph_rejects_inconsistent_guide_workflow_flags() -> None:
    graph = build_graph(
        Node(
            key="quest:guide",
            type=NodeType.QUEST,
            display_name="Guide",
            guide_only=True,
            implicit=True,
            repeatable=True,
        )
    )
    with pytest.raises(ValueError, match="inconsistent guide-only workflow"):
        compile_graph(graph)


def test_compile_graph_rejects_nonfinite_workflow_location() -> None:
    location = Node(
        key="location:bad",
        type=NodeType.LOCATION,
        display_name="Bad location",
        scene="Arena",
        trigger_bounds_center_x=1.0,
        trigger_bounds_center_y=2.0,
        trigger_bounds_center_z=3.0,
        trigger_bounds_extents_x=1.0,
        trigger_bounds_extents_y=1.0,
        trigger_bounds_extents_z=1.0,
    )
    workflow = Node(
        key="quest:guide",
        type=NodeType.QUEST,
        display_name="Guide",
        guide_only=True,
        implicit=True,
        repeatable=True,
        workflow_cycle=WorkflowCycle(
            trigger_item_stable_key="item:trigger",
            trigger_item_quantity=1,
            trigger_mode="proximity_auto_consume",
            location_stable_key=location.key,
            targets=[WorkflowTarget("character:target", 1)],
        ),
    )
    graph = build_graph(
        item_node("item:trigger"),
        _char("character:target"),
        location,
        workflow,
    )

    with pytest.raises(ValueError, match="non-finite location metadata"):
        compile_graph(graph)


@pytest.mark.parametrize(
    ("collision", "message"),
    [
        (
            Node(
                key="guide-quest:trigger:trigger:one",
                type=NodeType.QUEST,
                display_name="Existing synthetic identity",
                db_name="existing.synthetic",
            ),
            "guide quest key collides",
        ),
        (
            Node(
                key="quest:real",
                type=NodeType.QUEST,
                display_name="Real quest",
                db_name="guide.trigger.trigger:one",
            ),
            "guide quest db name collides",
        ),
    ],
)
def test_graph_builder_rejects_workflow_identity_collisions(collision: Node, message: str) -> None:
    from erenshor.application.guide.node_builder import _add_guide_workflow_nodes_and_edges

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE zones (stable_key TEXT, display_name TEXT);
            CREATE TABLE character_spawns (
                character_stable_key TEXT, spawn_point_stable_key TEXT, zone_stable_key TEXT, scene TEXT,
                event_x REAL, event_y REAL, event_z REAL, trigger_item_stable_key TEXT, trigger_mode TEXT,
                event_display_name TEXT, trigger_bounds_center_x REAL, trigger_bounds_center_y REAL,
                trigger_bounds_center_z REAL, trigger_bounds_extents_x REAL, trigger_bounds_extents_y REAL,
                trigger_bounds_extents_z REAL
            );
            INSERT INTO zones VALUES ('zone:event', 'Event Zone');
            INSERT INTO character_spawns VALUES (
                'character:target', 'trigger:one', 'zone:event', 'EventScene',
                1.0, 2.0, 3.0, 'item:trigger', 'proximity_auto_consume',
                'Event site', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0
            );
            """
        )
        graph = build_graph(item_node("item:trigger"), _char("character:target"), collision)

        with pytest.raises(ValueError, match=message):
            _add_guide_workflow_nodes_and_edges(conn, graph, {"EventScene": "zone:event"})
    finally:
        conn.close()


def test_build_graph_closes_connection_when_node_build_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from erenshor.application.guide import graph_builder

    class TrackingConnection:
        row_factory: object = None
        closed = False

        def close(self) -> None:
            self.closed = True

    connection = TrackingConnection()
    monkeypatch.setattr(graph_builder.sqlite3, "connect", lambda _: connection)
    monkeypatch.setattr(graph_builder, "_build_scene_to_zone", lambda _: {})

    def fail_node_build(*_: object) -> None:
        raise RuntimeError("synthetic node failure")

    monkeypatch.setattr(graph_builder, "build_nodes", fail_node_build)

    with pytest.raises(RuntimeError, match="synthetic node failure"):
        graph_builder.build_graph("unused.db")

    assert connection.closed
