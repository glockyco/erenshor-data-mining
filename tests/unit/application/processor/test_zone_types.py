from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.entities import process_zones
from erenshor.application.processor.mapping import load_mapping
from erenshor.application.processor.writer import Writer


def test_zone_types_reuse_raid_sources_and_reviewed_area_input(tmp_path: Path) -> None:
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE Zones (StableKey TEXT, SceneName TEXT, ZoneName TEXT, IsDungeon INTEGER, RaidCapable INTEGER);
        CREATE TABLE PlanarBosses (Scene TEXT, CharacterStableKey TEXT);
        CREATE TABLE ArenaRounds (StableKey TEXT, Scene TEXT, RoundIndex INTEGER);
        CREATE TABLE ArenaRoundEnemies (ArenaRoundStableKey TEXT, EnemyCharacterStableKey TEXT);
        INSERT INTO PlanarBosses VALUES ('NewPlane', 'character:boss');
        INSERT INTO ArenaRounds VALUES ('round:one', 'NewArena', 1);
        INSERT INTO ArenaRoundEnemies VALUES ('round:one', 'character:arena');
        INSERT INTO Zones VALUES ('zone:hall', 'Hall', 'Hall', 0, 1);
        INSERT INTO Zones VALUES ('zone:cave', 'Cave', 'Cave', 1, 0);
        INSERT INTO Zones VALUES ('zone:plane', 'NewPlane', 'Plane', 0, 1);
        INSERT INTO Zones VALUES ('zone:arena', 'NewArena', 'Arena', 0, 1);
        INSERT INTO Zones VALUES ('zone:event', 'EventScene', 'Event', 1, 0);
        INSERT INTO Zones VALUES ('zone:cell', 'Cell', 'Cell', 0, 0);
        INSERT INTO Zones VALUES ('zone:meadow', 'Meadow', 'Meadow', 1, 0);
    """)
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(
        json.dumps(
            {
                "rules": {
                    "zone:event": {
                        "wiki_page_name": "Event",
                        "display_name": "Event",
                        "image_name": "Event",
                        "zone_type": "Event",
                        "reason": "Reviewed scripted event region.",
                    },
                    "zone:hall": {
                        "wiki_page_name": "Hall",
                        "display_name": "Hall",
                        "image_name": "Hall",
                        "zone_type": "Outdoor",
                        "reason": "Reviewed broad world area, not a raid.",
                    },
                    "zone:cave": {
                        "wiki_page_name": "Cave",
                        "display_name": "Cave",
                        "image_name": "Cave",
                        "zone_type": "Dungeon",
                        "reason": "Reviewed dungeon area.",
                    },
                    "zone:cell": {
                        "wiki_page_name": "Cell",
                        "display_name": "Cell",
                        "image_name": "Cell",
                        "zone_type": "Dungeon",
                        "reason": "Reviewed dungeon despite the unrelated native task flag.",
                    },
                    "zone:meadow": {
                        "wiki_page_name": "Meadow",
                        "display_name": "Meadow",
                        "image_name": "Meadow",
                        "zone_type": "Outdoor",
                        "reason": "Reviewed outdoor area despite the native task flag.",
                    },
                    "zone:plane": {
                        "wiki_page_name": "Plane",
                        "display_name": "Plane",
                        "image_name": "Plane",
                        "zone_type": "Outdoor",
                        "reason": "A reviewed label cannot override exported raid encounters.",
                    },
                }
            }
        )
    )
    mapping, _ = load_mapping(mapping_file)
    writer = Writer(tmp_path / "clean.sqlite")
    try:
        writer.create_schema()
        process_zones(raw, writer, mapping)
        assert dict(writer.conn.execute("SELECT stable_key, zone_type FROM zones")) == {
            "zone:hall": "Outdoor",
            "zone:cave": "Dungeon",
            "zone:plane": "Raid",
            "zone:arena": "Raid",
            "zone:event": "Event",
            "zone:cell": "Dungeon",
            "zone:meadow": "Outdoor",
        }
        assert writer.conn.execute("SELECT raid_capable FROM zones WHERE stable_key='zone:hall'").fetchone()[0] == 1
    finally:
        raw.close()
        writer.conn.close()


@pytest.mark.parametrize(
    "key,kind,reason",
    [
        ("zone:event", "Raid", "Not a game-derived raid"),
        ("character:npc", "Event", "Wrong entity kind"),
        ("zone:event", "Event", ""),
        ("zone:event", "Dungeon", ""),
        ("zone:event", "Outdoor", ""),
        ("zone:event", "Home", "Not a public area class"),
        ("zone:event", None, "Null is not a reviewed class"),
        ("zone:event", [], "A list is not a class"),
    ],
)
def test_zone_type_overrides_are_narrow_and_require_a_reason(
    tmp_path: Path, key: str, kind: object, reason: str
) -> None:
    path = tmp_path / "mapping.json"
    path.write_text(
        json.dumps(
            {
                "rules": {
                    key: {
                        "wiki_page_name": "Event",
                        "display_name": "Event",
                        "image_name": "Event",
                        "zone_type": kind,
                        "reason": reason,
                    }
                }
            }
        )
    )
    with pytest.raises(ValueError, match="zone_type"):
        load_mapping(path)


@pytest.mark.parametrize("native_dungeon", [0, 1])
def test_unreviewed_nonraid_area_is_blocked_instead_of_inferred(tmp_path: Path, native_dungeon: int) -> None:
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE Zones (StableKey TEXT, SceneName TEXT, ZoneName TEXT, IsDungeon INTEGER, RaidCapable INTEGER);
        CREATE TABLE PlanarBosses (Scene TEXT, CharacterStableKey TEXT);
        CREATE TABLE ArenaRounds (StableKey TEXT, Scene TEXT, RoundIndex INTEGER);
        CREATE TABLE ArenaRoundEnemies (ArenaRoundStableKey TEXT, EnemyCharacterStableKey TEXT);
        INSERT INTO PlanarBosses VALUES ('KnownRaid', 'character:boss');
    """)
    raw.execute("INSERT INTO Zones VALUES ('zone:unreviewed','Unreviewed','Unreviewed',?,0)", (native_dungeon,))
    writer = Writer(tmp_path / "clean.sqlite")
    try:
        writer.create_schema()
        with pytest.raises(ValueError, match=r"zone:unreviewed.*reviewed mapping"):
            process_zones(raw, writer, {})
    finally:
        raw.close()
        writer.conn.close()
