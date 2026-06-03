"""Generate compact Lua data modules for ability link templates."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.skill import Skill
    from erenshor.domain.entities.spell import Spell
    from erenshor.domain.entities.stance import Stance

LuaData = dict[str, object]


class SpellDataRepository(Protocol):
    """Repository methods needed to build ability-link spell data."""

    def get_spells_for_wiki_generation(self) -> list[Spell]: ...


class SkillDataRepository(Protocol):
    """Repository methods needed to build ability-link skill data."""

    def get_skills_for_wiki_generation(self) -> list[Skill]: ...


class StanceDataRepository(Protocol):
    """Repository methods needed to build ability-link stance data."""

    def get_all(self) -> list[Stance]: ...


def generate_ability_links_module(
    spell_repo: SpellDataRepository,
    skill_repo: SkillDataRepository,
    stance_repo: StanceDataRepository,
) -> str:
    """Generate `Module:Erenshor/Data/AbilityLinks` from clean DB repositories."""
    return module_text(
        build_ability_links_data(
            spells=spell_repo.get_spells_for_wiki_generation(),
            skills=skill_repo.get_skills_for_wiki_generation(),
            stances=stance_repo.get_all(),
        )
    )


def write_ability_links_module(
    spell_repo: SpellDataRepository,
    skill_repo: SkillDataRepository,
    stance_repo: StanceDataRepository,
    output_root: Path,
) -> Path:
    """Write the generated ability-link data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "AbilityLinks.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_ability_links_module(spell_repo, skill_repo, stance_repo), encoding="utf-8")
    return output_path


def build_ability_links_data(
    spells: Iterable[Spell],
    skills: Iterable[Skill],
    stances: Iterable[Stance],
) -> LuaData:
    """Build the serializable ability-link lookup table for `mw.loadData()`."""
    abilities: dict[str, LuaData] = {}
    by_name: dict[str, str] = {}

    for stable_key, record in sorted(_iter_records(spells, skills, stances), key=lambda candidate: candidate[0]):
        abilities[stable_key] = record
        _index_name(by_name, record.get("name"), stable_key)
        _index_name(by_name, record.get("page"), stable_key)

    return {"abilities": abilities, "byName": dict(sorted(by_name.items()))}


def _iter_records(
    spells: Iterable[Spell],
    skills: Iterable[Skill],
    stances: Iterable[Stance],
) -> Iterable[tuple[str, LuaData]]:
    for spell in spells:
        record = _record(spell.stable_key, spell.display_name, spell.wiki_page_name, spell.image_name, "spell")
        if record is not None:
            yield spell.stable_key, record
    for skill in skills:
        record = _record(skill.stable_key, skill.display_name, skill.wiki_page_name, skill.image_name, "skill")
        if record is not None:
            yield skill.stable_key, record
    for stance in stances:
        record = _record(stance.stable_key, stance.display_name, stance.wiki_page_name, stance.image_name, "stance")
        if record is not None:
            yield stance.stable_key, record


def _record(stable_key: str, name: str | None, page: str | None, image: str | None, kind: str) -> LuaData | None:
    if not name and not page:
        return None
    resolved_name = name or page
    resolved_page = page or name
    if resolved_name is None or resolved_page is None:
        return None
    record: LuaData = {"name": resolved_name, "page": resolved_page, "kind": kind}
    if image:
        record["image"] = image
    else:
        record["image"] = resolved_name
    return record


def _index_name(index: dict[str, str], name: object, stable_key: str) -> None:
    if isinstance(name, str) and name:
        index.setdefault(name, stable_key)
