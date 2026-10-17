"""Grouped Sheets publication binds SQL, account identity and observed receipts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

from erenshor.application.publish import sheets
from erenshor.application.publish.models import PublishError, SurfaceUncertainError
from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.application.sheets.service import SheetsService
from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher, SheetsRequestError


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple:
    database = tmp_path / "source.sqlite"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE entries (id INTEGER, ratio REAL, label TEXT, nullable TEXT)"))
        connection.execute(text("INSERT INTO entries VALUES (7, 1.25, '=literal', NULL), (8, 2.5, 'other', '')"))
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "items.sql").write_text("SELECT id, ratio, label, nullable FROM entries ORDER BY id")
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "publisher@example.invalid",
                "client_id": "account-1",
                "project_id": "fixture",
                "private_key": "DO NOT FREEZE THIS SECRET",
            }
        )
    )
    publisher = GoogleSheetsPublisher(credentials)
    base = {
        "metadata": {"spreadsheetId": "spreadsheet-fixture"},
        "sheets": {
            "1": {
                "metadata": {
                    "properties": {
                        "sheetId": 1,
                        "title": "items",
                        "gridProperties": {"rowCount": 20, "columnCount": 8},
                    },
                    "tables": [
                        {
                            "tableId": "items-table",
                            "range": {
                                "sheetId": 1,
                                "startRowIndex": 0,
                                "endRowIndex": 3,
                                "startColumnIndex": 0,
                                "endColumnIndex": 4,
                            },
                        }
                    ],
                },
                "cells": {"0:0": {"userEnteredValue": {"stringValue": "old"}}},
                "row_metadata": {},
                "column_metadata": {},
            }
        },
    }
    publisher.inspect_workbook = Mock(return_value=base)
    formatter = SheetsFormatter(engine, queries, map_base_url="https://maps.example.invalid")
    service = SheetsService(formatter, publisher, "spreadsheet-fixture")
    ctx = SimpleNamespace(
        repo_root=tmp_path,
        variant="main",
        dry_run=False,
        config=SimpleNamespace(
            variants={
                "main": SimpleNamespace(
                    resolved_database=lambda root: database,
                    maps=SimpleNamespace(base_url="https://maps.example.invalid"),
                )
            }
        ),
    )
    monkeypatch.setattr(sheets, "create_sheets_service", lambda ctx: service)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return ctx, service, publisher, run_dir, credentials


def operation(environment: tuple, tabs: list[str] | None = None) -> tuple:
    ctx, _service, _publisher, run_dir, _credentials = environment
    drafts = sheets.prepare(ctx, {"tabs": tabs or ["items"], "summary": "Reviewed rows"}, run_dir)
    assert len(drafts) == 1
    draft = drafts[0]
    payload = draft.pop("payload")
    draft.update(_run_dir=str(run_dir), payload_sha256="frozen-payload-digest")
    return draft, payload


def observed_fixture(payload: dict) -> dict:
    """Supply explicit synthetic owned outputs, not a Google formula simulator."""
    observed = copy.deepcopy(payload["base_snapshot"])
    for tab in payload["tabs"]:
        sheet = observed["sheets"][str(tab["sheet_id"])]
        sheet["metadata"]["tables"][0]["range"] = copy.deepcopy(tab["range"])
        for row_index, row in enumerate(tab["rows"], tab["range"].get("startRowIndex", 0)):
            for column, value in enumerate(row, tab["range"].get("startColumnIndex", 0)):
                cell = sheet["cells"].setdefault(f"{row_index}:{column}", {})
                if value == "":
                    cell.pop("userEnteredValue", None)
                else:
                    key = (
                        "boolValue"
                        if isinstance(value, bool)
                        else "numberValue"
                        if isinstance(value, int | float)
                        else "stringValue"
                    )
                    cell["userEnteredValue"] = {key: value}
    return observed


def acknowledge(method: str, spreadsheet_id: str, arguments: dict) -> dict:
    assert method == "batchUpdate"
    return {"spreadsheetId": spreadsheet_id, "replies": [{} for _ in arguments["body"]["requests"]]}


def test_prepare_binds_exact_sql_rows_and_nonsecret_destination(environment: tuple) -> None:
    _ctx, _service, _publisher, _run_dir, credentials = environment
    draft, payload = operation(environment)
    assert draft["kind"] == "sheet"
    assert draft["id"] == "sheet:spreadsheet-fixture"
    assert draft["target"] == "spreadsheet-fixture"
    assert payload["tabs"][0]["rows"] == [
        ["id", "ratio", "label", "nullable"],
        [7, 1.25, "=literal", ""],
        [8, 2.5, "other", ""],
    ]
    assert payload["queries"] == [
        {
            "sheet_name": "items",
            "path": str(credentials.parent / "queries" / "items.sql"),
            "sql": "SELECT id, ratio, label, nullable FROM entries ORDER BY id",
        }
    ]
    assert "DO NOT FREEZE THIS SECRET" not in json.dumps([draft, payload])
    assert str(credentials) not in draft["inputs"]
    assert draft["destination"]["account"]["client_email"] == "publisher@example.invalid"
    assert all(Path(path).is_absolute() for path in draft["inputs"])
    assert draft["expected_base"]["selected_tabs"] == ["items"]
    assert len(payload["requests"]) == 1
    assert "batch_body_bytes" in payload
    assert "expected_snapshot" not in payload


def test_adapter_missing_table_never_produces_operation(environment: tuple) -> None:
    ctx, _service, publisher, run_dir, _credentials = environment
    publisher.inspect_workbook.return_value["sheets"]["1"]["metadata"].pop("tables")
    with pytest.raises(ValueError, match=r"No Google Sheets table.*items"):
        sheets.prepare(ctx, {"tabs": ["items"]}, run_dir)
    assert publisher._service is None
    assert list(run_dir.iterdir()) == []


def test_identity_change_invalidates_plan_before_write(environment: tuple) -> None:
    ctx, _service, _publisher, run_dir, credentials = environment
    draft, payload = operation(environment)
    changed = json.loads(credentials.read_text())
    changed["client_email"] = "another@example.invalid"
    credentials.write_text(json.dumps(changed))
    with pytest.raises(PublishError, match="account or destination changed"):
        sheets.check(ctx, draft, payload, {})
    assert list(run_dir.iterdir()) == []


def test_failed_predecessor_blocks_execution_without_request_log(environment: tuple) -> None:
    ctx, _service, _publisher, run_dir, _credentials = environment
    draft, payload = operation(environment)
    draft["dependencies"] = ["map:canonical"]
    with pytest.raises(PublishError, match="predecessors"):
        sheets.execute(ctx, draft, payload, {})
    assert list(run_dir.iterdir()) == []


def test_unknown_batch_retains_intent_and_never_replays(environment: tuple) -> None:
    ctx, _service, publisher, _run_dir, _credentials = environment
    draft, payload = operation(environment)
    publisher._request = Mock(side_effect=TimeoutError("lost response"))
    with pytest.raises(SurfaceUncertainError) as error:
        sheets.execute(ctx, draft, payload, {})
    log_path = Path(error.value.evidence["journal_path"])
    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert events[0]["evidence"]["running_request"] == 0
    assert events[0]["evidence"]["batch_body_sha256"] == payload["batch_body_sha256"]
    assert events[-1]["evidence"]["outcomes"][0]["status"] == "uncertain"
    publisher._request.assert_called_once()
    with pytest.raises(SurfaceUncertainError, match="journal already exists"):
        sheets.execute(ctx, draft, payload, {})
    publisher._request.assert_called_once()


def test_complete_receipt_reconciles_log_and_full_observed_postimage(environment: tuple) -> None:
    ctx, _service, publisher, _run_dir, _credentials = environment
    draft, payload = operation(environment)
    observed = observed_fixture(payload)
    publisher._request = Mock(side_effect=acknowledge)
    publisher.inspect_workbook.side_effect = [payload["base_snapshot"], observed]
    receipt = sheets.execute(ctx, draft, payload, {})
    publisher.inspect_workbook.side_effect = None
    publisher.inspect_workbook.return_value = observed
    sheets.reconcile(ctx, draft, payload, receipt, {})
    assert len(receipt["provider"]["outcomes"]) == 1
    assert receipt["provider"]["postflight_snapshot"] == observed
    changed = copy.deepcopy(observed)
    changed["sheets"]["1"]["cells"]["10:0"] = {"userEnteredValue": {"formulaValue": "=42"}}
    publisher.inspect_workbook.return_value = changed
    with pytest.raises(ValueError, match="completed state changed"):
        sheets.reconcile(ctx, draft, payload, receipt, {})
    publisher.inspect_workbook.return_value = observed
    Path(receipt["journal_path"]).write_text("altered journal\n")
    with pytest.raises(PublishError, match="journal differs"):
        sheets.reconcile(ctx, draft, payload, receipt, {})


def test_explicit_resume_after_definitive_zero_write_rejection_uses_new_journal(environment: tuple) -> None:
    ctx, _service, publisher, _run_dir, _credentials = environment
    draft, payload = operation(environment)
    rejection = HttpError(resp=Mock(status=403, reason="forbidden"), content=b'{"error":{"message":"forbidden"}}')
    publisher._request = Mock(side_effect=rejection)
    with pytest.raises(SheetsRequestError) as failure:
        sheets.execute(ctx, draft, payload, {})
    assert failure.value.evidence["safe_to_resume"] is True
    first_journal = Path(failure.value.evidence["journal_path"])
    publisher._request = Mock(side_effect=acknowledge)
    publisher.inspect_workbook.side_effect = [payload["base_snapshot"], observed_fixture(payload)]
    receipt = sheets.execute(ctx, draft, payload, {})
    assert Path(receipt["journal_path"]) != first_journal
    assert first_journal.exists()
    publisher._request.assert_called_once()


def test_selected_cross_tab_and_unselected_dependencies_share_one_atomic_operation(environment: tuple) -> None:
    ctx, _service, publisher, run_dir, _credentials = environment
    (ctx.repo_root / "queries" / "spells.sql").write_text("SELECT id FROM entries ORDER BY id")
    base = publisher.inspect_workbook.return_value
    base["sheets"]["1"]["metadata"]["tables"][0]["range"]["endRowIndex"] = 2
    spells = copy.deepcopy(base["sheets"]["1"])
    spells["metadata"]["properties"].update(sheetId=2, title="spells")
    spells["metadata"]["tables"][0].update(tableId="spells-table")
    spells["metadata"]["tables"][0]["range"].update(sheetId=2, endRowIndex=3)
    spells["cells"]["10:0"] = {"userEnteredValue": {"formulaValue": "=items!A6"}}
    base["sheets"]["2"] = spells
    unselected = copy.deepcopy(spells)
    unselected["metadata"]["properties"].update(sheetId=3, title="unselected")
    unselected["metadata"]["tables"] = []
    base["sheets"]["3"] = unselected
    base["metadata"]["namedRanges"] = [
        {"name": "footer", "range": {"sheetId": 1, "startRowIndex": 5, "endRowIndex": 6}}
    ]
    draft, payload = operation(environment, ["spells", "items"])
    assert [tab["sheet_name"] for tab in payload["tabs"]] == ["items", "spells"]
    assert [query["sheet_name"] for query in payload["queries"]] == ["items", "spells"]
    assert draft["expected_base"]["selected_tabs"] == ["items", "spells"]
    native = payload["requests"][0]["arguments"]["body"]["requests"]
    assert {request["updateCells"]["start"]["sheetId"] for request in native if "updateCells" in request} == {1, 2}
    observed = observed_fixture(payload)
    for sheet_id in ("2", "3"):
        observed["sheets"][sheet_id]["cells"]["10:0"]["userEnteredValue"]["formulaValue"] = "=items!A7"
    observed["metadata"]["namedRanges"][0]["range"].update(startRowIndex=6, endRowIndex=7)
    publisher.inspect_workbook.side_effect = [payload["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = sheets.execute(ctx, draft, payload, {})
    publisher._request.assert_called_once()
    assert receipt["provider"]["postflight_snapshot"] == observed
    assert len(list(run_dir.iterdir())) == 1


@pytest.mark.parametrize("changed", ["named-range", "unselected-formula"])
def test_unselected_workbook_edit_aborts_before_first_mutation(environment: tuple, changed: str) -> None:
    ctx, _service, publisher, _run_dir, _credentials = environment
    draft, payload = operation(environment)
    edited = copy.deepcopy(payload["base_snapshot"])
    if changed == "named-range":
        edited["metadata"]["namedRanges"] = [{"name": "new", "range": {"sheetId": 1, "endRowIndex": 6}}]
    else:
        unselected = copy.deepcopy(edited["sheets"]["1"])
        unselected["metadata"]["properties"].update(sheetId=2, title="unselected")
        unselected["cells"]["10:0"] = {"userEnteredValue": {"formulaValue": "=items!A6"}}
        edited["sheets"]["2"] = unselected
    publisher.inspect_workbook.return_value = edited
    publisher._request = Mock()
    with pytest.raises(SheetsRequestError, match="base snapshot changed"):
        sheets.execute(ctx, draft, payload, {})
    publisher._request.assert_not_called()
