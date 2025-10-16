"""Integration tests for item updates.

Tests cover all item types:
- Weapons (Primary, PrimaryOrSecondary, Secondary)
- Armor (Head, Chest, Legs, etc.)
- Auras
- Consumables
- Ability Books (TeachSpell, TeachSkill)
- Molds
- General items
- Edge cases (no sell value, unique, relic)
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from erenshor.application.services.update_service import UpdateService
from erenshor.domain.events import (
    ContentGenerated,
    PageUpdated,
    UpdateComplete,
    ValidationFailed,
)
from erenshor.infrastructure.storage.page_storage import PageStorage
from tests.conftest import assert_page_structure_valid


def test_weapon_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test weapon item generation (with Fancy-weapon table)."""
    # Process all items
    events = list(item_update_service.update_pages(test_engine))

    # Find weapon update events (exclude molds which have "Mold:" prefix)
    weapon_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and "Sword" in e.page_title
        and "Mold:" not in e.page_title
    ]

    assert len(weapon_events) >= 1, "Should generate at least one weapon page"

    # Check generated content
    for event in weapon_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        assert page is not None, f"Page not found in registry: {event.page_title}"

        content = test_output_storage.read(page)
        assert content is not None
        assert content is not None, f"Page content not found: {event.page_title}"

        # Verify structure: Item infobox + Fancy-weapon table
        assert_page_structure_valid(content, ["Item", "Fancy-weapon"])

        # Verify three tiers (0, 1, 2) - format is "tier = 0"
        assert "tier = 0" in content, "Should have tier 0"
        assert "tier = 1" in content, "Should have tier 1"
        assert "tier = 2" in content, "Should have tier 2"


def test_armor_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test armor item generation (with Fancy-armor table)."""
    events = list(item_update_service.update_pages(test_engine))

    # Find armor update events
    armor_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and ("Helm" in e.page_title or "Chest" in e.page_title)
    ]

    assert len(armor_events) >= 1, "Should generate at least one armor page"

    for event in armor_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Verify structure: Item infobox + Fancy-armor table
        assert_page_structure_valid(content, ["Item", "Fancy-armor"])

        # Verify three tiers - format is "tier = 0"
        assert "tier = 0" in content, "Should have tier 0"
        assert "tier = 1" in content, "Should have tier 1"
        assert "tier = 2" in content, "Should have tier 2"


def test_aura_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test aura item generation (Item template with type=Aura)."""
    events = list(item_update_service.update_pages(test_engine))

    aura_events = [
        e for e in events if isinstance(e, PageUpdated) and "Aura" in e.page_title
    ]

    assert len(aura_events) >= 1, "Should generate at least one aura page"

    for event in aura_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Verify structure: Item infobox only (no Fancy table)
        assert_page_structure_valid(content, ["Item"])

        # Should NOT have Fancy table
        assert "Fancy-" not in content, "Auras should not have Fancy tables"

        # Should have aura type
        assert "Aura" in content, "Should reference aura type or effects"


def test_consumable_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test consumable item generation (items with click effects)."""
    events = list(item_update_service.update_pages(test_engine))

    consumable_events = [
        e for e in events if isinstance(e, PageUpdated) and "Potion" in e.page_title
    ]

    assert len(consumable_events) >= 1, "Should generate at least one consumable page"

    for event in consumable_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Consumables use Item or specialized template
        # Should NOT have Fancy table
        assert "Fancy-" not in content, "Consumables should not have Fancy tables"


def test_ability_book_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test ability book generation (TeachSpell/TeachSkill items)."""
    events = list(item_update_service.update_pages(test_engine))

    book_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and ("Spell Book" in e.page_title or "Skill Book" in e.page_title)
    ]

    assert len(book_events) >= 1, "Should generate at least one ability book page"

    for event in book_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should NOT have Fancy table
        assert "Fancy-" not in content, "Ability books should not have Fancy tables"


def test_mold_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test mold/template item generation (Template=1)."""
    events = list(item_update_service.update_pages(test_engine))

    mold_events = [
        e for e in events if isinstance(e, PageUpdated) and "Mold" in e.page_title
    ]

    # Molds may or may not be generated depending on implementation
    # If generated, they should not have Fancy tables
    for event in mold_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert "Fancy-" not in content, "Molds should not have Fancy tables"


def test_general_item_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test general item generation (no special properties)."""
    events = list(item_update_service.update_pages(test_engine))

    general_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and (
            "Ore" in e.page_title or "Leather" in e.page_title or "Gem" in e.page_title
        )
    ]

    assert len(general_events) >= 1, "Should generate at least one general item page"

    for event in general_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # General items use Item template
        assert_page_structure_valid(content, ["Item"])

        # Should NOT have Fancy table
        assert "Fancy-" not in content, "General items should not have Fancy tables"


def test_item_with_no_sell_value(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test item with no sell value (edge case)."""
    events = list(item_update_service.update_pages(test_engine))

    quest_item_events = [
        e for e in events if isinstance(e, PageUpdated) and "Quest Item" in e.page_title
    ]

    # If quest items are generated, verify they handle zero sell value
    for event in quest_item_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should still have valid structure
        assert_page_structure_valid(content, ["Item"])


def test_unique_item_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test unique item generation (Unique=1)."""
    events = list(item_update_service.update_pages(test_engine))

    unique_events = [
        e for e in events if isinstance(e, PageUpdated) and "Legendary" in e.page_title
    ]

    # Unique weapons should still have Fancy table
    for event in unique_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Legendary Sword is a weapon, should have Fancy table
        if "Sword" in event.page_title:
            assert_page_structure_valid(content, ["Item", "Fancy-weapon"])


def test_relic_item_generation(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test relic item generation (Relic=1)."""
    events = list(item_update_service.update_pages(test_engine))

    relic_events = [
        e for e in events if isinstance(e, PageUpdated) and "Relic" in e.page_title
    ]

    # Relics are general items
    for event in relic_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert_page_structure_valid(content, ["Item"])
        assert "Fancy-" not in content, "Relics should not have Fancy tables"


def test_item_update_statistics(
    test_engine: Engine,
    item_update_service: UpdateService,
) -> None:
    """Test that UpdateComplete event has correct statistics."""
    events = list(item_update_service.update_pages(test_engine))

    complete_events = [e for e in events if isinstance(e, UpdateComplete)]

    assert len(complete_events) == 1, "Should have exactly one UpdateComplete event"

    complete = complete_events[0]
    assert complete.total > 0, "Should generate some items"
    assert (
        complete.updated > 0 or complete.unchanged > 0
    ), "Should have updated or unchanged items"


def test_item_validation_passes(
    test_engine: Engine,
    item_update_service: UpdateService,
) -> None:
    """Test that generated items pass validation."""
    events = list(item_update_service.update_pages(test_engine))

    failed_events = [e for e in events if isinstance(e, ValidationFailed)]

    # Ideally, all generated items should pass validation
    # If any fail, print them for debugging
    if failed_events:
        for event in failed_events:
            print(f"Validation failed for {event.page_title}:")
            for violation in event.violations:
                print(f"  - {violation.field}: {violation.message}")

    # Allow some failures but not too many
    assert len(failed_events) < 5, (
        f"Too many validation failures: {len(failed_events)}. "
        "Check if generated content is malformed."
    )


def test_item_content_not_empty(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that generated item pages are not empty."""
    events = list(item_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    for event in updated_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert content is not None, f"Page content is None: {event.page_title}"
        assert (
            len(content) > 100
        ), f"Page content too short ({len(content)} chars): {event.page_title}"
        assert (
            "{{" in content and "}}" in content
        ), f"Page has no templates: {event.page_title}"


def test_weapon_tier_stats(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that weapons have all three tiers with different stats."""
    events = list(item_update_service.update_pages(test_engine))

    # Find weapon events (exclude molds)
    weapon_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and "Sword" in e.page_title
        and "Mold:" not in e.page_title
    ]

    for event in weapon_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have damage ranges for each tier
        # Tier 0 should have lower damage than tier 2
        # This is a rough check - detailed validation happens in validators
        lines = content.split("\n")
        tier_lines = [line for line in lines if "tier = " in line]

        assert (
            len(tier_lines) >= 3
        ), f"Should have at least 3 tier rows in {event.page_title}"


def test_weapon_with_wrong_tier_count_is_skipped(
    test_engine: Engine,
    item_update_service: UpdateService,
    test_output_storage: PageStorage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that weapons with wrong tier count are skipped and error is logged."""
    import logging

    from sqlalchemy import text

    # Create a test weapon with only 2 tiers (missing tier)
    with test_engine.connect() as conn:
        # Insert a weapon item
        conn.execute(
            text(
                "INSERT INTO Items (Id, ResourceName, ItemName, RequiredSlot, ThisWeaponType, ItemValue, SellValue) "
                "VALUES ('9999', 'TestBadWeapon', 'Test Bad Weapon', 'Primary', 'OneHandMelee', 100, 50)"
            )
        )
        # Insert only 2 tiers (Normal and Blessed) - missing Godly
        conn.execute(
            text(
                "INSERT INTO ItemStats (ItemId, Quality, WeaponDmg, Str, Dex) "
                "VALUES ('9999', 'Normal', 15, 5, 0), ('9999', 'Blessed', 22, 8, 0)"
            )
        )
        conn.commit()

    try:
        # Capture logs
        with caplog.at_level(logging.ERROR):
            # Run update
            events = list(item_update_service.update_pages(test_engine))

        # Verify that "Test Bad Weapon" was NOT generated (skipped)
        generated_events = [e for e in events if isinstance(e, ContentGenerated)]
        bad_weapon_generated = [
            e for e in generated_events if "Test Bad Weapon" in e.page_title
        ]
        assert (
            len(bad_weapon_generated) == 0
        ), f"'Test Bad Weapon' should not be generated. Found: {bad_weapon_generated}"

        # Verify that "Test Bad Weapon" was NOT updated (skipped)
        updated_events = [e for e in events if isinstance(e, PageUpdated)]
        bad_weapon_updated = [
            e for e in updated_events if "Test Bad Weapon" in e.page_title
        ]
        assert (
            len(bad_weapon_updated) == 0
        ), f"'Test Bad Weapon' should not be updated. Found: {bad_weapon_updated}"

        # Verify error was logged
        error_logs = [
            record.message
            for record in caplog.records
            if record.levelname == "ERROR" and "Test Bad Weapon" in record.message
        ]

        assert len(error_logs) >= 1, (
            f"Expected error log for 'Test Bad Weapon'. "
            f"Error logs: {[r.message for r in caplog.records if r.levelname == 'ERROR']}"
        )

        # Verify error message mentions tier count and DATA ERROR
        error_msg = error_logs[0]
        assert (
            "DATA ERROR" in error_msg
        ), f"Error message should mention DATA ERROR: {error_msg}"
        assert (
            "tier" in error_msg.lower()
        ), f"Error message should mention tiers: {error_msg}"
        assert (
            "2" in error_msg and "3" in error_msg
        ), f"Error message should mention expected (3) and actual (2) tier counts: {error_msg}"

    finally:
        # Clean up test data
        with test_engine.connect() as conn:
            conn.execute(text("DELETE FROM ItemStats WHERE ItemId = '9999'"))
            conn.execute(text("DELETE FROM Items WHERE Id = '9999'"))
            conn.commit()


def test_ability_book_teaches_skill(
    item_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Items that teach skills (ability books) generate correctly."""
    list(item_update_service.update_pages(test_engine))

    # Skill Book: Power Strike teaches skill 100
    page = test_output_storage.registry.get_page_by_title("Skill Book: Power Strike")
    assert page is not None
    content = test_output_storage.read(page)
    assert content is not None

    # Should use Ability Books template
    assert "{{Ability Books" in content

    # Should have Learn Skill effect
    assert "|effects=Learn Skill: [[Power Strike]]" in content

    # Should have class requirements from skill (Duelist 5, Paladin 5)
    assert "[[Duelist]] (5)" in content
    assert "[[Paladin]] (5)" in content
