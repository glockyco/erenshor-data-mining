"""Category tag generation for wiki pages.

This module generates MediaWiki category tags programmatically based on entity properties,
supporting multi-category items and clean separation from template logic.

Categories are determined by:
- Item kind (weapon, armor, consumable, etc.)
- Item properties (quest items, crafting materials)
- Entity type (character, spell, etc.)

Design principles:
- Categories are separate from templates (not template-based)
- Multi-category support (items can belong to multiple categories)
- Type-safe with domain models
- Easy to extend with new category rules
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from erenshor.application.services.character_enricher import EnrichedCharacterData
    from erenshor.domain.entities.item import Item
    from erenshor.registry.resolver import RegistryResolver

__all__ = ["CategoryGenerator", "ItemKind", "classify_item_kind"]


# Import from existing classifier
from erenshor.registry.item_classifier import ItemKind, classify_item_kind


class CategoryGenerator:
    """Generate category tags for wiki pages.

    This class determines which MediaWiki categories an entity should belong to
    based on its type and properties. Categories are returned as a list of names
    without the [[Category:...]] wrapper, which is added during page generation.

    Examples:
        >>> resolver = RegistryResolver(...)
        >>> generator = CategoryGenerator(resolver)
        >>> item = Item(required_slot="Primary", ...)
        >>> categories = generator.generate_item_categories(item)
        >>> categories
        ['Weapons']

        >>> mold = Item(template=1, required_slot="General", ...)
        >>> categories = generator.generate_item_categories(mold)
        >>> categories
        ['Molds', 'Crafting Materials']
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize CategoryGenerator with registry resolver.

        Args:
            resolver: Registry resolver for display name lookups
        """
        self._resolver = resolver

    # Mapping from ItemKind to primary category name
    ITEM_KIND_TO_CATEGORY: ClassVar[dict[ItemKind, str]] = {
        ItemKind.WEAPON: "Weapons",
        ItemKind.ARMOR: "Armor",
        ItemKind.AURA: "Auras",
        ItemKind.ABILITY_BOOK: "Ability Books",
        ItemKind.CONSUMABLE: "Consumables",
        ItemKind.MOLD: "Molds",
        ItemKind.GENERAL: "Items",
    }

    def generate_item_categories(self, item: Item) -> list[str]:
        """Generate category tags for an item.

        Determines categories based on:
        1. Item kind (weapon, armor, consumable, etc.) → primary category
        2. Item properties → secondary categories

        Args:
            item: Item entity to generate categories for

        Returns:
            List of category names (without [[Category:...]] wrapper)
            Always includes at least one category (primary from item kind)

        Examples:
            Weapon:
                >>> item = Item(required_slot="Primary", ...)
                >>> generate_item_categories(item)
                ['Weapons']

            Mold (multi-category):
                >>> item = Item(template=1, required_slot="General", ...)
                >>> generate_item_categories(item)
                ['Molds', 'Crafting Materials']

            Quest Item (cross-cutting category):
                >>> item = Item(assign_quest_on_read="SomeQuest", ...)
                >>> generate_item_categories(item)
                ['Items', 'Quest Items']
        """
        categories: list[str] = []

        # Determine item kind using existing classifier
        kind = classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable) if item.disposable is not None else None,
        )

        # Add primary category from item kind
        primary_category = self.ITEM_KIND_TO_CATEGORY.get(kind, "Items")
        categories.append(primary_category)

        # Add secondary categories based on properties

        # Quest Items - items that interact with quests
        if self._is_quest_item(item):
            categories.append("Quest Items")

        # Crafting Materials - molds are crafting templates
        # Note: template=1 means this is a crafting mold/template
        if item.template == 1 and "Crafting Materials" not in categories:
            categories.append("Crafting Materials")

        return categories

    def _is_quest_item(self, item: Item) -> bool:
        """Check if item is a quest item.

        Quest items are items that:
        - Assign a quest when read (quest starter items)
        - Complete a quest when read (quest completion items)

        Args:
            item: Item to check

        Returns:
            True if item has quest interactions
        """
        return bool(
            (item.assign_quest_on_read_stable_key and item.assign_quest_on_read_stable_key.strip())
            or (item.complete_on_read_stable_key and item.complete_on_read_stable_key.strip())
        )

    def generate_character_categories(self, enriched: EnrichedCharacterData) -> list[str]:
        """Generate category tags for a character.

        Determines categories based on:
        1. Spawn locations → zone categories
        2. Character type (Enemy/Rare/Boss) → type category
        3. Vendor status → Vendor category

        Args:
            enriched: Enriched character data with spawn info

        Returns:
            List of category names (without [[Category:...]] wrapper)

        Examples:
            Boss in Port Azure:
                >>> categories
                ['Port Azure', 'Bosses']

            Vendor NPC in multiple zones:
                >>> categories
                ['Fernalla's Revival Plains', 'Port Azure', 'Vendors']
        """
        categories: list[str] = []

        # Add zone categories from spawn locations
        zone_page_titles = sorted(
            {
                title
                for info in enriched.spawn_infos
                if (title := self._resolver.resolve_page_title(info.zone_stable_key)) is not None
            }
        )
        categories.extend(zone_page_titles)

        # Add type category
        character = enriched.character
        if character.is_friendly:
            categories.append("Characters")
        else:
            categories.append("Enemies")

            # Add Bosses category for unique enemies
            if character.is_unique:
                categories.append("Bosses")

        # Add Vendor category
        if character.is_vendor:
            categories.append("Vendors")

        return categories

    def format_category_tags(self, categories: list[str]) -> str:
        """Format category names as MediaWiki category tags.

        Converts category names to full MediaWiki syntax with [[Category:...]] wrapper.
        Categories are joined with newlines for proper wiki formatting.

        Args:
            categories: List of category names (e.g., ["Weapons", "Quest Items"])

        Returns:
            Formatted wikitext with category tags, one per line

        Examples:
            >>> format_category_tags(["Weapons"])
            '[[Category:Weapons]]'

            >>> format_category_tags(["Molds", "Crafting Materials"])
            '[[Category:Molds]]\\n[[Category:Crafting Materials]]'
        """
        return "\n".join(f"[[Category:{cat}]]" for cat in categories)
