"""Value objects for loot system."""

from dataclasses import dataclass

__all__ = ["ItemDropInfo", "LootDropInfo"]


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


@dataclass(frozen=True)
class ItemDropInfo:
    """One item that can drop from using a source item (e.g. a fossil).

    Pure drop-edge data: the dropped item's StableKey, the drop probability, and
    whether the source guarantees one drop from its pool. The dropped item's page,
    name, and image resolve from the item record at the display layer.
    """

    dropped_item_stable_key: str
    drop_probability: float
    is_guaranteed: bool
