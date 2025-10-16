"""Value objects for crafting system."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CraftingMaterial", "CraftingReward"]


@dataclass(frozen=True)
class CraftingMaterial:
    """Material required for a crafting recipe.

    Attributes:
        material_item_id: Database ID of the material item
        material_slot: Slot position in crafting UI (1-based)
        material_quantity: Number of items required
    """

    material_item_id: str
    material_slot: int
    material_quantity: int


@dataclass(frozen=True)
class CraftingReward:
    """Reward from completing a crafting recipe.

    Attributes:
        reward_item_id: Database ID of the reward item
        reward_slot: Slot position in reward UI (1-based)
        reward_quantity: Number of items produced
    """

    reward_item_id: str
    reward_slot: int
    reward_quantity: int
