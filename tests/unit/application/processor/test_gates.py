"""Tests for the gate conditions of the clean build."""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.gates import Entry, _entry_rows, process_gates
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
        "INSERT INTO quest_variants (resource_name, quest_stable_key, unlock_item_for_vendor_stable_key)"
        " VALUES (?, ?, 'item:wares')",
        [("stock", "quest:stock"), ("stock2", "quest:stock2")],
    )
    conn.executemany(
        "INSERT INTO character_vendor_quest_unlocks"
        " (character_stable_key,quest_slot,quest_stable_key,quest_variant_resource_name)"
        " VALUES ('character:vendor', ?, ?, ?)",
        [(1, "quest:stock", "stock"), (2, "quest:stock2", "stock2")],
    )
    conn.execute(
        "INSERT INTO zones (stable_key, scene_name, zone_name, display_name, image_name, zone_type)"
        " VALUES ('zone:tomb', 'Tomb', 'Tomb', 'Tomb', 'Tomb', 'Dungeon')"
    )
    conn.execute(
        "INSERT INTO zone_lines"
        " (stable_key,scene,is_enabled,destination_zone_stable_key,"
        " component_is_enabled,collider_is_trigger,has_enabled_trigger)"
        " VALUES ('zoneline:island:tomb:808.08:14.08:592.64','Island',1,'zone:tomb',1,1,1)"
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
    conn.execute(
        "CREATE TABLE QuestActivationEffects (TargetKind TEXT, TargetStableKey TEXT, Effect TEXT,"
        " ListenerKey TEXT, GroupIndex INTEGER, AtomKind TEXT, AtomStableKey TEXT)"
    )
    conn.executescript(
        """
        CREATE TABLE ScriptedActivators (SourceKey TEXT, RuleId TEXT, SourceScene TEXT, ComponentIsEnabled INTEGER);
        CREATE TABLE ScriptedActivatorReferences (ReferenceId TEXT, SourceKey TEXT, Field TEXT);
        CREATE TABLE ScriptedActivatorTargets (
            ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO QuestActivationEffects VALUES (?, ?, 'enable', ?, ?, 'quest_done', ?)",
        [
            ("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", "listener:meet", 0, "quest:meet"),
            ("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", "listener:ritual", 0, "quest:ritual"),
            ("character", "character:lucian", "listener:two", 0, "quest:meet"),
            ("character", "character:lucian", "listener:two", 0, "quest:ritual"),
        ],
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
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'enable', 'listener:missing', 0, 'quest_done', 'quest:gone')"
    )

    with pytest.raises(ValueError, match="'quest:gone'"):
        process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))


def test_an_entry_records_the_lines_that_reach_its_target(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    line = "zoneline:island:tomb:808.08:14.08:592.64"
    body = (
        _COMPLETE
        + f"""
[[entries]]
target = "{_GHOST_SPAWN}"
via = ["{line}"]
reason = "The ledge."
"""
    )
    process_gates(raw, writer, _barriers(tmp_path, body))

    rows = [tuple(row) for row in writer.conn.execute("SELECT * FROM target_entries")]
    assert rows == [("spawn_point", _GHOST_SPAWN, line)]


def test_an_entry_through_a_line_into_another_scene_fails(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    body = (
        _COMPLETE
        + """
[[entries]]
target = "spawn:salted:1"
via = ["zoneline:island:tomb:808.08:14.08:592.64"]
reason = "Wrong scene."
"""
    )

    with pytest.raises(ValueError, match="leads to Tomb, not to Salted"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_item_and_quest_activators_are_alternatives_on_the_placement(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    raw.executemany(
        "INSERT INTO QuestActivationEffects VALUES ('spawn_point', ?, 'enable', ?, 0, ?, ?)",
        [
            (_GHOST_SPAWN, "listener:quest", "quest_done", "quest:meet"),
            (_GHOST_SPAWN, "listener:item", "item_held", _KEY),
        ],
    )
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))

    assert _gates(writer)[("spawn_point", _GHOST_SPAWN, None, "activation")] == [
        [("item_held", _KEY, None)],
        [("quest_done", "quest:meet", None)],
    ]
    assert ("character", _GHOST, None, "activation") not in _gates(writer)


def test_disable_after_enable_is_an_independent_negative_gate(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'disable', 'listener:two', 0, 'quest_done', 'quest:meet')"
    )
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'disable', 'listener:two', 0, 'quest_done', 'quest:ritual')"
    )
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))
    gates = _gates(writer)

    assert gates[("character", "character:lucian", None, "activation")] == [
        [("quest_done", "quest:meet", None), ("quest_done", "quest:ritual", None)]
    ]
    assert gates[("character", "character:lucian", None, "removal:listener:two:0")] == [
        [("quest_not_done", "quest:meet", None)],
        [("quest_not_done", "quest:ritual", None)],
    ]


def test_stored_return_cannot_be_a_fixed_target_entry(writer: Writer) -> None:
    line = "zoneline:island:tomb:808.08:14.08:592.64"
    writer.conn.execute(
        "INSERT INTO zone_line_destination_contexts VALUES (?, 'stored_return', "
        "'saved:zone', 'saved:landing', 'source')",
        (line,),
    )
    with pytest.raises(ValueError, match="stored return destination"):
        _entry_rows(writer.conn, [Entry(_GHOST_SPAWN, (line,), "The ledge has one entrance.")])
