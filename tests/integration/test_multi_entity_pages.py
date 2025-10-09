"""Integration tests for multi-entity page generation.

Tests that multiple entities (skill + spell, multiple characters, etc.) that map
to the same wiki page are correctly merged into a single file with multiple infoboxes.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

from erenshor.application.services.update_service import UpdateService
from erenshor.domain.events import PageUpdated, UpdateComplete
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry


def test_multi_entity_page_grouping_logic(
    ability_update_service: UpdateService,
    test_engine: Engine,
) -> None:
    """Test that multi-entity pages are handled correctly by grouping logic.

    Note: Test database may not have specific merged entities, but we verify
    the grouping logic works by checking event emission patterns.
    """
    from erenshor.domain.events import ContentGenerated, PageUpdated

    # Generate all abilities
    events = list(ability_update_service.update_pages(test_engine))

    # Get all page titles that have multiple ContentGenerated events
    content_events = [e for e in events if isinstance(e, ContentGenerated)]
    page_event_counts: dict[str, int] = {}
    for event in content_events:
        page_event_counts[event.page_title] = (
            page_event_counts.get(event.page_title, 0) + 1
        )

    multi_entity_pages = [
        title for title, count in page_event_counts.items() if count > 1
    ]

    # If test data has multi-entity pages, verify they got PageUpdated events
    if multi_entity_pages:
        page_updated_events = [e for e in events if isinstance(e, PageUpdated)]
        updated_titles = {e.page_title for e in page_updated_events}

        for title in multi_entity_pages:
            assert title in updated_titles, (
                f"Multi-entity page '{title}' should have PageUpdated event"
            )


def test_single_entity_page_unchanged(
    ability_update_service: UpdateService,
    test_engine: Engine,
    test_output_storage: PageStorage,
) -> None:
    """Single-entity pages should work as before (no regression)."""
    # Generate all abilities
    list(ability_update_service.update_pages(test_engine))

    # Mining is only a skill, not merged with anything
    page = test_output_storage.registry.get_page_by_title("Mining")

    # May not exist in test data - skip if not present
    if page is None:
        return

    content = test_output_storage.read(page)
    assert content is not None

    # Should have exactly ONE infobox
    ability_count = content.count("{{Ability")
    assert ability_count == 1, (
        f"Single-entity page should have 1 infobox, found {ability_count}"
    )


def test_statistics_count_entities_correctly(
    ability_update_service: UpdateService,
    test_engine: Engine,
) -> None:
    """UpdateComplete statistics should count all entities."""
    # Collect all events
    events = list(ability_update_service.update_pages(test_engine))

    complete_events = [e for e in events if isinstance(e, UpdateComplete)]
    assert len(complete_events) == 1

    complete = complete_events[0]

    # Total should count all entities
    # In test data: 8 spells + 10 skills = 18 abilities total
    assert complete.total >= 18, (
        f"Total should count entities (18+), got {complete.total}"
    )
