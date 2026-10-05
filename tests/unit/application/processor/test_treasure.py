from __future__ import annotations

import pytest

from erenshor.application.processor.npc_spawn import SpawnConstants
from erenshor.application.processor.treasure import (
    CHEST_DIG_LEVELS,
    GuardianProfile,
    chest_can_be_dug_in,
    guardian_outcomes,
    guardian_scaling_row,
    min_reading_level,
)

CONSTANTS = SpawnConstants(
    server_hp_mod=1.0, hp_scale=1.3, under35_hp_scale=1.75, under8_hp_scale=1.1, damage_balance_factor=1.1
)


def _guardian(stable_key: str, *, stats_first: bool) -> GuardianProfile:
    return GuardianProfile(
        stable_key=stable_key,
        stats_starts_first=stats_first,
        hand_set_resistances=False,
        level_varies=True,
        hard_set_ac=0,
        mitigation_bonus=1.0,
    )


# Component order of build 24405256: Ancient Skeleton lists NPC first, the
# other two list Stats first.
SKELETON = _guardian("character:ancient skeleton", stats_first=False)
HORROR = _guardian("character:ancient horror", stats_first=True)
DEMON = _guardian("character:ancient demon", stats_first=True)

# Guardians observed in game on 2026-10-05: player level, guardian (None when
# not recorded), and the guardian's level, health, AC, and attack.
SAMPLES = [
    (1, HORROR, 3, 858, 45, 3),
    (4, None, 6, 1430, 90, 6),
    (8, HORROR, 9, 3640, 135, 9),
    (11, SKELETON, 9, 4095, 135, 10),
    (14, None, 13, 9555, 195, 15),
    (18, None, 16, 16380, 240, 18),
    (22, None, 20, 25025, 300, 22),
    (26, None, 23, 28779, 345, 23),
    (29, None, 27, 42998, 405, 30),
    (31, None, 28, 44590, 420, 31),
    (33, None, 34, 154700, 510, 56),
    (35, None, 35, 159250, 525, 57),
]


@pytest.mark.parametrize(("player_level", "guardian", "level", "health", "ac", "attack"), SAMPLES)
def test_every_in_game_sample_is_a_possible_outcome(
    player_level: int, guardian: GuardianProfile | None, level: int, health: int, ac: int, attack: int
) -> None:
    candidates = [guardian] if guardian else [SKELETON, HORROR, DEMON]
    outcomes = {
        (o.level, o.health, o.armor_class, o.attack)
        for candidate in candidates
        for o in guardian_outcomes(player_level, candidate, CONSTANTS)
    }
    assert (level, health, ac, attack) in outcomes


def test_scaling_row_spans_every_outcome() -> None:
    row = guardian_scaling_row(1, HORROR, CONSTANTS)

    # Level 1 sets level 3 (the minimum), and NPC.Start moves it by one.
    assert (row["level_min"], row["level_max"]) == (2, 4)
    # The guardian keeps the HP of level 3, scaled by the factor of its final level.
    assert (row["health_min"], row["health_max"]) == (858, 858)
    assert (row["ac_min"], row["ac_max"]) == (30, 60)
    # Stats.Start runs first on the Horror: it rolls the resists from level 3.
    assert (row["resist_min"], row["resist_max"]) == (2, 4)
    assert (row["attack_delay_min"], row["attack_delay_max"]) == (147, 147)


def test_npc_first_guardian_rolls_resists_from_the_level_after_the_variance() -> None:
    row = guardian_scaling_row(1, SKELETON, CONSTANTS)

    assert (row["resist_min"], row["resist_max"]) == (1, 5)


def test_level_35_guardians_skip_the_variance() -> None:
    levels = {o.level for o in guardian_outcomes(35, HORROR, CONSTANTS)}

    # Offsets -3 to +1 give 32 to 36. Below 35 NPC.Start still moves the level.
    assert levels == {31, 32, 33, 34, 35, 36}


def test_reading_pools_open_above_levels_20_and_30() -> None:
    assert min_reading_level(True, True, True) == 1
    assert min_reading_level(False, True, True) == 21
    assert min_reading_level(False, False, True) == 31
    assert min_reading_level(False, False, False) is None


@pytest.mark.parametrize(
    ("zone_min_reading_level", "chests"),
    [
        (1, ["0-10", "10-20", "20-30", "30-35"]),
        # A map read at 21 points to these zones, and the player digs at 21 or later.
        (21, ["20-30", "30-35"]),
        (31, ["30-35"]),
        (None, []),
    ],
)
def test_chest_follows_the_digging_level_after_the_reading_level(
    zone_min_reading_level: int | None, chests: list[str]
) -> None:
    dug = [
        key.removeprefix("character:treasurechest ").removesuffix(" 1")
        for key, _, high in CHEST_DIG_LEVELS
        if chest_can_be_dug_in(zone_min_reading_level, high)
    ]
    assert dug == chests
