"""Character entity model.

This module defines the Character domain entity representing
all friendly and non-friendly NPCs, creatures, etc.
"""

from pydantic import Field

from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Character(BaseEntity):
    """Domain entity representing an in-game character (NPC, enemy, etc.).

    Characters include all non-player entities such as enemies, vendors, quest givers,
    and other friendly NPCs. The ObjectName field is used as the stable identifier.

    All fields match the Unity export schema from the Characters table.
    """

    # Primary keys and identifiers
    id: int = Field(description="Database ID (primary key)")
    coordinate_id: int | None = Field(default=None, description="Coordinate reference")
    # Prefabs and non-prefabs have different GUID formats:
    # - Example prefab GUID: "0075a488310a97f4d84a3c31f2998a8a"
    # - Example non-prefab GUID: "scene:Azure:2486006"
    guid: str | None = Field(default=None, description="Unity GUID")
    object_name: str | None = Field(default=None, description="Stable object identifier")
    npc_name: str | None = Field(default=None, description="Display name")

    # Coordinate data (from Coordinates table JOIN)
    scene: str | None = Field(default=None, description="Scene name")
    x: float | None = Field(default=None, description="X coordinate")
    y: float | None = Field(default=None, description="Y coordinate")
    z: float | None = Field(default=None, description="Z coordinate")

    # Faction
    my_world_faction: str | None = Field(default=None, description="World faction (Factions.REFNAME)")
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

    # Abilities (comma-separated lists - LEGACY DATA, use junction tables instead)
    # WARNING: These fields contain legacy data with mixed formats.
    # Use junction tables (CharacterAttackSpells, CharacterBuffSpells, etc.) for reliable ability relationships.
    attack_skills: str | None = Field(default=None, description="Attack skill IDs (legacy, use junction tables)")
    attack_spells: str | None = Field(default=None, description="Attack spell IDs (legacy, use junction tables)")
    buff_spells: str | None = Field(default=None, description="Buff spell IDs (legacy, use junction tables)")
    heal_spells: str | None = Field(default=None, description="Heal spell IDs (legacy, use junction tables)")
    group_heal_spells: str | None = Field(
        default=None, description="Group heal spell IDs (legacy, use junction tables)"
    )
    cc_spells: str | None = Field(default=None, description="Crowd control spell IDs (legacy, use junction tables)")
    taunt_spells: str | None = Field(default=None, description="Taunt spell IDs (legacy, use junction tables)")
    pet_spell: str | None = Field(default=None, description="Pet summon spell ID (legacy, use junction tables)")

    # Proc mechanics
    proc_on_hit: str | None = Field(default=None, description="Proc effect on hit")
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

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Format depends on whether character is a prefab:
        - Prefab: "character:object_name"
        - Non-prefab: "character:object_name|scene|x|y|z"

        Non-prefab characters (scene-specific instances) need coordinates
        for unique identification since multiple different characters can
        exist in the same scene.

        Returns:
            Stable key for registry lookups

        Raises:
            ValueError: If object_name is None
        """
        if self.object_name is None:
            raise ValueError("Cannot generate stable_key: object_name is None")

        # Prefab characters: simple object name
        if self.is_prefab:
            return build_stable_key(EntityType.CHARACTER, self.object_name)

        # Non-prefab characters: include scene and coordinates
        scene = self.scene if self.scene is not None else "Unknown"
        x = f"{self.x:.2f}" if self.x is not None else "0.00"
        y = f"{self.y:.2f}" if self.y is not None else "0.00"
        z = f"{self.z:.2f}" if self.z is not None else "0.00"
        identifier = f"{self.object_name}|{scene}|{x}|{y}|{z}"
        return build_stable_key(EntityType.CHARACTER, identifier)

    @property
    def normalized_resource_name(self) -> str:
        """Get normalized resource name for comparisons.

        Returns:
            Lowercase, whitespace-normalized object name

        Raises:
            ValueError: If object_name is None
        """
        if self.object_name is None:
            raise ValueError("Cannot normalize: object_name is None")
        return normalize_resource_name(self.object_name)
