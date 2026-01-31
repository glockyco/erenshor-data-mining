"""Pytest configuration and fixtures for generator tests."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.registry.resolver import RegistryResolver

IDENTITY_CLASS_NAMES = [
    "Arcanist",
    "Druid",
    "Duelist",
    "Paladin",
    "Stormcaller",
]


@pytest.fixture
def mock_class_display() -> ClassDisplayNameService:
    """Create a mock ClassDisplayNameService with identity mappings.

    Maps each class name to itself, suitable for tests that don't care
    about display name differences between variants.
    """
    service = MagicMock(spec=ClassDisplayNameService)
    identity = {name: name for name in IDENTITY_CLASS_NAMES}
    service.get_display_name.side_effect = lambda name: identity.get(name, name)
    service.map_class_list.side_effect = lambda names: sorted(identity.get(n, n) for n in names)
    service.get_all_display_names.return_value = sorted(identity.values())
    service.get_all_internal_names.return_value = sorted(identity.keys())
    return service


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
