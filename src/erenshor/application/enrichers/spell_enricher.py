"""Spell enrichment service for wiki generation.

This service aggregates spell-related data from multiple tables:
- Class restrictions from SpellClasses junction table
- Obtainability check for teaching items (only show classes if spell is obtainable)
"""

from loguru import logger

from erenshor.domain.enriched_data.spell import EnrichedSpellData
from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository

__all__ = ["EnrichedSpellData", "SpellEnricher"]


class SpellEnricher:
    """Service for enriching spells with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        spell_repo: SpellRepository,
        item_repo: ItemRepository,
    ) -> None:
        """Initialize spell enricher.

        Args:
            spell_repo: Repository for spell data (classes, etc.)
            item_repo: Repository for item data (teaching items, obtainability)
        """
        self._spell_repo = spell_repo
        self._item_repo = item_repo

    def enrich(self, spell: Spell) -> EnrichedSpellData:
        """Enrich spell with related data from other tables.

        Only populates classes field if the spell has at least one obtainable teaching item.
        This prevents showing class restrictions for unobtainable spells (debug spells, etc.).

        Args:
            spell: Spell entity

        Returns:
            EnrichedSpellData with classes (empty if no obtainable teaching items),
            items with effect, and teaching items
        """
        logger.debug(f"Enriching spell: {spell.spell_name}")

        # Get items that teach this spell (returns list of stable keys)
        teaching_item_keys = self._item_repo.get_items_that_teach_spell(spell.stable_key)

        # Filter to only obtainable teaching items
        obtainable_teaching_items = [key for key in teaching_item_keys if self._item_repo.is_item_obtainable(key)]

        # Only get classes if there's at least one obtainable teaching item
        classes: list[str] = []
        if obtainable_teaching_items:
            classes = self._spell_repo.get_spell_classes(spell.stable_key)
            logger.debug(
                f"Spell '{spell.spell_name}' has {len(obtainable_teaching_items)} "
                f"obtainable teaching items, classes: {classes}"
            )
        else:
            logger.debug(f"Spell '{spell.spell_name}' has no obtainable teaching items, skipping class restrictions")

        # Get items that grant this spell as an effect
        items_with_effect = self._item_repo.get_items_with_spell_effect(spell.stable_key)
        logger.debug(f"Spell '{spell.spell_name}' has {len(items_with_effect)} items with effect")

        return EnrichedSpellData(
            spell=spell,
            classes=classes,
            items_with_effect=items_with_effect,
            teaching_items=obtainable_teaching_items,
        )
