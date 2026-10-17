"""One reviewed provider-atomic publication for selected spreadsheet tabs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erenshor.application.publish.models import PublishError, SurfaceUncertainError
from erenshor.application.sheets.service import create_sheets_service
from erenshor.infrastructure.publishers.sheets import SheetsRequestError

if TYPE_CHECKING:
    from erenshor.application.sheets.service import SheetsService
    from erenshor.cli.context import CLIContext


RECOVERY = (
    "No automatic retry or transactional Sheets rollback. Retain the full stable workbook preimage, "
    "exact atomic batch body and request journal. A lost acknowledgement requires manual provider "
    "reconciliation and a new plan. Resume completed work only against its retained observed postimage."
)


def _destination(ctx: CLIContext, service: SheetsService) -> dict[str, Any]:
    return {
        **service.destination_identity(),
        "map_base_url": ctx.config.variants[ctx.variant].maps.base_url,
    }


def prepare(ctx: CLIContext, selection: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    """Execute selected SQL and inspect the workbook without creating remote state."""
    tabs = selection.get("tabs", [])
    if not tabs or len(set(tabs)) != len(tabs):
        raise PublishError("Sheets publication requires distinct exact selected tabs")
    service = create_sheets_service(ctx)
    try:
        available = {tab.name for tab in service.list_sheets()}
        missing = sorted(set(tabs) - available)
        if missing:
            raise PublishError(f"Invalid sheet names: {', '.join(missing)}")
        database = ctx.config.variants[ctx.variant].resolved_database(ctx.repo_root)
        application_dir = Path(__file__).resolve().parents[1]
        destination = _destination(ctx, service)
        payload = service.prepare_tabs(tabs)
        payload["destination"] = destination
        payload["summary"] = selection.get("summary", "")
        return [
            {
                "id": f"sheet:{destination['spreadsheet_id']}",
                "kind": "sheet",
                "target": destination["spreadsheet_id"],
                "dependencies": [],
                "payload": payload,
                "expected_base": {
                    "sha256": payload["base_sha256"],
                    "selected_tabs": [tab["sheet_name"] for tab in payload["tabs"]],
                    "guard": payload["guard"],
                },
                "recovery": RECOVERY,
                "inputs": [
                    str(database.resolve()),
                    *(query["path"] for query in payload["queries"]),
                    str(Path(__file__).resolve()),
                    str(application_dir / "sheets" / "service.py"),
                    str(application_dir / "sheets" / "formatter.py"),
                    str(application_dir.parent / "infrastructure" / "publishers" / "sheets.py"),
                ],
                "destination": destination,
            }
        ]
    finally:
        service.close()


def _assert_identity(
    ctx: CLIContext, service: SheetsService, operation: dict[str, Any], payload: dict[str, Any]
) -> None:
    destination = _destination(ctx, service)
    if operation["destination"] != destination or payload["destination"] != destination:
        raise PublishError("Sheets account or destination changed")
    if operation["target"] != destination["spreadsheet_id"] or payload["spreadsheet_id"] != operation["target"]:
        raise PublishError("Prepared Sheets payload targets a different destination")
    tabs = [tab["sheet_name"] for tab in payload["tabs"]]
    if [query["sheet_name"] for query in payload["queries"]] != tabs:
        raise PublishError("Prepared Sheets SQL selection differs from its native batch")
    expected_base = {"sha256": payload["base_sha256"], "selected_tabs": tabs, "guard": payload["guard"]}
    if operation["expected_base"] != expected_base:
        raise PublishError("Prepared Sheets base or tab selection does not match its operation")


def check(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> None:
    """Recheck the full stable workbook base, including all unselected tabs."""
    service = create_sheets_service(ctx)
    try:
        _assert_identity(ctx, service, operation, payload)
        service.publisher.check_prepared(payload)
    finally:
        service.close()


def execute(
    ctx: CLIContext, operation: dict[str, Any], payload: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Send one atomic native batch with a durable intent and acknowledgement."""
    if ctx.dry_run:
        raise PublishError("Dry-run Sheets operations cannot execute")
    if set(operation["dependencies"]) - set(receipts):
        raise PublishError("Sheets predecessors have not completed")
    service = create_sheets_service(ctx)
    log_path = Path(operation["_run_dir"]) / (
        "sheets-" + hashlib.sha256(operation["id"].encode()).hexdigest() + ".jsonl"
    )
    try:
        _assert_identity(ctx, service, operation, payload)
        journal_root = log_path
        attempt = 1
        while log_path.exists():
            content = log_path.read_bytes()
            events = [json.loads(line) for line in content.splitlines()] if content.endswith(b"\n") else []
            known_unwritten = (
                bool(events)
                and all(
                    event.get("operation") == operation["id"]
                    and event.get("payload_sha256") == operation["payload_sha256"]
                    for event in events
                )
                and events[-1]["evidence"].get("safe_to_resume") is True
                and not any(
                    outcome.get("status") != "rejected" for outcome in events[-1]["evidence"].get("outcomes", [])
                )
            )
            if not known_unwritten:
                raise SurfaceUncertainError(
                    "Sheets request journal already exists. Reconcile it before preparing a new plan",
                    {"journal_path": str(log_path)},
                )
            # Only explicit coordinator resume can reach another execution.
            # An acknowledged rejection with no writes permits a new attempt.
            attempt += 1
            log_path = journal_root.with_name(f"{journal_root.stem}-{attempt}.jsonl")
        with log_path.open("x", encoding="utf-8") as stream:
            directory = os.open(log_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

            def checkpoint(evidence: dict[str, Any]) -> None:
                event = {
                    "operation": operation["id"],
                    "payload_sha256": operation["payload_sha256"],
                    "evidence": evidence,
                }
                stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

            try:
                provider = service.publisher.execute_prepared(payload, outcome_sink=checkpoint)
            except SheetsRequestError as exc:
                checkpoint(exc.evidence)
                exc.evidence["journal_path"] = str(log_path)
                if exc.uncertain:
                    raise SurfaceUncertainError(str(exc), exc.evidence) from exc
                raise
        return {
            "provider": provider,
            "destination": operation["destination"],
            "journal_path": str(log_path),
            "journal_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        }
    finally:
        service.close()


def reconcile(
    ctx: CLIContext,
    operation: dict[str, Any],
    payload: dict[str, Any],
    receipt: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> None:
    """Accept only an acknowledged atomic batch and its exact observed state."""
    service = create_sheets_service(ctx)
    try:
        _assert_identity(ctx, service, operation, payload)
        if receipt.get("destination") != operation["destination"]:
            raise PublishError("Sheets receipt destination differs from the approved operation")
        log_path = Path(receipt["journal_path"])
        run_dir = Path(operation["_run_dir"]).resolve()
        if log_path.resolve().parent != run_dir:
            raise PublishError("Sheets request journal is outside its run directory")
        content = log_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != receipt.get("journal_sha256"):
            raise PublishError("Sheets request journal differs from its receipt")
        if not content.endswith(b"\n"):
            raise PublishError("Sheets request journal has an incomplete checkpoint")
        events = [json.loads(line) for line in content.splitlines()]
        if (
            not events
            or any(
                event.get("operation") != operation["id"] or event.get("payload_sha256") != operation["payload_sha256"]
                for event in events
            )
            or events[-1]["evidence"] != receipt["provider"]
        ):
            raise PublishError("Sheets receipt is not tied to the approved request journal")
        service.publisher.reconcile_prepared(payload, receipt["provider"])
    finally:
        service.close()
