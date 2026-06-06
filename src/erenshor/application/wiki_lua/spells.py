"""Generate a compact Lua data module for spell wiki pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.links import link_refs
from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.spell import Spell
    from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink, WikiLink

LuaData = dict[str, object]

_TEXT_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("image", "image_name"),
    ("description", "spell_desc"),
    ("specialDescriptor", "special_descriptor"),
    ("type", "type"),
    ("line", "line"),
    ("damageType", "damage_type"),
    ("addProcStableKey", "add_proc_stable_key"),
    ("petToSummonStableKey", "pet_to_summon_stable_key"),
    ("statusEffectStableKey", "status_effect_to_apply_stable_key"),
    ("statusEffectMessageOnPlayer", "status_effect_message_on_player"),
    ("statusEffectMessageOnNpc", "status_effect_message_on_npc"),
)

_NUMBER_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("requiredLevel", "required_level"),
    ("manaCost", "mana_cost"),
    ("aggro", "aggro"),
    ("castTimeTicks", "spell_charge_time"),
    ("cooldownSeconds", "cooldown"),
    ("durationTicks", "spell_duration_in_ticks"),
    ("range", "spell_range"),
    ("maxLevelTarget", "max_level_target"),
    ("targetDamage", "target_damage"),
    ("targetHealing", "target_healing"),
    ("casterHealing", "caster_healing"),
    ("shieldAmount", "shielding_amt"),
    ("resistModifier", "resist_modifier"),
    ("addProcChance", "add_proc_chance"),
    ("hp", "hp"),
    ("ac", "ac"),
    ("mana", "mana"),
    ("percentManaRestoration", "percent_mana_restoration"),
    ("movementSpeed", "movement_speed"),
    ("str", "str_"),
    ("dex", "dex"),
    ("end", "end_"),
    ("agi", "agi"),
    ("wis", "wis"),
    ("int", "int_"),
    ("cha", "cha"),
    ("mr", "mr"),
    ("er", "er"),
    ("pr", "pr"),
    ("vr", "vr"),
    ("damageShield", "damage_shield"),
    ("haste", "haste"),
    ("lifesteal", "percent_lifesteal"),
    ("atkRollModifier", "atk_roll_modifier"),
    ("bleedDamagePercent", "bleed_damage_percent"),
    ("resonance", "resonate_chance"),
    ("xpBonus", "xp_bonus"),
)

_BOOL_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("simUsable", "sim_usable"),
    ("unstableDuration", "unstable_duration"),
    ("instantEffect", "instant_effect"),
    ("selfOnly", "self_only"),
    ("groupEffect", "group_effect"),
    ("canHitPlayers", "can_hit_players"),
    ("applyToCaster", "apply_to_caster"),
    ("inflictOnSelf", "inflict_on_self"),
    ("lifetap", "lifetap"),
    ("root", "root_target"),
    ("stun", "stun_target"),
    ("charm", "charm_target"),
    ("fear", "fear_target"),
    ("crowdControl", "crowd_control_spell"),
    ("breakOnDamage", "break_on_damage"),
    ("breakOnAnyAction", "break_on_any_action"),
    ("taunt", "taunt_spell"),
    ("reapAndRenew", "reap_and_renew"),
    ("automateAttack", "automate_attack"),
    ("wornEffect", "worn_effect"),
    ("grantInvisibility", "grant_invisibility"),
    ("cannotInterrupt", "cannot_interrupt"),
    ("jolt", "jolt_spell"),
    ("noResonate", "no_resonate"),
)


class SpellDataRepository(Protocol):
    """Repository methods needed to build the spell data module."""

    def get_spells_for_wiki_generation(self) -> list[Spell]: ...

    def get_spell_classes(self, stable_key: str) -> list[str]: ...


class SpellRelationshipItemRepository(Protocol):
    """Item repository methods needed for spell relationship fields."""

    def get_obtainable_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]: ...

    def get_items_with_spell_effect(self, spell_stable_key: str) -> list[ItemLink]: ...


class SpellRelationshipCharacterRepository(Protocol):
    """Character repository methods needed for spell relationship fields."""

    def get_characters_using_spell(self, spell_stable_key: str) -> list[CharacterLink]: ...


def generate_spells_module(
    spell_repo: SpellDataRepository,
    item_repo: SpellRelationshipItemRepository | None = None,
    character_repo: SpellRelationshipCharacterRepository | None = None,
) -> str:
    """Generate `Module:Erenshor/Data/Spells` from clean DB repositories."""
    spells = spell_repo.get_spells_for_wiki_generation()
    classes = {spell.stable_key: spell_repo.get_spell_classes(spell.stable_key) for spell in spells}
    return module_text(
        build_spells_data(
            spells,
            classes,
            teaching_items_by_spell=_teaching_items_by_spell(spells, item_repo),
            items_with_effect_by_spell=_items_with_effect_by_spell(spells, item_repo),
            used_by_by_spell=_used_by_by_spell(spells, character_repo),
        )
    )


def write_spells_module(
    spell_repo: SpellDataRepository,
    output_root: Path,
    item_repo: SpellRelationshipItemRepository | None = None,
    character_repo: SpellRelationshipCharacterRepository | None = None,
) -> Path:
    """Write the generated spell data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Spells.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_spells_module(spell_repo, item_repo, character_repo), encoding="utf-8")
    return output_path


def build_spells_data(
    spells: Iterable[Spell],
    classes_by_spell: Mapping[str, Iterable[str]],
    teaching_items_by_spell: Mapping[str, Iterable[ItemLink]] | None = None,
    items_with_effect_by_spell: Mapping[str, Iterable[ItemLink]] | None = None,
    used_by_by_spell: Mapping[str, Iterable[CharacterLink]] | None = None,
) -> LuaData:
    """Build the serializable spell data table for `mw.loadData()`."""
    rows: dict[str, LuaData] = {}
    for spell in sorted(spells, key=lambda candidate: candidate.stable_key):
        record = _spell_record(
            spell,
            classes_by_spell.get(spell.stable_key, ()),
            teaching_items=(
                teaching_items_by_spell.get(spell.stable_key, ()) if teaching_items_by_spell is not None else ()
            ),
            items_with_effect=(
                items_with_effect_by_spell.get(spell.stable_key, ()) if items_with_effect_by_spell is not None else ()
            ),
            used_by=used_by_by_spell.get(spell.stable_key, ()) if used_by_by_spell is not None else (),
        )
        if record is not None:
            rows[spell.stable_key] = record
    return {"spells": rows}


def _spell_record(
    spell: Spell,
    classes: Iterable[str],
    teaching_items: Iterable[ItemLink] = (),
    items_with_effect: Iterable[ItemLink] = (),
    used_by: Iterable[CharacterLink] = (),
) -> LuaData | None:
    name = spell.display_name or spell.spell_name or spell.wiki_page_name
    page = spell.wiki_page_name or name
    if name is None or page is None:
        return None

    record: LuaData = {"name": name, "page": page, "classes": sorted(classes, key=str.casefold)}
    for lua_key, attr in _TEXT_FIELD_MAP:
        _put_text(record, lua_key, getattr(spell, attr))
    for lua_key, attr in _NUMBER_FIELD_MAP:
        _put_number(record, lua_key, getattr(spell, attr))
    for lua_key, attr in _BOOL_FIELD_MAP:
        _put_bool(record, lua_key, getattr(spell, attr))
    _put_list(record, "source", _link_list(teaching_items, "item"))
    _put_list(record, "itemsWithEffect", _link_list(items_with_effect, "item"))
    _put_list(record, "usedBy", _link_list(used_by, "character"))
    return record


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


def _link_list(links: Iterable[WikiLink], kind: str | None = None) -> list[LuaData]:
    return link_refs(links, kind)


def _teaching_items_by_spell(
    spells: Iterable[Spell], item_repo: SpellRelationshipItemRepository | None
) -> dict[str, list[ItemLink]]:
    if item_repo is None:
        return {}
    return {spell.stable_key: item_repo.get_obtainable_items_that_teach_spell(spell.stable_key) for spell in spells}


def _items_with_effect_by_spell(
    spells: Iterable[Spell], item_repo: SpellRelationshipItemRepository | None
) -> dict[str, list[ItemLink]]:
    if item_repo is None:
        return {}
    return {spell.stable_key: item_repo.get_items_with_spell_effect(spell.stable_key) for spell in spells}


def _used_by_by_spell(
    spells: Iterable[Spell], character_repo: SpellRelationshipCharacterRepository | None
) -> dict[str, list[CharacterLink]]:
    if character_repo is None:
        return {}
    return {spell.stable_key: character_repo.get_characters_using_spell(spell.stable_key) for spell in spells}
