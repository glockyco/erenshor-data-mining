from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def load_script(path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


compare = load_script("wiki-dev/parity/compare.py")


def test_identical_snapshots_have_no_divergences() -> None:
    snapshot = {
        "sidebar": {"first-link": {"color": "rgb(248, 202, 46)"}},
    }

    assert compare.compare_snapshots(snapshot, snapshot) == []


def test_value_mismatch_is_reported_with_expected_and_actual() -> None:
    baseline = {"sidebar": {"first-link": {"color": "rgb(248, 202, 46)"}}}
    actual = {"sidebar": {"first-link": {"color": "rgb(51, 102, 204)"}}}

    divergences = compare.compare_snapshots(baseline, actual)

    assert divergences == [
        compare.Divergence(
            component="sidebar",
            target="first-link",
            prop="color",
            expected="rgb(248, 202, 46)",
            actual="rgb(51, 102, 204)",
            kind="value",
        )
    ]


def test_surrounding_whitespace_does_not_cause_false_mismatch() -> None:
    baseline = {"body": {"root": {"--wiki-content-border-color": "#866806"}}}
    actual = {"body": {"root": {"--wiki-content-border-color": " #866806 "}}}

    assert compare.compare_snapshots(baseline, actual) == []


def test_missing_target_in_actual_is_reported() -> None:
    baseline = {"infobox": {"portable-shell": {"display": "block"}}}
    actual = {"infobox": {}}

    divergences = compare.compare_snapshots(baseline, actual)

    assert divergences == [
        compare.Divergence(
            component="infobox",
            target="portable-shell",
            prop="",
            expected=None,
            actual=None,
            kind="missing-target",
        )
    ]


def test_missing_property_in_actual_is_reported() -> None:
    baseline = {"table": {"header": {"color": "rgb(237, 237, 237)", "font-weight": "700"}}}
    actual = {"table": {"header": {"color": "rgb(237, 237, 237)"}}}

    divergences = compare.compare_snapshots(baseline, actual)

    assert divergences == [
        compare.Divergence(
            component="table",
            target="header",
            prop="font-weight",
            expected="700",
            actual=None,
            kind="missing-property",
        )
    ]


def test_extra_actual_targets_and_properties_are_ignored() -> None:
    baseline = {"body": {"root": {"color": "white"}}}
    actual = {
        "body": {"root": {"color": "white", "background": "black"}, "extra": {"x": "y"}},
        "unwatched": {"t": {"p": "v"}},
    }

    assert compare.compare_snapshots(baseline, actual) == []


def test_divergences_are_ordered_deterministically() -> None:
    baseline = {
        "zeta": {"t": {"p": "1"}},
        "alpha": {"t2": {"b": "1", "a": "1"}},
    }
    actual = {
        "zeta": {"t": {"p": "2"}},
        "alpha": {"t2": {"b": "2", "a": "2"}},
    }

    divergences = compare.compare_snapshots(baseline, actual)

    assert [(d.component, d.target, d.prop) for d in divergences] == [
        ("alpha", "t2", "a"),
        ("alpha", "t2", "b"),
        ("zeta", "t", "p"),
    ]


def test_baseline_round_trips_through_json(tmp_path: Path) -> None:
    snapshot = {"sidebar": {"first-link": {"color": "rgb(248, 202, 46)"}}}
    path = tmp_path / "baseline.json"

    compare.save_baseline(path, snapshot)
    loaded = compare.load_baseline(path)

    assert loaded == snapshot
    assert json.loads(path.read_text(encoding="utf-8")) == snapshot


def test_load_baseline_fails_loudly_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "baseline.json"

    try:
        compare.load_baseline(missing)
    except FileNotFoundError as error:
        assert "wiki-dev/parity_check.py --capture" in str(error)
    else:
        raise AssertionError("missing baseline did not raise")
