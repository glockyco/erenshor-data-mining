"""Tests for the gate conditions of the clean build."""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.barriers import Entry, entry_rows
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
def raw(writer: Writer) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE ObjectHierarchy (
            ObjectKey TEXT PRIMARY KEY, ParentObjectKey TEXT, ActiveSelf INTEGER, IsSceneObject INTEGER
        );
        CREATE TABLE QuestActivationEffects (
            TargetKind TEXT, TargetStableKey TEXT, Effect TEXT, ListenerKey TEXT,
            GroupIndex INTEGER, AtomKind TEXT, AtomStableKey TEXT,
            TargetObjectKey TEXT, ListenerObjectKey TEXT, ListenerComponentIsEnabled INTEGER
        );
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, SourceScene TEXT, ComponentIsEnabled INTEGER,
            ObjectKey TEXT, HostCharacterStableKey TEXT
        );
        CREATE TABLE ScriptedActivatorReferences (
            ReferenceId TEXT, SourceKey TEXT, Field TEXT, ReferenceKind TEXT, ReferenceKey TEXT
        );
        CREATE TABLE ScriptedActivatorTargets (
            ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT
        );
        CREATE TABLE DynamicCharacterSpawns (
            Key TEXT, CharacterStableKey TEXT, ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER
        );
        CREATE TABLE CharacterChainedSpawns (
            ParentStableKey TEXT, ChildStableKey TEXT, SourceScript TEXT,
            ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER
        );
        CREATE TABLE PlanningTableFurnishings (
            ObjectKey TEXT, ControllerObjectKey TEXT, Slot TEXT, Furnishing TEXT
        );
        """
    )
    for raw_table, clean_table, column in (
        ("Characters", "characters", "stable_key"),
        ("SpawnPoints", "character_spawns", "spawn_point_stable_key"),
        ("SpawnPointTriggers", "character_spawns", "spawn_point_stable_key"),
        ("ZoneLines", "zone_lines", "stable_key"),
        ("ItemBags", "item_bags", "stable_key"),
        ("Doors", "doors", "stable_key"),
        ("UiItemAccessTargets", "ui_item_access_targets", "stable_key"),
    ):
        conn.execute(f"CREATE TABLE {raw_table} (StableKey TEXT, ObjectKey TEXT, ComponentIsEnabled INTEGER)")
        if raw_table == "SpawnPointTriggers":
            continue
        for (key,) in writer.conn.execute(f"SELECT DISTINCT {column} FROM {clean_table} WHERE {column} IS NOT NULL"):
            conn.execute(f"INSERT INTO {raw_table} VALUES (?, ?, 1)", (key, f"object:{key}"))
            active = key not in {"character:lucian", "zoneline:island:tomb:808.08:14.08:592.64"}
            conn.execute("INSERT INTO ObjectHierarchy VALUES (?, NULL, ?, 1)", (f"object:{key}", int(active)))
    conn.execute("ALTER TABLE SpawnPoints ADD COLUMN IsDirectlyPlaced INTEGER DEFAULT 0")
    for listener in (
        "listener:meet",
        "listener:ritual",
        "listener:two",
        "listener:missing",
        "listener:quest",
        "listener:item",
    ):
        conn.execute("INSERT INTO ObjectHierarchy VALUES (?, NULL, 1, 1)", (listener,))
    conn.executemany(
        "INSERT INTO QuestActivationEffects VALUES (?, ?, 'enable', ?, ?, 'quest_done', ?, ?, ?, 1)",
        [
            (kind, key, listener, group, quest, f"object:{key}", listener)
            for kind, key, listener, group, quest in (
                ("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", "listener:meet", 0, "quest:meet"),
                ("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", "listener:ritual", 0, "quest:ritual"),
                ("character", "character:lucian", "listener:two", 0, "quest:meet"),
                ("character", "character:lucian", "listener:two", 0, "quest:ritual"),
            )
        ],
    )
    return conn


def _barriers(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "barriers.toml"
    path.write_text(body, encoding="utf-8")
    return path


_COMPLETE = f"""
[[barriers]]
kind = "door"
name = "Ghost door"
objects = ["{_DOOR}"]
targets = ["{_GHOST}", "zoneline:island:tomb:808.08:14.08:592.64"]
reason = "The ghost's crypt."
check = "navmesh"

[[barriers]]
kind = "door"
name = "Keep door"
objects = ["door:keep:282.83:33.13:272.05"]
targets = ["spawn:salted:1"]
reason = "The keep tower."
check = "render"
"""


def _record(**fields: str) -> str:
    """One [[barriers]] record, a complete door record unless fields override or, when empty, omit a field."""
    body = {
        "kind": '"door"',
        "name": '"Upper keep door"',
        "objects": '["door:keep:282.83:53.88:272.05"]',
        "targets": "[]",
        "reason": '"Nothing behind it."',
        "check": '"navmesh"',
    }
    body.update(fields)
    return "\n[[barriers]]\n" + "".join(f"{name} = {value}\n" for name, value in body.items() if value)


def _removal(raw: sqlite3.Connection, target: str, listener: str, quest: str, *, kind: str = "object") -> None:
    """A quest listener that disables a target once the quest is done."""
    target_object = target if kind == "object" else f"object:{target}"
    for obj in (listener, target_object):
        raw.execute("INSERT OR IGNORE INTO ObjectHierarchy VALUES (?, NULL, 1, 1)", (obj,))
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES (?, ?, 'disable', ?, 0, 'quest_done', ?, ?, ?, 1)",
        (kind, target, listener, quest, target_object, listener),
    )


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
    assert gates[("zone_line", line, None, f"activation:object:{line}")] == [
        [("quest_done", "quest:meet", None)],
        [("quest_done", "quest:ritual", None)],
    ]
    # One listener that needs two quests is one group.
    assert gates[("character", "character:lucian", None, "activation:object:character:lucian")] == [
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


def test_an_unrecorded_keyed_door_fails_the_build(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _record(objects=f'["{_DOOR}"]')

    with pytest.raises(ValueError, match=r"does not record these barriers: door:keep:282\.83:33\.13:272\.05 \(door\)"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_an_entry_for_a_door_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _COMPLETE + _record(objects='["door:gone:1.00:2.00:3.00"]')

    with pytest.raises(ValueError, match=re.escape("door:gone:1.00:2.00:3.00")):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_door_that_needs_no_key_is_no_barrier(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _COMPLETE + _record(objects='["door:tomb:100.00:0.00:0.00"]')

    with pytest.raises(ValueError, match=r"'door:tomb:100\.00:0\.00:0\.00', which no mechanism of this build opens"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_removed_object_opens_when_its_listener_quest_is_done(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    _removal(raw, "object:tomb:rockfall", "listener:meet", "quest:meet")
    body = _COMPLETE + _record(
        kind='"removed"', name='"Rock fall"', objects='["object:tomb:rockfall"]', targets=f'["{_GHOST_SPAWN}"]'
    )
    process_gates(raw, writer, _barriers(tmp_path, body))

    assert _gates(writer)[("spawn_point", _GHOST_SPAWN, None, "object:tomb:rockfall")] == [
        [("quest_done", "quest:meet", None)]
    ]
    assert writer.conn.execute("SELECT kind, name FROM barriers WHERE barrier_key = 'object:tomb:rockfall'").fetchone()


def test_a_door_that_a_listener_removes_opens_with_its_key_or_the_quest(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    _removal(raw, _DOOR, "listener:ritual", "quest:ritual", kind="door")
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))

    assert _gates(writer)[("character", _GHOST, None, _DOOR)] == [
        [("key_held", _KEY, None)],
        [("quest_done", "quest:ritual", None)],
    ]


def test_an_unrecorded_removed_object_fails_the_build(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    _removal(raw, "object:tomb:rockfall", "listener:meet", "quest:meet")

    with pytest.raises(ValueError, match=re.escape("object:tomb:rockfall (removed)")):
        process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))


def test_a_placement_that_a_listener_removes_is_no_barrier(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    _removal(raw, f"object:{_GHOST}", "listener:meet", "quest:meet")
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))

    assert writer.conn.execute("SELECT COUNT(*) FROM barriers").fetchone()[0] == 2


def test_a_record_of_the_wrong_kind_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    _removal(raw, "object:tomb:rockfall", "listener:meet", "quest:meet")
    body = _COMPLETE + _record(kind='"moved"', name='"Rock fall"', objects='["object:tomb:rockfall"]')

    with pytest.raises(ValueError, match="records 'object:tomb:rockfall' as moved, but it is removed"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_objects_that_open_differently_are_separate_barriers(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    _removal(raw, "object:tomb:rockfall", "listener:meet", "quest:meet")
    _removal(raw, "object:tomb:field", "listener:ritual", "quest:ritual")
    body = _COMPLETE + _record(
        kind='"removed"', name='"Rubble"', objects='["object:tomb:rockfall", "object:tomb:field"]'
    )

    with pytest.raises(ValueError, match="joins objects that open differently"):
        process_gates(raw, writer, _barriers(tmp_path, body))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": ""}, "has kind None"),
        ({"name": ""}, "needs a name"),
        ({"kind": '"wall"'}, "has kind 'wall'"),
        ({"kind": '["door"]'}, r"has kind \['door'\]"),
        ({"objects": "[]"}, "needs a non-empty list of objects"),
        ({"targets": ""}, "needs a list of guarded targets"),
        ({"reason": '" "'}, "needs a reason"),
        ({"check": ""}, "has check None"),
        ({"check": '"wiki"'}, "has check 'wiki'"),
        ({"guards": "[]"}, r"has unknown fields \['guards'\]"),
    ],
)
def test_a_malformed_record_fails(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection, fields: dict[str, str], message: str
) -> None:
    body = _COMPLETE + _record(**fields)

    with pytest.raises(ValueError, match=rf"barriers\.toml entry 2 {message}"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_target_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    body = _COMPLETE.replace(_GHOST, "character:missing")

    with pytest.raises(ValueError, match="character:missing"):
        process_gates(raw, writer, _barriers(tmp_path, body))


def test_a_listener_quest_the_build_lacks_fails(tmp_path: Path, writer: Writer, raw: sqlite3.Connection) -> None:
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'enable', 'listener:missing', 0, 'quest_done', 'quest:gone',"
        " 'object:character:lucian', 'listener:missing', 1)"
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
    raw.execute("UPDATE ObjectHierarchy SET ActiveSelf=0 WHERE ObjectKey=?", (f"object:{_GHOST_SPAWN}",))
    raw.executemany(
        "INSERT INTO QuestActivationEffects VALUES ('spawn_point', ?, 'enable', ?, 0, ?, ?, ?, ?, 1)",
        [
            (_GHOST_SPAWN, listener, kind, key, f"object:{_GHOST_SPAWN}", listener)
            for listener, kind, key in (
                ("listener:quest", "quest_done", "quest:meet"),
                ("listener:item", "item_held", _KEY),
            )
        ],
    )
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))

    assert _gates(writer)[("spawn_point", _GHOST_SPAWN, None, f"activation:object:{_GHOST_SPAWN}")] == [
        [("item_held", _KEY, None)],
        [("quest_done", "quest:meet", None)],
    ]
    assert not any(
        kind == "character" and key == _GHOST and gate.startswith("activation") for kind, key, _, gate in _gates(writer)
    )


def test_disable_after_enable_makes_the_same_quest_state_unavailable(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'disable', 'listener:two', 0, 'quest_done', 'quest:meet',"
        " 'object:character:lucian', 'listener:two', 1)"
    )
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:lucian', 'disable', 'listener:two', 0, 'quest_done', 'quest:ritual',"
        " 'object:character:lucian', 'listener:two', 1)"
    )
    process_gates(raw, writer, _barriers(tmp_path, _COMPLETE))
    gates = _gates(writer)

    assert gates[("character", "character:lucian", None, "activation:object:character:lucian")] == [
        [("never", "object:character:lucian", None)]
    ]


def test_stored_return_cannot_be_a_fixed_target_entry(writer: Writer) -> None:
    line = "zoneline:island:tomb:808.08:14.08:592.64"
    writer.conn.execute(
        "INSERT INTO zone_line_destination_contexts VALUES (?, 'stored_return', "
        "'saved:zone', 'saved:landing', 'source')",
        (line,),
    )
    with pytest.raises(ValueError, match="stored return destination"):
        entry_rows(writer.conn, [Entry(_GHOST_SPAWN, (line,), "The ledge has one entrance.")])


def test_a_wall_that_an_enabled_script_removes_needs_the_enabler_and_the_script_quest(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    raw.execute("ALTER TABLE ScriptedActivators ADD COLUMN SourceObjectName TEXT")
    raw.execute("CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT)")
    raw.execute("INSERT INTO code_facts VALUES ('progression.siv_torch.quest', 'quest', 'RITUAL')")
    for obj, parent in (
        ("object:tomb:statue", None),
        ("object:tomb:eye", "object:tomb:statue"),
        ("object:tomb:wall", None),
    ):
        raw.execute("INSERT INTO ObjectHierarchy VALUES (?, ?, 1, 1)", (obj, parent))
    raw.executemany(
        "INSERT INTO ScriptedActivators (SourceKey, RuleId, SourceScene, ComponentIsEnabled, ObjectKey)"
        " VALUES (?, ?, 'Tomb', ?, ?)",
        [("startup", "jaws_statue_startup", 1, "object:tomb:statue"), ("gaze", "siv_torch_gaze", 0, "object:tomb:eye")],
    )
    raw.executemany(
        "INSERT INTO ScriptedActivatorReferences VALUES (?, ?, ?, ?, ?)",
        [
            ("r1", "startup", "StartOnComplete", "quest", "quest:meet"),
            ("r2", "startup", "Vision", "controller", "gaze"),
            ("r3", "gaze", "BreakWall", "object", "object:tomb:wall"),
        ],
    )
    body = _COMPLETE + _record(
        kind='"removed"', name='"Gaze wall"', objects='["object:tomb:wall"]', targets=f'["{_GHOST_SPAWN}"]'
    )
    process_gates(raw, writer, _barriers(tmp_path, body))

    # The gaze behaviour starts disabled, so the wall falls only after the startup quest enables it.
    assert _gates(writer)[("spawn_point", _GHOST_SPAWN, None, "object:tomb:wall")] == [
        [("quest_done", "quest:meet", None), ("quest_done", "quest:ritual", None)]
    ]
    # The same controller finishes its quest in its zone once it can act.
    events = writer.conn.execute("SELECT quest_stable_key, zone_stable_key FROM scripted_events")
    assert [tuple(row) for row in events] == [("quest:ritual", "zone:tomb")]
    conditions = writer.conn.execute("SELECT atom_kind, atom_stable_key FROM scripted_event_conditions")
    assert [tuple(row) for row in conditions] == [("quest_done", "quest:meet")]


def test_cliffs_of_the_twin_giants_open_only_once_both_twins_are_dead(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    raw.execute("CREATE TABLE SpawnPointCharacters (SpawnPointStableKey TEXT, CharacterStableKey TEXT)")
    raw.executemany(
        "INSERT INTO SpawnPointCharacters VALUES (?, ?)",
        [(_GHOST_SPAWN, _GHOST), ("spawn:salted:1", "character:bassle")],
    )
    for obj in ("object:plane:bridge", "object:plane:frostcliff", "object:plane:infernocliff"):
        raw.execute("INSERT INTO ObjectHierarchy VALUES (?, NULL, 1, 1)", (obj,))
    raw.execute(
        "INSERT INTO ScriptedActivators (SourceKey, RuleId, SourceScene, ComponentIsEnabled, ObjectKey)"
        " VALUES ('bridge', 'twin_giants', 'Tomb', 1, 'object:plane:bridge')"
    )
    raw.executemany(
        "INSERT INTO ScriptedActivatorReferences VALUES (?, 'bridge', ?, ?, ?)",
        [
            ("r1", "FrostCliff", "object", "object:plane:frostcliff"),
            ("r2", "InfernoCliff", "object", "object:plane:infernocliff"),
            ("r3", "$checkin_spawn_point", "spawn_point", _GHOST_SPAWN),
            ("r4", "$checkin_spawn_point", "spawn_point", "spawn:salted:1"),
        ],
    )
    body = _COMPLETE + _record(
        kind='"removed"',
        name='"Frost cliff"',
        objects='["object:plane:frostcliff"]',
        targets='["zoneline:island:tomb:808.08:14.08:592.64"]',
    )
    body += _record(kind='"removed"', name='"Inferno cliff"', objects='["object:plane:infernocliff"]')
    process_gates(raw, writer, _barriers(tmp_path, body))

    # Either twin alive keeps both cliffs, so one group needs both deaths.
    assert _gates(writer)[
        ("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", None, "object:plane:frostcliff")
    ] == [[("encounter_won", "character:bassle", None), ("encounter_won", _GHOST, None)]]


def test_the_torch_statue_rises_only_while_the_flint_lights_the_torches(
    tmp_path: Path, writer: Writer, raw: sqlite3.Connection
) -> None:
    writer.conn.execute(
        "INSERT INTO items (stable_key, id, display_name, image_name) VALUES ('item:flint', '7', 'F', 'f')"
    )
    raw.execute("CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT)")
    raw.executemany(
        "INSERT INTO code_facts VALUES (?, ?, ?, 'text')",
        [
            ("progression.bellwain.flint", "item_id", "7"),
            ("progression.bellwain.finish", "quest", "MEET"),
            ("progression.bellwain.quest", "quest", "MEET"),
        ],
    )
    raw.execute("ALTER TABLE ScriptedActivators ADD COLUMN SourceObjectName TEXT")
    raw.execute("INSERT INTO ObjectHierarchy VALUES ('object:island:statue', NULL, 1, 1)")
    raw.execute(
        "INSERT INTO ScriptedActivators (SourceKey, RuleId, SourceScene, ComponentIsEnabled, ObjectKey)"
        " VALUES ('angel', 'bellwain_reveal', 'Tomb', 1, 'object:island:statue')"
    )
    raw.execute(
        "INSERT INTO ScriptedActivatorReferences VALUES ('r1', 'angel', '$host', 'object', 'object:island:statue')"
    )
    body = _COMPLETE + _record(
        kind='"moved"',
        name='"Torch statue"',
        objects='["object:island:statue"]',
        targets='["zoneline:island:tomb:808.08:14.08:592.64"]',
    )
    process_gates(raw, writer, _barriers(tmp_path, body))

    # The statue rises only once the torches are lit, which needs the flint.
    assert _gates(writer)[("zone_line", "zoneline:island:tomb:808.08:14.08:592.64", None, "object:island:statue")] == [
        [("item_held", "item:flint", None)]
    ]
