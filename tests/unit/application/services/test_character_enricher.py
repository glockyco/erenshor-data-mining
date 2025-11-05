"""Tests for character enricher service."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.services.character_enricher import CharacterEnricher, EnrichedCharacterData
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
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
            scene="Azure",
            zone_display="Port Azure",
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
def enricher(mock_faction_repo, mock_spawn_repo, mock_loot_repo):
    """Create character enricher with mocked repositories."""
    return CharacterEnricher(
        faction_repo=mock_faction_repo,
        spawn_repo=mock_spawn_repo,
        loot_repo=mock_loot_repo,
    )


class TestCharacterEnrichment:
    """Test character data enrichment."""

    def test_enrich_returns_enriched_data(self, enricher):
        """Test enricher returns EnrichedCharacterData."""
        character = Character(
            id=1,
            resource_name="TestGuard",
            npc_name="Test Guard",
            guid="char-guid-1",
        )

        result = enricher.enrich(character)

        assert isinstance(result, EnrichedCharacterData)
        assert result.character == character

    def test_enrich_fetches_spawn_info(self, enricher, mock_spawn_repo):
        """Test enricher fetches spawn info with correct parameters."""
        character = Character(
            id=1,
            resource_name="TestGuard",
            npc_name="Test Guard",
            guid="char-guid-1",
            is_prefab=0,
        )

        result = enricher.enrich(character)

        mock_spawn_repo.get_spawn_info_for_character.assert_called_once_with(
            character_guid="char-guid-1",
            character_id=1,
            is_prefab=False,
        )
        assert len(result.spawn_infos) == 1
        assert result.spawn_infos[0].zone_display == "Port Azure"

    def test_enrich_fetches_spawn_info_for_prefab(self, enricher, mock_spawn_repo):
        """Test enricher correctly handles prefab characters."""
        character = Character(
            id=1,
            resource_name="PrefabEnemy",
            npc_name="Prefab Enemy",
            guid="prefab-guid",
            is_prefab=1,
        )

        enricher.enrich(character)

        mock_spawn_repo.get_spawn_info_for_character.assert_called_once_with(
            character_guid="prefab-guid",
            character_id=1,
            is_prefab=True,
        )

    def test_enrich_fetches_loot_drops(self, enricher, mock_loot_repo):
        """Test enricher fetches loot drops for characters with guid."""
        character = Character(
            id=1,
            resource_name="Enemy",
            npc_name="Test Enemy",
            guid="enemy-guid",
        )

        result = enricher.enrich(character)

        mock_loot_repo.get_loot_for_character.assert_called_once_with("enemy-guid")
        assert len(result.loot_drops) == 1
        assert result.loot_drops[0].item_name == "Iron Sword"

    def test_enrich_skips_loot_for_character_without_guid(self, enricher, mock_loot_repo):
        """Test enricher skips loot fetch when character has no guid."""
        character = Character(
            id=1,
            resource_name="NoGuidCharacter",
            npc_name="No GUID Character",
            guid=None,
        )

        result = enricher.enrich(character)

        mock_loot_repo.get_loot_for_character.assert_not_called()
        assert result.loot_drops == []

    def test_enrich_fetches_faction_display_names(self, enricher, mock_faction_repo):
        """Test enricher fetches display names for character factions."""
        character = Character(
            id=1,
            resource_name="Guard",
            npc_name="City Guard",
            guid="guard-guid",
            my_world_faction="CITIZENS",
        )

        result = enricher.enrich(character)

        # Should request faction names for character's faction + GOOD/EVIL
        mock_faction_repo.get_faction_display_names.assert_called_once()
        called_refnames = set(mock_faction_repo.get_faction_display_names.call_args[0][0])
        assert "CITIZENS" in called_refnames
        assert "GOOD" in called_refnames
        assert "EVIL" in called_refnames

        assert "CITIZENS" in result.faction_display_names
        assert result.faction_display_names["CITIZENS"] == "The Citizens of Erenshor"

    def test_enrich_includes_faction_modifier_factions(self, enricher, mock_faction_repo):
        """Test enricher includes factions from faction modifiers."""
        character = Character(
            id=1,
            resource_name="QuestGiver",
            npc_name="Quest Giver",
            guid="quest-guid",
            my_world_faction="CITIZENS",
            faction_modifiers=[
                FactionModifier(faction_refname="GOOD", modifier_value=10),
                FactionModifier(faction_refname="EVIL", modifier_value=-5),
            ],
        )

        enricher.enrich(character)

        # Should include character faction + modifier factions + GOOD/EVIL defaults
        called_refnames = set(mock_faction_repo.get_faction_display_names.call_args[0][0])
        assert "CITIZENS" in called_refnames
        assert "GOOD" in called_refnames
        assert "EVIL" in called_refnames
        # All should be present (modifiers are also in the defaults)
        assert len(called_refnames) == 3

    def test_enrich_always_includes_good_evil_factions(self, enricher, mock_faction_repo):
        """Test enricher always requests GOOD and EVIL faction names."""
        character = Character(
            id=1,
            resource_name="NeutralNPC",
            npc_name="Neutral NPC",
            guid="neutral-guid",
            my_world_faction=None,
            faction_modifiers=None,
        )

        enricher.enrich(character)

        # Even with no explicit factions, should still request GOOD/EVIL
        called_refnames = set(mock_faction_repo.get_faction_display_names.call_args[0][0])
        assert "GOOD" in called_refnames
        assert "EVIL" in called_refnames

    def test_enriched_data_structure(self, enricher):
        """Test EnrichedCharacterData contains expected fields."""
        character = Character(
            id=1,
            resource_name="TestChar",
            npc_name="Test Character",
            guid="test-guid",
            my_world_faction="CITIZENS",
        )

        result = enricher.enrich(character)

        # Verify all expected fields exist
        assert hasattr(result, "character")
        assert hasattr(result, "spawn_infos")
        assert hasattr(result, "loot_drops")
        assert hasattr(result, "faction_display_names")

        # Verify types
        assert isinstance(result.character, Character)
        assert isinstance(result.spawn_infos, list)
        assert isinstance(result.loot_drops, list)
        assert isinstance(result.faction_display_names, dict)


class TestEnrichedCharacterData:
    """Test EnrichedCharacterData dataclass."""

    def test_enriched_data_initialization(self):
        """Test EnrichedCharacterData can be initialized."""
        character = Character(
            id=1,
            resource_name="Test",
            npc_name="Test",
            guid="test",
        )
        spawn_infos = [
            CharacterSpawnInfo(
                scene="TestScene",
                zone_display="Test Zone",
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
        faction_names = {"GOOD": "Good Faction"}

        enriched = EnrichedCharacterData(
            character=character,
            spawn_infos=spawn_infos,
            loot_drops=loot_drops,
            faction_display_names=faction_names,
        )

        assert enriched.character == character
        assert enriched.spawn_infos == spawn_infos
        assert enriched.loot_drops == loot_drops
        assert enriched.faction_display_names == faction_names

    def test_enriched_data_stores_raw_data_not_formatted(self):
        """Test EnrichedCharacterData stores raw data, not formatted strings."""
        character = Character(id=1, resource_name="Test", npc_name="Test", guid="test")

        enriched = EnrichedCharacterData(
            character=character,
            spawn_infos=[],
            loot_drops=[],
            faction_display_names={},
        )

        # Should be raw data structures, not formatted strings
        assert isinstance(enriched.spawn_infos, list)
        assert isinstance(enriched.loot_drops, list)
        assert isinstance(enriched.faction_display_names, dict)

        # Should NOT have formatted string fields
        assert not hasattr(enriched, "zones")
        assert not hasattr(enriched, "coordinates")
        assert not hasattr(enriched, "respawn")
        assert not hasattr(enriched, "drop_rates")
