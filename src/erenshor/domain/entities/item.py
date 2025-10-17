"""Item entity model.

This module defines the Item domain entity representing in-game items including
equipment, consumables, quest items, crafting materials, and more.
"""

from pydantic import Field

from erenshor.registry.resource_names import build_stable_key, normalize_resource_name
from erenshor.registry.schema import EntityType

from .base import BaseEntity


class Item(BaseEntity):
    """Domain entity representing an in-game item.

    Items include equipment, weapons, armor, consumables, quest items, crafting materials,
    and other inventory objects. The ResourceName field is used as the stable identifier
    across game versions.

    All fields match the Unity export schema from the Items table.
    """

    # Primary keys and identifiers
    item_db_index: int | None = Field(default=None, description="Database index (auto-generated)")
    id: str = Field(description="Primary key identifier")
    resource_name: str = Field(description="Stable resource identifier")

    # Display fields
    item_name: str | None = Field(default=None, description="Display name shown in game")
    lore: str | None = Field(default=None, description="Item lore/flavor text")

    # Equipment properties
    required_slot: str | None = Field(default=None, description="Equipment slot (e.g., 'Head', 'Chest')")
    this_weapon_type: str | None = Field(default=None, description="Weapon type classification")
    classes: str | None = Field(default=None, description="Class restrictions (comma-separated)")
    item_level: int | None = Field(default=None, description="Item level requirement")

    # Weapon properties
    weapon_dly: float | None = Field(default=None, description="Weapon attack delay")
    shield: int | None = Field(default=None, description="Shield AC value")
    weapon_proc_chance: float | None = Field(default=None, description="Weapon proc chance (0-1)")
    weapon_proc_on_hit: str | None = Field(default=None, description="Proc effect on hit")

    # Wand properties
    is_wand: int | None = Field(default=None, description="Is wand (boolean as integer)")
    wand_range: int | None = Field(default=None, description="Wand attack range")
    wand_proc_chance: float | None = Field(default=None, description="Wand proc chance (0-1)")
    wand_effect: str | None = Field(default=None, description="Wand spell effect")
    wand_bolt_color_r: float | None = Field(default=None, description="Wand bolt red channel")
    wand_bolt_color_g: float | None = Field(default=None, description="Wand bolt green channel")
    wand_bolt_color_b: float | None = Field(default=None, description="Wand bolt blue channel")
    wand_bolt_color_a: float | None = Field(default=None, description="Wand bolt alpha channel")
    wand_bolt_speed: float | None = Field(default=None, description="Wand projectile speed")
    wand_attack_sound_name: str | None = Field(default=None, description="Wand attack sound")

    # Bow properties
    is_bow: int | None = Field(default=None, description="Is bow (boolean as integer)")
    bow_effect: str | None = Field(default=None, description="Bow spell effect")
    bow_proc_chance: float | None = Field(default=None, description="Bow proc chance (0-1)")
    bow_range: int | None = Field(default=None, description="Bow attack range")
    bow_arrow_speed: float | None = Field(default=None, description="Arrow projectile speed")
    bow_attack_sound_name: str | None = Field(default=None, description="Bow attack sound")

    # Item effects
    item_effect_on_click: str | None = Field(default=None, description="Effect when clicked/used")
    item_skill_use: str | None = Field(default=None, description="Skill used by item")
    teach_spell: str | None = Field(default=None, description="Spell taught by item")
    teach_skill: str | None = Field(default=None, description="Skill taught by item")
    aura: str | None = Field(default=None, description="Aura effect when worn")
    worn_effect: str | None = Field(default=None, description="Effect when equipped")
    spell_cast_time: float | None = Field(default=None, description="Cast time for item spell")

    # Quest interactions
    assign_quest_on_read: str | None = Field(default=None, description="Quest assigned when read")
    complete_on_read: str | None = Field(default=None, description="Quest completed when read")

    # Crafting
    template: int | None = Field(default=None, description="Is crafting template (boolean)")
    template_ingredient_ids: str | None = Field(default=None, description="Ingredient item IDs")
    template_reward_ids: str | None = Field(default=None, description="Reward item IDs")

    # Economic properties
    item_value: int | None = Field(default=None, description="Base vendor value")
    sell_value: int | None = Field(default=None, description="Sell price to vendor")

    # Item flags
    stackable: int | None = Field(default=None, description="Can stack (boolean)")
    disposable: int | None = Field(default=None, description="Can be destroyed (boolean)")
    unique: int | None = Field(default=None, description="Unique item (boolean)")
    relic: int | None = Field(default=None, description="Relic item (boolean)")
    no_trade_no_destroy: int | None = Field(default=None, description="Cannot trade or destroy (boolean)")

    # Book properties
    book_title: str | None = Field(default=None, description="Book title for readable items")

    # Resource properties
    mining: int | None = Field(default=None, description="Mining resource (boolean)")
    fuel_source: int | None = Field(default=None, description="Is fuel source (boolean)")
    fuel_level: int | None = Field(default=None, description="Fuel power level")

    # Restrictions
    sim_players_cant_get: int | None = Field(default=None, description="Unavailable to sim players (boolean)")

    # Audio/Visual
    attack_sound_name: str | None = Field(default=None, description="Attack sound effect")
    item_icon_name: str | None = Field(default=None, description="Icon asset name")

    # Equipment interactions
    equipment_to_activate: str | None = Field(default=None, description="Required equipment to activate")
    hide_hair_when_equipped: int | None = Field(default=None, description="Hide hair when worn (boolean)")
    hide_head_when_equipped: int | None = Field(default=None, description="Hide head when worn (boolean)")

    @property
    def stable_key(self) -> str:
        """Generate stable key for registry lookups.

        Returns:
            Stable key in format "item:resource_name"
        """
        return build_stable_key(EntityType.ITEM, self.resource_name)

    @property
    def normalized_resource_name(self) -> str:
        """Get normalized resource name for comparisons.

        Returns:
            Lowercase, whitespace-normalized resource name
        """
        return normalize_resource_name(self.resource_name)
