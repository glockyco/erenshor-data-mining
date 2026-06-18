# Export Profiling and CodeFacts Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make slow refresh/export runs explainable with stage-level and listener-level timing, and add CodeFacts matcher support strong enough to pin the playtest guaranteed-loot retry loop.

**Architecture:** Add lightweight wall-clock timing at the Python pipeline boundaries first, then optional Unity export profiling inside `ExportBatch`/`AssetScanner` for listener-level attribution. Extend CodeFacts with a generic AST-node shape matcher so specs can pin compound statements such as `for` and `do/while`, not only expression statements.

**Tech Stack:** Python Typer CLI, Loguru, existing `Clock`/`MockClock`, Unity Editor C# export scripts, SQLite raw export, ICSharpCode.Decompiler/CSharp AST, pytest, dotnet fixture tests.

---

## Current Findings

The project already has limited export timing:

- `src/Assets/Editor/ExportBatch.cs` logs `[EXPORT_COMPLETE]` total Unity export time.
- `ExportBatch.ExecuteScanSynchronously()` logs broad scan phases: `ScriptableObjects`, `Prefabs`, `Scenes`.
- `src/erenshor/infrastructure/unity/batch_mode.py` logs `Still exporting...` every 30 seconds and has a total timeout.
- `src/erenshor/infrastructure/assetripper/assetripper.py` logs `Still exporting...` every 30 seconds while monitoring AssetRipper.

That is not enough to explain the slow run from this session. It cannot separate Steam download, AssetRipper startup/load/export/monitoring, Unity launch/license/import/compile overhead, C# scan time, listener `OnScanFinished()` database writes, code-facts, and clean DB build.

CodeFacts also needs stronger pinning. The playtest loot patch forced `loot.guarantee_one_drop` to pin only `ActualDrops.Add (item);` because `statement_shape` only matches `ExpressionStatement`. It cannot pin the surrounding `for (int i = 0; i < NumberOfGuaranteedDrops; i++)` and `do/while` retry loop, which is the actual semantic contract the probability calculator re-implements.

## Planned Commits

1. `feat(cli): log extraction stage timings`
2. `feat(export): add Unity listener profiling`
3. `feat(code-facts): pin compound statement shapes`
4. `docs(pipeline): document refresh timing output`

---

### Task 1: Add Python stage timing helpers

**Files:**
- Create: `src/erenshor/infrastructure/timing.py`
- Test: `tests/unit/infrastructure/test_timing.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/infrastructure/test_timing.py`:

```python
from __future__ import annotations

from loguru import logger

from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.timing import StageTimer


def test_stage_timer_logs_success_duration() -> None:
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    clock = MockClock()

    try:
        with StageTimer("extract.download", clock=clock):
            clock.advance(12.5)
    finally:
        logger.remove(sink_id)

    assert messages == ["[TIMING] extract.download completed in 12.50s"]


def test_stage_timer_logs_failure_duration() -> None:
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    clock = MockClock()

    try:
        try:
            with StageTimer("extract.export", clock=clock):
                clock.advance(7.25)
                raise RuntimeError("boom")
        except RuntimeError:
            pass
    finally:
        logger.remove(sink_id)

    assert messages == ["[TIMING] extract.export failed in 7.25s"]
```

- [ ] **Step 2: Run the red tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/test_timing.py -v
```

Expected: import failure for `erenshor.infrastructure.timing`.

- [ ] **Step 3: Implement the timing helper**

Create `src/erenshor/infrastructure/timing.py`:

```python
"""Small wall-clock timing helpers for CLI pipeline stages."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger

from erenshor.infrastructure.time import Clock, RealClock


@contextmanager
def StageTimer(name: str, *, clock: Clock | None = None) -> Iterator[None]:
    """Log a single stage duration with a stable `[TIMING]` prefix."""
    active_clock = clock if clock is not None else RealClock()
    start = active_clock.time()
    try:
        yield
    except Exception:
        elapsed = active_clock.time() - start
        logger.info(f"[TIMING] {name} failed in {elapsed:.2f}s")
        raise
    else:
        elapsed = active_clock.time() - start
        logger.info(f"[TIMING] {name} completed in {elapsed:.2f}s")
```

- [ ] **Step 4: Run the green tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/test_timing.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/infrastructure/timing.py tests/unit/infrastructure/test_timing.py
git commit -m "feat(cli): add stage timing helper"
```

---

### Task 2: Time the Python extraction command boundaries

**Files:**
- Modify: `src/erenshor/cli/commands/extract.py`
- Test: no new unit test; covered by Task 1 helper tests and existing command behavior. Verification uses a dry-run command and one real non-destructive command.

- [ ] **Step 1: Add timing imports**

Modify `src/erenshor/cli/commands/extract.py` imports:

```python
from erenshor.infrastructure.timing import StageTimer
```

- [ ] **Step 2: Wrap `download` work**

Inside `download()`, wrap the Steam call only, not dry-run handling:

```python
        with StageTimer(f"extract.download.{cli_ctx.variant}"):
            steamcmd.download(
                app_id=variant_config.app_id,
                install_dir=game_files_dir,
                validate=validate,
            )
```

- [ ] **Step 3: Wrap `rip` sub-stages**

Inside `rip()`, split the known expensive stages:

```python
        with StageTimer(f"extract.rip.remove_old_project.{cli_ctx.variant}"):
            if unity_project_dir.exists():
                logger.info(f"Removing old Unity project: {unity_project_dir}")
                shutil.rmtree(unity_project_dir)

        logger.info(f"Extracting Unity project: variant={cli_ctx.variant}")

        assetripper_config = cli_ctx.config.global_.assetripper
        assetripper = AssetRipper(
            executable_path=assetripper_config.resolved_path(cli_ctx.repo_root),
            port=assetripper_config.port,
            timeout=assetripper_config.timeout,
        )

        with StageTimer(f"extract.rip.assetripper.{cli_ctx.variant}"):
            assetripper.extract(
                source_dir=game_files_dir / "Erenshor_Data",
                target_dir=unity_project_dir,
                log_dir=logs_dir,
            )

        with StageTimer(f"extract.rip.postprocess.{cli_ctx.variant}"):
            editor_target = unity_project_dir / "ExportedProject" / "Assets" / "Editor"
            editor_source = variant_config.resolved_editor_scripts(cli_ctx.repo_root)
            logger.info(f"Creating Editor scripts symlink: {editor_target} -> {editor_source}")
            editor_target.symlink_to(editor_source)

            packages_source = cli_ctx.repo_root / "src" / "Assets" / "Packages"
            packages_target = unity_project_dir / "ExportedProject" / "Assets" / "Packages"
            if packages_source.exists():
                logger.info(f"Copying NuGet packages: {packages_source} -> {packages_target}")
                shutil.copytree(packages_source, packages_target, dirs_exist_ok=True)
            else:
                logger.warning(f"Packages directory not found: {packages_source}")

            _patch_manifest_after_rip(unity_project_dir, prior_user_deps)
```

Then wrap IDE generation separately:

```python
        with StageTimer(f"extract.rip.ide_project_files.{cli_ctx.variant}"):
            _generate_ide_project_files(cli_ctx, variant_config, unity_project_dir, game_files_dir)
```

- [ ] **Step 4: Wrap `export` sub-stages**

In `export()`, wrap deletion, Unity subprocess, and backup:

```python
        with StageTimer(f"extract.export.remove_old_raw_db.{cli_ctx.variant}"):
            if database_path.exists():
                logger.info(f"Removing old raw database: {database_path}")
                database_path.unlink()

        logger.info(f"Exporting game data: variant={cli_ctx.variant}")

        with StageTimer(f"extract.export.unity_subprocess.{cli_ctx.variant}"):
            unity.execute_method(
                project_path=unity_project_dir / "ExportedProject",
                class_name="ExportBatch",
                method_name="Run",
                log_file=log_file,
                arguments={
                    "dbPath": str(database_path.absolute()),
                    "logLevel": unity_log_level,
                },
            )

        with StageTimer(f"extract.export.backup.{cli_ctx.variant}"):
            _create_backup_after_export(cli_ctx, variant_config, database_path)
```

- [ ] **Step 5: Wrap `code-facts` and `build`**

In `code_facts()`:

```python
        with StageTimer(f"extract.code_facts.{cli_ctx.variant}"):
            count = extract_code_facts(cli_ctx.repo_root, assembly, raw_db_path)
```

In `build()`:

```python
        with StageTimer(f"extract.build.{cli_ctx.variant}"):
            build_clean_db(
                raw_db_path=raw_db_path,
                clean_db_path=clean_db_path,
                mapping_json_path=mapping_json_path,
            )
```

- [ ] **Step 6: Verify command parsing still works**

Run:

```bash
uv run erenshor extract --help
```

Expected: command help prints successfully.

Run a non-destructive dry-run:

```bash
uv run erenshor --dry-run -V playtest extract build
```

Expected: dry-run output only; no `[TIMING]` line because no real work ran.

- [ ] **Step 7: Commit**

```bash
git add src/erenshor/cli/commands/extract.py
git commit -m "feat(cli): log extraction stage timings"
```

---

### Task 3: Add AssetRipper internal sub-stage timings

**Files:**
- Modify: `src/erenshor/infrastructure/assetripper/assetripper.py`
- Test: `tests/unit/infrastructure/assetripper/test_assetripper.py`

- [ ] **Step 1: Write the failing test**

Append to `TestAssetRipperExtraction` in `tests/unit/infrastructure/assetripper/test_assetripper.py`:

```python
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.run")
    @patch("erenshor.infrastructure.assetripper.assetripper.subprocess.Popen")
    def test_extract_logs_internal_stage_timings(
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
        messages: list[str] = []
        sink_id = logger.add(messages.append, format="{message}")

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
        mock_clock = MockClock()
        assetripper = AssetRipper(executable_path=executable, port=8080, timeout=1, clock=mock_clock)

        original_path_open = Path.open
        from io import BytesIO

        def patched_path_open(self, mode="r", *args, **kwargs):
            if "assetripper_" in str(self) and "rb" in mode:
                return BytesIO(b"Export started\nFinished post-export\n")
            return original_path_open(self, mode, *args, **kwargs)

        try:
            with patch.object(Path, "open", patched_path_open):
                assetripper.extract(source_dir=source_dir, target_dir=target_dir, log_dir=tmp_path)
        finally:
            logger.remove(sink_id)

        assert any("[TIMING] assetripper.start_server completed" in message for message in messages)
        assert any("[TIMING] assetripper.load_files completed" in message for message in messages)
        assert any("[TIMING] assetripper.export_start completed" in message for message in messages)
        assert any("[TIMING] assetripper.monitor_export completed" in message for message in messages)
        assert any("[TIMING] assetripper.stop_server completed" in message for message in messages)
```

Also add `from loguru import logger` to the test imports.

- [ ] **Step 2: Run the red test**

```bash
uv run pytest tests/unit/infrastructure/assetripper/test_assetripper.py::TestAssetRipperExtraction::test_extract_logs_internal_stage_timings -v
```

Expected: assertion failure because no timing lines exist.

- [ ] **Step 3: Wrap AssetRipper internals**

In `src/erenshor/infrastructure/assetripper/assetripper.py`, import:

```python
from erenshor.infrastructure.timing import StageTimer
```

Modify `extract()`:

```python
        try:
            with StageTimer("assetripper.start_server", clock=self.clock):
                self.start_server(log_dir=log_dir)

            with StageTimer("assetripper.load_files", clock=self.clock):
                self._load_files(source_dir)

            with StageTimer("assetripper.export_start", clock=self.clock):
                self._export_files(target_dir)

            with StageTimer("assetripper.monitor_export", clock=self.clock):
                self._monitor_export()

            logger.info("Asset extraction complete!")
            logger.info(f"Unity project ready at: {target_dir}")
            if self._log_file:
                logger.info(f"Log file: {self._log_file}")

        finally:
            with StageTimer("assetripper.stop_server", clock=self.clock):
                self.stop_server()
```

- [ ] **Step 4: Run AssetRipper tests**

```bash
uv run pytest tests/unit/infrastructure/assetripper/test_assetripper.py -v
```

Expected: all AssetRipper tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/infrastructure/assetripper/assetripper.py tests/unit/infrastructure/assetripper/test_assetripper.py
git commit -m "feat(cli): time AssetRipper extraction stages"
```

---

### Task 4: Add Unity subprocess overhead timing

**Files:**
- Modify: `src/erenshor/infrastructure/unity/batch_mode.py`
- Test: `tests/unit/infrastructure/unity/test_batch_mode.py`

- [ ] **Step 1: Write failing test for subprocess timing**

Add to `TestUnityBatchModeExecuteMethod`:

```python
    @patch("erenshor.infrastructure.unity.batch_mode.subprocess.Popen")
    def test_execute_method_logs_subprocess_duration(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        unity_exe = tmp_path / "Unity"
        unity_exe.touch()
        project_path = tmp_path / "UnityProject"
        project_path.mkdir()
        (project_path / "Assets").mkdir()
        (project_path / "ProjectSettings").mkdir()
        log_file = tmp_path / "logs" / "export.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("[EXPORT_COMPLETE] Export completed successfully in 3.00s\n")
        messages: list[str] = []
        sink_id = logger.add(messages.append, format="{message}")

        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0]
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        mock_clock = MockClock()

        try:
            unity = UnityBatchMode(unity_path=unity_exe, timeout=1800, clock=mock_clock)
            unity.execute_method(
                project_path=project_path,
                class_name="ExportBatch",
                method_name="Run",
                log_file=log_file,
                arguments={"dbPath": "/path/to/db.sqlite", "logLevel": "normal"},
            )
        finally:
            logger.remove(sink_id)

        assert any("[TIMING] unity.batch_subprocess completed in 5.00s" in message for message in messages)
```

Add `from loguru import logger` to imports.

- [ ] **Step 2: Run red test**

```bash
uv run pytest tests/unit/infrastructure/unity/test_batch_mode.py::TestUnityBatchModeExecuteMethod::test_execute_method_logs_subprocess_duration -v
```

Expected: assertion failure.

- [ ] **Step 3: Implement subprocess timing**

Import:

```python
from erenshor.infrastructure.timing import StageTimer
```

Wrap the monitored loop in `execute_method()`:

```python
            with StageTimer("unity.batch_subprocess", clock=self.clock):
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

Keep `_check_execution_result()` outside the timing block so parsing failures are not counted as Unity subprocess runtime.

- [ ] **Step 4: Run Unity wrapper tests**

```bash
uv run pytest tests/unit/infrastructure/unity/test_batch_mode.py -v
```

Expected: all Unity wrapper tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/infrastructure/unity/batch_mode.py tests/unit/infrastructure/unity/test_batch_mode.py
git commit -m "feat(cli): time Unity batch subprocesses"
```

---

### Task 5: Add optional Unity listener-level profiling

**Files:**
- Modify: `src/Assets/Editor/ExportBatch.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs`

- [ ] **Step 1: Add profiler model**

Create `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs`:

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Debug = UnityEngine.Debug;

public sealed class AssetScanProfiler
{
    private readonly Dictionary<string, ListenerTiming> _timings = new();

    public bool Enabled { get; }

    public AssetScanProfiler(bool enabled)
    {
        Enabled = enabled;
    }

    public void Measure(string listenerName, string methodName, Action action)
    {
        if (!Enabled)
        {
            action();
            return;
        }

        var stopwatch = Stopwatch.StartNew();
        action();
        stopwatch.Stop();

        string key = listenerName + "." + methodName;
        if (!_timings.TryGetValue(key, out var timing))
        {
            timing = new ListenerTiming(listenerName, methodName);
            _timings[key] = timing;
        }

        timing.Calls++;
        timing.ElapsedTicks += stopwatch.ElapsedTicks;
    }

    public void LogSummary()
    {
        if (!Enabled)
            return;

        foreach (var timing in _timings.Values.OrderByDescending(t => t.ElapsedTicks))
        {
            double seconds = (double)timing.ElapsedTicks / Stopwatch.Frequency;
            Debug.Log($"[EXPORT_PROFILE] {timing.Listener}.{timing.Method}: {seconds:F3}s over {timing.Calls} calls");
        }
    }

    private sealed class ListenerTiming
    {
        public string Listener { get; }
        public string Method { get; }
        public long Calls { get; set; }
        public long ElapsedTicks { get; set; }

        public ListenerTiming(string listener, string method)
        {
            Listener = listener;
            Method = method;
        }
    }
}
```

- [ ] **Step 2: Thread profiler through `AssetScanner`**

Modify `AssetScanner`:

```csharp
private readonly AssetScanProfiler _profiler;

public AssetScanner(AssetScanProfiler? profiler = null)
{
    _profiler = profiler ?? new AssetScanProfiler(false);
}
```

Wrap listener invocation sites:

```csharp
_profiler.Measure(listenerObj.GetType().Name, "OnScanStarted", () =>
{
    InvokeListenerMethod(listenerObj, "OnScanStarted");
});
```

For `OnAssetFound` reflection calls, wrap only the method invocation:

```csharp
_profiler.Measure(listenerObj.GetType().Name, "OnAssetFound", () =>
{
    method.Invoke(listenerObj, new object[] { asset });
});
```

For `OnScanFinished`, wrap the final invocation and call `_profiler.LogSummary()` after all listeners finish.

- [ ] **Step 3: Add `-profile` command-line parsing in `ExportBatch`**

Extend `CommandLineArgs`:

```csharp
public bool profile;
```

Set default:

```csharp
profile = false
```

Parse:

```csharp
case "-profile":
    parsed.profile = string.Equals(args[i + 1], "true", StringComparison.OrdinalIgnoreCase);
    break;
```

Construct scanner:

```csharp
AssetScanProfiler profiler = new AssetScanProfiler(args.profile);
AssetScanner scanner = new AssetScanner(profiler);
```

Log config:

```csharp
Log(LogLevel.Normal, args.logLevel, $"[EXPORT_CONFIG] Profile: {args.profile}");
```

- [ ] **Step 4: Add CLI `--profile` flag for Unity export**

Modify `src/erenshor/cli/commands/extract.py` export signature:

```python
def export(
    ctx: typer.Context,
    profile: bool = typer.Option(False, "--profile", help="Log per-listener Unity export timings"),
) -> None:
```

Pass to Unity arguments:

```python
                arguments={
                    "dbPath": str(database_path.absolute()),
                    "logLevel": unity_log_level,
                    "profile": "true" if profile else "false",
                },
```

- [ ] **Step 5: Verify C# diagnostics and CLI help**

Run:

```bash
uv run erenshor extract export --help
```

Expected: help includes `--profile`.

Run LSP diagnostics for changed C# files:

```text
Use LSP diagnostics on:
- src/Assets/Editor/ExportBatch.cs
- src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs
- src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs
```

Expected: no diagnostics.

- [ ] **Step 6: Run a profiled playtest export**

Run:

```bash
uv run erenshor -V playtest extract export --profile
```

Expected output/log evidence:

```text
[EXPORT_CONFIG] Profile: True
[EXPORT_PROFILE] SomeListener.OnScanFinished: ...s over 1 calls
[EXPORT_PROFILE] SomeListener.OnAssetFound: ...s over ... calls
[TIMING] extract.export.unity_subprocess.playtest completed in ...s
```

If Unity license validation fails, open Unity Hub, wait until the license refreshes, rerun the same command once, and record the failed runtime separately in the final report.

- [ ] **Step 7: Commit**

```bash
git add src/Assets/Editor/ExportBatch.cs src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs src/Assets/Editor/ExportSystem/AssetScanner/AssetScanProfiler.cs src/erenshor/cli/commands/extract.py
git commit -m "feat(export): add optional listener profiling"
```

---

### Task 6: Add CodeFacts generic AST node shape matcher

**Files:**
- Modify: `src/tools/CodeFacts/Matchers.cs`
- Modify: `src/tools/CodeFacts/Specs.cs` only if stricter args validation is needed; otherwise leave unchanged.
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

The exact `shape` may need one analyzer failure to capture the pinned decompiler rendering. If it fails, copy the analyzer's normalized actual candidate output added in Step 4 rather than hand-editing spaces.

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

In `Matchers` add:

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

### Task 7: Pin playtest `GuaranteeOneDrop` retry-loop semantics

**Files:**
- Modify: `src/tools/CodeFacts/specs/erenshor-facts.json`

- [ ] **Step 1: Replace weak `statement_shape` pin**

Change `loot.guarantee_one_drop` from:

```json
"matcher": "statement_shape", "args": { "statement": "ActualDrops.Add (item);" }
```

to:

```json
"matcher": "node_shape",
"args": {
  "kind": "ForStatement",
  "shape": "for (int i = 0; i < NumberOfGuaranteedDrops; i++) { Item item = null; int num2 = 0; do { item = GuaranteeOneDrop [Random.Range (0, GuaranteeOneDrop.Count)]; num2++; } while (num2 < 10 && (item == null || ActualDrops.Contains (item))); if (item != null) { ActualDrops.Add (item); } }"
}
```

Keep the note explicit:

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

### Task 8: Document how to read timing output

**Files:**
- Modify: `.agent/skills/refreshing-game-data/SKILL.md` only if the current worktree owner confirms the existing unstaged skill edit is ours to update; otherwise modify the source-owned copy in the correct setup repo per global AGENTS guidance.
- Modify: `AGENTS.md` only if timing commands become essential workflow guidance.

- [ ] **Step 1: Add timing guidance to the refresh skill**

Add this to the refresh validation section:

```markdown
## Timing and profiling refreshes

Extraction commands emit `[TIMING]` lines. Use them to separate Steam download,
AssetRipper, Unity launch/export, code-facts, and clean build cost before
optimizing. For slow Unity exports, rerun only the export with listener profiling:

```bash
uv run erenshor -V playtest extract export --profile
```

Compare `unity.batch_subprocess` against Unity's `[EXPORT_COMPLETE]` time:
large gaps before `[EXPORT_START]` usually mean Unity license refresh, package
restore, asset import, or script compilation rather than listener work. Use
`[EXPORT_PROFILE]` rows to identify slow listeners or `OnScanFinished()` DB
writes.
```

- [ ] **Step 2: Verify no unrelated skill changes were swept in**

Run:

```bash
git diff -- .agent/skills/refreshing-game-data/SKILL.md
```

Expected: only the timing guidance if the file is intentionally in scope. If unrelated edits appear, stop and ask the owner before staging.

- [ ] **Step 3: Commit docs**

```bash
git add .agent/skills/refreshing-game-data/SKILL.md
git commit -m "docs(pipeline): document extraction timing output"
```

---

## Final Verification

Run after all tasks:

```bash
uv run ruff check src/erenshor/infrastructure/timing.py src/erenshor/cli/commands/extract.py src/erenshor/infrastructure/assetripper/assetripper.py src/erenshor/infrastructure/unity/batch_mode.py tests/unit/infrastructure/test_timing.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py tests/integration/test_code_facts_tool.py
uv run mypy src/erenshor/infrastructure/timing.py src/erenshor/cli/commands/extract.py src/erenshor/infrastructure/assetripper/assetripper.py src/erenshor/infrastructure/unity/batch_mode.py
uv run pytest tests/unit/infrastructure/test_timing.py tests/unit/infrastructure/assetripper/test_assetripper.py tests/unit/infrastructure/unity/test_batch_mode.py tests/integration/test_code_facts_tool.py tests/test_code_facts_coverage.py -v
uv run erenshor -V playtest extract code-facts
uv run erenshor -V playtest extract export --profile
```

Expected:

- Python checks pass.
- CodeFacts test fixture passes.
- Playtest code-facts extraction pins the full guaranteed-loot loop.
- Profiled playtest export log contains both `[TIMING]` and `[EXPORT_PROFILE]` rows.

Do not run `golden capture` for playtest. Do not deploy wiki, guide, maps, or sheets as part of this profiling work.

## Self-Review

- Spec coverage: export slowness gets CLI stage timing, AssetRipper sub-stage timing, Unity subprocess timing, and optional listener profiling. CodeFacts gets a compound AST node matcher and applies it to the exact loot-loop limitation found in this session.
- Placeholder scan: no incomplete markers or unbounded generic test steps remain.
- Type consistency: timing uses existing `Clock`/`MockClock`; CodeFacts matcher uses existing `FactSpec.Args` and `MethodDeclaration` patterns.
- Scope check: no new refresh orchestration command is introduced. The plan instruments existing commands, so it does not change pipeline order or variant safety rules.
