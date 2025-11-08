"""Skill entity model.

This module defines the Skill domain entity representing combat skills
and special abilities used by players and NPCs.
"""

from pydantic import Field

from .base import BaseEntity


class Skill(BaseEntity):
    """Domain entity representing a combat skill or special ability.

    Skills are activated abilities that often have equipment requirements
    (e.g., require bow, require shield). Skills do NOT cost mana to use.
    The ResourceName field is used as the stable identifier.

    All fields match the Unity export schema from the Skills table.
    """

    # Primary keys and identifiers
    stable_key: str = Field(description="Stable key from database (primary key)")

    # Display fields
    skill_name: str | None = Field(default=None, description="Display name")
    skill_desc: str | None = Field(default=None, description="Skill description")

    # Skill classification
    type_of_skill: str | None = Field(default=None, description="Skill type")
    cooldown: float | None = Field(default=None, description="Cooldown (divide by 60 to get seconds)")

    # Class requirements (level requirements per class)
    duelist_required_level: int | None = Field(default=None, description="Duelist level requirement")
    paladin_required_level: int | None = Field(default=None, description="Paladin level requirement")
    arcanist_required_level: int | None = Field(default=None, description="Arcanist level requirement")
    druid_required_level: int | None = Field(default=None, description="Druid level requirement")
    stormcaller_required_level: int | None = Field(default=None, description="Stormcaller level requirement")

    # Equipment requirements
    require_behind: int | None = Field(default=None, description="Requires backstab position (boolean)")
    require_2h: int | None = Field(default=None, description="Requires two-handed weapon (boolean)")
    require_dw: int | None = Field(default=None, description="Requires dual wield (boolean)")
    require_bow: int | None = Field(default=None, description="Requires bow (boolean)")
    require_shield: int | None = Field(default=None, description="Requires shield (boolean)")

    # Availability
    sim_players_autolearn: int | None = Field(default=None, description="Auto-learned by sim players (boolean)")

    # Skill effects
    ae_skill: int | None = Field(default=None, description="Area effect skill (boolean)")
    interrupt: int | None = Field(default=None, description="Interrupts target (boolean)")
    spawn_on_use_stable_key: str | None = Field(default=None, description="Spawned character stable key")
    effect_to_apply_stable_key: str | None = Field(default=None, description="Applied effect stable key (spell)")

    # Targeting
    affect_player: int | None = Field(default=None, description="Affects player (boolean)")
    affect_target: int | None = Field(default=None, description="Affects target (boolean)")
    skill_range: float | None = Field(default=None, description="Skill range")

    # Damage properties
    skill_power: int | None = Field(default=None, description="Base skill power")
    percent_dmg: float | None = Field(default=None, description="Damage multiplier (NOT actually a percentage)")
    damage_type: str | None = Field(default=None, description="Damage type")
    scale_off_weapon: int | None = Field(default=None, description="Scales with weapon damage (boolean)")

    # Proc mechanics
    proc_weap: int | None = Field(default=None, description="Proc weapon effects (boolean)")
    proc_shield: int | None = Field(default=None, description="Proc shield effects (boolean)")
    guarantee_proc: int | None = Field(default=None, description="Guaranteed proc (boolean)")

    # Automation
    automate_attack: int | None = Field(default=None, description="Start auto-attacking when used (boolean)")
    cast_on_target_stable_key: str | None = Field(default=None, description="Cast spell ResourceName on target")

    # Visual/Audio
    skill_anim_name: str | None = Field(default=None, description="Animation name")
    skill_icon_name: str | None = Field(default=None, description="Icon asset name")

    # Usage tracking
    player_uses: str | None = Field(default=None, description="Message shown in combat log when used by player")
    npc_uses: str | None = Field(default=None, description="Message shown in combat log when used by NPC")
