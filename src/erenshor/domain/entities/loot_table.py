"""Loot table entity model.

This module defines the LootTable domain entity representing loot drop
data for characters and enemies.
"""

from pydantic import Field

from .base import BaseEntity


class LootTable(BaseEntity):
    """Domain entity representing a loot drop entry.

    LootTable entries define what items can drop from characters,
    with associated probabilities and rarity information.

    This entity represents individual drop entries from the LootDrops table.
    Unlike other entities, loot tables don't have a single stable identifier
    field - they are identified by the combination of character and item.
    """

    # Identifiers (composite key)
    character_prefab_guid: str | None = Field(default=None, description="Character GUID")
    item_id: str | None = Field(default=None, description="Item ID that can drop")

    # Drop probability
    drop_probability: float | None = Field(default=None, description="Drop probability percentage (0-100)")
    expected_per_kill: float | None = Field(default=None, description="Expected drops per kill")
    drop_count_distribution: str | None = Field(default=None, description="Drop count distribution data")

    # Drop type flags
    is_actual: int | None = Field(default=None, description="If true, item ALWAYS drops on kill (boolean)")
    is_guaranteed: int | None = Field(
        default=None,
        description="If true, ONE of the guaranteed items always drops on kill (NOT all of them) (boolean)",
    )

    # Rarity flags
    # These are largely irrelevant. They influence how the final drop_probability is calculated.
    # However, `drop_probability` already contains the true drop chance, so rarities are only kept for posterity.
    is_common: int | None = Field(default=None, description="Common rarity (boolean)")
    is_uncommon: int | None = Field(default=None, description="Uncommon rarity (boolean)")
    is_rare: int | None = Field(default=None, description="Rare rarity (boolean)")
    is_legendary: int | None = Field(default=None, description="Legendary rarity (boolean)")

    # Unique flags
    is_unique: int | None = Field(
        default=None,
        description="Item only drops if not already in player's inventory (NOT a rarity class) (boolean)",
    )

    # Visibility
    is_visible: int | None = Field(
        default=None,
        description="If true, shows item on dropping character's model "
        "(players know item will drop if character is wearing it) (boolean)",
    )

    @property
    def composite_key(self) -> str:
        """Generate composite key for lookups.

        Returns:
            Composite key in format "character_guid:item_id"

        Raises:
            ValueError: If either field is None
        """
        if self.character_prefab_guid is None or self.item_id is None:
            raise ValueError("Cannot generate composite_key: character_prefab_guid or item_id is None")
        return f"{self.character_prefab_guid}:{self.item_id}"
