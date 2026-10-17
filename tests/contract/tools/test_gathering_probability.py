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
    from typing import Any

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "gathering_probability"
_NODE_KEY = "mining:fixture"
_FALLBACK_KEY = "GameManager.GuaranteeMine"


def _slots(guarantee: str | None, **pools: list[str | None]) -> list[dict[str, object]]:
    return [
        {"MiningNodeStableKey": _NODE_KEY, "Pool": pool, "Position": position, "ItemStableKey": key}
        for pool, keys in {"guarantee": [guarantee], **pools}.items()
        for position, key in enumerate(keys)
    ]


def _chances(output: dict[str, Any]) -> dict[str, float]:
    rows = output["rows"]
    assert len({row["ItemStableKey"] for row in rows}) == len(rows)
    assert all(row["MiningNodeStableKey"] == _NODE_KEY for row in rows)
    return {row["ItemStableKey"]: row["DropChance"] for row in rows}


def _single_write(output: dict[str, Any]) -> None:
    assert output["transactions"] == 1
    assert output["mutations"] > 0
    assert output["mutations"] == output["afterFirstFinish"]


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
        assert _chances(scenario) == pytest.approx(dict(expected), rel=0, abs=1e-12), scenario
        assert scenario["slots"] == _slots(
            scenario["nativeGuarantee"], Common=scenario["common"], Rare=scenario["rare"], Legend=scenario["legend"]
        )
        assert len(scenario["nodes"]) == 1
        node = scenario["nodes"][0]
        assert node["StableKey"] == _NODE_KEY
        for tier in ("Common", "Rare", "Legend"):
            assert node[f"{tier}Count"] == len(scenario[tier.lower()])
        assert scenario["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": "item:global guarantee"}]
        _single_write(scenario)

    # These rows come through both actual OnAssetFound overloads, then survive
    # clearing pools, changing item identities and discarding scene references.
    native = payload["native"]
    assert payload["nativeManagerFirst"] == native
    _single_write(native)
    assert native["nodes"] == [
        {
            "StableKey": _NODE_KEY,
            "Scene": "fixture",
            "X": 0,
            "Y": 0,
            "Z": 0,
            "NPCName": "deposit",
            "RespawnTime": 73.5,
            "CommonCount": 7,
            "RareCount": 3,
            "LegendCount": 3,
        }
    ]
    assert native["slots"] == _slots(
        "item:native guarantee",
        Common=["item:a", None, "item:a", "item:b", "item:c", "item:d", "item:e"],
        Rare=["item:rare", None, "item:rare"],
        Legend=["item:legend", "item:a", None],
    )
    assert native["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": "item:global guarantee"}]
    identities = {row["ItemStableKey"] for row in native["slots"] if row["ItemStableKey"] is not None}
    assert identities == {
        "item:native guarantee",
        "item:a",
        "item:b",
        "item:c",
        "item:d",
        "item:e",
        "item:rare",
        "item:legend",
    }
    chances = _chances(native)
    assert chances == pytest.approx(
        {
            "item:native guarantee": 20,
            "item:a": 2 * 55 / 7 + 4 / 3,
            "item:b": 55 / 7,
            "item:c": 55 / 7,
            "item:d": 55 / 7,
            "item:e": 55 / 7,
            "item:rare": 14,
            "item:legend": 4 / 3,
        },
        rel=0,
        abs=1e-12,
    )
    # Null slots keep their share and the native fallback is not an outcome when
    # the node has its own guarantee. Seven-way rates must not be float-rounded.
    assert sum(chances.values()) == pytest.approx(100 - 55 / 7 - 21 / 3 - 4 / 3, rel=0, abs=1e-12)
    assert abs(chances["item:b"] - round(chances["item:b"], 6)) > 1e-9

    serialized = payload["serializedWithNullFallback"]
    _single_write(serialized)
    assert _chances(serialized) == {"item:serialized guarantee": 100}
    assert serialized["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": None}]
    assert serialized["slots"] == _slots("item:serialized guarantee", Common=[], Rare=[], Legend=[])
    fallback = payload["fallbackSnapshot"]
    _single_write(fallback)
    assert _chances(fallback) == {"item:global guarantee": 100}
    assert fallback["slots"] == _slots(None, Common=[], Rare=[], Legend=[])
    assert fallback["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": "item:global guarantee"}]
    assert all(fallback["nodes"][0][f"{tier}Count"] == 0 for tier in ("Common", "Rare", "Legend"))

    failures = payload["failures"]
    assert failures["missing_manager"]["error"] == (
        "Mining export requires exactly one native GameManager component, found 0"
    )
    assert failures["multiple_managers"]["error"] == (
        "Mining export requires exactly one native GameManager component, found 2"
    )
    assert failures["null_fallback_required"]["error"] == (
        f"Mining node {_NODE_KEY} requires GameManager.GuaranteeMine because its native guarantee is null, "
        "but the captured fallback is null"
    )
    for tier in ("Common", "Rare", "Legend"):
        failure = failures[f"null_{tier.lower()}"]
        assert failure["error"] == (
            f"Mining node {_NODE_KEY} requires a non-null native MiningNode.{tier} list to derive Mine outcomes"
        )
        assert len(failure["captured"]) == 1
        for other in ("Common", "Rare", "Legend"):
            assert failure["captured"][0][f"{other}Count"] == (None if other == tier else 0)
    assert failures["all_null_lists"]["error"] == failures["null_common"]["error"]
    assert all(
        failures["all_null_lists"]["captured"][0][f"{tier}Count"] is None for tier in ("Common", "Rare", "Legend")
    )
    for failure in failures.values():
        output = failure["output"]
        assert output["mutations"] == output["afterFirstFinish"] == output["transactions"] == 0
        assert output["nodes"] == output["rows"] == output["slots"] == output["fallback"] == []

    reset = payload["reset"]
    assert reset["transactions"] == 2
    assert reset["mutations"] == reset["afterFirstFinish"]
    assert len(reset["nodes"]) == 1
    assert reset["nodes"][0]["StableKey"] == _NODE_KEY
    assert reset["slots"] == _slots(None, Common=[], Rare=[], Legend=[])
    assert reset["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": "item:reset fallback"}]
    assert _chances(reset) == {"item:reset fallback": 100}

    # A shared consumer discovers each host before capture. Keys come from the
    # actual resolver, including its native duplicate tracker, not suffix guesses.
    shared = payload["sharedIdentity"]
    expected_keys = shared["expected"]
    assert len(expected_keys) == len(set(expected_keys)) == 3
    assert shared["afterReset"] == expected_keys
    assert len(shared["rounds"]) == 2
    for scan, round_output in enumerate(shared["rounds"], start=1):
        assert round_output["before"] == expected_keys
        assert round_output["repeated"] == [key for key in expected_keys for _ in range(2)]
        assert round_output["afterCapture"] == expected_keys
        assert round_output["afterFinish"] == expected_keys
        captured = round_output["output"]
        assert captured["transactions"] == scan
        assert captured["mutations"] == captured["afterFirstFinish"]
        assert [node["StableKey"] for node in captured["nodes"]] == expected_keys
        assert captured["slots"] == [
            {"MiningNodeStableKey": key, "Pool": "guarantee", "Position": 0, "ItemStableKey": None}
            for key in expected_keys
        ]
        assert captured["rows"] == [
            {"MiningNodeStableKey": key, "ItemStableKey": "item:global guarantee", "DropChance": 100}
            for key in expected_keys
        ]
        assert captured["fallback"] == [{"SourceKey": _FALLBACK_KEY, "ItemStableKey": "item:global guarantee"}]

    # Raw water rows retain the original day/night identities, duplicate and null
    # positions, including the global-replacement item rather than synthetic keys.
    assert payload["water"] == [
        {"WaterStableKey": "fixture", "Type": kind, "Position": position, "ItemStableKey": key}
        for kind, keys in (
            ("DayFishable", ["item:fish", "item:fish", None, "item:gen - torn map top right"]),
            ("NightFishable", [None, "item:night fish", "item:gen - torn map top right"]),
        )
        for position, key in enumerate(keys)
    ]
