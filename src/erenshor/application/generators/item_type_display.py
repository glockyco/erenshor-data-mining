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
) -> str:
    """Build item type display string from item properties.

    Args:
        item: Item entity
        item_kind: Classified item kind
        related_quests: List of related quest links
        component_for: List of crafting component links

    Returns:
        Comma-separated type string (e.g., "[[Consumables|Consumable]], [[Quest Items|Quest Item]]")

    Note:
        Summoning item detection is not included here as it requires database access
        to look up the spell referenced by item_effect_on_click. This will be added
        when source enrichment is implemented with proper DB context.
    """
    types: list[str] = []

    # Consumable type
    if item_kind == ItemKind.CONSUMABLE:
        types.append("[[Consumables|Consumable]]")

    # Quest item type - mark as quest item if:
    # 1. Related to quests (rewards/requirements)
    # 2. Has CompleteOnRead (completes quest when read)
    # 3. Has AssignQuestOnRead (starts quest when read)
    is_quest_item = (
        bool(related_quests) or bool(item.complete_on_read_stable_key) or bool(item.assign_quest_on_read_stable_key)
    )
    if is_quest_item:
        types.append("[[Quest Items|Quest Item]]")

    # Crafting component type
    if component_for:
        types.append("[[Crafting]]")

    # Deduplicate while preserving order
    return ", ".join(dict.fromkeys(types))
