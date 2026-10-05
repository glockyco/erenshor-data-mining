"""What simulated-player chat can say, read from the clean knowledge base.

Chat answers from the knowledge base that the game ships, never from the
characters themselves. It names an entry without being asked when the entry
has a name and a zone. It names an entry as the source of an item when the
entry is the first one whose drops list the item. It names any entry when a
player asks for it by name.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Sequence


def normalize_chat_name(name: str | None) -> str:
    """Return a name as chat stores it (``KnowledgeDatabase.Normalize``)."""
    lowered = (name or "").lower()
    return "".join(character for character in lowered if character.isalnum() or character.isspace())


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    position: int
    npc_name: str
    zone_name: str | None
    level: int
    is_boss: bool
    prefab_path: str
    drops: tuple[str, ...]
    character_keys: tuple[str, ...]

    @property
    def prefab_file_name(self) -> str:
        return self.prefab_path.rpartition("/")[2]

    @property
    def named_unprompted(self) -> bool:
        """Whether random guild questions can pick the entry."""
        # code-fact: chat.random_name_requires_zone
        return bool(self.npc_name) and bool(self.zone_name)


class ChatKnowledge:
    """The entries in the order chat reads them, with lookups by item and by character."""

    def __init__(self, entries: Sequence[KnowledgeEntry]) -> None:
        self.entries = tuple(entries)
        # code-fact: chat.item_source_is_first_entry
        self._first_source: dict[str, int] = {}
        by_character: dict[str, list[KnowledgeEntry]] = defaultdict(list)
        for entry in self.entries:
            for item_name in entry.drops:
                self._first_source.setdefault(item_name, entry.position)
            for key in entry.character_keys:
                by_character[key].append(entry)
        self._by_character = {key: tuple(found) for key, found in by_character.items()}

    def items_named_as_source(self, entry: KnowledgeEntry) -> tuple[str, ...]:
        """Return the items for which chat names this entry as the source."""
        return tuple(dict.fromkeys(item for item in entry.drops if self._first_source[item] == entry.position))

    def entries_for_character(self, stable_key: str) -> tuple[KnowledgeEntry, ...]:
        return self._by_character.get(stable_key, ())


def load_chat_knowledge(clean: sqlite3.Connection) -> ChatKnowledge:
    """Read the knowledge base, its drops, and its character links from the clean database."""
    drops: dict[int, list[str]] = defaultdict(list)
    for entry_position, item_name in clean.execute(
        "SELECT entry_position, item_name FROM knowledge_entry_drops ORDER BY entry_position, position"
    ):
        drops[int(entry_position)].append(str(item_name))
    keys: dict[int, list[str]] = defaultdict(list)
    for entry_position, character_key in clean.execute(
        "SELECT entry_position, character_stable_key FROM knowledge_entry_characters ORDER BY 1, 2"
    ):
        keys[int(entry_position)].append(str(character_key))
    entries = tuple(
        KnowledgeEntry(
            position=int(position),
            npc_name=str(npc_name),
            zone_name=str(zone_name) if zone_name else None,
            level=int(level),
            is_boss=bool(is_boss),
            prefab_path=str(prefab_path),
            drops=tuple(drops[int(position)]),
            character_keys=tuple(keys[int(position)]),
        )
        for position, npc_name, zone_name, level, is_boss, prefab_path in clean.execute(
            "SELECT position, npc_name, zone_name, level, is_boss, prefab_path FROM knowledge_entries ORDER BY position"
        )
    )
    return ChatKnowledge(entries)
