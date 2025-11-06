"""Pytest configuration and fixtures for generator tests."""

from unittest.mock import MagicMock

import pytest

from erenshor.registry.resolver import RegistryResolver


@pytest.fixture
def mock_resolver() -> RegistryResolver:
    """Create a mock RegistryResolver for testing.

    Returns mock implementations for all resolver methods used by generators.
    For zone stable keys, returns just the zone name without prefix.
    """
    resolver = MagicMock(spec=RegistryResolver)

    # Mock resolve_page_title: for zone keys, return just the name; otherwise add prefix
    def resolve_page_title(key: str) -> str:
        # For zone:name format, return just the name part
        if ":" in key:
            return key.split(":", 1)[1]
        return f"Page_{key}"

    resolver.resolve_page_title.side_effect = resolve_page_title
    resolver.resolve_display_name.side_effect = lambda key: f"Display_{key}"
    resolver.resolve_image_name.side_effect = lambda key: f"Image_{key}"

    # Mock link methods
    resolver.character_link.side_effect = lambda key: f"{{{{CharacterLink|{key}}}}}"
    resolver.item_link.side_effect = lambda key: f"{{{{ItemLink|{key}}}}}"
    resolver.ability_link.side_effect = lambda key: f"{{{{AbilityLink|{key}}}}}"
    resolver.faction_link.side_effect = lambda key: f"{{{{FactionLink|{key}}}}}"
    resolver.zone_link.side_effect = lambda key: f"{{{{ZoneLink|{key}}}}}"
    resolver.quest_link.side_effect = lambda key: f"{{{{QuestLink|{key}}}}}"

    return resolver
