"""Generate compact Lua data modules for character wiki pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.character import Character
    from erenshor.domain.value_objects.faction import FactionModifier
    from erenshor.domain.value_objects.loot import LootDropInfo
    from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
    from erenshor.domain.value_objects.wiki_link import AbilityLink

LuaData = dict[str, object]


class CharacterDataRepository(Protocol):
    """Repository methods needed to build the character data module."""

    def get_characters_for_wiki_generation(self) -> list[Character]: ...


class CharacterSpawnRepository(Protocol):
    """Spawn lookup needed for character wiki data."""

    def get_spawn_info_for_character(self, stable_key: str) -> list[CharacterSpawnInfo]: ...


class CharacterLootRepository(Protocol):
    """Loot lookup needed for character wiki data."""

    def get_loot_for_character(self, stable_key: str) -> list[LootDropInfo]: ...


class CharacterSpellRepository(Protocol):
    """Spell lookup needed for character wiki data."""

    def get_spells_used_by_character(self, stable_key: str) -> list[AbilityLink]: ...


_CHARACTER_FIELD_MAP = (
    ("name", "display_name"),
    ("page", "wiki_page_name"),
    ("image", "image_name"),
    ("level", "level"),
    ("mana", "base_mana"),
    ("health", "effective_hp"),
    ("ac", "effective_ac"),
    ("strength", "base_str"),
    ("endurance", "base_end"),
    ("dexterity", "base_dex"),
    ("agility", "base_agi"),
    ("intelligence", "base_int"),
    ("wisdom", "base_wis"),
    ("charisma", "base_cha"),
)


def generate_characters_module(
    character_repo: CharacterDataRepository,
    spawn_repo: CharacterSpawnRepository,
    loot_repo: CharacterLootRepository,
    spell_repo: CharacterSpellRepository,
) -> str:
    """Generate `Module:Erenshor/Data/Characters` content from clean DB repositories."""
    characters = character_repo.get_characters_for_wiki_generation()
    spawn_infos = {
        character.stable_key: spawn_repo.get_spawn_info_for_character(character.stable_key) for character in characters
    }
    loot = {character.stable_key: loot_repo.get_loot_for_character(character.stable_key) for character in characters}
    spells = {
        character.stable_key: spell_repo.get_spells_used_by_character(character.stable_key) for character in characters
    }
    return module_text(build_characters_data(characters, spawn_infos, loot, spells))


def write_characters_module(
    character_repo: CharacterDataRepository,
    spawn_repo: CharacterSpawnRepository,
    loot_repo: CharacterLootRepository,
    spell_repo: CharacterSpellRepository,
    output_root: Path,
) -> Path:
    """Write the generated character data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Characters.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        generate_characters_module(character_repo, spawn_repo, loot_repo, spell_repo), encoding="utf-8"
    )
    return output_path


def build_characters_data(
    characters: Iterable[Character],
    spawn_infos_by_character: Mapping[str, list[CharacterSpawnInfo]],
    loot_by_character: Mapping[str, list[LootDropInfo]],
    spells_by_character: Mapping[str, list[AbilityLink]],
) -> LuaData:
    """Build the serializable character data table for `mw.loadData()`."""
    character_rows: dict[str, object] = {}

    for character in sorted(characters, key=lambda candidate: candidate.stable_key):
        page = character.wiki_page_name
        if page is None:
            continue
        character_rows[character.stable_key] = _character_record(
            character=character,
            spawn_infos=spawn_infos_by_character.get(character.stable_key, []),
            loot_drops=loot_by_character.get(character.stable_key, []),
            spells=spells_by_character.get(character.stable_key, []),
        )

    return {"characters": character_rows}


def _character_record(
    character: Character,
    spawn_infos: list[CharacterSpawnInfo],
    loot_drops: list[LootDropInfo],
    spells: list[AbilityLink],
) -> LuaData:
    row: LuaData = {}
    for lua_name, attr_name in _CHARACTER_FIELD_MAP:
        _put(row, lua_name, getattr(character, attr_name))

    display_name = character.display_name or character.npc_name or ""
    row["type"] = _character_type(character)
    _put(row, "faction", _format_faction(character))
    _put(row, "factionChange", _format_faction_modifiers(character.faction_modifiers or []))
    _put(row, "zones", _format_zones(spawn_infos))
    _put(row, "coordinates", _format_coordinates(spawn_infos))
    _put(row, "spawnChance", _format_spawn_chance(spawn_infos))
    _put(row, "respawn", _format_respawn(spawn_infos))
    _put(row, "guaranteedDrops", _format_guaranteed_drops(loot_drops))
    _put(row, "dropRates", _format_drop_rates(loot_drops, display_name))
    _put(row, "spells", _format_ability_links(spells))
    _put(row, "levelModMin", _level_mod_range(spawn_infos)[0])
    _put(row, "levelModMax", _level_mod_range(spawn_infos)[1])
    _put(row, "levelVarianceMin", 0 if character.group_encounter else -1)
    _put(row, "levelVarianceMax", 0 if character.group_encounter else 1)
    _put(row, "xpMultiplier", _xp_multiplier(character))
    _put(
        row,
        "magic",
        _format_resistance(
            character.base_mr, character.effective_min_mr, character.effective_max_mr, character.hand_set_resistances
        ),
    )
    _put(
        row,
        "poison",
        _format_resistance(
            character.base_pr, character.effective_min_pr, character.effective_max_pr, character.hand_set_resistances
        ),
    )
    _put(
        row,
        "elemental",
        _format_resistance(
            character.base_er, character.effective_min_er, character.effective_max_er, character.hand_set_resistances
        ),
    )
    _put(
        row,
        "void",
        _format_resistance(
            character.base_vr, character.effective_min_vr, character.effective_max_vr, character.hand_set_resistances
        ),
    )
    _put(row, "mapSelector", _map_selector(row["type"], display_name))
    row["hasDrops"] = bool(row.get("dropRates"))
    row["hasSpells"] = bool(row.get("spells"))
    return row


def _character_type(character: Character) -> str:
    if character.is_friendly:
        return "NPC"
    if character.is_unique:
        return "Boss"
    if character.is_rare and not character.is_common:
        return "Rare"
    return "Enemy"


def _format_faction(character: Character) -> str:
    display_name = character.my_world_faction_display_name
    if not display_name:
        return ""
    page_name = character.my_world_faction_wiki_page_name
    if not page_name:
        return display_name
    if page_name == display_name:
        return f"[[{page_name}]]"
    return f"[[{page_name}|{display_name}]]"


def _format_faction_modifiers(faction_modifiers: list[FactionModifier]) -> str:
    entries: list[tuple[str, str]] = []
    for modifier in faction_modifiers:
        display = modifier.faction_display_name
        page = modifier.faction_wiki_page_name
        if page is None:
            link = display
        elif page == display:
            link = f"[[{page}]]"
        else:
            link = f"[[{page}|{display}]]"
        sign = "+" if modifier.modifier_value > 0 else ""
        entries.append((display.lower(), f"{link} {sign}{modifier.modifier_value}"))
    return "<br>".join(line for _, line in sorted(entries))


def _format_zones(spawn_infos: list[CharacterSpawnInfo]) -> str:
    seen: dict[str, str] = {}
    for info in spawn_infos:
        seen.setdefault(info.zone_link.display_name, str(info.zone_link))
    return "<br>".join(seen[name] for name in sorted(seen, key=str.lower))


def _format_coordinates(spawn_infos: list[CharacterSpawnInfo]) -> str:
    unique_coords = {
        (info.x, info.y, info.z)
        for info in spawn_infos
        if info.x is not None and info.y is not None and info.z is not None
    }
    if len(unique_coords) != 1:
        return ""
    x, y, z = next(iter(unique_coords))
    return f"{x:.1f} x {y:.1f} x {z:.1f}"


def _format_spawn_chance(spawn_infos: list[CharacterSpawnInfo]) -> str:
    if not spawn_infos or not any(info.is_rare or info.is_unique for info in spawn_infos):
        return ""
    chances = [info.spawn_chance for info in spawn_infos]
    if all(chance == 100.0 for chance in chances):
        return ""
    by_zone: dict[str, list[float]] = {}
    for info in spawn_infos:
        by_zone.setdefault(info.zone_link.display_name, []).append(info.spawn_chance)
    out: list[str] = []
    for zone in sorted(by_zone):
        zone_chances = by_zone[zone]
        min_chance = min(zone_chances)
        max_chance = max(zone_chances)
        text = f"{round(min_chance)}%" if min_chance == max_chance else f"{round(min_chance)}-{round(max_chance)}%"
        out.append(f"{text} ({zone})" if len(by_zone) > 1 else text)
    return "<br>".join(out)


def _format_respawn(spawn_infos: list[CharacterSpawnInfo]) -> str:
    by_zone: dict[str, list[int]] = {}
    for info in spawn_infos:
        if info.base_respawn is None:
            continue
        by_zone.setdefault(info.zone_link.display_name, []).append(round(info.base_respawn / 60.0))
    if not by_zone:
        return ""
    entries: list[tuple[str, str]] = []
    for zone in sorted(by_zone):
        minutes = by_zone[zone]
        minimum = min(minutes)
        maximum = max(minutes)
        time_text = _minutes_to_duration(minimum) if minimum == maximum else f"{minimum}-{maximum} minutes"
        entries.append((zone, time_text))
    if len(entries) == 1:
        return entries[0][1]
    unique_times = {time_text for _, time_text in entries}
    if len(unique_times) == 1:
        return entries[0][1]
    return "<br>".join(f"{time_text} ({zone})" for zone, time_text in entries)


def _minutes_to_duration(minutes: int) -> str:
    if minutes <= 0:
        return ""
    if minutes == 1:
        return "1 minute"
    return f"{minutes} minutes"


def _format_guaranteed_drops(loot_drops: list[LootDropInfo]) -> str:
    entries = sorted({str(drop.item_link) for drop in loot_drops if drop.is_guaranteed and drop.drop_probability > 0})
    if len(entries) < 2:
        return ""
    return "<br>".join(entries)


def _format_drop_rates(loot_drops: list[LootDropInfo], character_display_name: str) -> str:
    entries: list[tuple[tuple[float, str], str]] = []
    for drop in loot_drops:
        if drop.item_link.page_title is None or drop.drop_probability <= 0:
            continue
        entry = f"{drop.item_link} ({drop.drop_probability:.1f}%)"
        refs: list[str] = []
        if drop.is_visible:
            refs.append(
                f"<ref>If {character_display_name} has {drop.item_link} equipped, it is guaranteed to drop.</ref>"
            )
        if drop.item_unique:
            refs.append(
                f"<ref>If the player is already holding {drop.item_link} in their inventory, "
                "another will not drop.</ref>"
            )
        if refs:
            entry += "".join(refs)
        entries.append(((-drop.drop_probability, drop.item_link.display_name.lower()), entry))
    seen: set[str] = set()
    out: list[str] = []
    for _, entry in sorted(entries):
        if entry not in seen:
            seen.add(entry)
            out.append(entry)
    return "<br>".join(out)


def _level_mod_range(spawn_infos: list[CharacterSpawnInfo]) -> tuple[int, int]:
    if not spawn_infos:
        return (0, 0)
    level_mods = [info.level_mod for info in spawn_infos]
    return (min(level_mods), max(level_mods))


def _xp_multiplier(character: Character) -> float:
    if not character.boss_xp_multiplier:
        return 1.0
    return character.boss_xp_multiplier


def _format_resistance(
    base_value: int | None, min_value: int | None, max_value: int | None, hand_set: int | None
) -> str:
    if hand_set:
        return "" if base_value is None else str(base_value)
    minimum = min_value or 0
    maximum = max_value or 0
    return f"{minimum}-{maximum}" if minimum != maximum else str(minimum)


def _format_ability_links(spells: list[AbilityLink]) -> str:
    visible = sorted((spell for spell in spells if spell.page_title is not None), key=lambda spell: spell.display_name)
    return "<br>".join(str(spell) for spell in visible)


def _map_selector(character_type: object, display_name: str) -> str:
    prefix = "npc" if character_type == "NPC" else "enemy"
    return f"{prefix}:{display_name}"


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value
