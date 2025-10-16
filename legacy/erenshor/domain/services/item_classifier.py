from __future__ import annotations

from typing import Literal

__all__ = ["classify_item_kind"]


ItemKind = Literal[
    "weapon", "armor", "aura", "ability_book", "consumable", "mold", "general"
]


def classify_item_kind(
    *,
    required_slot: str | None,
    teach_spell: str | None,
    teach_skill: str | None,
    template_flag: int | None,
    click_effect: str | None,
    disposable: bool | None,
) -> ItemKind:
    """Classify item type using minimal, explicit rules.

    - Weapons: RequiredSlot in {Primary, PrimaryOrSecondary, Secondary}
    - Armor: equippable slot not in the above; not General; not Aura
    - Auras: RequiredSlot == 'Aura'
    - Ability Books: TeachSpell or TeachSkill present
    - Consumables: RequiredSlot == 'General' and click effect present and Disposable is true
    - Molds: template_flag == 1
    - General: fallback
    """
    slot = (required_slot or "").strip()
    slot_low = slot.lower()

    # Aura takes precedence
    if slot_low == "aura":
        return "aura"

    # Ability books
    if (teach_spell and teach_spell.strip()) or (teach_skill and teach_skill.strip()):
        return "ability_book"

    # Molds
    if (template_flag or 0) == 1:
        return "mold"

    # Consumables
    if (
        slot_low == "general"
        and (click_effect and click_effect.strip())
        and bool(disposable)
    ):
        return "consumable"

    # Weapons
    if slot in {"Primary", "PrimaryOrSecondary", "Secondary"}:
        return "weapon"

    # Armor (equippable, not general/aura)
    if slot and slot_low not in {"general", "aura"}:
        return "armor"

    return "general"
