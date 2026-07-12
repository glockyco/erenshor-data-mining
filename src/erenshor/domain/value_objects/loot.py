"""Value objects for loot system."""

from dataclasses import dataclass

__all__ = ["LootDropInfo"]


@dataclass(frozen=True)
class LootDropInfo:
    """One item that can drop from a character.

    Pure drop-edge data: the dropped item is identified by its StableKey, and the
    drop's own facts (probability, guaranteed-pool membership, visible-equipped
    piece). Everything about the *item* — its page, name, image, uniqueness — is
    resolved from the item record at the display layer, never duplicated here.
    """

    item_stable_key: str
    drop_probability: float
    is_guaranteed: bool
    is_visible: bool
