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
    quality level.

    The composite key is (item_id, quality).
    """

    # Primary keys (composite)
    item_id: str = Field(description="Item ID (references Items.Id)")
    quality: str = Field(description="Quality level (Normal, Blessed, Godly)")

    # Weapon damage
    weapon_dmg: int | None = Field(default=None, description="Weapon damage bonus")

    # Core stats
    hp: int | None = Field(default=None, description="Health points", alias="HP")
    ac: int | None = Field(default=None, description="Armor class", alias="AC")
    mana: int | None = Field(default=None, description="Mana", alias="Mana")

    # Primary attributes
    strength: int | None = Field(default=None, description="Strength", alias="Str")
    endurance: int | None = Field(default=None, description="Endurance", alias="End")
    dexterity: int | None = Field(default=None, description="Dexterity", alias="Dex")
    agility: int | None = Field(default=None, description="Agility", alias="Agi")
    intelligence: int | None = Field(default=None, description="Intelligence", alias="Int")
    wisdom: int | None = Field(default=None, description="Wisdom", alias="Wis")
    charisma: int | None = Field(default=None, description="Charisma", alias="Cha")

    # Special stats
    res: int | None = Field(default=None, description="Resonance", alias="Res")

    # Resistances
    mr: int | None = Field(default=None, description="Magic resistance", alias="MR")
    er: int | None = Field(default=None, description="Elemental resistance", alias="ER")
    pr: int | None = Field(default=None, description="Poison resistance", alias="PR")
    vr: int | None = Field(default=None, description="Void resistance", alias="VR")

    # Stat scaling properties
    str_scaling: float | None = Field(default=None, description="Strength scaling factor")
    end_scaling: float | None = Field(default=None, description="Endurance scaling factor")
    dex_scaling: float | None = Field(default=None, description="Dexterity scaling factor")
    agi_scaling: float | None = Field(default=None, description="Agility scaling factor")
    int_scaling: float | None = Field(default=None, description="Intelligence scaling factor")
    wis_scaling: float | None = Field(default=None, description="Wisdom scaling factor")
    cha_scaling: float | None = Field(default=None, description="Charisma scaling factor")
    resist_scaling: float | None = Field(default=None, description="Resistance scaling factor")
    mitigation_scaling: float | None = Field(default=None, description="Mitigation scaling factor")

    # Wiki export
    wiki_string: str | None = Field(default=None, description="Formatted wiki string")

    @property
    def composite_key(self) -> str:
        """Generate composite key for lookups.

        Returns:
            Composite key in format "item_id:quality"
        """
        return f"{self.item_id}:{self.quality}"
