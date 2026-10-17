"""Authored defaults retain exact reference identity without acquiring NPC semantics."""

import sqlite3

import pytest

from erenshor.application.processor.authored_sims import process_authored_sims
from erenshor.application.processor.writer import Writer


@pytest.fixture
def databases(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE Characters (StableKey TEXT, NPCName TEXT, IsSimPlayer INTEGER);
        CREATE TABLE AuthoredSims (
            StableKey TEXT, PrefabGuid TEXT, PrefabLocalId INTEGER, PrefabPath TEXT,
            ObjectName TEXT, RawCharacterStableKey TEXT, NPCName TEXT, SeedClassName TEXT,
            SeedLevel INTEGER, SeedSkillLevel REAL, SeedIsMale INTEGER,
            SeedHairName TEXT, SeedHairColor INTEGER, SeedSkinColor INTEGER,
            IsGMCharacter INTEGER, Rival INTEGER
        );
        CREATE TABLE AuthoredSimReferences (
            SourceComponentKey TEXT, ReferenceIndex INTEGER, SourceScene TEXT,
            SourceScenePath TEXT, AuthoredSimStableKey TEXT
        );
        CREATE TABLE AuthoredSimEquipment (
            AuthoredSimStableKey TEXT, Position INTEGER, ItemStableKey TEXT
        );
        INSERT INTO Characters VALUES ('character:seed', 'Authored', 1);
        INSERT INTO Characters VALUES ('character:random', 'PoolName', 1);
        INSERT INTO AuthoredSims VALUES (
            'authored_sim:guid:100', 'guid', 100, 'Assets/seed.prefab',
            'SeedObject', 'character:seed', 'Authored', 'Reaver',
            7, 42.5, 0, 'Hair_A', 2, 3, 1, 1
        );
        INSERT INTO AuthoredSimReferences VALUES
            ('manager:1', 0, 'LoadScene', 'Assets/Scenes/LoadScene.unity', 'authored_sim:guid:100'),
            ('manager:1', 1, 'LoadScene', 'Assets/Scenes/LoadScene.unity', 'authored_sim:guid:100');
        INSERT INTO AuthoredSimEquipment VALUES
            ('authored_sim:guid:100', 0, 'item:seed'),
            ('authored_sim:guid:100', 1, NULL),
            ('authored_sim:guid:100', 2, 'item:seed');
    """)
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.insert_classes([{"class_name": "Reaver"}])
    writer.insert_items(
        [
            {
                "stable_key": "item:seed",
                "display_name": "Seed",
                "image_name": "Seed",
            }
        ]
    )
    yield raw, writer
    raw.close()
    writer.conn.close()


def test_defaults_and_references_survive_without_runtime_or_npc_facts(databases):
    raw, writer = databases
    process_authored_sims(raw, writer)
    sim = dict(writer.conn.execute("SELECT * FROM authored_sims").fetchone())
    assert sim == {
        "stable_key": "authored_sim:guid:100",
        "prefab_guid": "guid",
        "prefab_local_id": 100,
        "prefab_path": "Assets/seed.prefab",
        "object_name": "SeedObject",
        "raw_character_stable_key": "character:seed",
        "npc_name": "Authored",
        "seed_class_name": "Reaver",
        "seed_level": 7,
        "seed_skill_level": 42.5,
        "seed_is_male": 0,
        "seed_hair_name": "Hair_A",
        "seed_hair_color": 2,
        "seed_skin_color": 3,
        "is_gm_character": 1,
        "rival": 1,
    }
    assert [
        tuple(row)
        for row in writer.conn.execute("SELECT position, item_stable_key FROM authored_sim_equipment ORDER BY position")
    ] == [(0, "item:seed"), (1, None), (2, "item:seed")]
    assert writer.conn.execute("SELECT count(*) FROM authored_sim_references").fetchone()[0] == 2
    for table in ("characters", "character_spawns", "loot_drops", "character_vendor_items"):
        assert writer.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert list(writer.conn.execute("PRAGMA foreign_key_check")) == []


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("DELETE FROM AuthoredSimReferences", "distinct ActualSims reference set"),
        ("DELETE FROM AuthoredSims", "distinct ActualSims reference set"),
        ("UPDATE AuthoredSims SET PrefabLocalId = 101", "prefab reference"),
        ("UPDATE Characters SET IsSimPlayer = 0 WHERE StableKey = 'character:seed'", "raw SimPlayer"),
        ("UPDATE Characters SET NPCName = 'Wrong' WHERE StableKey = 'character:seed'", "name differs"),
        ("UPDATE AuthoredSimEquipment SET AuthoredSimStableKey = 'outside-list'", "outside ActualSims"),
    ],
)
def test_invalid_provenance_fails_instead_of_dropping_rows(databases, statement, message):
    raw, writer = databases
    raw.execute(statement)
    with pytest.raises(ValueError, match=message):
        process_authored_sims(raw, writer)


def test_missing_seed_item_is_not_silently_removed(databases):
    raw, writer = databases
    raw.execute("UPDATE AuthoredSimEquipment SET ItemStableKey = 'item:missing' WHERE Position = 0")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        process_authored_sims(raw, writer)
