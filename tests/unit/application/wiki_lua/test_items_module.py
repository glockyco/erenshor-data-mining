from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item

from erenshor.application.wiki_lua.items import build_items_data, generate_items_modules, write_items_modules
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.loot import ItemDropInfo
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, SourceInfo, UsedInInfo
from erenshor.domain.value_objects.wiki_link import ItemLink, QuestLink, StandardLink


def test_builds_item_index_and_sharded_records_with_tooltip_source_fields() -> None:
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
                    "description": "Long prose should stay out of Lua data modules.",
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


def test_builds_item_cast_time_from_exported_spell_cast_time() -> None:
    item = make_item(spell_cast_time=1.5, weapon_dly=2.5)
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Normal",
                "weapon_dmg": 18,
            }
        )
    ]

    data = build_items_data(items=[item], stats_by_item={item.stable_key: stats}, classes_by_item={})

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["castTime"] == 1.5


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


def test_builds_tooltip_source_fields_and_recipe_links() -> None:
    item = make_item(
        lore="Forged in a reliable test furnace.",
        is_wand=1,
        wand_range=35,
        book_title="The Ember Manual",
        template=1,
    )
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Normal",
                "str": 4,
            }
        )
    ]
    recipe = CraftingRecipe(
        materials=[
            (
                ItemLink(
                    page_title="Chunk of Copper Ore",
                    display_name="Chunk of Copper Ore",
                    image_name="Chunk of Copper Ore",
                ),
                2,
            )
        ],
        results=[
            (
                ItemLink(
                    page_title="Ember Longsword",
                    display_name="Ember Longsword",
                    image_name="Ember Longsword",
                ),
                1,
            )
        ],
    )

    data = build_items_data(
        items=[item],
        stats_by_item={item.stable_key: stats},
        classes_by_item={},
        recipes_by_item={item.stable_key: recipe},
    )

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["description"] == "Forged in a reliable test furnace."
    assert item_data["bookTitle"] == "The Ember Manual"
    assert item_data["wandRange"] == 35
    assert item_data["ingredients"] == [
        {
            "quantity": 2,
            "link": {
                "kind": "item",
                "page": "Chunk of Copper Ore",
                "text": "Chunk of Copper Ore",
                "image": "Chunk of Copper Ore",
            },
        }
    ]
    assert item_data["rewards"] == [
        {
            "quantity": 1,
            "link": {"kind": "item", "page": "Ember Longsword", "text": "Ember Longsword", "image": "Ember Longsword"},
        }
    ]


def test_builds_item_provenance_fields_from_source_info() -> None:
    item = make_item()
    vendor = StandardLink(page_title="B Vendor", display_name="B Vendor")
    duplicate_vendor = StandardLink(page_title="B Vendor", display_name="B Vendor")
    hidden_vendor = StandardLink(page_title=None, display_name="Hidden Vendor")
    high_drop = StandardLink(page_title="A Croc", display_name="A Croc")
    low_drop = StandardLink(page_title="Z Spider", display_name="Z Spider")
    quest_reward = QuestLink(page_title="Reward Quest", display_name="Reward Quest")
    quest_requirement = QuestLink(page_title="Required Quest", display_name="Required Quest")
    component_for = ItemLink(page_title="Copper Armor Mold", display_name="Copper Armor Mold")
    guaranteed_drop = ItemDropInfo(
        dropped_item_stable_key="item:a_fossil_reward", drop_probability=100.0, is_guaranteed=True
    )

    data = build_items_data(
        items=[item],
        stats_by_item={},
        classes_by_item={},
        sources_by_item={
            item.stable_key: SourceInfo(
                vendors=[vendor, duplicate_vendor, hidden_vendor],
                drops=[(low_drop, 12.5), (high_drop, 50.0)],
                quest_rewards=[quest_reward],
                quest_requirements=[quest_requirement],
                component_for=[component_for],
                item_drops=[guaranteed_drop],
            )
        },
    )

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["vendorSource"] == [{"kind": "page", "page": "B Vendor", "text": "B Vendor"}]
    assert item_data["source"] == [
        {"link": {"kind": "page", "page": "A Croc", "text": "A Croc"}, "probability": 50.0},
        {"link": {"kind": "page", "page": "Z Spider", "text": "Z Spider"}, "probability": 12.5},
    ]
    assert item_data["questSource"] == [{"kind": "quest", "page": "Reward Quest", "text": "Reward Quest"}]
    assert item_data["relatedQuest"] == [{"kind": "quest", "page": "Required Quest", "text": "Required Quest"}]
    assert item_data["componentFor"] == [{"kind": "item", "page": "Copper Armor Mold", "text": "Copper Armor Mold"}]
    assert item_data["containerDrops"] == [{"item": "item:a_fossil_reward", "probability": 100.0, "guaranteed": True}]


def test_formats_obtained_from_with_stable_keys_and_nil_omission() -> None:
    item = make_item()
    data = build_items_data(
        items=[item],
        stats_by_item={},
        classes_by_item={},
        sources_by_item={
            item.stable_key: SourceInfo(
                obtained_from=[
                    ObtainedFromInfo(
                        source_type="starting",
                        source_key="class:Arcanist",
                    ),
                    ObtainedFromInfo(
                        source_type="drop",
                        source_key="character:treasurechest 0-10 1",
                        probability=84.4,
                        is_guaranteed=True,
                    ),
                    ObtainedFromInfo(
                        source_type="fishing",
                        source_key="water:brake:287.10:7.50:247.80",
                        probability=19.0,
                        condition="night",
                    ),
                    ObtainedFromInfo(
                        source_type="fishing",
                        source_key="water:brake:287.10:7.50:247.80",
                        probability=5.9375,
                        condition="day",
                    ),
                    ObtainedFromInfo(
                        source_type="item_use",
                        source_key="item:gen - bag of offering stones",
                    ),
                ]
            )
        },
    )

    shard = data["index"]["byKey"][item.stable_key]
    assert data["shards"][shard][item.stable_key]["obtainedFrom"] == [
        {
            "type": "drop",
            "sourceKey": "character:treasurechest 0-10 1",
            "probability": 84.4,
            "guaranteed": True,
        },
        {
            "type": "fishing",
            "sourceKey": "water:brake:287.10:7.50:247.80",
            "probability": 5.9375,
            "condition": "day",
        },
        {
            "type": "fishing",
            "sourceKey": "water:brake:287.10:7.50:247.80",
            "probability": 19.0,
            "condition": "night",
        },
        {
            "type": "item_use",
            "sourceKey": "item:gen - bag of offering stones",
        },
        {"type": "starting", "sourceKey": "class:Arcanist"},
    ]


def test_formats_used_in_with_all_use_types_and_nil_omission() -> None:
    item = make_item()
    data = build_items_data(
        items=[item],
        stats_by_item={},
        classes_by_item={},
        sources_by_item={
            item.stable_key: SourceInfo(
                used_in=[
                    UsedInInfo(
                        use_type="quest_requirement",
                        target_key="quest:an ore for the forge",
                        quantity=1,
                    ),
                    UsedInInfo(
                        use_type="upgrade_material",
                        target_key="item:template - an otherwordly mold",
                    ),
                    UsedInInfo(
                        use_type="craft_material",
                        target_key="item:template - copper armor mold",
                        quantity=2,
                        slot=1,
                    ),
                    UsedInInfo(
                        use_type="blessing_removal_material",
                        target_key="item:template - inert diamond",
                    ),
                ]
            )
        },
    )

    shard = data["index"]["byKey"][item.stable_key]
    assert data["shards"][shard][item.stable_key]["usedIn"] == [
        {
            "type": "blessing_removal_material",
            "targetKey": "item:template - inert diamond",
        },
        {
            "type": "craft_material",
            "targetKey": "item:template - copper armor mold",
            "quantity": 2,
            "slot": 1,
        },
        {
            "type": "quest_requirement",
            "targetKey": "quest:an ore for the forge",
            "quantity": 1,
        },
        {
            "type": "upgrade_material",
            "targetKey": "item:template - an otherwordly mold",
        },
    ]


def test_generates_items_modules_with_provenance_data() -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={})

    modules = generate_items_modules(
        repo,
        sources_by_item={
            item.stable_key: SourceInfo(
                vendors=[StandardLink(page_title="Ember Vendor", display_name="Ember Vendor")],
            )
        },
    )

    assert '["vendorSource"] = {' in modules["Items/Weapons.lua"]
    assert '["kind"] = "page"' in modules["Items/Weapons.lua"]
    assert '["page"] = "Ember Vendor"' in modules["Items/Weapons.lua"]


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


def test_item_lua_record_includes_economy_flags_with_nondefault_values() -> None:
    item = make_item(
        must_be_equipped_to_click=1,
        player_cannot_sell=1,
        rare_item=1,
    )
    data = build_items_data(
        items=[item],
        stats_by_item={},
        classes_by_item={},
    )
    record = data["shards"]["Weapons"]["item:sword_of_flames"]
    assert record["mustBeEquippedToClick"] is True
    assert record["playerCannotSell"] is True
    assert record["rareItem"] is True
