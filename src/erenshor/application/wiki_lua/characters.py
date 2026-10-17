"""Bounded character records composed from canonical copy-scoped facts."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from erenshor.application.processor.npc_rewards import initialized_reward
from erenshor.application.processor.npc_spawn import (
    PLAYER_LEVEL_CAP,
    SpawnConstants,
    armor_class,
    balanced_hp,
    class_mitigation,
    resist_range,
    start_levels,
    start_order,
    starts_before,
    training_dummy_level,
)
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.value_objects.item_provenance import is_actionable_acquisition
from erenshor.domain.value_objects.npc_level import npc_level_bounds
from erenshor.domain.value_objects.wiki_filename import picture_file_title

if TYPE_CHECKING:
    from erenshor.domain.entities.character import Character
    from erenshor.domain.value_objects.item_provenance import ItemAcquisition


class CharacterDataRepository(Protocol):
    def get_characters_for_wiki_generation(self) -> Sequence[Character]: ...
    def get_character_data_members(self, stable_key: str) -> Sequence[Character]: ...
    def get_character_data_abilities(self, stable_key: str) -> Sequence[dict[str, object]]: ...


_STATS = {
    "baseLevel": "level",
    "mana": "base_mana",
    "strength": "base_str",
    "endurance": "base_end",
    "dexterity": "base_dex",
    "agility": "base_agi",
    "intelligence": "base_int",
    "wisdom": "base_wis",
    "charisma": "base_cha",
    "resonance": "base_res",
    "health": "effective_hp",
    "ac": "effective_ac",
    "baseHealth": "base_hp",
    "baseArmorClass": "base_ac",
    "magicMin": "effective_min_mr",
    "magicMax": "effective_max_mr",
    "elementalMin": "effective_min_er",
    "elementalMax": "effective_max_er",
    "poisonMin": "effective_min_pr",
    "poisonMax": "effective_max_pr",
    "voidMin": "effective_min_vr",
    "voidMax": "effective_max_vr",
    "acPerPlayerLevel": "ac_per_player_level",
    "dummyRecordingAC": "test_dummy_hand_set_ac",
}
_REWARDS = {
    "baseExperience": "initialized_xp",
    "xpPerPlayerLevel": "xp_per_player_level",
    "multiplier": "effective_xp_multiplier",
    "designerMultiplier": "boss_xp_multiplier",
    "rawBaseMin": "base_xp_min",
    "rawBonusMax": "base_xp_max",
}


def _known_fields(character: Character, fields: Mapping[str, str]) -> dict[str, object]:
    return {key: value for key, attr in fields.items() if (value := getattr(character, attr)) is not None}


def _reference(key: str, catalog: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    if key not in catalog:
        raise ValueError(f"Character data references missing canonical identity {key!r}")
    entry = catalog[key]
    return {field: value for field in ("name", "page", "disposition") if (value := entry.get(field)) is not None} | {
        "key": key
    }


def character_stat_profiles(
    member: Character,
    locations: Sequence[Mapping[str, object]],
    constants: SpawnConstants,
    mitigations: Mapping[str, float],
) -> list[dict[str, object]]:
    """Initialize each placement and variance outcome before taking supported bounds."""
    if not member.has_stats or member.level is None or member.treasure_chest:
        return []
    order = start_order(
        member.start_components_listed,
        member.start_components_by_file_id,
        None if member.is_active_at_load is None else bool(member.is_active_at_load),
    )
    if not order:
        raise ValueError(f"{member.stable_key}: missing native component start inventory")
    player_levels: Sequence[int | None] = (
        tuple(range(1, PLAYER_LEVEL_CAP + 1))
        if "TestDummy" in order and training_dummy_level(member.level) is None
        else (None,)
    )
    profiles: list[dict[str, object]] = []
    for location in locations or ({},):
        modifier = location.get("levelMod", 0)
        if type(modifier) is not int:
            raise ValueError(f"{member.stable_key}: placement level modifier is not an integer")
        placed_level = member.level + modifier
        for player_level in player_levels:
            npc_input = placed_level
            if starts_before(order, "TestDummy", "NPC"):
                dummy_input = training_dummy_level(placed_level) or player_level
                if dummy_input is None:
                    raise ValueError(f"{member.stable_key}: missing dummy player level")
                npc_input = dummy_input
            low, high = (
                npc_level_bounds(npc_input, bool(member.group_encounter))
                if member.is_npc
                else (placed_level, placed_level)
            )
            outcomes: list[dict[str, int | float | None]] = []
            for rolled in range(low, high + 1):
                levels = start_levels(order, placed_level, player_level, npc_level=rolled)
                reward = initialized_reward(
                    order,
                    placed_level,
                    member.boss_xp_multiplier if member.boss_xp_multiplier is not None else 0,
                    player_level=player_level,
                    npc_level=rolled,
                )
                outcome: dict[str, int | float | None] = {
                    "level": levels.final,
                    "health": balanced_hp(member.base_hp, levels.npc, constants)
                    if member.base_hp is not None and member.is_npc
                    else member.effective_hp,
                    "ac": (
                        armor_class(
                            levels.final, member.hard_set_ac, class_mitigation(mitigations, member.class_resource_name)
                        )
                        if member.is_npc and member.hard_set_ac is not None
                        else member.effective_ac
                        if not member.is_npc
                        else None
                    ),
                    "experience": reward.base_experience,
                    "multiplier": reward.multiplier if member.boss_xp_multiplier is not None else None,
                }
                for label, attr in (
                    ("magic", "base_mr"),
                    ("elemental", "base_er"),
                    ("poison", "base_pr"),
                    ("void", "base_vr"),
                ):
                    value = getattr(member, attr)
                    minimum, maximum = (
                        resist_range(levels.stats)
                        if member.is_npc and not member.hand_set_resistances
                        else (value, value)
                    )
                    outcome[label + "Min"] = minimum
                    outcome[label + "Max"] = maximum
                outcomes.append(outcome)
            profile: dict[str, object] = {"memberKey": member.stable_key}
            if "id" in location:
                profile["locationId"] = location["id"]
            if player_level is not None:
                profile["playerLevel"] = player_level
            for field in ("level", "health", "ac", "experience", "multiplier"):
                values = [row[field] for row in outcomes]
                if all(value is not None for value in values):
                    known = [value for value in values if value is not None]
                    profile[field + "Min"] = min(known)
                    profile[field + "Max"] = max(known)
            for field in ("magic", "elemental", "poison", "void"):
                lows = [row[field + "Min"] for row in outcomes]
                highs = [row[field + "Max"] for row in outcomes]
                if all(value is not None for value in (*lows, *highs)):
                    profile[field + "Min"] = min(value for value in lows if value is not None)
                    profile[field + "Max"] = max(value for value in highs if value is not None)
            profiles.append(profile)
    return profiles


def build_character_records(
    repository: CharacterDataRepository,
    *,
    locations_by_character: Mapping[str, Sequence[Mapping[str, object]]],
    acquisitions_by_character: Mapping[str, Sequence[ItemAcquisition]],
    catalog: Mapping[str, Mapping[str, object]],
    class_labels: Mapping[str, Mapping[str, object]],
    constants: SpawnConstants,
    mitigations: Mapping[str, float],
    build: Mapping[str, object],
    guardian_keys: frozenset[str] = frozenset(),
    summoned_by_character: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    common_world_characters: frozenset[str] = frozenset(),
    lifecycle_by_character: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    """Compose supplied canonical relation slices without selecting loot or eligibility."""
    records: dict[str, dict[str, object]] = {}
    for representative in sorted(repository.get_characters_for_wiki_generation(), key=lambda row: row.stable_key):
        key = representative.stable_key
        if not key.startswith("character:") or key in records or representative.is_sim_player:
            raise ValueError(f"Invalid or duplicate ordinary character identity {key!r}")
        if not representative.wiki_page_name or not representative.display_name:
            raise ValueError(f"{key}: missing canonical article identity")
        members = sorted(repository.get_character_data_members(key), key=lambda member: member.stable_key)
        if not members or len({member.stable_key for member in members}) != len(members):
            raise ValueError(f"{key}: missing or duplicate fact-source membership")
        locations = sorted(
            (dict(location) for location in locations_by_character.get(key, ())),
            key=lambda location: str(location["id"]),
        )
        member_keys = sorted(member.stable_key for member in members)
        if any(location.get("memberKey") not in member_keys for location in locations):
            raise ValueError(f"{key}: a location has no supporting fact-source member")
        variants: list[dict[str, object]] = []
        for member in members:
            variant: dict[str, object] = {"memberKeys": [member.stable_key]}
            if member.class_resource_name is not None:
                variant["class"] = dict(
                    class_labels.get(member.class_resource_name, {"name": member.class_resource_name})
                ) | {"resourceName": member.class_resource_name}
            if member.my_world_faction_stable_key:
                variant["faction"] = _reference(member.my_world_faction_stable_key, catalog)
            if member.faction_modifiers:
                variant["factionChanges"] = [
                    _reference(modifier.faction_stable_key, catalog) | {"amount": modifier.modifier_value}
                    for modifier in member.faction_modifiers
                ]
            if member.has_stats and not representative.treasure_chest and key not in guardian_keys:
                variant["stats"] = _known_fields(member, _STATS) | {
                    "levelScalesWithPlayer": bool(member.level_scales_with_player)
                }
                variant["rewards"] = _known_fields(member, _REWARDS)
                variant["profiles"] = character_stat_profiles(
                    member,
                    [location for location in locations if location["memberKey"] == member.stable_key],
                    constants,
                    mitigations,
                )
            variants.append(variant)
        abilities_by_usage: dict[tuple[str, str, float | None], dict[str, object]] = {}
        for ability in repository.get_character_data_abilities(key):
            ability_key, usage = str(ability["ability_key"]), str(ability["usage"])
            member_key = str(ability["character_stable_key"])
            if member_key not in member_keys or not ability.get("name"):
                raise ValueError(f"{key}: ability relation has missing identity or member")
            chance = cast("float | None", ability.get("chance"))
            record = abilities_by_usage.setdefault(
                (ability_key, usage, chance),
                _reference(ability_key, catalog) | {"usage": usage, "memberKeys": []},
            )
            if chance is not None:
                record["chance"] = chance
            source_members = record["memberKeys"]
            if not isinstance(source_members, list):
                raise ValueError("Invalid ability member collection")
            if member_key not in source_members:
                source_members.append(member_key)
        loot: list[dict[str, object]] = []
        relation_keys: set[str] = set()
        for acquisition in acquisitions_by_character.get(key, ()):
            if acquisition.kind != "character_drop":
                raise ValueError(
                    f"{key}: canonical character loot slice contains non-character source {acquisition.kind!r}"
                )
            if acquisition.source_copy_stable_key not in member_keys:
                raise ValueError(f"{key}: canonical loot has no supporting fact-source copy")
            if acquisition.acquisition_key in relation_keys:
                raise ValueError(f"{key}: duplicate canonical loot relation {acquisition.acquisition_key}")
            relation_keys.add(acquisition.acquisition_key)
            item = _reference(acquisition.item_stable_key, catalog)
            disposition = item.get("disposition")
            if (
                not isinstance(disposition, Mapping)
                or disposition.get("item_stable_key") != acquisition.item_stable_key
            ):
                raise ValueError(f"{key}: missing or mismatched canonical item disposition")
            if disposition.get("disposition") not in ("current", "removed", "unobtainable", "unused"):
                raise ValueError(f"{key}: unsupported canonical item disposition")
            loot.append(
                asdict(acquisition)
                | {
                    "item": item,
                    "actionable": disposition["disposition"] == "current" and is_actionable_acquisition(acquisition),
                }
            )
        records[key] = {
            "stableKey": key,
            "name": representative.display_name,
            "page": representative.wiki_page_name,
            "memberKeys": member_keys,
            "tier": representative.encounter_tier,
            "isVendor": bool(representative.is_vendor),
            "hasStats": any(member.has_stats for member in members),
            "isSummon": bool(representative.is_summon or (summoned_by_character or {}).get(key)),
            "scalingGuardian": key in guardian_keys,
            "pictures": {
                "render": picture_file_title("render", representative.image_name, representative.display_name),
                "screenshot": picture_file_title("screenshot", representative.image_name, representative.display_name),
            },
            "variants": variants,
            "abilities": [
                abilities_by_usage[identity]
                for identity in sorted(abilities_by_usage, key=lambda value: (value[0], value[1], str(value[2])))
            ],
            "locations": locations,
            "loot": sorted(loot, key=lambda relation: str(relation["acquisition_key"])),
            "summonedBy": list((summoned_by_character or {}).get(key, ())),
            "commonWorldDrops": key in common_world_characters,
            "build": dict(build),
        }
        for field in ("faction", "factionChanges"):
            values = [variant.get(field) for variant in variants]
            if values[0] is not None and all(value == values[0] for value in values):
                records[key][field] = values[0]
        if lifecycle_by_character and key in lifecycle_by_character:
            records[key]["lifecycle"] = dict(lifecycle_by_character[key])
    return records


def character_module_texts(records: Mapping[str, Mapping[str, object]], max_page_bytes: int) -> dict[str, str]:
    """Split stable hash buckets before returning any publication bytes."""
    if max_page_bytes <= 0:
        raise ValueError("Character module byte limit must be positive")
    grouped: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
    for key, record in sorted(records.items()):
        if not key.startswith("character:") or record.get("stableKey") != key:
            raise ValueError(f"Invalid character shard identity {key!r}")
        grouped[hashlib.sha256(key.encode()).hexdigest()[:2]][key] = record
    modules: dict[str, str] = {}
    by_key: dict[str, object] = {}
    pending = sorted(grouped.items())
    while pending:
        bucket, rows = pending.pop()
        text = module_text(dict(rows))
        if len(text.encode()) > max_page_bytes:
            if len(rows) == 1 or len(bucket) == 64:
                raise ValueError(f"Character record cannot fit page byte limit: {next(iter(rows))}")
            children: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
            for key, record in rows.items():
                children[hashlib.sha256(key.encode()).hexdigest()[: len(bucket) + 1]][key] = record
            pending.extend(sorted(children.items()))
            continue
        modules["Characters/" + bucket] = text
        for key, record in rows.items():
            for supported in (key, *cast("Sequence[object]", record.get("memberKeys", ()))):
                if not isinstance(supported, str) or not supported.startswith("character:"):
                    raise ValueError(f"Invalid supported character identity {supported!r}")
                target = {"key": key, "shard": bucket}
                if supported in by_key and by_key[supported] != target:
                    raise ValueError(f"Character member belongs to multiple representatives: {supported}")
                by_key[supported] = target
    modules["Characters"] = module_text({"schemaVersion": 1, "byKey": by_key})
    for title, text in modules.items():
        if len(text.encode()) > max_page_bytes:
            raise ValueError(f"Module:Erenshor/Data/{title} exceeds {max_page_bytes} bytes")
    return dict(sorted(modules.items()))


def write_characters_modules(
    records: Mapping[str, Mapping[str, object]],
    output_root: Path,
    *,
    max_page_bytes: int,
) -> list[Path]:
    """Write only after every shard and index passes the configured byte limit."""
    modules = character_module_texts(records, max_page_bytes)
    paths: list[Path] = []
    for title, text in modules.items():
        path = output_root / "Erenshor" / "Data" / (title + ".lua")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths
