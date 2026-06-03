"""Generate compact Lua data modules for quest wiki pages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.quest import Quest

LuaData = dict[str, object]


class QuestDataRepository(Protocol):
    """Repository methods needed to build the quest data module."""

    def get_quests_for_wiki_generation(self) -> list[Quest]: ...


def generate_quests_module(quest_repo: QuestDataRepository) -> str:
    """Generate `Module:Erenshor/Data/Quests` from clean DB repositories."""
    return module_text(build_quests_data(quest_repo.get_quests_for_wiki_generation()))


def write_quests_module(quest_repo: QuestDataRepository, output_root: Path) -> Path:
    """Write the generated quest data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Quests.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_quests_module(quest_repo), encoding="utf-8")
    return output_path


def build_quests_data(quests: Iterable[Quest]) -> LuaData:
    """Build the serializable quest data table for `mw.loadData()`."""
    quest_rows: dict[str, LuaData] = {}
    by_page: dict[str, str] = {}
    for quest in sorted(quests, key=lambda candidate: candidate.stable_key):
        record = _quest_record(quest)
        if record is None:
            continue
        quest_rows[quest.stable_key] = record
        page = record.get("page")
        if isinstance(page, str) and page:
            by_page[page] = quest.stable_key
    return {"quests": quest_rows, "byPage": dict(sorted(by_page.items()))}


def _quest_record(quest: Quest) -> LuaData | None:
    name = quest.display_name or quest.quest_name or quest.wiki_page_name
    page = quest.wiki_page_name or name
    if name is None or page is None:
        return None
    record: LuaData = {"name": name, "page": page}
    _put(record, "image", quest.image_name)
    _put(record, "repeatable", _yes_no(quest.repeatable))
    _put(record, "experience", quest.xp_on_complete)
    _put(record, "gold", quest.gold_on_complete)
    _put(record, "factionChanges", _faction_changes(quest.affected_factions, quest.affected_faction_amounts))
    return record


def _yes_no(value: int | None) -> str:
    return "Yes" if value else "No"


def _faction_changes(factions: str | None, amounts: str | None) -> str:
    if not factions or not amounts:
        return ""
    faction_values = [faction.strip() for faction in factions.split(",")]
    amount_values = [amount.strip() for amount in amounts.split(",")]
    out: list[str] = []
    for faction, amount in zip(faction_values, amount_values, strict=False):
        if not faction or not amount:
            continue
        prefix = "+" if not amount.startswith("-") else ""
        out.append(f"{faction} {prefix}{amount}")
    return "<br>".join(out)


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value
