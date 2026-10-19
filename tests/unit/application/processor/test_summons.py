from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.summons import process_summons
from erenshor.application.processor.writer import Writer

_RAW = """
CREATE TABLE DynamicSpawnSummoners (ControllerObjectKey TEXT, SourceField TEXT, SummonerIndex INTEGER,
    SourceScript TEXT, Summon TEXT, SummonerKind TEXT, SummonerStableKey TEXT);
CREATE TABLE DynamicCharacterSpawns (Key TEXT, CharacterStableKey TEXT, Scene TEXT, SourceScript TEXT,
    SourceField TEXT, ControllerObjectKey TEXT);
CREATE TABLE CharacterChainedSpawns (ParentStableKey TEXT, ChildStableKey TEXT, SourceScript TEXT,
    SourceField TEXT, ControllerObjectKey TEXT);
CREATE TABLE ScriptedActivators (SourceKey TEXT, ObjectKey TEXT, RuleId TEXT);
CREATE TABLE ScriptedActivatorReferences (SourceKey TEXT, Field TEXT, ReferenceKey TEXT);
CREATE TABLE Characters (StableKey TEXT, NPCName TEXT);
"""


@pytest.fixture
def databases(tmp_path: Path) -> tuple[sqlite3.Connection, Writer]:
    raw = sqlite3.connect(":memory:")
    raw.executescript(_RAW)
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    for key in ("boss", "rare boss", "add", "frost", "inferno", "chest", "vitheo", "legion", "parent", "child"):
        _character(writer.conn, f"character:{key}")
    return raw, writer


def _character(conn: sqlite3.Connection, key: str) -> None:
    conn.execute(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        (key, key, key),
    )


def _placement(conn: sqlite3.Connection, character: str, spawn: str, *, trigger: int = 0, script: str | None = None):
    conn.execute(
        "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, scene, x, y, z,"
        " is_trigger_spawn, source_script) VALUES (?, ?, 'Arena', 1, 2, 3, ?, ?)",
        (character, spawn, trigger, script),
    )


def _dynamic(raw: sqlite3.Connection, character: str, script: str, field: str, *summoners: tuple[str, str, str | None]):
    key = f"{character}|Arena|{script}"
    raw.execute(
        "INSERT INTO DynamicCharacterSpawns VALUES (?, ?, 'Arena', ?, ?, 'object:fight')",
        (key, character, script, field),
    )
    for index, (summon, kind, summoner) in enumerate(summoners):
        raw.execute(
            "INSERT INTO DynamicSpawnSummoners VALUES ('object:fight', ?, ?, ?, ?, ?, ?)",
            (field, index, script, summon, kind, summoner),
        )
    return key


def _summons(raw: sqlite3.Connection, writer: Writer) -> set[tuple[object, ...]]:
    process_summons(raw, writer)
    return {
        tuple(row)
        for row in writer.conn.execute(
            "SELECT character_stable_key, summon, summoner_index, summoner_stable_key FROM character_summons"
        )
    }


def test_a_spawn_point_summoner_is_each_character_that_spawns_there(databases):
    raw, writer = databases
    _placement(writer.conn, "character:boss", "spawn:boss")
    _placement(writer.conn, "character:rare boss", "spawn:boss")
    key = _dynamic(raw, "character:add", "FernallaFight", "Fawn", ("alive", "spawn_point", "spawn:boss"))
    _placement(writer.conn, "character:add", key)
    assert _summons(raw, writer) == {
        ("character:add", "alive", 0, "character:boss"),
        ("character:add", "alive", 0, "character:rare boss"),
    }


def test_a_chained_child_needs_its_parent_as_its_field_says(databases):
    raw, writer = databases
    _placement(writer.conn, "character:parent", "spawn:parent")
    _placement(writer.conn, "character:child", "spawn:chained:NPCFightEvent:1:2:3", trigger=1, script="NPCFightEvent")
    raw.execute(
        "INSERT INTO CharacterChainedSpawns VALUES ('character:parent', 'character:child', 'NPCFightEvent',"
        " 'SpawnOnDeath', 'prefab-object:parent')"
    )
    raw.execute(
        "INSERT INTO DynamicSpawnSummoners VALUES ('prefab-object:parent', 'SpawnOnDeath', 0, 'NPCFightEvent',"
        " 'defeated', 'character', 'character:parent')"
    )
    assert _summons(raw, writer) == {("character:child", "defeated", 0, "character:parent")}


def _arena(writer: Writer, opener: str) -> None:
    writer.conn.execute(
        "INSERT INTO arena_rounds (stable_key, scene, round_index, coin_item_stable_key,"
        " award_chest_character_stable_key) VALUES ('arenaround:8', 'Arena', 8, 'item:coin 8', 'character:chest')"
    )
    writer.conn.execute("INSERT INTO arena_round_enemies VALUES ('arenaround:8', 0, ?)", (opener,))


def test_the_legions_need_the_vitheo_that_round_8_checks_in(databases):
    raw, writer = databases
    _arena(writer, "character:vitheo")
    raw.execute("INSERT INTO Characters VALUES ('character:vitheo', 'Vitheo the Tactician')")
    key = _dynamic(raw, "character:legion", "VitheoFight", "LegionTier1", ("alive", "checked_in", None))
    _placement(writer.conn, "character:legion", key)
    assert _summons(raw, writer) == {("character:legion", "alive", 0, "character:vitheo")}


def test_a_round_8_that_opens_with_another_fighter_checks_no_vitheo_in(databases):
    raw, writer = databases
    _arena(writer, "character:boss")
    raw.execute("INSERT INTO Characters VALUES ('character:boss', 'Honsus')")
    key = _dynamic(raw, "character:legion", "VitheoFight", "LegionTier1", ("alive", "checked_in", None))
    _placement(writer.conn, "character:legion", key)
    with pytest.raises(ValueError, match="does not open with Vitheo the Tactician"):
        process_summons(raw, writer)


def _twins(raw: sqlite3.Connection, *twins: str) -> None:
    raw.execute("INSERT INTO ScriptedActivators VALUES ('source:bridge', 'object:fight', 'twin_giants')")
    for twin in twins:
        raw.execute(
            "INSERT INTO ScriptedActivatorReferences VALUES ('source:bridge', '$checkin_character', ?)", (twin,)
        )


def test_the_bridge_chest_needs_both_twins_that_check_in(databases):
    raw, writer = databases
    _twins(raw, "character:frost", "character:inferno")
    key = _dynamic(raw, "character:chest", "RewardListener", "Chest", ("defeated", "checked_in", None))
    _placement(writer.conn, "character:chest", key)
    # Each twin is its own summoner, so the chest needs both deaths.
    assert _summons(raw, writer) == {
        ("character:chest", "defeated", 0, "character:frost"),
        ("character:chest", "defeated", 1, "character:inferno"),
    }


def test_a_bridge_with_one_twin_fails(databases):
    raw, writer = databases
    _twins(raw, "character:frost")
    key = _dynamic(raw, "character:chest", "RewardListener", "Chest", ("defeated", "checked_in", None))
    _placement(writer.conn, "character:chest", key)
    with pytest.raises(ValueError, match="two twins"):
        process_summons(raw, writer)


def test_a_dialog_summon_needs_a_dialog_that_spawns_it(databases):
    raw, writer = databases
    _placement(writer.conn, "character:parent", "spawn:parent")
    _placement(writer.conn, "character:child", "spawn:chained:NPCDialog:1:2:3", trigger=1, script="NPCDialog")
    raw.execute(
        "INSERT INTO CharacterChainedSpawns VALUES ('character:parent', 'character:child', 'NPCDialog', 'Spawn',"
        " 'prefab-object:parent')"
    )
    raw.execute(
        "INSERT INTO DynamicSpawnSummoners VALUES ('prefab-object:parent', 'Spawn', 0, 'NPCDialog', 'dialog',"
        " 'character', 'character:parent')"
    )
    with pytest.raises(ValueError, match="no dialog of character:parent spawns character:child"):
        process_summons(raw, writer)
