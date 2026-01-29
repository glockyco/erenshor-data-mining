"""Stance entity model.

This module defines the Stance domain entity representing combat stances
that modify character stats when activated by specific skills.
"""

from pydantic import Field

from .base import BaseEntity


class Stance(BaseEntity):
    """Domain entity representing a combat stance.

    Stances are combat modifiers activated by skills that adjust primary
    stats (Strength, Agility, Intelligence) for tactical advantages.
    The StableKey field is used as the stable identifier.

    All fields match the Unity export schema from the Stances table.
    """

    # Primary keys and identifiers
    stable_key: str = Field(description="Stable key from database (primary key)")

    # Display fields
    display_name: str | None = Field(default=None, description="Display name of the stance")
    stance_desc: str | None = Field(default=None, description="Stance description")
    switch_message: str | None = Field(default=None, description="Message when switching to this stance")

    # Combat modifiers (multipliers)
    max_hp_mod: float | None = Field(default=None, description="Max HP multiplier (1.0 = 100%)")
    damage_mod: float | None = Field(default=None, description="Damage multiplier (1.0 = 100%)")
    proc_rate_mod: float | None = Field(default=None, description="Proc rate multiplier (1.0 = 100%)")
    damage_taken_mod: float | None = Field(default=None, description="Damage taken multiplier (1.0 = 100%)")
    aggro_gen_mod: float | None = Field(default=None, description="Aggro generation multiplier (1.0 = 100%)")
    spell_damage_mod: float | None = Field(default=None, description="Spell damage multiplier (1.0 = 100%)")

    # Self-damage mechanics
    self_damage_per_attack: float | None = Field(default=None, description="Damage to self per melee attack")
    self_damage_per_cast: float | None = Field(default=None, description="Damage to self per spell cast")

    # Lifesteal and resonance
    lifesteal_amount: float | None = Field(default=None, description="Lifesteal amount per hit")
    resonance_amount: float | None = Field(default=None, description="Resonance amount")

    # Special mechanics
    stop_regen: int | None = Field(default=None, description="Stops HP/mana regeneration (boolean)")
