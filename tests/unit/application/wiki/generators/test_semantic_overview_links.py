"""Tests for semantic class links in equipment overview rows."""

from types import SimpleNamespace

import pytest

from erenshor.application.wiki.generators.pages.armor_overview import ArmorOverviewPageGenerator
from erenshor.application.wiki.generators.pages.weapons_overview import WeaponsOverviewPageGenerator
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats


class _ClassDisplay:
    """Minimal class display service for overview row tests."""

    def get_display_name(self, class_name: str) -> str:
        return {"Duelist": "Windblade"}.get(class_name, class_name)


@pytest.mark.parametrize(
    ("generator_type", "equipment_kwargs"),
    [
        (ArmorOverviewPageGenerator, {"required_slot": "Chest"}),
        (
            WeaponsOverviewPageGenerator,
            {"required_slot": "Primary", "this_weapon_type": "OneHandMelee"},
        ),
    ],
)
def test_equipment_overview_rows_use_internal_class_keys_and_mapped_names(
    generator_type: type[ArmorOverviewPageGenerator | WeaponsOverviewPageGenerator],
    equipment_kwargs: dict[str, str],
) -> None:
    """Armor and weapon rows render mapped classes as keyed ClassLinks."""
    generator = generator_type(SimpleNamespace(class_display=_ClassDisplay()))
    item = Item(
        stable_key="item:test-equipment",
        display_name="Test Equipment",
        wiki_page_name="Test Equipment",
        **equipment_kwargs,
    )
    stats = ItemStats(item_stable_key=item.stable_key, quality="Standard")
    rows: list[str] = []

    if isinstance(generator, ArmorOverviewPageGenerator):
        generator._add_armor_row(rows, item, stats, ["Duelist", "Arcanist", "Duelist"])
    else:
        generator._add_weapon_row(rows, item, stats, ["Duelist", "Arcanist", "Duelist"])

    class_cell = next(row for row in rows if row.startswith("|{{ClassLink"))
    assert class_cell == (
        "|{{ClassLink|stablekey=class:arcanist|link=Arcanist|text=Arcanist}}, "
        "{{ClassLink|stablekey=class:duelist|link=Windblade|text=Windblade}}"
    )
    assert "[[Windblade]]" not in "\n".join(rows)
    assert "[[Arcanist]]" not in "\n".join(rows)
