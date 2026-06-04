"""Generate compact Lua data modules for quest wiki pages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.quest import Quest
    from erenshor.domain.value_objects.faction import FactionModifier

LuaData = dict[str, object]


class QuestDataRepository(Protocol):
    """Repository methods needed to build the quest data module."""

    def get_quests_for_wiki_generation(self) -> list[Quest]: ...

    def get_faction_changes_for_quests(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]: ...


def generate_quests_module(quest_repo: QuestDataRepository) -> str:
    """Generate `Module:Erenshor/Data/Quests` from clean DB repositories."""
    quests = quest_repo.get_quests_for_wiki_generation()
    stable_keys = [quest.stable_key for quest in quests]
    return module_text(build_quests_data(quests, quest_repo.get_faction_changes_for_quests(stable_keys)))


def write_quests_module(quest_repo: QuestDataRepository, output_root: Path) -> Path:
    """Write the generated quest data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Quests.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_quests_module(quest_repo), encoding="utf-8")
    return output_path


def build_quests_data(
    quests: Iterable[Quest],
    faction_changes_by_quest: dict[str, list[FactionModifier]],
) -> LuaData:
    """Build the serializable quest data table for `mw.loadData()`."""
    quest_rows: dict[str, LuaData] = {}
    for quest in sorted(quests, key=lambda candidate: candidate.stable_key):
        record = _quest_record(quest, faction_changes_by_quest.get(quest.stable_key, []))
        if record is None:
            continue
        quest_rows[quest.stable_key] = record
    return {"quests": quest_rows}


def _quest_record(quest: Quest, faction_changes: list[FactionModifier]) -> LuaData | None:
    name = quest.display_name or quest.quest_name or quest.wiki_page_name
    page = quest.wiki_page_name or name
    if name is None or page is None:
        return None
    record: LuaData = {"name": name, "page": page}
    _put(record, "image", quest.image_name)
    _put(record, "repeatable", _yes_no(quest.repeatable))
    _put(record, "experience", quest.xp_on_complete)
    _put(record, "gold", quest.gold_on_complete)
    _put(record, "factionChanges", _faction_changes(faction_changes))
    return record


def _yes_no(value: int | None) -> str:
    return "Yes" if value else "No"


def _faction_changes(faction_changes: list[FactionModifier]) -> str:
    out: list[str] = []
    for change in faction_changes:
        if change.modifier_value == 0:
            continue
        page = change.faction_wiki_page_name
        display = change.faction_display_name
        if page is None:
            faction = display
        elif page == display:
            faction = f"[[{display}]]"
        else:
            faction = f"[[{page}|{display}]]"
        prefix = "+" if change.modifier_value > 0 else ""
        out.append(f"{faction} {prefix}{change.modifier_value}")
    return "<br>".join(out)


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value
