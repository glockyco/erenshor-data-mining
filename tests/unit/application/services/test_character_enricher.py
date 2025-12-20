"""Tests for character enricher service."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.enrichers.character_enricher import CharacterEnricher, EnrichedCharacterData
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo


@pytest.fixture
def mock_faction_repo():
    """Create mock faction repository."""
    repo = MagicMock()
    repo.get_faction_display_names.return_value = {
        "GOOD": "The Followers of Good",
        "EVIL": "The Followers of Evil",
        "CITIZENS": "The Citizens of Erenshor",
    }
    return repo


@pytest.fixture
def mock_spawn_repo():
    """Create mock spawn point repository."""
    repo = MagicMock()
    repo.get_spawn_info_for_character.return_value = [
        CharacterSpawnInfo(
            zone_stable_key="zone:Port Azure",
            base_respawn=300.0,
            x=100.0,
            y=50.0,
            z=200.0,
            spawn_chance=100.0,
            is_rare=False,
            is_unique=False,
        )
    ]
    return repo


@pytest.fixture
def mock_loot_repo():
    """Create mock loot table repository."""
    repo = MagicMock()
    repo.get_loot_for_character.return_value = [
        LootDropInfo(
            item_name="Iron Sword",
            resource_name="IronSword",
            drop_probability=50.0,
            is_guaranteed=False,
            is_actual=True,
            is_common=True,
            is_uncommon=False,
            is_rare=False,
            is_legendary=False,
            is_unique=False,
            is_visible=True,
            item_unique=False,
        )
    ]
    return repo


@pytest.fixture
def mock_spell_repo():
    """Create mock spell repository."""
    repo = MagicMock()
    repo.get_spells_used_by_character.return_value = []
    return repo


@pytest.fixture
def enricher(mock_faction_repo, mock_spawn_repo, mock_loot_repo, mock_spell_repo):
    """Create character enricher with mocked repositories."""
    return CharacterEnricher(
        spawn_repo=mock_spawn_repo,
        loot_repo=mock_loot_repo,
        spell_repo=mock_spell_repo,
    )


class TestCharacterEnrichment:
    """Test character data enrichment."""

    def test_enrich_returns_enriched_data(self, enricher):
        """Test enricher returns EnrichedCharacterData."""
        character = Character(
            stable_key="char:TestGuard",
            object_name="TestGuard",
            npc_name="Test Guard",
        )

        result = enricher.enrich(character)

        assert isinstance(result, EnrichedCharacterData)
        assert result.character == character

    def test_enrich_fetches_spawn_info(self, enricher, mock_spawn_repo):
        """Test enricher fetches spawn info with correct parameters."""
        character = Character(
            stable_key="char:TestGuard",
            object_name="TestGuard",
            npc_name="Test Guard",
            is_prefab=0,
        )

        result = enricher.enrich(character)

        mock_spawn_repo.get_spawn_info_for_character.assert_called_once_with(
            character_stable_key="char:TestGuard",
            is_prefab=False,
        )
        assert len(result.spawn_infos) == 1
        assert result.spawn_infos[0].zone_stable_key == "zone:Port Azure"

    def test_enrich_fetches_spawn_info_for_prefab(self, enricher, mock_spawn_repo):
        """Test enricher correctly handles prefab characters."""
        character = Character(
            stable_key="char:PrefabEnemy",
            object_name="PrefabEnemy",
            npc_name="Prefab Enemy",
            is_prefab=1,
        )

        enricher.enrich(character)

        mock_spawn_repo.get_spawn_info_for_character.assert_called_once_with(
            character_stable_key="char:PrefabEnemy",
            is_prefab=True,
        )

    def test_enrich_fetches_loot_drops(self, enricher, mock_loot_repo):
        """Test enricher fetches loot drops for characters with guid."""
        character = Character(
            stable_key="char:Enemy",
            object_name="Enemy",
            npc_name="Test Enemy",
        )

        result = enricher.enrich(character)

        mock_loot_repo.get_loot_for_character.assert_called_once_with("char:Enemy")
        assert len(result.loot_drops) == 1
        assert result.loot_drops[0].item_name == "Iron Sword"

    def test_enrich_handles_character_without_stable_key(self, enricher):
        """Test enricher handles character with minimal data."""
        # Create a mock loot repo that returns empty
        from unittest.mock import MagicMock

        mock_loot_repo = MagicMock()
        mock_loot_repo.get_loot_for_character.return_value = []

        mock_spawn_repo = MagicMock()
        mock_spawn_repo.get_spawn_info_for_character.return_value = []

        mock_spell_repo = MagicMock()
        mock_spell_repo.get_spells_used_by_character.return_value = []

        enricher = CharacterEnricher(
            spawn_repo=mock_spawn_repo,
            loot_repo=mock_loot_repo,
            spell_repo=mock_spell_repo,
        )

        character = Character(
            stable_key="char:NoKeyCharacter",
            object_name="NoKeyCharacter",
            npc_name="No Key Character",
        )

        result = enricher.enrich(character)

        # Should call loot repo with stable key
        mock_loot_repo.get_loot_for_character.assert_called_once_with("char:NoKeyCharacter")
        assert result.loot_drops == []

    def test_enriched_data_structure(self, enricher):
        """Test EnrichedCharacterData contains expected fields."""
        character = Character(
            stable_key="char:TestChar",
            object_name="TestChar",
            npc_name="Test Character",
            my_world_faction_stable_key="faction:CITIZENS",
        )

        result = enricher.enrich(character)

        # Verify all expected fields exist
        assert hasattr(result, "character")
        assert hasattr(result, "spawn_infos")
        assert hasattr(result, "loot_drops")

        # Verify types
        assert isinstance(result.character, Character)
        assert isinstance(result.spawn_infos, list)
        assert isinstance(result.loot_drops, list)


class TestEnrichedCharacterData:
    """Test EnrichedCharacterData dataclass."""

    def test_enriched_data_initialization(self):
        """Test EnrichedCharacterData can be initialized."""
        character = Character(
            stable_key="char:Test",
            object_name="Test",
            npc_name="Test",
        )
        spawn_infos = [
            CharacterSpawnInfo(
                zone_stable_key="zone:Test Zone",
                base_respawn=60.0,
                x=1.0,
                y=2.0,
                z=3.0,
                spawn_chance=100.0,
                is_rare=False,
                is_unique=False,
            )
        ]
        loot_drops = [
            LootDropInfo(
                item_name="Test Item",
                resource_name="TestItem",
                drop_probability=100.0,
                is_guaranteed=True,
                is_actual=True,
                is_common=False,
                is_uncommon=False,
                is_rare=False,
                is_legendary=True,
                is_unique=False,
                is_visible=True,
                item_unique=False,
            )
        ]

        enriched = EnrichedCharacterData(
            character=character,
            spawn_infos=spawn_infos,
            loot_drops=loot_drops,
            spells=[],
        )

        assert enriched.character == character
        assert enriched.spawn_infos == spawn_infos
        assert enriched.loot_drops == loot_drops

    def test_enriched_data_stores_raw_data_not_formatted(self):
        """Test EnrichedCharacterData stores raw data, not formatted strings."""
        character = Character(stable_key="char:Test", object_name="Test", npc_name="Test")

        enriched = EnrichedCharacterData(
            character=character,
            spawn_infos=[],
            loot_drops=[],
            spells=[],
        )

        # Should be raw data structures, not formatted strings
        assert isinstance(enriched.spawn_infos, list)
        assert isinstance(enriched.loot_drops, list)

        # Should NOT have formatted string fields
        assert not hasattr(enriched, "zones")
        assert not hasattr(enriched, "coordinates")
        assert not hasattr(enriched, "respawn")
        assert not hasattr(enriched, "drop_rates")
