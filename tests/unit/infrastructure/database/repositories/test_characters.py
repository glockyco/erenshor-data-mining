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


def test_obtained_from_character_sources_preserve_keys_and_conditions(
    character_repo: CharacterRepository,
) -> None:
    """Character provenance keeps representative keys and quest-gate text."""
    drops = character_repo.get_character_drop_sources("item:template - inert diamond")
    assert drops[0].source_key == "character:treasurechest 0-10 1"
    assert drops[0].probability == 84.4
    assert drops[0].is_guaranteed is True

    vendors = character_repo.get_vendor_sources_for_item("item:furniture - azynthi coffin")
    assert len(vendors) == 1
    assert vendors[0].source_key == "character:breena carpenter"
    assert vendors[0].condition == "requires quest Crafting: Azynthian Resting Place"

    dialogs = character_repo.get_characters_giving_item("item:gen - shivering belt lamp")
    assert dialogs[0].source_key.startswith("character:kio the lightkeeper")
    assert dialogs[0].condition == "requires quest Meet Shivering Step"
