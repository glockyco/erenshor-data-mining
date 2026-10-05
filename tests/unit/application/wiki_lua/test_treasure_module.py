from __future__ import annotations

import pytest

from erenshor.application.wiki_lua.treasure import build_treasure_guardians_data
from erenshor.domain.value_objects.treasure import ChestWave, GuardianScaling, TreasureGuardian


def _scaling(key: str, player_level: int) -> GuardianScaling:
    return GuardianScaling(key, player_level, 2, 4, 858, 858, 3, 3, 147, 147, 30, 60, 2, 4)


class _Repository:
    def __init__(self, guardians: list[TreasureGuardian], scaling: list[GuardianScaling]) -> None:
        self._guardians = guardians
        self._scaling = scaling

    def get_treasure_guardians(self) -> list[TreasureGuardian]:
        return self._guardians

    def get_guardian_scaling(self) -> list[GuardianScaling]:
        return self._scaling

    def get_chest_waves(self) -> list[ChestWave]:
        return [ChestWave(0, 0.0, 3, 4, 5.0), ChestWave(1, 1.0, None, None, None)]


HORROR = TreasureGuardian("character:ancient horror", "Ancient Horror", "Ancient Horror")


def test_scaling_is_keyed_by_guardian_in_player_level_order() -> None:
    data = build_treasure_guardians_data(
        _Repository([HORROR], [_scaling(HORROR.stable_key, 2), _scaling(HORROR.stable_key, 1)])
    )

    scaling = data["scaling"]
    assert isinstance(scaling, dict)
    assert [row["playerLevel"] for row in scaling[HORROR.stable_key]] == [1, 2]


def test_scaling_of_a_character_that_is_no_wiki_guardian_is_left_out() -> None:
    data = build_treasure_guardians_data(
        _Repository([HORROR], [_scaling(HORROR.stable_key, 1), _scaling("character:unlisted", 1)])
    )

    scaling = data["scaling"]
    assert isinstance(scaling, dict)
    assert set(scaling) == {HORROR.stable_key}


def test_a_guardian_without_scaling_fails() -> None:
    with pytest.raises(ValueError, match="character:ancient horror"):
        build_treasure_guardians_data(_Repository([HORROR], []))
