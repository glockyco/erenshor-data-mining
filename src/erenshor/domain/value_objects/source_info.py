"""Resolved links and recipes for transitional canonical item rendering."""

from dataclasses import dataclass, field

from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemDisposition, ItemUse
from erenshor.domain.value_objects.wiki_link import ItemLink, QuestLink, WikiLink


@dataclass
class SourceInfo:
    """Keep canonical facts intact while resolving their wiki presentation."""

    acquisitions: tuple[ItemAcquisition, ...] = ()
    uses: tuple[ItemUse, ...] = ()
    links: dict[str, WikiLink] = field(default_factory=dict)
    recipes: list[tuple[ItemLink, CraftingRecipe]] = field(default_factory=list)
    outcomes: dict[str, ItemAcquisition] = field(default_factory=dict)
    quest_requirements: list[QuestLink] = field(default_factory=list)
    component_for: list[ItemLink] = field(default_factory=list)
    crafting_results: list[tuple[ItemLink, int]] = field(default_factory=list)
    recipe_ingredients: list[tuple[ItemLink, int]] = field(default_factory=list)
    disposition: ItemDisposition | None = None
