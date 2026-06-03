from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item

from erenshor.application.wiki_lua.items import build_items_data, generate_items_modules, write_items_modules
from erenshor.domain.entities.item_stats import ItemStats


def test_builds_item_index_and_sharded_records_without_long_prose_fields() -> None:
    item = make_item()
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": "item:sword_of_flames",
                "quality": "Normal",
                "weapon_dmg": 7,
                "str": 1,
                "dex": None,
                "ac": 3,
            }
        )
    ]

    data = build_items_data(
        items=[item],
        stats_by_item={item.stable_key: stats},
        classes_by_item={item.stable_key: ["Knight", "Paladin"]},
    )

    assert data == {
        "index": {"byKey": {"item:sword_of_flames": "Weapons"}},
        "shards": {
            "Weapons": {
                "item:sword_of_flames": {
                    "name": "Sword of Flames",
                    "page": "Sword of Flames",
                    "image": "Sword of Flames",
                    "slot": "Primary",
                    "weaponType": "Sword",
                    "itemLevel": 12,
                    "weaponDelay": 2.5,
                    "buyValue": 100,
                    "sellValue": 25,
                    "stackable": False,
                    "unique": True,
                    "type": "Weapon",
                    "damage": 7,
                    "armor": 3,
                    "classes": ["Knight", "Paladin"],
                    "stats": [
                        {
                            "quality": "Normal",
                            "weaponDamage": 7,
                            "ac": 3,
                            "str": 1,
                        }
                    ],
                }
            }
        },
    }


def test_uses_zero_quality_stat_as_summary_base_tier() -> None:
    item = make_item()
    blessed = ItemStats.model_validate(
        {
            "item_stable_key": item.stable_key,
            "quality": "Blessed",
            "weapon_dmg": 12,
            "ac": 6,
        }
    )
    base = ItemStats.model_validate(
        {
            "item_stable_key": item.stable_key,
            "quality": "0",
            "weapon_dmg": 7,
            "ac": 3,
        }
    )

    data = build_items_data(items=[item], stats_by_item={item.stable_key: [blessed, base]}, classes_by_item={})

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["damage"] == 7
    assert item_data["armor"] == 3


def test_builds_effect_chance_fields_for_overview_notes() -> None:
    item = make_item(
        weapon_proc_on_hit_stable_key="spell:ember_proc",
        weapon_proc_chance=33,
        wand_effect_stable_key="spell:wand_proc",
        wand_proc_chance=25,
        bow_effect_stable_key="spell:bow_proc",
        bow_proc_chance=12,
    )

    data = build_items_data(items=[item], stats_by_item={}, classes_by_item={})

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["weaponProcChance"] == 33
    assert item_data["wandProcChance"] == 25
    assert item_data["bowProcChance"] == 12


def test_item_index_does_not_include_page_or_name_fallbacks() -> None:
    first = make_item(stable_key="item:first", item_name="Shared A", display_name="Shared A")
    second = make_item(stable_key="item:second", item_name="Shared B", display_name="Shared B")

    data = build_items_data(
        items=[second, first],
        stats_by_item={},
        classes_by_item={},
    )

    assert data["index"] == {"byKey": {"item:first": "Weapons", "item:second": "Weapons"}}


def test_generates_items_modules_from_repository_data() -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={item.stable_key: ["Knight"]})

    modules = generate_items_modules(repo)

    assert modules["Items.lua"].startswith("return {\n")
    assert '["item:sword_of_flames"] = "Weapons"' in modules["Items.lua"]
    assert '["item:sword_of_flames"]' in modules["Items/Weapons.lua"]
    assert '["classes"] = {\n      "Knight",\n    },' in modules["Items/Weapons.lua"]


def test_writes_items_modules_to_data_module_paths(tmp_path: Path) -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={})

    output_paths = write_items_modules(repo, tmp_path)

    assert output_paths == [
        tmp_path / "Erenshor" / "Data" / "Items.lua",
        tmp_path / "Erenshor" / "Data" / "Items" / "Weapons.lua",
    ]
    assert output_paths[0].read_text(encoding="utf-8").startswith("return {\n")
    assert output_paths[1].read_text(encoding="utf-8").startswith("return {\n")
    assert '"classes"' not in output_paths[0].read_text(encoding="utf-8")
    assert "item:sword_of_flames" in output_paths[1].read_text(encoding="utf-8")


def test_splits_item_records_across_semantic_type_shards() -> None:
    weapon = make_item(stable_key="item:weapon", item_name="Weapon", display_name="Weapon", wiki_page_name="Weapon")
    armor = make_item(
        stable_key="item:armor",
        item_name="Armor",
        display_name="Armor",
        wiki_page_name="Armor",
        required_slot="Chest",
        this_weapon_type=None,
    )

    data = build_items_data(
        items=[weapon, armor],
        stats_by_item={},
        classes_by_item={},
    )

    assert data["index"]["byKey"] == {"item:armor": "Armor", "item:weapon": "Weapons"}
    assert set(data["shards"]) == {"Armor", "Weapons"}
    assert list(data["shards"]["Armor"]) == ["item:armor"]
    assert list(data["shards"]["Weapons"]) == ["item:weapon"]
