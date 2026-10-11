"""Tests for the runtime item mechanic derivations."""

from __future__ import annotations

import pytest

from erenshor.application.processor import item_mechanics
from erenshor.application.processor.item_mechanics import (
    derive_fishing_bonus_catches,
    derive_item_conversions,
    derive_item_zone_restrictions,
    derive_quality_offerings,
    require_facts,
    resolve_item_id,
)

_BOARD = {
    "Braxonian": {
        "Candlekeeper": "item:quest - game piece the candlekeeper",
        "ReplaceStatue": "item:template - a strange figurine",
        "Peon": "item:quest - game piece peon",
    }
}


def test_candlekeeper_figurine_converts_to_the_replace_statue_item() -> None:
    rows = derive_item_conversions(_BOARD, {"Braxonian": "zone:braxonian"})

    assert rows == [
        {
            "input_item_stable_key": "item:quest - game piece the candlekeeper",
            "output_item_stable_key": "item:template - a strange figurine",
            "zone_stable_key": "zone:braxonian",
            "mechanic": "chessboard figurine",
        }
    ]


@pytest.mark.parametrize(
    ("boards", "zones", "message"),
    [
        ({}, {}, "no board"),
        ({"Braxonian": {"Candlekeeper": "item:a", "ReplaceStatue": None}}, {"Braxonian": "zone:b"}, "lacks"),
        ({"Braxonian": {"Peon": "item:a"}}, {"Braxonian": "zone:b"}, "lacks"),
        (_BOARD, {}, "matches no zone"),
    ],
)
def test_conversion_fails_on_incomplete_export(boards, zones, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        derive_item_conversions(boards, zones)


def test_fishing_bonus_splits_one_catch_in_twenty_over_the_first_four_maps() -> None:
    rows = derive_fishing_bonus_catches(["item:tl", "item:tr", "item:bl", "item:br", "item:never drawn"])

    assert rows == [
        {"item_stable_key": key, "chance_per_catch": 1.25} for key in ("item:bl", "item:br", "item:tl", "item:tr")
    ]


def test_fishing_bonus_counts_a_repeated_map_twice() -> None:
    rows = derive_fishing_bonus_catches(["item:a", "item:a", None, "item:b"])

    assert rows == [
        {"item_stable_key": "item:a", "chance_per_catch": 2.5},
        {"item_stable_key": "item:b", "chance_per_catch": 1.25},
    ]


def test_fishing_bonus_fails_on_a_short_map_pool() -> None:
    with pytest.raises(ValueError, match="draws from 4"):
        derive_fishing_bonus_catches(["item:a", "item:b", "item:c"])


def test_time_stone_returns_unused_in_both_gated_zones() -> None:
    zones = {"ShiveringTomb2": "zone:shiveringtomb2", "StowawayPortal": "zone:stowawayportal", "Azure": "zone:azure"}

    rows = derive_item_zone_restrictions("item:gen - time stone", zones)

    assert rows == [
        {
            "item_stable_key": "item:gen - time stone",
            "zone_stable_key": "zone:shiveringtomb2",
            "outcome": "returned unused",
        },
        {
            "item_stable_key": "item:gen - time stone",
            "zone_stable_key": "zone:stowawayportal",
            "outcome": "returned unused",
        },
    ]


def test_time_stone_fails_when_a_gated_scene_has_no_zone() -> None:
    with pytest.raises(ValueError, match="StowawayPortal"):
        derive_item_zone_restrictions("item:gen - time stone", {"ShiveringTomb2": "zone:shiveringtomb2"})


def test_each_flame_well_accepts_the_offering_with_the_pinned_rule() -> None:
    rows = derive_quality_offerings(["character:well b", "character:well a"], "item:sivak", "item:offering stone")

    assert [row["character_stable_key"] for row in rows] == ["character:well a", "character:well b"]
    assert rows[0] == {
        "character_stable_key": "character:well a",
        "first_item_stable_key": "item:sivak",
        "second_item_stable_key": "item:offering stone",
        "chance_per_stone_pair": 40,
        "chance_per_improvement_level": 8,
        "enhance_chance_per_stone_pair": 5,
        "result_quality": "Blessed",
        "enhanced_quality": "Ascended",
    }


def test_flame_well_fails_without_a_well() -> None:
    with pytest.raises(ValueError, match="Braxonian Flame Well"):
        derive_quality_offerings([], "item:sivak", "item:offering stone")


def test_a_pinned_item_id_must_resolve() -> None:
    assert resolve_item_id({"2936548": "item:gen - time stone"}, "2936548") == "item:gen - time stone"
    with pytest.raises(ValueError, match="2936548"):
        resolve_item_id({}, "2936548")


def test_every_relied_on_fact_must_be_extracted() -> None:
    require_facts(set(item_mechanics._FACTS))
    with pytest.raises(ValueError, match=r"flame_well\.success_roll"):
        require_facts(set(item_mechanics._FACTS) - {"flame_well.success_roll"})
