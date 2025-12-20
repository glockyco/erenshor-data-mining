"""Tests for item enricher service."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.enrichers.item_enricher import EnrichedItemData, ItemEnricher
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats


@pytest.fixture
def mock_item_repo():
    """Create mock item repository."""
    repo = MagicMock()
    repo.get_item_stats.return_value = [
        ItemStats(
            item_stable_key="TestWeapon",
            quality="Normal",
            weapon_dmg=10,
            hp=0,
            ac=0,
            mana=0,
            strength=None,
            endurance=None,
            dexterity=None,
            agility=None,
            intelligence=None,
            wisdom=None,
            charisma=None,
            res=0,
            mr=0,
            er=0,
            pr=0,
            vr=0,
            str_scaling=0.0,
            end_scaling=0.0,
            dex_scaling=0.0,
            agi_scaling=0.0,
            int_scaling=0.0,
            wis_scaling=0.0,
            cha_scaling=0.0,
            resist_scaling=0.0,
            mitigation_scaling=0.0,
        ),
        ItemStats(
            item_stable_key="TestWeapon",
            quality="Blessed",
            weapon_dmg=12,
            hp=0,
            ac=0,
            mana=0,
            strength=None,
            endurance=None,
            dexterity=None,
            agility=None,
            intelligence=None,
            wisdom=None,
            charisma=None,
            res=0,
            mr=0,
            er=0,
            pr=0,
            vr=0,
            str_scaling=0.0,
            end_scaling=0.0,
            dex_scaling=0.0,
            agi_scaling=0.0,
            int_scaling=0.0,
            wis_scaling=0.0,
            cha_scaling=0.0,
            resist_scaling=0.0,
            mitigation_scaling=0.0,
        ),
        ItemStats(
            item_stable_key="TestWeapon",
            quality="Godly",
            weapon_dmg=14,
            hp=0,
            ac=0,
            mana=0,
            strength=None,
            endurance=None,
            dexterity=None,
            agility=None,
            intelligence=None,
            wisdom=None,
            charisma=None,
            res=0,
            mr=0,
            er=0,
            pr=0,
            vr=0,
            str_scaling=0.0,
            end_scaling=0.0,
            dex_scaling=0.0,
            agi_scaling=0.0,
            int_scaling=0.0,
            wis_scaling=0.0,
            cha_scaling=0.0,
            resist_scaling=0.0,
            mitigation_scaling=0.0,
        ),
    ]
    repo.get_item_classes.return_value = ["Paladin", "Duelist"]
    return repo


@pytest.fixture
def enricher(mock_item_repo):
    """Create item enricher with mocked repositories."""
    from unittest.mock import Mock

    mock_spell_repo = Mock()
    mock_skill_repo = Mock()
    mock_skill_repo.get_skill_by_stable_key.return_value = None
    mock_character_repo = Mock()
    mock_character_repo.get_vendors_selling_item.return_value = []
    mock_character_repo.get_characters_dropping_item.return_value = []

    mock_quest_repo = Mock()
    mock_quest_repo.get_quests_rewarding_item.return_value = []
    mock_quest_repo.get_quests_requiring_item.return_value = []

    # Mock item repository source methods
    mock_item_repo.get_items_producing_item.return_value = []
    mock_item_repo.get_items_requiring_item.return_value = []
    mock_item_repo.get_crafting_recipe.return_value = None

    return ItemEnricher(
        item_repo=mock_item_repo,
        spell_repo=mock_spell_repo,
        skill_repo=mock_skill_repo,
        character_repo=mock_character_repo,
        quest_repo=mock_quest_repo,
    )


class TestItemEnrichment:
    """Test item data enrichment."""

    def test_enrich_returns_enriched_data(self, enricher):
        """Test enricher returns EnrichedItemData."""
        item = Item(
            id="1",
            resource_name="TestSword",
            stable_key="item:testsword",
            item_name="Test Sword",
        )

        result = enricher.enrich(item)

        assert isinstance(result, EnrichedItemData)
        assert result.item == item

    def test_enrich_fetches_item_stats(self, enricher, mock_item_repo):
        """Test enricher fetches item stats with correct resource name."""
        item = Item(
            stable_key="item:TestWeapon",
            item_name="Test Weapon",
        )

        result = enricher.enrich(item)

        mock_item_repo.get_item_stats.assert_called_once_with("item:TestWeapon")
        assert len(result.stats) == 3
        assert result.stats[0].quality == "Normal"
        assert result.stats[1].quality == "Blessed"
        assert result.stats[2].quality == "Godly"

    def test_enrich_handles_items_without_stats(self, enricher, mock_item_repo):
        """Test enricher handles items with no stats (consumables, general items)."""
        mock_item_repo.get_item_stats.return_value = []

        item = Item(
            stable_key="item:Potion",
            item_name="Health Potion",
        )

        result = enricher.enrich(item)

        mock_item_repo.get_item_stats.assert_called_once_with("item:Potion")
        assert result.stats == []

    def test_enriched_data_structure(self, enricher):
        """Test EnrichedItemData contains expected fields."""
        item = Item(
            id="1",
            resource_name="TestItem",
            stable_key="item:testitem",
            item_name="Test Item",
        )

        result = enricher.enrich(item)

        # Verify all expected fields exist
        assert hasattr(result, "item")
        assert hasattr(result, "stats")
        assert hasattr(result, "classes")

        # Verify types
        assert isinstance(result.item, Item)
        assert isinstance(result.stats, list)
        assert isinstance(result.classes, list)


class TestEnrichedItemData:
    """Test EnrichedItemData dataclass."""

    def test_enriched_data_initialization(self):
        """Test EnrichedItemData can be initialized."""
        item = Item(
            id="1",
            resource_name="Test",
            stable_key="item:test",
            item_name="Test Item",
        )
        stats = [
            ItemStats(
                item_stable_key="Test",
                quality="Normal",
                weapon_dmg=5,
                hp=0,
                ac=0,
                mana=0,
                strength=None,
                endurance=None,
                dexterity=None,
                agility=None,
                intelligence=None,
                wisdom=None,
                charisma=None,
                res=0,
                mr=0,
                er=0,
                pr=0,
                vr=0,
                str_scaling=0.0,
                end_scaling=0.0,
                dex_scaling=0.0,
                agi_scaling=0.0,
                int_scaling=0.0,
                wis_scaling=0.0,
                cha_scaling=0.0,
                resist_scaling=0.0,
                mitigation_scaling=0.0,
            )
        ]
        classes = ["Paladin", "Duelist"]

        enriched = EnrichedItemData(item=item, stats=stats, classes=classes)

        assert enriched.item == item
        assert enriched.stats == stats
        assert enriched.classes == classes

    def test_enriched_data_stores_raw_data_not_formatted(self):
        """Test EnrichedItemData stores raw data, not formatted strings."""
        item = Item(id="1", resource_name="Test", stable_key="item:test", item_name="Test")

        enriched = EnrichedItemData(item=item, stats=[], classes=[])

        # Should be raw data structures, not formatted strings
        assert isinstance(enriched.stats, list)
        assert isinstance(enriched.classes, list)

        # Should NOT have formatted string fields
        assert not hasattr(enriched, "fancy_weapon")
        assert not hasattr(enriched, "fancy_armor")
        assert not hasattr(enriched, "stats_table")
