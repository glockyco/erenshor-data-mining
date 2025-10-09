"""Repository protocols (interfaces for data access)."""

from __future__ import annotations

from typing import Any, Protocol

from erenshor.domain.entities.character import DbCharacter
from erenshor.domain.entities.item import DbItem, DbItemStats
from erenshor.domain.entities.recipe import CraftingRecipe
from erenshor.domain.entities.spell import DbSkill, DbSpell

__all__ = [
    "CharacterRepository",
    "ItemRepository",
    "SpellRepository",
    "QuestRepository",
]


class ItemRepository(Protocol):
    """Protocol for accessing item data."""

    def get_all_items(self) -> list[DbItem]:
        """Retrieve all items from the database."""
        ...

    def get_item_by_id(self, item_id: int) -> DbItem | None:
        """Retrieve a specific item by its ID."""
        ...

    def get_item_stats(self, item_id: str) -> list[DbItemStats]:
        """Retrieve quality-based stats for an item."""
        ...

    def get_items_by_ids(self, item_ids: list[str]) -> list[DbItem]:
        """Fetch items by a list of IDs.

        Args:
            item_ids: List of item IDs to retrieve

        Returns:
            List of DbItem entities with Id, ItemName, ResourceName populated
        """
        ...

    def get_items_producing_item(self, item_id: str) -> list[DbItem]:
        """Get items whose crafting recipe produces the given item.

        Args:
            item_id: ID of the item to search for as a crafting reward

        Returns:
            List of DbItem entities representing molds/templates that produce this item

        Note:
            Uses CraftingRewards junction table for lookups
        """
        ...

    def get_items_requiring_item(self, item_id: str) -> list[DbItem]:
        """Get items whose crafting recipe requires the given item as material.

        Args:
            item_id: ID of the item to search for as a crafting material

        Returns:
            List of DbItem entities representing molds/templates that require this item

        Note:
            Uses CraftingRecipes junction table for lookups
        """
        ...

    def get_crafting_recipe(self, item_id: str) -> CraftingRecipe | None:
        """Get crafting recipe for an item (mold).

        Queries CraftingMaterials and CraftingRewards junction tables to build
        a complete recipe with materials and rewards.

        Args:
            item_id: Database ID of the mold/template item

        Returns:
            CraftingRecipe with materials and rewards, or None if item has no recipe

        Raises:
            JunctionEnrichmentError: If junction data is malformed or database error occurs
        """
        ...


class CharacterRepository(Protocol):
    """Protocol for accessing character data."""

    def get_all_characters(self) -> list[DbCharacter]:
        """Retrieve all characters from the database."""
        ...

    def get_character_by_guid(self, guid: str) -> DbCharacter | None:
        """Retrieve a specific character by its GUID."""
        ...

    def get_vendors_selling_item_by_name(self, item_name: str) -> list[dict[str, Any]]:
        """Get all vendors that sell an item by name.

        Args:
            item_name: Name of the item to search for

        Returns:
            List of character dictionaries representing vendors
        """
        ...

    def get_characters_dropping_item(self, item_id: str) -> list[dict[str, Any]]:
        """Get characters that drop a given item.

        Args:
            item_id: ID of the item

        Returns:
            List of character dictionaries with drop probability information
        """
        ...


class SpellRepository(Protocol):
    """Protocol for accessing spell and skill data."""

    def get_all_spells(self) -> list[DbSpell]:
        """Retrieve all spells from the database."""
        ...

    def get_all_skills(self) -> list[DbSkill]:
        """Retrieve all skills from the database."""
        ...

    def get_spell_by_id(self, spell_id: str) -> DbSpell | None:
        """Retrieve a specific spell by its ID."""
        ...


class QuestRepository(Protocol):
    """Protocol for accessing quest data."""

    def get_quests_rewarding_item(self, item_id: str) -> list[dict[str, Any]]:
        """Get quests that reward a given item.

        Args:
            item_id: ID of the item

        Returns:
            List of quest dictionaries
        """
        ...

    def get_quests_requiring_item(self, item_id: str) -> list[dict[str, Any]]:
        """Get quests that require a given item.

        Args:
            item_id: ID of the item

        Returns:
            List of quest dictionaries
        """
        ...

    def get_quest_by_dbname(self, db_name: str) -> dict[str, Any] | None:
        """Get quest record by DBName.

        Args:
            db_name: Database name of the quest

        Returns:
            Quest dictionary or None if not found
        """
        ...
