from dataclasses import replace

from erenshor.tools.vendor_inventory_tables import (
    ExistingInventoryItem,
    InventoryItem,
    VendorInventory,
    existing_type_index,
    parse_inventory_table,
    render_inventory_table,
    render_report,
    replace_inventory_table,
)


def _item(
    name: str,
    *,
    stable_key: str,
    price: int,
    teach_spell: str | None = None,
    required_slot: str = "General",
    weapon_type: str = "None",
    shield: bool = False,
    unlock_quests: set[str] | None = None,
) -> InventoryItem:
    return InventoryItem(
        stable_key=stable_key,
        display_name=name,
        wiki_page_name=name,
        required_slot=required_slot,
        weapon_type=weapon_type,
        teach_spell=teach_spell,
        teach_skill=None,
        is_template=False,
        click_effect=None,
        disposable=False,
        shield=shield,
        price=price,
        unlock_quests=unlock_quests or set(),
    )


def test_parse_inventory_table_accepts_itemlink_and_plain_links() -> None:
    wikitext = """
{| class="wikitable"
|+Store inventory
!Item name
!Item type
!Price
|-
|{{ItemLink|Copper Sword}}
|[[Weapons#Swords|Sword]]
|56
|-
|[[Spell Scroll: Group Healing]]
|[[Ability Books|Spell Scroll]]
|1,255
|}
"""

    parsed = parse_inventory_table(wikitext)

    assert parsed == (
        ExistingInventoryItem("Copper Sword", "[[Weapons#Swords|Sword]]", 56),
        ExistingInventoryItem("Spell Scroll: Group Healing", "[[Ability Books|Spell Scroll]]", 1255),
    )


def test_parse_inventory_table_uses_itemlink_display_text() -> None:
    wikitext = """
{| class="wikitable"
|+Store inventory
!Item name
!Item type
!Price
|-
|{{ItemLink|Spell Scroll: Meditative Trance|text=Spell Scroll: Meditative Trance (1)|stablekey=item:scroll}}
|[[Ability Books|Spell Scroll]]
|1100
|}
"""

    assert parse_inventory_table(wikitext) == (
        ExistingInventoryItem("Spell Scroll: Meditative Trance (1)", "[[Ability Books|Spell Scroll]]", 1100),
    )


def test_render_inventory_table_sorts_by_type_then_price_then_name() -> None:
    inventory = VendorInventory(
        "Vendor",
        (
            _item("Expensive General", stable_key="item:expensive", price=100),
            _item("Spell", stable_key="item:spell", price=5, teach_spell="spell:key"),
            _item("Zulu General", stable_key="item:zulu", price=20),
            _item("Alpha General", stable_key="item:alpha", price=20),
        ),
    )

    table = render_inventory_table(inventory, {})

    names = [
        "Alpha General",
        "Zulu General",
        "Expensive General",
        "Spell",
    ]
    assert [table.index(name) for name in names] == sorted(table.index(name) for name in names)
    assert "!Unlock condition" not in table


def test_render_inventory_table_uses_broad_equipment_types() -> None:
    inventory = VendorInventory(
        "Vendor",
        (
            _item("Sword", stable_key="item:sword", price=10, required_slot="Primary", weapon_type="Sword"),
            _item("Boots", stable_key="item:boots", price=20, required_slot="Foot"),
            _item("Shield", stable_key="item:shield", price=30, required_slot="Secondary", shield=True),
        ),
    )

    table = render_inventory_table(inventory, {})

    assert table.count("|[[Weapons|Weapon]]") == 1
    assert table.count("|[[Armor]]") == 2
    assert "|[[Weapons#Swords|Sword]]" not in table
    assert "|[[Armor#" not in table


def test_render_inventory_table_uses_broad_consumable_type() -> None:
    inventory = VendorInventory(
        "Vendor",
        (
            _item("Water", stable_key="item:water", price=1),
            _item("Bread", stable_key="item:bread", price=2),
        ),
    )

    table = render_inventory_table(
        inventory,
        {
            "Water": "[[Consumables|Drink]]",
            "Bread": "[[Consumables|Food]]",
        },
    )

    assert table.count("|[[Consumables|Consumable]]") == 2
    assert "|[[Consumables|Drink]]" not in table
    assert "|[[Consumables|Food]]" not in table


def test_render_inventory_table_preserves_display_name_for_shared_page() -> None:
    inventory = VendorInventory(
        "Vendor",
        (
            replace(
                _item(
                    "Spell Scroll: Meditative Trance (1)",
                    stable_key="item:spell scroll - meditate",
                    price=1100,
                    teach_spell="spell:meditative-trance",
                ),
                wiki_page_name="Spell Scroll: Meditative Trance",
            ),
        ),
    )
    table = render_inventory_table(inventory, {})

    assert "text=Spell Scroll: Meditative Trance (1)" in table
    assert "{{ItemLink|Spell Scroll: Meditative Trance|" in table


def test_existing_type_index_prefers_specific_type_over_general_item() -> None:
    tables = {
        "First": (ExistingInventoryItem("Eternal Ice", "[[:Category:Items|General Item]]", 5),),
        "Second": (ExistingInventoryItem("Eternal Ice", "[[Quest Items|Quest Item]]", 5),),
    }

    assert existing_type_index(tables)["Eternal Ice"] == "[[Quest Items|Quest Item]]"


def test_render_report_filters_current_tables_and_marks_quest_unlocks() -> None:
    current_item = _item("Bread", stable_key="item:bread", price=2)
    unlocked_item = _item(
        "Spell Scroll: New Spell",
        stable_key="item:new-spell",
        price=100,
        teach_spell="spell:new",
        unlock_quests={"A New Quest"},
    )
    inventories = (
        VendorInventory("Current Vendor", (current_item,)),
        VendorInventory("Stale Vendor", (unlocked_item,)),
    )
    existing = {
        "Current Vendor": (ExistingInventoryItem("Bread", "[[Consumables|Food]]", 2),),
        "Stale Vendor": None,
    }

    report, page_count, row_count = render_report(inventories, existing, include_all=False)

    assert page_count == 1
    assert row_count == 1
    assert "== Current Vendor ==" not in report
    assert "== Stale Vendor ==" in report
    assert "{{ItemLink|Spell Scroll: New Spell|stablekey=item:new-spell}}" in report
    assert "[[Ability Books|Spell Scroll]]" in report
    assert "!Unlock condition" in report
    assert "|Complete [[A New Quest]]" in report
    assert "<ref>" not in report


def test_replace_inventory_table_preserves_surrounding_article_content() -> None:
    old_text = """{{Character|name=Vendor}}

Manual introduction.

{| class="wikitable"
|+Store inventory
!Item name
!Item type
!Price
|-
|{{ItemLink|Old Item}}
|[[:Category:Items|General Item]]
|1
|}

Manual closing text.

[[Category:Characters]]
[[Category:Vendors]]
"""
    inventory = VendorInventory(
        "Vendor",
        (_item("Spell Scroll: New Spell", stable_key="item:new-spell", price=100, teach_spell="spell:new"),),
    )

    updated = replace_inventory_table(old_text, render_inventory_table(inventory, {}))

    assert updated.startswith("{{Character|name=Vendor}}\n\nManual introduction.\n\n")
    assert "Old Item" not in updated
    assert "Spell Scroll: New Spell" in updated
    assert "\n\nManual closing text.\n\n[[Category:Characters]]" in updated


def test_replace_inventory_table_inserts_missing_table_before_categories() -> None:
    old_text = """{{Character|name=Vendor}}

Manual article text.

[[Category:Characters]]
[[Category:Vendors]]
"""
    inventory = VendorInventory("Vendor", (_item("Bread", stable_key="item:bread", price=2),))

    updated = replace_inventory_table(old_text, render_inventory_table(inventory, {}))

    assert updated.startswith('{{Character|name=Vendor}}\n\nManual article text.\n\n{| class="wikitable"')
    assert updated.endswith("|}\n\n[[Category:Characters]]\n[[Category:Vendors]]\n")
