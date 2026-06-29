---
title: Export Field-Coverage Gate — Implementation Plan
type: plan
status: active
created: 2026-06-29
parent: 2026-06-29-export-field-coverage-gate
---

# Export Field-Coverage Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `skill://unity-export-system`, `skill://code-facts`, `skill://refreshing-game-data`, and the parent spec `docs/plans/2026-06-29-export-field-coverage-gate.md` before starting.

**Goal:** A pre-export gate that fails when a game class the exporter reads gains, loses, or retypes a public field without the change being acknowledged in a checked-in JSON manifest — plus the one-time reconciliation that seeds the manifest against the current playtest build.

**Architecture:** A standalone, **read-only** C# tool (`src/tools/ExportSurface/`, Mono.Cecil, metadata-only — no Unity, no decompiler) reads the shipped `Assembly-CSharp.dll` and diffs the public-instance-field surface of the in-scope game types against `field-coverage.json` (invariants 1–2: completeness, no staleness/retype), emitting a JSON envelope. A Python layer wraps it: the `extract export` precondition invokes the tool **and** runs a listener-declaration regex (invariant 3), aggregating one pass/fail before Unity compiles; a Python seeding helper produces and normalizes the manifest.

**Tech Stack:** C# .NET 9 console tool + Mono.Cecil; Python (Typer CLI, precondition system); pytest; JSON manifest.

**Variant scope:** Playtest is the focused build; the manifest is seeded from it. Single target — no per-variant logic.

**Constraints:**
- **No direct `dotnet` in workflows.** Per `AGENTS.md`, every workflow runs via `uv run erenshor …` / `uv run pytest`. `dotnet` appears **only** inside the Python runner's `subprocess` (mirroring `src/erenshor/application/code_facts/runner.py`).
- Metadata-only (`Mono.Cecil`, never `Assembly.LoadFrom`). Public instance fields only.
- The C# tool is **read-only** — it never writes the manifest. Drift is reported in the envelope; classification is human; manifest production/formatting is the Python seeding helper.
- In-scope types are the game-data listener `<T>`s, excluding the generic Unity wrappers `GameObject`/`Object`/`NullScriptableObject`.

---

## File map

- **Create** `src/tools/ExportSurface/ExportSurface.csproj` — .NET 9 console, pins `Mono.Cecil`.
- **Create** `src/tools/ExportSurface/Manifest.cs` — manifest model + JSON load (read-only).
- **Create** `src/tools/ExportSurface/Checker.cs` — Cecil field enumeration + completeness/staleness/retype diff + envelope model.
- **Create** `src/tools/ExportSurface/Program.cs` — CLI shell (`<dll> <manifest> [--out]`), `/Managed/` policy, exit codes.
- **Create** `src/erenshor/application/export_surface/__init__.py`, `runner.py` — wrap+invoke the tool (`dotnet` in subprocess), parse findings, invariant-3 regex, manifest seed/normalize helpers.
- **Create** `src/erenshor/cli/preconditions/checks/field_coverage.py` — the precondition check.
- **Modify** `src/erenshor/cli/commands/extract.py:28-30` (import) and `:404-408` (decorator).
- **Create** `src/tools/ExportSurface/field-coverage.json` — the seeded manifest (Sub-phase C).
- **Tests:** `tests/unit/application/export_surface/test_runner.py`, `test_listener_coverage.py`, `test_seed.py`; `tests/unit/cli/preconditions/checks/test_field_coverage.py`; `tests/integration/test_export_surface_tool.py`.

---

## Sub-phase A — ExportSurface C# tool (read-only checker, invariants 1–2)

Outcome: the Python runner (Task B1) can build and invoke the tool; given a DLL + manifest it exits 0 when the public field surface matches and 1 with a JSON envelope of findings otherwise. The tool is verified through the Python integration test (Task A4) — no direct `dotnet` commands.

### Task A1: Scaffold the project

**Files:** Create `src/tools/ExportSurface/ExportSurface.csproj` and `src/tools/ExportSurface/Program.cs` (stub)

- [ ] **Step 1:** Create the csproj, mirroring `src/tools/CodeFacts/CodeFacts.csproj` property block (net9.0, `RollForward=Major`, `Nullable=enable`, `ImplicitUsings=enable`, `InvariantGlobalization=true`, `AnalysisMode=Recommended`, `EnforceCodeStyleInBuild=true`) but swap the package:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <RollForward>Major</RollForward>
    <LangVersion>latest</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <InvariantGlobalization>true</InvariantGlobalization>
    <AnalysisMode>Recommended</AnalysisMode>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
  </PropertyGroup>
  <ItemGroup>
    <!-- Pinned exactly; metadata-only reader, no Unity, no decompiler.
         Confirm the latest-stable Mono.Cecil at implementation time and pin it. -->
    <PackageReference Include="Mono.Cecil" Version="0.11.6" />
  </ItemGroup>
</Project>
```

- [ ] **Step 2:** Add a minimal `Program.cs` so the `Exe` project is buildable from this commit (Task A3 replaces it with the real CLI):

```csharp
// Placeholder entry point; replaced by the real CLI in Task A3.
System.Console.Error.WriteLine("ExportSurface: not implemented yet");
return 2;
```

- [ ] **Step 3: Commit** — `chore(export): scaffold the ExportSurface tool project with a stub entry point`

### Task A2: Manifest model + JSON load (read-only)

**Files:** Create `src/tools/ExportSurface/Manifest.cs`

- [ ] **Step 1:** Implement the model + load, mirroring `src/tools/CodeFacts/Specs.cs`'s `System.Text.Json` record + `LoadSpecs` style. No writer — the tool never emits the manifest.

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ExportSurface;

internal sealed record FieldEntry(
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("status")] string Status,   // "captured" | "ignored"
    [property: JsonPropertyName("by")] string? By,
    [property: JsonPropertyName("reason")] string? Reason);

internal sealed record Manifest(
    [property: JsonPropertyName("tracks_build")] string TracksBuild,
    [property: JsonPropertyName("types")] List<string> Types,
    [property: JsonPropertyName("fields")] Dictionary<string, Dictionary<string, FieldEntry>> Fields)
{
    public static Manifest Load(string path) =>
        JsonSerializer.Deserialize<Manifest>(File.ReadAllText(path))
        ?? throw new InvalidDataException($"empty manifest: {path}");
}
```

- [ ] **Step 2: Commit** — `feat(export): add the read-only field-coverage manifest model`

### Task A3: Cecil enumeration + diff + envelope

**Files:** Create `src/tools/ExportSurface/Checker.cs`

- [ ] **Step 1:** Implement the metadata-only enumerator and the pure diff (covered by the Task A4 integration test):

```csharp
using Mono.Cecil;

namespace ExportSurface;

internal sealed record Finding(string Type, string Field, string Kind, string? Expected, string? Actual);

internal static class Checker
{
    public static Dictionary<string, string> PublicInstanceFields(ModuleDefinition module, string typeFullName)
    {
        var type = module.GetType(typeFullName)
            ?? throw new InvalidDataException($"in-scope type not found in assembly: {typeFullName}");
        var fields = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var f in type.Fields)
        {
            if (!f.IsPublic || f.IsStatic) continue;   // public instance only (spec §1)
            fields[f.Name] = f.FieldType.FullName;
        }
        return fields;
    }

    public static IEnumerable<Finding> Diff(
        string typeName,
        Dictionary<string, FieldEntry> manifestFields,
        Dictionary<string, string> actualFields)
    {
        foreach (var (name, actualType) in actualFields)
        {
            if (!manifestFields.TryGetValue(name, out var entry))
                yield return new Finding(typeName, name, "unclassified", null, actualType);
            else if (entry.Type != actualType)
                yield return new Finding(typeName, name, "retype", entry.Type, actualType);
        }
        foreach (var name in manifestFields.Keys)
            if (!actualFields.ContainsKey(name))
                yield return new Finding(typeName, name, "stale", manifestFields[name].Type, null);
    }
}
```

- [ ] **Step 2:** Replace the A1 stub `Program.cs` with the real CLI (mirror `src/tools/CodeFacts/Program.cs` arg handling + `/Managed/` policy):

```csharp
using Mono.Cecil;
using System.Text.Json;
using ExportSurface;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: ExportSurface <assembly.dll> <manifest.json> [--out <result.json>]");
    return 2;
}
string assemblyPath = Path.GetFullPath(args[0]);
string manifestPath = Path.GetFullPath(args[1]);
string? outPath = (args.Length >= 4 && args[2] == "--out") ? Path.GetFullPath(args[3]) : null;

if (!File.Exists(assemblyPath)) { Console.Error.WriteLine($"assembly not found: {assemblyPath}"); return 2; }
if (!assemblyPath.Replace('\\', '/').Contains("/Managed/"))
{ Console.Error.WriteLine($"refusing non-shipped assembly path (must be under .../Managed/): {assemblyPath}"); return 2; }
if (!File.Exists(manifestPath)) { Console.Error.WriteLine($"manifest not found: {manifestPath}"); return 2; }

var manifest = Manifest.Load(manifestPath);
var findings = new List<Finding>();
using (var asm = AssemblyDefinition.ReadAssembly(assemblyPath))
{
    var module = asm.MainModule;
    foreach (var typeName in manifest.Types)
    {
        var actual = Checker.PublicInstanceFields(module, typeName);
        var declared = manifest.Fields.TryGetValue(typeName, out var d) ? d : new();
        findings.AddRange(Checker.Diff(typeName, declared, actual));
    }
}
var envelope = new
{
    type = "erenshor://export/field-coverage-drift",
    status = findings.Count == 0 ? 0 : 1,
    detail = $"{findings.Count} field-coverage finding(s) against {Path.GetFileName(manifestPath)}.",
    findings = findings.OrderBy(f => f.Type).ThenBy(f => f.Field)
        .Select(f => new { script_type = f.Type, field_name = f.Field, kind = f.Kind, expected = f.Expected, actual = f.Actual }),
};
string json = JsonSerializer.Serialize(envelope, new JsonSerializerOptions { WriteIndented = true });
if (outPath is null) Console.WriteLine(json); else File.WriteAllText(outPath, json);
return findings.Count == 0 ? 0 : 1;
```

- [ ] **Step 3: Commit** — `feat(export): add the ExportSurface checker and CLI`

### Task A4: Python integration test (the tool's verification)

**Files:** Create `tests/integration/test_export_surface_tool.py` (mirror `tests/integration/test_code_facts_tool.py`)

- [ ] **Step 1: Write the failing test** — it builds + invokes the tool **through the Task B1 runner** against the playtest DLL with crafted manifests, asserting each finding kind. Skip when the DLL is absent (mirror `tests/integration/test_code_facts_real.py`). NOTE: this test depends on Task B1's `run_field_coverage`; if executing strictly in order, write the test now (it fails to import), implement B1, then it passes.

```python
import json
from pathlib import Path
import pytest
from erenshor.application.export_surface.runner import run_field_coverage

DLL = Path("variants/playtest/game/Erenshor_Data/Managed/Assembly-CSharp.dll")

@pytest.mark.integration
@pytest.mark.skipif(not DLL.exists(), reason="playtest shipped DLL not present")
def test_reports_each_finding_kind(tmp_path):
    repo = Path(".").resolve()
    # Empty fields -> every LootTable field is unclassified; bogus field -> stale;
    # wrong type on a real field -> retype. (Pick a field known-present at impl time.)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "tracks_build": "test",
        "types": ["LootTable"],
        "fields": {"LootTable": {
            "DefinitelyGoneField": {"type": "System.Int32", "status": "ignored", "reason": "test stale"},
        }},
    }))
    findings = run_field_coverage(repo, DLL.resolve(), manifest)
    kinds = {f["kind"] for f in findings}
    assert "unclassified" in kinds        # real LootTable fields absent from manifest
    assert "stale" in kinds               # DefinitelyGoneField not on the type
```

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_export_surface_tool.py -v`. Expected: PASS (after B1) or SKIP without the DLL.
- [ ] **Step 3: Commit** — `test(export): integration-test the ExportSurface tool via the runner`

---

## Sub-phase B — Python wrapper, invariant 3, precondition

### Task B1: Tool runner (wraps `dotnet`)

**Files:** Create `src/erenshor/application/export_surface/__init__.py` (empty); `runner.py`. Test: `tests/unit/application/export_surface/test_runner.py`

- [ ] **Step 1: Write the failing test** — missing DLL/manifest raises; a returncode-2 (usage/IO) raises `RuntimeError`; otherwise returns the parsed `findings` (monkeypatch `subprocess.run` for the success/returncode-2 paths):

```python
from pathlib import Path
import pytest
from erenshor.application.export_surface import runner

def test_missing_dll_raises(tmp_path):
    (tmp_path / "m.json").write_text("{}")
    with pytest.raises(FileNotFoundError):
        runner.run_field_coverage(Path("."), tmp_path / "nope.dll", tmp_path / "m.json")
```

- [ ] **Step 2:** Run it; expect ImportError/FAIL.
- [ ] **Step 3:** Implement `run_field_coverage(repo_root, assembly, manifest) -> list[dict]`, mirroring `code_facts/runner.py`'s subprocess pattern exactly:

```python
import json, subprocess
from pathlib import Path
from typing import Any

TOOL_PROJECT = Path("src") / "tools" / "ExportSurface"

def run_field_coverage(repo_root: Path, assembly: Path, manifest: Path) -> list[dict[str, Any]]:
    if not assembly.exists():
        raise FileNotFoundError(f"shipped game assembly not found: {assembly}")
    if not manifest.exists():
        raise FileNotFoundError(f"field-coverage manifest not found: {manifest}")
    project = repo_root / TOOL_PROJECT
    subprocess.run(["dotnet", "build", str(project), "-c", "Release"],
                   check=True, capture_output=True, text=True)
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--no-build", "--project", str(project),
         "--", str(assembly), str(manifest)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode not in (0, 1):   # 2 = usage/IO error
        raise RuntimeError(f"ExportSurface failed (exit {proc.returncode}).\n{proc.stderr}")
    return json.loads(proc.stdout)["findings"]
```

- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(export): add the field-coverage tool runner`

### Task B2: Invariant 3 — listener-type coverage

**Files:** Modify `runner.py`. Test: `tests/unit/application/export_surface/test_listener_coverage.py`

- [ ] **Step 1: Write the failing test** (temp listener dir; a missing `<T>` is reported; generic Unity wrappers excluded):

```python
from pathlib import Path
from erenshor.application.export_surface.runner import missing_listener_types

def test_missing_and_generic_excluded(tmp_path):
    d = tmp_path; (d / "ItemListener.cs").write_text("class ItemListener : IAssetScanListener<Item> {}")
    (d / "FooListener.cs").write_text("class FooListener : IAssetScanListener<Foo> {}")
    (d / "BookListener.cs").write_text("class BookListener : IAssetScanListener<NullScriptableObject> {}")
    assert missing_listener_types(d, {"Item"}) == ["Foo"]
```

- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement in `runner.py`:

```python
import re
GENERIC_UNITY_TYPES = {"GameObject", "Object", "NullScriptableObject"}
_LISTENER = re.compile(r"IAssetScanListener<(\w+)>")

def missing_listener_types(listener_dir: Path, declared_types: set[str]) -> list[str]:
    found: set[str] = set()
    for cs in listener_dir.glob("*.cs"):
        for m in _LISTENER.finditer(cs.read_text(encoding="utf-8")):
            if (t := m.group(1)) not in GENERIC_UNITY_TYPES:
                found.add(t)
    return sorted(found - declared_types)
```

- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(export): check listener-type coverage against the manifest`

### Task B3: Precondition check

**Files:** Create `src/erenshor/cli/preconditions/checks/field_coverage.py`. Test: `tests/unit/cli/preconditions/checks/test_field_coverage.py`

- [ ] **Step 1: Write the failing test** (monkeypatch `run_field_coverage` + `missing_listener_types`; assert `passed` toggles and detail names the findings):

```python
from erenshor.cli.preconditions.checks import field_coverage as fc

def test_fails_on_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(fc, "run_field_coverage", lambda *a: [{"script_type": "Item", "field_name": "X", "kind": "unclassified"}])
    monkeypatch.setattr(fc, "missing_listener_types", lambda *a: [])
    managed = tmp_path / "Erenshor_Data" / "Managed"; managed.mkdir(parents=True)
    (managed / "Assembly-CSharp.dll").write_bytes(b"")
    res = fc.export_field_coverage_current({"repo_root": tmp_path, "game_dir": tmp_path})
    assert res.passed is False and "unclassified" in res.detail
```

- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement `export_field_coverage_current(context) -> PreconditionResult` (import `run_field_coverage`, `missing_listener_types` at module scope so the test can patch them): resolve `dll = context["game_dir"]/"Erenshor_Data"/"Managed"/"Assembly-CSharp.dll"`, `manifest = context["repo_root"]/"src/tools/ExportSurface/field-coverage.json"`, `listener_dir = context["repo_root"]/"src/Assets/Editor/ExportSystem/AssetScanner/Listener"`; build `declared = set(json.loads(manifest.read_text())["types"])`; aggregate `run_field_coverage(...)` + `missing_listener_types(listener_dir, declared)`; return `PreconditionResult(False, "export_field_coverage_current", "export field-coverage gate failed", detail=<rendered findings + 'classify in src/tools/ExportSurface/field-coverage.json'>)` on any finding, else `PreconditionResult(True, "export_field_coverage_current", "export field surface matches the manifest")`.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(export): add the export field-coverage precondition`

### Task B4: Wire into `extract export`

**Files:** Modify `src/erenshor/cli/commands/extract.py`

- [ ] **Step 1:** Add the import (near `:28-30`):

```python
from erenshor.cli.preconditions.checks.field_coverage import export_field_coverage_current
```

- [ ] **Step 2:** Make it the **first** check in `export`'s decorator (`:404-408`):

```python
@require_preconditions(
    export_field_coverage_current,
    unity_project_exists,
    editor_scripts_linked,
    unity_version_matches,
)
def export(
```

- [ ] **Step 3:** Run `uv run pytest tests/unit/cli/commands/test_extract.py -v`. Expected: PASS (update any test that asserts the export precondition set to include the new check).
- [ ] **Step 4: Commit** — `feat(export): gate extract export on field-coverage before compile`

---

## Sub-phase C — Reconciliation (seed the manifest against playtest)

Outcome: a committed `field-coverage.json` classifying every public field of every in-scope type for the playtest build; export-relevant gaps captured or explicitly ignored; the gate passes on playtest.

### Task C1: Seeding helper

**Files:** Modify `runner.py` (add `seed_entries` + `write_manifest`). Test: `tests/unit/application/export_surface/test_seed.py`

- [ ] **Step 1: Write the failing test** — `seed_entries` turns `unclassified` findings into placeholder entries (status `""`) keyed by type→field; `write_manifest` emits sorted JSON with one field entry per line:

```python
from erenshor.application.export_surface.runner import seed_entries, write_manifest

def test_seed_and_write(tmp_path):
    findings = [{"script_type": "Item", "field_name": "RareItem", "kind": "unclassified", "actual": "System.Boolean"}]
    fields = seed_entries(findings)
    assert fields["Item"]["RareItem"] == {"type": "System.Boolean", "status": "", "by": None, "reason": None}
    out = tmp_path / "m.json"; write_manifest(out, "1", ["Item"], fields)
    text = out.read_text()
    assert text.count('"RareItem":') == 1 and "\n" in text
```

- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement `seed_entries(findings)` (group `unclassified` findings → `{type: {field: {"type": actual, "status": "", "by": None, "reason": None}}}`) and `write_manifest(path, tracks_build, types, fields)` — emit `{tracks_build, types(sorted), fields}` with each field entry serialized compact on one line, types and fields sorted (`json.dumps(entry, separators=(", ", ": "))` per entry, assembled with sorted keys). This is the one place the manifest is written; the C# tool stays read-only.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(export): add field-coverage manifest seeding and writer`

### Task C2: Generate the seed manifest

- [ ] **Step 1:** Compute the in-scope `types` (same rule as invariant 3) and write a seed manifest with empty `fields`:

```bash
uv run python -c "
from pathlib import Path
from erenshor.application.export_surface.runner import missing_listener_types, write_manifest
d = Path('src/Assets/Editor/ExportSystem/AssetScanner/Listener')
types = sorted(missing_listener_types(d, set()))   # all game-data listener <T>, generics excluded
write_manifest(Path('src/tools/ExportSurface/field-coverage.json'), 'SEED', types, {})
print(types)
"
```

- [ ] **Step 2:** Review the `types` list; drop any world-component type with no meaningful serialized data surface (document the decision in the commit message). Re-write the seed if the set changed.

### Task C3: Classify every field

- [ ] **Step 1:** Run the gate against playtest to list every field as `unclassified`, and seed placeholders:

```bash
uv run python -c "
from pathlib import Path
from erenshor.application.export_surface.runner import run_field_coverage, seed_entries, write_manifest
import json
repo = Path('.').resolve()
dll = repo / 'variants/playtest/game/Erenshor_Data/Managed/Assembly-CSharp.dll'
mpath = repo / 'src/tools/ExportSurface/field-coverage.json'
m = json.loads(mpath.read_text())
findings = run_field_coverage(repo, dll, mpath)
write_manifest(mpath, m['tracks_build'], m['types'], seed_entries(findings))
print(f'{len(findings)} fields to classify')
"
```

- [ ] **Step 2:** Edit `field-coverage.json`: set each entry's `status` to `captured` (+ `by`: the listener that reads it, cross-checked against `src/Assets/Editor/`) or `ignored` (+ `reason`). Leave genuinely-undecided fields as the C4 worklist.

### Task C4: Resolve gaps + commit

- [ ] **Step 1:** For each field that *should* be exported but isn't, implement the capture (listener/record/clean-DB column per `skill://unity-export-system`) as its own commit; otherwise mark `ignored(<reason>)`. For each `retype` finding, verify the consuming listener still reads it correctly.
- [ ] **Step 2:** Set `tracks_build` to the current playtest build id (from the export log / backup metadata).
- [ ] **Step 3: Commit** — `feat(export): seed the field-coverage manifest for the playtest build`

### Task C5: Full validation

- [ ] **Step 1:** `uv run erenshor -V playtest extract export` — the field-coverage precondition passes (exit 0), then the export runs.
- [ ] **Step 2:** Negative check: delete one manifest entry, re-run `uv run erenshor -V playtest extract export`, confirm it aborts with the field-coverage detail **before** Unity compiles; restore the entry.
- [ ] **Step 3:** `uv run pytest` green.

---

## Verification

- [ ] `uv run pytest tests/unit/application/export_surface tests/unit/cli/preconditions/checks/test_field_coverage.py -v` passes.
- [ ] `uv run pytest tests/integration/test_export_surface_tool.py -v` passes (or skips without the DLL).
- [ ] `uv run erenshor -V playtest extract export` runs the gate (exit 0) then exports.
- [ ] Deleting a manifest entry makes `extract export` fail fast with the field-coverage detail, before Unity compiles.
- [ ] `field-coverage.json` classifies every public field of every in-scope type; no empty `status` remains.
- [ ] `uv run pytest` (full suite) green.
- [ ] No step invokes `dotnet` directly; the only `dotnet` call is inside `runner.py`'s subprocess.

## Self-review

- **Spec coverage:** manifest (§4) → A2 (read), C1 (write); invariants 1–2 (§5) → A3; invariant 3 (§5) → B2; metadata-only Mono.Cecil (§6) → A1/A3; sibling read-only tool, no decompiler pin (§6) → A1–A3; pre-export precondition (§6) → B3/B4; reconciliation (§8) → C; single target (§7) → C2 (one `types` set, one manifest).
- **Type consistency:** envelope keys `script_type`/`field_name`/`kind`/`actual` match between A3 (emit), A4/B1 (consume), and C1 (`seed_entries`); `run_field_coverage`/`missing_listener_types`/`export_field_coverage_current`/`seed_entries`/`write_manifest` are referenced identically across tasks.
- **No direct dotnet in workflows:** all build/invoke goes through `runner.py`'s subprocess (mirroring `code_facts/runner.py`); plan steps use only `uv run …`.
- **Mono.Cecil version** `0.11.6` is the current stable line; confirm + pin latest-stable at A1 (CodeFacts pin policy).
