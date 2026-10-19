"""Unit tests for the guide compiler."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from erenshor.application.guide.compiler import (
    SpawnPosition,
    combine_gates,
    compile_graph,
    edge_type_byte,
)
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import (
    AtomKind,
    BackgroundSource,
    Edge,
    EdgeType,
    Gate,
    GateAtom,
    Node,
    NodeType,
    SubjectKind,
)

from .fixtures import build_graph, item_node, quest_node, spawn_node


def _done(quest: str) -> GateAtom:
    return GateAtom(AtomKind.QUEST_DONE, quest)


def _gate(subject: str, *groups: tuple[GateAtom, ...], kind: SubjectKind = SubjectKind.CHARACTER) -> Gate:
    return Gate(kind, subject, f"test:{len(groups)}", groups)


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


@pytest.mark.parametrize("kind", ["door", "ui_item_access_target"])
def test_gate_reader_preserves_shared_access_subjects_and_world_state(kind: str) -> None:
    from erenshor.application.guide.edge_builder import _add_gates

    graph = EntityGraph()
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE gate_conditions (
                subject_kind TEXT, subject_stable_key TEXT, item_stable_key TEXT, gate TEXT,
                group_index INTEGER, atom_kind TEXT, atom_stable_key TEXT, atom_slot TEXT, atom_quantity INTEGER
            );
            CREATE TABLE quests (stable_key TEXT, db_name TEXT);
            """
        )
        connection.execute(
            "INSERT INTO gate_conditions VALUES "
            "(?, 'access:native', NULL, 'activation', 0, 'world_state', ?, NULL, NULL)",
            (kind, "world_state:weather:raining:zone:braxonian"),
        )
        _add_gates(connection, graph)

    assert graph.gates_for(SubjectKind(kind), "access:native") == [
        Gate(
            SubjectKind(kind),
            "access:native",
            "activation",
            ((GateAtom(AtomKind.WORLD_STATE, "world_state:weather:raining:zone:braxonian"),),),
        )
    ]


@pytest.mark.parametrize("quantity", [None, 1, 9])
def test_gate_reader_and_override_preserve_defeat_quantity(quantity: int | None, tmp_path: Path) -> None:
    from erenshor.application.guide.edge_builder import _add_gates
    from erenshor.application.guide.graph_overrides import _parse_gate
    from erenshor.application.processor.writer import Writer

    graph = EntityGraph()
    writer = Writer(tmp_path / "reader.sqlite")
    writer.create_schema()
    with closing(writer.conn) as connection:
        connection.execute(
            """INSERT INTO gate_conditions (
                subject_kind, subject_stable_key, gate, group_index, atom_kind, atom_stable_key, atom_quantity
            ) VALUES ('character', 'character:astra', 'activation', 0, 'encounter_won', 'character:stardust', ?)""",
            (quantity,),
        )
        _add_gates(connection, graph)
    gate = graph.gates_for(SubjectKind.CHARACTER, "character:astra")[0]
    expected = GateAtom(AtomKind.ENCOUNTER_WON, "character:stardust", quantity=quantity or 1)
    assert gate.groups == ((expected,),)
    assert combine_gates([gate]) == ((expected,),)
    atom: dict[str, object] = {"kind": "encounter_won", "ref": "character:stardust"}
    if quantity is not None:
        atom["quantity"] = quantity
    assert _parse_gate(
        {"subject_kind": "character", "subject": "character:astra", "gate": "activation", "groups": [[atom]]}
    ).groups == ((expected,),)


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5])
def test_gate_atom_rejects_invalid_defeat_quantity(quantity) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        GateAtom(AtomKind.ENCOUNTER_WON, "character:stardust", quantity=quantity)


def test_compile_graph_assigns_dense_node_ids_in_key_order() -> None:
    compiled = compile_graph(build_graph(quest_node("quest:b"), item_node("item:a"), quest_node("quest:a")))

    assert compiled.node_keys == ["item:a", "quest:a", "quest:b"]
    assert compiled.node_key_to_id == {"item:a": 0, "quest:a": 1, "quest:b": 2}
    assert compiled.quest_node_ids == [1, 2]
    assert compiled.item_node_ids == [0]
    assert compiled.node_item_index == [0, -1, -1]


def test_compile_graph_builds_item_sources() -> None:
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
    item_x_id = compiled.node_key_to_id["item:x"]
    mob_id = compiled.node_key_to_id["char:mob"]
    spawn_id = compiled.node_key_to_id["spawn:mob:1"]
    item_index = compiled.node_item_index[item_x_id]
    source = compiled.item_sources[item_index][0]
    assert source.source_id == mob_id
    assert source.positions == [SpawnPosition(spawn_id=spawn_id, x=10.0, y=20.0, z=30.0)]


def test_gates_on_one_subject_must_all_hold() -> None:
    candle = GateAtom(AtomKind.ITEM_HELD, "item:candle")
    key = GateAtom(AtomKind.KEY_HELD, "item:key")
    listeners = _gate("char:x", (_done("quest:a"),), (candle,))
    door = _gate("char:x", (key,))

    # Each alternative of the listener also needs the key.
    assert combine_gates([listeners, door]) == ((candle, key), (key, _done("quest:a")))
    assert combine_gates([]) is None


def test_impossible_and_redundant_alternatives_drop_out() -> None:
    never = GateAtom(AtomKind.NEVER, "item:lost key")
    started = _gate("char:x", (_done("quest:a"),), (_done("quest:b"), _done("quest:c")))
    stopped = _gate("char:x", (GateAtom(AtomKind.QUEST_NOT_DONE, "quest:a"),), (_done("quest:b"),))

    # a with not-a contradicts itself, and b with c makes b, c, and not-a redundant.
    assert combine_gates([started, stopped]) == (
        (_done("quest:a"), _done("quest:b")),
        (_done("quest:b"), _done("quest:c")),
    )
    assert combine_gates([_gate("char:x", (never,))]) == ()


def test_zone_line_that_starts_disabled_stays_shut_without_an_activator() -> None:
    shut = Node("zoneline:shut", NodeType.ZONE_LINE, "Shut", scene="A", is_enabled=False)
    opened = Node("zoneline:opened", NodeType.ZONE_LINE, "Opened", scene="A", is_enabled=False)
    graph = build_graph(
        shut,
        opened,
        gates=[_gate("zoneline:opened", (_done("quest:a"),), kind=SubjectKind.ZONE_LINE)],
    )

    compiled = compile_graph(graph)
    by_subject = compiled.condition_by_subject

    assert compiled.conditions[by_subject[(SubjectKind.ZONE_LINE, "zoneline:shut", None)]] == ()
    assert compiled.conditions[by_subject[(SubjectKind.ZONE_LINE, "zoneline:opened", None)]] == ((_done("quest:a"),),)


def test_a_key_whose_only_source_is_behind_its_own_door_fails() -> None:
    key = GateAtom(AtomKind.KEY_HELD, "item:key")
    graph = build_graph(
        item_node("item:key"),
        _char("char:keeper"),
        spawn_node("spawn:keeper"),
        edges=[
            Edge(source="char:keeper", target="item:key", type=EdgeType.DROPS_ITEM),
            Edge(source="char:keeper", target="spawn:keeper", type=EdgeType.HAS_SPAWN),
        ],
        gates=[_gate("char:keeper", (key,))],
    )

    with pytest.raises(ValueError, match="char:keeper"):
        compile_graph(graph)


def test_an_alternative_way_around_the_door_is_no_cycle() -> None:
    key = GateAtom(AtomKind.KEY_HELD, "item:key")
    graph = build_graph(
        item_node("item:key"),
        _char("char:keeper"),
        spawn_node("spawn:keeper"),
        edges=[
            Edge(source="char:keeper", target="item:key", type=EdgeType.DROPS_ITEM),
            Edge(source="char:keeper", target="spawn:keeper", type=EdgeType.HAS_SPAWN),
        ],
        gates=[_gate("char:keeper", (key,), (_done("quest:a"),))],
    )

    compiled = compile_graph(graph)

    assert compiled.conditions == [((key,), (_done("quest:a"),))]


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
                is_map_visible INTEGER,
                furniture_item_stable_key TEXT,
                furniture_slot TEXT
            );
            """
        )
        conn.execute("INSERT INTO zones VALUES (?, ?)", ("zone:arena", "Arena"))
        conn.execute("INSERT INTO characters VALUES (?, ?)", ("char:arena", "Arena Champion"))
        conn.execute(
            "INSERT INTO character_spawns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                None,
                None,
            ),
        )
        graph = EntityGraph()
        _add_spawn_point_nodes(conn, graph, {})

        assert graph.get_node("spawn:arena").source_script == "VithArenaFight"
    finally:
        conn.close()


def test_graph_builder_omits_zone_lines_that_players_cannot_use(tmp_path: Path) -> None:
    from erenshor.application.guide.node_builder import _add_zone_line_nodes
    from erenshor.application.processor.writer import Writer

    writer = Writer(tmp_path / "guide.sqlite")
    writer.create_schema()
    try:
        writer.insert_zone_lines(
            [
                # A line that starts inactive stays a guide line, and its gate says when it appears.
                {
                    "stable_key": "zoneline:inactive",
                    "scene": "A",
                    "is_enabled": 0,
                    "is_usable": 1,
                    "unusable_reason": None,
                },
                {
                    "stable_key": "zoneline:sealed",
                    "scene": "A",
                    "is_enabled": 1,
                    "is_usable": 0,
                    "unusable_reason": "No walk reaches it.",
                },
            ]
        )
        graph = EntityGraph()
        _add_zone_line_nodes(writer.conn, graph, {})

        assert [node.key for node in graph.nodes_of_type(NodeType.ZONE_LINE)] == ["zoneline:inactive"]
    finally:
        writer.conn.close()


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


def test_build_graph_closes_connection_when_node_build_fails(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from erenshor.application.guide import graph_builder
    from erenshor.application.processor.writer import Writer

    path = tmp_path / "clean.sqlite"
    writer = Writer(path)
    writer.create_schema()
    connection = writer.conn
    monkeypatch.setattr(graph_builder.sqlite3, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setattr(graph_builder, "_build_scene_to_zone", lambda _: {})

    def fail_node_build(*_: object) -> None:
        raise RuntimeError("synthetic node failure")

    monkeypatch.setattr(graph_builder, "build_nodes", fail_node_build)

    with pytest.raises(RuntimeError, match="synthetic node failure"):
        graph_builder.build_graph(path)

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def _level_db(characters: str, spawns: str, stop_quests: str = "") -> sqlite3.Connection:
    """In-memory DB with the tables zone and character level estimation reads."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE zones (stable_key TEXT, display_name TEXT);
        CREATE TABLE characters (
            stable_key TEXT, level INTEGER, is_friendly INTEGER, is_map_visible INTEGER,
            encounter_tier TEXT, quest_complete_on_death TEXT
        );
        CREATE TABLE character_spawns (
            character_stable_key TEXT, spawn_point_stable_key TEXT, zone_stable_key TEXT
        );
        CREATE TABLE spawn_point_stop_quests (spawn_point_stable_key TEXT, quest_stable_key TEXT);
        INSERT INTO characters VALUES {characters};
        INSERT INTO character_spawns VALUES {spawns};
        {f"INSERT INTO spawn_point_stop_quests VALUES {stop_quests};" if stop_quests else ""}
        """
    )
    conn.execute("ALTER TABLE characters ADD COLUMN can_be_damaged INTEGER NOT NULL DEFAULT 1")
    return conn


def test_zone_levels_use_damageability_without_excluding_releasable_immunity() -> None:
    from erenshor.application.guide.graph_validation import _build_char_levels, _build_zone_medians

    conn = _level_db(
        "('character:immune', 99, 0, 1, 'enemy', 'quest:unreachable'), ('character:released', 25, 0, 1, 'enemy', NULL)",
        "('character:immune', 'spawn:i1', 'zone:test'),"
        " ('character:immune', 'spawn:i2', 'zone:test'),"
        " ('character:released', 'spawn:r', 'zone:test')",
    )
    try:
        conn.execute("ALTER TABLE characters ADD COLUMN invulnerable INTEGER NOT NULL DEFAULT 1")
        conn.execute("UPDATE characters SET can_be_damaged = 0 WHERE stable_key = 'character:immune'")
        assert _build_zone_medians(conn) == {"zone:test": 25}
        assert _build_char_levels(conn) == {"character:released": 25}
    finally:
        conn.close()


def test_chests_take_their_zone_level_and_stay_out_of_the_zone_median() -> None:
    from erenshor.application.guide.graph_validation import _denormalize_zone_and_source_levels

    conn = _level_db(
        "('character:mob', 40, 0, 1, 'enemy', NULL), ('character:chest', 1, 0, 1, 'chest', NULL)",
        "('character:mob', 'spawn:mob', 'zone:plane'), ('character:chest', 'spawn:chest', 'zone:plane')",
    )
    try:
        # An encounter script spawns the chest, so its node has no zone.
        graph = build_graph(
            Node("zone:plane", NodeType.ZONE, "Plane"),
            Node("character:chest", NodeType.CHARACTER, "Chest", level=1, encounter_tier="chest"),
        )
        _denormalize_zone_and_source_levels(conn, graph)
    finally:
        conn.close()

    # Level 1 is the TreasureChest faction's, not the level needed to loot it.
    assert graph.get_node("zone:plane").level == 40
    assert graph.get_node("character:chest").level == 40


def test_a_guardian_raises_only_the_zone_whose_spawns_its_death_ends() -> None:
    from erenshor.application.guide.graph_validation import _build_zone_medians

    conn = _level_db(
        "('character:ward', 5, 0, 1, 'enemy', NULL), ('character:fiend', 16, 0, 1, 'boss', 'quest:claim'),"
        " ('character:wolf', 5, 0, 1, 'enemy', NULL), ('character:alpha', 16, 0, 1, 'boss', 'quest:hunt')",
        "('character:ward', 'spawn:w1', 'zone:hall'), ('character:ward', 'spawn:w2', 'zone:hall'),"
        " ('character:fiend', 'spawn:f', 'zone:hall'), ('character:wolf', 'spawn:p1', 'zone:woods'),"
        " ('character:wolf', 'spawn:p2', 'zone:woods'), ('character:alpha', 'spawn:a', 'zone:woods')",
        # The claim ends every hall spawn; the hunt leaves one wolf point spawning.
        "('spawn:w1', 'quest:claim'), ('spawn:w2', 'quest:claim'), ('spawn:f', 'quest:claim'),"
        " ('spawn:p1', 'quest:hunt'), ('spawn:a', 'quest:hunt')",
    )
    try:
        medians = _build_zone_medians(conn)
    finally:
        conn.close()

    assert medians == {"zone:hall": 16, "zone:woods": 5}


def test_characters_get_the_level_of_reaching_them_beside_their_own_level() -> None:
    from erenshor.application.guide.graph_validation import _denormalize_quest_metadata

    conn = _level_db(
        "('character:mob', 4, 0, 1, 'enemy', NULL), ('character:boss', 20, 0, 1, 'boss', NULL),"
        " ('character:giver', 35, 1, 1, 'npc', NULL), ('character:brazier', 99, 1, 1, 'npc', NULL),"
        " ('character:statue', 99, 1, 1, 'npc', NULL)",
        "('character:mob', 'spawn:m1', 'zone:hills'), ('character:mob', 'spawn:m2', 'zone:hills'),"
        " ('character:boss', 'spawn:b', 'zone:hills'), ('character:giver', 'spawn:g', 'zone:hills'),"
        " ('character:brazier', 'spawn:r', 'zone:hills'), ('character:statue', 'spawn:s', 'zone:hills')",
    )
    try:
        graph = build_graph(
            Node("character:mob", NodeType.CHARACTER, "Mob", level=4),
            Node("character:boss", NodeType.CHARACTER, "Boss", level=20),
            # A friendly NPC can still be attacked; a brazier can't.
            Node("character:giver", NodeType.CHARACTER, "Giver", level=35, is_friendly=True),
            Node("character:brazier", NodeType.CHARACTER, "Brazier", level=99, is_friendly=True, invulnerable=True),
            Node("character:statue", NodeType.CHARACTER, "Statue", level=99, is_friendly=True, invulnerable=True),
            quest_node("quest:gate", "Gate"),
            edges=[Edge("quest:gate", "character:boss", EdgeType.STEP_KILL)],
            gates=[_gate("character:brazier", (_done("quest:gate"),))],
        )
        _denormalize_quest_metadata(conn, graph)
    finally:
        conn.close()

    # The zone median of the hills is 4, but the brazier waits on a level 20
    # quest. Combat levels stay; mod_writer picks one per interaction.
    assert graph.get_node("character:statue").place_level == 4
    assert graph.get_node("character:brazier").place_level == 20
    assert graph.get_node("character:giver").place_level == 4
    assert graph.get_node("character:statue").level == 99
    assert graph.get_node("character:boss").level == 20


def test_item_use_obtainability_propagates_used_item_level_and_ignores_background_sources() -> None:
    from erenshor.application.guide.graph_validation import _denormalize_quest_metadata

    conn = _level_db(
        "('character:mob', 25, 0, 1, 'enemy', NULL)",
        "('character:mob', 'spawn:mob', 'zone:forest')",
    )
    try:
        used = item_node("item:bag")
        created = item_node("item:stone")
        background = item_node(
            "item:background",
            background_sources=[
                BackgroundSource("world_drop", "Any enemy", 0.1, level=1),
                BackgroundSource("fishing_bonus", "Any fishing catch", 1.25),
                BackgroundSource("treasure_chest", "Treasure map chest", 50, level=1, level_max=9),
            ],
        )
        graph = build_graph(
            quest_node("quest:use", "USE"),
            quest_node("quest:background", "BACKGROUND"),
            used,
            created,
            background,
            Node("character:mob", NodeType.CHARACTER, "Mob", level=25),
            edges=[
                Edge("character:mob", used.key, EdgeType.DROPS_ITEM),
                Edge(used.key, created.key, EdgeType.CREATES_ITEM),
                Edge("quest:use", created.key, EdgeType.REQUIRES_ITEM),
                Edge("quest:background", background.key, EdgeType.REQUIRES_ITEM),
            ],
        )
        _denormalize_quest_metadata(conn, graph)
    finally:
        conn.close()
    assert used.obtainability_level == created.obtainability_level == 25
    assert graph.get_node("quest:use").level == 25
    assert background.obtainability_level is None
    assert graph.get_node("quest:background").level is None


def test_item_use_unknown_source_and_cycle_have_no_obtainability_level() -> None:
    from erenshor.application.guide.graph_validation import _item_obtainability_level, _LevelContext

    a, b = item_node("item:a"), item_node("item:b")
    graph = build_graph(a, b, edges=[Edge(a.key, b.key, EdgeType.CREATES_ITEM)])
    ctx = _LevelContext(graph, {}, {}, {}, {}, {})
    assert _item_obtainability_level(b.key, ctx, set()) is None
    graph.add_edge(Edge(b.key, a.key, EdgeType.CREATES_ITEM))
    graph.build_indexes()
    assert _item_obtainability_level(a.key, ctx, set()) is None


@pytest.mark.parametrize(
    ("action", "groups", "common_level", "expected"),
    [
        (EdgeType.STEP_TRAVEL, ("completion:test", "completion:test"), None, 4),
        (EdgeType.STEP_KILL, ("completion:test", "completion:test"), None, 4),
        (EdgeType.STEP_TALK, ("completion:test", "completion:test"), None, 4),
        (EdgeType.STEP_SHOUT, ("completion:test", "completion:test"), None, 4),
        (EdgeType.STEP_READ, ("completion:test", "completion:test"), None, 4),
        (EdgeType.STEP_TRAVEL, (None, None), None, 24),
        (EdgeType.STEP_KILL, (None, None), None, 24),
        (EdgeType.STEP_TALK, (None, None), None, 24),
        (EdgeType.STEP_SHOUT, (None, None), None, 24),
        (EdgeType.STEP_READ, (None, None), None, 4),
        (EdgeType.STEP_TRAVEL, ("completion:test", "completion:test"), 12, 12),
        (EdgeType.STEP_KILL, ("completion:test", "completion:test"), 12, 12),
        (EdgeType.STEP_TRAVEL, ("completion:first", "completion:second"), None, 24),
    ],
)
def test_quest_levels_preserve_required_steps_and_explicit_alternatives(
    action: EdgeType, groups: tuple[str | None, str | None], common_level: int | None, expected: int
) -> None:
    from erenshor.application.guide.graph_validation import _estimate_quest_level

    quest = quest_node("quest:choices", "CHOICES")
    zones = [Node(f"zone:{name}", NodeType.ZONE, name) for name in ("easy", "hard", "common")]
    characters = [Node(f"character:{name}", NodeType.CHARACTER, name) for name in ("easy", "hard", "common")]
    items = [item_node(f"item:{name}") for name in ("easy", "hard")]
    targets = {
        EdgeType.STEP_TRAVEL: zones,
        EdgeType.STEP_KILL: characters,
        EdgeType.STEP_TALK: characters,
        EdgeType.STEP_SHOUT: characters,
        EdgeType.STEP_READ: items,
    }[action]
    edges = [
        Edge(characters[0].key, items[0].key, EdgeType.DROPS_ITEM),
        Edge(characters[1].key, items[1].key, EdgeType.DROPS_ITEM),
        Edge(quest.key, targets[0].key, action, group=groups[0]),
        Edge(quest.key, targets[1].key, action, group=groups[1]),
    ]
    if common_level is not None:
        edges.append(Edge(quest.key, characters[2].key, EdgeType.STEP_KILL))
    graph = build_graph(quest, *zones, *characters, *items, edges=edges)
    zone_levels = {"zone:easy": 4, "zone:hard": 24, "zone:common": common_level or 1}
    character_levels = {"character:easy": 4, "character:hard": 24, "character:common": common_level or 1}
    character_zones = {character.key: zone.key for character, zone in zip(characters, zones, strict=True)}

    assert _estimate_quest_level(quest, graph, zone_levels, character_levels, character_zones, {}, {}) == expected
