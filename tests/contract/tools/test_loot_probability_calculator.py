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
    from typing import Any

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")

_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "loot_probability"


def _exhaustive_distribution(scenario: dict[str, Any], target: str) -> list[float]:
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
                pools: tuple[tuple[list[str | None], float], ...]
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
    precision = {row["ItemStableKey"]: row for row in payload["listenerPrecision"]}
    chance = 0.0033 / 7
    for index in range(7):
        row = precision[f"ultra:{index}"]
        assert row["DropProbability"] == pytest.approx(chance * 100, abs=1e-12)
        assert row["DropProbability"] != round(row["DropProbability"], 2)
        assert row["ExpectedPerKill"] == pytest.approx(chance, abs=1e-15)
        assert row["ExpectedPerKill"] != round(row["ExpectedPerKill"], 4)
        distribution = json.loads(row["DropCountDistribution"])
        assert all(isinstance(value, int | float) and not isinstance(value, bool) for value in distribution)
        assert distribution == pytest.approx([1 - chance, chance, 0], abs=1e-15)
    assert json.loads(precision["fixed"]["DropCountDistribution"]) == [0, 1, 0]
    unknown = payload["listenerUnknown"]
    assert len(unknown) == 1
    assert unknown[0]["ItemStableKey"] == "unmodeled"
    assert unknown[0]["DropProbability"] is None
    assert unknown[0]["ExpectedPerKill"] is None
    assert unknown[0]["DropCountDistribution"] is None
    zero = payload["listenerZero"]
    assert len(zero) == 1
    assert zero[0]["DropProbability"] == 0
    assert zero[0]["ExpectedPerKill"] == 0
    assert json.loads(zero[0]["DropCountDistribution"]) == [1]
    _assert_native_capture(payload["nativeCapture"])
    _assert_native_capture(payload["enabledNativeCapture"], enabled=True)
    _assert_mining_capture(payload["miningCapture"])
    _assert_disabled_capture(payload["disabledCapture"])
    _assert_callback_validation(payload["callbackValidation"])


def _assert_native_capture(capture: dict[str, Any], *, enabled: bool = False) -> None:
    bound_key = "character:snapshot:script:LootTable:0"
    other_key = "character:other:script:LootTable:0"
    unbound0 = "object:fixture:unbound[4]:script:LootTable:0"
    unbound1 = "object:fixture:unbound[4]:script:LootTable:1"
    prefab_key = "asset:fixture-guid:42:script:LootTable:0"
    sources = {row["StableKey"]: row for row in capture["sources"]}
    assert len(capture["sources"]) == 5
    assert sources.keys() == {bound_key, other_key, unbound0, unbound1, prefab_key}
    assert capture["transactions"] == 1
    assert capture["dropSourceForeignKey"] == {"record": "LootTableSourceRecord", "field": "StableKey"}
    pools = (
        "UltraRareDrop",
        "LegendaryDrop",
        "RareDrop",
        "UncommonDrop",
        "CommonDrop",
        "GuaranteeOneDrop",
        "ActualDrops",
    )
    bound = sources[bound_key]
    assert bound["CharacterStableKey"] == "character:snapshot"
    assert bound["ComponentIndex"] == 0
    assert bound["ComponentIsEnabled"] is enabled
    assert (bound["MaxNumberDrops"], bound["MaxNonCommonDrops"], bound["NumberOfGuaranteedDrops"]) == (2, 1, 2)
    assert [bound[f"{pool}Count"] for pool in pools] == [3] * 7
    for key, counts, config, component in (
        (unbound0, [None, 0, None, 0, None, 0, None], (-3, -2, -1), 0),
        (unbound1, [0, None, 0, None, 0, None, 3], (7, 5, 3), 1),
    ):
        source = sources[key]
        assert source["CharacterStableKey"] is None
        assert source["ComponentIsEnabled"] is True
        assert source["ComponentIndex"] == component
        assert [source[f"{pool}Count"] for pool in pools] == counts
        assert (source["MaxNumberDrops"], source["MaxNonCommonDrops"], source["NumberOfGuaranteedDrops"]) == config
    assert sources[prefab_key]["CharacterStableKey"] is None
    assert all(source["MiningNodeStableKey"] is None for source in sources.values())
    expected_slots = [
        (bound_key, pool, position, item)
        for pool in pools
        for position, item in enumerate(["snapshot:item", None, "snapshot:item"])
    ]
    expected_slots += [
        (unbound1, "ActualDrops", position, item)
        for position, item in enumerate(["unbound:actual", None, "unbound:actual"])
    ]
    expected_slots += [
        (prefab_key, "ActualDrops", 0, "prefab:actual"),
        (other_key, "UltraRareDrop", 0, "other:zero"),
    ]
    actual_slots = [
        (row["LootTableStableKey"], row["Pool"], row["Position"], row["ItemStableKey"]) for row in capture["slots"]
    ]
    assert len(actual_slots) == len(expected_slots)
    assert set(actual_slots) == set(expected_slots)
    assert capture["world"] == [
        {"Position": 0, "ItemStableKey": "snapshot:world"},
        {"Position": 1, "ItemStableKey": None},
        {"Position": 2, "ItemStableKey": "snapshot:world"},
    ]
    drops = {(row["LootTableStableKey"], row["ItemStableKey"]): row for row in capture["drops"]}
    assert len(capture["drops"]) == (3 if enabled else 2)
    expected_drops = {(bound_key, "snapshot:item"), (other_key, "other:zero")}
    if enabled:
        expected_drops.add((bound_key, "snapshot:world"))
    assert drops.keys() == expected_drops
    for (source_key, _), row in drops.items():
        assert row["CharacterStableKey"] == sources[source_key]["CharacterStableKey"]
        distribution = json.loads(row["DropCountDistribution"])
        assert all(isinstance(value, int | float) and not isinstance(value, bool) for value in distribution)
        assert sum(distribution) == pytest.approx(1, abs=1e-12)
        assert row["DropProbability"] == pytest.approx((1 - distribution[0]) * 100, abs=1e-12)
        assert row["ExpectedPerKill"] == pytest.approx(
            sum(count * probability for count, probability in enumerate(distribution)), abs=1e-12
        )
    captured_item = drops[bound_key, "snapshot:item"]
    assert captured_item["IsUnique"] is True
    assert captured_item["IsVisible"] is True
    assert captured_item["Zone"] == "CapturedZone"
    assert all(
        captured_item[flag]
        for flag in ("IsActual", "IsGuaranteed", "IsCommon", "IsUncommon", "IsRare", "IsLegendary", "IsUltraRare")
    )
    if enabled:
        assert drops[bound_key, "snapshot:world"]["IsCommonWorldItem"] is True
    else:
        assert captured_item["IsCommonWorldItem"] is False
        assert json.loads(captured_item["DropCountDistribution"]) == [0, 0, 1, 0]
        assert captured_item["DropProbability"] == 100
        assert captured_item["ExpectedPerKill"] == 2
    assert json.loads(drops[other_key, "other:zero"]["DropCountDistribution"]) == [1]
    assert drops[other_key, "other:zero"]["DropProbability"] == 0
    assert drops[other_key, "other:zero"]["ExpectedPerKill"] == 0
    if enabled:
        world_distribution = json.loads(drops[bound_key, "snapshot:world"]["DropCountDistribution"])
        expected_world = _exhaustive_distribution(
            {
                "lists": [["snapshot:item", None, "snapshot:item"] for _ in range(5)],
                "world": ["snapshot:world", None, "snapshot:world"],
                "rolls": 3,
                "cap": 1,
            },
            "snapshot:world",
        )
        assert world_distribution == pytest.approx(expected_world + [0] * 5, abs=1e-12)


def _assert_callback_validation(cases: list[dict[str, Any]]) -> None:
    expected_errors = {
        "missing_manager": "Expected exactly one GameManager component, found 0",
        "two_managers": "Expected exactly one GameManager component, found 2",
        "null_world": "GameManager.CommonWorldItems is null",
        "empty_world": "GameManager.CommonWorldItems is empty",
        "ambiguous_character_components": (
            "Unsupported LootTable binding for 'character:ambiguous': 2 native LootTable components. "
            "Runtime GetComponent<LootTable>() does not prove which table supplies this character's loot."
        ),
        "missing_identity": "LootTable 'fixture' has no stable scene or asset identity",
        "missing_component_index": "LootTable 'fixture' has no native component index",
        "conflicting_source": "Conflicting LootTable definitions for 'object:fixture:host[0]:script:LootTable:0'",
        "null_slot_world_completes_once": None,
    }
    assert {case["name"] for case in cases} == expected_errors.keys()
    for case in cases:
        assert case["error"] == expected_errors[case["name"]]
        assert case["transactions"] == (1 if case["error"] is None else 0)
        assert case["sources"] == []
        assert case["drops"] == []


def _assert_mining_capture(capture: dict[str, Any]) -> None:
    assert capture["characters"] == []
    assert capture["drops"] == []
    assert capture["miningForeignKey"] == {"record": "MiningNodeRecord", "field": "StableKey"}
    assert capture["characterForeignKey"] == {"record": "CharacterRecord", "field": "StableKey"}
    identities = capture["identities"]
    assert len(identities) == 2
    assert identities[0]["instanceId"] != identities[1]["instanceId"]
    assert identities[0]["key"] == "mining:FixtureZone:12:34:56"
    assert identities[1]["key"] == identities[0]["key"] + ":1"
    assert all(identity["key"] == identity["repeatedKey"] for identity in identities)
    sources = {source["StableKey"]: source for source in capture["sources"]}
    assert len(capture["sources"]) == 4
    expected_slots: list[tuple[str, str, int, str | None]] = []
    for index, identity in enumerate(identities):
        for component in range(2):
            key = f"native:mining:{index}:script:LootTable:{component}"
            source = sources[key]
            assert source["CharacterStableKey"] is None
            assert source["MiningNodeStableKey"] == identity["key"]
            assert source["ComponentIndex"] == component
            assert source["ComponentIsEnabled"] is (component == 0)
            pools: dict[str, list[str | None]] = {
                "UltraRareDrop": ["mining:random", None] if component == 0 else [],
                "LegendaryDrop": [],
                "RareDrop": [],
                "UncommonDrop": [],
                "CommonDrop": ["mining:common" if component == 0 else "mining:disabled"],
                "GuaranteeOneDrop": ["mining:guaranteed"] if component == 0 else [],
                "ActualDrops": ["mining:actual", None, "mining:actual"] if component == 0 else [],
            }
            for pool, items in pools.items():
                assert source[f"{pool}Count"] == len(items)
                expected_slots.extend((key, pool, position, item) for position, item in enumerate(items))
            assert (source["MaxNumberDrops"], source["MaxNonCommonDrops"], source["NumberOfGuaranteedDrops"]) == (
                (4, 2, 3) if component == 0 else (0, 0, 0)
            )
    assert sources.keys() == {
        f"native:mining:{index}:script:LootTable:{component}" for index in range(2) for component in range(2)
    }
    slots = [
        (slot["LootTableStableKey"], slot["Pool"], slot["Position"], slot["ItemStableKey"]) for slot in capture["slots"]
    ]
    assert len(slots) == len(expected_slots)
    assert set(slots) == set(expected_slots)


def _assert_disabled_capture(capture: dict[str, Any]) -> None:
    assert capture["world"] == [{"Position": 0, "ItemStableKey": "disabled:global"}]
    sources = {source["CharacterStableKey"]: source for source in capture["sources"]}
    assert len(capture["sources"]) == 2
    expected_slots: list[tuple[str, str, int, str | None]] = []
    actual_cases: tuple[tuple[str, list[str | None]], ...] = (
        ("character:preseeded", ["disabled:actual", None, "disabled:actual", "disabled:second"]),
        ("character:empty", []),
    )
    for character, actual in actual_cases:
        source = sources[character]
        assert source["StableKey"] == f"{character}:script:LootTable:0"
        assert source["ComponentIndex"] == 0
        assert source["ComponentIsEnabled"] is False
        assert source["MiningNodeStableKey"] is None
        assert (source["MaxNumberDrops"], source["MaxNonCommonDrops"], source["NumberOfGuaranteedDrops"]) == (5, 3, 4)
        pools: dict[str, list[str | None]] = {
            "UltraRareDrop": ["disabled:ultra"],
            "LegendaryDrop": ["disabled:legendary"],
            "RareDrop": ["disabled:rare"],
            "UncommonDrop": ["disabled:uncommon"],
            "CommonDrop": ["disabled:common"],
            "GuaranteeOneDrop": ["disabled:guaranteed"],
            "ActualDrops": actual,
        }
        for pool, items in pools.items():
            assert source[f"{pool}Count"] == len(items)
            expected_slots.extend((source["StableKey"], pool, position, item) for position, item in enumerate(items))
    slots = [
        (slot["LootTableStableKey"], slot["Pool"], slot["Position"], slot["ItemStableKey"]) for slot in capture["slots"]
    ]
    assert len(slots) == len(expected_slots)
    assert set(slots) == set(expected_slots)
    drops = {drop["ItemStableKey"]: drop for drop in capture["drops"]}
    assert len(capture["drops"]) == 2
    assert drops.keys() == {"disabled:actual", "disabled:second"}
    for item, count in (("disabled:actual", 2), ("disabled:second", 1)):
        drop = drops[item]
        assert drop["CharacterStableKey"] == "character:preseeded"
        assert drop["LootTableStableKey"] == "character:preseeded:script:LootTable:0"
        assert drop["DropProbability"] == 100
        assert drop["ExpectedPerKill"] == count
        expected = [0] * 5
        expected[count] = 1
        assert json.loads(drop["DropCountDistribution"]) == expected
        assert drop["IsUnique"] is (item == "disabled:actual")
        assert drop["IsActual"] is True
        assert not any(
            drop[flag]
            for flag in (
                "IsGuaranteed",
                "IsCommon",
                "IsCommonWorldItem",
                "IsUncommon",
                "IsRare",
                "IsLegendary",
                "IsUltraRare",
            )
        )
