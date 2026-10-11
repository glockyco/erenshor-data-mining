from __future__ import annotations

import pytest
from tests.unit.application.wiki_lua.fakes import make_item

from erenshor.application.wiki_lua.vendor_stock import build_vendor_stock_rows

_SWORD = make_item(stable_key="item:sword", display_name="Sword", item_value=120, required_slot="Primary")
_DRINK = {"required_slot": "General", "disposable": 1, "item_effect_on_click_stable_key": "spell:refresh"}
_BREAD = make_item(stable_key="item:bread", display_name="Bread", item_value=4, **_DRINK)
_ALE = make_item(stable_key="item:ale", display_name="Ale", item_value=4, **_DRINK)
_SET = make_item(
    stable_key="item:set", display_name="Dining Set", item_value=1000, required_slot="General", furniture_set=1
)
_ITEMS = {item.stable_key: item for item in (_SWORD, _BREAD, _ALE, _SET)}


def test_rows_sort_by_type_price_and_name_and_keep_unlocking_quests() -> None:
    stock = [
        ("character:vendor", "item:sword", "quest:b"),
        ("character:vendor", "item:sword", "quest:a"),
        ("character:vendor", "item:bread", None),
        ("character:vendor", "item:bread", "quest:c"),
        ("character:vendor", "item:ale", None),
        ("character:vendor", "item:set", None),
    ]

    rows = build_vendor_stock_rows(stock, _ITEMS)["character:vendor"]

    assert rows == [
        {"item": "item:ale", "price": 4, "type": "Consumable", "typePage": "Consumables"},
        {"item": "item:bread", "price": 4, "type": "Consumable", "typePage": "Consumables"},
        {"item": "item:set", "price": 1000, "type": "Furniture"},
        {"item": "item:sword", "price": 120, "type": "Weapon", "typePage": "Weapons", "quests": ["quest:a", "quest:b"]},
    ]


def test_an_item_without_a_wiki_page_fails_naming_vendor_and_item() -> None:
    with pytest.raises(ValueError, match="character:vendor sells item:hidden, which has no wiki page"):
        build_vendor_stock_rows([("character:vendor", "item:hidden", None)], _ITEMS)
