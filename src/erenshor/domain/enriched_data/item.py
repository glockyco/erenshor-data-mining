"""Enriched item data DTO."""

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.entities.skill import Skill
from erenshor.domain.entities.spell import Spell
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.source_info import SourceInfo

__all__ = ["EnrichedItemData"]


class EnrichedItemData:
    """Enriched item data with related entities.

    Contains raw item data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        item: Item,
        stats: list[ItemStats],
        classes: list[str],
        proc: ProcInfo | None = None,
        sources: SourceInfo | None = None,
        aura_spell: Spell | None = None,
        taught_spell: Spell | None = None,
        taught_spell_classes: list[str] | None = None,
        taught_skill: Skill | None = None,
    ) -> None:
        """Initialize enriched item data.

        Args:
            item: Item entity
            stats: ItemStats for quality variants (Normal/Blessed/Godly)
            classes: Class names that can equip this item (from ItemClasses junction table)
            proc: Proc information if item has a proc effect
            sources: Source information (vendors, drops, quests, crafting)
            aura_spell: Spell entity for aura items (from item.aura_stable_key)
            taught_spell: Spell entity for spell scrolls (from item.teach_spell_stable_key)
            taught_spell_classes: Classes that can use the taught spell (from SpellClasses)
            taught_skill: Skill entity for skill books (from item.teach_skill_stable_key)
        """
        self.item = item
        self.stats = stats
        self.classes = classes
        self.proc = proc
        self.sources = sources
        self.aura_spell = aura_spell
        self.taught_spell = taught_spell
        self.taught_spell_classes = taught_spell_classes or []
        self.taught_skill = taught_skill
