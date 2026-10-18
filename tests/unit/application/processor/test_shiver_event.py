"""ShiverEvent phases and its serialized parent/subquest checklist."""

from __future__ import annotations

import json
import sqlite3
from itertools import combinations
from typing import TYPE_CHECKING

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.edge_builder import (
    _add_quest_acquisition_edges,
    _add_quest_chain_edges,
    _add_quest_completion_edges,
    _add_quest_dialog_prerequisite_edges,
    _add_quest_step_edges,
)
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.mod_writer import serialize_mod_guide
from erenshor.application.guide.node_builder import _add_quest_nodes
from erenshor.application.guide.schema import EdgeType, Node, NodeType
from erenshor.application.processor.gates import SHIVER_KEEPER_QUESTS, SHIVER_MEET_ALL, process_gates
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

_TORCH = "quest:shiver-torch"
_FLAME = "quest:shiver-flamelit"
_LIGHTHOUSE = "quest:shiver-lighthousechange"
_GLASSES = "quest:shiver-glasses"
_FIRST = "character:initial-lightkeeper:placed-copy"
_KIO = "character:later-lightkeeper:placed-copy"
_HIDER = "character:hidden-guest:placed-copy"
_KEEPERS = tuple(f"character:keeper-copy-{index}" for index in range(4))
_TRIGGER = "trigger:shiver:position:0"


@pytest.fixture
def event(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    conn = writer.conn
    quests = (*SHIVER_KEEPER_QUESTS, SHIVER_MEET_ALL, _TORCH, _FLAME, _LIGHTHOUSE, _GLASSES, "quest:shiver-hider")
    conn.executemany(
        "INSERT INTO quests (stable_key, db_name, display_name, image_name) VALUES (?, ?, ?, ?)",
        [(key, key.removeprefix("quest:").upper(), key, key) for key in quests],
    )
    conn.execute("UPDATE quests SET display_name = 'Meet Shivering Step' WHERE stable_key = ?", (SHIVER_MEET_ALL,))
    conn.execute(
        "INSERT INTO zones (stable_key,scene_name,zone_name,display_name,image_name,zone_type)"
        " VALUES ('zone:event','EventScene','Shivering Step','Shivering Step','event','Event')"
    )
    characters = (
        *_KEEPERS,
        _FIRST,
        _KIO,
        _HIDER,
        "character:phantom-copy",
        "character:warm-flame-copy",
        "character:trigger-mob",
    )
    conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        [(key, key, key) for key in characters],
    )
    conn.execute(
        "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene)"
        " VALUES (?, ?, 'EventScene')",
        ("character:trigger-mob", _TRIGGER),
    )
    conn.executemany(
        "INSERT INTO quest_completion_sources VALUES (?, 'talk', 'character', ?, NULL)",
        list(zip(SHIVER_KEEPER_QUESTS, _KEEPERS, strict=True)),
    )
    conn.execute(
        "INSERT INTO quest_completion_sources VALUES ('quest:shiver-hider', 'talk', 'character', ?, NULL)", (_HIDER,)
    )
    conn.executemany(
        "INSERT INTO character_dialogs (character_stable_key, dialog_index, keywords, complete_quest_stable_key)"
        " VALUES (?, 0, 'HELLO', ?)",
        list(zip(_KEEPERS, SHIVER_KEEPER_QUESTS, strict=True)),
    )
    conn.execute(
        "INSERT INTO quest_completion_sources VALUES (?, 'scripted', 'scripted', NULL, 'speak to keepers')",
        (SHIVER_MEET_ALL,),
    )
    conn.execute(
        "INSERT INTO quest_acquisition_sources VALUES (?, 'scripted', 'scripted', NULL, NULL)", (SHIVER_MEET_ALL,)
    )
    raw = sqlite3.connect(":memory:")
    raw.executescript(
        """
        CREATE TABLE ObjectHierarchy (
            ObjectKey TEXT PRIMARY KEY, ParentObjectKey TEXT, ActiveSelf INTEGER, IsSceneObject INTEGER
        );
        INSERT INTO ObjectHierarchy VALUES ('object:event', NULL, 1, 1);
        CREATE TABLE QuestActivationEffects (
            TargetKind TEXT, TargetStableKey TEXT, Effect TEXT, ListenerKey TEXT,
            GroupIndex INTEGER, AtomKind TEXT, AtomStableKey TEXT,
            TargetObjectKey TEXT, ListenerObjectKey TEXT, ListenerComponentIsEnabled INTEGER
        );
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, SourceScene TEXT, ComponentIsEnabled INTEGER,
            ObjectKey TEXT, HostCharacterStableKey TEXT
        );
        CREATE TABLE ScriptedActivatorReferences (ReferenceId TEXT, SourceKey TEXT, Field TEXT);
        CREATE TABLE ScriptedActivatorTargets (ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT);
        INSERT INTO ScriptedActivators VALUES (
            'source:event', 'shiver_event', 'EventScene', 1, 'object:event', NULL
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
    for table in (
        "Characters",
        "SpawnPoints",
        "SpawnPointTriggers",
        "ZoneLines",
        "ItemBags",
        "Doors",
        "UiItemAccessTargets",
    ):
        raw.execute(f"CREATE TABLE {table} (StableKey TEXT, ObjectKey TEXT, ComponentIsEnabled INTEGER)")
    raw.execute("ALTER TABLE SpawnPoints ADD COLUMN IsDirectlyPlaced INTEGER DEFAULT 0")
    for table, keys in (("Characters", characters), ("SpawnPointTriggers", (_TRIGGER,))):
        for key in keys:
            raw.execute(
                "INSERT INTO ObjectHierarchy VALUES (?, 'object:event', 1, 1)",
                (f"object:{key}",),
            )
            raw.execute(f"INSERT INTO {table} VALUES (?, ?, 1)", (key, f"object:{key}"))
    targets = [
        ("FirstKio", "character", _FIRST),
        ("Kio", "character", _KIO),
        *(("WelcomeCrew", "character", key) for key in _KEEPERS),
        ("Hider", "character", _HIDER),
        ("SpawnTriggers", "spawn_point", _TRIGGER),
        ("Phantom", "character", "character:phantom-copy"),
        ("WarmFlame", "character", "character:warm-flame-copy"),
    ]
    for index, (field, kind, key) in enumerate(targets):
        ref = f"ref:{index}"
        raw.execute("INSERT INTO ScriptedActivatorReferences VALUES (?, 'source:event', ?)", (ref, field))
        raw.executemany(
            "INSERT INTO ScriptedActivatorTargets VALUES (?, ?, ?, ?)",
            [(ref, mode, kind, key) for mode in ("enable", "disable")],
        )
    barriers = tmp_path / "barriers.toml"
    barriers.write_text("", encoding="utf-8")
    process_gates(raw, writer, barriers)
    raw.close()
    return writer


def _available(event: Writer, kind: str, subject: str, completed: set[str]) -> bool:
    gates: dict[str, dict[int, list[bool]]] = {}
    for gate, group, atom, key in event.conn.execute(
        "SELECT gate, group_index, atom_kind, atom_stable_key FROM gate_conditions"
        " WHERE subject_kind = ? AND subject_stable_key = ?",
        (kind, subject),
    ):
        assert atom in {"quest_done", "quest_not_done"}
        satisfied = key in completed if atom == "quest_done" else key not in completed
        gates.setdefault(gate, {}).setdefault(group, []).append(satisfied)
    return all(any(all(atoms) for atoms in groups.values()) for groups in gates.values())


@pytest.mark.parametrize(
    "completed",
    [set(quests) for size in range(4) for quests in combinations(SHIVER_KEEPER_QUESTS, size)],
)
def test_any_unfinished_keeper_retains_first_kio_and_welcome_crew(event: Writer, completed: set[str]) -> None:
    assert _available(event, "character", _FIRST, completed)
    assert not _available(event, "character", _KIO, completed)
    assert all(_available(event, "character", key, completed) for key in _KEEPERS)


@pytest.mark.parametrize(
    ("later", "kio", "hider", "triggers", "warm_flame"),
    [
        (set(), True, False, False, False),
        ({_TORCH}, True, True, True, False),
        ({_TORCH, _FLAME}, True, False, True, True),
        ({_TORCH, _FLAME, _LIGHTHOUSE}, False, False, True, True),
    ],
)
def test_phase_transitions(
    event: Writer, later: set[str], kio: bool, hider: bool, triggers: bool, warm_flame: bool
) -> None:
    completed = set(SHIVER_KEEPER_QUESTS) | later
    assert not _available(event, "character", _FIRST, completed)
    assert not any(_available(event, "character", key, completed) for key in _KEEPERS)
    assert _available(event, "character", _KIO, completed) == kio
    assert _available(event, "character", _HIDER, completed) == hider
    assert _available(event, "spawn_point", _TRIGGER, completed) == triggers
    assert _available(event, "character", "character:warm-flame-copy", completed) == warm_flame
    # The rule belongs to the trigger placement, not every copy of its mob.
    assert _available(event, "character", "character:trigger-mob", completed)
    assert (
        event.conn.execute("SELECT count(*) FROM gate_conditions WHERE subject_stable_key = ?", (_TRIGGER,)).fetchone()[
            0
        ]
        == 1
    )


def test_phantom_requires_glasses_independently_of_other_phases(event: Writer) -> None:
    assert not _available(event, "character", "character:phantom-copy", set(SHIVER_KEEPER_QUESTS) | {_TORCH, _FLAME})
    assert _available(event, "character", "character:phantom-copy", {_GLASSES})


def test_serialized_parent_keeps_four_conversation_subquests_as_completion_steps(event: Writer) -> None:
    conn = event.conn
    conn.row_factory = sqlite3.Row
    graph = EntityGraph()
    _add_quest_nodes(conn, graph)
    for row in conn.execute("SELECT stable_key, display_name FROM characters"):
        graph.add_node(Node(row["stable_key"], NodeType.CHARACTER, row["display_name"]))
    graph.add_node(Node("zone:event", NodeType.ZONE, "Shivering Step", scene="EventScene"))
    _add_quest_acquisition_edges(conn, graph)
    _add_quest_completion_edges(conn, graph)
    _add_quest_step_edges(conn, graph)
    _add_quest_dialog_prerequisite_edges(conn, graph)
    _add_quest_chain_edges(conn, graph)
    graph.build_indexes()
    assert not graph.out_edges(SHIVER_MEET_ALL, EdgeType.REQUIRES_QUEST)
    payload = json.loads(serialize_mod_guide(graph, compile_graph(graph)))
    entries = {quest["stable_key"]: quest for quest in payload["quests"]}
    parent = entries[SHIVER_MEET_ALL]
    assert parent["acquisition"] == [
        {
            "method": "zone_entry",
            "source_name": "Shivering Step",
            "source_type": "zone",
            "source_stable_key": "zone:event",
        }
    ]
    assert not parent.get("prerequisites")
    assert {step["target_key"] for step in parent["steps"]} == set(SHIVER_KEEPER_QUESTS)
    assert len(parent["steps"]) == 4
    assert all(step["action"] == "complete_quest" and "or_group" not in step for step in parent["steps"])
    assert {source["source_stable_key"] for source in parent["completion"]} == set(SHIVER_KEEPER_QUESTS)
    assert all("or_group" not in source for source in parent["completion"])
    for quest, character in zip(SHIVER_KEEPER_QUESTS, _KEEPERS, strict=True):
        assert [(step["action"], step["target_key"], step["keyword"]) for step in entries[quest]["steps"]] == [
            ("talk", character, "HELLO")
        ]
    hider = entries["quest:shiver-hider"]
    assert "note" not in hider["acquisition"][0]
    assert len(hider["steps"]) == 1
    assert hider["steps"][0]["action"] == "talk"
    assert hider["steps"][0]["target_key"] == _HIDER
    assert hider["steps"][0]["description"] == (
        f"Speak to {_HIDER}. Wait for darkness, which begins ten seconds after completing The Shivering Torch."
    )
    assert any(edge.target == _TORCH for edge in graph.out_edges(SHIVER_MEET_ALL, EdgeType.CHAINS_TO))
