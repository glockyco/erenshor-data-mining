from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.domain.entities.item import Item

if TYPE_CHECKING:
    from erenshor.domain.entities.item_stats import ItemStats


class FakeItemRepository:
    def __init__(self, items: list[Item], stats: dict[str, list[ItemStats]], classes: dict[str, list[str]]) -> None:
        self._items = items
        self._stats = stats
        self._classes = classes

    def get_items_for_wiki_generation(self) -> list[Item]:
        return self._items

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        return self._stats.get(stable_key, [])

    def get_item_classes(self, stable_key: str) -> list[str]:
        return self._classes.get(stable_key, [])


def make_item(**overrides: object) -> Item:
    values = {
        "stable_key": "item:sword_of_flames",
        "item_name": "Sword of Flames",
        "display_name": "Sword of Flames",
        "wiki_page_name": "Sword of Flames",
        "image_name": "Sword of Flames",
        "lore": "Long prose should stay out of Lua data modules.",
        "required_slot": "Primary",
        "this_weapon_type": "Sword",
        "item_level": 12,
        "weapon_dly": 2.5,
        "item_value": 100,
        "sell_value": 25,
        "stackable": 0,
        "is_unique": 1,
    }
    values.update(overrides)
    return Item.model_validate(values)
