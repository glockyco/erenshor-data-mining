"""Item type display utilities.

This module provides utilities for building item type labels (Consumable, Quest Item,
Crafting, Summoning Item) based on item properties and related entities.
"""

from erenshor.domain.entities.item import Item
from erenshor.registry.item_classifier import ItemKind


def build_item_types(
    item: Item,
    item_kind: ItemKind,
    related_quests: list[str],
    component_for: list[str],
    is_summoning_item: bool = False,
) -> str:
    """Build item type display string from item properties.

    Args:
        item: Item entity
        item_kind: Classified item kind
        related_quests: List of related quest links
        component_for: List of crafting component links
        is_summoning_item: Whether item summons a pet

    Returns:
        Comma-separated type string (e.g., "[[Consumables|Consumable]], [[Quest Items|Quest Item]]")
    """
    types: list[str] = []

    # Consumable type
    if item_kind == ItemKind.CONSUMABLE:
        types.append("[[Consumables|Consumable]]")

    # Quest item type
    if related_quests:
        types.append("[[Quest Items|Quest Item]]")

    # Crafting component type
    if component_for:
        types.append("[[Crafting]]")

    # Summoning item type
    if is_summoning_item:
        types.append("[[:Category:Items|Summoning Item]]")

    # Deduplicate while preserving order
    return ", ".join(dict.fromkeys(types))


def is_summoning_item(item: Item) -> bool:
    """Check if item is a summoning item.

    Args:
        item: Item entity

    Returns:
        True if item summons a pet when clicked
    """
    if not item.item_effect_on_click:
        return False

    # Check if the click effect contains "Summon"
    return "Summon" in item.item_effect_on_click
