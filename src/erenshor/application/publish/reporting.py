"""Pure human review views over authoritative publication payloads and journals."""

from __future__ import annotations

import json
from typing import Any

from erenshor.application.publish.models import canonical, sha256

# These fields contain bytes to inspect separately, not operation or guard metadata.
_BULK_FIELDS = frozenset(
    {
        "rows",
        "values",
        "cells",
        "rowData",
        "base_snapshot",
        "postflight_snapshot",
        "observed_postimage",
        "asset_manifest",
        "worker_manifest",
        "files",
        "batch_body",
        "input_snapshots",
        "source_files",
        "original",
        "content",
        "diff",
        "source_text",
        "original_text",
        "text",
        "html",
    }
)


def _pointer(parent: str, key: str | int) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _path(path: str, run_dir: str | None) -> str:
    if not run_dir:
        return path
    if path == "$RUN" or path.startswith("$RUN/"):
        return run_dir.rstrip("/") + path[4:]
    if not path.startswith(("/", "$")):
        return run_dir.rstrip("/") + "/" + path
    return path


def _reference(value: Any, source: dict[str, Any], pointer: str) -> dict[str, Any]:
    raw = value.encode("utf-8") if isinstance(value, str) else canonical(value)
    result = {
        "omitted": True,
        **source,
        "json_pointer": pointer,
        "sha256": sha256(raw),
        "bytes": len(raw),
        "encoding": "utf-8" if isinstance(value, str) else "canonical-json",
        "count": len(value) if isinstance(value, str | list | dict) else 1,
    }
    if isinstance(value, str):
        result["line_count"] = len(value.splitlines())
    if isinstance(value, list) and pointer.rsplit("/", 1)[-1] in {"rows", "values", "rowData"}:
        widths = [len(row if isinstance(row, list) else row.get("values", [])) for row in value]
        result.update(row_count=len(value), column_count=max(widths, default=0), cell_count=sum(widths))
    if isinstance(value, dict) and isinstance(value.get("sheets"), dict):
        result.update(
            sheet_count=len(value["sheets"]),
            cell_count=sum(len(sheet.get("cells", {})) for sheet in value["sheets"].values()),
        )
    return result


def _summarize(value: Any, source: dict[str, Any], pointer: str = "") -> Any:
    if isinstance(value, dict):
        if value.get("omitted") is True:
            return dict(value)
        result = {}
        for key, item in value.items():
            child = _pointer(pointer, key)
            if key in _BULK_FIELDS and isinstance(item, str | list | dict):
                if isinstance(item, dict) and item.get("omitted") is True:
                    result[key] = dict(item)
                    continue
                reference = _reference(item, source, child)
                if key == "batch_body" and value.get("batch_body_path"):
                    reference["sidecar_path"] = value["batch_body_path"]
                if key in {"asset_manifest", "worker_manifest", "files", "source_files"} and isinstance(item, dict):
                    reference["file_count"] = len(item)
                    reference["file_bytes"] = sum(
                        entry.get("size", 0) for entry in item.values() if isinstance(entry, dict)
                    )
                    reference["provider_manifest_sha256"] = sha256(
                        json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                    )
                result[key] = reference
            else:
                result[key] = _summarize(item, source, child)
        return result
    if isinstance(value, list):
        return [_summarize(item, source, _pointer(pointer, index)) for index, item in enumerate(value)]
    return value


def review_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Retain every operation and guard, replacing bulk bytes with exact references.

    Payload paths are relative to report.run_dir. $RUN paths use the same root.
    Hashes describe the referenced field bytes, not the enclosing artifact file.
    Operation payload_sha256 and inputs retain the authoritative file hashes.
    """
    run_dir = report.get("run_dir")
    review_path = report.get("review_path", "$RUN/review.json")
    result = {
        key: _summarize(value, {"path": _path(review_path, run_dir)}, _pointer("", key))
        for key, value in report.items()
        if key not in {"operations", "execution"}
    }
    result["operations"] = []
    for index, operation in enumerate(report.get("operations", [])):
        summary = {key: value for key, value in operation.items() if key != "payload"}
        source = {"path": _path(operation["payload_path"], run_dir)}
        summary = _summarize(summary, {"path": _path(review_path, run_dir)}, _pointer("/operations", index))
        if len(operation.get("inputs", {})) > 32 and not operation["inputs"].get("omitted"):
            summary["inputs"] = _reference(
                operation["inputs"],
                {"path": _path(report.get("plan_path", "$RUN/plan.json"), run_dir)},
                _pointer(_pointer("/operations", index), "inputs"),
            )
        if "payload" in operation:
            summary["payload"] = _summarize(operation["payload"], source)
            body = summary["payload"].get("batch_body")
            if isinstance(body, dict) and body.get("sidecar_path"):
                body["sidecar_path"] = _path(body["sidecar_path"], run_dir)
            worker = operation["payload"].get("worker_manifest", {})
            bundle = operation["payload"].get("bundle", "").rsplit("/", 1)[-1]
            if isinstance(worker, dict) and isinstance(worker.get(bundle), dict):
                summary["payload"]["bundle_sha256"] = worker[bundle]["sha256"]
        result["operations"].append(summary)
    result["operation_count"] = len(result["operations"])
    if "execution" in report:
        result["execution"] = status_summary(report["execution"])
    return result


def status_summary(status: dict[str, Any]) -> dict[str, Any]:
    """Preserve receipt and recovery history without embedding workbook postimages.

    Journal references identify the exact JSONL record by its checksum. Their
    JSON pointers are relative to that record, including for nested evidence.
    """
    run_dir = status.get("run_dir")
    source = {"path": _path(status.get("journal", "$RUN/journal.jsonl"), run_dir)}
    result = {key: value for key, value in status.items() if key != "operations"}
    result["operations"] = []
    for index, operation in enumerate(status.get("operations", [])):
        summary = {key: value for key, value in operation.items() if key not in {"evidence", "history"}}
        if len(operation.get("inputs", {})) > 32 and not operation["inputs"].get("omitted"):
            summary["inputs"] = _reference(
                operation["inputs"],
                {"path": _path(status.get("plan_path", "$RUN/plan.json"), run_dir)},
                _pointer(_pointer("/operations", index), "inputs"),
            )
        for key in ("evidence", "history"):
            if key not in operation:
                continue
            events = operation[key] if key == "history" else [operation[key]]
            summarized = [_summarize(event, {**source, "record_checksum": event.get("checksum")}) for event in events]
            summary[key] = summarized if key == "history" else summarized[0]
        result["operations"].append(summary)
    result["operation_count"] = len(result["operations"])
    return result
