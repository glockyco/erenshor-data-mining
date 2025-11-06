"""Enriched item data DTO."""

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
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
    ) -> None:
        """Initialize enriched item data.

        Args:
            item: Item entity
            stats: ItemStats for quality variants (Normal/Blessed/Godly)
            classes: Class names that can equip this item (from ItemClasses junction table)
            proc: Proc information if item has a proc effect
            sources: Source information (vendors, drops, quests, crafting)
        """
        self.item = item
        self.stats = stats
        self.classes = classes
        self.proc = proc
        self.sources = sources
