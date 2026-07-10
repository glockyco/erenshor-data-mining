"""Item source information value object."""

from dataclasses import dataclass, field

from erenshor.domain.value_objects.loot import ItemDropInfo
from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink, QuestLink, WikiLink

__all__ = ["ObtainedFromInfo", "SourceInfo"]


@dataclass(frozen=True)
class ObtainedFromInfo:
    """Stable-keyed provenance edge for an item-owned obtainability row."""

    source_type: str
    source_key: str | None
    probability: float | None = None
    is_guaranteed: bool = False
    quantity: int | None = None
    condition: str | None = None


@dataclass
class SourceInfo:
    """All source information for an item.

    All fields carry pre-built WikiLink objects populated by repository JOINs.
    Section generators iterate link lists and call str(link) — no resolver
    or lookup at generation time.
    """

    # Vendors
    vendors: list[CharacterLink] = field(default_factory=list)

    # Drops from characters and items (e.g., fossils)
    drops: list[tuple[WikiLink, float]] = field(default_factory=list)

    # Quests
    quest_rewards: list[QuestLink] = field(default_factory=list)
    quest_requirements: list[QuestLink] = field(default_factory=list)

    # Crafting
    craft_sources: list[ItemLink] = field(default_factory=list)
    # Full recipe to craft this item: mold link + ingredient links with quantities
    craft_recipe: list[tuple[ItemLink, int]] = field(default_factory=list)
    # Items that require this item as a crafting component
    component_for: list[ItemLink] = field(default_factory=list)
    # What this mold produces: (result_link, quantity)
    crafting_results: list[tuple[ItemLink, int]] = field(default_factory=list)
    # What this mold needs as ingredients: (ingredient_link, quantity)
    recipe_ingredients: list[tuple[ItemLink, int]] = field(default_factory=list)

    # Item drops (for source items like fossils that produce random items), keyed by
    # the dropped item's StableKey; the link resolves from the item record at display.
    item_drops: list[ItemDropInfo] = field(default_factory=list)

    # Unified item-owned obtainability rows with stable source identity.
    obtained_from: list[ObtainedFromInfo] = field(default_factory=list)
