"""Item service for business logic related to items."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

__all__ = ["is_item_obtainable"]


def is_item_obtainable(engine: Engine, item_id: str, item_name: str) -> bool:
    """Check if an item is obtainable in the game through any means.

    An item is considered obtainable if it can be acquired via:
    - Drops from characters (LootDrops)
    - Purchase from vendors (CharacterVendorItems)
    - Quest rewards (Quests.ItemOnCompleteId)
    - Quest dialog rewards (CharacterDialogs.GiveItemName)
    - Fishing (WaterFishables.ItemName)
    - Mining (MiningNodeItems.ItemName)
    - Crafting recipes (CraftingRewards)
    - World item bags (ItemBags.ItemId)

    Args:
        engine: Database engine
        item_id: Item ID to check
        item_name: Item name to check (used for name-based lookups)

    Returns:
        True if the item can be obtained through any acquisition method,
        False if the item has no known acquisition source.
    """
    with engine.connect() as conn:
        try:
            # Check if item is dropped by any character
            drops_sql = text(
                """
                SELECT 1 FROM LootDrops
                WHERE ItemId = :item_id
                AND COALESCE(DropProbability, 0.0) > 0.0
                LIMIT 1
                """
            )
            if conn.execute(drops_sql, {"item_id": item_id}).fetchone():
                return True
        except OperationalError:
            pass  # Table doesn't exist in test fixtures

        try:
            # Check if item is sold by any vendor (junction table)
            vendor_sql = text(
                """
                SELECT 1 FROM CharacterVendorItems
                WHERE lower(trim(ItemName)) = lower(trim(:item_name))
                LIMIT 1
                """
            )
            if conn.execute(vendor_sql, {"item_name": item_name}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is a quest reward
            quest_reward_sql = text(
                """
                SELECT 1 FROM Quests
                WHERE ItemOnCompleteId = :item_id
                LIMIT 1
                """
            )
            if conn.execute(quest_reward_sql, {"item_id": item_id}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is given through quest dialog
            quest_dialog_sql = text(
                """
                SELECT 1 FROM CharacterDialogs
                WHERE GiveItemName = :item_name
                LIMIT 1
                """
            )
            if conn.execute(quest_dialog_sql, {"item_name": item_name}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is obtainable via fishing
            fishing_sql = text(
                """
                SELECT 1 FROM WaterFishables
                WHERE ItemName = :item_name
                LIMIT 1
                """
            )
            if conn.execute(fishing_sql, {"item_name": item_name}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is obtainable via mining
            mining_sql = text(
                """
                SELECT 1 FROM MiningNodeItems
                WHERE ItemName = :item_name
                LIMIT 1
                """
            )
            if conn.execute(mining_sql, {"item_name": item_name}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is craftable (junction table)
            crafting_sql = text(
                """
                SELECT 1 FROM CraftingRewards
                WHERE RewardItemId = :item_id
                LIMIT 1
                """
            )
            if conn.execute(crafting_sql, {"item_id": item_id}).fetchone():
                return True
        except OperationalError:
            pass

        try:
            # Check if item is in a world item bag
            itembag_sql = text(
                """
                SELECT 1 FROM ItemBags
                WHERE ItemId = :item_id
                LIMIT 1
                """
            )
            if conn.execute(itembag_sql, {"item_id": item_id}).fetchone():
                return True
        except OperationalError:
            pass

    # No acquisition method found
    return False
