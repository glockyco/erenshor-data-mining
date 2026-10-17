"""Tests for the special world drop derivation."""

from __future__ import annotations

import sqlite3

import pytest

from erenshor.application.processor.special_world_drops import (
    derive_special_world_drops,
    mask_shares,
    process_common_world_items,
)
from erenshor.application.processor.writer import Writer
from erenshor.application.wiki_lua.world_drops import build_world_drop_rows
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ProvenanceCondition

_SINGLE_POOLS = (
    "Sivak",
    "EssenceOfAmarion",
    "XPPot",
    "InertDiamond",
    "PlanarShard",
    "MoloraiMask",
    "Empty2",
    "CrystallizedBalance",
    "Planar",
)
_FACT_IDS = {
    "Sivak": "sivak",
    "WorldDropMolds": "world_drop_molds",
    "Maps": "maps",
    "EssenceOfAmarion": "essence_of_amarion",
    "XPPot": "xp_pot",
    "InertDiamond": "inert_diamond",
    "PlanarShard": "planar_shard",
    "Masks": "masks",
    "MoloraiMask": "molorai_mask",
    "Empty2": "empty2",
    "CrystallizedBalance": "crystallized_balance",
    "Planar": "planar",
}


def _pools() -> dict[str, list[str | None]]:
    pools: dict[str, list[str | None]] = {name: [f"item:{name.lower()}"] for name in _SINGLE_POOLS}
    pools["WorldDropMolds"] = ["item:mold a", "item:mold b", "item:mold a", None]
    pools["Maps"] = ["item:map"]
    pools["Masks"] = ["item:mask a", "item:mask b"]
    return pools


def _facts() -> dict[str, dict[str, str]]:
    facts = {f"loot.world_drop.{fact}": {"rate": "0.01", "min_level": "0"} for fact in _FACT_IDS.values()}
    facts["loot.world_drop.crystallized_balance"] = {"rate": "0.0005", "min_level": "30"}
    facts["loot.world_drop.mask_split"] = {"range_min": "0", "range_max": "100", "cutoff": "1"}
    return facts


def _valid(pools: dict[str, list[str | None]]) -> set[str]:
    return {key for entries in pools.values() for key in entries if key is not None}


def _by_item(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["item_stable_key"]): row for row in rows}


def test_single_item_roll_keeps_chance_and_level_gate() -> None:
    pools = _pools()
    rows = _by_item(derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, _facts(), _valid(pools)))

    assert rows["item:crystallizedbalance"]["drop_probability"] == pytest.approx(0.05)
    assert rows["item:crystallizedbalance"]["min_level_exclusive"] == 30


def test_pool_share_counts_duplicates_and_empty_entries() -> None:
    """An item listed twice gets twice the share, and an empty entry still takes a share."""
    pools = _pools()
    rows = _by_item(derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, _facts(), _valid(pools)))

    assert rows["item:mold a"]["drop_probability"] == pytest.approx(1.0 * 2 / 4)
    assert rows["item:mold b"]["drop_probability"] == pytest.approx(1.0 * 1 / 4)


def test_mask_roll_splits_98_to_2() -> None:
    assert mask_shares(0, 100, 1) == pytest.approx((0.98, 0.02))

    pools = _pools()
    rows = _by_item(derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, _facts(), _valid(pools)))

    assert rows["item:mask a"]["drop_probability"] == pytest.approx(1.0 * 0.98 / 2)
    assert rows["item:moloraimask"]["drop_probability"] == pytest.approx(1.0 * 0.02)


@pytest.mark.parametrize(
    ("pool", "fact_id", "gate", "successes"),
    [
        ("Sivak", "sivak", 10, 100),
        ("XPPot", "xp_pot", 12, 20),
        ("PlanarShard", "planar_shard", 15, 10),
        ("InertDiamond", "inert_diamond", 20, 80),
        ("CrystallizedBalance", "crystallized_balance", 30, 5),
        ("Planar", "planar", 30, 5),
    ],
)
def test_default_roll_outcomes_at_strict_level_boundaries(pool: str, fact_id: str, gate: int, successes: int) -> None:
    pools = _pools()
    facts = _facts()
    facts[f"loot.world_drop.{fact_id}"] = {"rate": str(successes / 10000), "min_level": str(gate)}
    rows = derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, facts, _valid(pools))
    item_key = pools[pool][0]
    assert item_key is not None
    drop = _by_item(rows)[item_key]
    view = build_world_drop_rows(
        [
            ItemAcquisition(
                f"acquisition:world:{pool}",
                item_key,
                "special_world_drop",
                f"world:{pool}",
                probability_kind="exact",
                probability_min=float(drop["drop_probability"]),
                probability_max=float(drop["drop_probability"]),
                probability_basis="per_kill",
                probability_stage="final_acquisition",
                conditions=(
                    ProvenanceCondition(
                        f"world-level:{pool}",
                        0,
                        0,
                        "actor_level",
                        actor="enemy",
                        minimum=float(drop["min_level_exclusive"]),
                        minimum_inclusive=False,
                    ),
                ),
            )
        ]
    )[item_key][0]

    for level in (0, 1, 10, 11, 12, 13, 15, 16, 20, 21, 30, 31, 42):
        # Enumerate equal-mass representative draws independently of the derivation.
        awarded = sum(level > gate and draw < successes for draw in range(10000))
        displayed = view["chance"] if level >= view["minLevel"] else 0
        assert displayed == pytest.approx(100 * awarded / 10000)


def test_two_independent_rolls_can_both_select_the_same_item() -> None:
    pools = _pools()
    pools["WorldDropMolds"] = ["item:shared"]
    pools["Maps"] = ["item:shared"]
    facts = _facts()
    facts["loot.world_drop.world_drop_molds"]["rate"] = "0.005"
    facts["loot.world_drop.maps"]["rate"] = "0.025"
    rows = derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, facts, _valid(pools))
    shared = [row for row in rows if row["item_stable_key"] == "item:shared"]

    assert sorted((row["pool"], row["drop_probability"]) for row in shared) == [
        ("Maps", 2.5),
        ("WorldDropMolds", 0.5),
    ]


@pytest.mark.parametrize(
    ("flags", "absent"),
    [
        ({"DropMasks": True, "DemoBuild": False}, {"item:empty2"}),
        ({"DropMasks": False, "DemoBuild": True}, {"item:mask a", "item:mask b", "item:moloraimask"}),
    ],
)
def test_disabled_rolls_have_no_rows(flags: dict[str, bool], absent: set[str]) -> None:
    pools = _pools()
    rows = _by_item(derive_special_world_drops(pools, flags, _facts(), _valid(pools)))

    assert absent.isdisjoint(rows)


def test_pool_without_a_code_fact_fails() -> None:
    pools = _pools()
    pools["NewPool"] = ["item:new"]

    with pytest.raises(ValueError, match="NewPool"):
        derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, _facts(), _valid(pools))


def test_missing_code_fact_fails() -> None:
    pools = _pools()
    facts = _facts()
    del facts["loot.world_drop.planar"]

    with pytest.raises(ValueError, match=r"loot\.world_drop\.planar"):
        derive_special_world_drops(pools, {"DropMasks": True, "DemoBuild": False}, facts, _valid(pools))


def test_common_world_items_preserve_positions_nulls_and_duplicate_entries(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE CommonWorldItems (Position INTEGER PRIMARY KEY, ItemStableKey TEXT)")
    raw.executemany(
        "INSERT INTO CommonWorldItems VALUES (?, ?)",
        [(4, "item:bread"), (0, None), (3, "item:bread"), (1, "item:water")],
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    try:
        writer.insert_items(
            [
                {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread.png"},
                {"stable_key": "item:water", "display_name": "Water", "image_name": "Water.png"},
            ]
        )
        process_common_world_items(raw, writer, {"item:bread", "item:water"})
        rows = writer.conn.execute(
            "SELECT position, item_stable_key FROM common_world_items ORDER BY position"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            (0, None),
            (1, "item:water"),
            (3, "item:bread"),
            (4, "item:bread"),
        ]
        foreign_keys = writer.conn.execute("PRAGMA foreign_key_list(common_world_items)").fetchall()
        assert any(row[2:5] == ("items", "item_stable_key", "stable_key") for row in foreign_keys)
    finally:
        raw.close()
        writer.conn.close()


def test_common_world_items_reject_missing_item_without_writing_partial_pool(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE CommonWorldItems (Position INTEGER PRIMARY KEY, ItemStableKey TEXT)")
    raw.executemany(
        "INSERT INTO CommonWorldItems VALUES (?, ?)",
        [(0, "item:bread"), (1, None), (2, "item:missing")],
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    try:
        with pytest.raises(ValueError, match=r"Common world items reference missing clean items.*item:missing"):
            process_common_world_items(raw, writer, {"item:bread"})
        assert writer.conn.execute("SELECT COUNT(*) FROM common_world_items").fetchone()[0] == 0
    finally:
        raw.close()
        writer.conn.close()
