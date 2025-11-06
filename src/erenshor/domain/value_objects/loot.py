"""Value objects for loot system."""

from pydantic import BaseModel, Field

__all__ = ["LootDropInfo"]


class LootDropInfo(BaseModel):
    """Loot drop information for a character.

    Represents one item that can drop from a character, with drop probability
    and rarity flags.

    Example:
        >>> loot = LootDropInfo(
        ...     item_name="Iron Sword",
        ...     item_stable_key="item:IronSword",
        ...     drop_probability=5.25,
        ...     is_guaranteed=False,
        ...     is_actual=True,
        ...     is_common=True,
        ...     is_uncommon=False,
        ...     is_rare=False,
        ...     is_legendary=False,
        ...     is_unique=False,
        ...     is_visible=True,
        ...     item_unique=False
        ... )
    """

    item_name: str | None = Field(default=None, description="Item display name")
    item_stable_key: str | None = Field(default=None, description="Item stable key (format: 'item:resource_name')")
    drop_probability: float = Field(description="Drop probability percentage (0-100)")
    is_guaranteed: bool = Field(description="Is guaranteed drop")
    is_actual: bool = Field(description="Is actual item (vs placeholder/aggregate)")
    is_common: bool = Field(description="Common rarity tier")
    is_uncommon: bool = Field(description="Uncommon rarity tier")
    is_rare: bool = Field(description="Rare rarity tier")
    is_legendary: bool = Field(description="Legendary rarity tier")
    is_unique: bool = Field(description="Unique rarity tier")
    is_visible: bool = Field(description="Visible in loot table")
    item_unique: bool = Field(description="Item is unique (from Items table)")

    model_config = {"frozen": True}  # Immutable value object
