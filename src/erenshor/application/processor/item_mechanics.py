"""Item sources and uses that only game code defines.

Four mechanics exist only in game methods, not in exported item data:

- ``Chessboard.CheckForGamepiece`` consumes the Candlekeeper figurine and gives
  back the item in the board's ``ReplaceStatue`` field.
- ``Fishing.Update`` replaces one catch in 20 with one of the first four
  entries of ``GameManager.Maps``.
- ``SpellVessel.DoMiscSpells`` returns the Time Stone unused in two scenes.
- ``TradeWindow.CheckOfferingStones`` blesses one piece of equipment offered at
  the Braxonian Flame Well with equal numbers of Sivakrux and Offering Stones.

Items come from the export where the game serializes them, and otherwise from
item IDs that code facts pin. Every rule constant below is pinned by the code
fact named in its tag, so a game update that changes it fails code-facts
extraction before this module runs.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import TYPE_CHECKING, cast

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from .writer import Writer

_FACTS = (
    "chessboard.candlekeeper_consumed",
    "chessboard.candlekeeper_gives_replace_statue",
    "fishing.map_bonus",
    "time_stone.gated_scenes",
    "time_stone.returned_in_gated_scenes",
    "flame_well.offering_npc",
    "flame_well.sivakrux_id",
    "flame_well.offering_stone_id",
    "flame_well.offered_piece_rule",
    "flame_well.balance_rule",
    "flame_well.chance_per_stone_pair",
    "flame_well.chance_per_improvement_level",
    "flame_well.success_roll",
    "flame_well.blessed_result",
    "flame_well.enhance_roll",
    "flame_well.ascended_result",
    "npc.runtime_name_is_npc_name",
)

# code-fact: chessboard.candlekeeper_consumed
# code-fact: chessboard.candlekeeper_gives_replace_statue
_CHESSBOARD_INPUT_FIELD = "Candlekeeper"
_CHESSBOARD_OUTPUT_FIELD = "ReplaceStatue"
_CHESSBOARD_MECHANIC = "chessboard figurine"

# code-fact: fishing.map_bonus
_FISHING_BONUS_ONE_IN = 20
_FISHING_BONUS_POOL_DRAW = 4
_FISHING_BONUS_POOL = "Maps"

# code-fact: time_stone.gated_scenes
# code-fact: time_stone.returned_in_gated_scenes
_TIME_STONE_ID = "2936548"
_TIME_STONE_SCENES = ("ShiveringTomb2", "StowawayPortal")
_TIME_STONE_OUTCOME = "returned unused"

# code-fact: flame_well.offering_npc
# code-fact: npc.runtime_name_is_npc_name
_FLAME_WELL_NPC_NAME = "Braxonian Flame Well"
# code-fact: flame_well.sivakrux_id
_SIVAKRUX_ID = "23431650"
# code-fact: flame_well.offering_stone_id
_OFFERING_STONE_ID = "340104"
# code-fact: flame_well.offered_piece_rule
# code-fact: flame_well.balance_rule
# code-fact: flame_well.chance_per_stone_pair
# code-fact: flame_well.success_roll
_CHANCE_PER_STONE_PAIR = 40
# code-fact: flame_well.chance_per_improvement_level
_CHANCE_PER_IMPROVEMENT_LEVEL = 8
# code-fact: flame_well.enhance_roll
_ENHANCE_CHANCE_PER_STONE_PAIR = 5
# code-fact: flame_well.blessed_result
_RESULT_QUALITY = "Blessed"
# code-fact: flame_well.ascended_result
_ENHANCED_QUALITY = "Ascended"


def require_facts(facts: Collection[str]) -> None:
    """Raise when a code fact this module relies on is missing."""
    missing = [fact for fact in _FACTS if fact not in facts]
    if missing:
        raise ValueError(f"Item mechanic code facts missing: {missing}")


def resolve_item_id(item_keys_by_id: dict[str, str], item_id: str) -> str:
    """Return the stable key of a pinned item ID, or raise naming the ID."""
    key = item_keys_by_id.get(item_id)
    if key is None:
        raise ValueError(f"Item ID {item_id} pinned by a code fact matches no item")
    return key


def derive_item_conversions(
    chessboard_items: Mapping[str, Mapping[str, str | None]],
    zone_by_scene: dict[str, str],
) -> list[dict[str, object]]:
    """One row per Chessboard: the Candlekeeper figurine yields ReplaceStatue."""
    if not chessboard_items:
        raise ValueError("Chessboard export has no board")
    rows: list[dict[str, object]] = []
    for scene, fields in sorted(chessboard_items.items()):
        input_key = fields.get(_CHESSBOARD_INPUT_FIELD)
        output_key = fields.get(_CHESSBOARD_OUTPUT_FIELD)
        if input_key is None or output_key is None:
            raise ValueError(f"Chessboard in {scene} lacks {_CHESSBOARD_INPUT_FIELD} or {_CHESSBOARD_OUTPUT_FIELD}")
        zone = zone_by_scene.get(scene)
        if zone is None:
            raise ValueError(f"Chessboard scene {scene} matches no zone")
        rows.append(
            {
                "input_item_stable_key": input_key,
                "output_item_stable_key": output_key,
                "zone_stable_key": zone,
                "mechanic": _CHESSBOARD_MECHANIC,
            }
        )
    return rows


def derive_fishing_bonus_catches(maps_pool: list[str | None]) -> list[dict[str, object]]:
    """One row per item the fishing bonus can catch, with its chance per catch in percent."""
    if len(maps_pool) < _FISHING_BONUS_POOL_DRAW:
        raise ValueError(
            f"{_FISHING_BONUS_POOL} pool has {len(maps_pool)} entries; fishing draws from {_FISHING_BONUS_POOL_DRAW}"
        )
    drawn = Counter(key for key in maps_pool[:_FISHING_BONUS_POOL_DRAW] if key is not None)
    return [
        {
            "item_stable_key": key,
            "chance_per_catch": 100 / _FISHING_BONUS_ONE_IN * count / _FISHING_BONUS_POOL_DRAW,
        }
        for key, count in sorted(drawn.items())
    ]


def derive_water_fishables(
    pools: Mapping[str, Mapping[str, list[str | None]]],
    maps_pool: list[str | None],
) -> list[dict[str, object]]:
    """Final percent per successful catch, including the global replacement once.

    Native serialized slots remain in the raw export. Null slots keep their
    selection mass, so emitted item probabilities need not sum to 100.
    """
    bonus = {
        str(row["item_stable_key"]): cast("float", row["chance_per_catch"])
        for row in derive_fishing_bonus_catches(maps_pool)
    }
    rows: list[dict[str, object]] = []
    for water_key, times in sorted(pools.items()):
        day = times.get("DayFishable", [])
        # code-fact: water.empty_night_fallback
        night = times.get("NightFishable", []) or day
        for time, pool in (("DayFishable", day), ("NightFishable", night)):
            # code-fact: fishing.source_eligibility
            if not pool:
                continue
            # code-fact: fishing.native_pool_draw
            # code-fact: fishing.map_bonus
            native_share = 100 * (1 - 1 / _FISHING_BONUS_ONE_IN)
            counts = Counter(key for key in pool if key is not None)
            for key in sorted(counts.keys() | bonus.keys()):
                rows.append(
                    {
                        "water_stable_key": water_key,
                        "type": time,
                        "item_stable_key": key,
                        "drop_chance": native_share * counts[key] / len(pool) + bonus.get(key, 0),
                    }
                )
    return rows


def process_water_fishables(raw: sqlite3.Connection, writer: Writer) -> None:
    """Combine native water slots with the same bonus used by the global source."""
    if "Position" not in {row[1] for row in raw.execute("PRAGMA table_info(WaterFishables)")}:
        raise ValueError(
            "WaterFishables lacks native pool positions. Run extract export, then extract code-facts "
            "before rebuilding the clean database."
        )
    required = {
        "water.empty_night_fallback",
        "fishing.source_eligibility",
        "fishing.native_pool_draw",
        "fishing.map_bonus",
    }
    facts = {str(row[0]) for row in raw.execute("SELECT DISTINCT fact_id FROM code_facts")}
    if missing := sorted(required - facts):
        raise ValueError(f"Fishing code facts missing: {missing}")
    pools: dict[str, dict[str, list[str | None]]] = {}
    for water, time, item in raw.execute(
        "SELECT WaterStableKey, Type, ItemStableKey FROM WaterFishables ORDER BY WaterStableKey, Type, Position"
    ):
        pools.setdefault(water, {}).setdefault(time, []).append(item)
    maps = [
        row[0]
        for row in raw.execute(
            "SELECT ItemStableKey FROM SpecialWorldDropItems WHERE Pool = ? ORDER BY Position",
            (_FISHING_BONUS_POOL,),
        )
    ]
    writer.insert_water_fishables(derive_water_fishables(pools, maps))


def derive_item_zone_restrictions(time_stone_key: str, zone_by_scene: dict[str, str]) -> list[dict[str, object]]:
    """One row per scene where the Time Stone returns unused."""
    rows: list[dict[str, object]] = []
    for scene in _TIME_STONE_SCENES:
        zone = zone_by_scene.get(scene)
        if zone is None:
            raise ValueError(f"Time Stone scene {scene} matches no zone")
        rows.append({"item_stable_key": time_stone_key, "zone_stable_key": zone, "outcome": _TIME_STONE_OUTCOME})
    return rows


def derive_quality_offerings(
    flame_well_keys: list[str], sivakrux_key: str, offering_stone_key: str
) -> list[dict[str, object]]:
    """One row per character that accepts the Flame Well offering."""
    if not flame_well_keys:
        raise ValueError(f"No character is named {_FLAME_WELL_NPC_NAME}")
    return [
        {
            "character_stable_key": key,
            "first_item_stable_key": sivakrux_key,
            "second_item_stable_key": offering_stone_key,
            "chance_per_stone_pair": _CHANCE_PER_STONE_PAIR,
            "chance_per_improvement_level": _CHANCE_PER_IMPROVEMENT_LEVEL,
            "enhance_chance_per_stone_pair": _ENHANCE_CHANCE_PER_STONE_PAIR,
            "result_quality": _RESULT_QUALITY,
            "enhanced_quality": _ENHANCED_QUALITY,
        }
        for key in sorted(flame_well_keys)
    ]


def process_item_mechanics(raw: sqlite3.Connection, writer: Writer) -> None:
    """Write the four item mechanic tables. Runs after items, zones, and characters."""
    require_facts({str(row[0]) for row in raw.execute("SELECT DISTINCT fact_id FROM code_facts")})

    clean = writer.conn
    item_keys_by_id = {
        str(row[0]): str(row[1]) for row in clean.execute("SELECT id, stable_key FROM items WHERE id IS NOT NULL")
    }
    zone_by_scene = {
        str(row[0]): str(row[1])
        for row in clean.execute("SELECT scene_name, stable_key FROM zones WHERE scene_name IS NOT NULL")
    }

    chessboard_items: dict[str, dict[str, str | None]] = {}
    for row in raw.execute("SELECT Scene, Field, ItemStableKey FROM ChessboardItems"):
        chessboard_items.setdefault(str(row[0]), {})[str(row[1])] = row[2]
    maps_pool = [
        row[0]
        for row in raw.execute(
            "SELECT ItemStableKey FROM SpecialWorldDropItems WHERE Pool = ? ORDER BY Position",
            (_FISHING_BONUS_POOL,),
        )
    ]
    flame_well_keys = [
        str(row[0])
        for row in clean.execute("SELECT stable_key FROM characters WHERE npc_name = ?", (_FLAME_WELL_NPC_NAME,))
    ]

    conversions = derive_item_conversions(chessboard_items, zone_by_scene)
    catches = derive_fishing_bonus_catches(maps_pool)
    restrictions = derive_item_zone_restrictions(resolve_item_id(item_keys_by_id, _TIME_STONE_ID), zone_by_scene)
    offerings = derive_quality_offerings(
        flame_well_keys,
        resolve_item_id(item_keys_by_id, _SIVAKRUX_ID),
        resolve_item_id(item_keys_by_id, _OFFERING_STONE_ID),
    )

    writer.insert_item_conversions(conversions)
    writer.insert_fishing_bonus_catches(catches)
    writer.insert_item_zone_restrictions(restrictions)
    writer.insert_quality_offerings(offerings)
    logger.info(
        f"Item mechanics: {len(conversions)} conversions, {len(catches)} fishing bonus catches, "
        f"{len(restrictions)} zone restrictions, {len(offerings)} quality offerings"
    )
