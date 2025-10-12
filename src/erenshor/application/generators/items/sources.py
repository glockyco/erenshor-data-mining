"""Source enrichment logic for items.

Handles vendor sources, drop sources, quest sources, and crafting sources.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.engine import Engine

from erenshor.domain.entities import DbItem
from erenshor.domain.value_objects.crafting import CraftingMaterial, CraftingReward
from erenshor.infrastructure.database.repositories import (
    get_characters_dropping_item,
    get_crafting_recipe,
    get_items_by_ids,
    get_items_producing_item,
    get_items_requiring_item,
    get_quest_by_dbname,
    get_quests_requiring_item,
    get_quests_rewarding_item,
    get_vendors_selling_item_by_name,
)
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import (
    COORDINATE_PRECISION,
    DROP_PROBABILITY_PRECISION,
)

__all__ = ["SourceEnricher", "QuestSources", "CraftingSources", "RecipeInfo"]


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuestSources:
    """Quest source information for an item."""

    reward_sources: list[str]  # Quests that reward this item
    requirement_sources: list[str]  # Quests that require this item


@dataclass(frozen=True)
class CraftingSources:
    """Crafting source information for an item."""

    craft_sources: list[str]  # Items/recipes that produce this item
    component_for: list[str]  # Items that require this as a component


@dataclass(frozen=True)
class RecipeInfo:
    """Recipe information for a mold item."""

    results: list[str]  # Items produced by this recipe
    ingredients: list[str]  # Materials required for this recipe


class SourceEnricher:
    """Enriches item sources from database.

    Queries database for vendors, droppers, quests, and crafting recipes,
    converting them to wiki links using the registry.
    """

    def __init__(
        self,
        engine: Engine,
        linker: RegistryLinkResolver,
    ) -> None:
        """Initialize source enricher with database engine and link resolver.

        Args:
            engine: SQLAlchemy engine for database queries
            linker: Link resolver for wiki page links
        """
        self.engine = engine
        self.linker = linker

    def _build_stable_identifier(self, character_data: dict[str, Any]) -> str:
        """Build stable identifier for character registry lookup.

        Args:
            character_data: Character data dict with ObjectName, Scene, X, Y, Z, IsPrefab

        Returns:
            Stable identifier string for registry lookup
        """
        if character_data.get("IsPrefab") and character_data.get("ObjectName"):
            return str(character_data.get("ObjectName") or "")

        scene = character_data.get("Scene") or "Unknown"
        coord_x = f"{float(character_data.get('X') or 0):.{COORDINATE_PRECISION}f}"
        coord_y = f"{float(character_data.get('Y') or 0):.{COORDINATE_PRECISION}f}"
        coord_z = f"{float(character_data.get('Z') or 0):.{COORDINATE_PRECISION}f}"
        object_name = character_data.get("ObjectName") or ""

        return f"{object_name}|{scene}|{coord_x}|{coord_y}|{coord_z}"


    def _format_crafting_items(
        self,
        items: list[CraftingReward] | list[CraftingMaterial],
        get_item_id: Callable[[Any], str],
        get_quantity: Callable[[Any], int],
        get_slot: Callable[[Any], int],
    ) -> list[str]:
        """Format crafting items (rewards or materials) with quantities.

        Generic helper that handles both CraftingReward and CraftingMaterial
        by using accessor functions to extract the relevant fields.

        Args:
            items: List of crafting rewards or materials
            get_item_id: Function to extract item ID (e.g., lambda r: r.reward_item_id)
            get_quantity: Function to extract quantity (e.g., lambda r: r.reward_quantity)
            get_slot: Function to extract slot (e.g., lambda r: r.reward_slot)

        Returns:
            List of formatted item links with quantities ("3x Item Name" or "Item Name")
        """
        if not items:
            return []

        # Sort by slot to preserve recipe order
        sorted_items = sorted(items, key=get_slot)

        # Extract item IDs and build quantity map
        item_ids = [get_item_id(item) for item in sorted_items]
        quantity_map = {get_item_id(item): get_quantity(item) for item in sorted_items}

        db_items = get_items_by_ids(self.engine, item_ids)

        formatted = []
        for db_item in db_items:
            quantity = quantity_map.get(db_item.Id, 1)

            link = self.linker.item_link(
                db_item.ResourceName,
                db_item.ItemName,
                db_item.Id,
            )

            # Always show quantity for consistency
            formatted.append(f"{quantity}x {link}")

        return formatted

    def get_vendor_sources(self, item: DbItem) -> list[str]:
        """Get vendor sources for an item.

        Args:
            item: Item to query

        Returns:
            List of vendor link strings
        """
        logger.debug(f"Fetching vendors for item: {item.ItemName} (ID: {item.Id})")
        vendor_sources: list[str] = []
        vendors = get_vendors_selling_item_by_name(self.engine, item.ItemName)

        if not vendors:
            logger.debug(f"No vendors sell {item.ItemName}")
            return vendor_sources

        logger.debug(f"Found {len(vendors)} vendors for {item.ItemName}")
        for vendor_data in vendors:
            vendor_name = vendor_data.get("NPCName") or ""
            if not vendor_name:
                logger.debug(f"Skipping vendor with no NPCName for {item.ItemName}")
                continue

            stable_identifier = self._build_stable_identifier(vendor_data)

            # Create EntityRef for link resolver
            from erenshor.domain.entities.page import EntityRef
            from erenshor.domain.value_objects.entity_type import EntityType

            vendor_guid = vendor_data.get("Guid")
            entity_ref = EntityRef(
                entity_type=EntityType.CHARACTER,
                db_id=vendor_guid,
                db_name=vendor_name,
                resource_name=stable_identifier,
            )
            vendor_link = self.linker.character_link(entity_ref)
            vendor_sources.append(vendor_link)

        logger.debug(
            f"Generated {len(vendor_sources)} vendor links for {item.ItemName}"
        )
        return vendor_sources

    def get_drop_sources(self, item: DbItem) -> list[str]:
        """Get drop sources for an item.

        Args:
            item: Item to query

        Returns:
            List of drop link strings with percentages
        """
        logger.debug(f"Fetching drop sources for item: {item.ItemName} (ID: {item.Id})")
        drop_sources: list[str] = []
        droppers = get_characters_dropping_item(self.engine, item.Id)

        if not droppers:
            logger.debug(f"No characters drop {item.ItemName}")
            return drop_sources

        logger.debug(f"Found {len(droppers)} droppers for {item.ItemName}")
        for dropper_data in droppers:
            dropper_name = dropper_data.get("NPCName") or ""
            if not dropper_name:
                logger.debug(f"Skipping dropper with no NPCName for {item.ItemName}")
                continue

            stable_identifier = self._build_stable_identifier(dropper_data)

            # Create EntityRef for link resolver
            from erenshor.domain.entities.page import EntityRef
            from erenshor.domain.value_objects.entity_type import EntityType

            dropper_guid = dropper_data.get("Guid")
            entity_ref = EntityRef(
                entity_type=EntityType.CHARACTER,
                db_id=dropper_guid,
                db_name=dropper_name,
                resource_name=stable_identifier,
            )
            character_link = self.linker.character_link(entity_ref)

            drop_probability = float(dropper_data.get("DropProbability", 0.0))
            formatted_link = (
                f"{character_link} ({drop_probability:.{DROP_PROBABILITY_PRECISION}f}%)"
            )
            drop_sources.append(formatted_link)

        logger.debug(f"Generated {len(drop_sources)} drop links for {item.ItemName}")
        return drop_sources

    def get_quest_sources(self, item: DbItem) -> QuestSources:
        """Get quest reward and requirement sources.

        Args:
            item: Item to query

        Returns:
            QuestSources with reward and requirement quest links
        """
        logger.debug(
            f"Fetching quest sources for item: {item.ItemName} (ID: {item.Id})"
        )

        reward_sources: list[str] = []
        rewarding_quests = get_quests_rewarding_item(self.engine, item.Id)
        logger.debug(f"Found {len(rewarding_quests)} quests rewarding {item.ItemName}")

        for quest_data in rewarding_quests:
            db_name = quest_data.get("DBName") or ""
            quest_name = quest_data.get("QuestName") or ""
            if db_name and quest_name:
                reward_sources.append(self.linker.quest_link(db_name, quest_name))

        requirement_sources: list[str] = []
        requiring_quests = get_quests_requiring_item(self.engine, item.Id)
        logger.debug(f"Found {len(requiring_quests)} quests requiring {item.ItemName}")

        for quest_data in requiring_quests:
            db_name = quest_data.get("DBName") or ""
            quest_name = quest_data.get("QuestName") or ""
            if db_name and quest_name:
                requirement_sources.append(self.linker.quest_link(db_name, quest_name))

        logger.debug(
            f"Generated {len(reward_sources)} reward and {len(requirement_sources)} "
            f"requirement quest links for {item.ItemName}"
        )
        return QuestSources(
            reward_sources=reward_sources,
            requirement_sources=requirement_sources,
        )

    def get_crafting_sources(self, item: DbItem) -> CraftingSources:
        """Get crafting sources and component usages.

        Queries items that produce this item (craft sources) and items that
        require this item as a component (component for).

        Uses CraftingRewards and CraftingRecipes junction tables.

        Args:
            item: Item to query

        Returns:
            CraftingSources with craft sources and component usage links
        """
        logger.debug(
            f"Fetching crafting sources for item: {item.ItemName} (ID: {item.Id})"
        )

        craft_sources: list[str] = []
        producing_items = get_items_producing_item(self.engine, item.Id)
        logger.debug(f"Found {len(producing_items)} items producing {item.ItemName}")

        for producer_item in producing_items:
            # Use enriched CraftingMaterials field from junction table
            materials = producer_item.CraftingMaterials or []
            ingredient_links = self._format_crafting_items(
                materials,
                get_item_id=lambda m: m.material_item_id,
                get_quantity=lambda m: m.material_quantity,
                get_slot=lambda m: m.material_slot,
            )

            producer_link = self.linker.item_link(
                producer_item.ResourceName,
                producer_item.ItemName,
                producer_item.Id,
            )
            # Add 1x prefix to mold for consistency with materials
            craft_sources.append(f"1x {producer_link}")
            craft_sources.extend(ingredient_links)

        component_for: list[str] = []
        requiring_items = get_items_requiring_item(self.engine, item.Id)
        logger.debug(f"Found {len(requiring_items)} items requiring {item.ItemName}")

        for requiring_item in requiring_items:
            component_for.append(
                self.linker.item_link(
                    requiring_item.ResourceName,
                    requiring_item.ItemName,
                    requiring_item.Id,
                )
            )

        logger.debug(
            f"Generated {len(craft_sources)} craft sources and {len(component_for)} "
            f"component usage links for {item.ItemName}"
        )
        return CraftingSources(
            craft_sources=craft_sources,
            component_for=component_for,
        )

    def get_recipe_info(self, item: DbItem) -> RecipeInfo:
        """Get recipe results and ingredients for a mold item.

        Uses CraftingRecipe repository method to fetch structured recipe data
        from junction tables. No CSV fallback - all data must come from junction tables.

        Args:
            item: Item to query

        Returns:
            RecipeInfo with results and ingredients
        """
        logger.debug(f"Fetching recipe info for item: {item.ItemName} (ID: {item.Id})")

        # Query repository for complete recipe
        recipe = get_crafting_recipe(self.engine, item.Id)
        if not recipe:
            logger.debug(f"No recipe found for {item.ItemName}")
            return RecipeInfo(results=[], ingredients=[])

        logger.debug(
            f"Found recipe for {item.ItemName} with {len(recipe.rewards)} rewards "
            f"and {len(recipe.materials)} materials"
        )

        crafting_results = self._format_crafting_items(
            recipe.rewards,
            get_item_id=lambda r: r.reward_item_id,
            get_quantity=lambda r: r.reward_quantity,
            get_slot=lambda r: r.reward_slot,
        )

        recipe_ingredients = self._format_crafting_items(
            recipe.materials,
            get_item_id=lambda m: m.material_item_id,
            get_quantity=lambda m: m.material_quantity,
            get_slot=lambda m: m.material_slot,
        )

        logger.debug(
            f"Generated {len(crafting_results)} result links and {len(recipe_ingredients)} "
            f"ingredient links for {item.ItemName}"
        )
        return RecipeInfo(
            results=crafting_results,
            ingredients=recipe_ingredients,
        )

    def get_quest_completion_link(self, item: DbItem) -> list[str]:
        """Get quest completion links for quest items.

        Args:
            item: Item to query

        Returns:
            List of quest links
        """
        logger.debug(
            f"Fetching quest completion link for item: {item.ItemName} (ID: {item.Id})"
        )
        related_quests: list[str] = []
        complete_on_read = getattr(item, "CompleteOnRead", None)

        if not complete_on_read:
            logger.debug(f"Item {item.ItemName} has no CompleteOnRead field")
            return related_quests

        logger.debug(f"Item {item.ItemName} completes quest: {complete_on_read}")
        quest_data = get_quest_by_dbname(self.engine, complete_on_read)
        if quest_data:
            quest_display_name = quest_data.get("QuestName") or ""
            if quest_display_name:
                quest_link = self.linker.quest_link(
                    complete_on_read, quest_display_name
                )
                related_quests.append(quest_link)
                logger.debug(
                    f"Generated quest completion link for {item.ItemName}: {quest_link}"
                )
        else:
            logger.warning(
                f"Quest {complete_on_read} not found for item {item.ItemName}"
            )

        return related_quests

    def get_auto_sources(
        self, item: DbItem, fishable_names: set[str], mining_names: set[str]
    ) -> list[str]:
        """Get auto-enriched sources (fishing, mining).

        Args:
            item: Item to check
            fishable_names: Set of fishable item names (lowercase)
            mining_names: Set of mining item names (lowercase)

        Returns:
            List of auto source links
        """
        logger.debug(f"Checking auto sources for item: {item.ItemName} (ID: {item.Id})")
        auto_sources: list[str] = []
        item_name_lower = item.ItemName.lower()

        if item_name_lower in fishable_names:
            auto_sources.append("[[Fishing]]")
            logger.debug(f"Item {item.ItemName} is fishable")

        if item_name_lower in mining_names:
            auto_sources.append("[[Mining]]")
            logger.debug(f"Item {item.ItemName} is from mining")

        if auto_sources:
            logger.debug(
                f"Generated {len(auto_sources)} auto source links for {item.ItemName}"
            )
        else:
            logger.debug(f"No auto sources found for {item.ItemName}")

        return auto_sources
