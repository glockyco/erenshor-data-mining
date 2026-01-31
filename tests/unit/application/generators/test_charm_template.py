"""Unit tests for charm template generation."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.generators.sections.categories import CategoryGenerator
from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats


@pytest.fixture
def enrich_item():
    """Helper to wrap items in EnrichedItemData."""

    def _enrich(item: Item, stats: list[ItemStats] | None = None, classes: list[str] | None = None) -> EnrichedItemData:
        return EnrichedItemData(item=item, stats=stats or [], classes=classes or [])

    return _enrich


@pytest.fixture
def mock_resolver():
    """Create mock registry resolver."""
    resolver = MagicMock()
    resolver.resolve_display_name.return_value = "Test Item"
    resolver.resolve_image_name.return_value = "Test Item"
    resolver.ability_link.return_value = "{{AbilityLink|Test Ability}}"
    resolver.item_link.return_value = "{{ItemLink|Test Item}}"
    return resolver


@pytest.fixture
def category_generator(mock_resolver):
    """Create category generator with mock resolver."""
    return CategoryGenerator(mock_resolver)


@pytest.fixture
def generator(mock_resolver, mock_class_display):
    """Create item template generator."""
    return ItemSectionGenerator(mock_resolver, mock_class_display)


class TestCharmTemplate:
    """Tests for charm template generation."""

    def test_charm_with_single_stat_scaling(self, generator, enrich_item):
        """Test charm with single stat scaling."""

        item = Item(
            id="charm-1",
            resource_name="CharmBrilliance",
            stable_key="item:charmbrilliance",
            item_name="Charm of Brilliance",
            required_slot="Charm",
            lore="You find yourself saying 'actually...' more.",
        )

        stat = ItemStats(
            item_stable_key="CharmBrilliance",
            quality="Normal",
            str_scaling=0.0,
            end_scaling=0.0,
            dex_scaling=0.0,
            agi_scaling=0.0,
            int_scaling=4.0,
            wis_scaling=0.0,
            cha_scaling=0.0,
        )

        enriched = enrich_item(item, stats=[stat], classes=["Arcanist", "Druid"])
        result = generator.generate_template(enriched, page_title="Charm of Brilliance")

        assert "{{Item" in result
        assert "{{Item/Charm" in result
        assert "|intscaling=4" in result
        assert "|strscaling=" in result and "|strscaling=0" not in result
        assert "|arcanist=True" in result
        assert "|druid=True" in result
        assert "|duelist=" in result

    def test_charm_with_multiple_stat_scaling(self, generator, enrich_item):
        """Test charm with multiple stat scaling."""

        item = Item(
            id="charm-2",
            resource_name="WarlordCharm",
            stable_key="item:warlordcharm",
            item_name="Warlord's Charm",
            required_slot="Charm",
        )

        stat = ItemStats(
            item_stable_key="WarlordCharm",
            quality="Normal",
            str_scaling=6.0,
            end_scaling=0.0,
            dex_scaling=2.0,
            agi_scaling=0.0,
            int_scaling=0.0,
            wis_scaling=0.0,
            cha_scaling=0.0,
        )

        enriched = enrich_item(item, stats=[stat], classes=["Paladin"])
        result = generator.generate_template(enriched, page_title="Warlord's Charm")

        assert "{{Item/Charm" in result
        assert "|strscaling=6" in result
        assert "|dexscaling=2" in result
        assert "|intscaling=" in result and "|intscaling=0" not in result
        assert "|paladin=True" in result

    def test_charm_without_stats(self, generator, enrich_item):
        """Test charm without stats falls back to Item template only."""

        item = Item(
            id="charm-3",
            resource_name="BasicCharm",
            stable_key="item:basiccharm",
            item_name="Basic Charm",
            required_slot="Charm",
        )

        enriched = enrich_item(item, stats=[], classes=[])
        result = generator.generate_template(enriched, page_title="Basic Charm")

        assert "{{Item" in result
        assert "{{Fancy-charm" not in result

    def test_charm_description_formatting(self, generator, enrich_item):
        """Test charm with multiple classes and stat scaling."""

        item = Item(
            id="charm-4",
            resource_name="AdventureCharm",
            stable_key="item:adventurecharm",
            item_name="Adventure Charm",
            required_slot="Charm",
            lore="Your step has more confidence and your mind is clear",
        )

        stat = ItemStats(
            item_stable_key="AdventureCharm",
            quality="Normal",
            end_scaling=1.0,
            dex_scaling=1.0,
            int_scaling=1.0,
            wis_scaling=1.0,
        )

        enriched = enrich_item(item, stats=[stat], classes=["Arcanist", "Duelist", "Druid", "Paladin", "Stormcaller"])
        result = generator.generate_template(enriched, page_title="Adventure Charm")

        # Note: lore/description is not included in charm templates
        assert "{{Item/Charm" in result
        assert "|endscaling=1" in result
        assert "|dexscaling=1" in result
        assert "|intscaling=1" in result
        assert "|wisscaling=1" in result
        assert all(
            f"|{cls.lower()}=True" in result for cls in ["arcanist", "duelist", "druid", "paladin", "stormcaller"]
        )
