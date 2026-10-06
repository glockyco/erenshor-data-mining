"""Effective stats of training dummies and other characters whose level follows the player."""

from __future__ import annotations

import pytest

from erenshor.application.processor.characters import _effective_stats
from erenshor.application.processor.npc_spawn import SpawnConstants

CONSTANTS = SpawnConstants(
    server_hp_mod=1.0, hp_scale=1.3, under35_hp_scale=1.75, under8_hp_scale=1.1, damage_balance_factor=1.1
)
MITIGATIONS = {"DefaultNPC": 1.0}


def _reliquary_dummy(
    level: int, hand_set_ac: int, by_file_id: str, *, hand_set_resistances: int = 0
) -> dict[str, object]:
    """A dummy of a Reliquary room, which the room activates after the scene loads."""
    return {
        "HasStats": 1,
        "IsNPC": 1,
        "Level": level,
        "BaseHP": 100_000_000,
        "BaseAtkDmg": 0,
        "HardSetAC": 0,
        "HandSetResistances": hand_set_resistances,
        "BaseMR": 35,
        "BaseER": 35,
        "BasePR": 35,
        "BaseVR": 35,
        "ArmorPenMult": 1.0,
        "ClassResourceName": None,
        "TestDummyHandSetAC": hand_set_ac,
        "StartComponentsListed": by_file_id,
        "StartComponentsByFileId": by_file_id,
        "IsActiveAtLoad": False,
    }


def _stats(row: dict[str, object], *, is_treasure_guardian: bool = False) -> dict[str, object]:
    return _effective_stats(row, CONSTANTS, MITIGATIONS, is_treasure_guardian=is_treasure_guardian)


def test_a_dummy_that_starts_first_has_the_health_and_ac_of_the_player_level() -> None:
    # In game on 2026-10-05, a Stone Training dummy had 143,000,000 health and
    # AC 75 at player level 5, and 227,499,984 health and AC 300 at level 20.
    stats = _stats(_reliquary_dummy(1, 400, "NPC,Stats,TestDummy"))

    assert stats["level_scales_with_player"] == 1
    assert stats["effective_hp"] is None
    assert stats["effective_ac"] is None
    assert stats["ac_per_player_level"] == 15
    assert stats["effective_min_mr"] is None


def test_a_dummy_that_starts_last_keeps_the_health_and_resists_of_its_prefab_level() -> None:
    # In game on 2026-10-05, the Wood Training dummy had 143,000,000 health
    # at player levels 5 and 20.
    stats = _stats(_reliquary_dummy(1, 0, "TestDummy,Stats,NPC"))

    assert stats["level_scales_with_player"] == 1
    assert stats["effective_hp"] == 143_000_000
    assert stats["ac_per_player_level"] == 15
    assert (stats["effective_min_mr"], stats["effective_max_mr"]) == (0, 1)


def test_a_level_42_dummy_keeps_its_level_and_fixed_stats() -> None:
    # In game on 2026-10-05, the Expert Training dummy stayed at level 42 with
    # 129,999,992 health and AC 630 at player levels 5 and 20.
    stats = _stats(_reliquary_dummy(42, 1000, "NPC,Stats,TestDummy", hand_set_resistances=1))

    assert stats["level_scales_with_player"] == 0
    assert stats["effective_hp"] == 129_999_992
    assert stats["effective_ac"] == 630
    assert stats["ac_per_player_level"] is None


def test_a_treasure_guardian_has_no_fixed_stats() -> None:
    row = _reliquary_dummy(8, 0, "Stats,NPC") | {"TestDummyHandSetAC": None, "StartComponentsByFileId": None}

    stats = _stats(row, is_treasure_guardian=True)

    assert stats["level_scales_with_player"] == 1
    assert stats["effective_hp"] is None
    assert stats["effective_ac"] is None
    assert stats["effective_base_atk_dmg"] is None


def test_a_dummy_that_would_spawn_with_its_hand_set_ac_stops_the_build() -> None:
    # Active at load, TestDummy starts after Stats and its hand-set AC stays,
    # which the infobox text does not describe.
    row = _reliquary_dummy(1, 400, "NPC,Stats,TestDummy") | {"IsActiveAtLoad": True, "StableKey": "character:dummy"}

    with pytest.raises(ValueError, match="spawns with its hand-set AC"):
        _stats(row)
