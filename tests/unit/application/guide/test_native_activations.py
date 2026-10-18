"""Native offering bindings, serialized acquisition paths and accessibility."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.graph_validation import (
    _character_accessibility_level,
    _item_obtainability_level,
    _LevelContext,
)
from erenshor.application.guide.mod_writer import serialize_mod_guide
from erenshor.application.guide.node_builder import _add_native_activations
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


@pytest.fixture
def native():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    site_columns = """event_display_name TEXT, event_x REAL, event_y REAL, event_z REAL,
        trigger_bounds_center_x REAL, trigger_bounds_center_y REAL, trigger_bounds_center_z REAL,
        trigger_bounds_extents_x REAL, trigger_bounds_extents_y REAL, trigger_bounds_extents_z REAL"""
    conn.execute(f"""CREATE TABLE character_spawns (character_stable_key TEXT,
        spawn_point_stable_key TEXT, source_script TEXT, scene TEXT,
        trigger_item_stable_key TEXT, {site_columns})""")
    conn.execute(f"""CREATE TABLE arena_rounds (stable_key TEXT, scene TEXT,
        arena_object_name TEXT, round_index INTEGER, coin_item_stable_key TEXT,
        award_chest_character_stable_key TEXT, {site_columns})""")
    conn.execute("""CREATE TABLE arena_round_enemies (arena_round_stable_key TEXT,
        sequence_index INTEGER, enemy_character_stable_key TEXT)""")
    graph = EntityGraph()
    site = ("Arena", 1, 2, 3, 4, 5, 6, 7, 8, 9)

    def node(key, kind):
        if not graph.has_node(key):
            graph.add_node(Node(key, kind, key, game_id="1" if kind == NodeType.ITEM else None))

    def spawn(character, script, scene, item=None, location=None):
        node(character, NodeType.CHARACTER)
        key = f"{character}|{script}"
        graph.add_node(Node(key, NodeType.SPAWN_POINT, character, scene=scene, x=20, y=21, z=22, source_script=script))
        graph.add_edge(Edge(character, key, EdgeType.HAS_SPAWN))
        conn.execute(
            "INSERT INTO character_spawns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (character, key, script, scene, item, *(location or (None,) * 10)),
        )
        return key

    for index in range(1, 9):
        item, chest = f"item:fee{index}", f"character:chest{index}"
        node(item, NodeType.ITEM)
        spawn(chest, "VithArena", "ArenaScene")
        conn.execute(
            "INSERT INTO arena_rounds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"round:{index}", "ArenaScene", "ARENA EVENT", index, item, chest, *site),
        )
        # The same enemy occurs in every round, twice in the first round.
        for sequence in range(2 if index == 1 else 1):
            conn.execute(
                "INSERT INTO arena_round_enemies VALUES (?,?,?)", (f"round:{index}", sequence, "character:enemy")
            )
    spawn("character:enemy", "VithArena", "ArenaScene")
    for index in range(2):
        item = f"item:feed{index}"
        node(item, NodeType.ITEM)
        spawn(f"character:feed{index}", "MalarothFeed", "FeedScene", item, ("Feeding site", *site[1:]))
    for index in range(12):
        item = f"item:piece{min(index, 6)}"
        node(item, NodeType.ITEM)
        spawn(f"character:piece{index}", "Chessboard", "BoardScene", item)
    yield conn, graph, spawn
    conn.close()


def _payload(native):
    conn, graph, _ = native
    _add_native_activations(conn, graph)
    graph.build_indexes()
    return json.loads(serialize_mod_guide(graph, compile_graph(graph)))


def test_native_rounds_bind_all_occurrences_and_reward_roles(native):
    payload = _payload(native)
    arena = payload["_activations"]["activation:VithArena:ArenaScene:ARENA EVENT"]
    assert len(arena["offerings"]) == 8
    assert arena["offerings"][0]["spawns"] == [{"character": "character:enemy", "quantity": 2}]
    assert [offer["item_stable_key"] for offer in arena["offerings"]] == [f"item:fee{i}" for i in range(1, 9)]
    refs = payload["_character_spawns"]["character:enemy"][0]["activations"]
    assert [ref["offering"] for ref in refs] == list(range(8))
    assert {ref["role"] for ref in refs} == {"spawn"}
    for index in range(8):
        chest = f"character:chest{index + 1}"
        assert arena["offerings"][index]["reward"] == chest
        assert payload["_character_spawns"][chest][0]["activations"] == [
            {"key": "activation:VithArena:ArenaScene:ARENA EVENT", "offering": index, "role": "reward"}
        ]
    assert set(payload["_gate_items"]) == {
        offer["item_stable_key"] for activation in payload["_activations"].values() for offer in activation["offerings"]
    }


def test_trigger_offerings_group_by_controller_site_and_random_choice(native):
    payload = _payload(native)
    assert len(payload["_activations"]) == 3
    feed = payload["_activations"]["activation:MalarothFeed:FeedScene:1.00:2.00:3.00"]
    assert len(feed["offerings"]) == 2
    assert feed["site"]["bounds"]["center"] == {"x": 4, "y": 5, "z": 6}
    board = payload["_activations"]["activation:Chessboard:BoardScene"]
    assert board["site"] is None and board["display_name"] is None
    assert len(board["offerings"]) == 7
    [random] = [offer for offer in board["offerings"] if offer["random"]]
    assert len(random["spawns"]) == 6
    assert all(spawn["quantity"] == 1 for spawn in random["spawns"])
    assert all(offer["reward"] is None for offer in board["offerings"])


def test_unbound_controller_placement_fails(native):
    _, _, spawn = native
    spawn("character:unbound", "VithArena", "ArenaScene")
    with pytest.raises(ValueError, match="unbound or ambiguous native arena placement"):
        _payload(native)


def test_activation_character_without_placement_fails(native):
    conn, _, _ = native
    conn.execute("DELETE FROM character_spawns WHERE character_stable_key = 'character:chest8'")
    with pytest.raises(ValueError, match="character has no bound placement"):
        _payload(native)


def test_mixed_sited_and_site_less_controller_fails(native):
    conn, _, _ = native
    conn.execute(
        "UPDATE character_spawns SET event_x = 1, event_y = 2, event_z = 3, "
        "trigger_bounds_center_x = 1, trigger_bounds_center_y = 2, trigger_bounds_center_z = 3, "
        "trigger_bounds_extents_x = 1, trigger_bounds_extents_y = 1, trigger_bounds_extents_z = 1 "
        "WHERE character_stable_key = 'character:piece0'"
    )
    with pytest.raises(ValueError, match="mixes sited and site-less"):
        _payload(native)


@pytest.mark.parametrize("coordinate", [float("inf"), None])
def test_partial_or_nonfinite_site_fails(native, coordinate):
    conn, _, _ = native
    conn.execute("UPDATE character_spawns SET event_x = ? WHERE source_script = 'MalarothFeed'", (coordinate,))
    with pytest.raises(ValueError, match="incomplete or nonfinite site"):
        _payload(native)


def test_chest_fee_level_follows_previous_offering_without_cycle(native):
    conn, graph, spawn = native
    _add_native_activations(conn, graph)
    spawn("character:fee_source", "Ordinary", "StartScene")
    graph.add_edge(Edge("character:fee_source", "item:fee1", EdgeType.DROPS_ITEM))
    for index in range(1, 9):
        graph.add_edge(Edge(f"character:chest{index}", f"item:fee{index % 8 + 1}", EdgeType.DROPS_ITEM))
    graph.build_indexes()
    ctx = _LevelContext(graph, {}, {"character:fee_source": 45}, {}, {}, {})
    assert _item_obtainability_level("item:fee2", ctx, set()) == 45
    assert _character_accessibility_level("character:chest1", ctx, set()) == 45
    # An ordinary copy remains an alternative, without requiring the offering.
    spawn("character:chest1", "Ordinary", "StartScene")
    graph.build_indexes()
    ctx = _LevelContext(graph, {}, {"character:chest1": 5, "character:fee_source": 45}, {}, {}, {})
    assert _character_accessibility_level("character:chest1", ctx, set()) == 5


def test_shipped_resource_has_exact_native_controller_coverage():
    path = Path(__file__).resolve().parents[4] / "quest_guides/quest-guide.json"
    payload = json.loads(path.read_text())
    controllers = payload["_activations"]
    assert len(controllers) == 3
    assert sorted(len(controller["offerings"]) for controller in controllers.values()) == [2, 7, 8]
    counts = dict.fromkeys(("VithArena", "MalarothFeed", "Chessboard"), 0)
    for placements in payload["_character_spawns"].values():
        for placement in placements:
            if placement.get("source_script") in counts:
                assert placement["activations"]
                counts[placement["source_script"]] += 1
    assert counts == {"VithArena": 20, "MalarothFeed": 2, "Chessboard": 12}
    board = controllers["activation:Chessboard:Braxonian"]
    [random] = [offer for offer in board["offerings"] if offer["random"]]
    assert len(random["spawns"]) == 6
    assert board["site"] is None
    arena_key = "activation:VithArena:PlaneOfVitheo:ARENA EVENT"
    arena = controllers[arena_key]
    assert arena["offerings"][3]["spawns"] == [{"character": "character:wandering champion", "quantity": 2}]
    assert arena["offerings"][5]["spawns"] == [{"character": "character:wandering champion", "quantity": 3}]
    for character, placements in payload["_character_spawns"].items():
        for placement in placements:
            if placement.get("source_script") != "VithArena":
                continue
            expected = []
            for index, offer in enumerate(arena["offerings"]):
                if any(spawn["character"] == character for spawn in offer["spawns"]):
                    expected.append({"key": arena_key, "offering": index, "role": "spawn"})
                if offer["reward"] == character:
                    expected.append({"key": arena_key, "offering": index, "role": "reward"})
            assert placement["activations"] == expected
    fee1 = payload["_gate_items"][arena["offerings"][0]["item_stable_key"]]
    fee2 = payload["_gate_items"][arena["offerings"][1]["item_stable_key"]]
    assert any(source["source_key"] == "character:arenachest 8" for source in fee1["sources"])
    assert any(source["source_key"] == "character:arenachest 1" for source in fee2["sources"])
