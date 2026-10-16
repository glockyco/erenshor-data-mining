"""Tests for the gate conditions of the clean build."""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.gates import process_gates
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

_DOOR = "door:tomb:114.41:-1.78:-2.48"
_GHOST = "character:ghost"
_GHOST_SPAWN = "spawn:tomb:138.56:-2.88:-20.52"
_KEY = "item:key - ghostly key"


@pytest.fixture
def writer(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    conn = writer.conn
    conn.executemany(
        "INSERT INTO quests (stable_key, db_name, display_name, image_name) VALUES (?, ?, ?, ?)",
        [(f"quest:{name.lower()}", name, name, name) for name in ("MEET", "RITUAL", "ANGLER", "STOCK", "STOCK2")],
    )
    conn.executemany(
        "INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, ?)",
        [(key, key, key) for key in (_KEY, "item:stone set", "item:wares")],
    )
    conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        [(key, key, key) for key in (_GHOST, "character:lucian", "character:bassle", "character:vendor")],
    )
    conn.executemany(
        "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene,"
        " spawn_upon_quest_complete_stable_key, furniture_item_stable_key, furniture_slot) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (_GHOST, _GHOST_SPAWN, "Tomb", None, None, None),
            ("character:bassle", "spawn:salted:1", "Salted", "quest:angler", None, None),
            ("character:vendor", "spawn:reliquary:l1", "Reliquary", None, "item:stone set", "L1"),
        ],
    )
    conn.execute("INSERT INTO spawn_point_stop_quests VALUES ('spawn:salted:1', 'quest:ritual')")
    conn.execute(
        "INSERT INTO character_deduplications (group_key, member_stable_key, is_wiki_generated)"
        " VALUES ('character:vendor', 'character:vendor', 1)"
    )
    conn.executemany(
        "INSERT INTO character_vendor_quest_unlocks VALUES ('character:vendor', ?)",
        [("quest:stock",), ("quest:stock2",)],
    )
    conn.executemany(
        "INSERT INTO quest_variants (resource_name, quest_stable_key, unlock_item_for_vendor_stable_key)"
        " VALUES (?, ?, 'item:wares')",
        [("stock", "quest:stock"), ("stock2", "quest:stock2")],
    )
    conn.execute(
        "INSERT INTO zone_lines (stable_key, scene, is_enabled)"
        " VALUES ('zoneline:island:tomb:808.08:14.08:592.64', 'Island', 1)"
    )
    conn.executemany(
        "INSERT INTO doors (stable_key, scene, x, y, z, key_item_stable_key) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (_DOOR, "Tomb", 114.41, -1.78, -2.48, _KEY),
            ("door:keep:282.83:33.13:272.05", "Keep", 282.83, 33.13, 272.05, "item:key - skeleton key"),
            ("door:tomb:100.00:0.00:0.00", "Tomb", 100.0, 0.0, 0.0, None),
        ],
    )
    return writer


@pytest.fixture
def raw() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE ZoneLineQuestUnlocks (ZoneLineStableKey TEXT, UnlockGroup INTEGER, QuestDBName TEXT)")
    conn.execute("CREATE TABLE CharacterQuestUnlocks (CharacterStableKey TEXT, UnlockGroup INTEGER, QuestDBName TEXT)")
    conn.executemany(
        "INSERT INTO ZoneLineQuestUnlocks VALUES ('zoneline:island:tomb:808.08:14.08:592.64', ?, ?)",
        [(4, "MEET"), (9, "RITUAL")],
    )
    conn.executemany(
        "INSERT INTO CharacterQuestUnlocks VALUES ('character:lucian', 2, ?)",
        [("MEET",), ("RITUAL",)],
    )
    return conn


def _barriers(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "barriers.toml"
    path.write_text(body, encoding="utf-8")
    return path


_COMPLETE = f"""
[[barriers]]
doors = ["{_DOOR}"]
guards = ["{_GHOST}", "zoneline:island:tomb:808.08:14.08:592.64"]
reason = "The ghost's crypt."

[[barriers]]
doors = ["door:keep:282.83:33.13:272.05"]
guards = ["spawn:salted:1"]
reason = "The keep tower."
"""


def _gates(writer: Writer) -> dict[tuple[str, str, str | None, str], list[list[tuple[str, str, str | None]]]]:
    result: dict[tuple[str, str, str | None, str], dict[int, list[tuple[str, str, str | None]]]] = {}
    for kind, subject, item, gate, group, atom, key, slot in writer.conn.execute(
        "SELECT subject_kind, subject_stable_key, item_stable_key, gate, group_index, atom_kind, atom_stable_key,"
        " atom_slot FROM gate_conditions ORDER BY 1, 2, 3, 4, 5, 6, 7"
    ):
        result.setdefault((kind, subject, item, gate), {}).setdefault(group, []).append((atom, key, slot))
    return {gate: [groups[index] for index in sorted(groups)] for gate, groups in result.items()}


def test_every_rule_becomes_a_gate(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))
    gates = _gates(writer)

    line = "zoneline:island:tomb:808.08:14.08:592.64"
    # Two listeners are alternatives: one group each.
    assert gates[("zone_line", line, None, "activation")] == [
        [("quest_done", "quest:meet", None)],
        [("quest_done", "quest:ritual", None)],
    ]
    # One listener that needs two quests is one group.
    assert gates[("character", "character:lucian", None, "activation")] == [
        [("quest_done", "quest:meet", None), ("quest_done", "quest:ritual", None)]
    ]
    assert gates[("spawn_point", "spawn:salted:1", None, "spawn_start")] == [[("quest_done", "quest:angler", None)]]
    assert gates[("spawn_point", "spawn:salted:1", None, "spawn_stop")] == [[("quest_not_done", "quest:ritual", None)]]
    assert gates[("spawn_point", "spawn:reliquary:l1", None, "furnishing")] == [
        [("room_furnished", "item:stone set", "L1")]
    ]
    # Either quest adds the item to the stock.
    assert gates[("vendor_item", "character:vendor", "item:wares", "vendor_unlock")] == [
        [("quest_done", "quest:stock", None)],
        [("quest_done", "quest:stock2", None)],
    ]
    assert gates[("character", _GHOST, None, _DOOR)] == [[("key_held", _KEY, None)]]
    assert gates[("zone_line", line, None, _DOOR)] == [[("key_held", _KEY, None)]]
    # The skeleton key is not an item of the build, so the keep door never opens.
    assert gates[("spawn_point", "spawn:salted:1", None, "door:keep:282.83:33.13:272.05")] == [
        [("never", "item:key - skeleton key", None)]
    ]


def test_an_unclassified_keyed_door_fails_the_build(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = f'[[barriers]]\ndoors = ["{_DOOR}"]\nguards = []\nreason = "Nothing behind it."\n'

    with pytest.raises(ValueError, match=r"door:keep:282\.83:33\.13:272\.05 \(Keep, item:key - skeleton key\)"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_an_entry_for_a_door_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _COMPLETE + '\n[[barriers]]\ndoors = ["door:gone:1.00:2.00:3.00"]\nguards = []\nreason = "Removed."\n'

    with pytest.raises(ValueError, match=re.escape("door:gone:1.00:2.00:3.00")):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_guard_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _COMPLETE.replace(_GHOST, "character:missing")

    with pytest.raises(ValueError, match="character:missing"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_listener_quest_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO CharacterQuestUnlocks VALUES ('character:lucian', 5, 'GONE')")

    with pytest.raises(ValueError, match="'GONE'"):
        process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))
