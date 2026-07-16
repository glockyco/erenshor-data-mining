"""Behavioral coverage for the build-derived physical critical model."""

from collections.abc import Callable
from itertools import pairwise
from math import isclose, nan
from typing import cast

import pytest

from erenshor.tools.critical_strike_model import (
    RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER,
    STANDARD_CRITICAL_MULTIPLIER,
    CriticalProfile,
    crippling_blow_expected_critical_multiplier,
    critical_hit_chance,
    critical_opportunities,
    expected_damage_multiplier,
)


@pytest.mark.parametrize(
    ("dexterity", "proficiency", "expected"),
    (
        (0, 12, 1),
        (8, 12, 1),
        (9, 12, 2),
        (100, 12, 13),
        (300, 21, 63),
        (900, 13, 117),
    ),
)
def test_critical_opportunities_match_single_precision_loop_bound(
    dexterity: int,
    proficiency: int,
    expected: int,
) -> None:
    assert critical_opportunities(dexterity, proficiency) == expected


@pytest.mark.parametrize(
    ("proficiency", "expected"),
    (
        (10, 0.0427777777777778),
        (40, 0.23916666666666678),
    ),
)
def test_ordinary_unsaturated_chance_uses_level_and_proficiency(proficiency: int, expected: float) -> None:
    assert isclose(critical_hit_chance(35, 100, proficiency), expected)


def test_critical_chance_uses_single_precision_opportunity_count() -> None:
    chance = critical_hit_chance(35, 300, 21)

    assert isclose(chance, 63 * (35 / 79) / 100)


def test_unsaturated_class_profiles_add_expected_trials() -> None:
    ordinary = critical_hit_chance(35, 100, 12)
    stormcaller = critical_hit_chance(35, 100, 12, CriticalProfile.STORMCALLER)
    windblade = critical_hit_chance(35, 100, 12, CriticalProfile.WINDBLADE)

    assert isclose(ordinary, 0.05170454545454546)
    assert isclose(stormcaller, 1.4 * ordinary)
    assert isclose(windblade, 2.0 * ordinary)


def test_critical_hit_chance_is_bounded_and_monotone_through_supported_dexterity() -> None:
    dexterity_values = (0, 100, 200, 600, 1200)
    for profile in CriticalProfile:
        for proficiency in (1, 12, 40):
            chances = [critical_hit_chance(35, dexterity, proficiency, profile) for dexterity in dexterity_values]
            assert all(0.0 <= chance <= 1.0 for chance in chances)
            assert all(previous <= current for previous, current in pairwise(chances))


def test_windblade_saturation_uses_capped_distribution() -> None:
    chance = critical_hit_chance(35, 200, 40, CriticalProfile.WINDBLADE)

    assert isclose(chance, 0.9385228688600923, rel_tol=0, abs_tol=1e-15)
    assert chance < 0.945


def test_level_scales_linearly_before_counter_cap() -> None:
    level_zero = critical_hit_chance(0, 100, 10)
    level_one = critical_hit_chance(1, 100, 10)
    level_thirty_five = critical_hit_chance(35, 100, 10)

    assert level_zero == 0.0
    assert isclose(level_thirty_five, 35.0 * level_one)


@pytest.mark.parametrize(
    ("chance", "multiplier", "expected"),
    (
        (0.0, STANDARD_CRITICAL_MULTIPLIER, 1.0),
        (0.5, STANDARD_CRITICAL_MULTIPLIER, 1.25),
        (1.0, RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER, 1.3),
    ),
)
def test_expected_damage_multiplier_uses_weighted_outcomes(chance: float, multiplier: float, expected: float) -> None:
    assert isclose(expected_damage_multiplier(chance, multiplier), expected)


def test_crippling_blow_conditional_multiplier() -> None:
    assert isclose(crippling_blow_expected_critical_multiplier(), 1.65)


@pytest.mark.parametrize(
    ("call", "args"),
    (
        (critical_hit_chance, (-1, 100, 10)),
        (critical_hit_chance, (36, 100, 10)),
        (critical_opportunities, (100, -1)),
        (critical_hit_chance, (35, -1, 10)),
        (critical_hit_chance, (35, 100, 0)),
        (critical_hit_chance, (35, 100, 41)),
        (critical_opportunities, (100, 0)),
        (critical_opportunities, (100, 41)),
    ),
)
def test_invalid_integer_ranges_raise_value_error(call: Callable[..., object], args: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        _ = call(*args)


@pytest.mark.parametrize(
    ("call", "args"),
    (
        (critical_hit_chance, (True, 100, 10)),
        (critical_hit_chance, (35, 100.0, 10)),
        (critical_hit_chance, (35, 100, True)),
        (critical_opportunities, (True, 10)),
        (critical_opportunities, (100, 10.0)),
    ),
)
def test_non_integer_inputs_raise_type_error(call: Callable[..., object], args: tuple[object, ...]) -> None:
    with pytest.raises(TypeError):
        _ = call(*args)


def test_non_enum_profile_raises_value_error() -> None:
    with pytest.raises(ValueError):
        _ = critical_hit_chance(35, 100, 10, cast("CriticalProfile", cast("object", "ordinary")))


@pytest.mark.parametrize("chance", (-0.01, 1.01, nan))
def test_invalid_chance_raises_value_error(chance: float) -> None:
    with pytest.raises(ValueError):
        _ = expected_damage_multiplier(chance, STANDARD_CRITICAL_MULTIPLIER)


@pytest.mark.parametrize("multiplier", (-0.01, nan))
def test_invalid_critical_multiplier_raises_value_error(multiplier: float) -> None:
    with pytest.raises(ValueError):
        _ = expected_damage_multiplier(0.5, multiplier)


@pytest.mark.parametrize(
    ("chance", "multiplier"),
    (("0.5", 1.5), (0.5, "1.5")),
)
def test_non_real_damage_inputs_raise_type_error(chance: object, multiplier: object) -> None:
    with pytest.raises(TypeError):
        _ = expected_damage_multiplier(cast("float", chance), cast("float", multiplier))
