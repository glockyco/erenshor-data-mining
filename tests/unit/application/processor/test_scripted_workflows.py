"""Behavioral coverage for scripted trigger workflow processor output."""

import sqlite3

import pytest

from erenshor.application.processor.characters import _optional_float, process_characters
from erenshor.application.processor.writer import Writer


@pytest.fixture
def processed_db(tmp_path):
    raw_path = tmp_path / "raw.sqlite"
    clean_path = tmp_path / "clean.sqlite"
    raw = sqlite3.connect(raw_path)
    raw.executescript(
        """
        CREATE TABLE Zones (StableKey TEXT, SceneName TEXT);
        CREATE TABLE Characters (
            StableKey TEXT PRIMARY KEY, ObjectName TEXT, NPCName TEXT,
            IsSimPlayer INTEGER, Scene TEXT, X REAL, Y REAL, Z REAL,
            IsEnabled INTEGER, IsCommon INTEGER, IsRare INTEGER, IsUnique INTEGER,
            IsFriendly INTEGER
        );
        CREATE TABLE SpawnPoints (
            StableKey TEXT, Scene TEXT, X REAL, Y REAL, Z REAL,
            IsEnabled INTEGER, IsDirectlyPlaced INTEGER, RareNPCChance INTEGER,
            LevelMod INTEGER, SpawnDelay1 REAL, SpawnDelay2 REAL, SpawnDelay3 REAL,
            SpawnDelay4 REAL, Staggerable INTEGER, StaggerMod REAL, NightSpawn INTEGER,
            PatrolPoints TEXT, LoopPatrol INTEGER, RandomWanderRange REAL,
            SpawnUponQuestCompleteStableKey TEXT, ProtectorStableKey TEXT
        );
        CREATE TABLE SpawnPointCharacters (
            SpawnPointStableKey TEXT, CharacterStableKey TEXT,
            SpawnChance REAL, IsCommon INTEGER, IsRare INTEGER
        );
        CREATE TABLE SpawnPointTriggers (
            StableKey TEXT, Scene TEXT, X REAL, Y REAL, Z REAL,
            IsEnabledByDefault INTEGER
        );
        CREATE TABLE SpawnPointTriggerCharacters (
            SpawnPointTriggerStableKey TEXT, CharacterStableKey TEXT, SpawnChance REAL
        );
        CREATE TABLE DynamicCharacterSpawns (
            Key TEXT PRIMARY KEY, CharacterStableKey TEXT, Scene TEXT,
            X REAL, Y REAL, Z REAL, SourceScript TEXT,
            EventX REAL, EventY REAL, EventZ REAL,
            TriggerItemStableKey TEXT, TriggerMode TEXT, EventDisplayName TEXT,
            TriggerBoundsCenterX REAL, TriggerBoundsCenterY REAL, TriggerBoundsCenterZ REAL,
            TriggerBoundsExtentsX REAL, TriggerBoundsExtentsY REAL, TriggerBoundsExtentsZ REAL
        );
        CREATE TABLE ArenaRounds (
            StableKey TEXT PRIMARY KEY, Scene TEXT, ArenaObjectName TEXT,
            RoundIndex INTEGER, CoinItemStableKey TEXT,
            AwardChestCharacterStableKey TEXT, TriggerMode TEXT,
            EventDisplayName TEXT, EventX REAL, EventY REAL, EventZ REAL,
            TriggerBoundsCenterX REAL, TriggerBoundsCenterY REAL, TriggerBoundsCenterZ REAL,
            TriggerBoundsExtentsX REAL, TriggerBoundsExtentsY REAL, TriggerBoundsExtentsZ REAL
        );
        CREATE TABLE ArenaRoundEnemies (
            ArenaRoundStableKey TEXT, SequenceIndex INTEGER, EnemyCharacterStableKey TEXT
        );
        CREATE TABLE LootDrops (
            CharacterStableKey TEXT, ItemStableKey TEXT, DropProbability REAL,
            ExpectedPerKill REAL, DropCountDistribution TEXT, IsActual INTEGER,
            IsGuaranteed INTEGER, IsCommon INTEGER, IsUncommon INTEGER, IsRare INTEGER,
            IsLegendary INTEGER, IsUltraRare INTEGER, IsUnique INTEGER, IsVisible INTEGER,
            Zone TEXT
        );
        CREATE TABLE CharacterDialogs (
            CharacterStableKey TEXT, DialogIndex INTEGER, DialogText TEXT, Keywords TEXT,
            GiveItemStableKey TEXT, AssignQuestStableKey TEXT, CompleteQuestStableKey TEXT,
            RepeatingQuestDialog TEXT, KillSelfOnSay INTEGER,
            RequiredQuestStableKey TEXT, SpawnCharacterStableKey TEXT
        );
        CREATE TABLE CharacterAEEvents (
            CharacterStableKey TEXT, ComponentType TEXT, TickDamage INTEGER,
            TickTime REAL, TickRange INTEGER, ResistModifier INTEGER, ResistType TEXT,
            EventHappens TEXT, DamageReason TEXT, AddEffectSpellStableKey TEXT,
            IsLifetap INTEGER, LifetapHealMod REAL, TriggerOnly INTEGER
        );
        CREATE TABLE CharacterAttackSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterBuffSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterHealSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterGroupHealSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterCCSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterTauntSpells (CharacterStableKey TEXT, SpellStableKey TEXT);
        CREATE TABLE CharacterAttackSkills (CharacterStableKey TEXT, SkillStableKey TEXT);
        CREATE TABLE CharacterVendorItems (CharacterStableKey TEXT, ItemStableKey TEXT);
        CREATE TABLE CharacterQuestManagerQuests (CharacterStableKey TEXT, QuestStableKey TEXT);
        CREATE TABLE CharacterAggressiveFactions (CharacterStableKey TEXT, FactionName TEXT);
        CREATE TABLE CharacterAlliedFactions (CharacterStableKey TEXT, FactionName TEXT);
        CREATE TABLE CharacterFactionModifiers (
            CharacterStableKey TEXT, FactionStableKey TEXT, ModifierValue REAL
        );
        CREATE TABLE CharacterDeathShouts (
            CharacterStableKey TEXT, SequenceIndex INTEGER, ShoutText TEXT
        );
        CREATE TABLE CharacterVendorQuestUnlocks (
            CharacterStableKey TEXT, QuestStableKey TEXT
        );
        CREATE TABLE SpawnPointPatrolPoints (
            SpawnPointStableKey TEXT, SequenceIndex INTEGER, X REAL, Y REAL, Z REAL
        );
        CREATE TABLE SpawnPointStopQuests (
            SpawnPointStableKey TEXT, QuestStableKey TEXT
        );
        """
    )
    raw.executemany(
        (
            "INSERT INTO Characters "
            "(StableKey, ObjectName, NPCName, IsSimPlayer, Scene, X, Y, Z, IsEnabled) "
            "VALUES (?, ?, ?, 0, ?, ?, ?, ?, 1)"
        ),
        [
            ("character:shivunax", "Shivunax", "Shivunax", "MalarothScene", None, None, None),
            ("character:demented", "Demented", "Demented", "MalarothScene", None, None, None),
            ("character:ordinary", "Ordinary", "Ordinary", None, None, None, None),
            ("character:arena-chest", "ArenaChest", "ArenaChest", None, None, None, None),
        ],
    )
    raw.execute(
        (
            "INSERT INTO SpawnPoints "
            "(StableKey, Scene, X, Y, Z, IsEnabled, IsDirectlyPlaced) "
            "VALUES (?, ?, ?, ?, ?, 1, 0)"
        ),
        ("spawn:ordinary", "OrdinaryScene", 9.0, 8.0, 7.0),
    )
    raw.execute(
        "INSERT INTO SpawnPointCharacters VALUES (?, ?, 1.0, 1, 0)",
        ("spawn:ordinary", "character:ordinary"),
    )
    raw.executemany(
        """INSERT INTO DynamicCharacterSpawns
           (Key, CharacterStableKey, Scene, X, Y, Z, SourceScript,
            EventX, EventY, EventZ, TriggerItemStableKey, TriggerMode,
            EventDisplayName, TriggerBoundsCenterX, TriggerBoundsCenterY,
            TriggerBoundsCenterZ, TriggerBoundsExtentsX, TriggerBoundsExtentsY,
            TriggerBoundsExtentsZ)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                "dyn:shivunax",
                "character:shivunax",
                "MalarothScene",
                1.0,
                2.0,
                3.0,
                "MalarothFeed",
                10.0,
                20.0,
                30.0,
                "item:mal-food",
                "proximity_auto_consume",
                "Malaroth feeding site",
                11.0,
                22.0,
                33.0,
                1.0,
                2.0,
                3.0,
            ),
            (
                "dyn:bad:1",
                "character:demented",
                "MalarothScene",
                4.0,
                5.0,
                6.0,
                "MalarothFeed",
                10.0,
                20.0,
                30.0,
                "item:bad-food",
                "proximity_auto_consume",
                "Malaroth feeding site",
                11.0,
                22.0,
                33.0,
                1.0,
                2.0,
                3.0,
            ),
            (
                "dyn:bad:2",
                "character:demented",
                "MalarothScene",
                7.0,
                8.0,
                9.0,
                "MalarothFeed",
                10.0,
                20.0,
                30.0,
                "item:bad-food",
                "proximity_auto_consume",
                "Malaroth feeding site",
                11.0,
                22.0,
                33.0,
                1.0,
                2.0,
                3.0,
            ),
        ],
    )
    raw.execute(
        """INSERT INTO ArenaRounds VALUES
           ('arena:1', 'ArenaScene', 'VitheoArena', 1, 'item:coin',
            'character:arena-chest', 'proximity_auto_consume', 'Vitheo''s arena',
            100.0, 200.0, 300.0, 110.0, 220.0, 330.0, 10.0, 20.0, 30.0)"""
    )
    writer = Writer(clean_path)
    writer.create_schema()
    process_characters(
        raw,
        writer,
        {
            "character:shivunax": {
                "display_name": "Shivunax",
                "wiki_page_name": "Shivunax",
                "image_name": "Shivunax",
                "is_wiki_generated": 1,
                "is_map_visible": 1,
            },
            "character:demented": {
                "display_name": "Demented Malaroth",
                "wiki_page_name": "Demented Malaroth",
                "image_name": "Demented Malaroth",
                "is_wiki_generated": 1,
                "is_map_visible": 1,
            },
        },
        {"item:coin", "item:mal-food", "item:bad-food"},
    )
    raw.close()
    yield writer._conn
    writer._conn.close()


def test_scripted_trigger_rows_preserve_items_bounds_and_identity(processed_db):
    rows = processed_db.execute(
        """SELECT character_stable_key, spawn_point_stable_key, x, y, z,
                  trigger_item_stable_key, trigger_mode, event_display_name,
                  event_x, event_y, event_z, trigger_bounds_center_x,
                  trigger_bounds_center_y, trigger_bounds_center_z,
                  trigger_bounds_extents_x, trigger_bounds_extents_y,
                  trigger_bounds_extents_z
           FROM character_spawns ORDER BY rowid"""
    ).fetchall()
    shivunax = next(row for row in rows if row[1] == "dyn:shivunax")
    bad = [row for row in rows if row[1] in {"dyn:bad:1", "dyn:bad:2"}]
    ordinary = next(row for row in rows if row[1] == "spawn:ordinary")
    assert shivunax[1:] == (
        "dyn:shivunax",
        1.0,
        2.0,
        3.0,
        "item:mal-food",
        "proximity_auto_consume",
        "Malaroth feeding site",
        10.0,
        20.0,
        30.0,
        11.0,
        22.0,
        33.0,
        1.0,
        2.0,
        3.0,
    )
    assert [row[1] for row in bad] == ["dyn:bad:1", "dyn:bad:2"]
    names = dict(processed_db.execute("SELECT stable_key, display_name FROM characters").fetchall())
    assert names["character:shivunax"] == "Shivunax"
    assert names["character:demented"] == "Demented Malaroth"
    assert [row[2:5] for row in bad] == [(4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
    assert all(row[5] == "item:bad-food" and row[0] == "character:demented" for row in bad)
    assert bad[0][8:] == shivunax[8:]
    assert shivunax[0] != bad[0][0] and shivunax[1] != bad[0][1]
    assert ordinary[2:5] == (9.0, 8.0, 7.0)
    assert all(value is None for value in ordinary[5:])

    arena = processed_db.execute("SELECT * FROM arena_rounds WHERE stable_key = 'arena:1'").fetchone()
    assert arena[6:9] == ("proximity_auto_consume", "Vitheo's arena", 100.0)
    assert tuple(arena[8:11]) != tuple(arena[11:14])
    assert tuple(arena[11:14]) == (110.0, 220.0, 330.0)
    assert tuple(arena[14:17]) == (10.0, 20.0, 30.0)


def test_nonfinite_trigger_bound_fails():
    with pytest.raises(ValueError, match="TriggerBoundsCenterX"):
        _optional_float(float("nan"), field="TriggerBoundsCenterX", row_key="dyn:bad")
