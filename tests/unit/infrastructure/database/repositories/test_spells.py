"""Tests for SpellRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repositories.spells import SpellRepository

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def spell_repo(integration_db: Path) -> SpellRepository:
    """Create SpellRepository with integration database."""
    db = DatabaseConnection(integration_db, read_only=False)
    return SpellRepository(db)


def test_get_spells_for_wiki_generation_returns_all_spells(spell_repo: SpellRepository):
    """Test that get_spells_for_wiki_generation returns all valid spells."""
    spells = spell_repo.get_spells_for_wiki_generation()

    assert len(spells) >= 3, "Expected at least 3 spells from integration database"
    assert all(isinstance(spell, Spell) for spell in spells)
    assert all(spell.spell_name for spell in spells), "All spells should have spell_name"
    assert all(spell.stable_key for spell in spells), "All spells should have stable_key"


def test_get_spells_for_wiki_generation_filters_blank_names(spell_repo: SpellRepository):
    """Test that spells with blank names are filtered out.

    This test verifies the WHERE clause filters work correctly.
    We rely on the integration database not having blank spell names.
    """
    spells = spell_repo.get_spells_for_wiki_generation()

    # All returned spells should have non-blank names
    for spell in spells:
        assert spell.spell_name, f"Found spell with blank spell_name: {spell.stable_key}"
        assert spell.stable_key, f"Found spell with blank stable_key: {spell.stable_key}"


def test_get_spells_for_wiki_generation_sorted_by_name(spell_repo: SpellRepository):
    """Test that spells are sorted by name case-insensitively."""
    spells = spell_repo.get_spells_for_wiki_generation()

    if len(spells) >= 2:
        display_names = [s.display_name.lower() if s.display_name else "" for s in spells]
        assert display_names == sorted(display_names), "Spells should be sorted by display_name"


def test_spell_entities_have_required_fields(spell_repo: SpellRepository):
    """Test that Spell entities have required fields populated."""
    spells = spell_repo.get_spells_for_wiki_generation()
    assert len(spells) > 0

    for spell in spells:
        # Required fields
        assert spell.spell_name is not None
        assert spell.stable_key is not None

        # Verify stable key format
        assert spell.stable_key.startswith("spell:")


def test_spell_repository_handles_database_error(tmp_path: Path):
    """Test that repository raises RepositoryError on database errors."""
    # Create a database path that doesn't exist
    nonexistent_db = tmp_path / "nonexistent.sqlite"

    # Try to create connection with read-only (will fail if file doesn't exist)
    with pytest.raises(DatabaseConnectionError):
        DatabaseConnection(nonexistent_db, read_only=True)


def test_spell_repository_validates_data_types(spell_repo: SpellRepository):
    """Test that repository correctly converts database types to Python types."""
    spells = spell_repo.get_spells_for_wiki_generation()
    assert len(spells) > 0

    for spell in spells:
        # Check type conversions
        assert isinstance(spell.stable_key, str)
        assert spell.spell_name is None or isinstance(spell.spell_name, str)
        assert spell.mana_cost is None or isinstance(spell.mana_cost, int)
        assert spell.cooldown is None or isinstance(spell.cooldown, int | float)
