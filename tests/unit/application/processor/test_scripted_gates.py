"""Scripted guidance follows exact exported placements and release branches."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.gates import Atom, Gate, _scripted_gates, _validate_atoms, process_gates
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def writer(tmp_path: Path) -> Iterator[Writer]:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    yield writer
    writer.conn.close()


@pytest.fixture
def databases(writer: Writer) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    raw = sqlite3.connect(":memory:")
    raw.executescript(
        """
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT PRIMARY KEY, RuleId TEXT, ComponentIsEnabled INTEGER,
            IsEnabled INTEGER, HostCharacterStableKey TEXT, SourceScene TEXT, SourceObjectName TEXT,
            ObjectKey TEXT
        );
        CREATE TABLE ScriptedActivatorReferences (
            ReferenceId TEXT PRIMARY KEY, SourceKey TEXT, Field TEXT, ReferenceKind TEXT,
            ReferenceKey TEXT, BoolValue INTEGER
        );
        CREATE TABLE ScriptedActivatorTargets (
            ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT
        );
        CREATE TABLE SpawnPointCharacters (SpawnPointStableKey TEXT, CharacterStableKey TEXT);
        CREATE TABLE SpawnPointEssentialLinks (
            SourceSpawnPointStableKey TEXT, EssentialSpawnPointStableKey TEXT
        );
        CREATE TABLE ArenaRounds (
            StableKey TEXT, Scene TEXT, ArenaObjectName TEXT, RoundIndex INTEGER
        );
        CREATE TABLE ArenaRoundEnemies (ArenaRoundStableKey TEXT, EnemyCharacterStableKey TEXT);
        CREATE TABLE QuestActivationEffects (
            TargetKind TEXT, TargetStableKey TEXT, Effect TEXT, ListenerKey TEXT,
            GroupIndex INTEGER, AtomKind TEXT, AtomStableKey TEXT,
            TargetObjectKey TEXT, ListenerObjectKey TEXT, ListenerComponentIsEnabled INTEGER
        );
        CREATE TABLE ObjectHierarchy (
            ObjectKey TEXT PRIMARY KEY, ParentObjectKey TEXT, ActiveSelf INTEGER, IsSceneObject INTEGER
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
    yield raw, writer.conn
    raw.close()


def _source(
    raw: sqlite3.Connection,
    source: str,
    rule: str,
    *,
    host: str | None = None,
    enabled: bool = True,
    active: bool = False,
    scene: str | None = "Scene",
    object_name: str = "Controller",
) -> None:
    raw.execute(
        "INSERT INTO ScriptedActivators VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (source, rule, int(enabled), int(active), host, scene, object_name, f"object:{source}"),
    )
    raw.execute("INSERT INTO ObjectHierarchy VALUES (?, NULL, 1, ?)", (f"object:{source}", int(scene is not None)))


def _reference(
    raw: sqlite3.Connection,
    source: str,
    field: str,
    kind: str,
    key: str | None,
    *,
    flag: bool | None = None,
) -> str:
    reference = f"{source}:field:{field}"
    raw.execute(
        "INSERT INTO ScriptedActivatorReferences VALUES (?, ?, ?, ?, ?, ?)",
        (reference, source, field, kind, key, None if flag is None else int(flag)),
    )
    return reference


def _target(
    raw: sqlite3.Connection,
    source: str,
    field: str,
    kind: str,
    key: str,
    *,
    mode: str = "enable",
) -> None:
    reference = f"{source}:field:{field}"
    if raw.execute("SELECT 1 FROM ScriptedActivatorReferences WHERE ReferenceId = ?", (reference,)).fetchone() is None:
        _reference(raw, source, field, "object", f"object:{field}")
    raw.execute("INSERT INTO ScriptedActivatorTargets VALUES (?, ?, ?, ?)", (reference, mode, kind, key))


def _character(conn: sqlite3.Connection, key: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO characters"
        " (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        (key, key, key),
    )


def _spawn(raw: sqlite3.Connection, conn: sqlite3.Connection, spawn: str, *characters: str) -> None:
    for character in characters:
        _character(conn, character)
        raw.execute("INSERT INTO SpawnPointCharacters VALUES (?, ?)", (spawn, character))
        conn.execute(
            "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene) VALUES (?, ?, 'Scene')",
            (character, spawn),
        )


def _release(
    conn: sqlite3.Connection,
    character: str,
    mechanism: str,
    source: str,
    conditions: list[tuple[str, str]],
    *,
    feasible: bool = True,
    enabled: bool = True,
) -> None:
    conn.executemany(
        "INSERT INTO character_damage_releases VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(character, mechanism, source, kind, key, int(feasible), int(enabled)) for kind, key in conditions],
    )


def _groups(gate: Gate) -> set[frozenset[Atom]]:
    return {frozenset(group) for group in gate.groups}


def _encounters(*characters: str) -> frozenset[Atom]:
    return frozenset(Atom("encounter_won", key) for key in characters)


@pytest.mark.parametrize(
    ("rule", "reveal_field", "spawn_field"),
    [
        ("restored_fernalla", "RestoredFernalla", "FernSpawnPoint"),
        ("restored_soluna", "RestoredSoluna", "SolunaSpawn"),
        ("restored_brax", "GodBraxRestored", "BraxSpawn"),
    ],
)
def test_restored_god_uses_exact_reveal_and_spawn_references(
    databases: tuple[sqlite3.Connection, sqlite3.Connection], rule: str, reveal_field: str, spawn_field: str
) -> None:
    raw, conn = databases
    source = "object:scene:fight[1]:script:Fight:0"
    _source(raw, source, rule)
    _spawn(raw, conn, "spawn:scene:boss", "character:actual boss")
    _spawn(raw, conn, "spawn:scene:other", "character:other boss")
    _character(conn, "character:restored:scene:1")
    _character(conn, "character:restored:scene:2")
    _reference(raw, source, spawn_field, "spawn_point", "spawn:scene:boss")
    _target(raw, source, reveal_field, "character", "character:restored:scene:1")
    _target(raw, source, reveal_field, "character", "character:restored:scene:2", mode="disable")

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert gates[0].subject_stable_key == "character:restored:scene:1"
    assert _groups(gates[0]) == {_encounters("character:actual boss")}
    assert source in gates[0].gate


def test_final_arena_round_uses_actual_enemy_not_observer_or_token(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    source = "object:scene:arena[2]:script:VithArena:0"
    _source(raw, source, "restored_vitheo", object_name="Exact arena")
    for key in ("character:restored", "character:combatant", "character:observer", "character:decoy"):
        _character(conn, key)
    _target(raw, source, "RestoredVitheo", "character", "character:restored")
    raw.executemany(
        "INSERT INTO ArenaRounds VALUES (?, ?, ?, ?)",
        [
            ("arenaround:actual:8", "Scene", "Exact arena", 8),
            ("arenaround:other:8", "Scene", "Other arena", 8),
            ("arenaround:actual:7", "Scene", "Exact arena", 7),
            ("arenaround:another-scene:8", "Another scene", "Exact arena", 8),
        ],
    )
    raw.executemany(
        "INSERT INTO ArenaRoundEnemies VALUES (?, ?)",
        [("arenaround:actual:8", "character:combatant"), ("arenaround:other:8", "character:decoy")],
    )

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert _groups(gates[0]) == {_encounters("character:combatant")}
    assert "arenaround:actual:8" in gates[0].gate
    _validate_atoms(conn, gates)


def test_missing_arena_enemy_contract_fails_instead_of_inventing_a_requirement(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    _source(raw, "controller", "restored_vitheo")
    raw.execute("INSERT INTO ArenaRounds VALUES ('arenaround:8', 'Scene', 'Controller', 8)")
    with pytest.raises(ValueError, match="Missing final arena enemies"):
        _scripted_gates(raw, conn)


def test_ward_deaths_are_and_with_or_between_proven_release_branches(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    host = "character:warded:scene:1"
    other_copy = "character:warded:scene:2"
    wards = ["character:ward:scene:1", "character:ward:scene:2", "character:alternate ward"]
    for key in (host, other_copy, *wards):
        _character(conn, key)
    for index in range(4):
        source = f"object:scene:ward-controller[{index}]"
        _source(raw, source, "shivering_phantom_wards", host=host)
        _release(
            conn,
            host,
            "shivering_phantom_wards",
            source,
            [("character_dead", ward) for ward in (wards[:2] if index == 0 else wards[2:])],
            feasible=index != 2,
            enabled=index != 3,
        )
    conn.executemany(
        "INSERT INTO character_deduplications (group_key, member_stable_key, is_wiki_generated) VALUES (?, ?, 1)",
        [(host, host), (host, other_copy)],
    )

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert gates[0].subject_stable_key == host
    assert _groups(gates[0]) == {_encounters(*wards[:2]), _encounters(wards[2])}
    assert all(atom.kind == "encounter_won" for group in gates[0].groups for atom in group)
    _validate_atoms(conn, gates)


def test_absent_wards_are_not_fabricated_encounters(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    _character(conn, "character:host")
    _source(raw, "controller", "shivering_phantom_wards", host="character:host")
    _release(
        conn,
        "character:host",
        "shivering_phantom_wards",
        "controller",
        [("ward1_absent", ""), ("ward2_absent", "")],
    )
    assert _scripted_gates(raw, conn) == []


def test_reliquary_provenance_binds_only_its_real_host_spawn(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    source = "character:fiend:script:ReliquaryFiend:0"
    _source(raw, source, "reliquary_wards", host="character:fiend", scene=None)
    _spawn(raw, conn, "spawn:host", "character:fiend")
    _spawn(raw, conn, "spawn:separate-copy", "character:fiend")
    _spawn(raw, conn, "spawn:ward-one", "character:ward-a", "character:ward-b")
    _spawn(raw, conn, "spawn:ward-two", "character:ward-c")
    _release(
        conn,
        "character:fiend",
        "reliquary_wards",
        "spawn:host",
        [("controller", source), ("spawn_point_cleared", "spawn:ward-one"), ("spawn_point_cleared", "spawn:ward-two")],
    )

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert (gates[0].subject_kind, gates[0].subject_stable_key) == ("spawn_point", "spawn:host")
    assert _groups(gates[0]) == {
        _encounters("character:ward-a", "character:ward-c"),
        _encounters("character:ward-b", "character:ward-c"),
    }
    assert all(selector in gates[0].gate for selector in (source, "spawn:host", "spawn:ward-one", "spawn:ward-two"))
    _validate_atoms(conn, gates)


def test_repeated_ward_archetype_keeps_all_required_spawn_selectors_in_gate_identity(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    source = "character:fiend:script:ReliquaryFiend:0"
    _source(raw, source, "reliquary_wards", host="character:fiend", scene=None)
    _spawn(raw, conn, "spawn:host", "character:fiend")
    wards = [f"spawn:ward-{index}" for index in range(4)]
    for ward in wards:
        _spawn(raw, conn, ward, "character:ward")
    _release(
        conn,
        "character:fiend",
        "reliquary_wards",
        "spawn:host",
        [("controller", source), *(("spawn_point_cleared", ward) for ward in wards)],
    )

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert _groups(gates[0]) == {frozenset({Atom("encounter_won", "character:ward", quantity=4)})}
    assert all(ward in gates[0].gate for ward in wards)


def test_shout_essentials_are_character_guidance_on_the_actual_spawn_not_a_quest_gate(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    source = "character:hermit:script:NPCShoutListener:0"
    _source(raw, source, "npc_shout_essentials", host="character:hermit", scene=None)
    _reference(raw, source, "UseEssentialSpawnsToBlockThisInstance", "bool", None, flag=True)
    _reference(raw, source, "TriggerQuest", "quest", "quest:shout completes this")
    _spawn(raw, conn, "spawn:actual-hermit", "character:hermit")
    _spawn(raw, conn, "spawn:another-hermit", "character:hermit")
    _spawn(raw, conn, "spawn:essential-one", "character:choice-a", "character:choice-b")
    _spawn(raw, conn, "spawn:essential-two", "character:required")
    raw.executemany(
        "INSERT INTO SpawnPointEssentialLinks VALUES ('spawn:actual-hermit', ?)",
        [("spawn:essential-one",), ("spawn:essential-two",)],
    )

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert (gates[0].subject_kind, gates[0].subject_stable_key) == ("spawn_point", "spawn:actual-hermit")
    assert _groups(gates[0]) == {
        _encounters("character:choice-a", "character:required"),
        _encounters("character:choice-b", "character:required"),
    }
    assert "spawn:essential-one" in gates[0].gate
    _validate_atoms(conn, gates)


def test_shout_without_essential_block_does_not_gate_its_host(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    _source(raw, "controller", "npc_shout_essentials", host="character:host")
    _reference(raw, "controller", "UseEssentialSpawnsToBlockThisInstance", "bool", None, flag=False)
    _spawn(raw, conn, "spawn:host", "character:host")
    raw.execute("INSERT INTO SpawnPointEssentialLinks VALUES ('spawn:host', 'spawn:unresolved')")
    assert _scripted_gates(raw, conn) == []


def test_memory_alternatives_merge_with_quest_activation_without_gating_a_separate_copy(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
    tmp_path: Path,
    writer: Writer,
) -> None:
    raw, conn = databases
    for key in ("character:memory:scene:1", "character:memory:scene:2", "character:inactive child"):
        _character(conn, key)
        raw.execute("INSERT INTO Characters VALUES (?, ?, 1)", (key, f"object:{key}"))
        raw.execute(
            "INSERT INTO ObjectHierarchy VALUES (?, NULL, ?, 1)",
            (f"object:{key}", int(key != "character:memory:scene:1")),
        )
    conn.execute(
        "INSERT INTO quests (stable_key, db_name, display_name, image_name)"
        " VALUES ('quest:alternative', 'alternative', 'Alternative', 'alternative')"
    )
    for index in range(2):
        source = f"object:scene:sphere[{index}]"
        item = f"item:candle-{index}"
        conn.execute("INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, ?)", (item, item, item))
        _source(raw, source, "memory_sphere")
        _reference(raw, source, "RequiredInInventory", "item", item)
        _target(raw, source, "Memory", "character", "character:memory:scene:1")
        _target(raw, source, "Memory", "character", "character:inactive child", mode="disable")
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('character', 'character:memory:scene:1', 'enable', 'quest-listener', 0, 'quest_done', 'quest:alternative',"
        " 'object:character:memory:scene:1', 'object:quest-listener', 1)"
    )
    raw.execute("INSERT INTO ObjectHierarchy VALUES ('object:quest-listener', NULL, 1, 1)")
    barriers = tmp_path / "barriers.toml"
    barriers.write_text("", encoding="utf-8")

    process_gates(raw, writer, barriers)

    rows = conn.execute(
        "SELECT subject_stable_key, gate, group_index, atom_kind, atom_stable_key FROM gate_conditions"
        " ORDER BY group_index"
    ).fetchall()
    assert len(rows) == 3
    assert {row[0] for row in rows} == {"character:memory:scene:1"}
    assert len({row[1] for row in rows}) == 1
    assert {(row[3], row[4]) for row in rows} == {
        ("item_held", "item:candle-0"),
        ("item_held", "item:candle-1"),
        ("quest_done", "quest:alternative"),
    }


def test_angel_quest_uses_only_exported_host_subjects_not_unreviewed_spatial_guards(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    conn.execute("INSERT INTO zone_lines (stable_key, scene) VALUES ('zoneline:under-angel', 'Scene')")
    conn.execute("INSERT INTO zone_lines (stable_key, scene) VALUES ('zoneline:nearby', 'Scene')")
    _source(raw, "angel-controller", "shivering_angel")
    _target(raw, "angel-controller", "$host", "zone_line", "zoneline:under-angel", mode="reference")
    _source(raw, "object-only-controller", "shivering_angel")
    _target(raw, "object-only-controller", "$host", "object", "object:another-angel", mode="reference")

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert gates[0].subject_stable_key == "zoneline:under-angel"
    assert gates[0].groups == ((Atom("quest_done", "quest:standangel"),),)


def test_npc_alive_gates_only_direct_death_reveals_not_barrier_children_or_neighbours(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    raw, conn = databases
    _source(raw, "barrier-controller", "npc_alive")
    _spawn(raw, conn, "spawn:boss", "character:boss")
    _reference(raw, "barrier-controller", "SpawnPoint", "spawn_point", "spawn:boss")
    for key in ("character:revealed", "character:barrier-child", "character:nearby"):
        _character(conn, key)
    _target(raw, "barrier-controller", "DespawnIfAlive", "character", "character:revealed")
    _target(raw, "barrier-controller", "SpawnIfAlive", "object", "object:barrier")
    _target(raw, "barrier-controller", "SpawnIfAlive", "character", "character:barrier-child")

    gates = _scripted_gates(raw, conn)

    assert len(gates) == 1
    assert gates[0].subject_stable_key == "character:revealed"
    assert _groups(gates[0]) == {_encounters("character:boss")}


@pytest.mark.parametrize("rule", ["restored_brax", "memory_sphere", "shivering_angel", "npc_alive"])
def test_disabled_component_does_not_prove_a_gate(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
    rule: str,
) -> None:
    raw, conn = databases
    _source(raw, "disabled-controller", rule, enabled=False, active=True)
    assert _scripted_gates(raw, conn) == []


def test_encounter_atoms_cannot_smuggle_non_character_selectors_into_the_closed_contract(
    databases: tuple[sqlite3.Connection, sqlite3.Connection],
) -> None:
    _, conn = databases
    gate = Gate("character", "character:target", "test", ((Atom("encounter_won", "spawn:ward"),),))
    with pytest.raises(ValueError, match="unknown encounter_won"):
        _validate_atoms(conn, [gate])
