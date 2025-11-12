"""Item enrichment service for wiki generation.

This service aggregates and formats all item-related data for wiki template generation:
- Item stats for quality variants (Normal/Blessed/Godly)
- Class restrictions from ItemClasses junction table
- Proc information (spell/skill triggered by item)
- Vendor sources
- Drop sources (character drops with probabilities)
- Quest sources (quest rewards and requirements)
- Crafting sources (recipes, materials, components)
"""

from loguru import logger

from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.source_info import SourceInfo
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository

__all__ = [
    "EnrichedItemData",
    "ItemEnricher",
    "ProcInfo",
    "SourceInfo",
]


class ItemEnricher:
    """Service for enriching items with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        item_repo: ItemRepository,
        spell_repo: SpellRepository,
        character_repo: CharacterRepository,
        quest_repo: QuestRepository,
    ) -> None:
        """Initialize item enricher.

        Args:
            item_repo: Repository for item data (stats, classes, crafting, etc.)
            spell_repo: Repository for spell data (for proc lookup)
            character_repo: Repository for character data (vendors, droppers)
            quest_repo: Repository for quest data (rewards, requirements)
        """
        self._item_repo = item_repo
        self._spell_repo = spell_repo
        self._character_repo = character_repo
        self._quest_repo = quest_repo

    def enrich(self, item: Item) -> EnrichedItemData:
        """Enrich item with related data from other tables.

        Args:
            item: Item entity

        Returns:
            EnrichedItemData with stats, classes, proc info, sources, and other related data
        """
        logger.debug(f"Enriching item: {item.item_name}")

        # Get quality variant stats (Normal/Blessed/Godly)
        stats = self._item_repo.get_item_stats(item.stable_key)

        # Get class restrictions from junction table
        classes = self._item_repo.get_item_classes(item.stable_key)

        # Extract proc information
        proc = self._extract_proc(item)

        # Get source information
        sources = self._get_sources(item)

        return EnrichedItemData(
            item=item,
            stats=stats,
            classes=classes,
            proc=proc,
            sources=sources,
        )

    def _extract_proc(self, item: Item) -> ProcInfo | None:
        """Extract proc information from item.

        Priority order (based on legacy implementation):

        For weapons:
        1. WeaponProcOnHit (with WeaponProcChance) - style: "Bash" if shield, else "Attack"
        2. WandEffect (with WandProcChance) - style: "Attack"
        3. BowEffect (with BowProcChance) - style: "Attack"
        4. ItemEffectOnClick - style: "Activatable" (no chance)

        For armor:
        1. WeaponProcOnHit (with WeaponProcChance) - style: "Cast"
        2. WornEffect - style: "Worn" (no chance)
        3. ItemEffectOnClick - style: "Activatable" (no chance)

        Args:
            item: Item to extract proc from

        Returns:
            ProcInfo if item has a proc, None otherwise
        """
        # Determine if this is a weapon or armor
        is_weapon_slot = item.required_slot in ("Primary", "Secondary", "PrimaryOrSecondary")

        # Priority 1: WeaponProcOnHit (used by both weapons and armor)
        if item.weapon_proc_on_hit_stable_key and (item.weapon_proc_chance or 0) > 0:
            spell = self._spell_repo.get_spell_by_stable_key(item.weapon_proc_on_hit_stable_key)
            if spell:
                # Style depends on item type
                if is_weapon_slot:
                    proc_style = "Bash" if item.shield else "Attack"
                else:
                    proc_style = "Cast"

                return ProcInfo(
                    stable_key=item.weapon_proc_on_hit_stable_key,
                    description=spell.spell_desc or "",
                    proc_chance=str(int(item.weapon_proc_chance)) if item.weapon_proc_chance is not None else "0",
                    proc_style=proc_style,
                )

        # Priority 2: WandEffect (weapons only)
        elif item.wand_effect_stable_key and (item.wand_proc_chance or 0) > 0:
            spell = self._spell_repo.get_spell_by_stable_key(item.wand_effect_stable_key)
            if spell:
                return ProcInfo(
                    stable_key=item.wand_effect_stable_key,
                    description=spell.spell_desc or "",
                    proc_chance=str(int(item.wand_proc_chance)) if item.wand_proc_chance is not None else "0",
                    proc_style="Attack",
                )

        # Priority 3: BowEffect (weapons only)
        elif item.bow_effect_stable_key and (item.bow_proc_chance or 0) > 0:
            spell = self._spell_repo.get_spell_by_stable_key(item.bow_effect_stable_key)
            if spell:
                return ProcInfo(
                    stable_key=item.bow_effect_stable_key,
                    description=spell.spell_desc or "",
                    proc_chance=str(int(item.bow_proc_chance)) if item.bow_proc_chance is not None else "0",
                    proc_style="Attack",
                )

        # Priority 4: WornEffect (armor only, no chance)
        elif item.worn_effect_stable_key:
            spell = self._spell_repo.get_spell_by_stable_key(item.worn_effect_stable_key)
            if spell:
                return ProcInfo(
                    stable_key=item.worn_effect_stable_key,
                    description=spell.spell_desc or "",
                    proc_chance="",
                    proc_style="Worn",
                )

        # Priority 5: ItemEffectOnClick (both weapons and armor, activatable, no chance)
        elif item.item_effect_on_click_stable_key:
            spell = self._spell_repo.get_spell_by_stable_key(item.item_effect_on_click_stable_key)
            if spell:
                return ProcInfo(
                    stable_key=item.item_effect_on_click_stable_key,
                    description=spell.spell_desc or "",
                    proc_chance="",
                    proc_style="Activatable",
                )

        # No proc found
        return None

    def _get_sources(self, item: Item) -> SourceInfo:
        """Get all source information for an item.

        Args:
            item: Item to get sources for

        Returns:
            SourceInfo with vendors, drops, quests, and crafting sources
        """
        logger.debug(f"Getting sources for item: {item.item_name}")

        # Get vendor sources
        vendors = self._get_vendor_sources(item)

        # Get drop sources
        drops = self._get_drop_sources(item)

        # Get quest sources (returns tuple of reward/requirement lists)
        quest_rewards, quest_requirements = self._get_quest_sources(item)

        # Get crafting sources (returns tuple of 5 lists)
        craft_sources, craft_recipe, component_for, crafting_results, recipe_ingredients = self._get_crafting_sources(
            item
        )

        return SourceInfo(
            vendors=vendors,
            drops=drops,
            quest_rewards=quest_rewards,
            quest_requirements=quest_requirements,
            craft_sources=craft_sources,
            craft_recipe=craft_recipe,
            component_for=component_for,
            crafting_results=crafting_results,
            recipe_ingredients=recipe_ingredients,
        )

    def _get_vendor_sources(self, item: Item) -> list[str]:
        """Get vendors selling this item.

        Args:
            item: Item to query

        Returns:
            List of character stable keys
        """
        vendor_rows = self._character_repo.get_vendors_selling_item(item.stable_key)
        vendors = [str(row["StableKey"]) for row in vendor_rows]
        logger.debug(f"Found {len(vendors)} vendors for {item.item_name}")
        return vendors

    def _get_drop_sources(self, item: Item) -> list[tuple[str, float]]:
        """Get characters dropping this item.

        Args:
            item: Item to query

        Returns:
            List of (character_stable_key, drop_probability) tuples
        """
        drop_rows = self._character_repo.get_characters_dropping_item(item.stable_key)
        drops = [
            (
                str(row["StableKey"]),
                float(row["DropProbability"]) if row["DropProbability"] is not None else 0.0,
            )
            for row in drop_rows
        ]
        logger.debug(f"Found {len(drops)} drop sources for {item.item_name}")
        return drops

    def _get_quest_sources(self, item: Item) -> tuple[list[str], list[str]]:
        """Get quests rewarding or requiring this item.

        Args:
            item: Item to query

        Returns:
            Tuple of (quest_reward_stable_keys, quest_requirement_stable_keys)
        """
        # Get quests rewarding this item
        reward_quests = self._quest_repo.get_quests_rewarding_item(item.stable_key)

        # Get quests requiring this item
        requirement_quests = self._quest_repo.get_quests_requiring_item(item.stable_key)

        logger.debug(
            f"Found {len(reward_quests)} reward quests and {len(requirement_quests)} "
            f"requirement quests for {item.item_name}"
        )
        return (reward_quests, requirement_quests)

    def _get_crafting_sources(
        self, item: Item
    ) -> tuple[list[str], list[tuple[str, int]], list[str], list[tuple[str, int]], list[tuple[str, int]]]:
        """Get crafting sources for this item.

        Args:
            item: Item to query

        Returns:
            Tuple of (craft_sources, craft_recipe, component_for, crafting_results, recipe_ingredients)
            - craft_sources: Item stable keys of molds that produce this item
            - craft_recipe: Full recipe to craft this item (mold + all ingredients with quantities)
            - component_for: Item stable keys that require this as component
            - crafting_results: What this mold produces (item_stable_key, quantity)
            - recipe_ingredients: What this mold needs (item_stable_key, quantity)
        """
        # Get items that produce this item (craft_sources)
        craft_sources = self._item_repo.get_items_producing_item(item.stable_key)

        # Get full recipe to craft this item (mold + ingredients from first mold that produces it)
        craft_recipe: list[tuple[str, int]] = []
        if craft_sources:
            # Use first mold's recipe
            mold_stable_key = craft_sources[0]
            mold_recipe = self._item_repo.get_crafting_recipe(mold_stable_key)
            if mold_recipe:
                # Add mold itself (1x quantity)
                craft_recipe.append((mold_stable_key, 1))

                # Add all ingredients from the mold's recipe
                materials = sorted(mold_recipe.get("materials", []), key=lambda m: m.get("MaterialSlot", 0))
                for material_row in materials:
                    stable_key = str(material_row.get("MaterialItemStableKey") or "")
                    quantity = int(material_row.get("MaterialQuantity", 1))
                    if stable_key:
                        craft_recipe.append((stable_key, quantity))

        # Get items that require this item (component_for)
        component_for = self._item_repo.get_items_requiring_item(item.stable_key)

        # Get recipe info if this is a mold
        recipe = self._item_repo.get_crafting_recipe(item.stable_key)
        crafting_results: list[tuple[str, int]] = []
        recipe_ingredients: list[tuple[str, int]] = []

        if recipe:
            # Extract rewards (what this mold produces) - sorted by slot
            rewards = sorted(recipe.get("rewards", []), key=lambda r: r.get("RewardSlot", 0))
            for reward_row in rewards:
                stable_key = str(reward_row.get("RewardItemStableKey") or "")
                quantity = int(reward_row.get("RewardQuantity", 1))
                if stable_key:
                    crafting_results.append((stable_key, quantity))

            # Extract materials (what this mold needs) - sorted by slot
            materials = sorted(recipe.get("materials", []), key=lambda m: m.get("MaterialSlot", 0))
            for material_row in materials:
                stable_key = str(material_row.get("MaterialItemStableKey") or "")
                quantity = int(material_row.get("MaterialQuantity", 1))
                if stable_key:
                    recipe_ingredients.append((stable_key, quantity))

        logger.debug(
            f"Found {len(craft_sources)} craft sources, {len(craft_recipe)} craft recipe items, "
            f"{len(component_for)} component usages, {len(crafting_results)} crafting results, "
            f"and {len(recipe_ingredients)} recipe ingredients for {item.item_name}"
        )
        return (craft_sources, craft_recipe, component_for, crafting_results, recipe_ingredients)
