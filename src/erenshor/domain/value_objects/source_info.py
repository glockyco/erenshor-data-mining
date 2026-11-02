"""Resolved links, places and recipes for public item rendering."""

from dataclasses import dataclass, field

from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.item_public_view import ItemStatus, PublicPlace, PublicSource, PublicUse
from erenshor.domain.value_objects.wiki_link import ItemLink, QuestLink, WikiLink


@dataclass
class SourceInfo:
    """Keep public facts intact while resolving their wiki presentation."""

    acquisitions: tuple[PublicSource, ...] = ()
    uses: tuple[PublicUse, ...] = ()
    places: dict[str, tuple[PublicPlace, ...]] = field(default_factory=dict)
    links: dict[str, WikiLink] = field(default_factory=dict)
    recipes: list[tuple[ItemLink, CraftingRecipe]] = field(default_factory=list)
    outcomes: dict[str, PublicSource] = field(default_factory=dict)
    quest_requirements: list[QuestLink] = field(default_factory=list)
    component_for: list[ItemLink] = field(default_factory=list)
    crafting_results: list[tuple[ItemLink, int]] = field(default_factory=list)
    recipe_ingredients: list[tuple[ItemLink, int]] = field(default_factory=list)
    disposition: ItemStatus | None = None
