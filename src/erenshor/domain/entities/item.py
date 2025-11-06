"""Item entity model.

This module defines the Item domain entity representing in-game items including
equipment, consumables, quest items, crafting materials, and more.
"""

from pydantic import Field

from .base import BaseEntity


class Item(BaseEntity):
    """Domain entity representing an in-game item.

    Items include equipment, weapons, armor, consumables, quest items, crafting materials,
    and other inventory objects. The ResourceName field is used as the stable identifier
    across game versions.

    All fields match the Unity export schema from the Items table.
    """

    # Primary keys and identifiers
    stable_key: str | None = Field(default=None, description="Stable key from database (primary key)")

    # Display fields
    item_name: str | None = Field(default=None, description="Display name shown in game")
    lore: str | None = Field(default=None, description="Item lore/flavor text")

    # Equipment properties
    required_slot: str | None = Field(default=None, description="Equipment slot (e.g., 'Head', 'Chest')")
    this_weapon_type: str | None = Field(default=None, description="Weapon type classification")
    item_level: int | None = Field(
        default=None,
        description="Rough representation of item power. "
        "NOT tied to character level requirements. "
        "All characters can equip items of all levels.",
    )

    # Weapon properties
    weapon_dly: float | None = Field(default=None, description="Weapon attack delay")
    shield: int | None = Field(default=None, description="Boolean flag indicating whether this is a shield")
    weapon_proc_chance: float | None = Field(default=None, description="Weapon proc chance percentage (0-100)")
    weapon_proc_on_hit_stable_key: str | None = Field(default=None, description="Proc effect on hit")

    # Wand properties
    is_wand: int | None = Field(default=None, description="Is wand (boolean as integer)")
    wand_range: int | None = Field(default=None, description="Wand attack range")
    wand_proc_chance: float | None = Field(default=None, description="Wand proc chance percentage (0-100)")
    wand_effect_stable_key: str | None = Field(default=None, description="Wand spell effect")
    wand_bolt_color_r: float | None = Field(default=None, description="Wand bolt red channel")
    wand_bolt_color_g: float | None = Field(default=None, description="Wand bolt green channel")
    wand_bolt_color_b: float | None = Field(default=None, description="Wand bolt blue channel")
    wand_bolt_color_a: float | None = Field(default=None, description="Wand bolt alpha channel")
    wand_bolt_speed: float | None = Field(default=None, description="Wand projectile speed")
    wand_attack_sound_name: str | None = Field(default=None, description="Wand attack sound")

    # Bow properties
    is_bow: int | None = Field(default=None, description="Is bow (boolean as integer)")
    bow_effect_stable_key: str | None = Field(default=None, description="Bow spell effect")
    bow_proc_chance: float | None = Field(default=None, description="Bow proc chance percentage (0-100)")
    bow_range: int | None = Field(default=None, description="Bow attack range")
    bow_arrow_speed: float | None = Field(default=None, description="Arrow projectile speed")
    bow_attack_sound_name: str | None = Field(default=None, description="Bow attack sound")

    # Item effects
    item_effect_on_click_stable_key: str | None = Field(
        default=None, description="Spell triggered when right-clicking item"
    )
    item_skill_use_stable_key: str | None = Field(default=None, description="Skill triggered when right-clicking item")
    teach_spell_stable_key: str | None = Field(default=None, description="Spell taught by item")
    teach_skill_stable_key: str | None = Field(default=None, description="Skill taught by item")
    aura_stable_key: str | None = Field(default=None, description="Spell aura effect")
    worn_effect_stable_key: str | None = Field(default=None, description="Spell effect when worn")
    spell_cast_time: float | None = Field(default=None, description="Cast time for item spell")

    # Quest interactions
    assign_quest_on_read_stable_key: str | None = Field(default=None, description="Quest assigned when read")
    complete_on_read_stable_key: str | None = Field(default=None, description="Quest completed when read")

    # Crafting
    # To craft an item, the player must place a template, ingredients, and a fuel source into a furnace.
    template: int | None = Field(default=None, description="Is crafting template (boolean)")
    template_ingredient_ids: str | None = Field(default=None, description="Ingredient item IDs")
    template_reward_ids: str | None = Field(default=None, description="Reward item IDs")

    # Economic properties
    item_value: int | None = Field(default=None, description="Cost to BUY from vendor")
    sell_value: int | None = Field(default=None, description="Amount received when SELLING to vendor")

    # Item flags
    stackable: int | None = Field(default=None, description="Can stack (boolean)")
    disposable: int | None = Field(default=None, description="Item is CONSUMED when clicked (boolean)")
    unique: int | None = Field(
        default=None,
        description="If true, item won't drop again if already in player's inventory (boolean)",
    )
    relic: int | None = Field(
        default=None,
        description="If true, only one can be equipped at once "
        "(e.g., can't dual-wield same weapon or wear 2x same ring) (boolean)",
    )
    no_trade_no_destroy: int | None = Field(default=None, description="Cannot trade or destroy (boolean)")

    # Book properties
    book_title: str | None = Field(default=None, description="Book title for readable items")

    # Resource properties
    mining: int | None = Field(
        default=None,
        description="Mining power (only used for pickaxes, not currently tied to in-game mechanics)",
    )
    fuel_source: int | None = Field(default=None, description="Is fuel source (boolean)")
    fuel_level: int | None = Field(default=None, description="Fuel power level")

    # Restrictions
    sim_players_cant_get: int | None = Field(default=None, description="Is unavailable to sim players (boolean)")

    # Audio/Visual
    attack_sound_name: str | None = Field(default=None, description="Attack sound effect")
    item_icon_name: str | None = Field(default=None, description="Icon asset name")

    # Equipment interactions
    equipment_to_activate: str | None = Field(default=None, description="Which model to show when equipped")
    hide_hair_when_equipped: int | None = Field(default=None, description="Hide hair when worn (boolean)")
    hide_head_when_equipped: int | None = Field(default=None, description="Hide head when worn (boolean)")
