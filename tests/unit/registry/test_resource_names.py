"""Tests for resource name utilities."""

import pytest

from erenshor.registry.resource_names import (
    build_stable_key,
    extract_resource_name,
    normalize_resource_name,
    parse_stable_key,
    validate_resource_name,
    validate_stable_key,
)
from erenshor.registry.schema import EntityType


class TestNormalizeResourceName:
    """Test normalize_resource_name function."""

    def test_normalize_basic(self):
        """Test basic normalization."""
        assert normalize_resource_name("IronSword") == "ironsword"
        assert normalize_resource_name("Iron Sword") == "iron sword"
        assert normalize_resource_name("iron_sword") == "iron_sword"

    def test_normalize_whitespace(self):
        """Test whitespace handling."""
        assert normalize_resource_name("  Iron Sword  ") == "iron sword"
        assert normalize_resource_name("Iron  Sword") == "iron sword"
        assert normalize_resource_name("Sword  of   Flames") == "sword of flames"

    def test_normalize_special_characters(self):
        """Test special character preservation."""
        assert normalize_resource_name("main_quest_01") == "main_quest_01"
        assert normalize_resource_name("Quest-123") == "quest-123"
        assert normalize_resource_name("Item (1)") == "item (1)"


class TestValidateResourceName:
    """Test validate_resource_name function."""

    def test_valid_resource_names(self):
        """Test valid resource names."""
        assert validate_resource_name("iron_sword") is True
        assert validate_resource_name("Iron Sword") is True
        assert validate_resource_name("main_quest_01") is True
        assert validate_resource_name("a") is True

    def test_invalid_empty_name(self):
        """Test empty resource names are invalid."""
        assert validate_resource_name("") is False
        assert validate_resource_name("   ") is False
        assert validate_resource_name("\t\n") is False

    def test_invalid_with_colon(self):
        """Test resource names with colons are invalid."""
        assert validate_resource_name("item:sword") is False
        assert validate_resource_name("valid:name") is False

    def test_invalid_too_long(self):
        """Test resource names longer than 255 characters are invalid."""
        assert validate_resource_name("a" * 255) is True
        assert validate_resource_name("a" * 256) is False
        assert validate_resource_name("a" * 300) is False


class TestBuildStableKey:
    """Test build_stable_key function."""

    def test_build_stable_key_basic(self):
        """Test building stable keys."""
        assert build_stable_key(EntityType.ITEM, "iron_sword") == "item:iron_sword"
        assert build_stable_key(EntityType.SPELL, "fireball") == "spell:fireball"
        assert build_stable_key(EntityType.CHARACTER, "goblin") == "character:goblin"
        assert build_stable_key(EntityType.QUEST, "main_quest") == "quest:main_quest"
        assert build_stable_key(EntityType.FACTION, "merchant_guild") == "faction:merchant_guild"

    def test_build_stable_key_normalization(self):
        """Test that build_stable_key normalizes resource names."""
        assert build_stable_key(EntityType.ITEM, "Iron Sword") == "item:iron sword"
        assert build_stable_key(EntityType.SPELL, "  Fireball  ") == "spell:fireball"
        assert build_stable_key(EntityType.CHARACTER, "Goblin  Warrior") == "character:goblin warrior"

    def test_build_stable_key_all_entity_types(self):
        """Test build_stable_key with all EntityType values."""
        entity_types = [
            EntityType.ITEM,
            EntityType.SPELL,
            EntityType.SKILL,
            EntityType.CHARACTER,
            EntityType.QUEST,
            EntityType.FACTION,
            EntityType.LOCATION,
            EntityType.ACHIEVEMENT,
            EntityType.CRAFTING_RECIPE,
            EntityType.LOOT_TABLE,
            EntityType.DIALOG,
            EntityType.OTHER,
        ]

        for entity_type in entity_types:
            key = build_stable_key(entity_type, "test_name")
            assert key == f"{entity_type.value}:test_name"

    def test_build_stable_key_empty_name_raises(self):
        """Test that empty resource name raises ValueError."""
        with pytest.raises(ValueError, match="Resource name cannot be empty"):
            build_stable_key(EntityType.ITEM, "")

        with pytest.raises(ValueError, match="Resource name cannot be empty"):
            build_stable_key(EntityType.ITEM, "   ")

    def test_build_stable_key_invalid_name_raises(self):
        """Test that invalid resource name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid resource name"):
            build_stable_key(EntityType.ITEM, "a" * 256)


class TestParseStableKey:
    """Test parse_stable_key function."""

    def test_parse_stable_key_basic(self):
        """Test parsing valid stable keys."""
        entity_type, resource_name = parse_stable_key("item:iron_sword")
        assert entity_type == EntityType.ITEM
        assert resource_name == "iron_sword"

        entity_type, resource_name = parse_stable_key("spell:fireball")
        assert entity_type == EntityType.SPELL
        assert resource_name == "fireball"

        entity_type, resource_name = parse_stable_key("character:goblin_warrior")
        assert entity_type == EntityType.CHARACTER
        assert resource_name == "goblin_warrior"

    def test_parse_stable_key_all_entity_types(self):
        """Test parsing with all EntityType values."""
        entity_types = [
            EntityType.ITEM,
            EntityType.SPELL,
            EntityType.SKILL,
            EntityType.CHARACTER,
            EntityType.QUEST,
            EntityType.FACTION,
            EntityType.LOCATION,
            EntityType.ACHIEVEMENT,
            EntityType.CRAFTING_RECIPE,
            EntityType.LOOT_TABLE,
            EntityType.DIALOG,
            EntityType.OTHER,
        ]

        for expected_type in entity_types:
            key = f"{expected_type.value}:test_name"
            entity_type, resource_name = parse_stable_key(key)
            assert entity_type == expected_type
            assert resource_name == "test_name"

    def test_parse_stable_key_with_colon_in_name(self):
        """Test parsing key where resource_name contains additional colons."""
        # Split on first colon only
        entity_type, resource_name = parse_stable_key("item:name:with:colons")
        assert entity_type == EntityType.ITEM
        assert resource_name == "name:with:colons"

    def test_parse_stable_key_invalid_format_raises(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid stable key format"):
            parse_stable_key("no_colon_here")

        with pytest.raises(ValueError, match="Invalid stable key format"):
            parse_stable_key("just_text")

    def test_parse_stable_key_unknown_type_raises(self):
        """Test that unknown entity type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown entity type"):
            parse_stable_key("unknown_type:some_name")

        with pytest.raises(ValueError, match="Unknown entity type"):
            parse_stable_key("invalid:test")


class TestExtractResourceName:
    """Test extract_resource_name function."""

    def test_extract_item_resource_name(self):
        """Test extracting resource name for items (ResourceName field)."""
        entity_data = {"ResourceName": "IronSword", "Name": "Iron Sword"}
        result = extract_resource_name(EntityType.ITEM, entity_data)
        assert result == "ironsword"

    def test_extract_spell_resource_name(self):
        """Test extracting resource name for spells (ResourceName field)."""
        entity_data = {"ResourceName": "Fireball", "Name": "Fireball"}
        result = extract_resource_name(EntityType.SPELL, entity_data)
        assert result == "fireball"

    def test_extract_skill_resource_name(self):
        """Test extracting resource name for skills (ResourceName field)."""
        entity_data = {"ResourceName": "Archery", "Name": "Archery"}
        result = extract_resource_name(EntityType.SKILL, entity_data)
        assert result == "archery"

    def test_extract_character_object_name(self):
        """Test extracting resource name for characters (ObjectName field)."""
        entity_data = {"ObjectName": "Goblin Warrior", "Name": "A Goblin"}
        result = extract_resource_name(EntityType.CHARACTER, entity_data)
        assert result == "goblin warrior"

    def test_extract_quest_dbname(self):
        """Test extracting resource name for quests (DBName field)."""
        entity_data = {"DBName": "MainQuest_01", "Name": "The Main Quest"}
        result = extract_resource_name(EntityType.QUEST, entity_data)
        assert result == "mainquest_01"

    def test_extract_faction_refname(self):
        """Test extracting resource name for factions (REFNAME field)."""
        entity_data = {"REFNAME": "MerchantGuild", "Name": "Merchant Guild"}
        result = extract_resource_name(EntityType.FACTION, entity_data)
        assert result == "merchantguild"

    def test_extract_missing_required_field_raises(self):
        """Test that missing required field raises KeyError."""
        # Item missing ResourceName
        with pytest.raises(KeyError, match="Missing required field 'ResourceName' for entity type 'item'"):
            extract_resource_name(EntityType.ITEM, {"Name": "Iron Sword"})

        # Character missing ObjectName
        with pytest.raises(KeyError, match="Missing required field 'ObjectName' for entity type 'character'"):
            extract_resource_name(EntityType.CHARACTER, {"Name": "Goblin"})

        # Quest missing DBName
        with pytest.raises(KeyError, match="Missing required field 'DBName' for entity type 'quest'"):
            extract_resource_name(EntityType.QUEST, {"Name": "Main Quest"})

        # Faction missing REFNAME
        with pytest.raises(KeyError, match="Missing required field 'REFNAME' for entity type 'faction'"):
            extract_resource_name(EntityType.FACTION, {"Name": "Merchant Guild"})

    def test_extract_flexible_types_with_resource_name(self):
        """Test extracting resource name for flexible types (LOCATION, etc.) with ResourceName."""
        entity_data = {"ResourceName": "Elderwood", "Name": "Elderwood Forest"}
        result = extract_resource_name(EntityType.LOCATION, entity_data)
        assert result == "elderwood"

    def test_extract_flexible_types_with_name_fallback(self):
        """Test extracting resource name for flexible types falling back to Name."""
        entity_data = {"Name": "Elderwood Forest"}
        result = extract_resource_name(EntityType.LOCATION, entity_data)
        assert result == "elderwood forest"

    def test_extract_flexible_types_empty_fallback(self):
        """Test extracting resource name for flexible types with no fields returns empty string."""
        entity_data = {}
        result = extract_resource_name(EntityType.LOCATION, entity_data)
        assert result == ""


class TestValidateStableKey:
    """Test validate_stable_key function."""

    def test_valid_stable_keys(self):
        """Test valid stable keys."""
        assert validate_stable_key("item:iron_sword") is True
        assert validate_stable_key("character:goblin_warrior") is True
        assert validate_stable_key("quest:main_quest_01") is True
        assert validate_stable_key("faction:merchant_guild") is True

    def test_invalid_no_colon(self):
        """Test that keys without colon are invalid."""
        assert validate_stable_key("invalid_key") is False
        assert validate_stable_key("justtext") is False

    def test_invalid_multiple_colons(self):
        """Test that keys with multiple colons are invalid."""
        assert validate_stable_key("item:valid:name") is False
        assert validate_stable_key("a:b:c:d") is False

    def test_invalid_entity_type(self):
        """Test that keys with unknown entity type are invalid."""
        assert validate_stable_key("unknown_type:some_name") is False
        assert validate_stable_key("invalid:test") is False

    def test_invalid_empty_resource_name(self):
        """Test that keys with empty resource name are invalid."""
        assert validate_stable_key("item:") is False
        assert validate_stable_key("spell:   ") is False

    def test_valid_all_entity_types(self):
        """Test validation with all EntityType values."""
        entity_types = [
            EntityType.ITEM,
            EntityType.SPELL,
            EntityType.SKILL,
            EntityType.CHARACTER,
            EntityType.QUEST,
            EntityType.FACTION,
            EntityType.LOCATION,
            EntityType.ACHIEVEMENT,
            EntityType.CRAFTING_RECIPE,
            EntityType.LOOT_TABLE,
            EntityType.DIALOG,
            EntityType.OTHER,
        ]

        for entity_type in entity_types:
            key = f"{entity_type.value}:test_name"
            assert validate_stable_key(key) is True
