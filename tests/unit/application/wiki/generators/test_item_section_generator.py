"""Tests for item section generation."""

from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats


def test_weapon_page_uses_single_lua_item_tooltip() -> None:
    generator = ItemSectionGenerator()
    item = Item(
        stable_key="item:ember_longsword",
        display_name="Ember Longsword",
        item_name="Ember Longsword",
        required_slot="PrimaryOrSecondary",
        this_weapon_type="OneHandMelee",
        item_value=12500,
    )
    enriched = EnrichedItemData(
        item=item,
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Normal", weapon_dmg=10)],
        classes=[],
    )

    result = generator.generate_template(enriched, "Ember Longsword")

    assert "{{ItemTooltip|stablekey=item:ember_longsword}}" in result
    assert "{{Item/Weapon" not in result
    assert "{{Fancy-weapon" not in result
    assert result.count("{{ItemTooltip") == 1


def test_general_page_uses_single_lua_item_tooltip() -> None:
    generator = ItemSectionGenerator()
    item = Item(
        stable_key="item:magical_bag",
        display_name="Magical Bag",
        item_name="Magical Bag",
        required_slot="General",
        lore="A larger bag.",
        item_value=25,
    )
    enriched = EnrichedItemData(item=item, stats=[], classes=[])

    result = generator.generate_template(enriched, "Magical Bag")

    assert "{{ItemTooltip|stablekey=item:magical_bag}}" in result
    assert "{{Item/General" not in result
    assert result.count("{{ItemTooltip") == 1
