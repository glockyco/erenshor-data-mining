"""Bounded human review must retain the complete publication safety metadata."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from erenshor.application.publish.models import canonical, sha256
from erenshor.application.publish.reporting import review_summary, status_summary


def operation(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": kind + ":target",
        "kind": kind,
        "target": "target",
        "dependencies": ["wiki_repo:prerequisite"],
        "dependency_reasons": {"wiki_repo:prerequisite": "Required exact source"},
        "expected_base": {"revision_id": 10, "content_sha256": "base-hash", "receipt": "previous"},
        "recovery": "No automatic retries. Reconcile unknown outcomes.",
        "destination": {"api_url": "https://wiki.invalid/api.php", "account": "reviewed-account"},
        "payload_path": "payloads/" + kind + ".json",
        "payload_sha256": "payload-file-hash",
        "inputs": {"$REPO/source.py": "source-file-hash"},
        "payload": payload,
    }


def report(operations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "approval_digest": "sha256:reviewed-plan",
        "run_dir": "/review/run",
        "plan_path": "$RUN/plan.json",
        "review_path": "$RUN/review.json",
        "summary_path": "$RUN/review-summary.json",
        "variant": "main",
        "game_build_id": "reviewed-build",
        "configuration": {"sheets": {"account": "service@review.invalid", "spreadsheet_id": "reviewed-sheet"}},
        "inputs": {"$REPO/database.sqlite": "database-sha256"},
        "operations": operations,
        "recovery": "No cross-service transaction.",
    }


@pytest.fixture(scope="module")
def large_report() -> dict[str, Any]:
    # Exactly 600,000 cells, represented both as selected RAW rows and typed native rows.
    rows = [["cell-bytes-must-not-appear"] * 100 for _ in range(6000)]
    native_rows = [{"values": [{"userEnteredValue": {"stringValue": value}} for value in rows[0]]}] * 6000
    body = {
        "requests": [
            {
                "updateCells": {
                    "start": {"sheetId": 7, "rowIndex": 2, "columnIndex": 1},
                    "rows": native_rows,
                    "fields": "userEnteredValue",
                }
            }
        ]
    }
    body_text = json.dumps(body)
    sheet = operation(
        "sheet",
        {
            "tabs": [
                {
                    "sheet_name": "Items",
                    "sheet_id": 7,
                    "table_id": "owned-table",
                    "range": {
                        "sheetId": 7,
                        "startRowIndex": 2,
                        "endRowIndex": 6002,
                        "startColumnIndex": 1,
                        "endColumnIndex": 101,
                    },
                    "rows": rows,
                }
            ],
            "requests": [{"method": "batchUpdate", "arguments": {"body": body}}],
            "batch_body": body_text,
            "batch_body_path": "$RUN/payloads/body.batch.json",
            "batch_body_sha256": sha256(body_text.encode()),
            "batch_body_bytes": len(body_text.encode()),
            "base_snapshot": {
                "metadata": {"title": "Workbook"},
                "sheets": {"7": {"cells": {"0:0": {"userEnteredValue": {"stringValue": "preimage-content"}}}}},
            },
            "base_sha256": "stable-workbook-hash",
            "guard": "full-workbook-preflight-owned-postflight-observed-receipt",
            "limitations": [
                "Concurrent writers can race preflight.",
                "Formula rebasing is provider-managed.",
                "Lost acknowledgement requires reconciliation and a new plan.",
            ],
            "queries": [{"path": "$REPO/items.sql", "sha256": "exact-query-hash"}],
        },
    )
    wiki = operation(
        "wiki_prose",
        {
            "content": "new prose\n" * 10000,
            "original": "old prose\n" * 10000,
            "diff": "-old prose\n+new prose\n" * 10000,
            "page_edits_file": "$REPO/prose.toml",
            "prose_review_sha256": "reviewed-prose-file-hash",
            "dependency_bases": {
                "Template:Data": {
                    "initial": {"revision_id": 22},
                    "receipt": "wiki_repo:prerequisite",
                    "content_sha256": "dependency-hash",
                }
            },
            "native_manifest": "$RUN/wiki/manifest.json",
        },
    )
    files = {f"asset-{index}.png": {"sha256": f"asset-digest-{index}", "size": 1024} for index in range(1900)}
    maps = operation(
        "map",
        {
            "assets": "$RUN/maps/build",
            "bundle": "$RUN/maps/worker.js",
            "config": "$RUN/maps/wrangler.jsonc",
            "config_sha256": "config-digest",
            "asset_manifest": files,
            "worker_manifest": {"worker.js": {"sha256": "bundle-digest", "size": 500}},
            "input_snapshots": [{"path": f"$REPO/images/{name}", **entry} for name, entry in files.items()],
            "database_route": {"path": "/db/erenshor.sqlite", "sha256": "database-digest"},
            "native_build_info": {"code": "code-digest", "data": "database-digest", "tiles": "tile-digest"},
            "guard": "preflight-and-postflight",
            "limitations": "Concurrent writers may race. No provider-downloadable asset manifest.",
        },
    )
    maps["inputs"] = {f"$REPO/images/{name}": entry["sha256"] for name, entry in files.items()}
    maps["destination"] = {
        "account_id": "actual-account",
        "service": "actual-service",
        "url": "https://maps.invalid",
        "origins": ["https://maps.invalid", "https://legacy.invalid"],
    }
    return report([wiki, maps, sheet])


def test_large_review_keeps_every_operation_and_guard_without_cell_bytes(large_report: dict[str, Any]) -> None:
    summary = review_summary(large_report)
    rendered = json.dumps(summary, indent=2)
    assert len(rendered) < 24000
    assert "cell-bytes-must-not-appear" not in rendered
    assert "preimage-content" not in rendered
    assert summary["operation_count"] == 3
    for original, summarized in zip(large_report["operations"], summary["operations"], strict=True):
        for key in (
            "id",
            "kind",
            "target",
            "dependencies",
            "dependency_reasons",
            "expected_base",
            "recovery",
            "destination",
            "payload_path",
            "payload_sha256",
        ):
            assert summarized[key] == original[key]
    for key in ("approval_digest", "variant", "game_build_id", "configuration", "inputs", "recovery"):
        assert summary[key] == large_report[key]
    payload = summary["operations"][2]["payload"]
    original_payload = large_report["operations"][2]["payload"]
    rows = payload["tabs"][0]["rows"]
    assert rows["row_count"] == 6000
    assert rows["column_count"] == 100
    assert rows["cell_count"] == 600000
    assert rows["path"] == "/review/run/payloads/sheet.json"
    assert rows["json_pointer"] == "/tabs/0/rows"
    assert rows["sha256"] == sha256(canonical(original_payload["tabs"][0]["rows"]))
    assert payload["tabs"][0]["range"] == original_payload["tabs"][0]["range"]
    start = payload["requests"][0]["arguments"]["body"]["requests"][0]["updateCells"]["start"]
    assert start == {"sheetId": 7, "rowIndex": 2, "columnIndex": 1}
    assert payload["batch_body"]["sidecar_path"] == "/review/run/payloads/body.batch.json"
    assert payload["batch_body"]["sha256"] == original_payload["batch_body_sha256"]
    assert payload["batch_body"]["bytes"] == original_payload["batch_body_bytes"]
    assert payload["limitations"] == original_payload["limitations"]
    assert payload["queries"] == original_payload["queries"]
    assert payload["base_sha256"] == "stable-workbook-hash"


def test_wiki_exact_prose_and_diff_references_and_dependencies(large_report: dict[str, Any]) -> None:
    original = large_report["operations"][0]["payload"]
    payload = review_summary(large_report)["operations"][0]["payload"]
    for key in ("content", "original", "diff"):
        assert payload[key]["path"] == "/review/run/payloads/wiki_prose.json"
        assert payload[key]["json_pointer"] == "/" + key
        assert payload[key]["sha256"] == sha256(original[key].encode())
        assert payload[key]["bytes"] == len(original[key].encode())
    for key in ("page_edits_file", "prose_review_sha256", "dependency_bases", "native_manifest"):
        assert payload[key] == original[key]


def test_map_inventory_references_preserve_asset_bundle_database_and_source_digests(
    large_report: dict[str, Any],
) -> None:
    original = large_report["operations"][1]
    summary = review_summary(large_report)["operations"][1]
    inputs = summary["inputs"]
    assert inputs["path"] == "/review/run/plan.json"
    assert inputs["json_pointer"] == "/operations/1/inputs"
    assert inputs["count"] == 1900
    assert inputs["sha256"] == sha256(canonical(original["inputs"]))
    payload = summary["payload"]
    for field in ("asset_manifest", "worker_manifest", "input_snapshots"):
        assert payload[field]["path"] == "/review/run/payloads/map.json"
        assert payload[field]["json_pointer"] == "/" + field
        assert payload[field]["sha256"] == sha256(canonical(original["payload"][field]))
    assert payload["asset_manifest"]["file_count"] == 1900
    assert payload["asset_manifest"]["file_bytes"] == 1900 * 1024
    assert payload["worker_manifest"]["provider_manifest_sha256"] == sha256(
        json.dumps(original["payload"]["worker_manifest"], sort_keys=True, separators=(",", ":")).encode()
    )
    assert payload["bundle_sha256"] == "bundle-digest"
    assert payload["database_route"]["sha256"] == "database-digest"
    assert payload["native_build_info"] == original["payload"]["native_build_info"]
    assert payload["config_sha256"] == "config-digest"


def test_status_preserves_receipts_and_every_history_record_without_postimages() -> None:
    snapshot = {"sheets": {"7": {"cells": {"0:0": "large-observed-cell" * 10000}}}}
    event = {
        "operation": "sheet:target",
        "state": "succeeded",
        "checksum": "exact-record-checksum",
        "previous": "previous-record-checksum",
        "time": "record-time",
        "receipt": {
            "journal_path": "/review/run/sheets.jsonl",
            "journal_sha256": "native-journal-hash",
            "provider": {
                "base_sha256": "base-hash",
                "batch_body_sha256": "body-hash",
                "postflight_sha256": sha256(canonical(snapshot)),
                "postflight_snapshot": snapshot,
                "outcomes": [{"status": "succeeded", "response": {"spreadsheetId": "reviewed-sheet", "replies": [{}]}}],
            },
        },
    }
    history = [
        {
            "operation": "sheet:target",
            "state": "running",
            "checksum": "running-checksum",
            "expected_base": {"sha256": "base-hash"},
        },
        event,
    ]
    status = {
        "digest": "reviewed-plan",
        "journal": "/review/run/journal.jsonl",
        "next": "Reconcile before resume.",
        "operations": [
            {
                "id": "sheet:target",
                "target": "reviewed-sheet",
                "state": "uncertain",
                "evidence": event,
                "history": history,
                "recovery": "Retain the full observed workbook.",
            }
        ],
    }
    summary = status_summary(status)
    assert len(json.dumps(summary)) < 6000
    assert "large-observed-cell" not in json.dumps(summary)
    state = summary["operations"][0]
    assert state["state"] == "uncertain"
    assert state["recovery"] == status["operations"][0]["recovery"]
    assert len(state["history"]) == 2
    assert state["history"][0] == history[0]
    observed = state["evidence"]["receipt"]["provider"]["postflight_snapshot"]
    assert observed["path"] == "/review/run/journal.jsonl"
    assert observed["record_checksum"] == "exact-record-checksum"
    assert observed["json_pointer"] == "/receipt/provider/postflight_snapshot"
    assert observed["sha256"] == event["receipt"]["provider"]["postflight_sha256"]
    assert state["history"][1]["receipt"]["provider"]["postflight_snapshot"] == observed
    assert state["evidence"]["receipt"]["journal_sha256"] == "native-journal-hash"
    assert state["evidence"]["receipt"]["provider"]["outcomes"] == event["receipt"]["provider"]["outcomes"]
    assert status["operations"][0]["evidence"]["receipt"]["provider"]["postflight_snapshot"] is snapshot


def test_summary_is_pure_idempotent_and_uses_escaped_json_pointers() -> None:
    original = report([operation("wiki_repo", {"nested/~metadata": {"diff": "Old\nNéw\n"}})])
    before = canonical(original)
    summary = review_summary(original)
    assert canonical(original) == before
    assert review_summary(summary) == summary
    diff = summary["operations"][0]["payload"]["nested/~metadata"]["diff"]
    assert diff["json_pointer"] == "/nested~1~0metadata/diff"
    assert diff["sha256"] == sha256("Old\nNéw\n".encode())


def test_status_retains_all_plan_guards_and_compacts_only_large_input_inventories(
    large_report: dict[str, Any],
) -> None:
    states = [
        {**{key: value for key, value in item.items() if key != "payload"}, "state": "pending"}
        for item in large_report["operations"]
    ]
    original = {
        **{key: value for key, value in large_report.items() if key not in {"operations", "approval_digest"}},
        "digest": large_report["approval_digest"],
        "journal": "/review/run/journal.jsonl",
        "operations": states,
    }
    summary = status_summary(original)
    assert len(json.dumps(summary)) < 8000
    for key in ("variant", "game_build_id", "configuration", "inputs"):
        assert summary[key] == original[key]
    for source, state in zip(states, summary["operations"], strict=True):
        for key in (
            "id",
            "kind",
            "target",
            "dependencies",
            "dependency_reasons",
            "expected_base",
            "recovery",
            "destination",
            "payload_path",
            "payload_sha256",
            "state",
        ):
            assert state[key] == source[key]
    assert summary["operations"][1]["inputs"]["count"] == 1900
    assert summary["operations"][1]["inputs"]["path"] == "/review/run/plan.json"
    assert summary["operations"][1]["inputs"]["json_pointer"] == "/operations/1/inputs"
    assert status_summary(summary) == summary


@pytest.mark.parametrize("command", ["apply", "resume", "status"])
def test_cli_handlers_print_bounded_dryrun_review(
    command: str,
    large_report: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from erenshor.cli.commands import publish

    context = typer.Context(typer.main.get_command(publish.app), obj=SimpleNamespace(dry_run=True))
    if command == "status":
        monkeypatch.setattr(
            publish,
            "status_publish",
            lambda path, ctx: {"digest": "reviewed-plan", "operations": [], "journal": "/review/run/journal.jsonl"},
        )
        publish.status(context, Path("/review/run/plan.json"))
    else:
        monkeypatch.setattr(
            publish, "apply_publish" if command == "apply" else "inspect_publish", lambda *args: large_report
        )
        # Preconditions are exercised by the ordered-publication CLI contract.
        getattr(publish, command).__wrapped__(context, Path("/review/run/plan.json"), None)
    stdout = capsys.readouterr().out
    assert len(stdout) < 24000
    parsed = json.loads(stdout)
    assert parsed["operation_count"] == (0 if command == "status" else 3)
    assert "cell-bytes-must-not-appear" not in stdout


def test_cli_inspection_error_prints_bounded_review(
    large_report: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    from erenshor.application.publish.coordinator import PublishInspectionError
    from erenshor.cli.commands.publish import _error

    with pytest.raises(typer.Exit):
        _error(PublishInspectionError("base changed", {**large_report, "valid": False, "conflicts": ["base changed"]}))
    captured = capsys.readouterr()
    assert len(captured.out) < 24000
    assert json.loads(captured.out)["conflicts"] == ["base changed"]
    assert "Publication refused: base changed" in captured.err
