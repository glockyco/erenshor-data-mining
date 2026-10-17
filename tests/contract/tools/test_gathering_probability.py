"""Execute actual gathering listeners against exhaustive mining and raw water outcomes."""

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
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "gathering_probability"


def test_gathering_listeners_preserve_runtime_outcomes(tmp_path: Path, dotnet_build: Callable[..., None]) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "GatheringProbabilityFixture.dll")], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    assert len(payload["mining"]) == 250
    for scenario in payload["mining"]:
        expected: defaultdict[str, float] = defaultdict(float)
        for roll in range(100):
            if roll >= 96:
                pool = scenario["legend"]
            elif roll >= 75:
                pool = scenario["rare"]
            elif roll < 20:
                pool = [scenario["guarantee"]]
            else:
                pool = scenario["common"]
            for item in pool or [scenario["guarantee"]]:
                if item is not None:
                    expected[item] += 1 / max(1, len(pool))
        actual = {row["ItemStableKey"]: row["DropChance"] for row in scenario["rows"]}
        assert actual == pytest.approx(dict(expected), abs=2e-5), scenario
    for missing in ("noManagerFailure", "noManagerItemFailure"):
        assert payload[missing] == (
            "Mining node fixture has no resolvable guarantee item. "
            "Export requires its serialized guarantee or an available GameManager.GuaranteeMine."
        )
    assert payload["serializedWithoutManager"] == [
        {
            "MiningNodeStableKey": "fixture",
            "ItemStableKey": "item:serialized guarantee",
            "DropChance": 100,
        }
    ]
    # The raw listener must capture identities and null/duplicate slots, not make
    # synthetic map keys or combine bonus chances while Unity loads scenes.
    assert payload["water"] == [
        {"WaterStableKey": "fixture", "Type": "DayFishable", "Position": position, "ItemStableKey": key}
        for position, key in enumerate(["item:fish", "item:fish", None, "item:gen - torn map top right"])
    ]
