---
title: Export Profiling and CodeFacts Pinning Implementation Plan
type: plan
status: implemented
created: 2026-06-17
archived: 2026-06-25
parent:
---

# Export Profiling and CodeFacts Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make slow playtest refresh/export runs explainable as persisted macro traces, expose per-listener Unity costs, and add CodeFacts matcher support strong enough to pin the playtest guaranteed-loot retry loop.

**Architecture:** Treat each refresh/export as a one-shot macro trace, not a micro-benchmark. Because `download`, `rip`, `export`, `code-facts`, and `build` are separate CLI process invocations, each command opens the same persisted active run ID for the current variant/build and appends structured span rows to that shared store. The reporter reconstructs the cross-stage trace from SQLite/JSONL, not by parsing logs. Unity export profiling records shared scanner work, dispatch/reflection overhead, `OnAssetFound` listener cost, and `OnScanFinished` database-write cost separately. CodeFacts gains a generic compound-node shape matcher for decompiled AST nodes such as `for` and `do/while`.

**Tech Stack:** Python Typer CLI, Loguru, Rich, SQLite, JSONL, Chrome trace JSON for Perfetto, existing `Clock`/`MockClock`, Unity Editor C# export scripts, `Stopwatch`, ICSharpCode.Decompiler/CSharp AST, pytest, dotnet fixture tests.

---

## Macro vs Micro Benchmarking Boundary

This work is for macro profiling. A refresh/export run is side-effectful, variant-dependent, minutes long, and cannot be looped thousands of times. Use wall-clock spans and persisted run telemetry.

Do not use BenchmarkDotNet or warmup/iteration benchmark harnesses for the Unity export pipeline. BenchmarkDotNet-style tooling is appropriate only for pure, isolated code such as `LootTableProbabilityCalculator` if we later need CPU/allocation comparisons for that function.

## Current Findings

The project already has limited export timing:

- `src/Assets/Editor/ExportBatch.cs` logs `[EXPORT_COMPLETE]` total Unity export time.
- `ExportBatch.ExecuteScanSynchronously()` logs broad scan phases: `ScriptableObjects`, `Prefabs`, `Scenes`.
- `src/erenshor/infrastructure/unity/batch_mode.py` logs `Still exporting...` every 30 seconds and has a total timeout.
- `src/erenshor/infrastructure/assetripper/assetripper.py` logs `Still exporting...` every 30 seconds while monitoring AssetRipper.

That is not enough. It cannot separate Steam download, AssetRipper startup/load/export/monitoring, Unity launch/license/import/compile overhead, C# scan time, per-listener `OnAssetFound`, reflective dispatch overhead, listener `OnScanFinished()` database writes, code-facts, and clean DB build.

Per-listener profiling is cleanly extractable, but only if it matches the actual dispatch model:

- Shared scanner work is not attributable to one listener: `Resources.LoadAll`, `AssetDatabase.FindAssets`, prefab loading, scene open, hierarchy traversal, and `GetComponents<Component>()` belong in `scanner.shared.*` spans.
- Listener `OnAssetFound` calls are interleaved across assets and listeners, so each listener needs an accumulator around every matching call.
- Listener `OnScanFinished` is a separate finalization phase and must be reported separately; this is where table creation, deletes, bulk inserts, and other database writes usually land.
- Current reflective dispatch performs repeated `GetMethod("OnAssetFound")` lookups in hot loops. Profiling must either report this as `dispatch.method_lookup` or cache it first and report the post-cache listener costs.

CodeFacts also needs stronger pinning. The playtest loot patch forced `loot.guarantee_one_drop` to pin only `ActualDrops.Add (item);` because `statement_shape` only matches `ExpressionStatement`. It cannot pin the surrounding `for (int i = 0; i < NumberOfGuaranteedDrops; i++)` and `do/while` retry loop, which is the actual semantic contract the probability calculator re-implements.

## File Structure

### New Python profiling module

`src/erenshor/infrastructure/export_profile.py`

Owns active run ID persistence, span collection, JSONL emission, SQLite persistence, Chrome trace JSON generation, and Markdown summary generation. It has no Typer dependency.

### CLI integration

`src/erenshor/cli/commands/extract.py`

Opens the active profile run for commands that perform real work, records high-level spans into the shared run, adds `extract profile report --latest`, and passes profile paths into Unity export when profiling is enabled.

### AssetRipper and Unity wrappers

`src/erenshor/infrastructure/assetripper/assetripper.py`

Records sub-spans for server startup, load, export start, monitor, and shutdown.

`src/erenshor/infrastructure/unity/batch_mode.py`

Records Unity subprocess wall time and parses Unity log markers so reports can show Unity subprocess overhead minus C# `ExportBatch` runtime.

### Unity export profiler

`src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs`

Owns C# `Stopwatch` accumulators and emits machine-readable `[EXPORT_PROFILE_JSON]` lines plus readable `[EXPORT_PROFILE]` summaries.

`src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs`

Separates shared scanner timings, method lookup/dispatch timings, `OnAssetFound`, and `OnScanFinished`; caches reflected listener methods.

`src/Assets/Editor/ExportBatch.cs`

Parses `-profile true` and optional `-profileOutput <path>`, constructs the profiler, and writes the final profiler artifact.

### CodeFacts matcher

`src/tools/CodeFacts/Matchers.cs`

Adds `node_shape` for compound AST node matching.

`src/tools/CodeFacts/specs/erenshor-facts.json`

Uses `node_shape` to pin the full playtest guaranteed-loot loop.

## Persistent Data Shape

Store profiling data under the variant, not in the raw or clean game database:

```text
variants/{variant}/profiles/current-run.json
variants/{variant}/profiles/export-runs.sqlite
variants/{variant}/profiles/runs/{run_id}.jsonl
variants/{variant}/profiles/runs/{run_id}.trace.json
variants/{variant}/profiles/runs/{run_id}.md
```

`current-run.json` is the cross-process correlation handle:

```json
{"run_id":"20260617T090000Z-playtest-23789241-a1b2c3d4","variant":"playtest","game_build_id":"23789241","started_at":"2026-06-17T09:00:00Z"}
```

Every extraction subcommand calls `ExportProfileRecorder.open_or_create(...)`. If `current-run.json` exists for the same variant and build ID, the command appends spans to that run. If the build ID changes, the command creates a new run and replaces `current-run.json`.

SQLite tables:

```sql
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
);

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
);

CREATE INDEX IF NOT EXISTS idx_export_profile_spans_run_duration
ON export_profile_spans(run_id, duration_ms DESC);
```

JSONL event shape:

```json
{"type":"run","run_id":"20260617T090000Z-playtest-23789241-a1b2c3d4","variant":"playtest","command":"refresh pipeline","status":"running"}
{"type":"span","run_id":"20260617T090000Z-playtest-23789241-a1b2c3d4","span_id":"000001","parent_span_id":null,"name":"extract.download","category":"cli","duration_ms":64000.0,"status":"ok","attributes":{"variant":"playtest"}}
{"type":"span","run_id":"20260617T090000Z-playtest-23789241-a1b2c3d4","span_id":"000002","parent_span_id":null,"name":"extract.export.unity_subprocess","category":"unity","duration_ms":524000.0,"status":"ok","attributes":{"variant":"playtest"}}
```

Chrome trace JSON uses complete events so it opens directly in Perfetto:

```json
{"name":"extract.export.unity_subprocess","cat":"unity","ph":"X","ts":1000000,"dur":524000000,"pid":1,"tid":1,"args":{"variant":"playtest"}}
```

## Agent-Oriented Report Shape

`uv run erenshor -V playtest extract profile report --latest` should print a first-page summary like this:

```text
Run: 20260617T090000Z-playtest-23789241-a1b2c3d4
Variant: playtest
Status: ok
Total: 28m12s

Top stages:
1. extract.rip.assetripper              17m31s
2. extract.export.unity_subprocess       8m44s
3. extract.download                      1m04s
4. extract.build                         18s
5. extract.code_facts                    12s

Unity subprocess: 8m44s
Unity ExportBatch: 3m21s
Unity overhead before/after ExportBatch: 5m23s
Likely bucket: license refresh, package restore, asset import, or script compile.

Top listener OnAssetFound:
1. CharacterListener        41.20s  18,203 calls  avg 2.26ms  max 82.00ms
2. LootTableListener        22.80s   1,144 calls  avg 19.93ms max 115.00ms

Top listener OnScanFinished:
1. CharacterListener        58.60s
2. SpawnPointListener       13.40s

Artifacts:
- JSONL: variants/playtest/profiles/runs/20260617T090000Z-playtest-23789241-a1b2c3d4.jsonl
- Trace: variants/playtest/profiles/runs/20260617T090000Z-playtest-23789241-a1b2c3d4.trace.json
- Markdown: variants/playtest/profiles/runs/20260617T090000Z-playtest-23789241-a1b2c3d4.md
```

## Planned Commits

1. `feat(cli): persist extraction profile runs`
2. `feat(cli): trace extraction pipeline stages`
3. `feat(export): profile Unity scanner listeners`
4. `feat(cli): report latest extraction profile`
5. `feat(code-facts): pin compound statement shapes`
6. `docs(pipeline): document extraction profiling`

---

### Task 1: Add profile run recorder and persistence

**Files:**
- Create: `src/erenshor/infrastructure/export_profile.py`
- Test: `tests/unit/infrastructure/test_export_profile.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/infrastructure/test_export_profile.py`:

```python
from __future__ import annotations

import json
import sqlite3

from erenshor.infrastructure.export_profile import ExportProfileRecorder
from erenshor.infrastructure.time import MockClock


def test_profile_recorder_persists_run_span_jsonl_and_trace(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    recorder = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract export --profile",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        machine="darwin-arm64",
        clock=clock,
    )

    with recorder.span("extract.export", category="cli", attributes={"variant": "playtest"}):
        clock.advance(2.5)
        with recorder.span("extract.export.unity_subprocess", category="unity", attributes={"log": "export.log"}):
            clock.advance(5.0)

    recorder.finish("ok")

    db_path = root / "export-runs.sqlite"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        run = conn.execute("SELECT variant, status FROM export_profile_runs WHERE run_id = ?", (recorder.run_id,)).fetchone()
        spans = conn.execute("SELECT name, duration_ms FROM export_profile_spans WHERE run_id = ? ORDER BY duration_ms DESC", (recorder.run_id,)).fetchall()

    assert run == ("playtest", "ok")
    assert spans[0] == ("extract.export", 7500.0)
    assert spans[1] == ("extract.export.unity_subprocess", 5000.0)

    jsonl_path = root / "runs" / f"{recorder.run_id}.jsonl"
    lines = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    assert lines[0]["type"] == "run"
    assert {line["name"] for line in lines if line["type"] == "span"} == {
        "extract.export",
        "extract.export.unity_subprocess",
    }

    trace = json.loads((root / "runs" / f"{recorder.run_id}.trace.json").read_text())
    assert trace["traceEvents"][0]["ph"] == "X"
    assert trace["traceEvents"][0]["name"] == "extract.export.unity_subprocess"

def test_profile_recorder_reuses_active_run_across_cli_invocations(tmp_path):
    clock = MockClock()
    root = tmp_path / "profiles"
    download = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract download",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with download.span("extract.download", category="cli"):
        clock.advance(1.0)
    download.finish_command("extract download", "ok")

    export = ExportProfileRecorder.open_or_create(
        root=root,
        variant="playtest",
        command="extract export",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )
    with export.span("extract.export", category="cli"):
        clock.advance(2.0)
    export.finish_command("extract export", "ok")

    assert export.run_id == download.run_id
    assert json.loads((root / "current-run.json").read_text())["run_id"] == download.run_id
    with sqlite3.connect(root / "export-runs.sqlite") as conn:
        spans = conn.execute(
            "SELECT name FROM export_profile_spans WHERE run_id = ? ORDER BY span_id",
            (download.run_id,),
        ).fetchall()
    assert spans == [("extract.download",), ("extract.export",)]
    lines = [json.loads(line) for line in (root / "runs" / f"{download.run_id}.jsonl").read_text().splitlines()]
    assert {line["name"] for line in lines if line["type"] == "span"} == {"extract.download", "extract.export"}
    trace = json.loads((root / "runs" / f"{download.run_id}.trace.json").read_text())
    assert {event["name"] for event in trace["traceEvents"]} == {"extract.download", "extract.export"}


def test_profile_recorder_marks_failed_runs(tmp_path):
    clock = MockClock()
    recorder = ExportProfileRecorder.open_or_create(
        root=tmp_path / "profiles",
        variant="playtest",
        command="extract export",
        game_build_id=None,
        git_sha="abcdef0",
        unity_version=None,
        assetripper_version=None,
        machine="darwin-arm64",
        clock=clock,
    )

    try:
        with recorder.span("extract.export", category="cli"):
            clock.advance(1.0)
            raise RuntimeError("boom")
    except RuntimeError:
        recorder.finish("failed")

    with sqlite3.connect(tmp_path / "profiles" / "export-runs.sqlite") as conn:
        status = conn.execute("SELECT status FROM export_profile_runs WHERE run_id = ?", (recorder.run_id,)).fetchone()[0]
        span_status = conn.execute("SELECT status FROM export_profile_spans WHERE run_id = ?", (recorder.run_id,)).fetchone()[0]

    assert status == "failed"
    assert span_status == "failed"
```

- [ ] **Step 2: Run the red tests**

```bash
uv run pytest tests/unit/infrastructure/test_export_profile.py -v
```

Expected: import failure for `erenshor.infrastructure.export_profile`.

- [ ] **Step 3: Implement the recorder**

Create `src/erenshor/infrastructure/export_profile.py` with these public APIs:

```python
from __future__ import annotations

import json
import platform
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from erenshor.infrastructure.time import Clock, RealClock


@dataclass(slots=True)
class ProfileSpan:
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
        return round((self.ended_at - self.started_at) * 1000.0, 3)


class ExportProfileRecorder:
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
    ) -> "ExportProfileRecorder":
        active = cls._read_active_run(root)
        if active and active["variant"] == variant and active.get("game_build_id") == game_build_id:
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

    def finish_command(self, command: str, status: str) -> None:
        if status == "failed":
            self.status = "failed"
        self._persist_run(last_command=command, last_command_status=status)
        self._write_artifacts()

    def finish(self, status: str) -> None:
        self.status = status
        self.ended_at = self.clock.time()
        self._persist_run()
        self._write_artifacts()

    def latest_summary_markdown(self) -> str:
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
        return json.loads(active_path.read_text())

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
        with sqlite3.connect(db_path) as conn:
            value = conn.execute(
                "SELECT MAX(CAST(span_id AS INTEGER)) FROM export_profile_spans WHERE run_id = ?",
                (self.run_id,),
            ).fetchone()[0]
        return int(value or 0) + 1

    def _ensure_schema(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "runs").mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.root / "export-runs.sqlite") as conn:
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

    def _persist_run(self, last_command: str | None = None, last_command_status: str | None = None) -> None:
        with sqlite3.connect(self.root / "export-runs.sqlite") as conn:
            conn.execute(
                """
                INSERT INTO export_profile_runs (
                    run_id, variant, command, game_build_id, git_sha, unity_version,
                    assetripper_version, started_at, ended_at, status, machine,
                    last_command, last_command_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    ended_at = excluded.ended_at,
                    status = excluded.status,
                    last_command = COALESCE(excluded.last_command, export_profile_runs.last_command),
                    last_command_status = COALESCE(excluded.last_command_status, export_profile_runs.last_command_status)
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

    def _load_existing_spans(self) -> list[ProfileSpan]:
        db_path = self.root / "export-runs.sqlite"
        if not db_path.exists():
            return []
        with sqlite3.connect(db_path) as conn:
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
        with sqlite3.connect(self.root / "export-runs.sqlite") as conn:
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
```

- [ ] **Step 4: Run the green tests**

```bash
uv run pytest tests/unit/infrastructure/test_export_profile.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/infrastructure/export_profile.py tests/unit/infrastructure/test_export_profile.py
git commit -m "feat(cli): persist extraction profile runs"
```

---

### Task 2: Trace Python extraction pipeline stages

**Files:**
- Modify: `src/erenshor/cli/commands/extract.py`
- Modify: `src/erenshor/infrastructure/assetripper/assetripper.py`
- Modify: `src/erenshor/infrastructure/unity/batch_mode.py`
- Test: `tests/unit/infrastructure/assetripper/test_assetripper.py`
- Test: `tests/unit/infrastructure/unity/test_batch_mode.py`

- [ ] **Step 1: Add failing AssetRipper timing test**

Append to `TestAssetRipperExtraction` in `tests/unit/infrastructure/assetripper/test_assetripper.py`:

```python
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_extract_records_internal_profile_spans(
        self,
        mock_popen: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        executable = tmp_path / "AssetRipper.GUI.Free"
        executable.touch()
        source_dir = tmp_path / "game/Erenshor_Data"
        source_dir.mkdir(parents=True)
        target_dir = tmp_path / "unity"
        profile = ExportProfileRecorder.open_or_create(
            root=tmp_path / "profiles",
            variant="playtest",
            command="extract rip",
            game_build_id="23789241",
            git_sha="abcdef0",
            unity_version=None,
            assetripper_version="1.2.3",
            machine="darwin-arm64",
            clock=MockClock(),
        )

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if "curl" in cmd:
                if any("/IO/Directory/Exists" in str(arg) for arg in cmd):
                    return MagicMock(returncode=0, stdout="true")
                if any("LoadFolder" in str(arg) for arg in cmd) or any("Export/UnityProject" in str(arg) for arg in cmd):
                    return MagicMock(returncode=0, stdout="\n302")
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_run_side_effect
        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1, clock=profile.clock)

        original_path_open = Path.open
        from io import BytesIO

        def patched_path_open(self, mode="r", *args, **kwargs):
            if "assetripper_" in str(self) and "rb" in mode:
                return BytesIO(b"Export started\nFinished post-export\n")
            return original_path_open(self, mode, *args, **kwargs)

        with patch.object(Path, "open", patched_path_open):
            assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path, profile=profile)

        names = {span.name for span in profile.spans}
        assert "assetripper.start_server" in names
        assert "assetripper.load_files" in names
        assert "assetripper.export_start" in names
        assert "assetripper.monitor_export" in names
        assert "assetripper.stop_server" in names
```

Add imports:

```python
from erenshor.infrastructure.export_profile import ExportProfileRecorder
```

- [ ] **Step 2: Add failing Unity subprocess timing test**

Append to `TestUnityBatchModeExecuteMethod` in `tests/unit/infrastructure/unity/test_batch_mode.py`:

```python
    @patch("erenshor.infrastructure.unity.batch_mode.subprocess.Popen")
    def test_execute_method_records_unity_subprocess_span(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        unity_exe = tmp_path / "Unity"
        unity_exe.touch()
        project_path = tmp_path / "UnityProject"
        project_path.mkdir()
        (project_path / "Assets").mkdir()
        (project_path / "ProjectSettings").mkdir()
        log_file = tmp_path / "logs" / "export.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("[EXPORT_START]\n[EXPORT_COMPLETE] Export completed successfully in 3.00s\n")
        profile = ExportProfileRecorder.open_or_create(
            root=tmp_path / "profiles",
            variant="playtest",
            command="extract export",
            game_build_id="23789241",
            git_sha="abcdef0",
            unity_version="2021.3.45f2",
            assetripper_version=None,
            machine="darwin-arm64",
            clock=MockClock(),
        )

        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0]
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        unity = UnityBatchMode(unity_path=unity_exe, timeout=1800, clock=profile.clock)
        unity.execute_method(
            project_path=project_path,
            class_name="ExportBatch",
            method_name="Run",
            log_file=log_file,
            arguments={"dbPath": "/path/to/db.sqlite", "logLevel": "normal"},
            profile=profile,
        )

        span = next(span for span in profile.spans if span.name == "unity.batch_subprocess")
        assert span.duration_ms == 5000.0
        assert span.attributes["log_file"] == str(log_file)
```

Add import:

```python
from erenshor.infrastructure.export_profile import ExportProfileRecorder
```

- [ ] **Step 3: Run red tests**

```bash
uv run pytest tests/unit/infrastructure/assetripper/test_assetripper.py::TestAssetRipperExtraction::test_extract_records_internal_profile_spans tests/unit/infrastructure/unity/test_batch_mode.py::TestUnityBatchModeExecuteMethod::test_execute_method_records_unity_subprocess_span -v
```

Expected: signature errors because `profile` parameters do not exist.

- [ ] **Step 4: Add optional profile parameters**

In `src/erenshor/infrastructure/assetripper/assetripper.py`, import the type under `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.infrastructure.export_profile import ExportProfileRecorder
```

Change `extract()` signature:

```python
    def extract(
        self,
        source_dir: Path,
        target_dir: Path,
        log_dir: Path,
        profile: ExportProfileRecorder | None = None,
    ) -> None:
```

Wrap sub-stages:

```python
        try:
            if profile is None:
                self.start_server(log_dir=log_dir)
                self._load_files(source_dir)
                self._export_files(target_dir)
                self._monitor_export()
            else:
                with profile.span("assetripper.start_server", category="assetripper"):
                    self.start_server(log_dir=log_dir)
                with profile.span("assetripper.load_files", category="assetripper"):
                    self._load_files(source_dir)
                with profile.span("assetripper.export_start", category="assetripper"):
                    self._export_files(target_dir)
                with profile.span("assetripper.monitor_export", category="assetripper"):
                    self._monitor_export()

            logger.info("Asset extraction complete!")
            logger.info(f"Unity project ready at: {target_dir}")
            if self._log_file:
                logger.info(f"Log file: {self._log_file}")

        finally:
            if profile is None:
                self.stop_server()
            else:
                with profile.span("assetripper.stop_server", category="assetripper"):
                    self.stop_server()
```

In `src/erenshor/infrastructure/unity/batch_mode.py`, add the same `TYPE_CHECKING` import and change `execute_method()` signature:

```python
        profile: ExportProfileRecorder | None = None,
```

Wrap the polling loop:

```python
            span_context = (
                profile.span("unity.batch_subprocess", category="unity", attributes={"log_file": str(log_file)})
                if profile is not None
                else nullcontext()
            )
            with span_context:
                while True:
                    returncode = process.poll()
                    if returncode is not None:
                        logger.info("Unity export completed")
                        break
                    elapsed = int(self.clock.time() - start_time)
                    if elapsed - last_update >= 30:
                        logger.info(f"Still exporting... ({elapsed}s elapsed)")
                        last_update = elapsed
                    if elapsed > self.timeout:
                        process.kill()
                        logger.error(f"Unity execution timed out after {self.timeout}s")
                        raise UnityRuntimeError(
                            f"Unity execution timed out after {self.timeout} seconds.\n"
                            f"Check log file: {log_file}\n"
                            "Consider increasing timeout in config.toml"
                        )
                    self.clock.sleep(5)
```

Import `nullcontext`:

```python
from contextlib import nullcontext
```

- [ ] **Step 5: Thread profile recorder through `extract.py`**

In `src/erenshor/cli/commands/extract.py`, create a helper:

```python
def _profile_root(cli_ctx: CLIContext) -> Path:
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_game_files(cli_ctx.repo_root).parents[0] / "profiles"
```

Use the project's resolved variant path conventions if a direct `resolved_profiles` helper exists by implementation time. If no helper exists, add one to the config model before using it.

Open the active profile run for real `download`, `rip`, `export`, `code_facts`, and `build` commands. Each separate CLI invocation appends spans to the same run when the variant/build ID matches `current-run.json`:

```python
profile = ExportProfileRecorder.open_or_create(
    root=_profile_root(cli_ctx),
    variant=cli_ctx.variant,
    command="extract export",
    game_build_id=_read_build_id(cli_ctx, variant_config),
    git_sha=_read_git_sha(cli_ctx.repo_root),
    unity_version=unity.get_version(),
    assetripper_version=None,
    machine=None,
)
command_name = "extract export"
try:
    with profile.span(command_name, category="cli", attributes={"variant": cli_ctx.variant}):
        ...
except Exception:
    profile.finish_command(command_name, "failed")
    profile.finish("failed")
    raise
else:
    profile.finish_command(command_name, "ok")
```

Only `extract build` should call `profile.finish("ok")` on success, because it is the terminal stage in the standard refresh sequence. Earlier successful commands leave the run status as `running` so later invocations can append spans.

- [ ] **Step 6: Run green tests**

```bash
uv run pytest tests/unit/infrastructure/test_export_profile.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/erenshor/cli/commands/extract.py src/erenshor/infrastructure/assetripper/assetripper.py src/erenshor/infrastructure/unity/batch_mode.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py
git commit -m "feat(cli): trace extraction pipeline stages"
```

---

### Task 3: Add Unity scanner listener profiler and cache reflection dispatch

**Files:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs`
- Modify: `src/Assets/Editor/ExportBatch.cs`
- Modify: `src/erenshor/cli/commands/extract.py`

- [ ] **Step 1: Add profiler model**

Create `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Debug = UnityEngine.Debug;

public sealed class AssetScanProfiler
{
    private readonly Dictionary<string, Timing> _timings = new();
    private readonly Stopwatch _runStopwatch = Stopwatch.StartNew();

    public bool Enabled { get; }
    public string OutputPath { get; }

    public AssetScanProfiler(bool enabled, string outputPath)
    {
        Enabled = enabled;
        OutputPath = outputPath;
    }

    public void Measure(string category, string name, Action action)
    {
        if (!Enabled)
        {
            action();
            return;
        }

        long startTicks = _runStopwatch.ElapsedTicks;
        var stopwatch = Stopwatch.StartNew();
        action();
        stopwatch.Stop();
        Add(category, name, startTicks, stopwatch.ElapsedTicks);
    }

    public void Add(string category, string name, long startTicks, long elapsedTicks)
    {
        string key = category + "." + name;
        if (!_timings.TryGetValue(key, out var timing))
        {
            timing = new Timing(category, name);
            _timings[key] = timing;
        }

        timing.Calls++;
        timing.ElapsedTicks += elapsedTicks;
        if (elapsedTicks > timing.MaxTicks)
            timing.MaxTicks = elapsedTicks;
        if (timing.FirstStartTicks == 0 || startTicks < timing.FirstStartTicks)
            timing.FirstStartTicks = startTicks;
    }

    public void LogAndWriteSummary()
    {
        if (!Enabled)
            return;

        var rows = _timings.Values
            .OrderByDescending(timing => timing.ElapsedTicks)
            .Select(timing => timing.ToRow())
            .ToList();

        foreach (var row in rows)
        {
            Debug.Log($"[EXPORT_PROFILE] {row.category}.{row.name}: {row.total_ms:F3}ms over {row.calls} calls avg={row.avg_ms:F3}ms max={row.max_ms:F3}ms");
            Debug.Log("[EXPORT_PROFILE_JSON] " + JsonConvert.SerializeObject(row));
        }

        if (!string.IsNullOrEmpty(OutputPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(OutputPath));
            File.WriteAllText(OutputPath, JsonConvert.SerializeObject(rows, Formatting.Indented));
        }
    }

    private sealed class Timing
    {
        public string Category { get; }
        public string Name { get; }
        public long Calls { get; set; }
        public long ElapsedTicks { get; set; }
        public long MaxTicks { get; set; }
        public long FirstStartTicks { get; set; }

        public Timing(string category, string name)
        {
            Category = category;
            Name = name;
        }

        public object ToRow()
        {
            double totalMs = TicksToMilliseconds(ElapsedTicks);
            return new
            {
                category = Category,
                name = Name,
                calls = Calls,
                total_ms = totalMs,
                avg_ms = Calls == 0 ? 0.0 : totalMs / Calls,
                max_ms = TicksToMilliseconds(MaxTicks),
                first_start_ms = TicksToMilliseconds(FirstStartTicks)
            };
        }

        private static double TicksToMilliseconds(long ticks)
        {
            return ticks * 1000.0 / Stopwatch.Frequency;
        }
    }
}
```

- [ ] **Step 2: Cache reflected methods in `AssetScanner`**

Add a private cache:

```csharp
private readonly Dictionary<(Type ListenerType, Type AssetType), MethodInfo?> _onAssetFoundMethodCache = new();
```

Add helper:

```csharp
private MethodInfo? GetCachedOnAssetFoundMethod(object listenerObj, Type assetType)
{
    var key = (listenerObj.GetType(), assetType);
    if (_onAssetFoundMethodCache.TryGetValue(key, out var cached))
        return cached;

    MethodInfo? method = listenerObj.GetType().GetMethod("OnAssetFound", new[] { assetType });
    _onAssetFoundMethodCache[key] = method;
    return method;
}
```

When profiling is enabled, measure lookup separately:

```csharp
MethodInfo? method = null;
_profiler.Measure("dispatch", listenerObj.GetType().Name + ".method_lookup", () =>
{
    method = GetCachedOnAssetFoundMethod(listenerObj, asset.GetType());
});
```

Then measure invocation:

```csharp
if (method != null)
{
    _profiler.Measure("listener.OnAssetFound", listenerObj.GetType().Name, () =>
    {
        method.Invoke(listenerObj, new object[] { asset });
    });
}
```

- [ ] **Step 3: Separate shared scanner spans**

Wrap scanner-owned work with category `scanner.shared`, for example:

```csharp
_profiler.Measure("scanner.shared", "scriptable_object_find_assets", () =>
{
    guids = AssetDatabase.FindAssets("t:ScriptableObject");
});
```

Use these names:

```text
scanner.shared.resources_load_all
scanner.shared.scriptable_object_find_assets
scanner.shared.prefab_find_assets
scanner.shared.scene_find_assets
scanner.shared.scene_open
scanner.shared.scene_hierarchy_walk
scanner.shared.get_components
```

Do not attribute these shared costs to listeners.

- [ ] **Step 4: Separate finalization spans**

Wrap `OnScanFinished` per listener:

```csharp
_profiler.Measure("listener.OnScanFinished", listenerObj.GetType().Name, () =>
{
    InvokeListenerMethod(listenerObj, "OnScanFinished");
});
```

Call `_profiler.LogAndWriteSummary()` after every listener finalization finishes.

- [ ] **Step 5: Wire CLI profile flags into Unity**

In `ExportBatch.CommandLineArgs`, add:

```csharp
public bool profile;
public string profileOutput;
```

Parse:

```csharp
case "-profile":
    parsed.profile = string.Equals(args[i + 1], "true", StringComparison.OrdinalIgnoreCase);
    break;
case "-profileOutput":
    parsed.profileOutput = args[i + 1];
    break;
```

Construct:

```csharp
AssetScanProfiler profiler = new AssetScanProfiler(args.profile, args.profileOutput);
AssetScanner scanner = new AssetScanner(profiler);
```

In Python export command, pass both:

```python
arguments={
    "dbPath": str(database_path.absolute()),
    "logLevel": unity_log_level,
    "profile": "true" if profile else "false",
    "profileOutput": str(profile_output_path),
}
```

- [ ] **Step 6: Verify C# diagnostics and profiled export**

Run LSP diagnostics on:

```text
src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs
src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs
src/Assets/Editor/ExportBatch.cs
```

Expected: no diagnostics.

Run:

```bash
uv run erenshor -V playtest extract export --profile
```

Expected log evidence:

```text
[EXPORT_PROFILE] scanner.shared.scene_hierarchy_walk: ...ms over ... calls
[EXPORT_PROFILE] dispatch.CharacterListener.method_lookup: ...ms over ... calls
[EXPORT_PROFILE] listener.OnAssetFound.CharacterListener: ...ms over ... calls
[EXPORT_PROFILE] listener.OnScanFinished.CharacterListener: ...ms over 1 calls
[EXPORT_PROFILE_JSON] {...}
```

If Unity license validation fails, open Unity Hub, wait until the license refreshes, rerun the same command once, and record the failed runtime separately in the final report.

- [ ] **Step 7: Commit**

```bash
git add src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs src/Assets/Editor/ExportBatch.cs src/erenshor/cli/commands/extract.py
git commit -m "feat(export): profile Unity scanner listeners"
```

---

### Task 4: Add profile report command for agents and humans

**Files:**
- Modify: `src/erenshor/cli/commands/extract.py`
- Modify: `src/erenshor/infrastructure/export_profile.py`
- Test: `tests/unit/infrastructure/test_export_profile.py`

- [ ] **Step 1: Write failing report test**

Append to `tests/unit/infrastructure/test_export_profile.py`:

```python
def test_latest_report_prioritizes_stages_and_listener_buckets(tmp_path):
    clock = MockClock()
    recorder = ExportProfileRecorder.open_or_create(
        root=tmp_path / "profiles",
        variant="playtest",
        command="extract export --profile",
        game_build_id="23789241",
        git_sha="abcdef0",
        unity_version="2021.3.45f2",
        assetripper_version="1.2.3",
        machine="darwin-arm64",
        clock=clock,
    )
    with recorder.span("extract.export.unity_subprocess", category="unity"):
        clock.advance(10.0)
    with recorder.span("unity.ExportBatch", category="unity"):
        clock.advance(4.0)
    with recorder.span("listener.OnAssetFound.CharacterListener", category="listener.OnAssetFound", attributes={"calls": 100}):
        clock.advance(3.0)
    with recorder.span("listener.OnScanFinished.CharacterListener", category="listener.OnScanFinished", attributes={"calls": 1}):
        clock.advance(2.0)
    recorder.finish("ok")

    report = recorder.latest_summary_markdown()

    assert "Unity overhead before/after ExportBatch" in report
    assert "listener.OnAssetFound.CharacterListener" in report
    assert "listener.OnScanFinished.CharacterListener" in report
    assert f"{recorder.run_id}.trace.json" in report
```

- [ ] **Step 2: Run red test**

```bash
uv run pytest tests/unit/infrastructure/test_export_profile.py::test_latest_report_prioritizes_stages_and_listener_buckets -v
```

Expected: missing sections in the current summary.

- [ ] **Step 3: Implement report builder**

Add helpers to `ExportProfileRecorder`:

```python
    @classmethod
    def load_latest(cls, root: Path) -> ExportProfileReport:
        return ExportProfileReport.load_latest(root)
```

Create a lightweight report class in the same file:

```python
class ExportProfileReport:
    def __init__(self, root: Path, run: dict[str, Any], spans: list[dict[str, Any]]) -> None:
        self.root = root
        self.run = run
        self.spans = spans

    @classmethod
    def load_latest(cls, root: Path) -> "ExportProfileReport":
        active_path = root / "current-run.json"
        active = json.loads(active_path.read_text()) if active_path.exists() else None
        with sqlite3.connect(root / "export-runs.sqlite") as conn:
            conn.row_factory = sqlite3.Row
            if active is not None:
                run = conn.execute(
                    "SELECT * FROM export_profile_runs WHERE run_id = ?",
                    (active["run_id"],),
                ).fetchone()
            else:
                run = conn.execute(
                    "SELECT * FROM export_profile_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
            if run is None:
                raise FileNotFoundError(f"No profile runs found in {root}")
            spans = conn.execute(
                "SELECT * FROM export_profile_spans WHERE run_id = ? ORDER BY duration_ms DESC",
                (run["run_id"],),
            ).fetchall()
        return cls(root, dict(run), [dict(span) for span in spans])

    def to_markdown(self) -> str:
        run_id = self.run["run_id"]
        top_spans = self.spans[:10]
        unity_subprocess = self._duration("unity.batch_subprocess")
        export_batch = self._duration("unity.ExportBatch")
        overhead = max(0.0, unity_subprocess - export_batch)
        lines = [
            f"# Export Profile {run_id}",
            "",
            f"Variant: `{self.run['variant']}`",
            f"Status: `{self.run['status']}`",
            "",
            "## Top stages",
            "",
        ]
        for index, span in enumerate(top_spans, start=1):
            lines.append(f"{index}. `{span['name']}` — {span['duration_ms']:.2f} ms")
        lines.extend([
            "",
            "## Unity overhead",
            "",
            f"Unity subprocess: {unity_subprocess:.2f} ms",
            f"Unity ExportBatch: {export_batch:.2f} ms",
            f"Unity overhead before/after ExportBatch: {overhead:.2f} ms",
            "",
            "## Artifacts",
            "",
            f"- JSONL: `{self.root / 'runs' / (run_id + '.jsonl')}`",
            f"- Trace: `{self.root / 'runs' / (run_id + '.trace.json')}`",
            f"- Markdown: `{self.root / 'runs' / (run_id + '.md')}`",
            "",
        ])
        return "\n".join(lines)

    def _duration(self, name: str) -> float:
        for span in self.spans:
            if span["name"] == name:
                return float(span["duration_ms"])
        return 0.0
```

Update `latest_summary_markdown()` to delegate to the richer report output after writing spans.

- [ ] **Step 4: Add Typer command**

In `src/erenshor/cli/commands/extract.py`, add a nested Typer app:

```python
profile_app = typer.Typer(name="profile", help="Inspect extraction profile runs", no_args_is_help=True)
app.add_typer(profile_app, name="profile")
```

Add command:

```python
@profile_app.command("report")
def profile_report(
    ctx: typer.Context,
    latest: bool = typer.Option(True, "--latest", help="Report the latest profile run"),
) -> None:
    cli_ctx: CLIContext = ctx.obj
    if not latest:
        raise typer.BadParameter("Only --latest is currently supported")
    root = _profile_root(cli_ctx)
    report = ExportProfileReport.load_latest(root)
    console.print(report.to_markdown())
```

- [ ] **Step 5: Run tests and help command**

```bash
uv run pytest tests/unit/infrastructure/test_export_profile.py -v
uv run erenshor -V playtest extract profile report --help
```

Expected: tests pass; help shows `report` options.

- [ ] **Step 6: Commit**

```bash
git add src/erenshor/infrastructure/export_profile.py src/erenshor/cli/commands/extract.py tests/unit/infrastructure/test_export_profile.py
git commit -m "feat(cli): report latest extraction profile"
```

---

### Task 5: Add CodeFacts generic AST node shape matcher

**Files:**
- Modify: `src/tools/CodeFacts/Matchers.cs`
- Modify: `src/tools/CodeFacts/tests/FixtureLib/FixtureLoot.cs`
- Modify: `tests/fixtures/code_facts/fixture-specs.json`
- Modify: `tests/integration/test_code_facts_tool.py`

- [ ] **Step 1: Extend fixture source with a compound retry loop**

Add to `FixtureLoot`:

```csharp
        public void GuaranteeRetryLike(int numberOfGuaranteedDrops)
        {
            for (int i = 0; i < numberOfGuaranteedDrops; i++)
            {
                string item = null;
                int attempts = 0;
                do
                {
                    item = PoolA[Rng.Next(0, PoolA.Count)];
                    attempts++;
                }
                while (attempts < 10 && (item == null || Drops.Contains(item)));
                if (item != null)
                {
                    Drops.Add(item);
                }
            }
        }
```

- [ ] **Step 2: Add fixture spec for the compound node**

In `tests/fixtures/code_facts/fixture-specs.json`, add:

```json
{
  "id": "fixture.guarantee_retry_loop",
  "mode": "assert",
  "type": "FixtureLib.FixtureLoot",
  "method": "GuaranteeRetryLike",
  "matcher": "node_shape",
  "args": {
    "kind": "ForStatement",
    "shape": "for (int i = 0; i < numberOfGuaranteedDrops; i++) { string item = null; int attempts = 0; do { item = PoolA [Rng.Next (0, PoolA.Count)]; attempts++; } while (attempts < 10 && (item == null || Drops.Contains (item))); if (item != null) { Drops.Add (item); } }"
  }
}
```

- [ ] **Step 3: Write failing integration tests**

Update `tests/integration/test_code_facts_tool.py`:

```python
def test_node_shape_asserts_compound_statement(fixture_dll: Path) -> None:
    rc, out = run_tool(fixture_dll, SPECS)
    assert rc == 0, out
    facts = {f["id"]: f for f in out["facts"]}
    assert facts["fixture.guarantee_retry_loop"]["ok"] is True
    assert facts["fixture.guarantee_retry_loop"]["values"] is None


def test_node_shape_violation_fails_loud(fixture_dll: Path, tmp_path: Path) -> None:
    specs = json.loads(SPECS.read_text())
    for fact in specs["facts"]:
        if fact["id"] == "fixture.guarantee_retry_loop":
            fact["args"]["shape"] = "for (int i = 0; i < numberOfGuaranteedDrops; i++) { Drops.Add (PoolA [0]); }"
    bad = tmp_path / "bad-node-shape.json"
    bad.write_text(json.dumps(specs))
    rc, out = run_tool(fixture_dll, bad)
    assert rc == 1
    assert any("fixture.guarantee_retry_loop" in e for e in out["errors"])
```

- [ ] **Step 4: Run red tests**

```bash
uv run pytest tests/integration/test_code_facts_tool.py::test_node_shape_asserts_compound_statement tests/integration/test_code_facts_tool.py::test_node_shape_violation_fails_loud -v
```

Expected: unknown matcher `node_shape`.

- [ ] **Step 5: Implement `node_shape` matcher**

In `Runner.Run()`, add:

```csharp
"node_shape" => Matchers.NodeShape(method, fact),
```

In `Matchers`, add:

```csharp
public static Dictionary<string, string> NodeShape(MethodDeclaration method, FactSpec fact)
{
    string kind = fact.Args["kind"];
    string wanted = Normalize(fact.Args["shape"]);

    var candidates = method.DescendantsAndSelf
        .Where(node => node.GetType().Name == kind)
        .Select(node => Normalize(node.ToString()))
        .ToList();

    int count = candidates.Count(candidate => candidate == wanted);
    if (count != 1)
    {
        string sample = candidates.Count == 0
            ? "no candidates"
            : string.Join(" | ", candidates.Take(5));
        throw new InvalidDataException(
            $"node_shape('{kind}') bound {count} times (need exactly 1): {fact.Args["shape"]}; candidates: {sample}");
    }

    return new();
}
```

- [ ] **Step 6: Run CodeFacts integration tests**

```bash
uv run pytest tests/integration/test_code_facts_tool.py -v
```

Expected: all CodeFacts tool tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/tools/CodeFacts/Matchers.cs src/tools/CodeFacts/tests/FixtureLib/FixtureLoot.cs tests/fixtures/code_facts/fixture-specs.json tests/integration/test_code_facts_tool.py
git commit -m "feat(code-facts): assert compound AST node shapes"
```

---

### Task 6: Pin playtest `GuaranteeOneDrop` retry-loop semantics

**Files:**
- Modify: `src/tools/CodeFacts/specs/erenshor-facts.json`

- [ ] **Step 1: Replace weak `statement_shape` pin**

Change `loot.guarantee_one_drop` from the weak expression-statement pin to:

```json
"matcher": "node_shape",
"args": {
  "kind": "ForStatement",
  "shape": "for (int i = 0; i < NumberOfGuaranteedDrops; i++) { Item item = null; int num2 = 0; do { item = GuaranteeOneDrop [Random.Range (0, GuaranteeOneDrop.Count)]; num2++; } while (num2 < 10 && (item == null || ActualDrops.Contains (item))); if (item != null) { ActualDrops.Add (item); } }"
}
```

Use this note:

```json
"note": "GuaranteeOneDrop semantics (NumberOfGuaranteedDrops random members of the pool drop per kill, retrying up to 10 times to avoid nulls or items already in ActualDrops, then accepting a non-null duplicate fallback). Re-implemented by LootTableProbabilityCalculator; if the loop, retry bound, duplicate guard, or add target changes, this hard-fails the refresh."
```

- [ ] **Step 2: Run code-facts on playtest**

```bash
uv run erenshor -V playtest extract code-facts
```

Expected: success and a row for `loot.guarantee_one_drop` with `ok=true`.

If the exact `shape` mismatches because of pinned decompiler spacing, copy the normalized candidate from the analyzer error into the spec and rerun once.

- [ ] **Step 3: Run code-facts coverage tests**

```bash
uv run pytest tests/test_code_facts_coverage.py tests/integration/test_code_facts_tool.py -v
```

Expected: tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/tools/CodeFacts/specs/erenshor-facts.json
git commit -m "feat(code-facts): pin guaranteed loot retry loop"
```

---

### Task 7: Document profiling workflow

**Files:**
- Modify: `.agent/skills/refreshing-game-data/SKILL.md` only if the current worktree owner confirms the existing unstaged skill edit is ours to update; otherwise modify the source-owned copy in the correct setup repo per global AGENTS guidance.

- [ ] **Step 1: Add timing guidance to the refresh skill**

Add this to the refresh validation section:

```markdown
## Timing and profiling refreshes

Extraction commands persist profile runs under `variants/{variant}/profiles/`.
Use them to separate Steam download, AssetRipper, Unity subprocess overhead,
Unity C# export, listener `OnAssetFound`, listener `OnScanFinished`, code-facts,
and clean build cost before optimizing.

```bash
uv run erenshor -V playtest extract profile report --latest
```

For slow Unity exports, rerun only the export with listener profiling:

```bash
uv run erenshor -V playtest extract export --profile
```

Compare `unity.batch_subprocess` against Unity's `[EXPORT_COMPLETE]` or
`unity.ExportBatch` span. Large gaps before the C# export usually mean Unity
license refresh, package restore, asset import, or script compilation rather
than listener work. Use `listener.OnAssetFound.*` rows for per-asset extraction
cost and `listener.OnScanFinished.*` rows for table creation/delete/insert cost.
Open the `.trace.json` artifact in Perfetto when the nested timeline matters.
```

- [ ] **Step 2: Verify no unrelated skill changes were swept in**

Run:

```bash
git diff -- .agent/skills/refreshing-game-data/SKILL.md
```

Expected: only the profiling guidance if the file is intentionally in scope. If unrelated edits appear, stop and ask the owner before staging.

- [ ] **Step 3: Commit docs**

```bash
git add .agent/skills/refreshing-game-data/SKILL.md
git commit -m "docs(pipeline): document extraction profiling"
```

---

## Final Verification

Run after all tasks:

```bash
uv run ruff check src/erenshor/infrastructure/export_profile.py src/erenshor/cli/commands/extract.py src/erenshor/infrastructure/assetripper/assetripper.py src/erenshor/infrastructure/unity/batch_mode.py tests/unit/infrastructure/test_export_profile.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py tests/integration/test_code_facts_tool.py
uv run mypy src/erenshor/infrastructure/export_profile.py src/erenshor/cli/commands/extract.py src/erenshor/infrastructure/assetripper/assetripper.py src/erenshor/infrastructure/unity/batch_mode.py
uv run pytest tests/unit/infrastructure/test_export_profile.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py tests/integration/test_code_facts_tool.py tests/test_code_facts_coverage.py -v
uv run erenshor -V playtest extract code-facts
uv run erenshor -V playtest extract export --profile
uv run erenshor -V playtest extract profile report --latest
```

Expected:

- Python checks pass.
- CodeFacts test fixture passes.
- Playtest code-facts extraction pins the full guaranteed-loot loop.
- Profiled playtest export writes SQLite, JSONL, Markdown, and Perfetto-compatible trace artifacts.
- The latest profile report separates shared scanner work, dispatch/reflection lookup, `listener.OnAssetFound`, and `listener.OnScanFinished`.

Do not run `golden capture` for playtest. Do not deploy wiki, guide, maps, or sheets as part of this profiling work.

## Self-Review

- Spec coverage: export slowness gets persistent macro traces, CLI stage spans, AssetRipper sub-stage spans, Unity subprocess overhead, optional Unity listener profiling, and a profile report designed for agents. CodeFacts gets a compound AST node matcher and applies it to the exact loot-loop limitation found in this session.
- Placeholder scan: no incomplete markers or unbounded generic test steps remain.
- Type consistency: profiling uses existing `Clock`/`MockClock`; Unity uses `Stopwatch`; CodeFacts matcher uses existing `FactSpec.Args` and `MethodDeclaration` patterns.
- Scope check: no refresh orchestration command is introduced. The plan instruments existing commands and adds a read-only report command, so it does not change pipeline order or variant safety rules.
