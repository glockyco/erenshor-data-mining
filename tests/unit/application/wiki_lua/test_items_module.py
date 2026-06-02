from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item

from erenshor.application.wiki_lua.items import build_items_data, generate_items_module, write_items_module
from erenshor.domain.entities.item_stats import ItemStats


def test_builds_compact_item_data_without_long_prose_fields() -> None:
    item = make_item()
    stats = [
        ItemStats.model_validate(
            {
                "item_stable_key": "item:sword_of_flames",
                "quality": "Normal",
                "weapon_dmg": 7,
                "str": 1,
                "dex": None,
            }
        )
    ]

    data = build_items_data(
        items=[item],
        stats_by_item={item.stable_key: stats},
        classes_by_item={item.stable_key: ["Knight", "Paladin"]},
    )

    assert data == {
        "items": {
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
                "classes": ["Knight", "Paladin"],
                "stats": [
                    {
                        "quality": "Normal",
                        "weaponDamage": 7,
                        "str": 1,
                    }
                ],
            }
        },
        "byPage": {"Sword of Flames": ["item:sword_of_flames"]},
    }


def test_groups_multiple_items_that_share_a_wiki_page() -> None:
    first = make_item(stable_key="item:first", item_name="Shared A", display_name="Shared A")
    second = make_item(stable_key="item:second", item_name="Shared B", display_name="Shared B")

    data = build_items_data(
        items=[second, first],
        stats_by_item={},
        classes_by_item={},
    )

    assert data["byPage"] == {"Sword of Flames": ["item:first", "item:second"]}


def test_generates_items_module_from_repository_data() -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={item.stable_key: ["Knight"]})

    module = generate_items_module(repo)

    assert module.startswith("return {\n")
    assert '["item:sword_of_flames"]' in module
    assert '["classes"] = {\n        "Knight",\n      },' in module


def test_writes_items_module_to_data_module_path(tmp_path: Path) -> None:
    item = make_item()
    repo = FakeItemRepository(items=[item], stats={}, classes={})

    output_path = write_items_module(repo, tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Items.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
