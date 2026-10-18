"""Common-world substitution pool and merged character loot export contracts."""

import sqlite3
from pathlib import Path

import pytest

from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository

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


def test_common_world_item_sources_preserve_reachable_swap_bounds(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean, DatabaseConnection(main_clean_db, read_only=True) as db:
        provenance = ItemProvenanceRepository(db)
        pool = clean.execute("SELECT item_stable_key FROM common_world_items").fetchall()
        assert pool
        for (item_key,) in pool:
            minimum, maximum, count = clean.execute(
                f"""SELECT MIN(ld.drop_probability), MAX(ld.drop_probability), COUNT(*)
                    FROM loot_drops ld
                    JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
                    WHERE ld.item_stable_key = ? AND ld.is_common_world_item = 1
                      AND NOT {_OWN_DROP}""",
                (item_key,),
            ).fetchone()
            assert count > 0, item_key
            sources = [fact for fact in provenance.get_acquisitions(item_key) if fact.kind == "common_world_item"]
            assert len(sources) == 1, item_key
            source = sources[0]
            assert source.source_stable_key is None
            assert source.source_copy_stable_key is None
            assert source.probability_basis == "per_kill"
            assert source.probability_min == pytest.approx(minimum)
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
        provenance = ItemProvenanceRepository(db)
        rows = clean.execute(
            f"""SELECT ld.character_stable_key, ld.item_stable_key, {_OWN_DROP} AS own_drop
                FROM loot_drops ld
                JOIN items i ON i.stable_key = ld.item_stable_key
                JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
                WHERE ld.is_common_world_item = 1 AND i.display_name IS NOT NULL"""
        ).fetchall()
        assert any(not own for _, _, own in rows)
        assert any(own for _, _, own in rows)
        actual_by_character = {
            key: {drop.item_link.stable_key for drop in characters.get_character_loot_drops(key)}
            for key in {key for key, _, _ in rows}
        }
        edges_by_character: dict[str, set[str]] = {key: set() for key in actual_by_character}
        for fact in provenance.iter_acquisitions():
            if fact.kind == "character_drop" and fact.source_copy_stable_key in edges_by_character:
                edges_by_character[fact.source_copy_stable_key].add(fact.item_stable_key)
        for character, item, own_drop in rows:
            assert (item in actual_by_character[character]) == bool(own_drop), (character, item)
            assert (item in edges_by_character[character]) == bool(own_drop), (character, item)


def test_common_pool_named_drops_preserve_native_copy_dimensions(main_raw_db: Path, main_clean_db: Path) -> None:
    with (
        sqlite3.connect(main_raw_db) as raw,
        sqlite3.connect(main_clean_db) as clean,
        DatabaseConnection(main_clean_db, read_only=True) as db,
    ):
        items_repo = ItemRepository(db)
        provenance = ItemProvenanceRepository(db)
        pool = {row[0] for row in clean.execute("SELECT item_stable_key FROM common_world_items")}
        items = [item for item in items_repo.get_items_for_wiki_generation() if item.stable_key in pool]
        assert {item.stable_key for item in items} == pool
        compared = 0
        excluded_compared = 0
        for item in items:
            rows = clean.execute(
                f"""SELECT ld.character_stable_key, s.group_key, ld.drop_probability,
                           ld.expected_per_kill, ld.drop_count_distribution, ld.is_guaranteed,
                           c.guaranteed_drop_rolls
                    FROM loot_drops ld
                    JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
                    JOIN characters c ON c.stable_key = ld.character_stable_key
                    WHERE ld.item_stable_key = ? AND {_OWN_DROP}""",
                (item.stable_key,),
            ).fetchall()
            facts = [fact for fact in provenance.get_acquisitions(item.stable_key) if fact.kind == "character_drop"]
            by_copy = {fact.source_copy_stable_key: fact for fact in facts}
            assert len(by_copy) == len(facts)
            clean_copies = {
                row[0]
                for row in clean.execute(
                    "SELECT character_stable_key FROM loot_drops WHERE item_stable_key = ?", (item.stable_key,)
                )
            }
            # Excluded serialized copies remain facts, not player acquisition paths.
            excluded = {
                copy: (chance, expected, distribution)
                for copy, chance, expected, distribution in raw.execute(
                    """SELECT CharacterStableKey, DropProbability, ExpectedPerKill, DropCountDistribution
                       FROM LootDrops WHERE ItemStableKey = ?""",
                    (item.stable_key,),
                )
                if copy not in clean_copies
            }
            assert set(by_copy) == {row[0] for row in rows} | set(excluded), item.stable_key
            for copy, (chance, expected, distribution) in excluded.items():
                fact = by_copy[copy]
                assert fact.player_access_state == "non_acquirable"
                assert any(atom.predicate == "never" for atom in fact.conditions)
                assert fact.probability_min == chance
                assert fact.probability_max == chance
                assert fact.expected_quantity == expected
                assert fact.count_distribution == distribution
                assert any(evidence.input_relation == "raw.LootDrops" for evidence in fact.evidence)
                excluded_compared += 1
            for copy, group, chance, expected, distribution, guaranteed, rolls in rows:
                fact = by_copy[copy]
                assert fact.source_stable_key == group
                assert fact.source_group_key == group
                assert fact.probability_min == chance
                assert fact.probability_max == chance
                assert fact.probability_kind == ("unknown" if chance is None else "exact")
                assert fact.probability_basis == "per_kill"
                assert fact.probability_stage == "final_acquisition"
                assert fact.expected_quantity == expected
                assert fact.count_distribution == distribution
                assert fact.guarantee_scope == ("pool" if guaranteed else None)
                assert fact.guaranteed_roll_count == (rolls if guaranteed else None)
                assert fact.evidence
                compared += 1
        assert compared > 0
        assert excluded_compared > 0
