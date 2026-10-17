"""Zone-wide eligibility keeps pool weights and unknown runtime prerequisites."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from erenshor.application.processor.writer import Writer
from erenshor.application.processor.zone_wide_spawns import SPECTRE_RULE, process_zone_wide_spawns

_FACTS = (
    "spectres.entry_delay_start",
    "spectres.entry_attempt",
    "spectres.single_entry_call",
    "spectres.roll",
    "spectres.spawn_selection",
    "spectres.recent_zones",
    "spectres.cosmetic_slots",
    "spectres.spawn_point_registration",
)
_EXCLUDED = ("Azure", "Stowaway", "Tutorial", "SummerEvent", "ShiveringStep", "ShiveringTomb", "ShiveringTomb2")


@pytest.fixture
def databases(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Writer]]:
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE ZoneWideSpawnCandidates (RuleId TEXT, Slot INTEGER, CharacterStableKey TEXT);
        CREATE TABLE CosmeticItems (ItemStableKey TEXT, Field TEXT);
        CREATE TABLE SpawnPoints (Scene TEXT, IsEnabled INTEGER);
        CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT);
    """)
    raw.executemany("INSERT INTO code_facts VALUES (?, 'ok', 'true')", ((fact,) for fact in _FACTS))
    raw.execute("INSERT INTO CosmeticItems VALUES ('item:lens', 'WatchersLens')")
    pool = [
        "character:a",
        "character:b",
        "character:c",
        "character:d",
        "character:rare",
        "character:a",
        "character:b",
        "character:c",
        "character:d",
    ]
    raw.executemany(
        "INSERT INTO ZoneWideSpawnCandidates VALUES (?, ?, ?)",
        ((SPECTRE_RULE, slot, key) for slot, key in enumerate(pool)),
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.conn.execute("INSERT INTO items (stable_key, display_name, image_name) VALUES ('item:lens', 'Lens', '')")
    writer.conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player) "
        "VALUES (?, ?, '', 'enemy', 0)",
        ((key, key) for key in sorted(set(pool))),
    )
    scenes = (*_EXCLUDED, "Valid", "DisabledOnly", "NoPoints")
    writer.conn.executemany(
        "INSERT INTO zones (stable_key,scene_name,zone_name,display_name,image_name,zone_type)"
        " VALUES (?, ?, ?, ?, '', 'Outdoor')",
        ((f"zone:{scene}", scene, scene, scene) for scene in scenes),
    )
    raw.executemany("INSERT INTO SpawnPoints VALUES (?, 1)", ((scene,) for scene in (*_EXCLUDED, "Valid")))
    raw.execute("INSERT INTO SpawnPoints VALUES ('Valid', 0)")
    raw.execute("INSERT INTO SpawnPoints VALUES ('DisabledOnly', 0)")
    writer.conn.commit()
    yield raw, writer
    raw.close()
    writer.conn.close()


def test_nine_slots_keep_four_double_weights_and_one_single(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    rows = writer.conn.execute(
        "SELECT character_stable_key, weight, total_weight "
        "FROM zone_wide_spawn_candidates ORDER BY character_stable_key"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("character:a", 2, 9),
        ("character:b", 2, 9),
        ("character:c", 2, 9),
        ("character:d", 2, 9),
        ("character:rare", 1, 9),
    ]
    assert writer.conn.execute("SELECT COUNT(*) FROM character_spawns").fetchone()[0] == 0
    assert writer.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_zone_wide_characters_are_known_without_placed_markers(
    databases: tuple[sqlite3.Connection, Writer],
) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    assert writer.conn.execute("SELECT COUNT(*) FROM characters_in_game").fetchone()[0] == 5
    assert writer.conn.execute("SELECT COUNT(*) FROM map_character_spawns").fetchone()[0] == 0
    writer.conn.execute("DELETE FROM zone_wide_spawn_zones")
    assert writer.conn.execute("SELECT COUNT(*) FROM characters_in_game").fetchone()[0] == 0


def test_ten_percent_roll_and_weighted_selection_are_distinct(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    chances = dict(
        writer.conn.execute("""
        SELECT character_stable_key, attempt_probability * weight / total_weight
        FROM zone_wide_spawn_candidates JOIN zone_wide_spawn_rules USING (rule_id)
    """)
    )
    assert chances["character:a"] == pytest.approx(1 / 45)
    assert chances["character:rare"] == pytest.approx(1 / 90)
    assert sum(chances.values()) == pytest.approx(0.1)


def test_excluded_scenes_and_missing_points_are_not_eligible(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    eligible = dict(
        writer.conn.execute("SELECT zone_stable_key, authored_spawn_point_count FROM zone_wide_spawn_zones")
    )
    assert eligible == {"zone:Valid": 2, "zone:DisabledOnly": 1}
    assert raw.execute("SELECT COUNT(*) FROM SpawnPoints WHERE Scene = 'Azure'").fetchone()[0] == 1
    assert {f"zone:{scene}" for scene in _EXCLUDED}.isdisjoint(eligible)
    assert "zone:NoPoints" not in eligible


def test_disabled_points_are_potential_not_fabricated_runtime_state(
    databases: tuple[sqlite3.Connection, Writer],
) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    enabled = dict(writer.conn.execute("SELECT zone_stable_key, enabled_spawn_point_count FROM zone_wide_spawn_zones"))
    assert enabled == {"zone:Valid": 1, "zone:DisabledOnly": 0}
    rule = writer.conn.execute("SELECT * FROM zone_wide_spawn_rules").fetchone()
    assert rule["requires_registered_spawn_point"] == 1
    assert "is_available" not in dict(rule)
    columns = {row[1] for row in writer.conn.execute("PRAGMA table_info(zone_wide_spawn_zones)")}
    assert columns.isdisjoint({"x", "y", "z", "spawn_point_stable_key"})


def test_lens_prerequisite_uses_exported_item_not_a_name_override(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    rule = writer.conn.execute("SELECT * FROM zone_wide_spawn_rules").fetchone()
    assert rule["required_cosmetic_item_stable_key"] == "item:lens"
    assert rule["recent_successful_zone_limit"] == 5
    assert rule["max_attempts_per_entry"] == 1


@pytest.mark.parametrize("deltas, expected", [([0.1] * 100, 1), ([0.2] * 100, 1), ([1 / 6] * 100, 0)])
def test_entry_timer_contract_does_not_repeat_attempts(
    databases: tuple[sqlite3.Connection, Writer], deltas: list[float], expected: int
) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    rule = writer.conn.execute("SELECT * FROM zone_wide_spawn_rules").fetchone()
    assert rule["attempt_trigger"] == "entry_timer_crosses_below_zero"
    remaining = rule["entry_delay_ticks"]
    attempts = 0
    for delta in deltas:
        if remaining > 0:
            remaining -= rule["entry_delay_ticks_per_second"] * delta
            if remaining < 0:
                attempts += 1
    assert attempts == expected
    assert attempts <= rule["max_attempts_per_entry"]


def test_recent_successes_expire_after_five_other_scenes(databases: tuple[sqlite3.Connection, Writer]) -> None:
    raw, writer = databases
    process_zone_wide_spawns(raw, writer)
    limit = writer.conn.execute("SELECT recent_successful_zone_limit FROM zone_wide_spawn_rules").fetchone()[0]
    history: list[str] = []
    for scene in ("A", "B", "C", "D", "E"):
        history.append(scene)
    assert "A" in history
    history.append("F")
    if len(history) > limit:
        history.pop(0)
    assert history == ["B", "C", "D", "E", "F"]
    assert "A" not in history


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("DELETE FROM CosmeticItems", "one exported WatchersLens"),
        ("UPDATE CosmeticItems SET ItemStableKey = 'item:missing'", "unknown item"),
        ("INSERT INTO CosmeticItems VALUES ('item:lens', 'WatchersLens')", "one exported WatchersLens"),
        ("UPDATE ZoneWideSpawnCandidates SET Slot = 9 WHERE Slot = 8", "unique and contiguous"),
        ("UPDATE ZoneWideSpawnCandidates SET Slot = 7 WHERE Slot = 8", "unique and contiguous"),
        (
            "UPDATE ZoneWideSpawnCandidates SET CharacterStableKey = 'character:missing' WHERE Slot = 0",
            "Unknown zone-wide",
        ),
        ("UPDATE ZoneWideSpawnCandidates SET RuleId = 'unknown' WHERE Slot = 0", "candidate pool"),
        ("DELETE FROM ZoneWideSpawnCandidates", "candidate pool"),
        ("DELETE FROM code_facts WHERE fact_id = 'spectres.entry_attempt'", "facts missing"),
    ],
)
def test_incomplete_raw_contract_fails_closed(
    databases: tuple[sqlite3.Connection, Writer], mutation: str, message: str
) -> None:
    raw, writer = databases
    raw.execute(mutation)
    with pytest.raises(ValueError, match=message):
        process_zone_wide_spawns(raw, writer)
    assert writer.conn.execute("SELECT COUNT(*) FROM zone_wide_spawn_rules").fetchone()[0] == 0


def test_lifecycle_facts_pin_the_actual_branch_not_just_its_name() -> None:
    specs_path = Path(__file__).resolve().parents[4] / "src/tools/CodeFacts/specs/erenshor-facts.json"
    specs = {fact["id"]: fact for fact in json.loads(specs_path.read_text())["facts"]}
    assert set(_FACTS) <= specs.keys()
    branch = specs["spectres.entry_attempt"]["args"]["shape"]
    assert branch.startswith("if (SivakSpectreDly > 0f)")
    assert "SivakSpectreDly < 0f" in branch
    assert "HasCosmetic (GameData.PlayerInv.WatchersLens)" in branch
    assert "!GameData.SivakayanSpawnedZones.Contains" in branch
    assert branch.count("SpawnSivakayanSpecter ();") == 1
    assert specs["spectres.single_entry_call"]["args"] == {"statement": "SpawnSivakayanSpecter ();", "count": "1"}
    assert all(f'name != "{scene}"' in branch for scene in _EXCLUDED)
    assert "CosmeticSlots" in specs["spectres.cosmetic_slots"]["args"]["shape"]
    selection = specs["spectres.spawn_selection"]["args"]["shape"]
    assert "SpawnPointsInScene.Count > 0" in selection
    assert selection.index("Object.Instantiate") < selection.index("GameData.AddSivakayanSpawn")
