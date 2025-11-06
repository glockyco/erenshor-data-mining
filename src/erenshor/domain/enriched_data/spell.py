"""Enriched spell data DTO."""

from erenshor.domain.entities.spell import Spell

__all__ = ["EnrichedSpellData"]


class EnrichedSpellData:
    """Enriched spell data with related entities.

    Contains raw spell data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        spell: Spell,
        classes: list[str],
        items_with_effect: list[str],
        teaching_items: list[str],
    ) -> None:
        """Initialize enriched spell data.

        Args:
            spell: Spell entity
            classes: Class names that can use this spell (from SpellClasses junction table).
                     Empty list if no obtainable teaching items exist.
            items_with_effect: Item stable keys that grant this spell as an effect
            teaching_items: Item stable keys that teach this spell
        """
        self.spell = spell
        self.classes = classes
        self.items_with_effect = items_with_effect
        self.teaching_items = teaching_items
