"""Item type display utilities.

This module provides utilities for building item type labels (Consumable, Quest Item,
Crafting, Summoning Item) based on item properties and related entities.
"""

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_kind import ItemKind


def build_item_types(
    item: Item,
    item_kind: ItemKind,
    quest_requirements: list[str],
    component_for: list[str],
) -> str:
    """Build item type display string from item properties.

    Args:
        item: Item entity
        item_kind: Classified item kind
        quest_requirements: List of quest requirement links (items needed for quests)
        component_for: List of crafting component links

    Returns:
        Comma-separated type string (e.g., "[[Consumables|Consumable]], [[Quest Items|Quest Item]]")

    Note:
        Items are classified as "Quest Item" only if they are:
        - Required by quests (quest_requirements), NOT if they are merely quest rewards
        - Have CompleteOnRead (completes quest when read)
        - Have AssignQuestOnRead (starts quest when read)
    """
    types: list[str] = []

    # Consumable type
    if item_kind == ItemKind.CONSUMABLE:
        types.append("[[Consumables|Consumable]]")

    # Quest item type - mark as quest item if:
    # 1. Required by quests (NOT just rewarded by quests)
    # 2. Has CompleteOnRead (completes quest when read)
    # 3. Has AssignQuestOnRead (starts quest when read)
    is_quest_item = (
        bool(quest_requirements) or bool(item.complete_on_read_stable_key) or bool(item.assign_quest_on_read_stable_key)
    )
    if is_quest_item:
        types.append("[[Quest Items|Quest Item]]")

    # Crafting component type
    if component_for:
        types.append("[[Crafting]]")

    # Deduplicate while preserving order
    return ", ".join(dict.fromkeys(types))
