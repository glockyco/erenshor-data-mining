"""Tests for QuestRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.domain.entities.quest import Quest
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.quests import QuestRepository

if TYPE_CHECKING:
    from pathlib import Path


def test_get_quests_for_wiki_generation_returns_sorted_quests(integration_db: Path) -> None:
    """Quest Lua generation reads real clean DB quest rows in display order."""
    repo = QuestRepository(DatabaseConnection(integration_db, read_only=True))

    quests = repo.get_quests_for_wiki_generation()

    assert quests
    assert all(isinstance(quest, Quest) for quest in quests)
    assert all(quest.stable_key for quest in quests)
    display_names = [quest.display_name.lower() if quest.display_name else "" for quest in quests]
    assert display_names == sorted(display_names)
