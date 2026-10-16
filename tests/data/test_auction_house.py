"""Ordinary auction draws supply source-free pages without inventing stock."""

import sqlite3
from pathlib import Path

SOURCE_FREE_PAGES = {
    "Beast Stone",
    "Charm of the Shield",
    "Cold Steel Plate",
    "Daggersilk Gloves",
    "Daggersilk Hood",
    "Daggersilk Shirt",
    "Daggersilk Shoes",
    "Daggersilk Sleeves",
    "Daggersilk Trousers",
    "Echoes",
    "Judicial Boots",
    "Lamplighter's Spark",
    "Lightkeeper's Cape",
    "Pristine Ceremonial Ring",
    "Spell Scroll: Crushing Current",
    "Spell Scroll: Dissipate Storm",
    "Spell Scroll: Invoke Storm",
    "Unusual Copper Sceptre",
}


def test_previously_source_free_items_have_direct_auction_source(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as conn:
        placeholders = ",".join("?" for _ in SOURCE_FREE_PAGES)
        rows = conn.execute(
            f"""SELECT DISTINCT i.wiki_page_name FROM items i
                JOIN auction_house_items a ON a.item_stable_key = i.stable_key
                WHERE a.route = 'direct' AND i.wiki_page_name IN ({placeholders})""",
            sorted(SOURCE_FREE_PAGES),
        ).fetchall()
    assert {row[0] for row in rows} == SOURCE_FREE_PAGES
    assert len(rows) == 18


def test_listing_routes_respect_level_and_flag_exclusions(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as conn:
        assert conn.execute("SELECT count(*) FROM auction_house_items").fetchone()[0] > 0
        assert (
            conn.execute("""
            SELECT count(*) FROM auction_house_items a JOIN items i ON i.stable_key = a.item_stable_key
            WHERE i.no_trade_no_destroy = 1 OR i.is_unique = 1 OR i.furniture_set = 1
               OR i.item_level >= 40 OR (a.route = 'direct' AND i.item_level >= 36)
        """).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("""
            SELECT count(*) FROM auction_house_items a JOIN items i ON i.stable_key = a.item_stable_key
            WHERE i.display_name = 'Shivering Torch'
        """).fetchone()[0]
            == 0
        )


def test_no_normal_level_forces_an_exhausted_draw(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as conn:
        sim_cap = int(conn.execute("SELECT value FROM code_facts WHERE fact_id='auction.sim_level_cap'").fetchone()[0])
        player_cap = int(
            conn.execute("SELECT value FROM code_facts WHERE fact_id='auction.player_level_cap'").fetchone()[0]
        )
        for level in range(1, sim_cap + 1):
            assert (
                conn.execute(
                    """
                SELECT count(*) FROM auction_house_items WHERE route='direct'
                AND ? BETWEEN min_sim_level AND max_sim_level
            """,
                    (level,),
                ).fetchone()[0]
                > 0
            ), f"sim level {level} forces retry exhaustion"
        for level in range(1, player_cap + 1):
            assert (
                conn.execute(
                    """
                SELECT count(*) FROM auction_house_items WHERE route='replacement'
                AND ? BETWEEN min_player_level AND max_player_level
            """,
                    (level,),
                ).fetchone()[0]
                > 0
            ), f"player level {level} forces replacement exhaustion"


def test_broker_objects_are_resolved_without_coordinates(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as conn:
        names = conn.execute("""
            SELECT DISTINCT c.object_name FROM auction_house_brokers b
            JOIN characters c ON c.stable_key=b.character_stable_key
        """).fetchall()
    assert {row[0] for row in names} == {"Thella Steepleton", "Goldie Retalio"}
