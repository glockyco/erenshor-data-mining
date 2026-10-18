"""Contract: every gate of the clean database reaches quest-guide.json.

A placement, zone line, or source in the guide must be at least as gated as
each gate the clean database records on it: every group of its condition must
satisfy one group of every such gate.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import pytest

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


def _source_condition(conn: sqlite3.Connection, guide: dict[str, Any], source: dict[str, Any]) -> Condition | None:
    """Resolve the selected canonical acquisition and its exact placement."""
    if "acquisition_key" not in source:
        return _condition(guide, source.get("condition"))
    fact = guide["_source_facts"][source["acquisition_key"]]
    atoms = list(fact["conditions"])
    if "location_key" in source:
        locations = [location for location in fact["locations"] if location["location_key"] == source["location_key"]]
        assert len(locations) == 1, source
        atoms.extend(locations[0]["conditions"])
    db_names = dict(conn.execute("SELECT stable_key, db_name FROM quests"))
    gates: dict[tuple[str, str], dict[int, set[Atom]]] = defaultdict(lambda: defaultdict(set))
    for atom in atoms:
        if atom["phase"] != "availability":
            continue
        predicate = atom["predicate"]
        key = atom["reference_stable_key"]
        ref = db_names[key] if predicate in ("quest_done", "quest_not_done") else key
        quantity = atom["minimum"] if predicate == "encounter_won" and atom["minimum"] is not None else 1
        gates[(atom["scope"], atom["gate_key"])][atom["group_index"]].add(
            (predicate, ref, atom["reference_slot"], quantity)
        )
    if not gates:
        return None
    groups: Condition = [frozenset()]
    for alternatives in gates.values():
        groups = [
            group | frozenset(alternative)
            for group in groups
            for alternative in alternatives.values()
            if not any(atom[0] == "never" for atom in alternative)
        ]
    return groups


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
    for character, entries in guide["_character_spawns"].items():
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
    item_sources: list[tuple[str, dict[str, Any]]] = [
        (item, source) for item, value in guide["_gate_items"].items() for source in value.get("sources", [])
    ]
    for quest in guide["quests"]:
        for required in quest.get("required_items", []):
            item_sources += [(required["item_stable_key"], source) for source in required.get("sources", [])]
    for item, source in item_sources:
        if source.get("type") == "vendor":
            result[("vendor_item", source["source_key"], item)].append(_source_condition(conn, guide, source))
        elif source.get("type") == "pickup":
            result[("item_bag", source["source_key"], None)].append(_source_condition(conn, guide, source))
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
