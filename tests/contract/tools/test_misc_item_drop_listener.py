"""Execute native fossil pool and field binding capture, including the fossil SQLite query."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "misc_item_drops"


def test_misc_listener_preserves_native_slots_and_all_item_use_sources(
    tmp_path: Path, dotnet_build: Callable[..., None]
) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "MiscItemDropsFixture.dll")], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    weighted = payload["weighted"]
    assert weighted["pools"] == [
        {
            "PoolStableKey": "Misc.FossilGame",
            "SourceComponentKey": "object:fixture:misc[0]:script:Misc:0",
            "SlotCount": 4,
        }
    ]
    assert [(row["Position"], row["ItemStableKey"]) for row in weighted["slots"]] == [
        (0, "item:a"),
        (1, None),
        (2, "item:a"),
        (3, "item:b"),
    ]
    assert all(row["PoolStableKey"] == "Misc.FossilGame" for row in weighted["slots"])
    outcomes = {(row["SourceItemStableKey"], row["DroppedItemStableKey"]): row for row in weighted["outcomes"]}
    assert set(outcomes) == {
        (source, item) for source in ("item:source-a", "item:source-b") for item in ("item:a", "item:b")
    }
    for (_, item), row in outcomes.items():
        assert row["DropProbability"] == (50 if item == "item:a" else 25)
        assert row["IsGuaranteed"] is True
        assert row["PoolStableKey"] == "Misc.FossilGame"
    assert weighted["CheckedItems"] == ["item:a", "item:b"]
    for row in payload["precision"]["outcomes"]:
        expected = 100 / 3 if row["DroppedItemStableKey"] == "item:a" else 200 / 3
        assert row["DropProbability"] == pytest.approx(expected, abs=1e-12)
        assert row["DropProbability"] != round(row["DropProbability"], 2)
    all_null = payload["allNull"]
    assert all_null["pools"][0]["SlotCount"] == 2
    assert [row["ItemStableKey"] for row in all_null["slots"]] == [None, None]
    assert all_null["outcomes"] == []
    assert all_null["CheckedItems"] == []
    reset = payload["reset"]
    assert reset["pools"][0]["SlotCount"] == 2
    assert [(row["Position"], row["ItemStableKey"]) for row in reset["slots"]] == [(0, "item:b"), (1, None)]
    assert len(reset["outcomes"]) == 2
    assert all(row["DroppedItemStableKey"] == "item:b" and row["DropProbability"] == 50 for row in reset["outcomes"])
    failures = payload["failures"]
    assert set(failures) == {
        "missing_source",
        "multiple_sources",
        "null_pool",
        "empty_pool",
        "no_click_source",
        "query_failure",
        "missing_outcome",
        "non_scene_source",
    }
    assert all(row["mutations"] == 0 for row in failures.values())
    assert "found none" in failures["missing_source"]["error"]
    assert "exactly one Misc" in failures["multiple_sources"]["error"]
    assert "null or empty" in failures["null_pool"]["error"]
    assert "null or empty" in failures["empty_pool"]["error"]
    assert "No exported item" in failures["no_click_source"]["error"]
    assert failures["query_failure"]["error"] == "Fixture query failure"
    assert failures["missing_outcome"]["error"] == "Missing referenced item item:b"
    assert "placed scene object" in failures["non_scene_source"]["error"]

    # A captured field binding is separate from fossil pools and item-grant outcomes.
    bindings = payload["nativeItemBindings"]
    source_key = "object:fixture:calibration hall[2]/native host[1]:script:GameManager:0"
    for case, item_key in (
        ("nonNull", "item:serialized-native-binding"),
        ("serializedNull", None),
        ("capturedSnapshot", "item:captured-native-binding"),
    ):
        captured = bindings[case]
        snapshot = captured["snapshot"]
        assert snapshot["bindings"] == [
            {
                "BindingKey": "GameManager.PlanarShard",
                "SourceComponentKey": source_key,
                "ItemStableKey": item_key,
            }
        ]
        assert snapshot["Tables"] == ["NativeItemBindingRecord"]
        assert snapshot["QueryText"] == ""
        assert snapshot["CheckedItems"] == ([] if item_key is None else [item_key])
        assert snapshot["Mutations"] == captured["writesBeforeSecondFinish"] == 3

    binding_failures = bindings["failures"]
    assert set(binding_failures) == {
        "missing_source",
        "multiple_sources",
        "non_scene_source",
        "missing_item",
        "invalid_item_reference",
    }
    callback_errors = {
        "missing_source": None,
        "multiple_sources": "Native item bindings require exactly one GameManager component",
        "non_scene_source": "Fixture source is not a placed scene object",
        "missing_item": None,
        "invalid_item_reference": "Fixture item has no stable identity",
    }
    finish_errors = {
        "missing_source": "Native item bindings require exactly one GameManager component, found 0",
        "multiple_sources": "Native item bindings require exactly one GameManager component, found 2",
        "non_scene_source": "Native item binding snapshot is missing",
        "missing_item": "Missing referenced item item:b",
        "invalid_item_reference": "Native item binding snapshot is missing",
    }
    for case, failure in binding_failures.items():
        assert failure["callbackError"] == callback_errors[case]
        assert failure["finishErrors"] == [finish_errors[case]] * 2
        assert failure["mutationsBeforeReset"] == 0
        assert failure["tablesBeforeReset"] == []
        assert failure["checkedBeforeReset"] == (["item:b", "item:b"] if case == "missing_item" else [])
        recovered = failure["recovered"]
        assert recovered["bindings"] == [
            {
                "BindingKey": "GameManager.PlanarShard",
                "SourceComponentKey": "object:fixture:misc[0]:script:GameManager:0",
                "ItemStableKey": "item:a",
            }
        ]
        assert recovered["Mutations"] == 3
        assert recovered["Tables"] == ["NativeItemBindingRecord"]
        assert recovered["QueryText"] == ""
        assert recovered["CheckedItems"] == failure["checkedBeforeReset"] + ["item:a"]

    binding_reset = bindings["reset"]
    assert binding_reset["first"] == [
        {
            "BindingKey": "GameManager.PlanarShard",
            "SourceComponentKey": "object:fixture:misc[0]:script:GameManager:0",
            "ItemStableKey": "item:a",
        }
    ]
    assert binding_reset["second"] == [
        {
            "BindingKey": "GameManager.PlanarShard",
            "SourceComponentKey": "object:fixture:replacement[3]:script:GameManager:0",
            "ItemStableKey": None,
        }
    ]
    assert binding_reset["writesBeforeSecondFinish"] == binding_reset["writesAfterSecondFinish"] == 6
    assert binding_reset["missingSourceError"] == finish_errors["missing_source"]
    assert binding_reset["final"]["bindings"] == binding_reset["second"]
    assert binding_reset["final"]["Mutations"] == 6
    assert binding_reset["final"]["CheckedItems"] == ["item:a"]
    assert binding_reset["final"]["Tables"] == ["NativeItemBindingRecord"]
    assert binding_reset["final"]["QueryText"] == ""

    # Run the captured production query, rather than trusting the fixture database adapter's rows.
    assert weighted["QueryArguments"] == ["Break Fossil"]
    with sqlite3.connect(":memory:") as db:
        db.executescript(
            "CREATE TABLE Items(StableKey TEXT PRIMARY KEY,ItemEffectOnClickStableKey TEXT);"
            "CREATE TABLE Spells(StableKey TEXT PRIMARY KEY,SpellName TEXT);"
        )
        db.executemany(
            "INSERT INTO Spells VALUES (?,?)",
            [("spell:first", "Break Fossil"), ("spell:alias", "Break Fossil"), ("spell:other", "Different")],
        )
        db.executemany(
            "INSERT INTO Items VALUES (?,?)",
            [
                ("item:source-b", "spell:alias"),
                ("item:source-a", "spell:first"),
                ("item:unrelated", "spell:other"),
                ("item:no-spell", None),
                ("item:missing-spell", "spell:missing"),
            ],
        )
        assert db.execute(weighted["QueryText"], weighted["QueryArguments"]).fetchall() == [
            ("item:source-a",),
            ("item:source-b",),
        ]
