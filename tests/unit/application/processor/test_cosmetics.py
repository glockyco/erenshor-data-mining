"""The clean database says what each item does in a cosmetic slot."""

import sqlite3

import pytest

from erenshor.application.processor.entities import process_items
from erenshor.application.processor.writer import Writer


def _raw(cosmetic_items: list[tuple[str, str, str]]) -> sqlite3.Connection:
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
    raw.execute(
        "CREATE TABLE Items (StableKey TEXT, ItemName TEXT, ResourceName TEXT, RequiredSlot TEXT, "
        "EquipmentToActivate TEXT)"
    )
    raw.executemany(
        "INSERT INTO Items VALUES (?, ?, ?, ?, ?)",
        [
            ("item:mask fox", "Mask: Fox", "MASK FOX", "General", "Fox"),
            # A helmet whose part has a mask's look but is no mask object.
            ("item:mask of spies", "Mask of Spies", "MASK OF SPIES", "Head", "BanditMask"),
            ("item:belt lamp", "Belt Lamp", "BELT LAMP", "General", None),
            ("item:watcher's lens", "Watcher's Lens", "WATCHERS LENS", "General", None),
            ("item:bread", "Bread", "BREAD", "General", None),
        ],
    )
    raw.execute("CREATE TABLE ItemModelParts (Body TEXT, Slot TEXT, Position INTEGER, Part TEXT, Meshes TEXT)")
    raw.executemany(
        "INSERT INTO ItemModelParts VALUES (?, ?, ?, ?, '')",
        [
            ("Male", "HalloweenMasks", 0, "Fox"),
            ("Female", "HalloweenMasks", 0, "Fox"),
            ("Male", "Head", 3, "BanditMask"),
        ],
    )
    raw.execute("CREATE TABLE CosmeticItems (ItemStableKey TEXT, Effect TEXT, Field TEXT)")
    raw.executemany("INSERT INTO CosmeticItems VALUES (?, ?, ?)", cosmetic_items)
    raw.execute(
        "CREATE TABLE CraftingRewards ("
        "RecipeItemStableKey TEXT, RewardSlot INTEGER, RewardItemStableKey TEXT, RewardQuantity INTEGER)"
    )
    for table in ("ItemStats", "ItemClasses", "CraftingRecipes", "ItemDrops"):
        raw.execute(f"CREATE TABLE {table} (placeholder TEXT)")
    return raw


def test_masks_and_the_items_that_the_inventory_names_are_cosmetic(tmp_path):
    raw = _raw(
        [
            ("item:belt lamp", "BeltLamp", "BeltLampItem"),
            ("item:watcher's lens", "FernallanLensObj", "WatchersLens"),
        ]
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()

    process_items(raw, writer, {})

    rows = writer.conn.execute("SELECT stable_key, cosmetic_effect FROM items ORDER BY stable_key").fetchall()
    assert [tuple(row) for row in rows] == [
        ("item:belt lamp", "belt lamp"),
        ("item:bread", None),
        ("item:mask fox", "mask"),
        ("item:mask of spies", None),
        ("item:watcher's lens", "lens"),
    ]


@pytest.mark.parametrize(
    ("cosmetic_items", "message"),
    [
        ([("item:keeper's lantern", "BeltLamp", "KeepersLamp")], "which is no item"),
        ([("item:bread", "SpectreObj", "SpectreItem")], "which no effect describes"),
    ],
)
def test_an_inventory_item_that_the_build_cannot_describe_stops_it(tmp_path, cosmetic_items, message):
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()

    with pytest.raises(ValueError, match=message):
        process_items(_raw(cosmetic_items), writer, {})
