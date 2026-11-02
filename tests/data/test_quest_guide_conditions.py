"""Contract: every gate of the clean database reaches quest-guide.json.

A placement, zone line, or source in the guide must be at least as gated as
each gate the clean database records on it: every group of its condition must
satisfy one group of every such gate.
"""

from __future__ import annotations

import sqlite3
import struct
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import pytest
from tests.unit.application.guide.wire import character_spawns, decode_mod_guide

if TYPE_CHECKING:
    from pathlib import Path

    from erenshor.application.guide.graph import EntityGraph

Atom = tuple[str, str, str | None, int]
Condition = list[frozenset[Atom]]
Subject = tuple[str, str, str | None]


@pytest.fixture(scope="module")
def guide(graph: EntityGraph) -> dict[str, Any]:
    from erenshor.application.guide.compiler import compile_graph
    from erenshor.application.guide.mod_writer import build_mod_guide

    return build_mod_guide(graph, compile_graph(graph))


def _position(scene: str, x: float, y: float, z: float) -> tuple[str, float, float, float]:
    return (scene, round(x, 2), round(y, 2), round(z, 2))


def _condition(guide: dict[str, Any], index: int | None) -> Condition | None:
    if index is None:
        return None
    return [
        frozenset((atom["kind"], atom["ref"], atom.get("slot"), atom.get("quantity", 1)) for atom in group)
        for group in guide["_conditions"][index]
    ]


def _database_gates(conn: sqlite3.Connection) -> dict[tuple[str, str, str | None, str], Condition]:
    db_names = dict(conn.execute("SELECT stable_key, db_name FROM quests"))
    groups: dict[tuple[str, str, str | None, str], dict[int, set[Atom]]] = defaultdict(lambda: defaultdict(set))
    for kind, subject, item, gate, index, atom, key, slot, quantity in conn.execute(
        "SELECT subject_kind, subject_stable_key, item_stable_key, gate, group_index, atom_kind, atom_stable_key,"
        " atom_slot, atom_quantity FROM gate_conditions"
    ):
        ref = db_names[key] if atom in ("quest_done", "quest_not_done") else key
        groups[(kind, subject, item, gate)][index].add((atom, ref, slot, quantity or 1))
    return {
        key: [frozenset(group) for group in by_index.values() if not any(a[0] == "never" for a in group)]
        for key, by_index in groups.items()
    }


def _guide_conditions(
    conn: sqlite3.Connection, graph: EntityGraph, guide: dict[str, Any]
) -> dict[Subject, list[Condition | None]]:
    """The guide's conditions by database subject."""
    from erenshor.application.guide.schema import EdgeType

    result: dict[Subject, list[Condition | None]] = defaultdict(list)
    lines = {_position(e["scene"], e["x"], e["y"], e["z"]): e.get("condition") for e in guide["_zone_lines"]}
    for key, scene, x, y, z in conn.execute("SELECT stable_key, scene, x, y, z FROM zone_lines"):
        position = _position(scene, x, y, z)
        if position in lines:
            result[("zone_line", key, None)].append(_condition(guide, lines[position]))
    characters_by_spawn: dict[str, set[str]] = defaultdict(set)
    for character, spawn in conn.execute("SELECT character_stable_key, spawn_point_stable_key FROM character_spawns"):
        characters_by_spawn[spawn].add(character)
    for character in guide["_character_spawns"]:
        entries = character_spawns(guide, character)
        # The writer orders placements by scene, position, and spawn point key.
        spawns = []
        for edge in graph.out_edges(character, EdgeType.HAS_SPAWN):
            spawn = graph.get_node(edge.target)
            if spawn is not None and spawn.scene:
                spawns.append((spawn.scene, spawn.x, spawn.y, spawn.z, spawn.key))
        spawns.sort()
        assert len(spawns) == len(entries), character
        for (_, _, _, _, spawn_key), entry in zip(spawns, entries, strict=True):
            condition = _condition(guide, entry.get("condition"))
            copies = characters_by_spawn[spawn_key]
            if character in copies:
                result[("character", character, None)].append(condition)
            else:
                assert len(copies) == 1, (character, spawn_key, copies)
                result[("character", next(iter(copies)), None)].append(condition)
            result[("spawn_point", spawn_key, None)].append(condition)
    return result


def test_every_database_gate_reaches_the_guide(main_clean_db: Path, graph: EntityGraph, guide: dict[str, Any]) -> None:
    conn = sqlite3.connect(f"file:{main_clean_db}?mode=ro", uri=True)
    try:
        gates = _database_gates(conn)
        conditions = _guide_conditions(conn, graph, guide)
    finally:
        conn.close()

    checked = 0
    missing: list[str] = []
    for (kind, subject, item, gate), gate_groups in sorted(gates.items(), key=lambda pair: str(pair[0])):
        for condition in conditions.get((kind, subject, item), []):
            checked += 1
            if condition is None or not all(any(g <= group for g in gate_groups) for group in condition):
                missing.append(f"{kind} {subject} {item or ''} {gate}: {condition}")
    assert checked > 100
    assert not missing, "\n".join(missing[:20])


@pytest.mark.parametrize("persisted", [False, True], ids=["generated", "published"])
def test_public_sources_and_shared_places_are_serialized_once(
    main_clean_db: Path, graph: EntityGraph, guide: dict[str, Any], persisted: bool
) -> None:
    from dataclasses import asdict
    from pathlib import Path

    from erenshor.domain.value_objects.item_public_view import PublicCondition
    from erenshor.infrastructure.database.connection import DatabaseConnection
    from erenshor.infrastructure.database.repositories.item_public_view import ItemPublicViewRepository

    if persisted:
        path = Path(__file__).resolve().parents[2] / "quest_guides" / "quest-guide.json"
        guide = decode_mod_guide(path.read_text())

    item_keys = set(guide["_gate_items"])
    use_keys: set[str] = set()
    acquisition_keys: set[str] = set()

    def references(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("item_stable_key"):
                item_keys.add(value["item_stable_key"])
            if value.get("target_type") == "item":
                item_keys.add(value["target_key"])
            if value.get("use_key"):
                use_keys.add(value["use_key"])
            use_keys.update(value.get("use_keys", ()))
            if "acquisition_key" in value:
                key = value["acquisition_key"]
                acquisition_keys.add(key)
                item_keys.add(guide["_sources"][key]["item_stable_key"])
            assert "operation_use_keys" not in value
            for child in value.values():
                references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)

    references(guide["quests"])
    references(guide["_gate_items"])
    assert set(guide["_item_uses"]) == use_keys

    with DatabaseConnection(main_clean_db, read_only=True) as database:
        repository = ItemPublicViewRepository(database)
        sources = repository.sources()
        expected = {source.source_key: source for source in sources if source.item_stable_key in item_keys}
        place_sets = {source.place_set_key for source in expected.values() if source.place_set_key is not None}
        place_sets.update(
            use["place_set_key"] for use in guide["_item_uses"].values() if use.get("place_set_key") is not None
        )
        places = {key: repository.places(key) for key in place_sets}

    assert expected
    assert len(guide["_sources"]) == len(expected)
    assert set(guide["_sources"]) == set(expected)
    assert acquisition_keys <= expected.keys()
    assert guide["_version"] == 11
    assert "_source_facts" not in guide
    assert "_source_ranks" not in guide
    assert set(guide["_place_sets"]) == place_sets

    def conditions(value: dict[str, Any]) -> tuple[PublicCondition, ...]:
        return tuple(
            PublicCondition(**{"gate_index": 0, "alternative_index": 0, "atom_index": 0, **atom})
            for atom in value.get("conditions", [])
        )

    for key, source in expected.items():
        entry = guide["_sources"][key]
        entity_key = source.source_copy_stable_key or source.source_stable_key
        assert entry.get("source_key") == entity_key
        assert entry["item_stable_key"] == source.item_stable_key
        assert entry["kind"] == source.kind
        assert entry.get("place_set_key") == source.place_set_key
        assert entry.get("chance") == source.probability_min
        assert entry.get("chance_max") == source.probability_max
        assert entry.get("quantity") == source.quantity_min
        assert conditions(entry) == source.conditions
        if key in graph.source_ranks:
            tier, depth = graph.source_ranks[key]
            assert entry["rank"] == {"tier": tier, "depth": depth}
        else:
            assert "rank" not in entry
        assert not {"children", "operation_use_keys", "acquisition_key", "location_key", "x", "y", "z"} & entry.keys()

    markers = {
        spawn["stable_key"] for character in guide["_character_spawns"] for spawn in character_spawns(guide, character)
    }
    for key in place_sets:
        entries = guide["_place_sets"][key]
        expected_places = places[key]
        assert len(entries) == len(expected_places)
        assert [entry["place_key"] for entry in entries] == [str(index) for index in range(len(expected_places))]
        for entry, public in zip(entries, expected_places, strict=True):
            assert conditions(entry) == public.conditions
            expected_place = {
                field: value
                for field, value in asdict(public).items()
                if field not in {"place_set_key", "place_key", "conditions"}
                and value is not None
                and not (field == "entry_zone_line_keys" and not value)
            }
            expected_place["entry_zone_line_keys"] = list(public.entry_zone_line_keys)
            if not expected_place["entry_zone_line_keys"]:
                del expected_place["entry_zone_line_keys"]
            if public.marker_stable_key in markers:
                for field in ("scene", "x", "y", "z", "zone_stable_key"):
                    expected_place.pop(field, None)
                assert not {"scene", "x", "y", "z", "zone", "zone_stable_key"} & entry.keys()
            elif public.zone_stable_key is not None:
                zone = graph.get_node(public.zone_stable_key)
                if zone is not None:
                    expected_place["zone"] = zone.display_name
            if persisted:
                for field in ("x", "y", "z"):
                    if field in expected_place:
                        assert struct.pack("f", entry[field]) == struct.pack("f", expected_place[field])
                        expected_place[field] = entry[field]
            actual_place = {
                field: value
                for field, value in entry.items()
                if field not in {"place_key", "conditions"}
                and value is not None
                and not (field == "entry_zone_line_keys" and not value)
            }
            assert actual_place == expected_place
