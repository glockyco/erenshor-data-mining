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

from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.character import EnrichedCharacterData
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.enriched_data.skill import EnrichedSkillData
    from erenshor.domain.enriched_data.spell import EnrichedSpellData
    from erenshor.domain.enriched_data.stance import EnrichedStanceData
    from erenshor.domain.entities.item import Item

__all__ = ["CategoryGenerator", "ItemKind", "classify_item_kind"]


class CategoryGenerator:
    """Generate category tags for wiki pages.

    This class determines which MediaWiki categories an entity should belong to
    based on its type and properties. Categories are returned as a list of names
    without the [[Category:...]] wrapper, which is added during page generation.

    Examples:
        >>> generator = CategoryGenerator()
        >>> item = Item(required_slot="Primary", ...)
        >>> categories = generator.generate_item_categories(item)
        >>> categories
        ['Weapons']

        >>> mold = Item(template=1, required_slot="General", ...)
        >>> categories = generator.generate_item_categories(mold)
        >>> categories
        ['Molds', 'Crafting']
    """

    def __init__(self) -> None:
        pass

    def generate_categories(
        self,
        enriched: EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData,
    ) -> list[str]:
        """Generate category list for any enriched entity."""
        from erenshor.domain.enriched_data.character import EnrichedCharacterData
        from erenshor.domain.enriched_data.item import EnrichedItemData
        from erenshor.domain.enriched_data.skill import EnrichedSkillData
        from erenshor.domain.enriched_data.spell import EnrichedSpellData
        from erenshor.domain.enriched_data.stance import EnrichedStanceData

        if isinstance(enriched, EnrichedItemData):
            return self.generate_item_categories(enriched)
        if isinstance(enriched, EnrichedCharacterData):
            return self.generate_character_categories(enriched)
        if isinstance(enriched, (EnrichedSpellData, EnrichedSkillData, EnrichedStanceData)):
            return []
        return []

    # Mapping from ItemKind to primary category name
    ITEM_KIND_TO_CATEGORY: ClassVar[dict[ItemKind, str]] = {
        ItemKind.WEAPON: "Weapons",
        ItemKind.ARMOR: "Armor",
        ItemKind.CHARM: "Charms",
        ItemKind.AURA: "Auras",
        ItemKind.SPELL_SCROLL: "Ability Books",
        ItemKind.SKILL_BOOK: "Ability Books",
        ItemKind.CONSUMABLE: "Consumables",
        ItemKind.MOLD: "Molds",
        ItemKind.GENERAL: "Items",
    }

    def generate_item_categories(self, enriched: EnrichedItemData) -> list[str]:
        """Generate category tags for an item.

        Determines categories based on:
        1. Item kind (weapon, armor, consumable, etc.) → primary category
        2. Item properties → secondary categories
        """
        item = enriched.item
        categories: list[str] = []

        kind = classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable) if item.disposable is not None else None,
        )

        primary_category = self.ITEM_KIND_TO_CATEGORY.get(kind, "Items")
        categories.append(primary_category)

        if self._is_quest_item(item):
            categories.append("Quest Items")

        if item.template == 1 and "Crafting" not in categories:
            categories.append("Crafting")

        return categories

    def _is_quest_item(self, item: Item) -> bool:
        """Check if item is a quest item."""
        return bool(
            (item.assign_quest_on_read_stable_key and item.assign_quest_on_read_stable_key.strip())
            or (item.complete_on_read_stable_key and item.complete_on_read_stable_key.strip())
        )

    def generate_character_categories(self, enriched: EnrichedCharacterData) -> list[str]:
        """Generate category tags for a character.

        Determines categories based on:
        1. Spawn locations → zone categories (via pre-built zone_link on CharacterSpawnInfo)
        2. Character type (Enemy/Rare/Boss) → type category
        3. Vendor status → Vendor category
        """
        categories: list[str] = []

        # Zone categories from spawn locations — zone_link.page_title is pre-built
        zone_page_titles = sorted(
            {info.zone_link.page_title for info in enriched.spawn_infos if info.zone_link.page_title is not None}
        )
        categories.extend(zone_page_titles)

        character = enriched.character
        if character.is_friendly:
            categories.append("Characters")
        else:
            categories.append("Enemies")

            if character.is_unique:
                categories.append("Bosses")

        if character.is_vendor:
            categories.append("Vendors")

        return categories

    def format_category_tags(self, categories: list[str]) -> str:
        """Format category names as MediaWiki category tags."""
        return "\n".join(f"[[Category:{cat}]]" for cat in categories)
