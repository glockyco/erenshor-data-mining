"""Spell entity model.

This module defines the Spell domain entity representing magical abilities
including damage spells, buffs, debuffs, heals, and crowd control effects.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Spell(BaseEntity):
    """Domain entity representing a magical spell or ability.

    Spells include damage spells, healing spells, buffs, debuffs, crowd control,
    and other magical effects. The ResourceName field is used as the stable identifier.

    All fields match the Unity export schema from the Spells table.
    """

    # Primary keys and identifiers
    spell_db_index: int = Field(description="Database index (primary key)")
    id: str | None = Field(default=None, description="Spell ID")
    resource_name: str | None = Field(default=None, description="Stable resource identifier")

    # Display fields
    spell_name: str | None = Field(default=None, description="Display name")
    spell_desc: str | None = Field(default=None, description="Spell description")
    special_descriptor: str | None = Field(default=None, description="Special categorization")

    # Spell classification
    type: str | None = Field(default=None, description="Spell type (damage, heal, buff, etc.)")
    line: str | None = Field(default=None, description="Spell line/school")
    classes: str | None = Field(default=None, description="Class restrictions")
    required_level: int | None = Field(default=None, description="Minimum level requirement")

    # Casting properties
    mana_cost: int | None = Field(default=None, description="Mana cost to cast")
    sim_usable: int | None = Field(default=None, description="Usable by sim players (boolean)")
    aggro: int | None = Field(default=None, description="Aggro amount generated")
    spell_charge_time: float | None = Field(default=None, description="Cast time in seconds")
    cooldown: float | None = Field(default=None, description="Cooldown in seconds")
    spell_duration_in_ticks: int | None = Field(default=None, description="Duration in game ticks")
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
    add_proc: str | None = Field(default=None, description="Additional proc effect")
    add_proc_chance: int | None = Field(default=None, description="Proc chance percentage")

    # Stat modifications
    hp: int | None = Field(default=None, description="HP modifier")
    ac: int | None = Field(default=None, description="AC modifier")
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
    energy_resist: int | None = Field(default=None, description="Energy resistance modifier", alias="ER")
    poison_resist: int | None = Field(default=None, description="Poison resistance modifier", alias="PR")
    vitality_resist: int | None = Field(default=None, description="Vitality resistance modifier", alias="VR")

    # Combat modifiers
    damage_shield: int | None = Field(default=None, description="Damage shield amount")
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
    pet_to_summon_resource_name: str | None = Field(default=None, description="Summoned pet resource name")
    status_effect_to_apply: str | None = Field(default=None, description="Status effect ID")
    reap_and_renew: int | None = Field(default=None, description="Reap and Renew mechanic")
    resonate_chance: int | None = Field(default=None, description="Resonate chance percentage")
    xp_bonus: float | None = Field(default=None, description="XP bonus multiplier")
    automate_attack: int | None = Field(default=None, description="Auto-attack (boolean)")
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
    status_effect_message_on_player: str | None = Field(default=None, description="Player status message")
    status_effect_message_on_npc: str | None = Field(default=None, description="NPC status message")

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Returns:
            Stable key in format "spell:resource_name"

        Raises:
            ValueError: If resource_name is None
        """
        if self.resource_name is None:
            raise ValueError("Cannot generate stable_key: resource_name is None")
        return build_stable_key(EntityType.SPELL, self.resource_name)

    @property
    def normalized_resource_name(self) -> str:
        """Get normalized resource name for comparisons.

        Returns:
            Lowercase, whitespace-normalized resource name

        Raises:
            ValueError: If resource_name is None
        """
        if self.resource_name is None:
            raise ValueError("Cannot normalize: resource_name is None")
        return normalize_resource_name(self.resource_name)
