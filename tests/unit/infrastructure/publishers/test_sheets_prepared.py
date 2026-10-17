"""Atomic native Sheets requests and honest observed-workbook reconciliation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher, SheetsRequestError, _sheet_snapshot


def snapshot() -> dict:
    return _sheet_snapshot(
        {
            "properties": {"sheetId": 7, "title": "items", "gridProperties": {"rowCount": 12, "columnCount": 8}},
            "tables": [
                {
                    "tableId": "table-7",
                    "range": {
                        "sheetId": 7,
                        "startRowIndex": 1,
                        "endRowIndex": 4,
                        "startColumnIndex": 1,
                        "endColumnIndex": 3,
                    },
                }
            ],
            "data": [
                {
                    "startRow": 1,
                    "startColumn": 1,
                    "rowData": [
                        {"values": [{"userEnteredValue": {"stringValue": "old header"}, "note": "keep note"}]},
                        {"values": [{"userEnteredValue": {"numberValue": 1}}]},
                        {"values": [{"userEnteredValue": {"numberValue": 2}}]},
                        {"values": [{"userEnteredFormat": {"backgroundColor": {"red": 1}}}]},
                        {
                            "values": [
                                {
                                    "userEnteredValue": {"formulaValue": "=B6+$B$6+Other!B6"},
                                    "userEnteredFormat": {"textFormat": {"bold": True}},
                                }
                            ]
                        },
                    ],
                    "rowMetadata": [{}, {}, {}, {"pixelSize": 40}],
                }
            ],
        }
    )


def workbook() -> dict:
    return {"metadata": {"spreadsheetId": "spreadsheet"}, "sheets": {"7": snapshot()}}


@pytest.fixture
def publisher(tmp_path: Path) -> GoogleSheetsPublisher:
    result = GoogleSheetsPublisher(tmp_path / "unused-credentials.json")
    result.inspect_workbook = Mock(return_value=workbook())
    result._service = MagicMock()
    return result


def observed_fixture(prepared: dict) -> dict:
    """Construct synthetic stable cells. This is not evidence of provider rebasing."""
    observed = copy.deepcopy(prepared["base_snapshot"])
    for tab in prepared["tabs"]:
        sheet = observed["sheets"][str(tab["sheet_id"])]
        table = next(table for table in sheet["metadata"]["tables"] if table["tableId"] == tab["table_id"])
        old_end, end = table["range"]["endRowIndex"], tab["range"]["endRowIndex"]
        cells = {}
        for address, cell in sheet["cells"].items():
            row, column = map(int, address.split(":"))
            if end < old_end and end <= row < old_end:
                continue
            moved = row + end - old_end if row >= old_end else row
            cells[f"{moved}:{column}"] = cell
        sheet["cells"] = cells
        dimensions = {}
        for index, value in sheet["row_metadata"].items():
            row = int(index)
            if end < old_end and end <= row < old_end:
                continue
            dimensions[str(row + end - old_end if row >= old_end else row)] = value
        sheet["row_metadata"] = dimensions
        table["range"] = copy.deepcopy(tab["range"])
        for row_index, row in enumerate(tab["rows"], tab["range"].get("startRowIndex", 0)):
            for column, value in enumerate(row, tab["range"].get("startColumnIndex", 0)):
                cell = cells.setdefault(f"{row_index}:{column}", {})
                for key in ("userEnteredValue", "textFormatRuns", "chipRuns"):
                    cell.pop(key, None)
                if value != "":
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


def same_rows() -> list:
    return [["header", "other"], [1, "a"], [2, "b"]]


def test_missing_table_blocks_preparation_without_writes(publisher: GoogleSheetsPublisher) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["metadata"].pop("tables")
    with pytest.raises(ValueError, match=r"No Google Sheets table.*items"):
        publisher.prepare_table("spreadsheet", "items", [["header"]])
    publisher._service.spreadsheets.assert_not_called()


def test_freezes_typed_cells_one_batch_and_exact_native_body(publisher: GoogleSheetsPublisher) -> None:
    rows = [["string", "number", "float", "bool"], ["=not a formula", 7, 1.25, True], ["", 0, -2.5, False]]
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    assert len(prepared["requests"]) == 1
    body = prepared["requests"][0]["arguments"]["body"]
    assert body["requests"][0] == {
        "updateCells": {
            "start": {"sheetId": 7, "rowIndex": 1, "columnIndex": 1},
            "rows": [
                {"values": [{"userEnteredValue": {"stringValue": value}} for value in rows[0]]},
                {
                    "values": [
                        {"userEnteredValue": {"stringValue": "=not a formula"}},
                        {"userEnteredValue": {"numberValue": 7}},
                        {"userEnteredValue": {"numberValue": 1.25}},
                        {"userEnteredValue": {"boolValue": True}},
                    ]
                },
                {
                    "values": [
                        {},
                        {"userEnteredValue": {"numberValue": 0}},
                        {"userEnteredValue": {"numberValue": -2.5}},
                        {"userEnteredValue": {"boolValue": False}},
                    ]
                },
            ],
            "fields": "userEnteredValue",
        }
    }
    assert prepared["batch_body"] == json.dumps(body, allow_nan=False)
    assert prepared["batch_body_bytes"] == len(prepared["batch_body"].encode())
    assert prepared["batch_body_sha256"] == hashlib.sha256(prepared["batch_body"].encode()).hexdigest()
    assert "expected_snapshot" not in prepared
    assert "expected_sha256" not in prepared
    rows[1][0] = "later edit"
    assert body["requests"][0]["updateCells"]["rows"][1]["values"][0]["userEnteredValue"] == {
        "stringValue": "=not a formula"
    }
    publisher._service.spreadsheets.assert_not_called()


@pytest.mark.parametrize(
    "rows,kinds",
    [
        ([["header"], [1], [2], [3], [4]], ["updateCells", "insertDimension", "updateCells", "updateTable"]),
        ([["header"], [1]], ["updateCells", "repeatCell", "deleteDimension", "updateTable"]),
    ],
)
def test_native_resize_sequences_are_one_atomic_batch(
    publisher: GoogleSheetsPublisher, rows: list, kinds: list
) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    batch = prepared["requests"][0]["arguments"]["body"]["requests"]
    assert [next(iter(request)) for request in batch] == kinds
    if "repeatCell" in kinds:
        assert batch[1]["repeatCell"] == {
            "range": {"sheetId": 7, "startRowIndex": 3, "endRowIndex": 4},
            "cell": {},
            "fields": "userEnteredValue",
        }
    assert prepared["base_snapshot"]["sheets"]["7"]["cells"]["5:1"]["userEnteredValue"]["formulaValue"].startswith(
        "=B6"
    )


def test_growth_retains_native_append_before_insert(publisher: GoogleSheetsPublisher) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["metadata"]["properties"]["gridProperties"]["rowCount"] = 4
    prepared = publisher.prepare_table("spreadsheet", "items", [["header"], [1], [2], [3], [4]])
    batch = prepared["requests"][0]["arguments"]["body"]["requests"]
    assert batch[1] == {"appendDimension": {"sheetId": 7, "dimension": "ROWS", "length": 2}}
    assert "insertDimension" in batch[2]


@pytest.mark.parametrize("change", ["formula", "format", "table", "dimension", "named-range", "unselected"])
def test_full_workbook_edit_blocks_before_any_request(publisher: GoogleSheetsPublisher, change: str) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    edited = copy.deepcopy(prepared["base_snapshot"])
    sheet = edited["sheets"]["7"]
    if change == "formula":
        sheet["cells"]["5:1"]["userEnteredValue"]["formulaValue"] = "=42"
    elif change == "format":
        sheet["cells"]["5:1"]["userEnteredFormat"]["textFormat"]["bold"] = False
    elif change == "table":
        sheet["metadata"]["tables"][0]["name"] = "renamed"
    elif change == "dimension":
        sheet["row_metadata"]["4"]["pixelSize"] = 41
    elif change == "named-range":
        edited["metadata"]["namedRanges"] = [{"name": "new", "range": {"sheetId": 7, "endRowIndex": 6}}]
    else:
        edited["sheets"]["8"] = copy.deepcopy(sheet)
    publisher.inspect_workbook.return_value = edited
    publisher._request = Mock()
    with pytest.raises(SheetsRequestError, match="base snapshot changed") as error:
        publisher.execute_prepared(prepared)
    assert error.value.evidence == {"safe_to_resume": True, "outcomes": []}
    publisher._request.assert_not_called()


@pytest.mark.parametrize(
    "formula", ["=SUM(Table1[A6])", "=SUM(Table1[[#ALL],[A6]:[B6]])", "=SUM(Table1[A']6])", "=Ünicode!A6"]
)
def test_formula_text_is_captured_not_interpreted(publisher: GoogleSheetsPublisher, formula: str) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["5:1"]["userEnteredValue"] = {
        "formulaValue": formula
    }
    prepared = publisher.prepare_table("spreadsheet", "items", [["header"], [1], [2], [3], [4]])
    assert prepared["base_snapshot"]["sheets"]["7"]["cells"]["5:1"]["userEnteredValue"] == {"formulaValue": formula}
    assert formula not in prepared["batch_body"]
    publisher._service.spreadsheets.assert_not_called()


@pytest.mark.parametrize("selected", [False, True])
def test_cross_tab_formula_and_named_range_are_reviewed_without_prediction(
    publisher: GoogleSheetsPublisher, selected: bool
) -> None:
    base = publisher.inspect_workbook.return_value
    other = copy.deepcopy(base["sheets"]["7"])
    other["metadata"]["properties"].update(sheetId=8, title="spells")
    other["metadata"]["tables"][0]["tableId"] = "table-8"
    other["metadata"]["tables"][0]["range"]["sheetId"] = 8
    other["cells"]["5:1"]["userEnteredValue"] = {"formulaValue": "=items!A6"}
    base["sheets"]["8"] = other
    base["metadata"]["namedRanges"] = [
        {"name": "footer", "range": {"sheetId": 7, "startRowIndex": 5, "endRowIndex": 6}}
    ]
    tabs = {"items": [["header"], [1], [2], [3], [4]]}
    if selected:
        tabs["spells"] = same_rows()
    prepared = publisher.prepare_tables("spreadsheet", tabs)
    observed = observed_fixture(prepared)
    observed["sheets"]["7"]["cells"]["7:1"]["userEnteredValue"]["formulaValue"] = "=B8+$B$8+Other!B6"
    observed["sheets"]["8"]["cells"]["5:1"]["userEnteredValue"]["formulaValue"] = "=items!A8"
    observed["metadata"]["namedRanges"][0]["range"].update(startRowIndex=7, endRowIndex=8)
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    publisher._request.assert_called_once()
    assert receipt["postflight_snapshot"] == observed
    publisher.inspect_workbook.side_effect = None
    publisher.inspect_workbook.return_value = observed
    publisher.reconcile_prepared(prepared, receipt)


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("lost response"),
        KeyboardInterrupt(),
        HttpError(resp=Mock(status=503, reason="unavailable"), content=b"unavailable"),
        HttpError(resp=Mock(status=408, reason="timeout"), content=b"timeout"),
    ],
)
def test_unknown_outcomes_stop_without_retry(publisher: GoogleSheetsPublisher, failure: BaseException) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    publisher._request = Mock(side_effect=failure)
    checkpoints = []
    with pytest.raises(SheetsRequestError) as error:
        publisher.execute_prepared(prepared, lambda event: checkpoints.append(copy.deepcopy(event)))
    assert error.value.uncertain is True
    assert error.value.evidence["outcomes"][0]["status"] == "uncertain"
    assert checkpoints[0]["running_request"] == 0
    publisher._request.assert_called_once()


def test_rejected_atomic_batch_is_known_unwritten(publisher: GoogleSheetsPublisher) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", [["header"], [1], [2], [3]])
    publisher._request = Mock(side_effect=HttpError(resp=Mock(status=400, reason="invalid"), content=b"invalid"))
    with pytest.raises(SheetsRequestError) as error:
        publisher.execute_prepared(prepared)
    assert error.value.uncertain is False
    assert error.value.evidence["safe_to_resume"] is True
    assert len(error.value.evidence["outcomes"]) == 1
    publisher._request.assert_called_once()


@pytest.mark.parametrize(
    "response", [None, {}, {"spreadsheetId": "other"}, {"spreadsheetId": "spreadsheet", "replies": []}]
)
def test_incomplete_acknowledgement_is_uncertain(publisher: GoogleSheetsPublisher, response: object) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    publisher._request = Mock(return_value=response)
    with pytest.raises(SheetsRequestError) as error:
        publisher.execute_prepared(prepared)
    assert error.value.uncertain is True
    publisher._request.assert_called_once()


@pytest.mark.parametrize("change", ["owned", "note", "chip", "format", "scalar"])
def test_postflight_owned_values_and_preservation_invariants(publisher: GoogleSheetsPublisher, change: str) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["6:3"] = {
        "userEnteredValue": {"stringValue": "@"},
        "chipRuns": [{"startIndex": 0, "chip": {"richLinkProperties": {"uri": "file:one"}}}],
    }
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    observed = observed_fixture(prepared)
    cells = observed["sheets"]["7"]["cells"]
    if change == "owned":
        cells["2:1"]["userEnteredValue"] = {"numberValue": 99}
    elif change == "note":
        cells["1:1"]["note"] = "lost note"
    elif change == "chip":
        cells["6:3"]["chipRuns"][0]["chip"]["richLinkProperties"]["uri"] = "file:two"
    elif change == "format":
        cells["5:1"]["userEnteredFormat"]["textFormat"]["bold"] = False
    else:
        cells["6:3"]["userEnteredValue"] = {"stringValue": "changed"}
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    with pytest.raises(SheetsRequestError, match="postflight") as error:
        publisher.execute_prepared(prepared)
    assert error.value.uncertain is True
    assert error.value.evidence["outcomes"][0]["status"] == "succeeded"
    publisher._request.assert_called_once()


def test_chip_identity_removal_and_receipt_reconciliation(publisher: GoogleSheetsPublisher) -> None:
    cell = publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["2:1"]
    cell.update(
        userEnteredValue={"stringValue": "@"},
        chipRuns=[{"startIndex": 0, "chip": {"personProperties": {"email": "one@example.invalid"}}}],
    )
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    assert prepared["base_snapshot"]["sheets"]["7"]["cells"]["2:1"]["chipRuns"]
    observed = observed_fixture(prepared)
    assert "chipRuns" not in observed["sheets"]["7"]["cells"]["2:1"]
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    publisher.inspect_workbook.side_effect = None
    publisher.inspect_workbook.return_value = observed
    publisher.reconcile_prepared(prepared, receipt)
    changed = copy.deepcopy(observed)
    changed["sheets"]["7"]["cells"]["9:0"] = {"userEnteredValue": {"formulaValue": "=42"}}
    publisher.inspect_workbook.return_value = changed
    with pytest.raises(ValueError, match="completed state changed"):
        publisher.reconcile_prepared(prepared, receipt)
    broken = copy.deepcopy(receipt)
    broken["outcomes"] = []
    with pytest.raises(ValueError, match="Incomplete Sheets receipt"):
        publisher.reconcile_prepared(prepared, broken)


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_dynamic_cell_outputs_overlapping_writes_fail_before_approval(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["2:1"][field] = {"dataSourceId": "connected"}
    with pytest.raises(ValueError, match=f"unsupported {field}"):
        publisher.prepare_table("spreadsheet", "items", same_rows())
    publisher._service.spreadsheets.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("userEnteredValue", {"stringValue": "neighbor"}),
        ("note", "neighbor note"),
        ("chipRuns", [{"startIndex": 0, "chip": {"personProperties": {"email": "neighbor@example.invalid"}}}]),
        ("userEnteredFormat", {"textFormat": {"bold": True}}),
    ],
)
def test_whole_row_deletion_rejects_nonowned_content(
    publisher: GoogleSheetsPublisher, field: str, value: object
) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["3:5"] = {field: value}
    with pytest.raises(ValueError, match=r"deleting whole rows.*non-owned cell"):
        publisher.prepare_table("spreadsheet", "items", [["header"], [1]])
    publisher._service.spreadsheets.assert_not_called()


def test_width_expansion_rejects_overlapping_nonowned_content(publisher: GoogleSheetsPublisher) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["2:3"] = {
        "userEnteredValue": {"stringValue": "neighbor"}
    }
    with pytest.raises(ValueError, match="width expansion overlaps non-owned cell"):
        publisher.prepare_table("spreadsheet", "items", [["a", "b", "c"], [1, 2, 3], [4, 5, 6]])
    publisher._service.spreadsheets.assert_not_called()


def test_inspection_reads_full_stable_workbook_and_chip_identity(publisher: GoogleSheetsPublisher) -> None:
    native = publisher._service.spreadsheets()
    sheet = {
        **snapshot()["metadata"],
        "charts": [
            {
                "chartId": 9,
                "spec": {
                    "dataSourceChartProperties": {
                        "dataSourceId": "chart-source",
                        "dataExecutionStatus": {"state": "RUNNING"},
                    }
                },
            }
        ],
        "slicers": [{"slicerId": 10, "spec": {"title": "filter"}}],
        "rowGroups": [{"depth": 1, "range": {"sheetId": 7, "dimension": "ROWS", "startIndex": 4, "endIndex": 6}}],
        "columnGroups": [{"depth": 1, "range": {"sheetId": 7, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 6}}],
        "developerMetadata": [{"metadataId": 11, "metadataKey": "owner", "metadataValue": "editor"}],
        "data": [
            {
                "rowData": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "@"},
                                "chipRuns": [
                                    {
                                        "startIndex": 0,
                                        "chip": {"richLinkProperties": {"uri": "file:one", "mimeType": "text/plain"}},
                                    }
                                ],
                                "dataSourceTable": {
                                    "dataSourceId": "source",
                                    "dataExecutionStatus": {"state": "RUNNING"},
                                },
                                "dataSourceFormula": {
                                    "dataSourceId": "formula-source",
                                    "dataExecutionStatus": {"state": "RUNNING"},
                                },
                                "effectiveValue": {"numberValue": 1},
                                "formattedValue": "1",
                                "effectiveFormat": {"textFormat": {"bold": True}},
                                "hyperlink": "https://example.invalid",
                                "futureCellField": {"dataExecutionStatus": "stable user content"},
                            }
                        ]
                    }
                ],
                "rowMetadata": [{"hiddenByFilter": True, "hiddenByUser": True}],
            }
        ],
    }
    native.get.return_value.execute.return_value = {
        "spreadsheetId": "spreadsheet",
        "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/spreadsheet/edit",
        "namedRanges": [{"name": "footer", "range": {"sheetId": 7, "endRowIndex": 6}}],
        "dataSourceSchedules": [{"enabled": True, "nextRun": {"startTime": "volatile"}}],
        "futureWorkbookField": {"dataExecutionStatus": "stable user content"},
        "sheets": [sheet],
    }
    captured = GoogleSheetsPublisher.inspect_workbook(publisher, "spreadsheet")
    cell = captured["sheets"]["7"]["cells"]["0:0"]
    assert cell["chipRuns"][0]["chip"]["richLinkProperties"] == {"uri": "file:one", "mimeType": "text/plain"}
    assert cell["dataSourceTable"] == {"dataSourceId": "source"}
    assert cell["dataSourceFormula"] == {"dataSourceId": "formula-source"}
    assert cell["futureCellField"] == {"dataExecutionStatus": "stable user content"}
    assert not {"effectiveValue", "formattedValue", "effectiveFormat", "hyperlink"} & cell.keys()
    metadata = captured["sheets"]["7"]["metadata"]
    assert metadata["charts"][0]["spec"]["dataSourceChartProperties"] == {"dataSourceId": "chart-source"}
    for field in ("slicers", "rowGroups", "columnGroups", "developerMetadata"):
        assert metadata[field] == sheet[field]
    assert captured["sheets"]["7"]["row_metadata"]["0"] == {"hiddenByUser": True}
    assert captured["metadata"]["namedRanges"]
    assert captured["metadata"]["spreadsheetUrl"].endswith("/spreadsheet/edit")
    assert captured["metadata"]["dataSourceSchedules"] == [{"enabled": True}]
    assert captured["metadata"]["futureWorkbookField"] == {"dataExecutionStatus": "stable user content"}
    arguments = native.get.call_args.kwargs
    assert "ranges" not in arguments
    assert "fields" not in arguments
    assert arguments["includeGridData"] is True
    native.get.return_value.execute.assert_called_once_with(num_retries=0)


def test_native_transport_preserves_exact_batch_body_without_retries(publisher: GoogleSheetsPublisher) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    prepared = json.loads(json.dumps(prepared, sort_keys=True))
    service = build("sheets", "v4", developerKey="fixture", static_discovery=True)
    resource = service.spreadsheets()
    native = resource.batchUpdate(spreadsheetId="spreadsheet", **prepared["requests"][0]["arguments"])
    assert native.body == prepared["batch_body"]
    native.execute = Mock(return_value=acknowledge("batchUpdate", "spreadsheet", prepared["requests"][0]["arguments"]))
    resource.batchUpdate = Mock(return_value=native)
    service.spreadsheets = Mock(return_value=resource)
    publisher._service = service
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed_fixture(prepared)]
    receipt = publisher.execute_prepared(prepared)
    native.execute.assert_called_once_with(num_retries=0)
    resource.batchUpdate.assert_called_once_with(spreadsheetId="spreadsheet", **prepared["requests"][0]["arguments"])
    assert receipt["batch_body_sha256"] == prepared["batch_body_sha256"]


def test_chip_only_editor_change_blocks_before_atomic_mutation(publisher: GoogleSheetsPublisher) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["cells"]["6:3"] = {
        "userEnteredValue": {"stringValue": "@"},
        "chipRuns": [{"startIndex": 0, "chip": {"richLinkProperties": {"uri": "file:original"}}}],
    }
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    edited = copy.deepcopy(prepared["base_snapshot"])
    edited["sheets"]["7"]["cells"]["6:3"]["chipRuns"][0]["chip"]["richLinkProperties"]["uri"] = "file:replacement"
    publisher.inspect_workbook.return_value = edited
    publisher._request = Mock()
    with pytest.raises(SheetsRequestError, match="base snapshot changed"):
        publisher.execute_prepared(prepared)
    publisher._request.assert_not_called()


@pytest.mark.parametrize("change", ["body", "split", "base"])
def test_approved_body_and_preimage_bytes_are_checked_before_send(
    publisher: GoogleSheetsPublisher, change: str
) -> None:
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    if change == "body":
        prepared["requests"][0]["arguments"]["body"]["requests"][0]["updateCells"]["fields"] = "*"
    elif change == "split":
        prepared["requests"].append(copy.deepcopy(prepared["requests"][0]))
    else:
        prepared["base_snapshot"]["sheets"]["7"]["cells"]["1:1"]["note"] = "changed preimage"
    publisher._request = Mock()
    with pytest.raises(SheetsRequestError, match=r"approved bytes|one atomic batch"):
        publisher.execute_prepared(prepared)
    publisher._request.assert_not_called()


@pytest.mark.parametrize("field", ["merges", "protectedRanges", "bandedRanges", "filterViews", "conditionalFormats"])
def test_row_deletion_rejects_nonowned_metadata_even_without_values(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    region = {"sheetId": 7, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 5, "endColumnIndex": 7}
    value = region if field == "merges" else {"range": region}
    if field == "conditionalFormats":
        value = {
            "ranges": [region],
            "booleanRule": {"condition": {"type": "NOT_BLANK"}, "format": {"textFormat": {"bold": True}}},
        }
    publisher.inspect_workbook.return_value["sheets"]["7"]["metadata"][field] = [value]
    with pytest.raises(ValueError, match="deleting whole rows intersects non-owned"):
        publisher.prepare_table("spreadsheet", "items", [["header"], [1]])
    publisher._service.spreadsheets.assert_not_called()


def test_retained_table_column_types_are_checked_after_atomic_write(publisher: GoogleSheetsPublisher) -> None:
    publisher.inspect_workbook.return_value["sheets"]["7"]["metadata"]["tables"][0]["columnProperties"] = [
        {"columnIndex": 0, "columnName": "Old", "columnType": "TEXT"},
    ]
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    observed = observed_fixture(prepared)
    observed["sheets"]["7"]["metadata"]["tables"][0]["columnProperties"][0]["columnType"] = "DOUBLE"
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    with pytest.raises(SheetsRequestError, match="postflight"):
        publisher.execute_prepared(prepared)
    publisher._request.assert_called_once()


@pytest.mark.parametrize("selected", [False, True])
def test_unknown_stable_cell_field_fails_before_approval(publisher: GoogleSheetsPublisher, selected: bool) -> None:
    base = publisher.inspect_workbook.return_value
    sheet = base["sheets"]["7"] if selected else copy.deepcopy(base["sheets"]["7"])
    if not selected:
        sheet["metadata"]["properties"].update(sheetId=8, title="unselected")
        base["sheets"]["8"] = sheet
    sheet["cells"]["5:1"]["futureCellField"] = {"stableIdentity": "editor"}
    with pytest.raises(ValueError, match="unsupported futureCellField"):
        publisher.prepare_table("spreadsheet", "items", same_rows())
    publisher._service.spreadsheets.assert_not_called()


def add_unselected_anchor(publisher: GoogleSheetsPublisher, field: str, definition: dict) -> None:
    publisher.inspect_workbook.return_value["sheets"]["8"] = _sheet_snapshot(
        {
            "properties": {"sheetId": 8, "title": "unselected", "gridProperties": {"rowCount": 12, "columnCount": 8}},
            "data": [{"rowData": [{"values": [{field: copy.deepcopy(definition)}]}]}],
        }
    )


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_unselected_connected_anchor_identity_is_checked(publisher: GoogleSheetsPublisher, field: str) -> None:
    definition = (
        {"source": {"sheetId": 7, "startRowIndex": 1, "endRowIndex": 7}}
        if field == "pivotTable"
        else {"dataSourceId": "original"}
    )
    add_unselected_anchor(publisher, field, definition)
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    observed = observed_fixture(prepared)
    anchor = observed["sheets"]["8"]["cells"]["0:0"][field]
    if field == "pivotTable":
        anchor["source"]["sheetId"] = 99
    else:
        anchor["dataSourceId"] = "replacement"
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    with pytest.raises(SheetsRequestError, match="postflight"):
        publisher.execute_prepared(prepared)
    publisher._request.assert_called_once()


@pytest.mark.parametrize("change_definition", [False, True])
def test_pivot_source_rebasing_is_provider_managed_but_definition_is_checked(
    publisher: GoogleSheetsPublisher, change_definition: bool
) -> None:
    add_unselected_anchor(
        publisher,
        "pivotTable",
        {
            "source": {
                "sheetId": 7,
                "startRowIndex": 1,
                "endRowIndex": 7,
                "startColumnIndex": 1,
                "endColumnIndex": 3,
            },
            "values": [{"summarizeFunction": "SUM", "sourceColumnOffset": 0}],
        },
    )
    prepared = publisher.prepare_table("spreadsheet", "items", [["header"], [1], [2], [3], [4]])
    observed = observed_fixture(prepared)
    pivot = observed["sheets"]["8"]["cells"]["0:0"]["pivotTable"]
    pivot["source"]["endRowIndex"] = 9
    if change_definition:
        pivot["values"][0]["summarizeFunction"] = "AVERAGE"
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    if change_definition:
        with pytest.raises(SheetsRequestError, match="postflight"):
            publisher.execute_prepared(prepared)
    else:
        receipt = publisher.execute_prepared(prepared)
        assert receipt["postflight_snapshot"]["sheets"]["8"]["cells"]["0:0"]["pivotTable"] == pivot
    publisher._request.assert_called_once()


def test_unselected_data_source_table_definition_is_checked(publisher: GoogleSheetsPublisher) -> None:
    add_unselected_anchor(publisher, "dataSourceTable", {"dataSourceId": "original", "rowLimit": 10})
    prepared = publisher.prepare_table("spreadsheet", "items", same_rows())
    observed = observed_fixture(prepared)
    observed["sheets"]["8"]["cells"]["0:0"]["dataSourceTable"]["rowLimit"] = 20
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    with pytest.raises(SheetsRequestError, match="postflight"):
        publisher.execute_prepared(prepared)
    publisher._request.assert_called_once()


def selected_tab_anchor(publisher: GoogleSheetsPublisher, field: str, address: str = "9:9") -> list:
    sheet = publisher.inspect_workbook.return_value["sheets"]["7"]
    sheet["metadata"]["properties"]["gridProperties"]["columnCount"] = 12
    sheet["metadata"]["tables"][0]["range"].update(startRowIndex=0, endRowIndex=4, startColumnIndex=0, endColumnIndex=2)
    if field == "pivotTable":
        definition = {
            "source": {
                "sheetId": 7,
                "startRowIndex": 0,
                "endRowIndex": 4,
                "startColumnIndex": 0,
                "endColumnIndex": 2,
            },
            "values": [{"summarizeFunction": "SUM", "sourceColumnOffset": 1}],
        }
    elif field == "dataSourceTable":
        definition = {"dataSourceId": "connected", "rowLimit": 10}
    else:
        definition = {"dataSourceId": "connected"}
    cell = {field: definition}
    if field == "dataSourceFormula":
        cell["userEnteredValue"] = {"formulaValue": "=SUM(Connected!Column)"}
    sheet["cells"][address] = cell
    return [["name", "value"], ["a", 1], ["b", 2], ["c", 3]]


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_same_size_a1_b4_update_preserves_unrelated_j10_anchor(publisher: GoogleSheetsPublisher, field: str) -> None:
    rows = selected_tab_anchor(publisher, field)
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    body = prepared["requests"][0]["arguments"]["body"]["requests"]
    assert body[0]["updateCells"]["start"] == {"sheetId": 7, "rowIndex": 0, "columnIndex": 0}
    assert [len(row["values"]) for row in body[0]["updateCells"]["rows"]] == [2, 2, 2, 2]
    original_anchor = copy.deepcopy(prepared["base_snapshot"]["sheets"]["7"]["cells"]["9:9"])
    observed = observed_fixture(prepared)
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    assert receipt["postflight_snapshot"]["sheets"]["7"]["cells"]["9:9"] == original_anchor
    publisher._request.assert_called_once()


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_actual_raw_write_overlap_with_dynamic_anchor_rejects_before_mutation(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    rows = selected_tab_anchor(publisher, field, "2:0")
    publisher._request = Mock()
    with pytest.raises(ValueError, match=f"unsupported {field}.*RAW writes"):
        publisher.prepare_table("spreadsheet", "items", rows)
    publisher._request.assert_not_called()


@pytest.mark.parametrize("grow", [False, True])
def test_row_resize_before_unrelated_pivot_moves_whole_object(publisher: GoogleSheetsPublisher, grow: bool) -> None:
    rows = selected_tab_anchor(publisher, "pivotTable")
    rows = [*rows, ["d", 4], ["e", 5]] if grow else rows[:3]
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    observed = observed_fixture(prepared)
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    address = "11:9" if grow else "8:9"
    assert receipt["postflight_snapshot"]["sheets"]["7"]["cells"][address]["pivotTable"]
    publisher._request.assert_called_once()


@pytest.mark.parametrize("grow", [False, True])
def test_row_resize_below_unrelated_pivot_does_not_infer_a_spill_rectangle(
    publisher: GoogleSheetsPublisher, grow: bool
) -> None:
    rows = selected_tab_anchor(publisher, "pivotTable", "0:9")
    rows = [*rows, ["d", 4], ["e", 5]] if grow else rows[:3]
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    observed = observed_fixture(prepared)
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    assert receipt["postflight_snapshot"]["sheets"]["7"]["cells"]["0:9"]["pivotTable"]
    assert any("dynamic-output extents" in limitation for limitation in prepared["limitations"])
    publisher._request.assert_called_once()


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_disjoint_same_row_writes_do_not_infer_a_dynamic_output_rectangle(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    rows = selected_tab_anchor(publisher, field, "0:0")
    sheet = publisher.inspect_workbook.return_value["sheets"]["7"]
    sheet["metadata"]["tables"][0]["range"].update(startColumnIndex=9, endColumnIndex=11)
    if field == "pivotTable":
        sheet["cells"]["0:0"][field]["source"].update(startColumnIndex=9, endColumnIndex=11)
    prepared = publisher.prepare_table("spreadsheet", "items", rows)
    observed = observed_fixture(prepared)
    publisher.inspect_workbook.side_effect = [prepared["base_snapshot"], observed]
    publisher._request = Mock(side_effect=acknowledge)
    receipt = publisher.execute_prepared(prepared)
    assert receipt["postflight_snapshot"]["sheets"]["7"]["cells"]["0:0"][field]
    publisher._request.assert_called_once()


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_known_whole_row_deletion_erases_unowned_anchor_and_rejects_before_mutation(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    rows = selected_tab_anchor(publisher, field, "3:9")
    publisher._request = Mock()
    with pytest.raises(ValueError, match=r"deleting whole rows.*non-owned cell.*J4"):
        publisher.prepare_table("spreadsheet", "items", rows[:3])
    publisher._request.assert_not_called()


@pytest.mark.parametrize("field", ["pivotTable", "dataSourceTable", "dataSourceFormula"])
def test_width_expansion_into_existing_j1_anchor_rejects_before_mutation(
    publisher: GoogleSheetsPublisher, field: str
) -> None:
    rows = selected_tab_anchor(publisher, field, "0:9")
    rows = [row + [""] * 8 for row in rows]
    publisher._request = Mock()
    with pytest.raises(ValueError, match=r"width expansion overlaps non-owned cell.*J1"):
        publisher.prepare_table("spreadsheet", "items", rows)
    publisher._request.assert_not_called()
