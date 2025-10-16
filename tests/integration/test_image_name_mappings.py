"""Integration tests for image_name in content generation."""

from __future__ import annotations


import pytest
from sqlalchemy.engine import Engine

from erenshor.domain.entities.page import EntityRef
from erenshor.registry.core import WikiRegistry


def test_image_name_in_spell_generation(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """Spell generators use custom image_name from registry."""
    from erenshor.infrastructure.database.repositories import get_spells

    spells = list(get_spells(test_engine, obtainable_only=False))
    if not spells:
        pytest.skip("No spells in test database")

    spell = spells[0]
    entity = EntityRef.from_spell(spell)

    test_registry.register_entity(entity, spell.SpellName)
    test_registry.set_image_name_override(entity.uid, "Custom_Spell_Image")

    image_name = test_registry.get_image_name(entity)
    assert (
        image_name == "Custom_Spell_Image"
    ), f"Expected 'Custom_Spell_Image', got '{image_name}'"

    test_registry.image_name_overrides.pop(entity.uid)
    image_name = test_registry.get_image_name(entity)
    assert (
        image_name == spell.SpellName
    ), f"Should fall back to db_name '{spell.SpellName}', got '{image_name}'"


def test_image_name_in_item_generation(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """Item entities use custom image_name from registry."""
    from erenshor.infrastructure.database.repositories import get_items

    items = list(get_items(test_engine, obtainable_only=False))
    if not items:
        pytest.skip("No items in test database")

    item = items[0]
    entity = EntityRef.from_item(item)

    test_registry.register_entity(entity, item.ItemName)
    test_registry.set_image_name_override(entity.uid, "Custom_Item_Image")

    image_name = test_registry.get_image_name(entity)
    assert image_name == "Custom_Item_Image"


def test_image_name_overrides_display_name(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """Image name override takes precedence over display_name."""
    from erenshor.infrastructure.database.repositories import get_items

    items = list(get_items(test_engine, obtainable_only=False))
    if not items:
        pytest.skip("No items in test database")

    item = items[0]
    entity = EntityRef.from_item(item)

    test_registry.register_entity(entity, item.ItemName)

    test_registry.set_display_name_override(entity.uid, "Display Name Override")
    test_registry.set_image_name_override(entity.uid, "Image Name Override")

    image_name = test_registry.get_image_name(entity)
    assert image_name == "Image Name Override"

    display_name = test_registry.get_display_name(entity)
    assert display_name == "Display Name Override"


def test_image_name_no_fallback_to_page_title(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """No cascading fallback: page title does not affect image_name."""
    from erenshor.infrastructure.database.repositories import get_items

    items = list(get_items(test_engine, obtainable_only=False))
    if not items:
        pytest.skip("No items in test database")

    item = items[0]
    entity = EntityRef.from_item(item)

    custom_page_name = f"{item.ItemName} (Custom)"
    test_registry.register_entity(entity, custom_page_name)

    image_name = test_registry.get_image_name(entity)
    assert image_name == item.ItemName  # Falls back to db_name, not page title


def test_image_name_no_fallback_to_display_name(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """No cascading fallback: display_name does not affect image_name."""
    from erenshor.infrastructure.database.repositories import get_spells

    spells = list(get_spells(test_engine, obtainable_only=False))
    if not spells:
        pytest.skip("No spells in test database")

    spell = spells[0]
    entity = EntityRef.from_spell(spell)

    test_registry.register_entity(entity, spell.SpellName)

    test_registry.set_display_name_override(entity.uid, "Custom Display Name")

    image_name = test_registry.get_image_name(entity)
    assert image_name == spell.SpellName  # Falls back to db_name, not display_name


def test_character_image_name_override(
    test_engine: Engine,
    test_registry: WikiRegistry,
) -> None:
    """Character entities use custom image_name from registry."""
    from erenshor.infrastructure.database.repositories import get_characters

    characters = list(get_characters(test_engine))
    if not characters:
        pytest.skip("No characters in test database")

    char = characters[0]
    entity = EntityRef.from_character(char)

    test_registry.register_entity(entity, char.NPCName)
    test_registry.set_image_name_override(entity.uid, "Custom_Character_Image")

    image_name = test_registry.get_image_name(entity)
    assert image_name == "Custom_Character_Image"
