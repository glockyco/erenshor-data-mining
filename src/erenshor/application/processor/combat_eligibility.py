"""Derive combat eligibility for actual exported character copies.

Dedup groups are presentation identities, not interchangeable game objects.
Release evidence therefore never crosses a character stable key. Ward controllers
are solved to a least fixed point so an immune dependency cycle cannot unlock
itself merely because each member has a controller.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .writer import Writer


# Exporter and producer share this closed contract. A new shipped release
# branch needs an explicit producer decision rather than implicit acceptance.
_SCRIPT_MECHANISMS = frozenset(
    {
        "npc_protector_null",
        "npc_protector_inactive",
        "npc_protector_weather",
        "health_phase_timer",
        "spawn_health_phase_timer",
        "combat_ward_cycle",
        "combat_empty_wards",
        "trade_turn_in",
    }
)


@dataclass(frozen=True)
class _Release:
    character: str
    mechanism: str
    source: str
    conditions: tuple[tuple[str, str], ...]
    can_release: bool
    enabled: bool
    # Each dependency is a set of possible characters at one required source.
    dependencies: tuple[frozenset[str], ...] = ()


def _rows(raw: sqlite3.Connection, table: str, columns: str) -> list[sqlite3.Row]:
    try:
        return raw.execute(f"SELECT {columns} FROM {table}").fetchall()
    except sqlite3.Error as exc:
        raise ValueError(f"Missing combat eligibility export contract: {table} ({columns})") from exc


def _flag(value: object, context: str) -> bool:
    if value not in (0, 1):
        raise ValueError(f"Invalid combat eligibility boolean for {context}: {value!r}")
    return bool(value)


def _key(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing combat eligibility identity: {context}")
    return value


def _script_releases(raw: sqlite3.Connection, characters: set[str]) -> list[_Release]:
    groups: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in _rows(
        raw,
        "CharacterDamageReleaseRules",
        "RuleKey, CharacterStableKey, Mechanism, SourceStableKey, ConditionKind, "
        "ConditionStableKey, CanRelease, ControllerEnabled",
    ):
        character = _key(row["CharacterStableKey"], "release character")
        mechanism = _key(row["Mechanism"], "release mechanism")
        if mechanism not in _SCRIPT_MECHANISMS:
            raise ValueError(f"Unknown combat eligibility mechanism: {mechanism}")
        if character not in characters:
            raise ValueError(f"Damage release references unknown raw character: {character}")
        source = _key(row["SourceStableKey"], "release source")
        _key(row["RuleKey"], "release rule")
        groups[character, mechanism, source].append(row)
    releases = []
    for (character, mechanism, source), rows in groups.items():
        states = {
            (
                _flag(row["CanRelease"], source),
                _flag(row["ControllerEnabled"], source),
            )
            for row in rows
        }
        if len(states) != 1:
            raise ValueError(f"Inconsistent damage release group: {source}")
        can_release, enabled = states.pop()
        conditions = tuple(
            sorted(
                {
                    (
                        _key(row["ConditionKind"], source),
                        "" if row["ConditionStableKey"] is None else _key(row["ConditionStableKey"], source),
                    )
                    for row in rows
                }
            )
        )
        releases.append(_Release(character, mechanism, source, conditions, can_release, enabled))
    return releases


def _validate_quest_releases(raw: sqlite3.Connection, releases: list[_Release]) -> None:
    variants = {
        _key(row["ResourceName"], "quest resource"): (
            _key(row["QuestStableKey"], "quest variant"),
            _flag(row["DropInvulnOnHolder"], str(row["ResourceName"])),
        )
        for row in _rows(raw, "QuestVariants", "ResourceName, QuestStableKey, DropInvulnOnHolder")
    }
    holders = {
        (row["QuestStableKey"], row["CharacterStableKey"])
        for row in _rows(raw, "QuestCharacterRoles", "QuestStableKey, CharacterStableKey, Role")
        if row["Role"] == "item_turnin"
    }
    sources = {
        (row["QuestStableKey"], row["SourceStableKey"])
        for row in _rows(raw, "QuestCompletionSources", "QuestStableKey, Method, SourceType, SourceStableKey")
        if row["Method"] == "item_turnin" and row["SourceType"] == "character"
    }
    for release in releases:
        if release.mechanism != "trade_turn_in":
            continue
        resources = [key for kind, key in release.conditions if kind == "quest_variant"]
        if len(resources) != 1 or resources[0] not in variants:
            raise ValueError(f"Missing exact quest variant for trade release: {release.source}")
        quest, drop_invuln = variants[resources[0]]
        if not drop_invuln:
            raise ValueError(f"Trade release variant does not drop holder invulnerability: {resources[0]}")
        if (quest, release.character) not in holders & sources:
            raise ValueError(f"Trade release has no actual item-turn-in holder relation: {release.source}")


def _ward_releases(raw: sqlite3.Connection, characters: set[str]) -> list[_Release]:
    references: dict[str, dict[str, list[sqlite3.Row]]] = defaultdict(lambda: defaultdict(list))
    for row in _rows(
        raw,
        "ScriptedActivatorReferences",
        "SourceKey, Field, ReferenceKind, ReferenceKey",
    ):
        references[row["SourceKey"]][row["Field"]].append(row)
    placements: dict[str, set[str]] = defaultdict(set)
    occupants: dict[str, set[str]] = defaultdict(set)
    spawn_keys = {row["StableKey"] for row in _rows(raw, "SpawnPoints", "StableKey")}
    for row in _rows(raw, "SpawnPointCharacters", "SpawnPointStableKey, CharacterStableKey"):
        spawn, character = row["SpawnPointStableKey"], row["CharacterStableKey"]
        if spawn not in spawn_keys or character not in characters:
            raise ValueError(f"Unresolved combat eligibility spawn binding: {spawn}, {character}")
        placements[character].add(spawn)
        occupants[spawn].add(character)
    essentials: dict[str, set[str]] = defaultdict(set)
    for row in _rows(raw, "SpawnPointEssentialLinks", "SourceSpawnPointStableKey, EssentialSpawnPointStableKey"):
        spawn, ward = row["SourceSpawnPointStableKey"], row["EssentialSpawnPointStableKey"]
        if spawn not in spawn_keys or ward not in spawn_keys:
            raise ValueError(f"Unresolved essential spawn reference: {spawn}, {ward}")
        essentials[spawn].add(ward)
    releases = []
    for row in _rows(
        raw,
        "ScriptedActivators",
        "SourceKey, RuleId, ComponentIsEnabled, HostCharacterStableKey",
    ):
        mechanism = row["RuleId"]
        if mechanism not in {"shivering_phantom_wards", "reliquary_wards"}:
            continue
        source = _key(row["SourceKey"], "ward controller")
        character = _key(row["HostCharacterStableKey"], source)
        if character not in characters:
            raise ValueError(f"Ward controller references unknown character: {character}")
        # Effective activity also includes the host's current active state.
        # Prefabs and quest-activated scene hosts can run this component later.
        enabled = _flag(row["ComponentIsEnabled"], source)
        if mechanism == "shivering_phantom_wards":
            conditions = []
            dependencies = []
            for field in ("ward1", "ward2"):
                refs = references[source].get(field, [])
                if len(refs) != 1:
                    raise ValueError(f"Missing or ambiguous ward reference: {source}.{field}")
                ref = refs[0]
                if ref["ReferenceKind"] == "null" and ref["ReferenceKey"] is None:
                    conditions.append((field + "_absent", ""))
                elif ref["ReferenceKind"] == "character" and ref["ReferenceKey"] in characters:
                    ward = ref["ReferenceKey"]
                    conditions.append(("character_dead", ward))
                    dependencies.append(frozenset({ward}))
                else:
                    raise ValueError(f"Unresolved ward character reference: {source}.{field}")
            releases.append(
                _Release(character, mechanism, source, tuple(conditions), True, enabled, tuple(dependencies))
            )
        else:
            # ReliquaryFiend.Start reads its own NPC's real spawn point. A
            # standalone prefab is not a fictional scene placement.
            for spawn in sorted(placements[character]):
                wards = sorted(essentials[spawn])
                release_conditions = (("controller", source), *(("spawn_point_cleared", ward) for ward in wards))
                release_dependencies = tuple(frozenset(occupants[ward]) for ward in wards if occupants[ward])
                releases.append(
                    _Release(character, mechanism, spawn, release_conditions, True, enabled, release_dependencies)
                )
    return releases


def process_combat_eligibility(raw: sqlite3.Connection, writer: Writer) -> None:
    """Populate every clean copy, rejecting missing or unknown source contracts."""
    raw_characters = {
        _key(row["StableKey"], "character"): _flag(row["Invulnerable"], str(row["StableKey"]))
        for row in _rows(raw, "Characters", "StableKey, Invulnerable")
    }
    clean_characters = {row[0] for row in writer.conn.execute("SELECT stable_key FROM characters")}
    if missing := clean_characters - raw_characters.keys():
        raise ValueError(f"Clean characters missing raw combat eligibility state: {sorted(missing)}")
    characters = set(raw_characters)
    releases = _script_releases(raw, characters) + _ward_releases(raw, characters)
    _validate_quest_releases(raw, releases)
    damageable = {character for character, immune in raw_characters.items() if not immune}
    changed = True
    while changed:
        changed = False
        for release in releases:
            if (
                release.character not in damageable
                and release.enabled
                and release.can_release
                and all(dependency & damageable for dependency in release.dependencies)
            ):
                damageable.add(release.character)
                changed = True
    provenance: list[dict[str, object]] = []
    for release in releases:
        if release.character not in clean_characters:
            continue
        feasible = release.can_release and all(dependency & damageable for dependency in release.dependencies)
        for kind, key in release.conditions:
            provenance.append(
                {
                    "character_stable_key": release.character,
                    "mechanism": release.mechanism,
                    "source_stable_key": release.source,
                    "condition_kind": kind,
                    "condition_stable_key": key,
                    "can_release": int(feasible),
                    "controller_enabled": int(release.enabled),
                }
            )
    with writer.conn:
        writer.conn.execute("DELETE FROM character_damage_releases")
        writer.conn.executemany(
            "UPDATE characters SET can_be_damaged = ? WHERE stable_key = ?",
            [(int(character in damageable), character) for character in sorted(clean_characters)],
        )
        writer.insert_character_damage_releases(provenance)
    logger.info(
        "Combat eligibility: {} of {} character copies",
        len(clean_characters & damageable),
        len(clean_characters),
    )
