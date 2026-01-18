"""Character entity model.

This module defines the Character domain entity representing
all friendly and non-friendly NPCs, creatures, etc.
"""

from pydantic import Field

from erenshor.domain.value_objects.faction import FactionModifier

from .base import BaseEntity


class Character(BaseEntity):
    """Domain entity representing an in-game character (NPC, enemy, etc.).

    Characters include all non-player entities such as enemies, vendors, quest givers,
    and other friendly NPCs. The ObjectName field is used as the stable identifier.

    All fields match the Unity export schema from the Characters table.
    """

    # Primary keys and identifiers
    stable_key: str = Field(description="Stable key from database (primary key)")
    object_name: str | None = Field(default=None, description="Stable object identifier")
    npc_name: str | None = Field(default=None, description="Display name")

    # Coordinate data (embedded in Characters table)
    scene: str | None = Field(default=None, description="Scene name")
    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate")

    # Faction
    my_world_faction_stable_key: str | None = Field(
        default=None, description="World faction stable key (e.g., 'faction:good')"
    )
    my_faction: str | None = Field(default=None, description="Faction")
    aggro_range: float | None = Field(default=None, description="Aggro detection range")
    attack_range: float | None = Field(default=None, description="Attack range")
    aggressive_towards: str | None = Field(default=None, description="Hostile factions")
    allies: str | None = Field(default=None, description="Allied factions")
    has_modify_faction: int | None = Field(default=None, description="Rewards reputation on kill (boolean)")
    faction_modifiers: list[FactionModifier] | None = Field(
        default=None,
        description="On-kill reputation changes (from CharacterFactionModifiers junction table)",
    )

    # Character type flags
    is_prefab: int | None = Field(default=None, description="Is prefab (boolean)")
    is_common: int | None = Field(default=None, description="Is common spawn (boolean)")
    is_rare: int | None = Field(default=None, description="Is rare spawn (boolean)")
    is_unique: int | None = Field(default=None, description="Is unique/boss (boolean)")
    is_friendly: int | None = Field(default=None, description="Is friendly (boolean)")
    is_npc: int | None = Field(default=None, description="Is NPC (boolean)")
    is_sim_player: int | None = Field(default=None, description="Is SimPlayer (boolean)")
    is_vendor: int | None = Field(default=None, description="Is vendor (boolean)")
    is_mining_node: int | None = Field(default=None, description="Is mining node (boolean)")

    # Feature flags
    has_stats: int | None = Field(default=None, description="Has combat stats (boolean)")
    has_dialog: int | None = Field(default=None, description="Has dialog (boolean)")
    is_enabled: int | None = Field(default=None, description="Is enabled (boolean)")
    invulnerable: int | None = Field(default=None, description="Is invulnerable (boolean)")

    # Death events
    shout_on_death: str | None = Field(default=None, description="Death shout message")
    quest_complete_on_death: str | None = Field(default=None, description="Quest completed on death")
    destroy_on_death: int | None = Field(default=None, description="Destroy on death (boolean)")

    # Base stats
    level: int | None = Field(default=None, description="Character level")
    base_xp_min: float | None = Field(default=None, description="Min XP received when killed (before multipliers)")
    base_xp_max: float | None = Field(default=None, description="Max XP received when killed (before multipliers)")
    boss_xp_multiplier: float | None = Field(default=None, description="XP multiplier")
    base_hp: int | None = Field(default=None, description="Base health points")
    base_ac: int | None = Field(default=None, description="Base armor class")
    base_mana: int | None = Field(default=None, description="Base mana")

    # Primary attributes
    base_str: int | None = Field(default=None, description="Base strength")
    base_end: int | None = Field(default=None, description="Base endurance")
    base_dex: int | None = Field(default=None, description="Base dexterity")
    base_agi: int | None = Field(default=None, description="Base agility")
    base_int: int | None = Field(default=None, description="Base intelligence")
    base_wis: int | None = Field(default=None, description="Base wisdom")
    base_cha: int | None = Field(default=None, description="Base charisma")
    base_res: int | None = Field(default=None, description="Base resonance (chance to double-cast spells)")

    # Resistances
    base_mr: int | None = Field(default=None, description="Base magic resistance")
    base_er: int | None = Field(default=None, description="Base elemental resistance")
    base_pr: int | None = Field(default=None, description="Base poison resistance")
    base_vr: int | None = Field(default=None, description="Base void resistance")

    # Combat attributes
    run_speed: float | None = Field(default=None, description="Movement speed")
    base_life_steal: float | None = Field(default=None, description="Base lifesteal")
    base_mh_atk_delay: float | None = Field(default=None, description="Main hand attack delay")
    base_oh_atk_delay: float | None = Field(default=None, description="Off hand attack delay")

    # Effective stats (calculated)
    effective_hp: int | None = Field(default=None, description="Calculated HP")
    effective_ac: int | None = Field(default=None, description="Calculated AC")
    effective_base_atk_dmg: int | None = Field(default=None, description="Calculated base damage")
    effective_attack_ability: float | None = Field(default=None, description="Calculated attack rating")
    effective_min_mr: int | None = Field(default=None, description="Calculated min magic resist")
    effective_max_mr: int | None = Field(default=None, description="Calculated max magic resist")
    effective_min_er: int | None = Field(default=None, description="Calculated min elemental resist")
    effective_max_er: int | None = Field(default=None, description="Calculated max elemental resist")
    effective_min_pr: int | None = Field(default=None, description="Calculated min poison resist")
    effective_max_pr: int | None = Field(default=None, description="Calculated max poison resist")
    effective_min_vr: int | None = Field(default=None, description="Calculated min void resist")
    effective_max_vr: int | None = Field(default=None, description="Calculated max void resist")

    # Abilities - stored in junction tables:
    # - CharacterAttackSkillRecord
    # - CharacterAttackSpellRecord, CharacterBuffSpellRecord, CharacterHealSpellRecord
    # - CharacterGroupHealSpellRecord, CharacterCCSpellRecord, CharacterTauntSpellRecord

    # Proc mechanics
    pet_spell_stable_key: str | None = Field(default=None, description="Pet summon spell ResourceName")
    proc_on_hit_stable_key: str | None = Field(default=None, description="Proc spell ResourceName")
    proc_on_hit_chance: float | None = Field(default=None, description="Proc chance percentage (0-100)")

    # Stat overrides
    hand_set_resistances: int | None = Field(default=None, description="Uses manually set resistances (boolean)")
    hard_set_ac: int | None = Field(default=None, description="Uses manually set AC value")

    # Damage properties
    base_atk_dmg: int | None = Field(default=None, description="Base attack damage")
    oh_atk_dmg: int | None = Field(default=None, description="Off-hand attack damage")
    min_atk_dmg: int | None = Field(default=None, description="Minimum attack damage")
    damage_range_min: float | None = Field(default=None, description="Damage variance min")
    damage_range_max: float | None = Field(default=None, description="Damage variance max")
    damage_mult: float | None = Field(default=None, description="Damage multiplier")
    armor_pen_mult: float | None = Field(default=None, description="Armor penetration multiplier")
    power_attack_base_dmg: int | None = Field(default=None, description="Power attack base damage")
    power_attack_freq: float | None = Field(default=None, description="Power attack frequency")

    # AI behavior
    heal_tolerance: float | None = Field(default=None, description="Heal at HP threshold (0-1)")
    leash_range: float | None = Field(default=None, description="Leash distance from spawn")
    aggro_regardless_of_level: int | None = Field(default=None, description="Ignore level for aggro (boolean)")
    mobile: int | None = Field(default=None, description="Can move (boolean)")
    group_encounter: int | None = Field(default=None, description="Group encounter (boolean)")

    # Special flags
    treasure_chest: int | None = Field(default=None, description="Is treasure chest (boolean)")
    do_not_leave_corpse: int | None = Field(default=None, description="No corpse on death (boolean)")

    # Achievements
    set_achievement_on_defeat: str | None = Field(default=None, description="Achievement on defeat")
    set_achievement_on_spawn: str | None = Field(default=None, description="Achievement on spawn")

    # Messages
    aggro_msg: str | None = Field(default=None, description="Aggro message")
    aggro_emote: str | None = Field(default=None, description="Aggro emote")
    spawn_emote: str | None = Field(default=None, description="Spawn emote")

    # Guild
    guild_name: str | None = Field(default=None, description="Guild name")

    # Vendor data
    vendor_desc: str | None = Field(default=None, description="Vendor description")
    items_for_sale: str | None = Field(default=None, description="Vendor inventory IDs")
    # LEGACY! Use junction table (ItemsForSale) instead of items_for_sale.
    # Example items_for_sale: "The Fall of Rockshade Hold, Strange Beasts of Erenshor, The Birth of Port Azure"
