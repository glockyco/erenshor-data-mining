"""The clean database lists only the reward that the forge awards."""

import sqlite3

from erenshor.application.processor.entities import process_items
from erenshor.application.processor.writer import Writer


def test_a_template_with_two_rewards_crafts_only_the_first(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE code_facts (fact_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT)")
    raw.executemany(
        "INSERT INTO code_facts VALUES (?, ?, ?)",
        [
            ("auction.player_listing_gates", "item_level", "!= 0"),
            ("auction.player_listing_gates", "item_value", "!= 0"),
            ("auction.player_listing_gate", "ok", "true"),
        ],
    )
    raw.execute("CREATE TABLE Items (StableKey TEXT, ItemName TEXT, ResourceName TEXT, RequiredSlot TEXT)")
    raw.executemany(
        "INSERT INTO Items VALUES (?, ?, ?, ?)",
        [
            ("item:template - ring", "A Ring Mold", "TEMPLATE - RING", "General"),
            ("item:ring", "Ceremonial Ring", "RING", "Ring"),
            ("item:ring 1", "Pristine Ceremonial Ring", "RING 1", "Ring"),
        ],
    )
    raw.execute(
        "CREATE TABLE CraftingRewards ("
        "RecipeItemStableKey TEXT, RewardSlot INTEGER, RewardItemStableKey TEXT, RewardQuantity INTEGER)"
    )
    raw.executemany(
        "INSERT INTO CraftingRewards VALUES (?, ?, ?, ?)",
        [
            ("item:template - ring", 1, "item:ring", 1),
            ("item:template - ring", 2, "item:ring 1", 1),
        ],
    )
    for table in ("ItemStats", "ItemClasses", "CraftingRecipes", "ItemDrops"):
        raw.execute(f"CREATE TABLE {table} (placeholder TEXT)")

    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()
    process_items(raw, writer, {})

    rows = writer.conn.execute(
        "SELECT recipe_item_stable_key, reward_slot, reward_item_stable_key FROM crafting_rewards"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("item:template - ring", 1, "item:ring")]

    raw.close()
    writer.conn.close()
