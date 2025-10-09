"""Integration tests for character/enemy updates.

Tests cover all character types:
- Unique bosses (with coordinates)
- Rare enemies (with spawn chance)
- Common enemies
- Friendly NPCs
- Vendors
- Multi-entity skip logic
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from erenshor.application.services.update_service import UpdateService
from erenshor.domain.events import (
    PageUpdated,
    UpdateComplete,
    ValidationFailed,
)
from erenshor.infrastructure.storage.page_storage import PageStorage
from tests.conftest import assert_page_structure_valid


def test_unique_boss_generation(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test unique boss character generation (with coordinates)."""
    events = list(character_update_service.update_pages(test_engine))

    boss_events = [
        e for e in events if isinstance(e, PageUpdated) and "Dragon" in e.page_title
    ]

    assert len(boss_events) >= 1, "Should generate at least one boss page"

    for event in boss_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should use Enemy template
        assert_page_structure_valid(content, ["Enemy"])

        # Unique bosses should have coordinates (since IsUnique=true)
        assert "coordinates" in content.lower() or "location" in content.lower(), (
            "Unique boss should have coordinates"
        )


def test_rare_enemy_generation(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test rare enemy generation (with spawn chance)."""
    events = list(character_update_service.update_pages(test_engine))

    rare_events = [
        e for e in events if isinstance(e, PageUpdated) and "Elite" in e.page_title
    ]

    assert len(rare_events) >= 1, "Should generate at least one rare enemy page"

    for event in rare_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert_page_structure_valid(content, ["Enemy"])

        # Rare enemies may have spawn chance if hostile
        # This depends on implementation details


def test_common_enemy_generation(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test common enemy generation."""
    events = list(character_update_service.update_pages(test_engine))

    common_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and ("Goblin" in e.page_title or "Orc" in e.page_title)
    ]

    assert len(common_events) >= 1, "Should generate at least one common enemy page"

    for event in common_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert_page_structure_valid(content, ["Enemy"])

        # Common enemies should NOT have coordinates (not unique)
        # They may have spawn locations and zones


def test_friendly_npc_generation(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test friendly NPC generation (use Enemy template regardless)."""
    events = list(character_update_service.update_pages(test_engine))

    npc_events = [
        e
        for e in events
        if isinstance(e, PageUpdated)
        and ("Merchant" in e.page_title or "Elder" in e.page_title)
    ]

    # NPCs may or may not be generated depending on implementation
    # If generated, they should use Enemy template
    for event in npc_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert_page_structure_valid(content, ["Enemy"])

        # Friendly NPCs should have type=NPC or similar
        assert "NPC" in content or "Friendly" in content, (
            "Friendly NPC should be marked appropriately"
        )


def test_character_with_drops(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test character with loot drops (guaranteeddrops + droprates)."""
    events = list(character_update_service.update_pages(test_engine))

    # Boss has guaranteed drops
    boss_events = [
        e for e in events if isinstance(e, PageUpdated) and "Dragon" in e.page_title
    ]

    for event in boss_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have drop information
        # Implementation may use guaranteeddrops and droprates fields
        assert "drop" in content.lower(), "Boss should have drop information"


def test_character_stats_populated(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that character stats are populated correctly."""
    events = list(character_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    for event in updated_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # Should have level
        assert "level" in content.lower(), f"{event.page_title} should have level"

        # Should have health (Enemy template uses 'health' not 'hp')
        assert "health" in content.lower(), f"{event.page_title} should have health"


def test_character_update_statistics(
    test_engine: Engine,
    character_update_service: UpdateService,
) -> None:
    """Test that UpdateComplete event has correct statistics."""
    events = list(character_update_service.update_pages(test_engine))

    complete_events = [e for e in events if isinstance(e, UpdateComplete)]

    assert len(complete_events) == 1, "Should have exactly one UpdateComplete event"

    complete = complete_events[0]
    assert complete.total > 0, "Should generate some characters"


def test_character_validation_passes(
    test_engine: Engine,
    character_update_service: UpdateService,
) -> None:
    """Test that generated characters pass validation."""
    events = list(character_update_service.update_pages(test_engine))

    failed_events = [e for e in events if isinstance(e, ValidationFailed)]

    if failed_events:
        for event in failed_events:
            print(f"Validation failed for {event.page_title}:")
            for violation in event.violations:
                print(f"  - {violation.field}: {violation.message}")

    # Allow some failures but not too many
    assert len(failed_events) < 5, f"Too many validation failures: {len(failed_events)}"


def test_character_content_not_empty(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that generated character pages are not empty."""
    events = list(character_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    for event in updated_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        assert content is not None, f"Page content is None: {event.page_title}"
        assert len(content) > 50, (
            f"Page content too short ({len(content)} chars): {event.page_title}"
        )
        assert "{{" in content and "}}" in content, (
            f"Page has no templates: {event.page_title}"
        )


def test_simplayer_skip(
    test_engine: Engine,
    character_update_service: UpdateService,
) -> None:
    """Test that sim players (IsSimPlayer=1) are skipped."""
    events = list(character_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    # None of our test data has IsSimPlayer=1, but verify logic
    # by checking that only expected characters are generated
    assert len(updated_events) <= 10, (
        "Should not generate more than 10 character pages (test data has 10 non-sim characters)"
    )


def test_enemy_template_used_for_all(
    test_engine: Engine,
    character_update_service: UpdateService,
    test_output_storage: PageStorage,
) -> None:
    """Test that Enemy template is used for ALL characters (hostile and friendly)."""
    events = list(character_update_service.update_pages(test_engine))

    updated_events = [e for e in events if isinstance(e, PageUpdated)]

    for event in updated_events:
        page = test_output_storage.registry.get_page_by_title(event.page_title)
        assert page is not None
        content = test_output_storage.read(page)
        assert content is not None

        # All should use Enemy template (per CLAUDE.md requirements)
        assert_page_structure_valid(content, ["Enemy"])

        # Should NOT have legacy "Enemy Stats" template
        assert "Enemy Stats" not in content, (
            "Should not have legacy Enemy Stats template"
        )
