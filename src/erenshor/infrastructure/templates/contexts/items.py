"""Item template contexts."""

from __future__ import annotations

import builtins as _b
from typing import List

from pydantic import BaseModel


class ItemInfoboxContext(BaseModel):
    """Base item infobox context."""

    block_id: _b.str  # item:{subtype}:{ResourceName}
    # Common fields per Template:Item
    title: _b.str = ""
    image: _b.str = ""
    imagecaption: _b.str = ""
    type: _b.str = ""
    vendorsource: _b.str = ""
    source: _b.str = ""
    othersource: _b.str = ""
    questsource: _b.str = ""
    relatedquest: _b.str = ""
    craftsource: _b.str = ""
    componentfor: _b.str = ""
    relic: _b.str = ""
    classes: _b.str = ""
    effects: _b.str = ""
    damage: _b.str = ""
    delay: _b.str = ""
    dps: _b.str = ""
    casttime: _b.str = ""
    duration: _b.str = ""
    cooldown: _b.str = ""
    description: _b.str = ""
    buy: _b.str = ""
    sell: _b.str = ""
    itemid: _b.str = ""
    # Compatibility fields used by some templates (e.g., Mold)
    crafting: _b.str = ""
    recipe: _b.str = ""


class AbilityBookInfoboxContext(ItemInfoboxContext):
    """Ability book item context."""

    image: _b.str = ""
    imagecaption: _b.str = ""
    type: _b.str = ""
    spelltype: _b.str = ""
    classes: _b.str = ""
    effects: _b.str = ""
    manacost: _b.str = ""
    othersource: _b.str = ""


class AuraInfoboxContext(ItemInfoboxContext):
    """Aura item context."""

    image: _b.str = ""
    type: _b.str = ""
    classes: _b.str = ""
    buffgiven: _b.str = ""


class FancyWeaponColumn(BaseModel):
    """Single column in a fancy weapon table."""

    image: _b.str
    name: _b.str
    type: _b.str
    relic: _b.str = ""
    str: _b.str = ""
    end: _b.str = ""
    dex: _b.str = ""
    agi: _b.str = ""
    int: _b.str = ""
    wis: _b.str = ""
    cha: _b.str = ""
    res: _b.str = ""
    damage: _b.str = ""
    delay: _b.str = ""
    health: _b.str = ""
    mana: _b.str = ""
    armor: _b.str = ""
    magic: _b.str = ""
    poison: _b.str = ""
    elemental: _b.str = ""
    void: _b.str = ""
    description: _b.str = ""
    arcanist: _b.str = ""
    duelist: _b.str = ""
    druid: _b.str = ""
    paladin: _b.str = ""
    stormcaller: _b.str = ""
    proc_name: _b.str = ""
    proc_desc: _b.str = ""
    proc_chance: _b.str = ""
    proc_style: _b.str = ""
    tier: _b.str = ""


class FancyWeaponTableContext(BaseModel):
    """Context for fancy weapon tables."""

    block_id: _b.str  # table:ItemFancy:weapon:{ResourceName}
    columns: List[FancyWeaponColumn]


class FancyArmorColumn(FancyWeaponColumn):
    """Single column in a fancy armor table (inherits weapon fields)."""

    slot: _b.str = ""


class FancyArmorTableContext(BaseModel):
    """Context for fancy armor tables."""

    block_id: _b.str  # table:ItemFancy:armor:{ResourceName}
    columns: List[FancyArmorColumn]


class FancyWeaponTemplateContext(BaseModel):
    """Context for individual fancy weapon tier templates."""

    block_id: _b.str  # fancy:weapon:{ResourceName}:{tier}
    # All the fancy weapon template parameters
    image: _b.str = ""
    name: _b.str = ""
    type: _b.str = ""
    relic: _b.str = ""
    str: _b.str = ""
    end: _b.str = ""
    dex: _b.str = ""
    agi: _b.str = ""
    int: _b.str = ""
    wis: _b.str = ""
    cha: _b.str = ""
    res: _b.str = ""
    damage: _b.str = ""
    delay: _b.str = ""
    health: _b.str = ""
    mana: _b.str = ""
    armor: _b.str = ""
    magic: _b.str = ""
    poison: _b.str = ""
    elemental: _b.str = ""
    void: _b.str = ""
    description: _b.str = ""
    arcanist: _b.str = ""
    duelist: _b.str = ""
    druid: _b.str = ""
    paladin: _b.str = ""
    stormcaller: _b.str = ""
    proc_name: _b.str = ""
    proc_desc: _b.str = ""
    proc_chance: _b.str = ""
    proc_style: _b.str = ""
    tier: _b.str = ""


class FancyArmorTemplateContext(BaseModel):
    """Context for individual fancy armor tier templates."""

    block_id: _b.str  # fancy:armor:{ResourceName}:{tier}
    # Fancy armor template uses same parameters as Fancy weapon template
    image: _b.str = ""
    name: _b.str = ""
    type: _b.str = ""
    slot: _b.str = ""
    relic: _b.str = ""
    str: _b.str = ""
    end: _b.str = ""
    dex: _b.str = ""
    agi: _b.str = ""
    int: _b.str = ""
    wis: _b.str = ""
    cha: _b.str = ""
    res: _b.str = ""
    health: _b.str = ""
    mana: _b.str = ""
    armor: _b.str = ""
    magic: _b.str = ""
    poison: _b.str = ""
    elemental: _b.str = ""
    void: _b.str = ""
    description: _b.str = ""
    arcanist: _b.str = ""
    duelist: _b.str = ""
    druid: _b.str = ""
    paladin: _b.str = ""
    stormcaller: _b.str = ""
    proc_name: _b.str = ""
    proc_desc: _b.str = ""
    proc_chance: _b.str = ""
    proc_style: _b.str = ""
    tier: _b.str = ""


class FancyCharmContext(BaseModel):
    """Context for Fancy-charm template."""

    block_id: _b.str  # fancy:charm:{ResourceName}
    image: _b.str = ""
    name: _b.str = ""
    description: _b.str = ""
    strscaling: _b.str = ""
    endscaling: _b.str = ""
    dexscaling: _b.str = ""
    agiscaling: _b.str = ""
    intscaling: _b.str = ""
    wisscaling: _b.str = ""
    chascaling: _b.str = ""
    arcanist: _b.str = ""
    duelist: _b.str = ""
    druid: _b.str = ""
    paladin: _b.str = ""
    stormcaller: _b.str = ""


__all__ = [
    "ItemInfoboxContext",
    "AbilityBookInfoboxContext",
    "AuraInfoboxContext",
    "FancyWeaponColumn",
    "FancyWeaponTableContext",
    "FancyArmorColumn",
    "FancyArmorTableContext",
    "FancyWeaponTemplateContext",
    "FancyArmorTemplateContext",
    "FancyCharmContext",
]
