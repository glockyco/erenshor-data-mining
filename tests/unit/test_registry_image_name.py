"""Unit tests for WikiRegistry image_name functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from erenshor.domain.entities.page import EntityRef
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.registry.core import WikiRegistry


@pytest.fixture
def temp_registry() -> WikiRegistry:
    """Create a temporary registry for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_dir = Path(tmpdir) / "registry"
        registry_dir.mkdir(parents=True)
        registry = WikiRegistry(registry_dir=registry_dir)
        yield registry


def test_get_image_name_with_override(temp_registry: WikiRegistry) -> None:
    """Image name override takes precedence over all fallbacks."""
    entity = EntityRef(
        entity_type=EntityType.SPELL,
        db_id="123",
        db_name="Test Spell",
        resource_name="SPELL - Test",
    )

    temp_registry.register_entity(entity, "Test Spell Page")
    temp_registry.set_display_name_override(entity.uid, "Custom Display Name")
    temp_registry.set_image_name_override(entity.uid, "Custom_Image_Name")

    result = temp_registry.get_image_name(entity)
    assert result == "Custom_Image_Name"


def test_get_image_name_fallback_to_display_name(temp_registry: WikiRegistry) -> None:
    """Falls back to display_name when no image override."""
    entity = EntityRef(
        entity_type=EntityType.ITEM,
        db_id="456",
        db_name="Test Item",
        resource_name="ITEM_TEST",
    )

    temp_registry.register_entity(entity, "Test Item Page")
    temp_registry.set_display_name_override(entity.uid, "Custom Display Name")

    result = temp_registry.get_image_name(entity)
    assert result == "Custom Display Name"


def test_get_image_name_fallback_to_page_title(temp_registry: WikiRegistry) -> None:
    """Falls back to page title when no display_name or image override."""
    entity = EntityRef(
        entity_type=EntityType.CHARACTER,
        db_id="789",
        db_name="Test Character",
        resource_name="CHAR_TEST",
    )

    temp_registry.register_entity(entity, "Test Character Page")

    result = temp_registry.get_image_name(entity)
    assert result == "Test Character Page"


def test_get_image_name_fallback_to_db_name_when_not_mapped(
    temp_registry: WikiRegistry,
) -> None:
    """Falls back to db_name when entity is unmapped."""
    entity = EntityRef(
        entity_type=EntityType.SPELL,
        db_id="999",
        db_name="Unmapped Spell",
        resource_name="UNMAPPED",
    )

    result = temp_registry.get_image_name(entity)
    assert result == "Unmapped Spell"


def test_set_image_name_override(temp_registry: WikiRegistry) -> None:
    """Setting image name override works correctly."""
    entity = EntityRef(
        entity_type=EntityType.SKILL,
        db_id="111",
        db_name="Test Skill",
        resource_name="SKILL_TEST",
    )

    temp_registry.set_image_name_override(entity.uid, "My_Custom_Image")

    assert entity.uid in temp_registry.image_name_overrides
    assert temp_registry.image_name_overrides[entity.uid] == "My_Custom_Image"

    result = temp_registry.get_image_name(entity)
    assert result == "My_Custom_Image"


def test_image_name_persistence(temp_registry: WikiRegistry) -> None:
    """Image name overrides persist in registry.json."""
    entity = EntityRef(
        entity_type=EntityType.ITEM,
        db_id="222",
        db_name="Test Persistent Item",
        resource_name="PERSISTENT",
    )

    temp_registry.set_image_name_override(entity.uid, "Persistent_Image")
    temp_registry.save()

    new_registry = WikiRegistry(registry_dir=temp_registry.registry_dir)
    new_registry.load()

    assert entity.uid in new_registry.image_name_overrides
    assert new_registry.image_name_overrides[entity.uid] == "Persistent_Image"
    assert new_registry.get_image_name(entity) == "Persistent_Image"


def test_fallback_chain_priority_order(temp_registry: WikiRegistry) -> None:
    """Fallback chain: image_name > display_name > page_title > db_name."""
    entity = EntityRef(
        entity_type=EntityType.SPELL,
        db_id="333",
        db_name="Original DB Name",
        resource_name="PRIORITY_TEST",
    )

    assert temp_registry.get_image_name(entity) == "Original DB Name"

    temp_registry.register_entity(entity, "Wiki Page Title")
    assert temp_registry.get_image_name(entity) == "Wiki Page Title"

    temp_registry.set_display_name_override(entity.uid, "Display Override")
    assert temp_registry.get_image_name(entity) == "Display Override"

    temp_registry.set_image_name_override(entity.uid, "Image Override")
    assert temp_registry.get_image_name(entity) == "Image Override"


def test_image_name_with_manual_mapping(temp_registry: WikiRegistry) -> None:
    """Image name works with manual mappings."""
    entity = EntityRef(
        entity_type=EntityType.SPELL,
        db_id="444",
        db_name="Spell Name",
        resource_name="MANUAL_TEST",
    )

    temp_registry.create_page("Manual Page Title")
    temp_registry.set_manual_mapping(entity.stable_key, "Manual Page Title")

    assert temp_registry.get_image_name(entity) == "Manual Page Title"

    temp_registry.set_display_name_override(entity.uid, "Manual Display")
    assert temp_registry.get_image_name(entity) == "Manual Display"

    temp_registry.set_image_name_override(entity.uid, "Manual Image")
    assert temp_registry.get_image_name(entity) == "Manual Image"


def test_image_name_never_returns_none(temp_registry: WikiRegistry) -> None:
    """get_image_name always returns a non-empty string."""
    entity = EntityRef(
        entity_type=EntityType.ITEM,
        db_id="555",
        db_name="Safety Test Item",
        resource_name="SAFETY",
    )

    result = temp_registry.get_image_name(entity)
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_image_name_with_special_characters(temp_registry: WikiRegistry) -> None:
    """Image names with special characters returned raw, not URL-encoded."""
    test_cases = [
        ("Aura: Blessing of Stone", "Aura: Blessing of Stone"),
        ("Predator's Grace", "Predator's Grace"),
        ("Explorer's Cap", "Explorer's Cap"),
        ("Spell Scroll: Infernis", "Spell Scroll: Infernis"),
        ("Stone Giant's Blood", "Stone Giant's Blood"),
    ]

    for page_title, expected_image in test_cases:
        entity = EntityRef(
            entity_type=EntityType.SPELL,
            db_id=f"test_{page_title}",
            db_name=page_title,
            resource_name=f"TEST_{page_title}",
        )

        temp_registry.register_entity(entity, page_title)

        result = temp_registry.get_image_name(entity)
        assert result == expected_image
        assert "{{PAGENAMEE}}" not in result
        assert "%3A" not in result
        assert "%27" not in result


def test_image_name_never_returns_magic_constants(temp_registry: WikiRegistry) -> None:
    """get_image_name never returns MediaWiki magic constants."""
    entity = EntityRef(
        entity_type=EntityType.ITEM,
        db_id="666",
        db_name="Test Item",
        resource_name="NO_MAGIC",
    )

    result = temp_registry.get_image_name(entity)
    assert "{{PAGENAMEE}}" not in result
    assert "{{PAGENAME}}" not in result

    temp_registry.register_entity(entity, "Test Page")
    result = temp_registry.get_image_name(entity)
    assert "{{PAGENAMEE}}" not in result
    assert "{{PAGENAME}}" not in result

    temp_registry.set_display_name_override(entity.uid, "Display Name")
    result = temp_registry.get_image_name(entity)
    assert "{{PAGENAMEE}}" not in result
    assert "{{PAGENAME}}" not in result
