"""Value objects for loot system."""

from dataclasses import dataclass

from erenshor.domain.value_objects.wiki_link import ItemLink

__all__ = ["LootDropDisplayInfo", "LootDropInfo"]


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
class LootDropDisplayInfo:
    """Resolved loot-drop data used when rendering character pages.

    The item link and item uniqueness are resolved from the joined item record;
    the remaining fields describe the character's drop edge.
    """

    item_link: ItemLink
    drop_probability: float
    is_guaranteed: bool
    is_visible: bool
    item_unique: bool
