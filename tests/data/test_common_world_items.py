"""Common-world substitution pool and merged character loot export contracts."""

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.wiki_lua.items import build_item_sources_by_item
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repositories.zones import ZoneRepository

_OWN_DROP = """(
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0)
    OR COALESCE(ld.is_rare, 0) OR COALESCE(ld.is_legendary, 0)
    OR COALESCE(ld.is_ultra_rare, 0) OR COALESCE(ld.is_guaranteed, 0)
    OR COALESCE(ld.is_actual, 0)
)"""


def test_common_world_pool_matches_raw_positions(main_raw_db, main_clean_db):
    with sqlite3.connect(main_raw_db) as raw, sqlite3.connect(main_clean_db) as clean:
        raw_rows = raw.execute("SELECT Position, ItemStableKey FROM CommonWorldItems ORDER BY Position").fetchall()
        clean_rows = clean.execute(
            "SELECT position, item_stable_key FROM common_world_items ORDER BY position"
        ).fetchall()
        assert len(raw_rows) == 6
        assert all(key is not None for _, key in raw_rows)
        assert clean_rows == raw_rows
        assert (
            clean.execute(
                """SELECT COUNT(*) FROM common_world_items p
               LEFT JOIN items i ON i.stable_key = p.item_stable_key
               WHERE p.item_stable_key IS NOT NULL AND i.stable_key IS NULL"""
            ).fetchone()[0]
            == 0
        )
        assert (
            raw.execute("SELECT COUNT(*) FROM LootDrops WHERE ItemStableKey = 'A Common World Drop'").fetchone()[0] == 0
        )
        assert (
            clean.execute("SELECT COUNT(*) FROM loot_drops WHERE item_stable_key = 'A Common World Drop'").fetchone()[0]
            == 0
        )
        assert clean.execute("SELECT COUNT(*) FROM items WHERE stable_key = 'A Common World Drop'").fetchone()[0] == 0


def test_every_common_loot_character_has_the_whole_pool(main_raw_db, main_clean_db):
    with sqlite3.connect(main_raw_db) as raw, sqlite3.connect(main_clean_db) as clean:
        common_characters = {
            row[0] for row in raw.execute("SELECT DISTINCT CharacterStableKey FROM LootDrops WHERE IsCommon = 1")
        }
        # Unreachable boss phases intentionally have no clean loot rows.
        clean_characters = {row[0] for row in clean.execute("SELECT DISTINCT character_stable_key FROM loot_drops")}
        common_characters &= clean_characters
        assert common_characters
        pool = {row[0] for row in clean.execute("SELECT item_stable_key FROM common_world_items")}
        for character in sorted(common_characters):
            rows = clean.execute(
                """SELECT item_stable_key
                   FROM loot_drops WHERE character_stable_key = ? AND is_common_world_item = 1""",
                (character,),
            ).fetchall()
            assert {row[0] for row in rows} == pool, character


def test_bread_is_one_combined_own_and_world_drop_row(main_raw_db, main_clean_db):
    with sqlite3.connect(main_raw_db) as raw, sqlite3.connect(main_clean_db) as clean:
        bread_keys = {
            row[0]
            for row in clean.execute(
                """SELECT i.stable_key FROM items i
                   JOIN common_world_items p ON p.item_stable_key = i.stable_key
                   WHERE i.display_name = 'Bread'"""
            )
        }
        assert len(bread_keys) == 1
        bread = bread_keys.pop()
        raw_rows = raw.execute(
            """SELECT CharacterStableKey, DropProbability, ExpectedPerKill, DropCountDistribution
               FROM LootDrops WHERE ItemStableKey = ? AND IsCommon = 1 AND IsCommonWorldItem = 1""",
            (bread,),
        ).fetchall()
        assert raw_rows
        compared = 0
        for character, probability, expected, distribution in raw_rows:
            rows = clean.execute(
                """SELECT drop_probability, expected_per_kill, drop_count_distribution,
                          is_common, is_common_world_item
                   FROM loot_drops WHERE character_stable_key = ? AND item_stable_key = ?""",
                (character, bread),
            ).fetchall()
            if rows:
                assert rows == [(probability, expected, distribution, 1, 1)]
                compared += 1
        assert compared > 0


def test_common_world_item_sources_use_only_reachable_positive_swap_rows(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean, DatabaseConnection(main_clean_db, read_only=True) as db:
        characters = CharacterRepository(db)
        pool = clean.execute("SELECT item_stable_key FROM common_world_items").fetchall()
        assert pool
        for (item_key,) in pool:
            minimum, maximum, count = clean.execute(
                f"""SELECT MIN(ld.drop_probability), MAX(ld.drop_probability), COUNT(*)
                    FROM loot_drops ld
                    JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
                    WHERE ld.item_stable_key = ? AND ld.is_common_world_item = 1
                      AND NOT {_OWN_DROP} AND ld.drop_probability > 0""",
                (item_key,),
            ).fetchone()
            assert count > 0, item_key
            sources = characters.get_common_world_item_sources(item_key)
            assert len(sources) == 1, item_key
            source = sources[0]
            assert source.source_type == "common_world_item"
            assert source.source_key is None
            assert source.probability == pytest.approx(minimum)
            assert source.probability_max == pytest.approx(maximum)


def test_bread_page_has_one_common_world_item_drop_range(main_clean_db: Path, main_wiki_generated: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        rows = clean.execute(
            f"""SELECT MIN(ld.drop_probability), MAX(ld.drop_probability), COUNT(*)
                FROM loot_drops ld
                JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
                JOIN items i ON i.stable_key = ld.item_stable_key
                WHERE i.display_name = 'Bread' AND ld.is_common_world_item = 1
                  AND NOT {_OWN_DROP} AND ld.drop_probability > 0"""
        ).fetchone()
    minimum, maximum, count = rows
    assert count > 0
    low, high = f"{minimum:.1f}", f"{maximum:.1f}"
    chance = low if low == high else f"{low}\u2013{high}"
    page = (main_wiki_generated / "Bread.txt").read_text()
    source = next(line for line in page.splitlines() if line.startswith("|source="))
    assert source.count("Any enemy with common drops") == 1
    assert f"Any enemy with common drops ({chance}% per kill)" in source


def test_character_page_loot_excludes_swap_only_rows_and_retains_combined_rows(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean, DatabaseConnection(main_clean_db, read_only=True) as db:
        characters = CharacterRepository(db)
        loot_tables = LootTableRepository(db)
        rows = clean.execute(
            f"""SELECT ld.character_stable_key, ld.item_stable_key, {_OWN_DROP} AS own_drop
                FROM loot_drops ld
                JOIN items i ON i.stable_key = ld.item_stable_key
                WHERE ld.is_common_world_item = 1 AND i.display_name IS NOT NULL"""
        ).fetchall()
        assert any(not own for _, _, own in rows)
        assert any(own for _, _, own in rows)
        actual_by_character = {
            key: {drop.item_link.stable_key for drop in characters.get_character_loot_drops(key)}
            for key in {key for key, _, _ in rows}
        }
        edges_by_character = {
            key: {drop.item_stable_key for drop in loot_tables.get_loot_for_character(key)}
            for key in actual_by_character
        }
        for character, item, own_drop in rows:
            assert (item in actual_by_character[character]) == bool(own_drop), (character, item)
            assert (item in edges_by_character[character]) == bool(own_drop), (character, item)


def test_data_items_named_drop_sources_keep_only_own_drop_groups(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean, DatabaseConnection(main_clean_db, read_only=True) as db:
        items_repo = ItemRepository(db)
        characters = CharacterRepository(db)
        pool = {row[0] for row in clean.execute("SELECT item_stable_key FROM common_world_items")}
        items = [item for item in items_repo.get_items_for_wiki_generation() if item.stable_key in pool]
        assert {item.stable_key for item in items} == pool
        sources = build_item_sources_by_item(items, items_repo, characters, QuestRepository(db), ZoneRepository(db))
        combined_groups = 0
        for item in items:
            expected = dict(
                clean.execute(
                    f"""WITH own_groups AS (
                            SELECT s.group_key, MAX(ld.drop_probability) AS probability
                            FROM character_fact_sources s
                            JOIN loot_drops ld ON ld.character_stable_key = s.member_stable_key
                            WHERE ld.item_stable_key = ? AND {_OWN_DROP} AND ld.drop_probability > 0
                            GROUP BY s.group_key
                        )
                        SELECT MIN(d.member_stable_key), g.probability
                        FROM own_groups g
                        JOIN character_deduplications d ON d.group_key = g.group_key
                        WHERE d.is_wiki_generated = 1
                        GROUP BY g.group_key, g.probability""",
                    (item.stable_key,),
                ).fetchall()
            )
            combined_groups += len(expected)
            obtained = sources[item.stable_key].obtained_from
            actual = {source.source_key: source.probability for source in obtained if source.source_type == "drop"}
            assert actual == pytest.approx(expected), item.stable_key
            assert len([source for source in obtained if source.source_type == "drop"]) == len(expected)
            assert [source for source in obtained if source.source_type == "common_world_item"] == (
                characters.get_common_world_item_sources(item.stable_key)
            )
            named_droppers = {
                link.stable_key: chance for link, chance in characters.get_characters_dropping_item(item.stable_key)
            }
            assert named_droppers == pytest.approx(expected), item.stable_key
        assert combined_groups > 0
