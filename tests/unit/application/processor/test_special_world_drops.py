"""Tests for the special world drop derivation."""

from __future__ import annotations

import pytest

from erenshor.application.processor.special_world_drops import derive_special_world_drops, mask_shares

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
