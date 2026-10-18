"""Scene and controller availability reaches the subjects that consumers read."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.gates import Atom, Gate, _death_trigger_gates
from erenshor.application.processor.hierarchy import apply_hierarchy_activity
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def databases(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    raw = sqlite3.connect(":memory:")
    raw.executescript(
        """
        CREATE TABLE ObjectHierarchy (ObjectKey TEXT PRIMARY KEY, ParentObjectKey TEXT,
            ActiveSelf INTEGER, IsSceneObject INTEGER);
        CREATE TABLE ScriptedActivators (SourceKey TEXT, ObjectKey TEXT, HostCharacterStableKey TEXT);
        CREATE TABLE DynamicCharacterSpawns (Key TEXT, CharacterStableKey TEXT,
            ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER);
        CREATE TABLE CharacterChainedSpawns (ParentStableKey TEXT, ChildStableKey TEXT, SourceScript TEXT,
            ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER);
        CREATE TABLE QuestActivationEffects (TargetObjectKey TEXT, Effect TEXT, ListenerKey TEXT,
            ListenerObjectKey TEXT, ListenerComponentIsEnabled INTEGER, GroupIndex INTEGER,
            AtomKind TEXT, AtomStableKey TEXT);
        CREATE TABLE ScriptedActivatorReferences (ReferenceId TEXT, SourceKey TEXT, Field TEXT,
            ReferenceKind TEXT, ReferenceKey TEXT);
        CREATE TABLE ScriptedActivatorTargets (ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT);
        CREATE TABLE SpawnPointCharacters (SpawnPointStableKey TEXT, CharacterStableKey TEXT);
        CREATE TABLE UiItemAccessTargets (StableKey TEXT, ObjectKey TEXT);
        CREATE TABLE PlanningTableFurnishings (
            ObjectKey TEXT, ControllerObjectKey TEXT, Slot TEXT, Furnishing TEXT
        );
        """
    )
    for table in ("Characters", "SpawnPoints", "SpawnPointTriggers", "ZoneLines", "ItemBags", "Doors"):
        raw.execute(f"CREATE TABLE {table} (StableKey TEXT, ObjectKey TEXT, ComponentIsEnabled INTEGER)")
    raw.execute("ALTER TABLE SpawnPoints ADD COLUMN IsDirectlyPlaced INTEGER DEFAULT 0")
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        [(key, key, key) for key in ("character:occupant", "character:fallen", "character:born")],
    )
    yield raw, writer.conn
    raw.close()
    writer.conn.close()


def _object(
    raw: sqlite3.Connection, key: str, *, parent: str | None = None, active: bool = True, scene: bool = True
) -> None:
    raw.execute("INSERT INTO ObjectHierarchy VALUES (?, ?, ?, ?)", (key, parent, int(active), int(scene)))


def _subject(
    raw: sqlite3.Connection, conn: sqlite3.Connection, kind: str, key: str, obj: str, *, component: bool = True
) -> None:
    table = {
        "character": "Characters",
        "spawn_point": "SpawnPoints",
        "zone_line": "ZoneLines",
        "ui_item_access_target": "UiItemAccessTargets",
    }[kind]
    if kind == "ui_item_access_target":
        raw.execute(f"INSERT INTO {table} VALUES (?, ?)", (key, obj))
        conn.execute(
            "INSERT INTO ui_item_access_targets VALUES (?, 'Scene', ?, 'PlanningDesk', 0, 0, 0, 0, 0)", (key, obj)
        )
    else:
        raw.execute(
            f"INSERT INTO {table} (StableKey, ObjectKey, ComponentIsEnabled) VALUES (?, ?, ?)",
            (key, obj, int(component)),
        )
        if kind == "character":
            conn.execute(
                "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, "
                "level_scales_with_player) VALUES (?, ?, ?, 'npc', 0)",
                (key, key, key),
            )
        elif kind == "spawn_point":
            conn.execute(
                "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene)"
                " VALUES ('character:occupant', ?, 'Scene')",
                (key,),
            )
        else:
            conn.execute("INSERT INTO zone_lines (stable_key, scene) VALUES (?, 'Scene')", (key,))


def _effect(raw: sqlite3.Connection, target: str, host: str, quest: str, *, effect: str = "enable") -> None:
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES (?, ?, ?, ?, 1, 0, 'quest_done', ?)",
        (target, effect, host + ":listener", host, quest),
    )


def _groups(gates: list[Gate], kind: str, key: str) -> set[frozenset[Atom]]:
    return {
        frozenset(group)
        for gate in gates
        if (gate.subject_kind, gate.subject_stable_key) == (kind, key)
        for group in gate.groups
    }


def test_an_ancestor_activation_reaches_descendants_but_not_inactive_children(databases):
    raw, conn = databases
    _object(raw, "listener")
    _object(raw, "root", active=False)
    _object(raw, "middle", parent="root")
    _object(raw, "leaf", parent="middle")
    _object(raw, "off", parent="root", active=False)
    _subject(raw, conn, "zone_line", "zoneline:leaf", "leaf")
    _subject(raw, conn, "character", "character:off", "off")
    _effect(raw, "root", "listener", "quest:ritual")

    gates = apply_hierarchy_activity(raw, conn, [])

    assert _groups(gates, "zone_line", "zoneline:leaf") == {frozenset({Atom("quest_done", "quest:ritual")})}
    assert _groups(gates, "character", "character:off") == {frozenset({Atom("never", "off")})}


def test_hosted_planning_controller_and_ui_share_the_desks_activation(databases):
    raw, conn = databases
    _object(raw, "listener")
    _object(raw, "desk", active=False)
    _object(raw, "portal", active=False)
    _object(raw, "line", parent="portal")
    _subject(raw, conn, "zone_line", "zoneline:raid", "line")
    _subject(raw, conn, "ui_item_access_target", "desk:access", "desk")
    _effect(raw, "desk", "listener", "quest:claim")
    raw.execute("INSERT INTO ScriptedActivators VALUES ('planning', 'desk', NULL)")
    rune = Atom("planning_slot_item", "item:rune", "PlanarFern")

    gates = apply_hierarchy_activity(
        raw, conn, [Gate("object", "portal", "activation:planning", ((rune,),), controller_source_key="planning")]
    )

    claim = Atom("quest_done", "quest:claim")
    assert _groups(gates, "zone_line", "zoneline:raid") == {frozenset({claim, rune})}
    assert _groups(gates, "ui_item_access_target", "desk:access") == {frozenset({claim})}


def test_furnished_room_descendant_needs_the_furniture_and_claimed_desk_host(databases):
    raw, conn = databases
    _object(raw, "claim-listener")
    _object(raw, "desk", active=False)
    _object(raw, "furnishing", active=False)
    _object(raw, "vendor", parent="furnishing")
    _subject(raw, conn, "character", "character:furnished-vendor", "vendor")
    _effect(raw, "desk", "claim-listener", "quest:claim")
    conn.execute(
        "INSERT INTO items (stable_key, display_name, image_name, furniture_set, equipment_to_activate)"
        " VALUES ('item:stone-set', 'Stone Furniture', '', 1, 'StoneRoom')"
    )
    raw.execute("INSERT INTO PlanningTableFurnishings VALUES ('furnishing', 'desk', 'L1', 'StoneRoom')")

    gates = apply_hierarchy_activity(raw, conn, [])

    assert _groups(gates, "character", "character:furnished-vendor") == {
        frozenset({Atom("quest_done", "quest:claim"), Atom("room_furnished", "item:stone-set", "L1")})
    }


def test_controller_spawn_inherits_the_host_spawn_quest(databases):
    raw, conn = databases
    _object(raw, "fight")
    _subject(raw, conn, "spawn_point", "spawn:twisted", "fight")
    conn.execute(
        "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene)"
        " VALUES ('character:fallen', 'spawn:phase', 'Scene')"
    )
    raw.execute("INSERT INTO DynamicCharacterSpawns VALUES ('spawn:phase', 'character:fallen', 'fight', 1)")
    quest = Atom("quest_done", "quest:dyingwish4")

    gates = apply_hierarchy_activity(raw, conn, [Gate("spawn_point", "spawn:twisted", "spawn_start", ((quest,),))])

    assert _groups(gates, "spawn_point", "spawn:phase") == {frozenset({quest})}


def test_a_disable_keeps_its_inverse_and_its_controller_host(databases):
    raw, conn = databases
    _object(raw, "listener")
    _object(raw, "inactive-listener", active=False)
    _object(raw, "target")
    _subject(raw, conn, "character", "character:target", "target")
    _effect(raw, "target", "listener", "quest:remove", effect="disable")
    _effect(raw, "target", "inactive-listener", "quest:unreachable", effect="disable")

    gates = apply_hierarchy_activity(raw, conn, [])

    assert _groups(gates, "character", "character:target") == {frozenset({Atom("quest_not_done", "quest:remove")})}


@pytest.mark.parametrize("active,component", [(False, True), (True, False), (False, False)])
def test_a_starting_inactive_placement_without_an_activator_is_never_available(databases, active, component):
    raw, conn = databases
    _object(raw, "inactive", active=active)
    _subject(raw, conn, "spawn_point", "spawn:unused", "inactive", component=component)

    gates = apply_hierarchy_activity(raw, conn, [])

    assert _groups(gates, "spawn_point", "spawn:unused") == {frozenset({Atom("never", "inactive")})}


def test_an_active_subject_does_not_need_an_optional_activator(databases):
    raw, conn = databases
    _object(raw, "listener")
    _object(raw, "target")
    _subject(raw, conn, "character", "character:target", "target")
    _effect(raw, "target", "listener", "quest:optional")
    assert apply_hierarchy_activity(raw, conn, []) == []


def test_an_inactive_controller_cannot_activate_its_own_parent(databases):
    raw, conn = databases
    _object(raw, "root", active=False)
    _object(raw, "listener", parent="root")
    _subject(raw, conn, "character", "character:target", "root")
    _effect(raw, "root", "listener", "quest:cycle")
    gates = apply_hierarchy_activity(raw, conn, [])
    assert _groups(gates, "character", "character:target") == {frozenset({Atom("never", "root")})}


@pytest.mark.parametrize("rule", ["astra_deaths", "stowaway_deaths"])
def test_death_effect_needs_every_member_of_its_exported_set(databases, rule):
    raw, conn = databases
    _object(raw, "controller")
    raw.execute("INSERT INTO ScriptedActivators VALUES ('source', 'controller', NULL)")
    victims = ["character:first", "character:second"]
    for index, character in enumerate(victims):
        _object(raw, "victim" + str(index), scene=False)
        _subject(raw, conn, "character", character, "victim" + str(index))
    if rule == "astra_deaths":
        for index, character in enumerate(victims):
            raw.execute(
                "INSERT INTO ScriptedActivatorReferences VALUES (?, 'source', 'StarSpawns', 'spawn_point', ?)",
                (str(index), "spawn:star" + str(index)),
            )
            raw.execute("INSERT INTO SpawnPointCharacters VALUES (?, ?)", ("spawn:star" + str(index), character))
        raw.execute(
            "INSERT INTO ScriptedActivatorReferences"
            " VALUES ('dragon', 'source', 'Dragon', 'character', 'character:born')"
        )
        raw.execute("INSERT INTO DynamicCharacterSpawns VALUES ('spawn:born', 'character:born', 'controller', 1)")
        conn.execute(
            "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene)"
            " VALUES ('character:born', 'spawn:born', 'Scene')"
        )
    else:
        for index, character in enumerate(victims):
            raw.execute(
                "INSERT INTO ScriptedActivatorReferences VALUES (?, 'source', '$checkin_character', 'character', ?)",
                (str(index), character),
            )
        _object(raw, "keeper", active=False)
        _subject(raw, conn, "spawn_point", "spawn:born", "keeper")
        raw.execute(
            "INSERT INTO ScriptedActivatorReferences VALUES ('keeper', 'source', 'KeeperSpawn', 'object', 'keeper')"
        )
        raw.execute("INSERT INTO ScriptedActivatorTargets VALUES ('keeper', 'enable', 'object', 'keeper')")

    triggers = _death_trigger_gates(raw, conn, "source", rule)
    gates = apply_hierarchy_activity(raw, conn, triggers)

    assert _groups(gates, "spawn_point", "spawn:born") == {frozenset(Atom("encounter_won", key) for key in victims)}


def test_missing_death_trigger_set_fails_instead_of_publishing_an_ungated_spawn(databases):
    raw, conn = databases
    with pytest.raises(ValueError, match="Missing death trigger spawns"):
        _death_trigger_gates(raw, conn, "source", "astra_deaths")


def test_hierarchy_missing_an_ancestor_fails_closed(databases):
    raw, conn = databases
    _object(raw, "leaf", parent="missing")
    with pytest.raises(ValueError, match="lacks ancestor"):
        apply_hierarchy_activity(raw, conn, [])


def test_disabled_character_behaviour_on_an_active_object_is_not_an_inactive_placement(databases):
    raw, conn = databases
    _object(raw, "npc")
    _subject(raw, conn, "character", "character:called-externally", "npc", component=False)
    assert apply_hierarchy_activity(raw, conn, []) == []


def test_a_listener_can_remove_its_own_host_after_the_quest(databases):
    raw, conn = databases
    _object(raw, "gate")
    _subject(raw, conn, "zone_line", "zoneline:gate", "gate")
    _effect(raw, "gate", "gate", "quest:claim", effect="disable")

    gates = apply_hierarchy_activity(raw, conn, [])

    assert _groups(gates, "zone_line", "zoneline:gate") == {frozenset({Atom("quest_not_done", "quest:claim")})}
