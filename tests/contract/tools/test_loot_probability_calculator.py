"""Compare the actual Unity calculator with an exhaustive runtime-ladder model."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")

_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "loot_probability"


def _exhaustive_distribution(scenario: dict, target: str) -> list[float]:
    states = {(0, 0): 1.0}
    lists = scenario["lists"]
    for _ in range(scenario["rolls"]):
        next_states: defaultdict[tuple[int, int], float] = defaultdict(float)
        for (used, count), probability in states.items():
            # Independent intervals of the uniform [0,100] roll. Walking the
            # ladder for each interval reproduces the game's fall-through.
            for low, high in zip((0, 0.33, 2.3, 7, 15, 70), (0.33, 2.3, 7, 15, 70, 100), strict=True):
                roll = (low + high) / 2
                selected = next(
                    (
                        tier
                        for tier, threshold in enumerate((0.33, 2.3, 7, 15, 70))
                        if roll < threshold and lists[tier] and (tier == 4 or used < scenario["cap"])
                    ),
                    None,
                )
                interval_probability = probability * (high - low) / 100
                if selected is None:
                    next_states[used, count] += interval_probability
                    continue
                if selected == 4:
                    pools = ((lists[4], 0.9), (scenario["world"], 0.1))
                else:
                    pools = ((lists[selected], 1.0),)
                for pool, share in pools:
                    for item in pool:
                        next_states[used + (selected < 4), count + (item == target)] += (
                            interval_probability * share / len(pool)
                        )
        states = dict(next_states)
    result = [0.0] * (scenario["rolls"] + 1)
    for (_, count), probability in states.items():
        result[count] += probability
    return result


def test_calculator_matches_runtime_outcomes(
    tmp_path: Path,
    dotnet_build: Callable[..., None],
) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "LootProbabilityFixture.dll")],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    for scenario in payload["scenarios"]:
        eligible_lists = scenario["lists"] + ([scenario["world"]] if scenario["lists"][4] else [])
        eligible_items = {item for pool in eligible_lists for item in pool if item is not None}
        assert scenario["distributions"].keys() == eligible_items, scenario["name"]
        for item, actual in scenario["distributions"].items():
            expected = _exhaustive_distribution(scenario, item)
            assert actual[: len(expected)] == pytest.approx(expected, abs=1e-12), (scenario["name"], item)
            assert sum(actual) == pytest.approx(1.0, abs=1e-12)
            assert all(value >= -1e-12 for value in actual)
            assert all(value == pytest.approx(0.0, abs=1e-12) for value in actual[len(expected) :])
    # Actual and guaranteed Bread contribute two copies before the ordinary roll;
    # both normal Common and world substitution hit the very same item index.
    assert payload["fixedAndGuaranteed"]["Bread"] == pytest.approx([0, 0, 0.3, 0.7])
