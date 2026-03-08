"""Enriched spell data DTO."""

from erenshor.domain.entities.spell import Spell
from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink

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
        items_with_effect: list[ItemLink],
        teaching_items: list[ItemLink],
        used_by_characters: list[CharacterLink],
        pet_to_summon: CharacterLink | None = None,
    ) -> None:
        """Initialize enriched spell data.

        Args:
            spell: Spell entity (carries add_proc_link and status_effect_link)
            classes: Class names that can use this spell (from spell_classes junction table).
                     Empty list if no obtainable teaching items exist.
            items_with_effect: Pre-built ItemLink objects for items that grant this spell
            teaching_items: Pre-built ItemLink objects for items that teach this spell
            used_by_characters: Pre-built CharacterLink objects for NPCs that use this spell
            pet_to_summon: Pre-built CharacterLink for the pet summoned by this spell (if any)
        """
        self.spell = spell
        self.classes = classes
        self.items_with_effect = items_with_effect
        self.teaching_items = teaching_items
        self.used_by_characters = used_by_characters
        self.pet_to_summon = pet_to_summon
