"""Common-world substitution pool and merged character loot export contracts."""

import sqlite3


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
