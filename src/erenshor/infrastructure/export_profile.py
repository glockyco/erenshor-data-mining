"""Persistent macro profiling for extraction pipeline runs."""

from __future__ import annotations

import json
import platform
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from erenshor.infrastructure.time import Clock, RealClock


@dataclass(slots=True)
class ProfileSpan:
    """A single timed span in an extraction profile run."""

    run_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    category: str
    started_at: float
    ended_at: float
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Span duration in milliseconds, rounded for stable persistence."""
        return round((self.ended_at - self.started_at) * 1000.0, 3)


class ExportProfileRecorder:
    """Record extraction profile spans across separate CLI invocations."""

    @classmethod
    def open_or_create(
        cls,
        *,
        root: Path,
        variant: str,
        command: str,
        game_build_id: str | None,
        git_sha: str | None,
        unity_version: str | None,
        assetripper_version: str | None,
        machine: str | None = None,
        clock: Clock | None = None,
    ) -> ExportProfileRecorder:
        """Open the active variant/build run or create a new one."""
        active = cls._read_active_run(root)
        if (
            active
            and active["variant"] == variant
            and active.get("game_build_id") == game_build_id
            and cls._active_run_is_running(root, active["run_id"])
        ):
            return cls(
                root=root,
                run_id=active["run_id"],
                variant=variant,
                command=active.get("command", "refresh pipeline"),
                game_build_id=game_build_id,
                git_sha=git_sha,
                unity_version=unity_version,
                assetripper_version=assetripper_version,
                machine=machine,
                clock=clock,
                started_at_iso=active["started_at"],
            )

        recorder = cls(
            root=root,
            run_id=cls._make_run_id(variant, game_build_id),
            variant=variant,
            command="refresh pipeline",
            game_build_id=game_build_id,
            git_sha=git_sha,
            unity_version=unity_version,
            assetripper_version=assetripper_version,
            machine=machine,
            clock=clock,
            started_at_iso=None,
        )
        recorder._write_active_run()
        return recorder

    def __init__(
        self,
        *,
        root: Path,
        run_id: str,
        variant: str,
        command: str,
        game_build_id: str | None,
        git_sha: str | None,
        unity_version: str | None,
        assetripper_version: str | None,
        machine: str | None = None,
        clock: Clock | None = None,
        started_at_iso: str | None = None,
    ) -> None:
        self.root = root
        self.variant = variant
        self.command = command
        self.game_build_id = game_build_id
        self.git_sha = git_sha
        self.unity_version = unity_version
        self.assetripper_version = assetripper_version
        self.machine = machine if machine is not None else f"{platform.system().lower()}-{platform.machine().lower()}"
        self.clock = clock if clock is not None else RealClock()
        self.run_id = run_id
        self.started_at = self.clock.time() if started_at_iso is None else self._from_iso(started_at_iso)
        self.ended_at: float | None = None
        self.status = "running"
        self._span_stack: list[tuple[str, str, str, float, dict[str, Any]]] = []
        self._ensure_schema()
        self.spans: list[ProfileSpan] = self._load_existing_spans()
        self._next_span_id = self._load_next_span_id()
        self._persist_run()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        category: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        """Record a timed span and persist it when the block exits."""
        span_id = f"{self._next_span_id:06d}"
        self._next_span_id += 1
        parent_span_id = self._span_stack[-1][0] if self._span_stack else None
        start = self.clock.time()
        attrs = attributes if attributes is not None else {}
        self._span_stack.append((span_id, name, category, start, attrs))
        status = "ok"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            self._span_stack.pop()
            span = ProfileSpan(
                run_id=self.run_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=name,
                category=category,
                started_at=start,
                ended_at=self.clock.time(),
                status=status,
                attributes=attrs,
            )
            self.spans.append(span)
            self._persist_span(span)
            self._write_artifacts()

    def record_external_span(
        self,
        name: str,
        *,
        category: str,
        started_at: float,
        duration_ms: float,
        attributes: dict[str, Any] | None = None,
        status: str = "ok",
    ) -> None:
        """Persist a span measured outside this Python process."""
        span_id = f"{self._next_span_id:06d}"
        self._next_span_id += 1
        span = ProfileSpan(
            run_id=self.run_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            category=category,
            started_at=started_at,
            ended_at=started_at + (duration_ms / 1000.0),
            status=status,
            attributes=attributes if attributes is not None else {},
        )
        self.spans.append(span)
        self._persist_span(span)
        self._write_artifacts()

    def finish_command(self, command: str, status: str) -> None:
        """Record the most recent command result without closing the run."""
        if status == "failed":
            self.status = "failed"
        self._persist_run(last_command=command, last_command_status=status)
        self._write_artifacts()

    def update_game_build_id(self, game_build_id: str | None) -> None:
        """Retag the active run after a download discovers the current build."""
        self.game_build_id = game_build_id
        self._persist_run()
        self._write_active_run()
        self._write_artifacts()

    def finish(self, status: str) -> None:
        """Close the run with a final status."""
        self.status = status
        self.ended_at = self.clock.time()
        self._persist_run()
        self._clear_active_run()
        self._write_artifacts()

    def latest_summary_markdown(self) -> str:
        """Return a compact Markdown summary for the current run."""
        ordered = sorted(self.spans, key=lambda span: span.duration_ms, reverse=True)
        lines = [
            f"# Export Profile {self.run_id}",
            "",
            f"Variant: `{self.variant}`",
            f"Status: `{self.status}`",
            "",
            "## Top spans",
            "",
        ]
        for span in ordered[:20]:
            lines.append(f"- `{span.name}` — {span.duration_ms:.2f} ms")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _make_run_id(variant: str, game_build_id: str | None) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        build = game_build_id if game_build_id else "unknown"
        return f"{stamp}-{variant}-{build}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _read_active_run(root: Path) -> dict[str, Any] | None:
        active_path = root / "current-run.json"
        if not active_path.exists():
            return None
        return cast("dict[str, Any]", json.loads(active_path.read_text()))

    @staticmethod
    def _active_run_is_running(root: Path, run_id: str) -> bool:
        db_path = root / "export-runs.sqlite"
        if not db_path.exists():
            return False
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                status = cast(
                    "tuple[str] | None",
                    conn.execute(
                        "SELECT status FROM export_profile_runs WHERE run_id = ?",
                        (run_id,),
                    ).fetchone(),
                )
        except sqlite3.Error:
            return False
        return status == ("running",)

    def _clear_active_run(self) -> None:
        active_path = self.root / "current-run.json"
        if not active_path.exists():
            return
        active = self._read_active_run(self.root)
        if active and active.get("run_id") == self.run_id:
            active_path.unlink()

    def _write_active_run(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "current-run.json").write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "variant": self.variant,
                    "game_build_id": self.game_build_id,
                    "started_at": self._iso(self.started_at),
                    "command": self.command,
                },
                sort_keys=True,
            )
            + "\n"
        )

    def _load_next_span_id(self) -> int:
        db_path = self.root / "export-runs.sqlite"
        if not db_path.exists():
            return 1
        with closing(sqlite3.connect(db_path)) as conn:
            value = conn.execute(
                "SELECT MAX(CAST(span_id AS INTEGER)) FROM export_profile_spans WHERE run_id = ?",
                (self.run_id,),
            ).fetchone()[0]
        return int(value or 0) + 1

    def _ensure_schema(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "runs").mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.root / "export-runs.sqlite")) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS export_profile_runs (
                    run_id TEXT PRIMARY KEY,
                    variant TEXT NOT NULL,
                    command TEXT NOT NULL,
                    game_build_id TEXT,
                    git_sha TEXT,
                    unity_version TEXT,
                    assetripper_version TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL,
                    machine TEXT NOT NULL,
                    last_command TEXT,
                    last_command_status TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS export_profile_spans (
                    run_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    status TEXT NOT NULL,
                    attributes_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, span_id),
                    FOREIGN KEY (run_id) REFERENCES export_profile_runs(run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_export_profile_spans_run_duration
                ON export_profile_spans(run_id, duration_ms DESC)
                """
            )
            conn.commit()

    def _persist_run(self, last_command: str | None = None, last_command_status: str | None = None) -> None:
        with closing(sqlite3.connect(self.root / "export-runs.sqlite")) as conn:
            conn.execute(
                """
                INSERT INTO export_profile_runs (
                    run_id, variant, command, game_build_id, git_sha, unity_version,
                    assetripper_version, started_at, ended_at, status, machine,
                    last_command, last_command_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    game_build_id = COALESCE(excluded.game_build_id, export_profile_runs.game_build_id),
                    git_sha = COALESCE(excluded.git_sha, export_profile_runs.git_sha),
                    unity_version = COALESCE(excluded.unity_version, export_profile_runs.unity_version),
                    assetripper_version = COALESCE(
                        excluded.assetripper_version,
                        export_profile_runs.assetripper_version
                    ),
                    ended_at = excluded.ended_at,
                    status = excluded.status,
                    last_command = COALESCE(excluded.last_command, export_profile_runs.last_command),
                    last_command_status = COALESCE(
                        excluded.last_command_status,
                        export_profile_runs.last_command_status
                    )
                """,
                (
                    self.run_id,
                    self.variant,
                    self.command,
                    self.game_build_id,
                    self.git_sha,
                    self.unity_version,
                    self.assetripper_version,
                    self._iso(self.started_at),
                    self._iso(self.ended_at) if self.ended_at is not None else None,
                    self.status,
                    self.machine,
                    last_command,
                    last_command_status,
                ),
            )
            conn.commit()

    def _load_existing_spans(self) -> list[ProfileSpan]:
        db_path = self.root / "export-runs.sqlite"
        if not db_path.exists():
            return []
        with closing(sqlite3.connect(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT run_id, span_id, parent_span_id, name, category, started_at,
                       ended_at, status, attributes_json
                FROM export_profile_spans
                WHERE run_id = ?
                ORDER BY span_id
                """,
                (self.run_id,),
            ).fetchall()
        return [
            ProfileSpan(
                run_id=row[0],
                span_id=row[1],
                parent_span_id=row[2],
                name=row[3],
                category=row[4],
                started_at=self._from_iso(row[5]),
                ended_at=self._from_iso(row[6]),
                status=row[7],
                attributes=json.loads(row[8]),
            )
            for row in rows
        ]

    def _persist_span(self, span: ProfileSpan) -> None:
        with closing(sqlite3.connect(self.root / "export-runs.sqlite")) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO export_profile_spans (
                    run_id, span_id, parent_span_id, name, category, started_at,
                    ended_at, duration_ms, status, attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span.run_id,
                    span.span_id,
                    span.parent_span_id,
                    span.name,
                    span.category,
                    self._iso(span.started_at),
                    self._iso(span.ended_at),
                    span.duration_ms,
                    span.status,
                    json.dumps(span.attributes, sort_keys=True),
                ),
            )
            conn.commit()

    def _write_artifacts(self) -> None:
        run_dir = self.root / "runs"
        jsonl_path = run_dir / f"{self.run_id}.jsonl"
        trace_path = run_dir / f"{self.run_id}.trace.json"
        md_path = run_dir / f"{self.run_id}.md"
        all_spans = self._load_existing_spans()
        self.spans = all_spans
        jsonl_path.write_text("\n".join(self._jsonl_events(all_spans)) + "\n")
        trace_path.write_text(json.dumps({"traceEvents": self._trace_events(all_spans)}, indent=2) + "\n")
        md_path.write_text(self.latest_summary_markdown())

    def _jsonl_events(self, spans: list[ProfileSpan]) -> list[str]:
        events: list[dict[str, Any]] = [
            {
                "type": "run",
                "run_id": self.run_id,
                "variant": self.variant,
                "command": self.command,
                "status": self.status,
                "game_build_id": self.game_build_id,
                "git_sha": self.git_sha,
            }
        ]
        events.extend(
            {
                "type": "span",
                "run_id": span.run_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "name": span.name,
                "category": span.category,
                "duration_ms": span.duration_ms,
                "status": span.status,
                "attributes": span.attributes,
            }
            for span in spans
        )
        return [json.dumps(event, sort_keys=True) for event in events]

    def _trace_events(self, spans: list[ProfileSpan]) -> list[dict[str, Any]]:
        base = self.started_at
        return [
            {
                "name": span.name,
                "cat": span.category,
                "ph": "X",
                "ts": int((span.started_at - base) * 1_000_000),
                "dur": int((span.ended_at - span.started_at) * 1_000_000),
                "pid": 1,
                "tid": 1,
                "args": span.attributes,
            }
            for span in sorted(spans, key=lambda item: item.started_at)
        ]

    @staticmethod
    def _iso(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, UTC).isoformat()

    @staticmethod
    def _from_iso(timestamp: str) -> float:
        return datetime.fromisoformat(timestamp).timestamp()
