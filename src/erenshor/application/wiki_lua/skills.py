"""Generate a compact Lua data module for skill wiki pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.links import link_refs, mapped_class_link_ref
from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.skill import Skill
    from erenshor.domain.value_objects.wiki_link import ItemLink

LuaData = dict[str, object]

_CLASS_LEVEL_FIELDS: tuple[tuple[str, str], ...] = (
    ("Duelist", "duelist_required_level"),
    ("Paladin", "paladin_required_level"),
    ("Arcanist", "arcanist_required_level"),
    ("Druid", "druid_required_level"),
    ("Stormcaller", "stormcaller_required_level"),
    ("Reaver", "reaver_required_level"),
)

_TEXT_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("image", "image_name"),
    ("description", "skill_desc"),
    ("type", "type_of_skill"),
    ("stanceStableKey", "stance_to_use_stable_key"),
    ("spawnOnUseStableKey", "spawn_on_use_stable_key"),
    ("effectStableKey", "effect_to_apply_stable_key"),
    ("damageType", "damage_type"),
    ("castOnTargetStableKey", "cast_on_target_stable_key"),
    ("skillAnimName", "skill_anim_name"),
    ("skillIconName", "skill_icon_name"),
    ("playerUses", "player_uses"),
    ("npcUses", "npc_uses"),
)

_NUMBER_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("range", "skill_range"),
    ("skillPower", "skill_power"),
    ("percentDmg", "percent_dmg"),
)

_BOOL_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("requireBehind", "require_behind"),
    ("require2h", "require_2h"),
    ("requireDw", "require_dw"),
    ("requireBow", "require_bow"),
    ("requireShield", "require_shield"),
    ("simPlayersAutolearn", "sim_players_autolearn"),
    ("aeSkill", "ae_skill"),
    ("interrupt", "interrupt"),
    ("affectPlayer", "affect_player"),
    ("affectTarget", "affect_target"),
    ("scaleOffWeapon", "scale_off_weapon"),
    ("procWeap", "proc_weap"),
    ("procShield", "proc_shield"),
    ("guaranteeProc", "guarantee_proc"),
    ("skillCanCrit", "skill_can_crit"),
    ("automateAttack", "automate_attack"),
)


class SkillDataRepository(Protocol):
    """Repository methods needed to build the skill data module."""

    def get_skills_for_wiki_generation(self) -> list[Skill]: ...

    def get_class_display_names(self) -> dict[str, str]: ...


class SkillRelationshipItemRepository(Protocol):
    """Item repository methods needed for skill relationship fields."""

    def get_obtainable_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]: ...

    def get_items_with_skill_effect(self, skill_stable_key: str) -> list[ItemLink]: ...


def generate_skills_module(
    skill_repo: SkillDataRepository,
    item_repo: SkillRelationshipItemRepository | None = None,
) -> str:
    """Generate `Module:Erenshor/Data/Skills` from clean DB repositories."""
    skills = skill_repo.get_skills_for_wiki_generation()
    return module_text(
        build_skills_data(
            skills,
            skill_repo.get_class_display_names(),
            teaching_items_by_skill=_teaching_items_by_skill(skills, item_repo),
            items_with_effect_by_skill=_items_with_effect_by_skill(skills, item_repo),
        )
    )


def write_skills_module(
    skill_repo: SkillDataRepository,
    output_root: Path,
    item_repo: SkillRelationshipItemRepository | None = None,
) -> Path:
    """Write the generated skill data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Skills.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_skills_module(skill_repo, item_repo), encoding="utf-8")
    return output_path


def build_skills_data(
    skills: Iterable[Skill],
    class_display_names: Mapping[str, str],
    teaching_items_by_skill: Mapping[str, Iterable[ItemLink]] | None = None,
    items_with_effect_by_skill: Mapping[str, Iterable[ItemLink]] | None = None,
) -> LuaData:
    """Build the serializable skill data table for `mw.loadData()`."""
    rows: dict[str, LuaData] = {}
    for skill in sorted(skills, key=lambda candidate: candidate.stable_key):
        record = _skill_record(
            skill,
            class_display_names,
            teaching_items=teaching_items_by_skill.get(skill.stable_key, ())
            if teaching_items_by_skill is not None
            else (),
            items_with_effect=(
                items_with_effect_by_skill.get(skill.stable_key, ()) if items_with_effect_by_skill is not None else ()
            ),
        )
        if record is not None:
            rows[skill.stable_key] = record
    return {"skills": rows}


def _skill_record(
    skill: Skill,
    class_display_names: Mapping[str, str],
    teaching_items: Iterable[ItemLink] = (),
    items_with_effect: Iterable[ItemLink] = (),
) -> LuaData | None:
    name = skill.display_name or skill.skill_name or skill.wiki_page_name
    page = skill.wiki_page_name or name
    if name is None or page is None:
        return None

    record: LuaData = {"name": name, "page": page, "classLevels": _class_levels(skill, class_display_names)}
    for lua_key, attr in _TEXT_FIELD_MAP:
        _put_text(record, lua_key, getattr(skill, attr))
    for lua_key, attr in _NUMBER_FIELD_MAP:
        _put_number(record, lua_key, getattr(skill, attr))
    for lua_key, attr in _BOOL_FIELD_MAP:
        _put_bool(record, lua_key, getattr(skill, attr))
    if skill.cooldown is not None:
        _put_number(record, "cooldownSeconds", round(skill.cooldown / 60, 2))
    _put_list(record, "source", link_refs(teaching_items, "item"))
    _put_list(record, "itemsWithEffect", link_refs(items_with_effect, "item"))
    return record


def _class_levels(skill: Skill, class_display_names: Mapping[str, str]) -> list[LuaData]:
    levels: list[LuaData] = []
    for class_name, attr in _CLASS_LEVEL_FIELDS:
        level = getattr(skill, attr)
        if level is not None and level > 0:
            class_reference = mapped_class_link_ref(class_name, class_display_names)
            display_name = class_display_names[class_name].strip()
            levels.append(
                {
                    "className": class_name,
                    "displayName": display_name,
                    **class_reference,
                    "level": level,
                }
            )
    return sorted(levels, key=lambda row: str(row["displayName"]).casefold())


def _put_text(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value


def _put_number(row: LuaData, key: str, value: object) -> None:
    if value is not None:
        row[key] = value


def _put_bool(row: LuaData, key: str, value: object) -> None:
    row[key] = bool(value)


def _put_list(row: LuaData, key: str, value: list[LuaData]) -> None:
    if value:
        row[key] = value


def _teaching_items_by_skill(
    skills: Iterable[Skill], item_repo: SkillRelationshipItemRepository | None
) -> dict[str, list[ItemLink]]:
    if item_repo is None:
        return {}
    return {skill.stable_key: item_repo.get_obtainable_items_that_teach_skill(skill.stable_key) for skill in skills}


def _items_with_effect_by_skill(
    skills: Iterable[Skill], item_repo: SkillRelationshipItemRepository | None
) -> dict[str, list[ItemLink]]:
    if item_repo is None:
        return {}
    return {skill.stable_key: item_repo.get_items_with_skill_effect(skill.stable_key) for skill in skills}
