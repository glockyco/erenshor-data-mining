"""Spell entity model.

This module defines the Spell domain entity representing magical abilities
including damage spells, buffs, debuffs, heals, and crowd control effects.
"""

from pydantic import Field

from .base import BaseEntity


class Spell(BaseEntity):
    """Domain entity representing a magical spell or ability.

    Spells include damage spells, healing spells, buffs, debuffs, crowd control,
    and other magical effects. Spells DO cost mana to use.
    The ResourceName field is used as the stable identifier.

    All fields match the Unity export schema from the Spells table.
    """

    # Primary keys and identifiers
    stable_key: str | None = Field(default=None, description="Stable key from database (primary key)")

    # Display fields
    spell_name: str | None = Field(default=None, description="Display name")
    spell_desc: str | None = Field(default=None, description="Spell description")
    special_descriptor: str | None = Field(default=None, description="Special descriptor")
    # spell_desc and special_descriptor are both prose descriptions of a spell.
    # They should have more-or-less the same semantics but are shown at different places in the UI.

    # Spell classification
    type: str | None = Field(default=None, description="Spell type (Damage, StatusEffect, Beneficial, etc.)")
    line: str | None = Field(default=None, description="Spell line/school (Generic, Global_Buff, Direct_Damage, etc.)")
    required_level: int | None = Field(default=None, description="Minimum level requirement")

    # Casting properties
    mana_cost: int | None = Field(default=None, description="Mana cost to cast")
    sim_usable: int | None = Field(default=None, description="Usable by sim players (boolean)")
    aggro: int | None = Field(default=None, description="Aggro amount generated")
    spell_charge_time: float | None = Field(default=None, description="Cast time (divide by 60 to get seconds)")
    cooldown: float | None = Field(default=None, description="Cooldown in seconds")
    spell_duration_in_ticks: int | None = Field(
        default=None, description="Duration in game ticks (multiply by 3 to get seconds)"
    )
    unstable_duration: int | None = Field(default=None, description="Unstable duration flag")
    instant_effect: int | None = Field(default=None, description="Instant cast (boolean)")

    # Targeting
    spell_range: float | None = Field(default=None, description="Cast range")
    self_only: int | None = Field(default=None, description="Self-cast only (boolean)")
    max_level_target: int | None = Field(default=None, description="Max target level")
    group_effect: int | None = Field(default=None, description="Affects group (boolean)")
    can_hit_players: int | None = Field(default=None, description="Can target players (boolean)")
    apply_to_caster: int | None = Field(default=None, description="Also affects caster (boolean)")

    # Damage/Healing effects
    target_damage: int | None = Field(default=None, description="Damage to target")
    target_healing: int | None = Field(default=None, description="Healing to target")
    caster_healing: int | None = Field(default=None, description="Healing to caster")
    shielding_amt: int | None = Field(default=None, description="Shield/absorb amount")
    lifetap: int | None = Field(default=None, description="Lifetap (boolean)")
    damage_type: str | None = Field(default=None, description="Damage type (magic, poison, etc.)")
    resist_modifier: float | None = Field(default=None, description="Resist check modifier")

    # Proc effects
    add_proc_stable_key: str | None = Field(default=None, description="Additional proc effect")
    # Example add_proc: "Soul Tap (10488989)"
    add_proc_chance: int | None = Field(default=None, description="Proc chance percentage (0-100)")

    # Stat modifications
    hp: int | None = Field(default=None, description="Health modifier")
    ac: int | None = Field(default=None, description="Armor modifier")
    mana: int | None = Field(default=None, description="Mana modifier")
    percent_mana_restoration: int | None = Field(default=None, description="Mana regen percentage")
    movement_speed: float | None = Field(default=None, description="Movement speed modifier")

    # Primary stats
    strength: int | None = Field(default=None, description="Strength modifier", alias="Str")
    dexterity: int | None = Field(default=None, description="Dexterity modifier", alias="Dex")
    endurance: int | None = Field(default=None, description="Endurance modifier", alias="End")
    agility: int | None = Field(default=None, description="Agility modifier", alias="Agi")
    wisdom: int | None = Field(default=None, description="Wisdom modifier", alias="Wis")
    intelligence: int | None = Field(default=None, description="Intelligence modifier", alias="Int")
    charisma: int | None = Field(default=None, description="Charisma modifier", alias="Cha")

    # Resistances
    magic_resist: int | None = Field(default=None, description="Magic resistance modifier", alias="MR")
    elemental_resist: int | None = Field(default=None, description="Elemental resistance modifier", alias="ER")
    poison_resist: int | None = Field(default=None, description="Poison resistance modifier", alias="PR")
    void_resist: int | None = Field(default=None, description="Void resistance modifier", alias="VR")

    # Combat modifiers
    damage_shield: int | None = Field(
        default=None, description="Thorns effect - damage dealt to attackers when they hit the affected character"
    )
    haste: float | None = Field(default=None, description="Haste modifier")
    percent_lifesteal: float | None = Field(default=None, description="Lifesteal percentage")
    atk_roll_modifier: int | None = Field(default=None, description="Attack roll modifier")
    bleed_damage_percent: int | None = Field(default=None, description="Bleed damage percentage")

    # Crowd control
    root_target: int | None = Field(default=None, description="Root effect (boolean)")
    stun_target: int | None = Field(default=None, description="Stun effect (boolean)")
    charm_target: int | None = Field(default=None, description="Charm effect (boolean)")
    crowd_control_spell: int | None = Field(default=None, description="Is CC spell (boolean)")
    break_on_damage: int | None = Field(default=None, description="Break on damage (boolean)")
    break_on_any_action: int | None = Field(default=None, description="Break on any action (boolean)")
    taunt_spell: int | None = Field(default=None, description="Taunt effect (boolean)")

    # Special effects
    pet_to_summon_stable_key: str | None = Field(default=None, description="Summoned pet resource name")
    # pet_to_summon_stable_key is actually the Characters.NPCName of the summoned creature
    status_effect_to_apply_stable_key: str | None = Field(default=None, description="Status effect ID")
    # status_effect_to_apply: "Vithean Revenge (18285300)" # noqa: ERA001 (commented-out code, false positive)
    reap_and_renew: int | None = Field(default=None, description="Reap and Renew mechanic")
    resonate_chance: int | None = Field(default=None, description="Resonate chance percentage")
    xp_bonus: float | None = Field(default=None, description="XP bonus multiplier")
    automate_attack: int | None = Field(default=None, description="Start auto-attacking when used (boolean)")
    worn_effect: int | None = Field(default=None, description="Worn as passive (boolean)")

    # Visual effects
    spell_charge_fx_index: int | None = Field(default=None, description="Charge VFX index")
    spell_resolve_fx_index: int | None = Field(default=None, description="Resolve VFX index")
    spell_icon_name: str | None = Field(default=None, description="Icon asset name")
    shake_dur: float | None = Field(default=None, description="Screen shake duration")
    shake_amp: float | None = Field(default=None, description="Screen shake amplitude")
    color_r: float | None = Field(default=None, description="Effect red channel")
    color_g: float | None = Field(default=None, description="Effect green channel")
    color_b: float | None = Field(default=None, description="Effect blue channel")
    color_a: float | None = Field(default=None, description="Effect alpha channel")

    # Status messages
    status_effect_message_on_player: str | None = Field(
        default=None, description="Message shown in combat log when used on player"
    )
    status_effect_message_on_npc: str | None = Field(
        default=None, description="Message shown in combat log when used on NPC"
    )
