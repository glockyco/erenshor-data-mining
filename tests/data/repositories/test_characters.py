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


def test_page_vendor_status_covers_every_group_member(character_repo: CharacterRepository) -> None:
    """Cerbantias Flameward sells items only as the 'combined' duplicate, not the representative."""
    cerbantias = next(
        character
        for character in character_repo.get_characters_for_wiki_generation()
        if character.wiki_page_name == "Cerbantias Flameward"
    )

    assert cerbantias.stable_key == "character:cerbantias flameward"
    assert cerbantias.is_vendor


def test_roster_collapses_same_page_copies_and_keeps_all_abyssal_tiers(character_repo: CharacterRepository) -> None:
    from erenshor.application.wiki_lua.zone_rosters import build_zone_roster_rows

    rows = build_zone_roster_rows(character_repo.get_zone_roster_spawns())["zone:abyssal"]
    assert len([row for row in rows if row["tier"] == "enemy"]) == 9
    assert len([row for row in rows if row["tier"] == "boss"]) == 6
    assert len({row["character"] for row in rows}) == 15
    assert all(0 <= row["chanceMin"] <= row["chanceMax"] <= 100 for row in rows)
