"""Give dynamic and chained placements the characters that they need first.

The ``summoned_by`` rules of dynamic-spawn-catalog.toml say, for each spawning
field, which characters must be fighting, dead, or spoken to before the field
spawns. The export resolves each rule to characters and spawn points
(``DynamicSpawnSummoners``). This step maps them onto the clean placements and
resolves the characters that check in at run time.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .characters import chained_placements

if TYPE_CHECKING:
    import sqlite3

    from .writer import Writer

# code-fact: arena.vitheo_checkin
# VithArena checks the first fighter of round 8 in with VitheoFight when it is
# Vitheo the Tactician.
_VITHEO_ROUND = 8
_VITHEO_NAME = "Vitheo the Tactician"

_Summoner = tuple[int, str, str, str, str | None]


def process_summons(raw: sqlite3.Connection, writer: Writer) -> int:
    """Write ``character_summons``. Return the number of rows."""
    conn = writer.conn
    summoners: dict[tuple[str, str], list[_Summoner]] = defaultdict(list)
    for controller, field, index, script, summon, kind, key in raw.execute(
        "SELECT ControllerObjectKey, SourceField, SummonerIndex, SourceScript, Summon, SummonerKind,"
        " SummonerStableKey FROM DynamicSpawnSummoners ORDER BY 1, 2, 3"
    ):
        summoners[controller, field].append((index, script, summon, kind, key))
    characters = {key for (key,) in conn.execute("SELECT stable_key FROM characters")}
    placements = {
        key
        for (key,) in conn.execute(
            "SELECT spawn_point_stable_key FROM character_spawns WHERE spawn_point_stable_key IS NOT NULL"
        )
    }
    occupants: dict[str, set[str]] = defaultdict(set)
    for spawn, character in conn.execute(
        "SELECT spawn_point_stable_key, character_stable_key FROM character_spawns"
        " WHERE spawn_point_stable_key IS NOT NULL"
    ):
        occupants[spawn].add(character)
    dialogs = {
        (host, child)
        for host, child in conn.execute(
            "SELECT character_stable_key, spawn_character_stable_key FROM character_dialogs"
            " WHERE spawn_character_stable_key IS NOT NULL"
        )
    }
    scenes: dict[str, set[str]] = defaultdict(set)
    for controller, scene in raw.execute("SELECT ControllerObjectKey, Scene FROM DynamicCharacterSpawns"):
        scenes[controller].add(scene)

    def checked_in(controller: str, script: str, where: str) -> set[str]:
        if script == "RewardListener":
            # code-fact: progression.twins.chest
            twins = {
                key
                for (key,) in raw.execute(
                    "SELECT r.ReferenceKey FROM ScriptedActivators a JOIN ScriptedActivatorReferences r"
                    " ON r.SourceKey = a.SourceKey WHERE a.ObjectKey = ? AND a.RuleId = 'twin_giants'"
                    " AND r.Field = '$checkin_character'",
                    (controller,),
                )
            }
            if len(twins) != 2:
                raise ValueError(f"{where}: expected the two twins that check in, got {sorted(twins)}")
            return twins
        if script == "VitheoFight":
            if len(scenes[controller]) != 1:
                raise ValueError(f"{where}: the controller spawns in scenes {sorted(scenes[controller])}")
            (scene,) = scenes[controller]
            fighters = [
                key
                for (key,) in conn.execute(
                    "SELECT e.enemy_character_stable_key FROM arena_rounds r JOIN arena_round_enemies e"
                    " ON e.arena_round_stable_key = r.stable_key AND e.sequence_index = 0"
                    " WHERE r.scene = ? AND r.round_index = ?",
                    (scene, _VITHEO_ROUND),
                )
            ]
            names = {
                name
                for key in fighters
                for (name,) in raw.execute("SELECT NPCName FROM Characters WHERE StableKey = ?", (key,))
            }
            if len(fighters) != 1 or names != {_VITHEO_NAME}:
                raise ValueError(f"{where}: round {_VITHEO_ROUND} does not open with {_VITHEO_NAME}: {fighters}")
            return set(fighters)
        raise ValueError(f"{where}: no check-in binding for {script}")

    def resolve(controller: str, summoner: _Summoner, where: str) -> set[str]:
        _, script, _, kind, key = summoner
        if kind == "checked_in":
            return checked_in(controller, script, where)
        if kind == "character" and key is not None and key in characters:
            return {key}
        if kind == "spawn_point" and key is not None and occupants.get(key):
            return occupants[key]
        raise ValueError(f"{where}: summoner {kind} {key!r} names no clean character")

    rows: list[dict[str, object]] = []

    def emit(character: str, spawn: str, controller: str, script: str, field: str) -> None:
        where = f"{script}.{field} {spawn}"
        index = 0
        for summoner in summoners[controller, field]:
            _, _, summon, kind, _ = summoner
            found = sorted(resolve(controller, summoner, where))
            # Every character that checks in counts, while the characters of one
            # spawn point are alternatives, because only one of them spawns.
            for group in ([key] for key in found) if kind == "checked_in" else [found]:
                for key in group:
                    if summon == "dialog" and (key, character) not in dialogs:
                        raise ValueError(f"{where}: no dialog of {key} spawns {character}")
                    rows.append(
                        {
                            "character_stable_key": character,
                            "spawn_point_stable_key": spawn,
                            "source_script": script,
                            "source_field": field,
                            "summon": summon,
                            "summoner_index": index,
                            "summoner_stable_key": key,
                        }
                    )
                index += 1

    for key, character, script, field, controller in raw.execute(
        "SELECT Key, CharacterStableKey, SourceScript, SourceField, ControllerObjectKey"
        " FROM DynamicCharacterSpawns ORDER BY Key"
    ):
        if (controller, field) not in summoners or character not in characters:
            continue
        if key not in placements:
            raise ValueError(f"{script}.{field} spawn {key!r} has no clean placement")
        emit(character, key, controller, script, field)
    for parent, child, script, field, controller in raw.execute(
        "SELECT ParentStableKey, ChildStableKey, SourceScript, SourceField, ControllerObjectKey"
        " FROM CharacterChainedSpawns ORDER BY 1, 2, 3, 4"
    ):
        if (controller, field) not in summoners or child not in characters:
            continue
        for spawn, _ in chained_placements(conn, parent, child, script):
            if spawn is not None:
                emit(child, spawn, controller, script, field)
    return writer.insert_character_summons(rows)
