"""Special world drops: the item rolls that every loot-table kill makes.

``LootTable.InitLootTable`` rolls each special drop independently after the
killed character's own table. The exported pools (``SpecialWorldDropItems``)
name the items, the exported flags (``SpecialWorldDropFlags``) enable or
disable rolls, and the ``loot.world_drop.*`` code facts give each roll's
chance and level gate. This module combines them into one clean row per item
and roll, with the chance per kill at the default loot rate and no bonuses.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .writer import Writer


@dataclass(frozen=True)
class _Roll:
    fact_id: str
    # The GameManager flag that must be set for the roll to happen, or None.
    required_flag: str | None = None


# Every exported pool and the code fact that holds its chance and level gate.
# code-fact: loot.world_drop.masks_gate
# code-fact: loot.world_drop.empty2_gate
_ROLLS: dict[str, _Roll] = {
    "Sivak": _Roll("loot.world_drop.sivak"),
    "WorldDropMolds": _Roll("loot.world_drop.world_drop_molds"),
    "Maps": _Roll("loot.world_drop.maps"),
    "EssenceOfAmarion": _Roll("loot.world_drop.essence_of_amarion"),
    "XPPot": _Roll("loot.world_drop.xp_pot"),
    "InertDiamond": _Roll("loot.world_drop.inert_diamond"),
    "PlanarShard": _Roll("loot.world_drop.planar_shard"),
    "Masks": _Roll("loot.world_drop.masks", required_flag="DropMasks"),
    "MoloraiMask": _Roll("loot.world_drop.molorai_mask", required_flag="DropMasks"),
    "Empty2": _Roll("loot.world_drop.empty2", required_flag="DemoBuild"),
    "CrystallizedBalance": _Roll("loot.world_drop.crystallized_balance"),
    "Planar": _Roll("loot.world_drop.planar"),
}

_MASK_SPLIT_FACT = "loot.world_drop.mask_split"


def mask_shares(range_min: int, range_max: int, cutoff: int) -> tuple[float, float]:
    """Shares of the ordinary-mask and Molorai Mask branches of the mask roll.

    The game draws ``Random.Range(range_min, range_max)``, an integer in
    ``[range_min, range_max)``, and picks an ordinary mask when it exceeds
    ``cutoff``.
    """
    # code-fact: loot.world_drop.mask_split
    outcomes = range_max - range_min
    ordinary = range_max - cutoff - 1
    return ordinary / outcomes, (outcomes - ordinary) / outcomes


def derive_special_world_drops(
    pools: dict[str, list[str | None]],
    flags: dict[str, bool],
    facts: dict[str, dict[str, str]],
    valid_item_keys: set[str],
) -> list[dict[str, object]]:
    """Derive one row per item and roll.

    ``pools`` maps a pool name to its entries in list order, with None for an
    empty entry. An empty entry still counts toward the pool size, because
    the game can pick it.
    """
    unknown = set(pools) - set(_ROLLS)
    if unknown:
        raise ValueError(f"Special world drop pools without a code fact mapping: {sorted(unknown)}")
    missing = set(_ROLLS) - set(pools)
    if missing:
        raise ValueError(f"Special world drop pools missing from the export: {sorted(missing)}")
    for roll in _ROLLS.values():
        if roll.fact_id not in facts:
            raise ValueError(f"Special world drop code fact missing: {roll.fact_id}")
        if roll.required_flag is not None and roll.required_flag not in flags:
            raise ValueError(f"Special world drop flag missing from the export: {roll.required_flag}")

    split = facts.get(_MASK_SPLIT_FACT)
    if split is None:
        raise ValueError(f"Special world drop code fact missing: {_MASK_SPLIT_FACT}")
    ordinary_share, molorai_share = mask_shares(int(split["range_min"]), int(split["range_max"]), int(split["cutoff"]))
    branch_share = {"Masks": ordinary_share, "MoloraiMask": molorai_share}

    rows: list[dict[str, object]] = []
    for pool, entries in sorted(pools.items()):
        roll = _ROLLS[pool]
        if roll.required_flag is not None and not flags[roll.required_flag]:
            continue
        fact = facts[roll.fact_id]
        roll_percent = float(fact["rate"]) * 100 * branch_share.get(pool, 1.0)
        for item_key, count in sorted(Counter(key for key in entries if key is not None).items()):
            if item_key not in valid_item_keys:
                continue
            rows.append(
                {
                    "item_stable_key": item_key,
                    "pool": pool,
                    "drop_probability": roll_percent * count / len(entries),
                    "min_level_exclusive": int(fact["min_level"]),
                }
            )
    return rows


def process_special_world_drops(
    raw: sqlite3.Connection,
    writer: Writer,
    valid_item_keys: set[str],
) -> None:
    """Write the clean ``special_world_drops`` table."""
    pools: dict[str, list[str | None]] = {}
    for row in raw.execute("SELECT Pool, ItemStableKey FROM SpecialWorldDropItems ORDER BY Pool, Position"):
        pools.setdefault(str(row[0]), []).append(row[1])
    flags = {str(row[0]): bool(row[1]) for row in raw.execute("SELECT Name, Value FROM SpecialWorldDropFlags")}
    facts: dict[str, dict[str, str]] = {}
    for row in raw.execute("SELECT fact_id, key, value FROM code_facts WHERE fact_id LIKE 'loot.world_drop.%'"):
        facts.setdefault(str(row[0]), {})[str(row[1])] = str(row[2])

    rows = derive_special_world_drops(pools, flags, facts, valid_item_keys)
    writer.insert_special_world_drops(rows)
    logger.info(f"Special world drops: {len(rows)} rows")
