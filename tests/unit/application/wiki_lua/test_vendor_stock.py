from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeCharacterRepository, FakeItemProvenanceRepository, make_item

from erenshor.application.wiki_lua.vendor_stock import build_vendor_stock_rows, item_type, write_vendor_stock_module
from erenshor.domain.value_objects.item_provenance import ItemUse
from erenshor.domain.value_objects.vendor_stock import VendorStockEntry

_SWORD = make_item(stable_key="item:sword", display_name="Sword", item_value=120, required_slot="Primary")
_DRINK = {"required_slot": "General", "disposable": 1, "item_effect_on_click_stable_key": "spell:refresh"}
_BREAD = make_item(stable_key="item:bread", display_name="Bread", item_value=4, **_DRINK)
_ALE = make_item(stable_key="item:ale", display_name="Ale", item_value=4, **_DRINK)
_SET = make_item(
    stable_key="item:set", display_name="Dining Set", item_value=1000, required_slot="General", furniture_set=1
)
_ITEMS = {item.stable_key: item for item in (_SWORD, _BREAD, _ALE, _SET)}


def _entry(item: str, quest: str | None = None, copy: str = "character:vendor", furniture: str | None = None):
    return VendorStockEntry("character:vendor", copy, furniture, item, quest)


def test_rows_sort_by_type_price_and_name_and_keep_unlocking_quests() -> None:
    stock = [
        _entry("item:sword", "quest:b"),
        _entry("item:sword", "quest:a"),
        _entry("item:bread"),
        _entry("item:bread", "quest:c"),
        _entry("item:ale"),
        _entry("item:set"),
    ]

    rows = build_vendor_stock_rows(stock, _ITEMS, {}, set())["character:vendor"]

    assert rows == [
        {"item": "item:ale", "price": 4, "type": "Consumable", "typePage": "Consumables"},
        {"item": "item:bread", "price": 4, "type": "Consumable", "typePage": "Consumables"},
        {"item": "item:set", "price": 1000, "type": "Furniture"},
        {"item": "item:sword", "price": 120, "type": "Weapon", "typePage": "Weapons", "quests": ["quest:a", "quest:b"]},
    ]


def test_an_item_that_only_some_furniture_copies_sell_names_their_furniture() -> None:
    stock = [
        _entry("item:bread", copy="character:wood", furniture="item:wood set"),
        _entry("item:bread", copy="character:stone", furniture="item:stone set"),
        _entry("item:sword", copy="character:stone", furniture="item:stone set"),
    ]

    rows = {row["item"]: row for row in build_vendor_stock_rows(stock, _ITEMS, {}, set())["character:vendor"]}

    assert "furniture" not in rows["item:bread"]
    assert rows["item:sword"]["furniture"] == ["item:stone set"]


def test_an_item_that_only_some_unfurnished_copies_sell_fails_naming_vendor_and_item() -> None:
    stock = [
        _entry("item:bread", copy="character:vendor"),
        _entry("item:bread", copy="character:vendor twin"),
        _entry("item:sword", copy="character:vendor twin"),
    ]

    with pytest.raises(ValueError, match="Only some copies of character:vendor sell item:sword"):
        build_vendor_stock_rows(stock, _ITEMS, {}, set())


@pytest.mark.parametrize(
    ("fields", "uses", "molds", "expected"),
    [
        ({}, set(), {"item:thing"}, "Mold"),
        ({}, {"crafting_material"}, set(), "Crafting"),
        ({"fuel_source": 1}, set(), set(), "Crafting"),
        ({}, {"crafting_material", "quest_requirement"}, set(), "Crafting"),
        ({}, {"quest_requirement"}, set(), "Quest Item"),
        ({"complete_on_read_stable_key": "quest:a"}, set(), set(), "Quest Item"),
        ({"book_title": "StrangeBeasts"}, set(), set(), "Lore"),
        ({"book_title": ""}, set(), set(), "General"),
        ({"furniture_set": 1}, {"quest_requirement"}, set(), "Furniture"),
    ],
)
def test_a_general_item_is_typed_by_what_it_is_for(
    fields: dict[str, object], uses: set[str], molds: set[str], expected: str
) -> None:
    item = make_item(stable_key="item:thing", required_slot="General", **fields)

    assert item_type(item, uses, molds) == expected


def test_an_item_without_a_wiki_page_fails_naming_vendor_and_item() -> None:
    with pytest.raises(ValueError, match="character:vendor sells item:hidden, which has no wiki page"):
        build_vendor_stock_rows([_entry("item:hidden")], _ITEMS, {}, set())


def test_vendor_writer_uses_canonical_material_and_smithing_mechanic_facts(tmp_path: Path) -> None:
    material = make_item(stable_key="item:material", required_slot="General")
    mold = make_item(stable_key="item:mold", required_slot="General")
    provenance = FakeItemProvenanceRepository(
        [material.stable_key, mold.stable_key],
        uses=[
            ItemUse("craft:slot:3", material.stable_key, mold.stable_key, "crafting_material", material_slot=3),
            ItemUse("smith:fuel", material.stable_key, mold.stable_key, "smithing", mechanic="upgrade_material"),
        ],
    )
    vendors = FakeCharacterRepository([], vendor_stock=[_entry(material.stable_key), _entry(mold.stable_key)])
    path = write_vendor_stock_module(
        vendors,
        [material, mold],
        provenance,
        {"character:vendor", material.stable_key, mold.stable_key},
        tmp_path,
    )
    content = path.read_text(encoding="utf-8")
    assert '["type"] = "Crafting"' in content
    assert '["type"] = "Mold"' in content
