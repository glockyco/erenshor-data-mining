"""Item source information value object."""

from dataclasses import dataclass

__all__ = ["SourceInfo"]


@dataclass
class SourceInfo:
    """All source information for an item.

    Raw data from repositories (just stable keys and minimal metadata).
    Template generators format this into wiki links via registry resolver.
    """

    # Vendors
    vendors: list[str]  # Character stable keys

    # Drops
    drops: list[tuple[str, float]]  # (character_stable_key, drop_probability)

    # Quests
    quest_rewards: list[str]  # Quest stable keys that reward this item
    quest_requirements: list[str]  # Quest stable keys that require this item

    # Crafting
    craft_sources: list[str]  # Item stable keys (molds) that produce this item
    craft_recipe: list[tuple[str, int]]  # Recipe to craft this item: mold + ingredients (item_stable_key, quantity)
    component_for: list[str]  # Item stable keys that require this as component
    crafting_results: list[tuple[str, int]]  # What this mold produces: (item_stable_key, quantity)
    recipe_ingredients: list[tuple[str, int]]  # What this mold needs: (item_stable_key, quantity)

    # Item drops (for consumables like fossils that produce random items)
    item_drops: list[tuple[str, float]]  # (dropped_item_stable_key, drop_probability)
