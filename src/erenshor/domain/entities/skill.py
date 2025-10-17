"""Skill entity model.

This module defines the Skill domain entity representing combat skills
and special abilities used by players and NPCs.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Skill(BaseEntity):
    """Domain entity representing a combat skill or special ability.

    Skills are activated abilities that often have equipment requirements
    (e.g., require bow, require shield). The ResourceName field is used
    as the stable identifier.

    All fields match the Unity export schema from the Skills table.
    """

    # Primary keys and identifiers
    skill_db_index: int = Field(description="Database index (primary key)")
    id: str | None = Field(default=None, description="Skill ID")
    resource_name: str | None = Field(default=None, description="Stable resource identifier")

    # Display fields
    skill_name: str | None = Field(default=None, description="Display name")
    skill_desc: str | None = Field(default=None, description="Skill description")

    # Skill classification
    type_of_skill: str | None = Field(default=None, description="Skill type")
    cooldown: float | None = Field(default=None, description="Cooldown in seconds")

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
    spawn_on_use_resource_name: str | None = Field(default=None, description="Spawned entity on use")
    effect_to_apply_id: str | None = Field(default=None, description="Applied effect ID (can only contain spell IDs)")

    # Targeting
    affect_player: int | None = Field(default=None, description="Affects player (boolean)")
    affect_target: int | None = Field(default=None, description="Affects target (boolean)")
    skill_range: float | None = Field(default=None, description="Skill range")

    # Damage properties
    skill_power: int | None = Field(default=None, description="Base skill power")
    percent_dmg: float | None = Field(default=None, description="Damage percentage modifier")
    damage_type: str | None = Field(default=None, description="Damage type")
    scale_off_weapon: int | None = Field(default=None, description="Scales with weapon damage (boolean)")

    # Proc mechanics
    proc_weap: int | None = Field(default=None, description="Proc weapon effects (boolean)")
    proc_shield: int | None = Field(default=None, description="Proc shield effects (boolean)")
    guarantee_proc: int | None = Field(default=None, description="Guaranteed proc (boolean)")

    # Automation
    automate_attack: int | None = Field(
        default=None, description="Causes character to start auto-attacking when skill is used (boolean)"
    )
    cast_on_target_id: str | None = Field(default=None, description="Cast spell on target")

    # Visual/Audio
    skill_anim_name: str | None = Field(default=None, description="Animation name")
    skill_icon_name: str | None = Field(default=None, description="Icon asset name")

    # Usage tracking
    player_uses: str | None = Field(
        default=None, description="Message shown in combat log when skill is used by player"
    )
    npc_uses: str | None = Field(default=None, description="Message shown in combat log when skill is used by NPC")

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Returns:
            Stable key in format "skill:resource_name"

        Raises:
            ValueError: If resource_name is None
        """
        if self.resource_name is None:
            raise ValueError("Cannot generate stable_key: resource_name is None")
        return build_stable_key(EntityType.SKILL, self.resource_name)

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
