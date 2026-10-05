from __future__ import annotations

from erenshor.application.processor.npc_spawn import SpawnConstants, balanced_hp, spawn_attack

CONSTANTS = SpawnConstants(
    server_hp_mod=1.0, hp_scale=1.3, under35_hp_scale=1.75, under8_hp_scale=1.1, damage_balance_factor=1.1
)


def _attack(base: int, before: int, after: int, *, stats_first: bool, floors: bool = True) -> int:
    return spawn_attack(
        base,
        before,
        after,
        stats_starts_first=stats_first,
        floors_at_level=floors,
        damage_balance_factor=CONSTANTS.damage_balance_factor,
    )


def test_stats_first_floors_at_the_level_before_the_balance_factor() -> None:
    # Observed in game on 2026-10-05: level 20, attack 0 before Start gives 22
    # on Ancient Horror, Ancient Demon, A Grizzly Bear, and A Seafiend Spirtist,
    # whatever level the variance then rolls.
    assert _attack(0, 20, 19, stats_first=True) == 22
    assert _attack(0, 20, 21, stats_first=True) == 22


def test_npc_first_floors_at_the_level_after_the_variance() -> None:
    # Observed in game on 2026-10-05: Ancient Skeleton, A Rock Minion, and
    # Alpha Wolf end with the attack equal to their rolled level.
    assert _attack(0, 20, 19, stats_first=False) == 19
    assert _attack(0, 20, 21, stats_first=False) == 21


def test_attack_above_the_level_keeps_the_balance_factor_in_either_order() -> None:
    assert _attack(40, 20, 20, stats_first=True) == 44
    assert _attack(40, 20, 20, stats_first=False) == 44


def test_hand_set_resistances_skip_the_level_floor() -> None:
    assert _attack(5, 20, 20, stats_first=True, floors=False) == 6
    assert _attack(5, 20, 20, stats_first=False, floors=False) == 6
    assert _attack(0, 20, 20, stats_first=False, floors=False) == 1


def test_balanced_hp_switches_multiplier_between_levels_7_and_8_and_after_36() -> None:
    assert balanced_hp(600, 7, CONSTANTS) == 858
    assert balanced_hp(600, 8, CONSTANTS) == 1365
    assert balanced_hp(600, 36, CONSTANTS) == 1365
    assert balanced_hp(600, 37, CONSTANTS) == 780
