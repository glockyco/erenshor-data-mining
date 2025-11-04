"""Tests for character template generator."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.generators.character_template_generator import CharacterTemplateGenerator
from erenshor.application.services.character_enricher import EnrichedCharacterData
from erenshor.domain.entities.character import Character


@pytest.fixture
def generator():
    """Create character template generator."""
    return CharacterTemplateGenerator()


@pytest.fixture
def mock_enriched():
    """Create mock enriched character data."""
    enriched = MagicMock(spec=EnrichedCharacterData)
    enriched.display_name = "Test Character"
    enriched.image_name = "Test Character"
    enriched.enemy_type = "Enemy"
    enriched.faction = "[[Test Faction]]"
    enriched.faction_change = ""
    enriched.zones = "[[Test Zone]]"
    enriched.coordinates = ""
    enriched.spawn_chance = ""
    enriched.respawn = "5 minutes"
    enriched.guaranteed_drops = ""
    enriched.drop_rates = ""
    return enriched


class TestResistanceFormatting:
    """Test resistance value formatting based on HandSetResistances flag."""

    def test_dynamic_resistances_show_range(self, generator, mock_enriched):
        """Characters without HandSetResistances should show resistance ranges."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=1,
            hand_set_resistances=0,  # Dynamic resistances
            base_mr=5,  # These should be IGNORED
            base_pr=15,
            base_er=5,
            base_vr=5,
            effective_min_mr=0,  # Use these instead
            effective_max_mr=1,
            effective_min_pr=0,
            effective_max_pr=1,
            effective_min_er=0,
            effective_max_er=1,
            effective_min_vr=0,
            effective_max_vr=1,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show ranges, not base values
        assert "|magic=0-1" in template
        assert "|poison=0-1" in template
        assert "|elemental=0-1" in template
        assert "|void=0-1" in template
        # Should NOT show the incorrect base values
        assert "|magic=5" not in template
        assert "|poison=15" not in template

    def test_hand_set_resistances_use_base_values(self, generator, mock_enriched):
        """Characters with HandSetResistances=1 should use base resistance values."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=10,
            hand_set_resistances=1,  # Use base values
            base_mr=50,
            base_pr=75,
            base_er=25,
            base_vr=100,
            effective_min_mr=5,  # Should be IGNORED
            effective_max_mr=12,
            effective_min_pr=5,
            effective_max_pr=12,
            effective_min_er=5,
            effective_max_er=12,
            effective_min_vr=5,
            effective_max_vr=12,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show base values
        assert "|magic=50" in template
        assert "|poison=75" in template
        assert "|elemental=25" in template
        assert "|void=100" in template
        # Should NOT show ranges
        assert "5-12" not in template

    def test_dynamic_resistances_same_min_max_shows_single_value(self, generator, mock_enriched):
        """When min and max are the same, show single value not range."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=1,
            hand_set_resistances=0,
            effective_min_mr=5,
            effective_max_mr=5,  # Same as min
            effective_min_pr=0,
            effective_max_pr=0,
            effective_min_er=10,
            effective_max_er=10,
            effective_min_vr=0,
            effective_max_vr=0,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show single values when min == max
        assert "|magic=5" in template
        assert "|poison=0" in template
        assert "|elemental=10" in template
        assert "|void=0" in template
        # Should NOT show ranges
        assert "5-5" not in template
        assert "10-10" not in template

    def test_none_resistances_default_to_zero(self, generator, mock_enriched):
        """None resistance values should default to 0."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            hand_set_resistances=0,
            effective_min_mr=None,
            effective_max_mr=None,
            effective_min_pr=None,
            effective_max_pr=None,
            effective_min_er=None,
            effective_max_er=None,
            effective_min_vr=None,
            effective_max_vr=None,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show 0 for all None values
        assert "|magic=0" in template
        assert "|poison=0" in template
        assert "|elemental=0" in template
        assert "|void=0" in template


class TestResistanceRegressions:
    """Regression tests for resistance calculation bugs."""

    def test_grass_spider_resistances(self, generator, mock_enriched):
        """A Grass Spider should show 0-1 resistance range, not base values.

        Regression test: Previously showed incorrect base values (5, 15, 5, 5)
        instead of calculated ranges (0-1 for all resistances).

        Game logic: NPCs without HandSetResistances use dynamic resistance
        calculation: Level * Random.Range(0.5f, 1.2f)
        Export logic: Stores as EffectiveMin/Max = Level * 0.5 / Level * 1.2
        """
        character = Character(
            id=42,
            object_name="AGrassSpider",
            npc_name="A Grass Spider",
            guid="test-guid",
            level=1,
            hand_set_resistances=0,  # Dynamic calculation
            base_mr=5,  # From prefab (ignored for dynamic NPCs)
            base_pr=15,
            base_er=5,
            base_vr=5,
            effective_min_mr=0,  # Level 1 * 0.5 = 0.5 rounds to 0
            effective_max_mr=1,  # Level 1 * 1.2 = 1.2 rounds to 1
            effective_min_pr=0,
            effective_max_pr=1,
            effective_min_er=0,
            effective_max_er=1,
            effective_min_vr=0,
            effective_max_vr=1,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show calculated ranges for level 1 creature
        assert "|magic=0-1" in template
        assert "|poison=0-1" in template
        assert "|elemental=0-1" in template
        assert "|void=0-1" in template
        # Should NOT show the incorrect prefab base values
        assert "|magic=5" not in template
        assert "|poison=15" not in template


class TestExperienceCalculation:
    """Test XP calculation with BossXpMultiplier."""

    def test_normal_npc_xp_no_multiplier(self, generator, mock_enriched):
        """Normal NPCs with no multiplier should show base XP range."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=4,
            base_xp_min=16.0,
            base_xp_max=36.0,
            boss_xp_multiplier=None,  # No multiplier
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show base XP (16-36)
        assert "|experience=16-36" in template

    def test_boss_xp_with_multiplier(self, generator, mock_enriched):
        """Boss NPCs should apply XP multiplier."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Boss",
            guid="test-guid",
            level=40,
            base_xp_min=160.0,
            base_xp_max=360.0,
            boss_xp_multiplier=8.0,  # 8x multiplier
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show multiplied XP (160*8 to 360*8 = 1280-2880)
        assert "|experience=1280-2880" in template

    def test_zero_multiplier_treated_as_one(self, generator, mock_enriched):
        """Zero multiplier should be treated as 1.0."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=4,
            base_xp_min=16.0,
            base_xp_max=36.0,
            boss_xp_multiplier=0.0,  # Zero should become 1.0
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show base XP (not multiplied by 0)
        assert "|experience=16-36" in template

    def test_same_min_max_xp_shows_single_value(self, generator, mock_enriched):
        """When min and max XP are the same, show single value."""
        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=10,
            base_xp_min=100.0,
            base_xp_max=100.0,
            boss_xp_multiplier=2.0,
        )
        mock_enriched.character = character

        template = generator.generate_template(mock_enriched)

        # Should show single value (100*2 = 200)
        assert "|experience=200" in template
        assert "200-200" not in template
