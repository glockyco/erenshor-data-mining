from __future__ import annotations

from typing import Any, cast

from erenshor.tools.wiki_cargo_probe.queries import (
    batch_counts_match,
    batch_sample_matches,
    lifecycle_key_matches,
    lifecycle_state_matches,
    query_table,
    replacement_row_matches,
    reverse_page_title_is_ambiguous,
    reverse_rows_match_keys,
    rows_present,
)
from erenshor.tools.wiki_cargo_probe.scenarios.lifecycle import build_lifecycle_probe
from erenshor.tools.wiki_cargo_probe.scenarios.recreate_batching import build_recreate_batching_probe


def test_query_table_escapes_apostrophes_in_probe_keys() -> None:
    class RecordingContext:
        def __init__(self) -> None:
            self.where: str | None = None

        def query_cargo_table(self, **kwargs: Any) -> dict[str, Any]:
            self.where = kwargs["where"]
            return {"ok": True, "rows": []}

    context = RecordingContext()

    assert query_table(cast("Any", context), "ProbeTable", "O'Brien") == {"ok": True, "rows": []}
    assert context.where == "ProbeKey='O''Brien'"


def test_replacement_row_validation_requires_one_matching_original_probe_row() -> None:
    matching_row = {"title": {"ProbeKey": "UnitProbeKey", "ProbeValue": "Original"}}

    assert replacement_row_matches({"ok": True, "rows": [matching_row]}, "UnitProbeKey") is True
    assert (
        replacement_row_matches(
            {"ok": True, "rows": [{"ProbeKey": "UnitProbeKey", "ProbeValue": "Original"}]},
            "UnitProbeKey",
        )
        is True
    )
    assert replacement_row_matches({"ok": False, "rows": [matching_row]}, "UnitProbeKey") is False
    assert replacement_row_matches({"ok": True, "rows": []}, "UnitProbeKey") is False
    assert replacement_row_matches({"ok": True, "rows": [matching_row, matching_row]}, "UnitProbeKey") is False
    assert (
        replacement_row_matches(
            {"ok": True, "rows": [{"title": {"ProbeKey": "WrongKey", "ProbeValue": "Original"}}]},
            "UnitProbeKey",
        )
        is False
    )
    assert (
        replacement_row_matches(
            {"ok": True, "rows": [{"title": {"ProbeKey": "UnitProbeKey", "ProbeValue": "Changed"}}]},
            "UnitProbeKey",
        )
        is False
    )


def test_multi_entity_reverse_validation_requires_item_keys_and_flags_shared_page_ambiguity() -> None:
    reverse_result = {
        "ok": True,
        "rows": [
            {"title": {"Page": "SharedPage", "ItemKey": "ItemB"}},
            {"title": {"Page": "SharedPage", "ItemKey": "ItemA"}},
        ],
    }

    assert reverse_rows_match_keys(reverse_result, ("ItemA", "ItemB")) is True
    assert reverse_page_title_is_ambiguous(reverse_result, 2) is True

    mismatched_reverse_result = {
        "ok": True,
        "rows": [
            {"title": {"Page": "SharedPage", "ItemKey": "ItemB"}},
            {"title": {"Page": "SharedPage", "ItemKey": "ItemC"}},
        ],
    }
    unambiguous_page_result = {
        "ok": True,
        "rows": [
            {"title": {"Page": "PageA", "ItemKey": "ItemA"}},
            {"title": {"Page": "PageB", "ItemKey": "ItemB"}},
        ],
    }

    assert reverse_rows_match_keys(mismatched_reverse_result, ("ItemA", "ItemB")) is False
    assert reverse_page_title_is_ambiguous(unambiguous_page_result, 2) is False


def test_rows_present_requires_ok_results_and_expected_lengths() -> None:
    queries = {
        "A": {"ok": True, "rows": [{"title": {"ProbeKey": "Key"}}]},
        "B": {"ok": True, "rows": [{"title": {}}, {"title": {}}]},
    }

    assert rows_present(queries, {"A": 1, "B": 2}) is True
    assert rows_present({"A": queries["A"]}, {"A": 1, "B": 2}) is False
    assert rows_present({**queries, "C": {"ok": True, "rows": []}}, {"A": 1, "B": 2}) is False
    assert rows_present(queries, {"A": 1, "B": 1}) is False
    assert rows_present({**queries, "A": {"ok": False, "rows": [{"title": {}}]}}, {"A": 1, "B": 2}) is False


def test_lifecycle_key_matches_checks_item_relationship_rows() -> None:
    state = {
        "ItemA": {
            "items": {"ok": True, "rows": [{"title": {"StableKey": "ItemA"}}]},
            "obtained_from": {
                "ok": True,
                "rows": [{"title": {"SourceKey": "SourceB"}}, {"title": {"SourceKey": "SourceA"}}],
            },
            "used_in": {"ok": True, "rows": [{"title": {"UseKey": "UseA"}}]},
        }
    }

    assert lifecycle_key_matches(state, "ItemA", ("SourceA", "SourceB"), ("UseA",)) is True
    assert lifecycle_key_matches(state, "ItemA", ("SourceA",), ("UseA",)) is False
    assert lifecycle_key_matches(state, "Missing", (), ()) is False
    assert (
        lifecycle_key_matches({"ItemA": {**state["ItemA"], "items": {"ok": False, "rows": []}}}, "ItemA", (), ())
        is False
    )
    empty_state = {
        "ItemA": {
            "items": {"ok": True, "rows": []},
            "obtained_from": {"ok": True, "rows": []},
            "used_in": {"ok": True, "rows": []},
        }
    }
    assert lifecycle_key_matches(empty_state, "ItemA", (), (), item_present=False) is True


def test_lifecycle_state_matches_checks_kept_and_removed_items() -> None:
    candidate = build_lifecycle_probe("UnitProbe")
    state = {
        candidate.item_key: {
            "items": {"ok": True, "rows": [{"title": {"StableKey": candidate.item_key}}]},
            "obtained_from": {"ok": True, "rows": [{"title": {"SourceKey": "SourceA1"}}]},
            "used_in": {"ok": True, "rows": []},
        },
        candidate.removed_key: {
            "items": {"ok": True, "rows": []},
            "obtained_from": {"ok": True, "rows": []},
            "used_in": {"ok": True, "rows": []},
        },
    }

    assert (
        lifecycle_state_matches(
            state,
            candidate,
            item_sources=("SourceA1",),
            item_uses=(),
            removed_sources=(),
            removed_uses=(),
            removed_present=False,
        )
        is True
    )
    assert (
        lifecycle_state_matches(
            state,
            candidate,
            item_sources=("SourceA2",),
            item_uses=(),
            removed_sources=(),
            removed_uses=(),
            removed_present=False,
        )
        is False
    )


def test_recreate_batching_validation_helpers_require_counts_and_matching_sample_rows() -> None:
    candidate = build_recreate_batching_probe("UnitProbe", 3)
    matching_counts = {
        "Items": {"ok": True, "count": 3},
        "ObtainedFrom": {"ok": True, "count": 3},
        "UsedIn": {"ok": True, "count": 3},
    }

    assert batch_counts_match(matching_counts, 3) is True
    assert batch_counts_match({**matching_counts, "UsedIn": {"ok": True, "count": 2}}, 3) is False
    assert batch_counts_match({**matching_counts, "Items": {"ok": False, "count": 3}}, 3) is False

    sample_state = {
        "UnitProbeBatchItem0001": {
            "items": {"ok": True, "rows": [{"title": {"StableKey": "UnitProbeBatchItem0001"}}]},
            "obtained_from": {"ok": True, "rows": [{"title": {"SourceKey": "UnitProbeBatchSource0001"}}]},
            "used_in": {"ok": True, "rows": [{"title": {"UseKey": "UnitProbeBatchUse0001"}}]},
        },
        "UnitProbeBatchItem0002": {
            "items": {"ok": True, "rows": [{"title": {"StableKey": "UnitProbeBatchItem0002"}}]},
            "obtained_from": {"ok": True, "rows": [{"title": {"SourceKey": "UnitProbeBatchSource0002"}}]},
            "used_in": {"ok": True, "rows": [{"title": {"UseKey": "UnitProbeBatchUse0002"}}]},
        },
        "UnitProbeBatchItem0003": {
            "items": {"ok": True, "rows": [{"title": {"StableKey": "UnitProbeBatchItem0003"}}]},
            "obtained_from": {"ok": True, "rows": [{"title": {"SourceKey": "UnitProbeBatchSource0003"}}]},
            "used_in": {"ok": True, "rows": [{"title": {"UseKey": "UnitProbeBatchUse0003"}}]},
        },
    }

    assert batch_sample_matches(candidate, sample_state) is True

    mismatched_sample_state = {
        **sample_state,
        "UnitProbeBatchItem0002": {
            **sample_state["UnitProbeBatchItem0002"],
            "obtained_from": {"ok": True, "rows": [{"title": {"SourceKey": "WrongSource"}}]},
        },
    }
    assert batch_sample_matches(candidate, mismatched_sample_state) is False
