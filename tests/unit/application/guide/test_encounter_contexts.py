"""Exercise the canonical encounter reader with isolated clean-schema fixtures."""

import sqlite3

import pytest

from erenshor.application.guide.encounter_contexts import read_encounter_contexts, validate_loaded_state_contract

_ACCOUNT = "account_state:reliquary_claimed"
_QUEST = "quest:independent-source-identity"
_ENCOUNTER = "encounter:native-controller-123"
_FACTS = (
    "guide.gates.reliquary_claim_loaded",
    "guide.state.reliquary_load_before_play",
    "guide.state.reliquary_load_before_play_alternate",
)


@pytest.fixture
def conn():
    database = sqlite3.connect(":memory:")
    database.executescript(
        """
        CREATE TABLE quests (stable_key TEXT PRIMARY KEY, db_name TEXT);
        CREATE TABLE character_spawns (spawn_point_stable_key TEXT PRIMARY KEY, character_stable_key TEXT);
        CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT);
        CREATE TABLE encounter_placements (
            encounter_key TEXT, root_spawn_stable_key TEXT, member_spawn_stable_key TEXT,
            role TEXT, context_kind TEXT, post_completion_role TEXT
        );
        CREATE TABLE encounter_conditions (
            encounter_key TEXT, state_scope TEXT, state_key TEXT, required_value TEXT
        );
        CREATE TABLE encounter_completions (
            encounter_key TEXT, event_kind TEXT, state_scope TEXT, state_key TEXT, result_value TEXT
        );
        CREATE TABLE encounter_event_conditions (
            encounter_key TEXT, event_kind TEXT, state_scope TEXT, state_key TEXT, required_value TEXT
        );
        """
    )
    database.execute("INSERT INTO quests VALUES (?, ?)", (_QUEST, "UNRELATED_DB_NAME"))
    database.executemany(
        "INSERT INTO character_spawns VALUES (?, ?)",
        [(f"spawn:{index}", "character:deduplicated-prefab") for index in range(5)],
    )
    database.executemany("INSERT INTO code_facts VALUES (?, 'ok', 'true', 'bool')", [(fact,) for fact in _FACTS])
    database.executemany(
        "INSERT INTO encounter_placements VALUES (?, 'spawn:0', ?, ?, 'account_claim', 'player_home')",
        [(_ENCOUNTER, f"spawn:{index}", "root" if index == 0 else "support") for index in range(5)],
    )
    database.executemany(
        "INSERT INTO encounter_conditions VALUES (?, ?, ?, 'false')",
        [(_ENCOUNTER, "account", _ACCOUNT), (_ENCOUNTER, "character", _QUEST)],
    )
    database.executemany(
        "INSERT INTO encounter_completions VALUES (?, ?, ?, ?, 'true')",
        [
            (_ENCOUNTER, "host_death", "account", _ACCOUNT),
            (_ENCOUNTER, "host_death", "character", _QUEST),
            (_ENCOUNTER, "scene_awake_quest_completed", "account", _ACCOUNT),
            (_ENCOUNTER, "scene_awake_account_claimed", "character", _QUEST),
        ],
    )
    database.executemany(
        "INSERT INTO encounter_event_conditions VALUES (?, ?, ?, ?, 'true')",
        [
            (_ENCOUNTER, "scene_awake_quest_completed", "character", _QUEST),
            (_ENCOUNTER, "scene_awake_account_claimed", "account", _ACCOUNT),
        ],
    )
    yield database
    database.close()


def test_preserves_exact_rows_and_independent_quest_identity(conn):
    result = read_encounter_contexts(conn)
    assert set(result) == {
        "encounter_placements",
        "encounter_conditions",
        "encounter_completions",
        "encounter_event_conditions",
    }
    for family, actual in result.items():
        cursor = conn.execute(f"SELECT * FROM {family}")
        fields = [column[0] for column in cursor.description]
        expected = [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]
        assert sorted(actual, key=repr) == sorted(expected, key=repr)
    placements = result["encounter_placements"]
    assert len(placements) == 5
    assert {row["member_spawn_stable_key"] for row in placements} == {f"spawn:{i}" for i in range(5)}
    assert sum(row["role"] == "support" for row in placements) == 4
    assert all(row["context_kind"] == "account_claim" for row in placements)
    assert all(row["post_completion_role"] == "player_home" for row in placements)
    assert {row["required_value"] for row in result["encounter_conditions"]} == {"false"}
    assert {row["result_value"] for row in result["encounter_completions"]} == {"true"}
    assert _QUEST in {row["state_key"] for row in result["encounter_completions"]}
    assert read_encounter_contexts(conn) == result
    conn.row_factory = sqlite3.Row
    assert read_encounter_contexts(conn) == result


def test_empty_existing_families_need_no_account_facts(conn):
    for family in (
        "encounter_event_conditions",
        "encounter_completions",
        "encounter_conditions",
        "encounter_placements",
    ):
        conn.execute(f"DELETE FROM {family}")
    conn.execute("DROP TABLE code_facts")
    assert all(not rows for rows in read_encounter_contexts(conn).values())


@pytest.mark.parametrize(
    "family", ["encounter_placements", "encounter_conditions", "encounter_completions", "encounter_event_conditions"]
)
def test_missing_family_fails(conn, family):
    conn.execute(f"DROP TABLE {family}")
    with pytest.raises(ValueError, match="encounter table"):
        read_encounter_contexts(conn)


@pytest.mark.parametrize("fact", _FACTS)
@pytest.mark.parametrize("mutation", ["missing", "false", "failed", "wrong_type", "duplicate"])
def test_entry_contract_rejects_unverified_facts(conn, fact, mutation):
    if mutation == "missing":
        conn.execute("DELETE FROM code_facts WHERE fact_id = ?", (fact,))
    elif mutation == "false":
        conn.execute("UPDATE code_facts SET value = 'false' WHERE fact_id = ?", (fact,))
    elif mutation == "failed":
        conn.execute("UPDATE code_facts SET key = 'error', value = 'assertion failed' WHERE fact_id = ?", (fact,))
    elif mutation == "wrong_type":
        conn.execute("UPDATE code_facts SET value_type = 'string' WHERE fact_id = ?", (fact,))
    else:
        conn.execute("INSERT INTO code_facts VALUES (?, 'ok', 'true', 'bool')", (fact,))
    with pytest.raises(ValueError, match=fact):
        validate_loaded_state_contract(conn)
    with pytest.raises(ValueError, match=fact):
        read_encounter_contexts(conn)


@pytest.mark.parametrize(
    "statement, message",
    [
        ("DELETE FROM character_spawns WHERE spawn_point_stable_key = 'spawn:4'", "actual placement"),
        ("DELETE FROM quests", "state reference"),
        ("UPDATE encounter_conditions SET state_scope = 'zone'", "state reference"),
        (
            "UPDATE encounter_conditions SET state_key = 'account_state:unknown' WHERE state_scope = 'account'",
            "state reference",
        ),
        ("UPDATE encounter_conditions SET required_value = 'False'", "boolean"),
        ("UPDATE encounter_conditions SET required_value = 'true'", "availability"),
        ("UPDATE encounter_placements SET context_kind = NULL", "nonempty"),
        ("UPDATE encounter_placements SET post_completion_role = 'combat'", "purpose"),
        ("UPDATE encounter_placements SET role = 'support'", "exactly one root"),
        (
            "UPDATE encounter_placements SET root_spawn_stable_key = 'spawn:1'"
            " WHERE member_spawn_stable_key = 'spawn:4'",
            "exactly one root",
        ),
        ("UPDATE encounter_conditions SET encounter_key = 'encounter:absent'", "no placement"),
        ("DELETE FROM encounter_conditions WHERE state_scope = 'character'", "character quest"),
        ("DELETE FROM encounter_completions WHERE event_kind = 'host_death'", "effects"),
        ("UPDATE encounter_completions SET result_value = 'false'", "effects"),
        ("UPDATE encounter_event_conditions SET required_value = 'false'", "guards"),
        ("DELETE FROM encounter_event_conditions", "guards"),
        ("UPDATE encounter_event_conditions SET event_kind = 'scene_start'", "guards"),
        (
            "INSERT INTO encounter_event_conditions"
            " SELECT encounter_key, event_kind, 'account', 'account_state:reliquary_claimed', 'true'"
            " FROM encounter_event_conditions WHERE state_scope = 'character'",
            "guards",
        ),
        (
            "INSERT INTO encounter_placements SELECT * FROM encounter_placements WHERE role = 'support' LIMIT 1",
            "Duplicate",
        ),
    ],
)
def test_rejects_incomplete_or_unsupported_common_rows(conn, statement, message):
    conn.execute(statement)
    with pytest.raises(ValueError, match=message):
        read_encounter_contexts(conn)


def test_requires_entry_facts_table_for_account_binding(conn):
    conn.execute("DROP TABLE code_facts")
    with pytest.raises(ValueError, match="requires code_facts"):
        read_encounter_contexts(conn)


def test_missing_required_column_fails_even_when_empty(conn):
    conn.execute("DROP TABLE encounter_placements")
    conn.execute("CREATE TABLE encounter_placements (encounter_key TEXT)")
    with pytest.raises(ValueError, match="encounter table"):
        read_encounter_contexts(conn)


def test_schema_eight_preserves_all_encounter_rows_and_exact_stored_return_line(conn):
    import json

    from erenshor.application.guide.compiler import compile_graph
    from erenshor.application.guide.encounter_contexts import read_zone_line_destination_contexts
    from erenshor.application.guide.mod_writer import serialize_mod_guide
    from erenshor.application.guide.schema import Node, NodeType

    from .fixtures import build_graph, quest_node

    graph = build_graph(
        quest_node(_QUEST, "UNRELATED_DB_NAME"),
        Node(
            "line:actual",
            NodeType.ZONE_LINE,
            "Physical return",
            scene="Home",
            x=1,
            y=2,
            z=3,
            destination_zone_key="zone:stale",
            destination_display="Stale destination",
            landing_x=7,
            landing_y=8,
            landing_z=9,
        ),
    )
    conn.execute(
        "CREATE TABLE zone_line_destination_contexts (zone_line_stable_key TEXT, kind TEXT, "
        "destination_state_key TEXT, landing_state_key TEXT, source_key TEXT)"
    )
    conn.execute(
        "INSERT INTO zone_line_destination_contexts VALUES "
        "('line:actual','stored_return','character_state:reliquary_return_zone',"
        "'character_state:reliquary_return_landing','controller:actual')"
    )
    graph.encounters = read_encounter_contexts(conn)
    graph.zone_line_destination_contexts = read_zone_line_destination_contexts(conn, graph)
    payload = json.loads(serialize_mod_guide(graph, compile_graph(graph)))
    assert payload["_encounters"] == graph.encounters
    assert len(payload["_encounters"]["encounter_placements"]) == 5
    assert payload["_quest_state_keys"] == {_QUEST: "UNRELATED_DB_NAME"}
    assert payload["_zone_line_destination_contexts"]["line:actual"] == {
        "zone_line_stable_key": "line:actual",
        "kind": "stored_return",
        "destination_state_key": "character_state:reliquary_return_zone",
        "landing_state_key": "character_state:reliquary_return_landing",
        "source_key": "controller:actual",
    }
    [line] = payload["_zone_lines"]
    assert line["stable_key"] == "line:actual"
    assert not {"destination_zone_key", "destination_display", "landing_x", "landing_y", "landing_z"}.intersection(line)


def test_stored_return_context_requires_an_actual_line_without_fallback(conn):
    from erenshor.application.guide.encounter_contexts import read_zone_line_destination_contexts

    from .fixtures import build_graph

    graph = build_graph()
    with pytest.raises(ValueError, match="zone_line_destination_contexts"):
        read_zone_line_destination_contexts(conn, graph)
    conn.execute(
        "CREATE TABLE zone_line_destination_contexts (zone_line_stable_key TEXT, kind TEXT, "
        "destination_state_key TEXT, landing_state_key TEXT, source_key TEXT)"
    )
    conn.execute(
        "INSERT INTO zone_line_destination_contexts VALUES "
        "('line:missing','stored_return','character_state:reliquary_return_zone',"
        "'character_state:reliquary_return_landing','controller:actual')"
    )
    with pytest.raises(ValueError, match="actual guide line"):
        read_zone_line_destination_contexts(conn, graph)
