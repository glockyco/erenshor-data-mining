"""Successful sim listing routes have distinct level and display gates."""

from dataclasses import replace

import pytest

from erenshor.application.processor.auction import ListingItem, ListingRules, derive_listing_routes

RULES = ListingRules(direct_cap=35, direct_above=3, direct_below=5, sim_cap=35, player_cap=35)
CLASSES = {"Arcanist", "Druid", "Duelist", "Paladin", "Reaver", "Stormcaller"}
ITEM = ListingItem("item:test", "123", 10, 5, slot="Head", classes=frozenset(CLASSES))


def routes(item: ListingItem) -> dict[str, dict[str, object]]:
    return {str(row["route"]): row for row in derive_listing_routes(item, RULES, {"item:currency"}, CLASSES)}


@pytest.mark.parametrize(("level", "bounds"), [(0, (1, 5)), (1, (1, 6)), (10, (7, 15)), (35, (32, 35))])
def test_direct_window_boundaries(level: int, bounds: tuple[int, int]) -> None:
    row = routes(replace(ITEM, level=level))["direct"]
    assert (row["min_sim_level"], row["max_sim_level"]) == bounds
    assert row["min_player_level"] is None


@pytest.mark.parametrize("level", [-1, 36, 40, 50])
def test_direct_draw_excludes_outside_item_cap(level: int) -> None:
    assert "direct" not in routes(replace(ITEM, level=level))


@pytest.mark.parametrize("flag", ["no_trade", "unique", "furniture"])
def test_hard_flags_exclude_every_route(flag: str) -> None:
    assert routes(replace(ITEM, **{flag: True})) == {}


def test_direct_draw_ignores_sim_get_and_class_restrictions() -> None:
    assert set(routes(replace(ITEM, sim_cannot_get=True, classes=frozenset()))) == {"direct"}


@pytest.mark.parametrize("change", [{"cannot_sell": True}, {"taught_spell_level": -1}, {"item_id": "315843"}])
def test_display_replaces_original_but_does_not_recheck_replacement(change: dict) -> None:
    assert set(routes(replace(ITEM, **change))) == {"replacement"}


def test_taught_spell_level_is_not_the_item_level() -> None:
    assert "direct" in routes(replace(ITEM, level=0, taught_spell_level=50))


def test_replacement_window_uses_player_not_sim_level() -> None:
    row = routes(ITEM)["replacement"]
    assert (row["min_player_level"], row["max_player_level"]) == (10, 35)
    assert row["min_sim_level"] is None
    assert "replacement" not in routes(replace(ITEM, level=0))
    assert "replacement" not in routes(replace(ITEM, level=36))


def test_currency_is_replaced_not_offered() -> None:
    assert routes(replace(ITEM, key="item:currency")) == {}


def test_gear_surplus_requires_a_storage_path() -> None:
    assert routes(replace(ITEM, level=36)) == {}
    mismatch = routes(replace(ITEM, level=36, classes=frozenset({"Druid"})))["gear_surplus"]
    assert (mismatch["min_sim_level"], mismatch["max_sim_level"]) == (30, 35)
    hand = routes(replace(ITEM, level=39, slot="PrimaryOrSecondary"))["gear_surplus"]
    assert (hand["min_sim_level"], hand["max_sim_level"]) == (35, 35)
    assert routes(replace(ITEM, level=40, slot="Primary")) == {}


def test_scoped_worn_effect_can_force_gear_into_storage() -> None:
    assert "gear_surplus" in routes(replace(ITEM, level=39, worn_effect_id="45807425"))


def test_zero_value_cannot_be_listed() -> None:
    assert routes(replace(ITEM, value=0)) == {}
