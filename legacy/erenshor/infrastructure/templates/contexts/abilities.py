"""Context for ability (spell/skill) infobox templates.

This unified context supports both spells and skills. Fields are populated
based on entity type - spells have full combat mechanics, skills have fewer fields.
"""

from __future__ import annotations

import builtins as _b

from pydantic import BaseModel


class AbilityInfoboxContext(BaseModel):
    """Unified context for ability infoboxes (spells and skills).

    Supports both:
    - Spells: Abilities that cost mana (comprehensive combat mechanics)
    - Skills: Abilities that don't cost mana (simplified format)

    Fields are conditionally populated based on entity type.
    """

    # Required identity
    block_id: _b.str
    id: _b.str
    # Header / media
    title: _b.str = ""
    image: _b.str = ""
    imagecaption: _b.str = ""
    # Basic fields
    description: _b.str = ""
    type: _b.str = ""
    line: _b.str = ""
    classes: list[_b.str] = []
    # Targeting / levels
    required_level: _b.str = ""
    manacost: _b.str = ""
    aggro: _b.str = ""
    is_taunt: bool = False
    casttime: _b.str = ""
    cooldown: _b.str = ""
    duration: _b.str = ""
    duration_in_ticks: _b.str = ""
    has_unstable_duration: bool = False
    is_instant_effect: bool = False
    is_reap_and_renew: bool = False
    is_sim_usable: bool = True
    range: _b.str = ""
    max_level_target: _b.str = ""
    is_self_only: bool = False
    is_group_effect: bool = False
    is_applied_to_caster: bool = False
    # Effects & stats
    effects: _b.str = ""  # Linked effects from skill fields
    damage_type: _b.str = ""
    resist_modifier: _b.str = ""
    target_damage: _b.str = ""
    target_healing: _b.str = ""
    caster_healing: _b.str = ""
    shield_amount: _b.str = ""
    pet_to_summon: _b.str = ""
    status_effect: _b.str = ""
    add_proc: _b.str = ""
    add_proc_chance: _b.str = ""
    has_lifetap: bool = False
    lifesteal: _b.str = ""
    damage_shield: _b.str = ""
    percent_mana_restoration: _b.str = ""
    bleed_damage_percent: _b.str = ""
    special_descriptor: _b.str = ""
    hp: _b.str = ""
    ac: _b.str = ""
    mana: _b.str = ""
    str: _b.str = ""
    dex: _b.str = ""
    end: _b.str = ""
    agi: _b.str = ""
    wis: _b.str = ""
    int: _b.str = ""
    cha: _b.str = ""
    mr: _b.str = ""
    er: _b.str = ""
    vr: _b.str = ""
    pr: _b.str = ""
    haste: _b.str = ""
    resonance: _b.str = ""
    movement_speed: _b.str = ""
    atk_roll_modifier: _b.str = ""
    xp_bonus: _b.str = ""
    is_root: bool = False
    is_stun: bool = False
    is_charm: bool = False
    is_broken_on_damage: bool = False
    # Lists / sources
    itemswitheffect: _b.str = ""
    source: _b.str = ""


# Type aliases for backward compatibility and clarity
SpellInfoboxContext = AbilityInfoboxContext
SkillInfoboxContext = AbilityInfoboxContext

__all__ = ["AbilityInfoboxContext", "SpellInfoboxContext", "SkillInfoboxContext"]
