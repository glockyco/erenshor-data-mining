"""Unit tests for item obtainability checking.

Tests cover all acquisition methods:
- Drops from characters
- Vendor sales
- Quest rewards
- Quest dialog rewards
- Fishing
- Mining
- Crafting recipes
- World item bags
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from erenshor.domain.services import is_item_obtainable


def create_test_db() -> Engine:
    """Create an in-memory test database with sample data."""
    engine = create_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        # Create all necessary tables
        conn.execute(
            text(
                """
            CREATE TABLE Items (
                Id VARCHAR PRIMARY KEY,
                ItemName VARCHAR,
                ResourceName VARCHAR
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE LootDrops (
                CharacterPrefabGuid VARCHAR,
                ItemId VARCHAR,
                DropProbability FLOAT
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE Characters (
                Id INTEGER PRIMARY KEY,
                Guid VARCHAR,
                NPCName VARCHAR
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE Quests (
                QuestDBIndex INTEGER PRIMARY KEY,
                QuestName VARCHAR,
                ItemOnCompleteId VARCHAR
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE CharacterDialogs (
                CharacterId INTEGER,
                DialogIndex INTEGER,
                GiveItemName VARCHAR
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE WaterFishables (
                WaterId INTEGER,
                Type VARCHAR,
                ItemName VARCHAR,
                DropChance FLOAT
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE MiningNodeItems (
                MiningNodeId INTEGER,
                ItemName VARCHAR,
                DropChance FLOAT
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE ItemBags (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                CoordinateId INTEGER,
                ItemId VARCHAR,
                Respawns INTEGER
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE CharacterVendorItems (
                CharacterId INTEGER,
                ItemName VARCHAR
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE CraftingRewards (
                RecipeItemId VARCHAR,
                RewardSlot INTEGER,
                RewardItemId VARCHAR,
                RewardQuantity INTEGER
            )
        """
            )
        )

        conn.commit()

    return engine


def test_item_dropped_by_character(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via character drops."""
    with test_engine.connect() as conn:
        # Insert test data
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('1', 'Sword', 'sword')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO LootDrops (CharacterPrefabGuid, ItemId, DropProbability) VALUES ('goblin', '1', 0.5)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "1", "Sword")
    assert result is True, "Item dropped by character should be obtainable"


def test_item_sold_by_vendor(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via vendor purchase."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('2', 'Potion', 'potion')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) VALUES (1, 'vendor1', 'Bob')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) VALUES (1, 'Potion')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) VALUES (1, 'Bread')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) VALUES (1, 'Water')"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "2", "Potion")
    assert result is True, "Item sold by vendor should be obtainable"


def test_item_quest_reward(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via quest reward."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('3', 'Shield', 'shield')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Quests (QuestDBIndex, QuestName, ItemOnCompleteId) VALUES (1, 'Save the Town', '3')"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "3", "Shield")
    assert result is True, "Item from quest reward should be obtainable"


def test_item_quest_dialog_reward(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via quest dialog."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('4', 'Ring', 'ring')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterDialogs (CharacterId, DialogIndex, GiveItemName) VALUES (1, 1, 'Ring')"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "4", "Ring")
    assert result is True, "Item from quest dialog should be obtainable"


def test_item_from_fishing(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via fishing."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('5', 'Fish', 'fish')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO WaterFishables (WaterId, Type, ItemName, DropChance) VALUES (1, 'Common', 'Fish', 0.7)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "5", "Fish")
    assert result is True, "Item from fishing should be obtainable"


def test_item_from_mining(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via mining."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('6', 'Ore', 'ore')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO MiningNodeItems (MiningNodeId, ItemName, DropChance) VALUES (1, 'Ore', 0.8)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "6", "Ore")
    assert result is True, "Item from mining should be obtainable"


def test_item_from_crafting(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable via crafting recipe."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('7', 'Armor', 'armor')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('100', 'Recipe: Armor', 'recipe_armor')"
            )
        )
        # Recipe that produces items '7' and '8'
        conn.execute(
            text(
                "INSERT INTO CraftingRewards (RecipeItemId, RewardSlot, RewardItemId, RewardQuantity) VALUES ('100', 1, '7', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CraftingRewards (RecipeItemId, RewardSlot, RewardItemId, RewardQuantity) VALUES ('100', 2, '8', 1)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "7", "Armor")
    assert result is True, "Item from crafting recipe should be obtainable"


def test_item_from_world_bag(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable from world item bag."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('8', 'Treasure', 'treasure')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ItemBags (CoordinateId, ItemId, Respawns) VALUES (1, '8', 1)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "8", "Treasure")
    assert result is True, "Item from world bag should be obtainable"


def test_item_not_obtainable(test_engine: Engine = create_test_db()) -> None:
    """Test item with no acquisition methods."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('99', 'Unobtainable', 'unobtainable')"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "99", "Unobtainable")
    assert result is False, "Item with no sources should not be obtainable"


def test_item_with_zero_drop_rate(test_engine: Engine = create_test_db()) -> None:
    """Test item with zero drop probability is not obtainable."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('10', 'Disabled', 'disabled')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO LootDrops (CharacterPrefabGuid, ItemId, DropProbability) VALUES ('npc', '10', 0.0)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "10", "Disabled")
    assert result is False, "Item with zero drop rate should not be obtainable"


def test_item_multiple_sources(test_engine: Engine = create_test_db()) -> None:
    """Test item obtainable from multiple sources."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('11', 'Common', 'common')"
            )
        )
        # Multiple acquisition methods
        conn.execute(
            text(
                "INSERT INTO LootDrops (CharacterPrefabGuid, ItemId, DropProbability) VALUES ('mob', '11', 0.3)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) VALUES (2, 'vendor2', 'Shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) VALUES (2, 'Common')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) VALUES (2, 'Rare')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO WaterFishables (WaterId, Type, ItemName, DropChance) VALUES (2, 'Rare', 'Common', 0.1)"
            )
        )
        conn.commit()

    result = is_item_obtainable(test_engine, "11", "Common")
    assert result is True, "Item with multiple sources should be obtainable"


def test_crafting_recipe_token_matching(test_engine: Engine = create_test_db()) -> None:
    """Test that crafting recipe token matching is exact (no partial matches)."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('12', 'Item12', 'item12')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('123', 'Item123', 'item123')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) VALUES ('200', 'Recipe', 'recipe')"
            )
        )
        # Recipe produces '123' and '456', not '12'
        conn.execute(
            text(
                "INSERT INTO CraftingRewards (RecipeItemId, RewardSlot, RewardItemId, RewardQuantity) VALUES ('200', 1, '123', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CraftingRewards (RecipeItemId, RewardSlot, RewardItemId, RewardQuantity) VALUES ('200', 2, '456', 1)"
            )
        )
        conn.commit()

    # Item '12' should NOT be obtainable (only '123' is in recipe)
    result = is_item_obtainable(test_engine, "12", "Item12")
    assert result is False, "Should not match partial item IDs in recipes"

    # Item '123' SHOULD be obtainable
    result = is_item_obtainable(test_engine, "123", "Item123")
    assert result is True, "Should match exact item ID in recipe"


def test_vendor_substring_does_not_match(
    test_engine: Engine = create_test_db(),
) -> None:
    """Vendor matching should not match substrings.

    Regression test: "Spell Scroll: Focus" should NOT match
    "Spell Scroll: Focus Target" in vendor inventory.
    """
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('focus1', 'Spell Scroll: Focus', 'SPELL SCROLL - Focus')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('focus2', 'Spell Scroll: Focus Target', 'SPELL SCROLL - Focus Target')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) "
                "VALUES (1, 'vendor1', 'Test Vendor')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Spell Scroll: Focus Target')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Other Item')"
            )
        )
        conn.commit()

    # Should NOT match (substring but not exact token)
    result = is_item_obtainable(test_engine, "focus1", "Spell Scroll: Focus")
    assert result is False, "Should not match substring of vendor item"

    # Should match (exact token)
    result = is_item_obtainable(test_engine, "focus2", "Spell Scroll: Focus Target")
    assert result is True, "Should match exact vendor item"


def test_vendor_exact_token_with_whitespace(
    test_engine: Engine = create_test_db(),
) -> None:
    """Vendor matching should handle whitespace properly."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('item1', 'Test Item', 'test_item')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) "
                "VALUES (1, 'vendor1', 'Shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, ' Test Item ')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, ' Other Item ')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, ' Third ')"
            )
        )
        conn.commit()

    # Should match despite extra whitespace in vendor list
    result = is_item_obtainable(test_engine, "item1", "Test Item")
    assert result is True, "Should match with whitespace normalization"


def test_vendor_case_insensitive_matching(
    test_engine: Engine = create_test_db(),
) -> None:
    """Vendor matching should be case-insensitive."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('item1', 'UPPER CASE', 'upper_case')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) "
                "VALUES (1, 'vendor1', 'Shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'upper case')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'other')"
            )
        )
        conn.commit()

    # Should match case-insensitively
    result = is_item_obtainable(test_engine, "item1", "UPPER CASE")
    assert result is True, "Should match case-insensitively"


def test_vendor_single_item_in_list(test_engine: Engine = create_test_db()) -> None:
    """Vendor matching should work for single-item lists."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('item1', 'Single Item', 'single_item')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) "
                "VALUES (1, 'vendor1', 'Shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Single Item')"
            )
        )
        conn.commit()

    # Should match single item
    result = is_item_obtainable(test_engine, "item1", "Single Item")
    assert result is True, "Should match single item in list"


def test_vendor_empty_string_does_not_match(
    test_engine: Engine = create_test_db(),
) -> None:
    """Vendor matching should not match empty strings."""
    with test_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO Items (Id, ItemName, ResourceName) "
                "VALUES ('empty1', '', 'empty_item')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO Characters (Id, Guid, NPCName) "
                "VALUES (1, 'vendor1', 'Shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Coral')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Fish')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO CharacterVendorItems (CharacterId, ItemName) "
                "VALUES (1, 'Bone')"
            )
        )
        conn.commit()

    # Empty string should NOT match any vendor items (even though it's a substring of all)
    result = is_item_obtainable(test_engine, "empty1", "")
    assert result is False, "Empty string should not match vendor items"
