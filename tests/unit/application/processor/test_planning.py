from __future__ import annotations

import sqlite3

import pytest

from erenshor.application.processor.planning import furniture_items_by_character


def _raw(items: list[tuple[str, int, str]], placements: list[tuple[str, str, str]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE Items (StableKey TEXT, FurnitureSet INTEGER, EquipmentToActivate TEXT)")
    conn.execute("CREATE TABLE PlanningTableCharacters (CharacterStableKey TEXT, Slot TEXT, Furnishing TEXT)")
    conn.executemany("INSERT INTO Items VALUES (?, ?, ?)", items)
    conn.executemany("INSERT INTO PlanningTableCharacters VALUES (?, ?, ?)", placements)
    return conn


def test_a_room_furnishing_takes_the_furniture_set_that_names_it() -> None:
    raw = _raw(
        [
            ("item:wood training set", 1, "Wood Training"),
            ("item:stone training set", 1, "Stone Training"),
            # Only furniture sets build a room, so another item that names
            # the same child places nothing.
            ("item:training sword", 0, "Wood Training"),
        ],
        [("character:dummy l1", "L1", "Wood Training"), ("character:dummy r4", "R4", "Stone Training")],
    )

    assert furniture_items_by_character(raw) == {
        "character:dummy l1": ("item:wood training set", "L1"),
        "character:dummy r4": ("item:stone training set", "R4"),
    }


def test_two_furniture_sets_that_build_one_furnishing_stop_the_build() -> None:
    raw = _raw([("item:a", 1, "Wood Training"), ("item:b", 1, "Wood Training")], [])

    with pytest.raises(ValueError, match="both build 'Wood Training'"):
        furniture_items_by_character(raw)


def test_a_furnishing_that_no_furniture_set_builds_stops_the_build() -> None:
    raw = _raw([("item:wood training set", 1, "Wood Training")], [("character:golem", "L2", "Smithy")])

    with pytest.raises(ValueError, match="no furniture set builds the furnishing 'Smithy'"):
        furniture_items_by_character(raw)


def test_a_statue_furnishing_with_a_character_stops_the_build() -> None:
    raw = _raw([("item:golden statue", 1, "GoldBrax")], [("character:statue npc", "StatueFR", "GoldBrax")])

    with pytest.raises(ValueError, match="only rooms are described"):
        furniture_items_by_character(raw)
