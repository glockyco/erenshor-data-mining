"""Crafting recipe value objects."""

from dataclasses import dataclass, field

from erenshor.domain.value_objects.wiki_link import ItemLink


@dataclass(frozen=True)
class CraftingRecipe:
    """Complete crafting recipe for a mold item.

    materials is ordered by material_slot ascending.
    results is ordered by reward_slot ascending.

    All item references are pre-built ItemLink objects — section generators
    call str(link) directly without resolver lookup.
    """

    materials: list[tuple[ItemLink, int]] = field(default_factory=list)
    results: list[tuple[ItemLink, int]] = field(default_factory=list)
