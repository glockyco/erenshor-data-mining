"""Base classes and utilities for item generators.

This module provides shared logic for all item type generators including
classification, quest handling, and common formatting utilities.
"""

from __future__ import annotations

import logging

from erenshor.domain.entities import DbItem

__all__ = ["ItemGeneratorBase", "build_item_types", "classify_item_kind"]


logger = logging.getLogger(__name__)


def classify_item_kind(item: DbItem) -> str:
    """Classify item into one of: weapon, armor, charm, aura, ability_book, consumable, mold, general.

    Args:
        item: Database item to classify

    Returns:
        Item type string
    """
    weapon_kinds = {
        "TwoHandMelee",
        "OneHandMelee",
        "TwoHandBow",
        "OneHandDagger",
        "TwoHandStaff",
    }
    slot_raw = (item.RequiredSlot or "").strip()

    is_equippable_weapon = slot_raw.lower() != "general"
    is_weapon = (
        (item.ThisWeaponType in weapon_kinds)
        or bool(item.IsWand)
        or bool(item.IsBow)
        or (slot_raw in ("Primary", "PrimaryOrSecondary", "Secondary"))
    ) and is_equippable_weapon

    is_mold = int(item.Template or 0) == 1
    is_ability_book = (
        (item.TeachSpell and item.TeachSpell.strip())
        or (item.TeachSkill and item.TeachSkill.strip())
        or (item.ItemName or "").lower().startswith("spell scroll:")
    )

    is_aura = slot_raw.lower() == "aura"
    is_charm = slot_raw.lower() == "charm"

    non_equip = {"general", "aura", "charm"}
    is_armor = (
        (not is_weapon)
        and (not is_mold)
        and not is_ability_book
        and bool(slot_raw)
        and (slot_raw.lower() not in non_equip)
    )

    is_consumable = False
    if (
        not is_ability_book
        and item.ItemEffectOnClick
        and item.ItemEffectOnClick.strip()
    ):
        slot = slot_raw.lower()
        if (not slot or slot == "general") and getattr(item, "Disposable", None):
            is_consumable = True

    if is_mold:
        return "mold"
    if is_ability_book:
        return "ability_book"
    if is_aura:
        return "aura"
    if is_charm:
        return "charm"
    if is_consumable:
        return "consumable"
    if is_weapon:
        return "weapon"
    if is_armor:
        return "armor"
    return "general"


def build_item_types(
    item: DbItem, related_quests: list[str], comp_for: list[str]
) -> str:
    """Build item type display string from item properties.

    Args:
        item: Database item
        related_quests: List of related quest links
        comp_for: List of crafting component links

    Returns:
        Comma-separated type string
    """
    from erenshor.shared.text import parse_name_and_id

    types: list[str] = []

    item_kind = classify_item_kind(item)
    if item_kind == "consumable":
        types.append("[[Consumables|Consumable]]")

    if related_quests:
        types.append("[[Quest Items|Quest Item]]")

    if comp_for:
        types.append("[[Crafting]]")

    if item.ItemEffectOnClick and "Summon" in item.ItemEffectOnClick:
        parsed = parse_name_and_id(item.ItemEffectOnClick)
        if parsed and len(parsed) == 2:
            _, spell_id = parsed
            if spell_id is not None:
                # Summoning item classification requires spell lookup via engine
                # Generators with engine access should implement this locally
                types.append("[[:Category:Items|Summoning Item]]")

    return ", ".join(dict.fromkeys(types))


class ItemGeneratorBase:
    """Base class for all item generators.

    Provides common utilities for source enrichment, link resolution,
    and shared formatting logic. This is NOT a BaseGenerator subclass
    because specialized generators don't need the abstract generate() method.
    """

    def _dedup(self, items: list[str]) -> list[str]:
        """Deduplicate list while preserving order.

        Args:
            items: List of strings to deduplicate

        Returns:
            Deduplicated list
        """
        seen = set()
        out: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out
