"""Unit tests for RegistryResolver.

Tests registry resolver functionality including:
- Auto-initialization when registry.db is missing
- Auto-rebuild when mapping.json is newer
- Resource name normalization in link methods
- Page title, display name, and image name resolution
"""

import json
import sqlite3
from pathlib import Path

import pytest

from erenshor.registry.resolver import RegistryResolver


@pytest.fixture
def game_database(tmp_path: Path) -> Path:
    """Create a test game database with empty tables."""
    db_path = tmp_path / "game.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables that RegistryResolver expects
    cursor.execute("CREATE TABLE Items (StableKey TEXT PRIMARY KEY, ItemName TEXT)")
    cursor.execute("CREATE TABLE Spells (StableKey TEXT PRIMARY KEY, SpellName TEXT)")
    cursor.execute("CREATE TABLE Skills (StableKey TEXT PRIMARY KEY, SkillName TEXT)")
    cursor.execute("CREATE TABLE Characters (StableKey TEXT PRIMARY KEY, NPCName TEXT)")
    cursor.execute("CREATE TABLE Zones (StableKey TEXT PRIMARY KEY, ZoneName TEXT)")
    cursor.execute("CREATE TABLE Factions (StableKey TEXT PRIMARY KEY, FactionDesc TEXT)")
    cursor.execute("CREATE TABLE Quests (StableKey TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE QuestVariants (QuestStableKey TEXT, QuestName TEXT)")

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def temp_mapping_json(tmp_path: Path) -> Path:
    """Create a temporary mapping.json file."""
    mapping_data = {
        "rules": {
            "item:test sword": {
                "wiki_page_name": "Test Sword",
                "display_name": "Test Sword",
                "image_name": "Test Sword",
                "mapping_type": "direct",
                "reason": None,
            },
            "item:gen - scribbles of a mad priest 4": {
                "wiki_page_name": "Scribbles of a Mad Priest",
                "display_name": "Scribbles of a Mad Priest",
                "image_name": "Scribbles of a Mad Priest",
                "mapping_type": "custom",
                "reason": None,
            },
            "faction:brax": {
                "wiki_page_name": "The Torchbearers of Brax",
                "display_name": "The Torchbearers of Brax",
                "image_name": None,
                "mapping_type": "custom",
                "reason": "Database has lowercase 'the', should be capital 'The'",
            },
            "zone:azure": {
                "wiki_page_name": "Port Azure",
                "display_name": "Port Azure",
                "image_name": None,
                "mapping_type": "direct",
                "reason": None,
            },
            "character:excluded_npc": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test NPC",
            },
            "item:excluded_item": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test item",
            },
            "spell:fireball": {
                "wiki_page_name": "Fireball",
                "display_name": "Fireball",
                "image_name": None,
                "mapping_type": "direct",
                "reason": None,
            },
            "skill:sword mastery": {
                "wiki_page_name": "Sword Mastery",
                "display_name": "Sword Mastery",
                "image_name": None,
                "mapping_type": "direct",
                "reason": None,
            },
            "faction:excluded_faction": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test faction",
            },
            "zone:excluded_zone": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test zone",
            },
            "spell:test_with_image": {
                "wiki_page_name": "Test Page Title",
                "display_name": "Test Spell",
                "image_name": "CustomImage",
                "mapping_type": "custom",
                "reason": "Test image override",
            },
            "spell:test_with_display": {
                "wiki_page_name": "Test Page Title",
                "display_name": "Custom Display",
                "image_name": None,
                "mapping_type": "custom",
                "reason": "Test display override",
            },
            "spell:excluded_spell": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test spell",
            },
            "skill:excluded_skill": {
                "wiki_page_name": None,
                "display_name": None,
                "image_name": None,
                "mapping_type": "exclude",
                "reason": "Internal test skill",
            },
        }
    }

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(mapping_data, indent=2))
    return mapping_path


@pytest.fixture
def resolver(tmp_path: Path, game_database: Path, temp_mapping_json: Path) -> RegistryResolver:
    """Create a RegistryResolver with test data."""
    registry_path = tmp_path / "registry.db"
    return RegistryResolver(registry_path, game_database, temp_mapping_json)


class TestAutoInitialization:
    """Tests for automatic registry initialization."""

    def test_creates_registry_when_missing(self, tmp_path: Path, game_database: Path, temp_mapping_json: Path) -> None:
        """Test registry is created when database doesn't exist."""
        registry_path = tmp_path / "registry.db"
        assert not registry_path.exists()

        _resolver = RegistryResolver(registry_path, game_database, temp_mapping_json)

        assert registry_path.exists()
        assert registry_path.stat().st_size > 0

    def test_rebuilds_when_empty(self, tmp_path: Path, game_database: Path, temp_mapping_json: Path) -> None:
        """Test registry is rebuilt when database is empty."""
        registry_path = tmp_path / "registry.db"
        registry_path.touch()  # Create empty file
        assert registry_path.stat().st_size == 0

        RegistryResolver(registry_path, game_database, temp_mapping_json)

        assert registry_path.stat().st_size > 0

    def test_rebuilds_when_mapping_newer(self, tmp_path: Path, game_database: Path, temp_mapping_json: Path) -> None:
        """Test registry is rebuilt when mapping.json is newer than registry.db."""
        registry_path = tmp_path / "registry.db"

        # Create initial registry
        RegistryResolver(registry_path, game_database, temp_mapping_json)
        initial_mtime = registry_path.stat().st_mtime

        # Simulate mapping.json being updated
        import time

        time.sleep(0.1)  # Ensure timestamp difference
        temp_mapping_json.touch()

        # Initialize again - should rebuild
        RegistryResolver(registry_path, game_database, temp_mapping_json)
        new_mtime = registry_path.stat().st_mtime

        assert new_mtime > initial_mtime

    def test_no_rebuild_when_up_to_date(self, tmp_path: Path, game_database: Path, temp_mapping_json: Path) -> None:
        """Test registry is NOT rebuilt when already up-to-date."""
        registry_path = tmp_path / "registry.db"

        # Create initial registry
        RegistryResolver(registry_path, game_database, temp_mapping_json)
        initial_mtime = registry_path.stat().st_mtime

        # Initialize again - should NOT rebuild
        import time

        time.sleep(0.1)
        RegistryResolver(registry_path, game_database, temp_mapping_json)
        new_mtime = registry_path.stat().st_mtime

        assert new_mtime == initial_mtime

    def test_raises_when_mapping_missing(self, tmp_path: Path, game_database: Path) -> None:
        """Test raises FileNotFoundError when mapping.json doesn't exist."""
        registry_path = tmp_path / "registry.db"
        missing_mapping = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError, match=r"mapping\.json not found"):
            RegistryResolver(registry_path, game_database, missing_mapping)


class TestResourceNameNormalization:
    """Tests for resource name normalization in link methods."""

    def test_item_link_normalizes_uppercase(self, resolver: RegistryResolver) -> None:
        """Test item_link normalizes uppercase resource names."""
        # "GEN - Scribbles of a mad priest 4" should normalize to lowercase
        result = resolver.item_link("GEN - Scribbles of a mad priest 4", "Scribbles of a mad priest")

        assert result == "{{ItemLink|Scribbles of a Mad Priest}}"

    def test_faction_link_normalizes_uppercase(self, resolver: RegistryResolver) -> None:
        """Test faction_link normalizes uppercase resource names."""
        # "Brax" should normalize to "brax" for lookup
        result = resolver.faction_link("Brax", "the Torchbearers of Brax")

        assert result == "[[The Torchbearers of Brax]]"

    def test_zone_link_normalizes_uppercase(self, resolver: RegistryResolver) -> None:
        """Test zone_link normalizes uppercase resource names."""
        # "Azure" should normalize to "azure" for lookup
        result = resolver.zone_link("Azure", "Port Azure")

        assert result == "[[Port Azure]]"

    def test_item_link_with_mixed_case(self, resolver: RegistryResolver) -> None:
        """Test item_link handles mixed case resource names."""
        result = resolver.item_link("Test Sword", "Test Sword")

        assert result == "{{ItemLink|Test Sword}}"

    def test_faction_link_with_mixed_case(self, resolver: RegistryResolver) -> None:
        """Test faction_link handles mixed case resource names."""
        result = resolver.faction_link("BRAX", "the Torchbearers of Brax")

        assert result == "[[The Torchbearers of Brax]]"


class TestPageTitleResolution:
    """Tests for page title resolution."""

    def test_resolve_with_override(self, resolver: RegistryResolver) -> None:
        """Test resolves page title using mapping.json override."""
        result = resolver.resolve_page_title("faction:brax", "the Torchbearers of Brax")

        assert result == "The Torchbearers of Brax"

    def test_resolve_with_fallback(self, resolver: RegistryResolver) -> None:
        """Test falls back to entity name when no override exists."""
        result = resolver.resolve_page_title("item:unknown", "Unknown Item")

        assert result == "Unknown Item"

    def test_resolve_excluded_returns_none(self, resolver: RegistryResolver) -> None:
        """Test returns None for excluded entities."""
        result = resolver.resolve_page_title("character:excluded_npc", "Excluded NPC")

        assert result is None


class TestDisplayNameResolution:
    """Tests for display name resolution."""

    def test_resolve_with_override(self, resolver: RegistryResolver) -> None:
        """Test resolves display name using mapping.json override."""
        result = resolver.resolve_display_name("item:gen - scribbles of a mad priest 4", "Scribbles of a mad priest")

        assert result == "Scribbles of a Mad Priest"

    def test_resolve_with_fallback(self, resolver: RegistryResolver) -> None:
        """Test falls back to entity name when no override exists."""
        result = resolver.resolve_display_name("item:unknown", "Unknown Item")

        assert result == "Unknown Item"

    def test_resolve_excluded_still_returns_name(self, resolver: RegistryResolver) -> None:
        """Test returns display name even for excluded entities."""
        result = resolver.resolve_display_name("character:excluded_npc", "Excluded NPC")

        assert result == "Excluded NPC"


class TestImageNameResolution:
    """Tests for image name resolution."""

    def test_resolve_with_override(self, resolver: RegistryResolver) -> None:
        """Test resolves image name using mapping.json override."""
        result = resolver.resolve_image_name("item:gen - scribbles of a mad priest 4", "Scribbles of a mad priest")

        assert result == "Scribbles of a Mad Priest"

    def test_resolve_with_fallback(self, resolver: RegistryResolver) -> None:
        """Test falls back to entity name when no override exists."""
        result = resolver.resolve_image_name("item:unknown", "Unknown Item")

        assert result == "Unknown Item"

    def test_resolve_excluded_returns_none(self, resolver: RegistryResolver) -> None:
        """Test returns None for excluded entities."""
        result = resolver.resolve_image_name("character:excluded_npc", "Excluded NPC")

        assert result is None


class TestExclusionChecks:
    """Tests for exclusion checking."""

    def test_is_excluded_true(self, resolver: RegistryResolver) -> None:
        """Test is_excluded returns True for excluded entities."""
        assert resolver.is_excluded("character:excluded_npc") is True

    def test_is_excluded_false(self, resolver: RegistryResolver) -> None:
        """Test is_excluded returns False for non-excluded entities."""
        assert resolver.is_excluded("item:test sword") is False

    def test_is_excluded_false_for_unknown(self, resolver: RegistryResolver) -> None:
        """Test is_excluded returns False for unknown entities."""
        assert resolver.is_excluded("item:unknown") is False


class TestLinkGeneration:
    """Tests for link template generation."""

    def test_item_link_simple(self, resolver: RegistryResolver) -> None:
        """Test generates simple ItemLink template."""
        result = resolver.item_link("test sword", "Test Sword")

        assert result == "{{ItemLink|Test Sword}}"

    def test_item_link_with_overrides(self, resolver: RegistryResolver) -> None:
        """Test generates ItemLink with display name and image overrides."""
        result = resolver.item_link("gen - scribbles of a mad priest 4", "Scribbles of a mad priest")

        assert result == "{{ItemLink|Scribbles of a Mad Priest}}"

    def test_item_link_excluded(self, resolver: RegistryResolver) -> None:
        """Test returns plain text for excluded items."""
        result = resolver.item_link("excluded_item", "Excluded Item")

        assert result == "Excluded Item"
        assert "{{ItemLink" not in result

    def test_faction_link_simple(self, resolver: RegistryResolver) -> None:
        """Test generates simple faction link."""
        result = resolver.faction_link("azure", "Port Azure Citizens")

        assert result == "[[Port Azure Citizens]]"

    def test_faction_link_with_override(self, resolver: RegistryResolver) -> None:
        """Test generates faction link with override."""
        result = resolver.faction_link("brax", "the Torchbearers of Brax")

        assert result == "[[The Torchbearers of Brax]]"

    def test_faction_link_excluded(self, resolver: RegistryResolver) -> None:
        """Test returns plain text for excluded factions."""
        result = resolver.faction_link("excluded_faction", "Excluded Faction")

        assert result == "Excluded Faction"
        assert "[[" not in result

    def test_zone_link_simple(self, resolver: RegistryResolver) -> None:
        """Test generates simple zone link."""
        result = resolver.zone_link("azure", "Port Azure")

        assert result == "[[Port Azure]]"

    def test_zone_link_excluded(self, resolver: RegistryResolver) -> None:
        """Test returns plain text for excluded zones."""
        result = resolver.zone_link("excluded_zone", "Excluded Zone")

        assert result == "Excluded Zone"
        assert "[[" not in result


class TestAbilityLink:
    """Test ability_link method for spells and skills."""

    def test_ability_link_spell_simple(self, resolver: RegistryResolver) -> None:
        """Test simple spell link without overrides."""
        result = resolver.ability_link("spell", "GEN - Stun", "Stun")

        assert result == "{{AbilityLink|Stun}}"

    def test_ability_link_skill_simple(self, resolver: RegistryResolver) -> None:
        """Test simple skill link without overrides."""
        result = resolver.ability_link("skill", "Bash", "Bash")

        assert result == "{{AbilityLink|Bash}}"

    def test_ability_link_with_image_override(self, resolver: RegistryResolver) -> None:
        """Test ability link with image name override."""
        result = resolver.ability_link("spell", "test_with_image", "Test Spell")

        assert "{{AbilityLink|Test Page Title" in result
        assert "image=CustomImage.png" in result

    def test_ability_link_with_display_override(self, resolver: RegistryResolver) -> None:
        """Test ability link with display name override."""
        result = resolver.ability_link("spell", "test_with_display", "Test Spell")

        assert "{{AbilityLink|Test Page Title" in result
        assert "text=Custom Display" in result

    def test_ability_link_spell_excluded(self, resolver: RegistryResolver) -> None:
        """Test returns plain text for excluded spells."""
        result = resolver.ability_link("spell", "excluded_spell", "Excluded Spell")

        assert result == "Excluded Spell"
        assert "{{" not in result

    def test_ability_link_skill_excluded(self, resolver: RegistryResolver) -> None:
        """Test returns plain text for excluded skills."""
        result = resolver.ability_link("skill", "excluded_skill", "Excluded Skill")

        assert result == "Excluded Skill"
        assert "{{" not in result

    def test_ability_link_invalid_entity_type_raises_error(self, resolver: RegistryResolver) -> None:
        """Test raises ValueError for invalid entity type."""
        with pytest.raises(ValueError, match="entity_type must be 'spell' or 'skill'"):
            resolver.ability_link("invalid", "TEST", "Test")

    def test_ability_link_normalizes_case(self, resolver: RegistryResolver) -> None:
        """Test ability_link normalizes uppercase resource names."""
        result = resolver.ability_link("spell", "GEN - STUN", "Stun")

        # Should normalize the stable key
        assert "{{AbilityLink|" in result
