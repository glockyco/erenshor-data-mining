"""Item kind classification.

This module provides item classification logic to determine item "kinds" (weapon, armor,
consumable, etc.) based on item properties. Used by category generation and other systems
that need to group items by type.

Classification rules are explicit and minimal:
- Cosmetics: a cosmetic slot gives the item an effect (mask, belt lamp, or lens)
- Weapons: RequiredSlot in {Primary, PrimaryOrSecondary, Secondary}
- Armor: Equippable slot not in weapon slots; not General; not Aura
- Auras: RequiredSlot == 'Aura'
- Spell Books: TeachSpell present
- Skill Books: TeachSkill present
- Consumables: RequiredSlot == 'General' AND click effect present AND Disposable is true
- Molds: template_flag == 1
- General: fallback for all other items
"""

from enum import StrEnum

__all__ = ["ItemKind", "classify_item_kind"]


class ItemKind(StrEnum):
    """Item kind enumeration.

    Uses StrEnum so members are actual strings, providing both
    enum safety and string compatibility.
    """

    WEAPON = "weapon"
    ARMOR = "armor"
    CHARM = "charm"
    AURA = "aura"
    SPELL_SCROLL = "spellscroll"
    SKILL_BOOK = "skillbook"
    CONSUMABLE = "consumable"
    MOLD = "mold"
    COSMETIC = "cosmetic"
    GENERAL = "general"


def classify_item_kind(  # noqa: PLR0911
    *,
    required_slot: str | None,
    teach_spell: str | None,
    teach_skill: str | None,
    template_flag: int | None,
    click_effect: str | None,
    disposable: bool | None,
    cosmetic: bool,
) -> ItemKind:
    """Classify item type using minimal, explicit rules.

    Classification priority (first match wins):
    1. Cosmetics - a cosmetic slot gives the item an effect
    2. Auras - RequiredSlot == 'Aura'
    3. Charms - RequiredSlot == 'Charm'
    4. Spell Books - TeachSpell present
    5. Skill Books - TeachSkill present
    6. Molds - template_flag == 1
    7. Consumables - RequiredSlot == 'General' + click effect + Disposable
    8. Weapons - RequiredSlot in {Primary, PrimaryOrSecondary, Secondary}
    9. Armor - Equippable slot not in weapon/general/aura/charm
    10. General - fallback

    Args:
        required_slot: Equipment slot (e.g., 'Primary', 'Head', 'General', 'Aura')
        teach_spell: Spell taught by item (if any)
        teach_skill: Skill taught by item (if any)
        template_flag: Crafting template flag (1 = mold)
        click_effect: Effect triggered on right-click
        disposable: Whether item is consumed on use
        cosmetic: Whether a cosmetic slot gives the item an effect

    Returns:
        ItemKind classification

    Examples:
        >>> classify_item_kind(
        ...     required_slot="Primary",
        ...     teach_spell=None,
        ...     teach_skill=None,
        ...     template_flag=None,
        ...     click_effect=None,
        ...     disposable=None,
        ...     cosmetic=False,
        ... )
        ItemKind.WEAPON

        >>> classify_item_kind(
        ...     required_slot="General",
        ...     teach_spell=None,
        ...     teach_skill=None,
        ...     template_flag=1,
        ...     click_effect=None,
        ...     disposable=None,
        ...     cosmetic=False,
        ... )
        ItemKind.MOLD

        >>> classify_item_kind(
        ...     required_slot="General",
        ...     teach_spell=None,
        ...     teach_skill=None,
        ...     template_flag=None,
        ...     click_effect="HealSpell",
        ...     disposable=True,
        ...     cosmetic=False,
        ... )
        ItemKind.CONSUMABLE
    """
    # 1. Cosmetics (the cosmetic slots give the item an effect)
    if cosmetic:
        return ItemKind.COSMETIC

    slot = (required_slot if required_slot is not None else "").strip()
    slot_low = slot.lower()

    # 2. Auras (special equipment slot)
    if slot_low == "aura":
        return ItemKind.AURA

    # 3. Charms (special equipment slot)
    if slot_low == "charm":
        return ItemKind.CHARM

    # 4. Spell books (teach spells)
    if teach_spell is not None and teach_spell.strip():
        return ItemKind.SPELL_SCROLL

    # 5. Skill books (teach skills)
    if teach_skill is not None and teach_skill.strip():
        return ItemKind.SKILL_BOOK

    # 6. Molds (crafting templates)
    if (template_flag or 0) == 1:
        return ItemKind.MOLD

    # 7. Consumables (clickable, disposable general items)
    if slot_low == "general" and (click_effect is not None and click_effect.strip()) and bool(disposable):
        return ItemKind.CONSUMABLE

    # 8. Weapons (primary/secondary slots)
    if slot in {"Primary", "PrimaryOrSecondary", "Secondary"}:
        return ItemKind.WEAPON

    # 9. Armor (equippable, not general/aura/charm/weapon)
    if slot and slot_low not in {"general", "aura", "charm"}:
        return ItemKind.ARMOR

    # 10. General (fallback)
    return ItemKind.GENERAL
