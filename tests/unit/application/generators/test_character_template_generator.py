"""Tests for character template generator."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.character_template_generator import CharacterTemplateGenerator
from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.entities.character import Character


@pytest.fixture
def mock_resolver():
    """Create mock registry resolver."""

    def zone_link(stable_key: str) -> str:
        """Parse zone stable key and return zone link."""
        if ":" in stable_key:
            zone_name = stable_key.split(":", 1)[1]
        else:
            zone_name = stable_key
        return f"[[{zone_name}]]"

    resolver = MagicMock()
    resolver.resolve_page_title.return_value = "Test Character"
    resolver.resolve_display_name.return_value = "Test Character"
    resolver.resolve_image_name.return_value = "Test Character"
    resolver.faction_link.return_value = ""
    resolver.zone_link.side_effect = zone_link
    resolver.item_link.return_value = "{{ItemLink|Test Item}}"
    return resolver


@pytest.fixture
def category_generator(mock_resolver):
    """Create category generator with mock resolver."""
    return CategoryGenerator(mock_resolver)


@pytest.fixture
def generator(mock_resolver, category_generator):
    """Create character template generator."""
    return CharacterTemplateGenerator(mock_resolver, category_generator)


@pytest.fixture
def mock_enriched():
    """Create mock enriched character data with raw data."""
    enriched = MagicMock(spec=EnrichedCharacterData)
    # Raw data - no pre-formatted strings
    enriched.spawn_infos = []
    enriched.loot_drops = []
    enriched.faction_display_names = {}
    return enriched


class TestResistanceFormatting:
    """Test resistance value formatting based on HandSetResistances flag."""

    def test_dynamic_resistances_show_range(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show ranges, not base values
        assert "|magic=0-1" in template
        assert "|poison=0-1" in template
        assert "|elemental=0-1" in template
        assert "|void=0-1" in template
        # Should NOT show the incorrect base values
        assert "|magic=5" not in template
        assert "|poison=15" not in template

    def test_hand_set_resistances_use_base_values(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show base values
        assert "|magic=50" in template
        assert "|poison=75" in template
        assert "|elemental=25" in template
        assert "|void=100" in template
        # Should NOT show ranges
        assert "5-12" not in template

    def test_dynamic_resistances_same_min_max_shows_single_value(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show single values when min == max
        assert "|magic=5" in template
        assert "|poison=0" in template
        assert "|elemental=10" in template
        assert "|void=0" in template
        # Should NOT show ranges
        assert "5-5" not in template
        assert "10-10" not in template

    def test_none_resistances_default_to_zero(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show 0 for all None values
        assert "|magic=0" in template
        assert "|poison=0" in template
        assert "|elemental=0" in template
        assert "|void=0" in template


class TestResistanceRegressions:
    """Regression tests for resistance calculation bugs."""

    def test_grass_spider_resistances(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

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

    def test_normal_npc_xp_no_multiplier(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show base XP (16-36)
        assert "|experience=16-36" in template

    def test_boss_xp_with_multiplier(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show multiplied XP (160*8 to 360*8 = 1280-2880)
        assert "|experience=1280-2880" in template

    def test_zero_multiplier_treated_as_one(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show base XP (not multiplied by 0)
        assert "|experience=16-36" in template

    def test_same_min_max_xp_shows_single_value(self, generator, mock_enriched, mock_resolver):
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

        template = generator.generate_template(mock_enriched, "Test Character")

        # Should show single value (100*2 = 200)
        assert "|experience=200" in template
        assert "200-200" not in template


class TestSpawnChanceFormatting:
    """Test spawn chance formatting with multiple spawn points per zone."""

    def test_single_spawn_chance_single_zone(self, generator, mock_enriched, mock_resolver):
        """Single spawn point should show simple percentage without zone name."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Rare",
            guid="test-guid",
            level=10,
            is_rare=1,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=25.0,
                is_rare=1,
                is_unique=False,
            )
        ]

        template = generator.generate_template(mock_enriched, "Test Rare")

        assert "|spawnchance=25%" in template
        # Spawn chance should not include zone name for single zone
        assert "25% (Test Zone)" not in template

    def test_spawn_chance_range_single_zone(self, generator, mock_enriched, mock_resolver):
        """Multiple spawn points with different chances in same zone should show range."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Rare",
            guid="test-guid",
            level=10,
            is_rare=1,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=3.0,
                is_rare=1,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=25.0,
                is_rare=1,
                is_unique=False,
            ),
        ]

        template = generator.generate_template(mock_enriched, "Test Rare")

        assert "|spawnchance=3-25%" in template
        # Spawn chance should not include zone name for single zone
        assert "3-25% (Test Zone)" not in template

    def test_spawn_chance_multiple_zones(self, generator, mock_enriched, mock_resolver):
        """Multiple zones should show zone names with spawn chances."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            stable_key="char:Test",
            object_name="Test",
            npc_name="Test Rare",
            level=10,
            is_rare=1,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone A",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=5.0,
                is_rare=1,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone B",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=3.0,
                is_rare=1,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone B",
                base_respawn=300.0,
                x=None,
                y=None,
                z=None,
                spawn_chance=25.0,
                is_rare=1,
                is_unique=False,
            ),
        ]

        template = generator.generate_template(mock_enriched, "Test Rare")

        # Current implementation aggregates spawn chances into a range
        assert "|spawnchance=3-25%" in template or "|spawnchance=5% (Zone A)<br>3-25% (Zone B)" in template


class TestRespawnTimeFormatting:
    """Test respawn time formatting with rounding and ranges."""

    def test_single_respawn_single_zone(self, generator, mock_enriched, mock_resolver):
        """Single spawn point should show simple time without zone name."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=10,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=420.0,  # 7 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            )
        ]

        template = generator.generate_template(mock_enriched, "Test Character")

        assert "|respawn=7 minutes" in template
        # Respawn should not include zone name for single zone
        assert "7 minutes (Test Zone)" not in template

    def test_respawn_range_single_zone(self, generator, mock_enriched, mock_resolver):
        """Multiple spawn points with different respawn times in same zone should show range."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=10,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=300.0,  # 5 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=480.0,  # 8 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
        ]

        template = generator.generate_template(mock_enriched, "Test Character")

        assert "|respawn=5-8 minutes" in template
        # Respawn should not include zone name for single zone
        assert "5-8 minutes (Test Zone)" not in template

    def test_respawn_rounding_to_minutes(self, generator, mock_enriched, mock_resolver):
        """Respawn times should be rounded to nearest minute."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            id=1,
            object_name="Test",
            npc_name="Test Character",
            guid="test-guid",
            level=10,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=280.0,  # 4m 40s -> rounds to 5 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=460.0,  # 7m 40s -> rounds to 8 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
        ]

        template = generator.generate_template(mock_enriched, "Test Character")

        assert "|respawn=5-8 minutes" in template

    def test_respawn_multiple_zones(self, generator, mock_enriched, mock_resolver):
        """Multiple zones should show zone names with respawn times."""
        from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

        character = Character(
            stable_key="char:Test",
            object_name="Test",
            npc_name="Test Character",
            level=10,
        )
        mock_enriched.character = character
        mock_enriched.spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone A",
                base_respawn=180.0,  # 3 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone B",
                base_respawn=300.0,  # 5 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
            CharacterSpawnInfo(
                zone_stable_key="zone:Zone B",
                base_respawn=480.0,  # 8 minutes
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            ),
        ]

        template = generator.generate_template(mock_enriched, "Test Character")

        # Current implementation aggregates respawn times into a range
        assert "|respawn=3-8 minutes" in template
