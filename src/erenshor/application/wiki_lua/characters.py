"""Generate compact Lua data modules for character wiki pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.links import link_ref, link_refs
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.value_objects.wiki_link import FactionLink

if TYPE_CHECKING:
    from erenshor.domain.entities.character import Character
    from erenshor.domain.value_objects.faction import FactionModifier
    from erenshor.domain.value_objects.loot import LootDropInfo
    from erenshor.domain.value_objects.spawn import CharacterSpawnInfo, CharacterSpawnRow
    from erenshor.domain.value_objects.wiki_link import AbilityLink, CharacterAbilityUsage

LuaData = dict[str, object]


class CharacterDataRepository(Protocol):
    """Repository methods needed to build the character data module."""

    def get_characters_for_wiki_generation(self) -> list[Character]: ...


class CharacterSpawnRepository(Protocol):
    """Spawn lookup needed for character wiki data."""

    def get_spawn_info_for_character(self, stable_key: str, /) -> list[CharacterSpawnInfo]: ...

    def get_cargo_spawn_rows_for_character(self, stable_key: str, /) -> list[CharacterSpawnRow]: ...


class CharacterLootRepository(Protocol):
    """Loot lookup needed for character wiki data."""

    def get_loot_for_character(self, stable_key: str, /) -> list[LootDropInfo]: ...


class CharacterSpellRepository(Protocol):
    """Spell lookup needed for character wiki data."""

    def get_spells_used_by_character(self, stable_key: str, /) -> list[AbilityLink]: ...

    def get_character_ability_usages(self, stable_key: str, /) -> list[CharacterAbilityUsage]: ...


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
    ("baseArmorPenPercentage", "base_armor_pen_percentage"),
    ("baseAttackRollModifier", "base_attack_roll_modifier"),
    ("cannotBeSnared", "cannot_be_snared"),
    ("canNeverSeeInvis", "can_never_see_invis"),
    ("dpsDummy", "dps_dummy"),
    ("isWyrm", "is_wyrm"),
    ("noRun", "no_run"),
    ("neverAggro", "never_aggro"),
    ("noDmgCap", "no_dmg_cap"),
    ("canPhantomStrike", "can_phantom_strike"),
    ("noSelfHeal", "no_self_heal"),
    ("aggroRegardlessOfLOS", "aggro_regardless_of_los"),
    ("ignoreLOSForAggro", "ignore_los_for_aggro"),
    ("simPlayersIgnoreUntilOrdered", "sim_players_ignore_until_ordered"),
    ("enrage", "enrage"),
    ("spawnWithStatus", "spawn_with_status_stable_key"),
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
    spawn_rows = {
        character.stable_key: spawn_repo.get_cargo_spawn_rows_for_character(character.stable_key)
        for character in characters
    }
    ability_usages = {
        character.stable_key: spell_repo.get_character_ability_usages(character.stable_key) for character in characters
    }
    return module_text(build_characters_data(characters, spawn_infos, loot, spells, spawn_rows, ability_usages))


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
    spawn_rows_by_character: Mapping[str, list[CharacterSpawnRow]],
    ability_usages_by_character: Mapping[str, list[CharacterAbilityUsage]],
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
            spawn_rows=spawn_rows_by_character.get(character.stable_key, []),
            ability_usages=ability_usages_by_character.get(character.stable_key, []),
        )

    return {"characters": character_rows}


def _character_record(
    character: Character,
    spawn_infos: list[CharacterSpawnInfo],
    loot_drops: list[LootDropInfo],
    spells: list[AbilityLink],
    spawn_rows: list[CharacterSpawnRow],
    ability_usages: list[CharacterAbilityUsage],
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
    _put(row, "spawnType", _format_spawn_type(spawn_infos))
    _put(row, "respawn", _format_respawn(spawn_infos))
    _put(row, "dropRates", _format_drop_rates(loot_drops))
    _put(row, "spells", _format_ability_links(spells))
    _put(row, "spawns", _format_spawn_rows(spawn_rows))
    _put(row, "abilities", _format_ability_usages(ability_usages))
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


def _format_faction(character: Character) -> LuaData | str:
    display_name = character.my_world_faction_display_name
    if not display_name:
        return ""
    page_name = character.my_world_faction_wiki_page_name
    if not page_name:
        return display_name
    ref = link_ref(
        FactionLink(
            page_title=page_name,
            display_name=display_name,
            stable_key=character.my_world_faction_stable_key,
        ),
        "faction",
    )
    if ref is None:
        return display_name
    return ref


def _format_faction_modifiers(faction_modifiers: list[FactionModifier]) -> list[LuaData]:
    entries: list[tuple[tuple[str, str, int], LuaData]] = []
    for modifier in faction_modifiers:
        display = modifier.faction_display_name
        page = modifier.faction_wiki_page_name
        ref = None
        if page is not None:
            ref = link_ref(
                FactionLink(
                    page_title=page,
                    display_name=display,
                    stable_key=modifier.faction_stable_key,
                ),
                "faction",
            )
        if ref is None:
            ref = {"kind": "page", "page": display, "text": display}
        entries.append(
            (
                (display.casefold(), modifier.faction_stable_key, modifier.modifier_value),
                {"link": ref, "modifier": modifier.modifier_value},
            )
        )
    return [entry for _, entry in sorted(entries)]


def _format_zones(spawn_infos: list[CharacterSpawnInfo]) -> list[LuaData]:
    seen: dict[str, LuaData] = {}
    for info in spawn_infos:
        ref = link_ref(info.zone_link, "zone")
        if ref is not None:
            seen.setdefault(info.zone_link.display_name, ref)
    return [seen[name] for name in sorted(seen, key=str.lower)]


def _format_coordinates(spawn_infos: list[CharacterSpawnInfo]) -> str:
    unique_coords = {
        (info.x, info.y, info.z)
        for info in spawn_infos
        if info.x is not None and info.y is not None and info.z is not None
    }
    ordinary_coords = {
        (info.x, info.y, info.z)
        for info in spawn_infos
        if info.source_script is None and info.x is not None and info.y is not None and info.z is not None
    }
    coords = unique_coords if len(unique_coords) == 1 else ordinary_coords
    if len(coords) == 1:
        x, y, z = next(iter(coords))
        return f"{x:.1f} x {y:.1f} x {z:.1f}"
    if unique_coords and all(info.source_script is not None for info in spawn_infos):
        return "<br>".join(f"{x:.1f} x {y:.1f} x {z:.1f}" for x, y, z in sorted(unique_coords))
    return ""


def _format_spawn_chance(spawn_infos: list[CharacterSpawnInfo]) -> str:
    if not spawn_infos or not any(info.is_rare or info.is_unique for info in spawn_infos):
        return ""
    by_zone: dict[str, list[float]] = {}
    for info in spawn_infos:
        if info.spawn_chance is None:
            continue
        by_zone.setdefault(info.zone_link.display_name, []).append(info.spawn_chance)
    if not by_zone:
        return ""
    if all(chance == 100.0 for chances in by_zone.values() for chance in chances):
        return ""
    out: list[str] = []
    for zone in sorted(by_zone):
        zone_chances = by_zone[zone]
        min_chance = min(zone_chances)
        max_chance = max(zone_chances)
        text = f"{round(min_chance)}%" if min_chance == max_chance else f"{round(min_chance)}-{round(max_chance)}%"
        out.append(f"{text} ({zone})" if len(by_zone) > 1 else text)
    return "<br>".join(out)


def _format_spawn_type(spawn_infos: list[CharacterSpawnInfo]) -> str:
    has_dynamic = any(info.source_script is not None for info in spawn_infos)
    has_ordinary = any(info.source_script is None for info in spawn_infos)
    if has_dynamic and not has_ordinary:
        return "Dynamic event spawn"
    return ""


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


def _format_spawn_rows(spawn_rows: list[CharacterSpawnRow]) -> list[LuaData]:
    rows: list[LuaData] = []
    for spawn in spawn_rows:
        row: LuaData = {
            "zone": spawn.zone,
            "scene": spawn.scene,
            "x": spawn.x,
            "y": spawn.y,
            "z": spawn.z,
            "spawnChance": spawn.spawn_chance,
            "nightSpawn": spawn.night_spawn,
            "spawnUponQuestComplete": spawn.spawn_upon_quest_complete,
            "levelMod": spawn.level_mod,
            "rareNpcChance": spawn.rare_npc_chance,
            "spawnType": spawn.spawn_type,
            "origin": spawn.origin,
        }
        rows.append({key: value for key, value in row.items() if value is not None})
    return rows


def _format_ability_usages(usages: list[CharacterAbilityUsage]) -> list[LuaData]:
    return [{"ability": usage.ability_key, "usage": usage.usage} for usage in usages]


def _format_drop_rates(loot_drops: list[LootDropInfo]) -> list[LuaData]:
    """One entry per loot drop, connected to the item by StableKey.

    Each entry carries only drop-edge facts: the dropped item's StableKey (the
    canonical connection, consumed both by the Cargo ``Drops`` store and by the
    infobox, which resolves the item's link and uniqueness at render time), the
    drop probability, and the guaranteed-pool / visible-equipped flags. Order is
    set by the repository query (probability desc, then item name); the infobox
    derives both the "Overall Drop Rates" and "Guaranteed One Of" rows from this
    single list.
    """
    out: list[LuaData] = []
    for drop in loot_drops:
        entry: LuaData = {"item": drop.item_stable_key, "probability": drop.drop_probability}
        # code-fact: loot.guarantee_one_drop
        if drop.is_guaranteed:
            entry["guaranteed"] = True
        if drop.is_visible:
            entry["visible"] = True
        out.append(entry)
    return out


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


def _format_ability_links(spells: list[AbilityLink]) -> list[LuaData]:
    return link_refs(spells, "ability")


def _map_selector(character_type: object, display_name: str) -> str:
    prefix = "npc" if character_type == "NPC" else "enemy"
    return f"{prefix}:{display_name}"


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value not in ("", []):
        row[key] = value
