"""Unit tests for CharacterEnricher service.

Tests the character data enrichment service including:
- Enemy type classification (Boss/Rare/Enemy/NPC)
- Faction modifier formatting with display name translation
- Zone list formatting with wiki links
- Coordinate formatting (unique characters only)
- Spawn chance formatting
- Respawn time formatting (human-readable)
- Loot drop formatting (guaranteed + drop rates)
- Reference note generation for loot
"""

from unittest.mock import Mock

import pytest

from erenshor.application.services.character_enricher import CharacterEnricher
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo


@pytest.fixture
def mock_faction_repo():
    """Mock faction repository."""
    repo = Mock()
    repo.get_faction_display_names.return_value = {
        "AzureCitizens": "Citizens of Port Azure",
        "SavannahPriel": "Savannah Priel",
    }
    return repo


@pytest.fixture
def mock_spawn_repo():
    """Mock spawn point repository."""
    repo = Mock()
    repo.get_spawn_info_for_character.return_value = []
    return repo


@pytest.fixture
def mock_loot_repo():
    """Mock loot table repository."""
    repo = Mock()
    repo.get_loot_for_character.return_value = []
    return repo


@pytest.fixture
def mock_registry_resolver():
    """Mock registry resolver."""
    resolver = Mock()
    # Mock display name and image name resolution to return page title by default
    resolver.resolve_display_name.side_effect = lambda key, name: name
    resolver.resolve_image_name.side_effect = lambda key, name: name
    resolver.item_link.side_effect = lambda res, name: f"{{{{ItemLink|{name}}}}}"
    resolver.faction_link.side_effect = lambda ref, name: f"[[{name}]]"
    resolver.zone_link.side_effect = lambda scene, name: f"[[{name}]]"
    return resolver


@pytest.fixture
def enricher(mock_faction_repo, mock_spawn_repo, mock_loot_repo, mock_registry_resolver):
    """CharacterEnricher instance with mocked dependencies."""
    return CharacterEnricher(
        faction_repo=mock_faction_repo,
        spawn_repo=mock_spawn_repo,
        loot_repo=mock_loot_repo,
        registry_resolver=mock_registry_resolver,
    )


def make_spawn_info(
    scene: str,
    zone_display: str,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    spawn_chance: float = 100.0,
    base_respawn: float = 0.0,
) -> CharacterSpawnInfo:
    """Helper to create CharacterSpawnInfo with all required fields."""
    return CharacterSpawnInfo(
        scene=scene,
        zone_display=zone_display,
        x=x,
        y=y,
        z=z,
        spawn_chance=spawn_chance,
        base_respawn=base_respawn,
        is_rare=False,
        is_unique=False,
    )


class TestEnemyTypeClassification:
    """Test enemy type classification logic."""

    def test_classify_unique_as_boss(self, enricher):
        """Unique characters should be classified as Boss."""
        character = Character(
            id=1,
            object_name="EldothMolorai",
            npc_name="Eldoth Molorai",
            is_unique=1,
            is_rare=0,
            is_npc=0,
            is_friendly=0,
        )

        enriched = enricher.enrich(character, "Eldoth Molorai")

        assert enriched.enemy_type == "Boss"

    def test_classify_rare_as_rare(self, enricher):
        """Rare characters should be classified as Rare."""
        character = Character(
            id=2,
            object_name="GrassSpider",
            npc_name="A Grass Spider",
            is_unique=0,
            is_rare=1,  # SQLite boolean (0/1)
            is_npc=0,
            is_friendly=0,
        )

        enriched = enricher.enrich(character, "A Grass Spider")

        assert enriched.enemy_type == "Rare"

    def test_classify_npc_as_npc(self, enricher):
        """NPCs should be classified as NPC."""
        character = Character(
            id=3,
            object_name="MerchantToby",
            npc_name="Merchant Toby",
            is_unique=0,
            is_rare=0,
            is_npc=1,  # SQLite boolean (0/1)
            is_friendly=0,
        )

        enriched = enricher.enrich(character, "Merchant Toby")

        assert enriched.enemy_type == "NPC"

    def test_classify_friendly_as_npc(self, enricher):
        """Friendly characters should be classified as NPC."""
        character = Character(
            id=4,
            object_name="GuardCaptain",
            npc_name="Guard Captain",
            is_unique=0,
            is_rare=0,
            is_npc=0,
            is_friendly=1,  # SQLite boolean (0/1)
        )

        enriched = enricher.enrich(character, "Guard Captain")

        assert enriched.enemy_type == "NPC"

    def test_classify_normal_enemy_as_enemy(self, enricher):
        """Normal enemies should be classified as Enemy."""
        character = Character(
            id=5,
            object_name="Goblin",
            npc_name="Goblin",
            is_unique=0,
            is_rare=0,
            is_npc=0,
            is_friendly=0,
        )

        enriched = enricher.enrich(character, "Goblin")

        assert enriched.enemy_type == "Enemy"


class TestFactionModifierFormatting:
    """Test faction modifier formatting."""

    def test_format_empty_faction_modifiers(self, enricher):
        """Empty faction modifiers should return empty string."""
        character = Character(
            id=1,
            object_name="TestNPC",
            npc_name="Test NPC",
            faction_modifiers=[],
        )

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.faction_change == ""

    def test_format_faction_modifiers_with_display_names(self, enricher, mock_faction_repo):
        """Faction modifiers should use display names from repository."""
        character = Character(
            id=1,
            object_name="TestNPC",
            npc_name="Test NPC",
            faction_modifiers=[
                FactionModifier(faction_refname="AzureCitizens", modifier_value=3),
                FactionModifier(faction_refname="SavannahPriel", modifier_value=-5),
            ],
        )

        enriched = enricher.enrich(character, "Test NPC")

        # Should be sorted by display name
        assert enriched.faction_change == "+3 [[Citizens of Port Azure]]<br>-5 [[Savannah Priel]]"
        mock_faction_repo.get_faction_display_names.assert_called_once_with(["AzureCitizens", "SavannahPriel"])

    def test_format_faction_modifiers_filters_zero_values(self, enricher):
        """Zero-value faction modifiers should be filtered out."""
        character = Character(
            object_name="TestNPC",
            id=1,
            npc_name="Test NPC",
            faction_modifiers=[
                FactionModifier(faction_refname="AzureCitizens", modifier_value=0),
                FactionModifier(faction_refname="SavannahPriel", modifier_value=3),
            ],
        )

        enriched = enricher.enrich(character, "Test NPC")

        # Only non-zero modifier should appear
        assert enriched.faction_change == "+3 [[Savannah Priel]]"


class TestZoneFormatting:
    """Test zone list formatting."""

    def test_format_empty_zones(self, enricher, mock_spawn_repo):
        """No spawn points should return empty zones string."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_spawn_repo.get_spawn_info_for_character.return_value = []

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.zones == ""

    def test_format_multiple_zones(self, enricher, mock_spawn_repo):
        """Multiple zones should be formatted with wiki links and <br> separator."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Hidden",
                zone_display="Hidden Hills",
                x=150.0,
                y=60.0,
                z=250.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Zones should be sorted by display name
        assert enriched.zones == "[[Hidden Hills]]<br>[[Port Azure]]"

    def test_format_zones_deduplicates(self, enricher, mock_spawn_repo):
        """Duplicate zones should be deduplicated."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=110.0,
                y=55.0,
                z=210.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Should only appear once
        assert enriched.zones == "[[Port Azure]]"


class TestCoordinateFormatting:
    """Test coordinate formatting."""

    def test_format_coordinates_single_spawn(self, enricher, mock_spawn_repo):
        """Single spawn point should show coordinates with one decimal place."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_unique=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=123.456,
                y=78.9,
                z=234.567,
                spawn_chance=100.0,
                base_respawn=0.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.coordinates == "123.5 x 78.9 x 234.6"

    def test_format_coordinates_multiple_spawns(self, enricher, mock_spawn_repo):
        """Multiple spawn points should not show coordinates."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Hidden",
                zone_display="Hidden Hills",
                x=150.0,
                y=60.0,
                z=250.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.coordinates == ""

    def test_format_coordinates_missing_data(self, enricher, mock_spawn_repo):
        """Missing coordinate data should return empty string."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_unique=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=None,
                y=None,
                z=None,
                spawn_chance=100.0,
                base_respawn=0.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.coordinates == ""


class TestSpawnChanceFormatting:
    """Test spawn chance formatting."""

    def test_format_spawn_chance_all_100(self, enricher, mock_spawn_repo):
        """All 100% spawn chances should return empty string."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Hidden",
                zone_display="Hidden Hills",
                x=150.0,
                y=60.0,
                z=250.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            ),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.spawn_chance == ""

    def test_format_spawn_chance_varied(self, enricher, mock_spawn_repo):
        """Varied spawn chances should be formatted and deduplicated."""
        character = Character(
            id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1, is_rare=1, is_unique=0
        )
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=50.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Hidden",
                zone_display="Hidden Hills",
                x=150.0,
                y=60.0,
                z=250.0,
                spawn_chance=25.0,
                base_respawn=300.0,
            ),
            make_spawn_info(
                scene="Brake",
                zone_display="Faerie's Brake",
                x=175.0,
                y=65.0,
                z=275.0,
                spawn_chance=50.0,
                base_respawn=300.0,
            ),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Should be sorted descending and deduplicated
        assert enriched.spawn_chance == "50%<br>25%"


class TestRespawnFormatting:
    """Test respawn time formatting."""

    def test_format_respawn_zero(self, enricher, mock_spawn_repo):
        """Zero respawn should return empty string."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_unique=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=0.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == ""

    def test_format_respawn_minutes_only(self, enricher, mock_spawn_repo):
        """Respawn time with only minutes should format correctly."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=300.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == "5 minutes"

    def test_format_respawn_minutes_and_seconds(self, enricher, mock_spawn_repo):
        """Respawn time with minutes and seconds should format correctly."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=400.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == "6 minutes 40 seconds"

    def test_format_respawn_seconds_only(self, enricher, mock_spawn_repo):
        """Respawn time with only seconds should format correctly."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=45.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == "45 seconds"

    def test_format_respawn_singular_minute(self, enricher, mock_spawn_repo):
        """Respawn time of 1 minute should use singular form."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=60.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == "1 minute"

    def test_format_respawn_singular_second(self, enricher, mock_spawn_repo):
        """Respawn time of 1 second should use singular form."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid", is_prefab=1)
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Azure",
                zone_display="Port Azure",
                x=100.0,
                y=50.0,
                z=200.0,
                spawn_chance=100.0,
                base_respawn=61.0,
            )
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.respawn == "1 minute 1 second"


class TestLootDropFormatting:
    """Test loot drop formatting."""

    @staticmethod
    def _make_loot_drop(
        item_id: str,
        item_name: str,
        drop_probability: float,
        is_guaranteed: bool = False,
        is_visible: bool = False,
        item_unique: bool = False,
    ) -> LootDropInfo:
        """Helper to create LootDropInfo with all required fields."""
        return LootDropInfo(
            item_id=item_id,
            item_name=item_name,
            resource_name=item_name.replace(" ", ""),
            drop_probability=drop_probability,
            is_guaranteed=is_guaranteed,
            is_actual=True,
            is_common=True,
            is_uncommon=False,
            is_rare=False,
            is_legendary=False,
            is_unique=False,
            is_visible=is_visible,
            item_unique=item_unique,
        )

    def test_format_loot_drops_empty(self, enricher, mock_loot_repo):
        """No loot drops should return empty strings."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = []

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.guaranteed_drops == ""
        assert enriched.drop_rates == ""

    def test_format_loot_drops_single_item(self, enricher, mock_loot_repo):
        """Single loot drop should format correctly."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Sword", 50.0)
        ]

        enriched = enricher.enrich(character, "Test NPC")

        assert enriched.guaranteed_drops == ""  # Single guaranteed not shown
        assert enriched.drop_rates == "{{ItemLink|Sword}} (50.0%)"

    def test_format_loot_drops_multiple_guaranteed(self, enricher, mock_loot_repo):
        """Multiple guaranteed drops should be shown without percentages."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Sword", 100.0, is_guaranteed=True),
            self._make_loot_drop("102", "Shield", 100.0, is_guaranteed=True),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Should appear in both guaranteed and drop_rates
        assert "{{ItemLink|Shield}}" in enriched.guaranteed_drops
        assert "{{ItemLink|Sword}}" in enriched.guaranteed_drops
        assert "{{ItemLink|Shield}} (100.0%)" in enriched.drop_rates
        assert "{{ItemLink|Sword}} (100.0%)" in enriched.drop_rates

    def test_format_loot_drops_with_references(self, enricher, mock_loot_repo):
        """Loot drops with is_visible or item_unique should include reference notes."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Magic Sword", 75.0, is_visible=True),
            self._make_loot_drop("102", "Unique Ring", 25.0, item_unique=True),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Should contain reference notes
        assert "<ref>If Test NPC has {{ItemLink|Magic Sword}} equipped" in enriched.drop_rates
        assert "<ref>If the player is already holding {{ItemLink|Unique Ring}}" in enriched.drop_rates

    def test_format_loot_drops_sorted_by_probability(self, enricher, mock_loot_repo):
        """Loot drops should be sorted by probability (descending)."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Common Item", 10.0),
            self._make_loot_drop("102", "Rare Item", 90.0),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Higher probability should come first
        lines = enriched.drop_rates.split("<br>")
        assert "Rare Item" in lines[0]
        assert "Common Item" in lines[1]

    def test_format_guaranteed_drops_sorted_alphabetically(self, enricher, mock_loot_repo):
        """Guaranteed drops should be sorted alphabetically by item name."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Zebra Hide", 100.0, is_guaranteed=True),
            self._make_loot_drop("102", "Apple", 100.0, is_guaranteed=True),
            self._make_loot_drop("103", "Mushroom", 100.0, is_guaranteed=True),
        ]

        enriched = enricher.enrich(character, "Test NPC")

        # Should be sorted alphabetically
        lines = enriched.guaranteed_drops.split("<br>")
        assert "Apple" in lines[0]
        assert "Mushroom" in lines[1]
        assert "Zebra Hide" in lines[2]

    def test_item_link_does_not_use_icon_parameter(self, enricher, mock_loot_repo, mock_registry_resolver):
        """item_link should not be called with icon parameter (Unity internal identifier)."""
        character = Character(id=1, object_name="Test NPC", npc_name="Test NPC", guid="test-guid")
        mock_loot_repo.get_loot_for_character.return_value = [
            self._make_loot_drop("101", "Test Item", 50.0)
        ]

        enricher.enrich(character, "Test NPC")

        # Verify item_link was called with exactly 2 args (resource_name, item_name)
        # NOT 3 args (resource_name, item_name, icon_name)
        mock_registry_resolver.item_link.assert_called()
        call_args = mock_registry_resolver.item_link.call_args
        assert len(call_args[0]) == 2  # Two positional args
        assert call_args[0] == ("TestItem", "Test Item")  # (resource_name, item_name)


class TestCoordinateFormattingRegressions:
    """Regression tests for coordinate formatting bugs."""

    def test_coordinates_use_x_separator_with_decimal_precision(self, enricher, mock_spawn_repo):
        """Coordinates should use 'x' separator and show one decimal place.

        Regression test: Previously used comma separator and int() conversion,
        outputting "944, 71, 590" instead of "944.5 x 71.5 x 590.1".
        """
        character = Character(
            id=1, object_name="Stoneman", npc_name="Stoneman Diamondine", guid="test-guid", is_unique=1
        )
        mock_spawn_repo.get_spawn_info_for_character.return_value = [
            make_spawn_info(
                scene="Mines",
                zone_display="Crystal Mines",
                x=944.5,
                y=71.5,
                z=590.1,
                spawn_chance=100.0,
                base_respawn=0.0,
            )
        ]

        enriched = enricher.enrich(character, "Stoneman Diamondine")

        # Should use 'x' separator and show one decimal place
        assert enriched.coordinates == "944.5 x 71.5 x 590.1"
