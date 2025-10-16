"""Item generators module.

Provides ItemGenerator facade that delegates to specialized generators
for different item types: weapons, armor, auras, consumables, ability books,
molds, and general items.

This module maintains a stable interface while providing a clean
separation of concerns internally.
"""

from __future__ import annotations

import logging
from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import BaseGenerator, GeneratedContent
from erenshor.application.generators.items.ability_books import (
    AbilityBookGenerator,
)
from erenshor.application.generators.items.auras import AuraGenerator
from erenshor.application.generators.items.base import (
    ItemGeneratorBase,
    build_item_types,
    classify_item_kind,
)
from erenshor.application.generators.items.charms import CharmGenerator
from erenshor.application.generators.items.consumables import ConsumableGenerator
from erenshor.application.generators.items.general import GeneralItemGenerator
from erenshor.application.generators.items.molds import MoldGenerator
from erenshor.application.generators.items.sources import SourceEnricher
from erenshor.application.generators.items.weapon_armor import WeaponArmorGenerator
from erenshor.domain.entities.page import EntityRef
from erenshor.infrastructure.database.repositories import (
    get_fishable_item_names,
    get_items,
    get_mining_item_names,
)
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver

logger = logging.getLogger(__name__)


class ItemGenerator(BaseGenerator):
    """Generate item page content from database.

    Facade that coordinates specialized generators for different item types
    with clean separation of concerns.

    Delegates to:
    - WeaponArmorGenerator: Weapons and armor with fancy tables
    - CharmGenerator: Charm items with Fancy-charm template
    - AuraGenerator: Aura items
    - AbilityBookGenerator: Ability books
    - ConsumableGenerator: Consumable items
    - MoldGenerator: Mold items
    - GeneralItemGenerator: General items (fallback)
    """

    def __init__(self) -> None:
        """Initialize item generator facade."""
        super().__init__()
        self._weapon_armor_gen = WeaponArmorGenerator()
        self._charm_gen = CharmGenerator()
        self._aura_gen = AuraGenerator()
        self._ability_book_gen = AbilityBookGenerator()
        self._consumable_gen = ConsumableGenerator()
        self._mold_gen = MoldGenerator()
        self._general_gen = GeneralItemGenerator()
        self._source_enricher: SourceEnricher | None = None

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate item content with streaming.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or 'id:1234') to process specific items

        Yields:
            GeneratedContent for each item, one at a time
        """
        linker = RegistryLinkResolver(registry)

        # Initialize source enricher with engine and link resolver
        self._source_enricher = SourceEnricher(engine, linker)

        items = get_items(engine, obtainable_only=False)

        if filter:
            items = [
                item
                for item in items
                if self._matches_filter(item.ItemName or "", item.Id, filter)
            ]

        fishable_names = {n.lower() for n in get_fishable_item_names(engine)}
        mining_names = {n.lower() for n in get_mining_item_names(engine)}

        for item in items:
            # Check if entity is in registry (skip if explicitly excluded)
            entity_ref = EntityRef.from_item(item)
            # Only skip if registry has pages (i.e., has been built)
            # Empty registry means first run or test - don't skip
            if registry.pages and not registry.resolve_entity(entity_ref):
                # Entity excluded from registry - skip generation
                continue

            try:
                page_title = linker.resolve_item_title(
                    item.ResourceName, item.ItemName, item.Id
                )

                # Classify item type
                item_kind = classify_item_kind(item)

                # Enrich sources
                vendor_sources = self._source_enricher.get_vendor_sources(item)
                drop_sources = self._source_enricher.get_drop_sources(item)
                quest_info = self._source_enricher.get_quest_sources(item)
                crafting_info = self._source_enricher.get_crafting_sources(item)
                recipe_info = self._source_enricher.get_recipe_info(item)

                # Extract from structured types
                quest_sources = list(quest_info.reward_sources)
                related_quests = list(quest_info.requirement_sources)
                craft_sources = list(crafting_info.craft_sources)
                component_for = list(crafting_info.component_for)
                crafting_results = list(recipe_info.results)
                recipe_ingredients = list(recipe_info.ingredients)

                # Add quest completion link
                completion_quests = self._source_enricher.get_quest_completion_link(
                    item
                )
                related_quests.extend(completion_quests)

                # Sort for determinism
                quest_sources = sorted(quest_sources)
                related_quests = sorted(related_quests)
                crafting_results = sorted(crafting_results)
                recipe_ingredients = sorted(recipe_ingredients)

                # Auto-enrich sources
                others = self._source_enricher.get_auto_sources(
                    item, fishable_names, mining_names
                )

                # Deduplicate
                vendor_sources = self._dedup(sorted(vendor_sources))
                drop_sources = self._dedup(sorted(drop_sources))
                craft_sources = self._dedup(craft_sources)  # Preserve order: mold first, then materials
                component_for = self._dedup(sorted(component_for))

                # Build type display
                display_type = build_item_types(item, related_quests, component_for)

                # Delegate to specialized generator
                if item_kind == "weapon":
                    blocks = self._weapon_armor_gen.generate_weapon_blocks(
                        engine,
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        crafting_results,
                        recipe_ingredients,
                    )
                elif item_kind == "armor":
                    blocks = self._weapon_armor_gen.generate_armor_blocks(
                        engine,
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        crafting_results,
                        recipe_ingredients,
                    )
                elif item_kind == "charm":
                    blocks = self._charm_gen.generate_charm_blocks(
                        engine,
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                    )
                elif item_kind == "aura":
                    block = self._aura_gen.generate_aura_block(
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        others,
                    )
                    blocks = [block]
                elif item_kind == "ability_book":
                    block = self._ability_book_gen.generate_ability_book_block(
                        engine,
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                    )
                    blocks = [block]
                elif item_kind == "mold":
                    block = self._mold_gen.generate_mold_block(
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        crafting_results,
                        recipe_ingredients,
                        display_type,
                        others,
                    )
                    blocks = [block]
                elif item_kind == "consumable":
                    block = self._consumable_gen.generate_consumable_block(
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        display_type,
                        others,
                    )
                    blocks = [block]
                else:  # general
                    block = self._general_gen.generate_general_block(
                        item,
                        page_title,
                        linker,
                        vendor_sources,
                        drop_sources,
                        quest_sources,
                        related_quests,
                        craft_sources,
                        component_for,
                        crafting_results,
                        recipe_ingredients,
                        display_type,
                        others,
                    )
                    blocks = [block]

                entity_ref = EntityRef.from_item(item)

                yield GeneratedContent(
                    entity_ref=entity_ref,
                    page_title=page_title,
                    rendered_blocks=blocks,
                )
            except Exception as exc:
                item_name = getattr(item, "ItemName", "Unknown")
                item_id = getattr(item, "Id", "Unknown")
                logger.error(
                    f"Failed to generate content for item '{item_name}' (ID: {item_id}): {exc}"
                )
                continue

    def _dedup(self, items: list[str]) -> list[str]:
        """Deduplicate list while preserving order.

        Args:
            items: List of strings to deduplicate

        Returns:
            Deduplicated list
        """
        seen = set()
        deduplicated_items: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                deduplicated_items.append(item)
        return deduplicated_items


__all__ = [
    "ItemGenerator",
    "ItemGeneratorBase",
    "WeaponArmorGenerator",
    "CharmGenerator",
    "AuraGenerator",
    "AbilityBookGenerator",
    "ConsumableGenerator",
    "MoldGenerator",
    "GeneralItemGenerator",
    "SourceEnricher",
    "classify_item_kind",
    "build_item_types",
]
