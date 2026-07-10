"""Tests for CharacterRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def character_repo(integration_db: Path) -> CharacterRepository:
    """Create CharacterRepository with the real integration database."""
    return CharacterRepository(DatabaseConnection(integration_db, read_only=False))


def test_wiki_generation_characters_keep_spawned_statuses(character_repo: CharacterRepository) -> None:
    """Spawned status spell keys survive the character repository projection."""
    characters = character_repo.get_characters_for_wiki_generation()
    status_keys = [
        character.spawn_with_status_stable_key for character in characters if character.spawn_with_status_stable_key
    ]

    assert status_keys
    assert all(key.startswith("spell:") for key in status_keys)
