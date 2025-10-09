"""Crafting recipe domain aggregate.

Represents a complete crafting recipe with materials and rewards. This is a
domain aggregate that combines data from multiple junction tables into a
cohesive unit.

Design:
- Immutable value object (frozen dataclass)
- Validates business rules (must have at least one reward)
- Self-contained (all data needed for crafting is here)
- Domain language (not database columns)
"""

from __future__ import annotations

from dataclasses import dataclass

from erenshor.domain.value_objects.crafting import CraftingMaterial, CraftingReward

__all__ = ["CraftingRecipe"]


@dataclass(frozen=True)
class CraftingRecipe:
    """Complete crafting recipe with materials and rewards.

    Represents the full recipe for a mold item, including what materials
    are needed and what items are produced.

    Attributes:
        recipe_item_id: Database ID of the mold/template item
        materials: List of materials required (from CraftingMaterials junction)
        rewards: List of items produced (from CraftingRewards junction)

    Invariants:
        - Must have at least one reward (can't craft nothing)
        - Materials can be empty (some recipes are free)
        - Both lists maintain slot order from database

    Example:
        >>> recipe = CraftingRecipe(
        ...     recipe_item_id="123",
        ...     materials=[
        ...         CraftingMaterial("iron_ore", 1, 5),
        ...         CraftingMaterial("coal", 2, 2),
        ...     ],
        ...     rewards=[
        ...         CraftingReward("iron_bar", 1, 1),
        ...     ],
        ... )
        >>> recipe.recipe_item_id
        '123'
        >>> len(recipe.materials)
        2
    """

    recipe_item_id: str
    materials: list[CraftingMaterial]
    rewards: list[CraftingReward]

    def __post_init__(self) -> None:
        """Validate business rules after initialization.

        Raises:
            ValueError: If recipe has no rewards (invalid business rule)
        """
        if not self.rewards:
            raise ValueError(
                f"Recipe {self.recipe_item_id} must have at least one reward. "
                "A recipe that produces nothing is invalid."
            )
