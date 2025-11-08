"""Item stats entity model.

This module defines the ItemStats domain entity representing item statistics
and quality variations for equipment.
"""

from pydantic import Field

from .base import BaseEntity


class ItemStats(BaseEntity):
    """Domain entity representing item statistics by quality level.

    ItemStats define the stat bonuses that items provide at different quality levels
    (Normal, Blessed, Godly). Each item can have multiple stat entries - one for each
    quality level. Only weapons and armor have item stats.

    The composite key is (item_stable_key, quality).
    """

    # Primary keys (composite)
    item_stable_key: str = Field(description="Item stable key (format: 'item:resource_name')")
    quality: str = Field(description="Quality level (Normal, Blessed, Godly)")

    # Weapon damage
    weapon_dmg: int | None = Field(default=None, description="Weapon damage")

    # Core stats (field names match pascal_to_snake output from DB columns)
    ac: int | None = Field(default=None, description="Armor (from DB column 'AC')")
    hp: int | None = Field(default=None, description="Health (from DB column 'HP')")
    mana: int | None = Field(default=None, description="Mana (from DB column 'Mana')")

    # Primary attributes (using safe field names with aliases for DB columns)
    # Note: 'str', 'int', 'end' are Python builtins, so we use safe names + Field(alias=...)
    str_: int | None = Field(default=None, description="Strength (from DB column 'Str')", alias="str")
    end_: int | None = Field(default=None, description="Endurance (from DB column 'End')", alias="end")
    dex: int | None = Field(default=None, description="Dexterity (from DB column 'Dex')")
    agi: int | None = Field(default=None, description="Agility (from DB column 'Agi')")
    int_: int | None = Field(default=None, description="Intelligence (from DB column 'Int')", alias="int")
    wis: int | None = Field(default=None, description="Wisdom (from DB column 'Wis')")
    cha: int | None = Field(default=None, description="Charisma (from DB column 'Cha')")

    # Special stats (field names match pascal_to_snake output from DB columns)
    res: int | None = Field(default=None, description="Resonance (from DB column 'Res')")

    # Resistances (field names match pascal_to_snake output from DB columns)
    mr: int | None = Field(default=None, description="Magic resistance (from DB column 'MR')")
    er: int | None = Field(default=None, description="Elemental resistance (from DB column 'ER')")
    pr: int | None = Field(default=None, description="Poison resistance (from DB column 'PR')")
    vr: int | None = Field(default=None, description="Void resistance (from DB column 'VR')")

    # Stat scaling properties
    # These are often referred to as "proficiencies" throughout the game.
    str_scaling: float | None = Field(default=None, description="Strength scaling factor")
    end_scaling: float | None = Field(default=None, description="Endurance scaling factor")
    dex_scaling: float | None = Field(default=None, description="Dexterity scaling factor")
    agi_scaling: float | None = Field(default=None, description="Agility scaling factor")
    int_scaling: float | None = Field(default=None, description="Intelligence scaling factor")
    wis_scaling: float | None = Field(default=None, description="Wisdom scaling factor")
    cha_scaling: float | None = Field(default=None, description="Charisma scaling factor")
    resist_scaling: float | None = Field(default=None, description="Resistance scaling factor")
    mitigation_scaling: float | None = Field(default=None, description="Mitigation scaling factor")

    @property
    def composite_key(self) -> str:
        """Generate composite key for lookups.

        Returns:
            Composite key in format "item_stable_key:quality"
        """
        return f"{self.item_stable_key}:{self.quality}"

    @property
    def stable_key(self) -> str:
        """Return stable identifier for this entity.

        Returns:
            Composite key based on resource name and quality.
        """
        return self.composite_key
