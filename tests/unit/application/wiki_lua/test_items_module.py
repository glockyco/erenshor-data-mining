from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from tests.unit.application.wiki_lua.fakes import (
    FakeItemRepository,
    make_item,
)

from erenshor.application.wiki_lua.items import (
    build_items_data,
    generate_items_modules,
    write_items_modules,
)
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.item_provenance import ItemUse
from erenshor.domain.value_objects.wiki_link import ItemLink

if TYPE_CHECKING:
    from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository


def _provenance_repo(uses: tuple[ItemUse, ...] = ()) -> ItemProvenanceRepository:
    return cast("ItemProvenanceRepository", SimpleNamespace(get_uses=lambda _key: list(uses)))


def test_builds_item_index_and_sharded_records_with_tooltip_source_fields() -> None:
    item = make_item()
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": "item:sword_of_flames",
                "quality": "Standard",
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
        class_display_names={"Knight": "Knight", "Paladin": "Paladin"},
    )

    assert data == {
        "index": {"byKey": {"item:sword_of_flames": "Weapons"}},
        "shards": {
            "Weapons": {
                "item:sword_of_flames": {
                    "name": "Sword of Flames",
                    "description": "Long prose should stay out of Lua data modules.",
                    "page": "Sword of Flames",
                    "icon": "Sword of Flames icon.png",
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
                    "classLinks": [
                        {"kind": "class", "stablekey": "class:knight"},
                        {"kind": "class", "stablekey": "class:paladin"},
                    ],
                    "stats": [
                        {
                            "quality": "Standard",
                            "weaponDamage": 7,
                            "ac": 3,
                            "str": 1,
                        }
                    ],
                }
            }
        },
    }


def test_preserves_all_quality_rows_in_gameplay_order() -> None:
    item = make_item()
    qualities = [
        "Standard",
        "Improved +1",
        "Improved +2",
        "Improved +3",
        "Improved +4",
        "Improved +5",
        "Blessed",
        "Ascended",
    ]
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": quality,
                "weapon_dmg": index + 10,
                "hp": index + 20,
                "ac": index + 1,
            }
        )
        for index, quality in reversed(list(enumerate(qualities)))
    ]

    data = build_items_data(items=[item], stats_by_item={item.stable_key: stats}, classes_by_item={})

    record = data["shards"][data["index"]["byKey"][item.stable_key]][item.stable_key]
    assert [row["quality"] for row in record["stats"]] == qualities
    assert [row["weaponDamage"] for row in record["stats"]] == list(range(10, 18))
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
            "quality": "Standard",
            "weapon_dmg": 7,
            "ac": 3,
        }
    )

    data = build_items_data(items=[item], stats_by_item={item.stable_key: [blessed, base]}, classes_by_item={})

    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    assert item_data["damage"] == 7
    assert item_data["armor"] == 3


def test_preserves_improved_plus_five_resists_from_release_data() -> None:
    item = make_item()
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Standard",
                "mr": 0,
                "er": 0,
                "pr": 0,
                "vr": 0,
            }
        ),
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Improved +4",
                "mr": 1,
                "er": 1,
                "pr": 1,
                "vr": 1,
            }
        ),
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Improved +5",
                "mr": 6,
                "er": 7,
                "pr": 8,
                "vr": 9,
            }
        ),
    ]

    data = build_items_data(items=[item], stats_by_item={item.stable_key: stats}, classes_by_item={})

    rows = {
        row["quality"]: row for row in data["shards"][data["index"]["byKey"][item.stable_key]][item.stable_key]["stats"]
    }
    assert {rows["Improved +4"][key] for key in ("mr", "er", "pr", "vr")} == {1}
    assert tuple(rows["Improved +5"][key] for key in ("mr", "er", "pr", "vr")) == (6, 7, 8, 9)

    item = make_item(spell_cast_time=1.5, weapon_dly=2.5)
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": item.stable_key,
                "quality": "Standard",
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
                "quality": "Standard",
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
                "image": "Chunk of Copper Ore icon.png",
            },
        }
    ]
    assert item_data["rewards"] == [
        {
            "quantity": 1,
            "link": {
                "kind": "item",
                "page": "Ember Longsword",
                "text": "Ember Longsword",
                "image": "Ember Longsword icon.png",
            },
        }
    ]


def test_legacy_item_record_does_not_publish_retired_provenance_fields() -> None:
    item = make_item()
    data = build_items_data(items=[item], stats_by_item={}, classes_by_item={})
    shard = data["index"]["byKey"][item.stable_key]
    item_data = data["shards"][shard][item.stable_key]
    for removed in (
        "obtainedFrom",
        "usedIn",
        "vendorSource",
        "source",
        "questSource",
        "relatedQuest",
        "componentFor",
        "containerDrops",
    ):
        assert removed not in item_data


def test_lists_the_zones_where_using_an_item_has_another_outcome() -> None:
    stone, plain = make_item(stable_key="item:time_stone"), make_item(stable_key="item:plain")
    data = build_items_data(
        items=[stone, plain],
        stats_by_item={},
        classes_by_item={},
        zone_restrictions_by_item={
            stone.stable_key: [("zone:shiveringtomb2", "returned unused"), ("zone:stowawayportal", "returned unused")]
        },
    )

    records = {key: data["shards"][shard][key] for key, shard in data["index"]["byKey"].items()}
    assert records[stone.stable_key]["zoneRestrictions"] == [
        {"zoneKey": "zone:shiveringtomb2", "outcome": "returned unused"},
        {"zoneKey": "zone:stowawayportal", "outcome": "returned unused"},
    ]
    assert "zoneRestrictions" not in records[plain.stable_key]


def test_legacy_item_modules_use_canonical_zone_restrictions_without_source_schema_changes() -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={})
    use = ItemUse(
        "use:zone",
        item.stable_key,
        "zone:reliquary",
        "zone_restriction",
        mechanic="consumed",
    )
    modules = generate_items_modules(repo, _provenance_repo((use,)))
    assert '["zoneRestrictions"] = {' in modules["Items/Weapons.lua"]
    assert '"zone:reliquary"' in modules["Items/Weapons.lua"]
    assert '"obtainedFrom"' not in modules["Items/Weapons.lua"]


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

    modules = generate_items_modules(repo, _provenance_repo(), class_display_names={"Knight": "Knight"})

    assert modules["Items.lua"].startswith("return {\n")
    assert '["item:sword_of_flames"] = "Weapons"' in modules["Items.lua"]
    assert '["item:sword_of_flames"]' in modules["Items/Weapons.lua"]
    assert "class:knight" in modules["Items/Weapons.lua"]
    assert '"Knight"' in modules["Items/Weapons.lua"]


def test_writes_items_modules_to_data_module_paths(tmp_path: Path) -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={})

    output_paths = write_items_modules(repo, tmp_path, _provenance_repo())

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
