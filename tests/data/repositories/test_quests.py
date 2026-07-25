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


def test_get_faction_changes_for_quests_returns_display_names(integration_db: Path) -> None:
    """Quest faction changes are joined to display names for Lua output."""
    repo = QuestRepository(DatabaseConnection(integration_db, read_only=True))

    changes = repo.get_faction_changes_for_quests(["quest:a skeleton eye for alyssa fearnon"])

    assert changes["quest:a skeleton eye for alyssa fearnon"]
    assert [
        (change.faction_display_name, change.modifier_value)
        for change in changes["quest:a skeleton eye for alyssa fearnon"]
    ] == [
        ("Fernalla's Children", 1),
        ("The Children of Sivakaya", -1),
    ]


def test_quest_reward_sources_keep_stable_keys(integration_db: Path) -> None:
    """Quest provenance uses the quest StableKey rather than page text."""
    repo = QuestRepository(DatabaseConnection(integration_db, read_only=True))

    sources = repo.get_quest_reward_sources("item:gen - nightmare crystal")

    assert sources
    assert all(source.source_type == "quest" for source in sources)
    assert all(source.source_key.startswith("quest:") for source in sources)


def test_quest_requirement_sources_keep_quantities_and_stable_keys(integration_db: Path) -> None:
    """Quest requirements retain quantities while using quest StableKeys."""
    repo = QuestRepository(DatabaseConnection(integration_db, read_only=True))

    sources = repo.get_quest_requirement_sources("item:gen - eldrich crystal")

    assert sources
    assert all(source.use_type == "quest_requirement" for source in sources)
    assert all(source.target_key.startswith("quest:") for source in sources)
    assert all(source.quantity is not None for source in sources)
    assert all(source.slot is None for source in sources)
