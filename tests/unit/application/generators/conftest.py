"""Pytest configuration and fixtures for generator tests."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService

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
    service.map_class_list.side_effect = lambda names: sorted(str(identity.get(n, n)) for n in names)
    service.get_all_display_names.return_value = sorted(identity.values())
    service.get_all_internal_names.return_value = sorted(identity.keys())
    return service
