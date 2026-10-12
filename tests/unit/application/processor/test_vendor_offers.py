"""What vendors sell: the copies that players can meet, or the generated copies of a vendor placed nowhere."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    conn = writer.conn
    characters = ("shop", "shop bkp", "summon", "chest", "orphan", "unused")
    conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player)"
        " VALUES (?, ?, ?, 'npc', 0)",
        [(f"character:{name}", name, name) for name in characters],
    )
    conn.executemany(
        "INSERT INTO character_deduplications (group_key, member_stable_key, is_wiki_generated) VALUES (?, ?, ?)",
        [
            ("character:shop", "character:shop", 1),
            ("character:shop", "character:shop bkp", 0),
            ("character:summon", "character:summon", 1),
            ("character:chest", "character:chest", 1),
            ("character:orphan", "character:orphan", 1),
            # A prefab that a review found unused, which the mapping excludes.
            ("character:unused", "character:unused", 0),
        ],
    )
    conn.execute("INSERT INTO character_spawns (character_stable_key, scene) VALUES ('character:shop', 'Azure')")
    conn.execute(
        "INSERT INTO spells (stable_key, display_name, image_name, pet_to_summon_stable_key)"
        " VALUES ('spell:summon', 'Summon', 'Summon', 'character:summon')"
    )
    conn.execute("INSERT INTO treasure_locations (stable_key) VALUES ('treasure:loc')")
    conn.execute(
        "INSERT INTO treasure_chest_possible_spawns (chest_character_stable_key, treasure_location_stable_key,"
        " level_min, level_max, player_level_min, player_level_max)"
        " VALUES ('character:chest', 'treasure:loc', 1, 9, 1, 9)"
    )
    conn.executemany(
        "INSERT INTO character_vendor_items (character_stable_key, item_stable_key) VALUES (?, ?)",
        [
            ("character:shop", "item:a"),
            ("character:shop bkp", "item:a"),
            ("character:shop bkp", "item:b"),
            ("character:summon", "item:c"),
            ("character:chest", "item:d"),
            ("character:orphan", "item:g"),
            ("character:unused", "item:h"),
        ],
    )
    conn.executemany(
        "INSERT INTO character_vendor_quest_unlocks (character_stable_key, quest_stable_key) VALUES (?, ?)",
        [("character:shop", "quest:r"), ("character:shop bkp", "quest:q")],
    )
    conn.executemany(
        "INSERT INTO quest_variants (resource_name, quest_stable_key, unlock_item_for_vendor_stable_key)"
        " VALUES (?, ?, ?)",
        [("R", "quest:r", "item:f"), ("Q", "quest:q", "item:e")],
    )
    yield conn
    conn.close()


def test_characters_in_game_are_placed_summoned_or_possible_chests(conn: sqlite3.Connection) -> None:
    in_game = {row[0] for row in conn.execute("SELECT stable_key FROM characters_in_game")}

    assert in_game == {"character:shop", "character:summon", "character:chest"}


def test_only_copies_in_the_game_sell_unless_the_export_places_none(conn: sqlite3.Connection) -> None:
    # A generated vendor that the export places nowhere still sells; an unused prefab does not.
    offers = {
        tuple(row)
        for row in conn.execute(
            "SELECT vendor_stable_key, copy_stable_key, item_stable_key, quest_stable_key FROM vendor_offers"
        )
    }

    assert offers == {
        ("character:shop", "character:shop", "item:a", None),
        ("character:shop", "character:shop", "item:f", "quest:r"),
        ("character:summon", "character:summon", "item:c", None),
        ("character:chest", "character:chest", "item:d", None),
        ("character:orphan", "character:orphan", "item:g", None),
    }
