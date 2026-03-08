"""Value objects for loot system."""

from dataclasses import dataclass

from erenshor.domain.value_objects.wiki_link import ItemLink

__all__ = ["LootDropInfo"]


@dataclass(frozen=True)
class LootDropInfo:
    """Loot drop information for a character.

    Represents one item that can drop from a character, with drop probability
    and rarity flags.

    The item_link is a pre-built ItemLink constructed by the repository
    from JOIN columns. Section generators call str(item_link) to render it.
    """

    item_link: ItemLink
    drop_probability: float
    is_guaranteed: bool
    is_actual: bool
    is_common: bool
    is_uncommon: bool
    is_rare: bool
    is_legendary: bool
    is_unique: bool
    is_visible: bool
    item_unique: bool
