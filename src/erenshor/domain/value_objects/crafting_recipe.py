"""Crafting recipe value object."""

from typing import TypedDict


class CraftingMaterial(TypedDict):
    """Material required for crafting recipe."""

    MaterialItemStableKey: str
    MaterialQuantity: int
    MaterialSlot: int


class CraftingReward(TypedDict):
    """Reward produced by crafting recipe."""

    RewardItemStableKey: str
    RewardQuantity: int
    RewardSlot: int


class CraftingRecipe(TypedDict):
    """Crafting recipe with materials and rewards.

    Structure returned by ItemRepository.get_crafting_recipe().
    """

    materials: list[CraftingMaterial]
    rewards: list[CraftingReward]
