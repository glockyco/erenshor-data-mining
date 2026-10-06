from __future__ import annotations

import pytest

from erenshor.application.processor.npc_spawn import (
    SpawnConstants,
    StartLevels,
    armor_class,
    attack_ability,
    balanced_hp,
    spawn_attack,
    start_levels,
    start_order,
    starts_before,
    training_dummy_level,
)

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


def test_attack_ability_bonus_starts_at_level_20_and_tops_out_at_level_40() -> None:
    assert attack_ability(19, 1.0) == 820
    assert attack_ability(20, 1.0) == 860
    assert attack_ability(30, 1.0) == pytest.approx(1260 * 1.165, rel=1e-6)
    assert attack_ability(40, 1.0) == pytest.approx(1660 * 1.33, rel=1e-6)
    assert attack_ability(50, 1.0) == pytest.approx(2060 * 1.33, rel=1e-6)
    assert attack_ability(1, 1.5) == 150


def test_hard_set_ac_replaces_the_level_and_the_class_scales_it() -> None:
    assert armor_class(10, 50, 1.0) == 50
    assert armor_class(10, 0, 1.1) == 165


def test_a_training_dummy_takes_the_player_level_below_42_and_42_above() -> None:
    assert training_dummy_level(1) is None
    assert training_dummy_level(41) is None
    assert training_dummy_level(42) == 42
    assert training_dummy_level(50) == 42


def test_a_start_after_the_training_dummy_sees_the_level_it_gave() -> None:
    assert start_levels(("TestDummy", "Stats", "NPC"), 1, 20) == StartLevels(npc=20, stats=20, final=20)
    assert start_levels(("NPC", "Stats", "TestDummy"), 1, 20) == StartLevels(npc=1, stats=1, final=20)
    assert start_levels(("Stats", "NPC"), 7, None) == StartLevels(npc=7, stats=7, final=7)
    with pytest.raises(ValueError, match="takes the player's level"):
        start_levels(("TestDummy", "Stats", "NPC"), 1, None)


def test_instantiated_prefabs_start_in_component_list_order() -> None:
    order = start_order("Stats,NPC", None, None)

    assert starts_before(order, "Stats", "NPC")


def test_scene_characters_start_in_file_id_order_and_reverse_it_when_activated_later() -> None:
    # Observed in game on 2026-10-05: Amethi Plazzo lists Stats first but its
    # file IDs put NPC first, and it started NPC first. A pocket vendor of the
    # Reliquary with the same orders, activated with its room, started Stats first.
    assert not starts_before(start_order("Stats,NPC", "NPC,Stats", True), "Stats", "NPC")
    assert starts_before(start_order("Stats,NPC", "NPC,Stats", False), "Stats", "NPC")
    assert start_order("NPC,Stats,TestDummy", "NPC,Stats,TestDummy", False) == ("TestDummy", "Stats", "NPC")
