from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from erenshor.infrastructure.config.paths import get_path_resolver

__all__ = ["Category", "EventType", "Reporter", "Severity", "entity", "open"]


logger = logging.getLogger(__name__)


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Category(str, Enum):
    ITEMS = "items"
    CHARACTERS = "characters"
    ABILITIES = "abilities"
    FISHING = "fishing"
    VALIDATE = "validate"
    AUDIT = "audit"
    IO = "io"


class EventType(str, Enum):
    UPDATE = "update"
    VIOLATION = "violation"
    ERROR = "error"
    METRIC = "metric"


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _run_id(command: str) -> str:
    ts = _utc_now_iso().replace(":", "-")
    safe_cmd = command.replace(" ", "_")
    return f"{ts}_{safe_cmd}"


def entity(
    *,
    page_title: Optional[str] = None,
    resource_name: Optional[str] = None,
    db_id: Optional[str] = None,
    guid: Optional[str] = None,
    file_path: Optional[str] = None,
) -> Dict[str, str]:
    e: Dict[str, str] = {}
    if page_title is not None:
        e["page_title"] = page_title
    if resource_name is not None:
        e["resource_name"] = resource_name
    if db_id is not None:
        e["db_id"] = db_id
    if guid is not None:
        e["guid"] = guid
    if file_path is not None:
        e["file_path"] = file_path
    return e


@dataclass
class Reporter:
    run_id: str
    command: str
    args: Dict[str, Any]
    base_dir: Path
    schema_version: str = "1.0"
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None

    # counters
    total_events: int = 0
    errors_count: int = 0
    violations_count: int = 0
    updates_count: int = 0
    counts_by_severity: Dict[str, int] = field(default_factory=dict)
    counts_by_category: Dict[str, int] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # file handles
    _events_fp: Any = field(default=None, repr=False)

    @classmethod
    def open(
        cls,
        *,
        command: str,
        args: Dict[str, Any] | None = None,
        reports_dir: Path | None = None,
    ) -> "Reporter":
        """Open a new reporter with optional reports directory override.

        Args:
            command: Command name for this report
            args: Command arguments
            reports_dir: Optional reports directory override. If None, uses PathResolver default.

        Returns:
            Reporter instance
        """
        if reports_dir is None:
            resolver = get_path_resolver()
            reports_dir = resolver.reports_dir
        rid = _run_id(command)
        base = reports_dir / rid
        base.mkdir(parents=True, exist_ok=True)
        rep = cls(run_id=rid, command=command, args=args or {}, base_dir=base)
        rep._events_fp = (base / "events.jsonl").open("a", encoding="utf-8")
        return rep

    def _emit(self, payload: Dict[str, Any]) -> None:
        payload["timestamp"] = _utc_now_iso()
        payload["run_id"] = self.run_id
        payload["command"] = self.command
        self._events_fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._events_fp.flush()
        self.total_events += 1
        sev = payload.get("severity")
        if sev:
            self.counts_by_severity[sev] = self.counts_by_severity.get(sev, 0) + 1
        cat = payload.get("category")
        if cat:
            self.counts_by_category[cat] = self.counts_by_category.get(cat, 0) + 1

    def emit_update(
        self,
        *,
        entity: Dict[str, str] | None = None,
        action: str,
        category: Category = Category.ITEMS,
        details: Dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            {
                "type": EventType.UPDATE.value,
                "severity": Severity.INFO.value,
                "category": str(category.value),
                "action": action,
                "entity": entity or {},
                "details": details or {},
            }
        )
        self.updates_count += 1

    def emit_violation(
        self,
        *,
        rule_id: str,
        message: str,
        entity: Dict[str, str] | None = None,
        category: Category = Category.VALIDATE,
        details: Dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            {
                "type": EventType.VIOLATION.value,
                "severity": Severity.ERROR.value,
                "category": str(category.value),
                "rule_id": rule_id,
                "message": message,
                "entity": entity or {},
                "details": details or {},
            }
        )
        self.violations_count += 1

    def emit_error(
        self,
        *,
        message: str,
        exception: Optional[Exception] = None,
        entity: Dict[str, str] | None = None,
        category: Category = Category.IO,
        details: Dict[str, Any] | None = None,
    ) -> None:
        exc_payload = None
        if exception is not None:
            exc_payload = {"name": type(exception).__name__, "message": str(exception)}
        self._emit(
            {
                "type": EventType.ERROR.value,
                "severity": Severity.ERROR.value,
                "category": str(category.value),
                "message": message,
                "exception": exc_payload,
                "entity": entity or {},
                "details": details or {},
            }
        )
        self.errors_count += 1

    def metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value
        self._emit(
            {
                "type": EventType.METRIC.value,
                "severity": Severity.INFO.value,
                "category": Category.VALIDATE.value,
                "key": key,
                "value": value,
            }
        )

    def finish(self, *, exit_code: int = 0) -> None:
        self.finished_at = _utc_now_iso()
        self.exit_code = exit_code
        # summary
        summary = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "command": self.command,
            "counts": {
                "total_events": self.total_events,
                "errors": self.errors_count,
                "violations": self.violations_count,
                "updates": self.updates_count,
            },
            "counts_by_severity": self.counts_by_severity,
            "counts_by_category": self.counts_by_category,
            "metrics": self.metrics,
        }
        (self.base_dir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        manifest = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "command": self.command,
            "args": self.args,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
        }
        (self.base_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        if self._events_fp is not None:
            try:
                self._events_fp.close()
            except Exception as e:
                logger.warning(f"Failed to close events file: {e}")

    def summary_line(self) -> str:
        return (
            f"command={self.command} violations={self.violations_count} "
            f"errors={self.errors_count} updates={self.updates_count} run={self.base_dir}"
        )
