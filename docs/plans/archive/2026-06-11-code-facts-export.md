---
title: Code-Facts Export Implementation Plan
type: plan
status: implemented
created: 2026-06-11
archived: 2026-06-25
parent:
---

# Code-Facts Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote hardcoded game-logic constants to first-class exported data: a pinned C# analyzer extracts them from the shipped `Assembly-CSharp.dll` into the raw→clean DB pipeline, and structural assertions fail the refresh loudly when re-implemented game semantics drift.

**Architecture:** A `src/tools/CodeFacts/` .NET console tool (ICSharpCode.Decompiler, exact-pinned) decompiles named methods to typed ASTs and runs declarative fact specs in two modes — `extract` (values flow out as data) and `assert` (structural invariants must hold). Python invokes the tool, writes `code_facts` tables into the raw DB; the processor carries them to the clean DB under golden coverage. Game update → values auto-flow and appear in golden diffs; structure change → matcher binds ≠ exactly once → hard failure.

**Tech Stack:** .NET 8 console + ICSharpCode.Decompiler (NuGet, exact version pin); Python (subprocess + sqlite3, no new deps); pytest (`integration` marker for steps needing dotnet/game files).

**Tracking:** bd issue `Erenshor-7jw`.

---

## Design decisions (locked during review — do not relitigate)

1. **Extract over verify.** Numeric parameters and IDs are *data*: extracted, not hand-curated-then-checked. Drift for these becomes impossible by construction. Human review point = the existing mandatory golden-diff review.
2. **Assert only semantics.** Where the pipeline *re-implements* game logic (Python derivation rules, Lua mappings), the analyzer asserts the upstream structure still matches and fails loud otherwise.
3. **Shipped DLL only.** Input is `variants/{variant}/game/Erenshor_Data/Managed/Assembly-CSharp.dll`. NEVER `unity/ExportedProject/Library/ScriptAssemblies/` (locally recompiled) or `AuxiliaryFiles/` (derived). Hard-assert the path shape.
4. **Fail fast, bind exactly once.** A matcher that binds zero or multiple times is a hard error. No fuzzy fallbacks.
5. **Values are strings end-to-end.** AST literal → invariant string → TEXT columns. No float round-tripping.
6. **Tests assert shape, not values.** The real-DLL integration test asserts every fact extracted + sane types/ranges. Exact values are golden-file territory; duplicating them in tests would reintroduce the thrash this design eliminates.
7. **Tool version pinned exactly.** ICSharpCode.Decompiler upgrades are deliberate, separate commits — never combined with a game update.

## Grounded facts to encode (verified against the main-variant binary, 2026-06-11)

`LootTable.InitLootTable` per-kill world-drop injections (`LootTable.cs:101-159`); rate scales by `GameData.ServerLootRate + num` except where noted:

| Pool / item member | Rate | Gate |
|---|---|---|
| `WorldDropMolds[…]` | 0.005 | — |
| `Maps[…]` | 0.0125 | — |
| `Sivak` | 0.001 | `Level > 15` |
| `XPPot` | 0.002 | `Level > 12` |
| `InertDiamond` | 0.008 | `Level > 20` |
| `PlanarShard` | 0.001 | `Level > 15` |
| `CrystallizedBalance` | 0.0005 | `Level > 30` |
| `Planar` | 0.0005 | `Level > 30` |
| `Misc.Masks[…]` / `Misc.MoloraiMask` | 0.001 — **not loot-rate-scaled**; 99%/1% inner split | `GM.DropMasks` |
| `Empty2` | 0.001 | **`GM.DemoBuild` only** — fact exists but is variant-conditional |
| `CommonWorldItems[…]` | replaces common-slot roll when `Random.Range(0,10) > 8` | — |

Other targets:
- `AuctionHouse.UpdateAH(List<string>, string, float)` (`AuctionHouse.cs:508`) — auctionable envelope gates (item level bounds, value > 0, `SimPlayersCantGet`).
- `Smithing.Combine` — hardcoded upgrade IDs as **string** literals: `"31377423"` (golden template), `"46289586"` (fuel), `"2298018"` (blessing removal).
- `LootTable.InitLootTable` — `GuaranteeOneDrop` shape: exactly one `ActualDrops.Add(GuaranteeOneDrop[Random.Range(0, GuaranteeOneDrop.Count)])` (assert mode).
- `ItemInfoWindow` proc-trigger display strings (assert mode; exact method grounded in Task 6).

## Planned commits

1. `chore(export): scaffold CodeFacts analyzer tool`
2. `feat(export): add extract-mode AST matchers with fixture tests`
3. `feat(export): seed loot, auction, and smithing fact specs`
4. `feat(pipeline): write code facts to the raw database`
5. `feat(pipeline): carry code facts into the clean database`
6. `feat(export): assert structural invariants for re-implemented semantics`
7. `test(pipeline): cross-check code-fact coverage`
8. `docs(pipeline): document code-facts workflow and discovery layer`

## File structure

```
src/tools/CodeFacts/
  CodeFacts.csproj            # net8.0 console, ICSharpCode.Decompiler pinned
  Program.cs                  # arg parsing, orchestration, JSON output, exit codes
  Specs.cs                    # spec/result record types + JSON loading
  Matchers.cs                 # extract + assert matchers over decompiled ASTs
  specs/erenshor-facts.json   # THE fact registry (single source of truth)
  tests/FixtureLib/           # tiny classlib compiled by tests; known shapes
src/erenshor/application/code_facts/
  __init__.py
  runner.py                   # invoke tool, parse JSON, write raw tables
src/erenshor/application/processor/code_facts.py   # raw -> clean passthrough
tests/test_code_facts_writer.py                    # unit (fake JSON, no dotnet)
tests/integration/test_code_facts_tool.py          # fixture-built DLL, matcher behavior
tests/integration/test_code_facts_real.py          # real DLL, shape assertions
tests/test_code_facts_coverage.py                  # specs <-> consumer cross-check
.agent/skills/code-facts/SKILL.md                  # new skill
```
Modified: `AGENTS.md` (boundary list + commands), `src/erenshor/cli/commands/extract.py`, `src/erenshor/application/processor/build.py`, `.agent/skills/refreshing-game-data/SKILL.md`.

> **Warning:** `.agent/skills/refreshing-game-data/SKILL.md` currently carries unrelated *unstaged user edits*. When Task 5 touches it, stage only your hunks (`git add -p`) — never the whole file.

---

### Task 1: Scaffold the CodeFacts analyzer tool

**Files:**
- Create: `src/tools/CodeFacts/CodeFacts.csproj`, `src/tools/CodeFacts/Program.cs`, `src/tools/CodeFacts/.gitignore`
- Modify: `AGENTS.md` (the "Only modify code in…" line)

- [ ] **Step 1: Verify the dotnet SDK supports net8.0**

Run: `dotnet --list-sdks`
Expected: at least one `8.x` (or newer) SDK line. If none, install via `brew install dotnet-sdk` before continuing.

- [ ] **Step 2: Create the project and pin the decompiler**

```bash
mkdir -p src/tools/CodeFacts
cd src/tools/CodeFacts && dotnet new console -n CodeFacts -o . --force
dotnet add package ICSharpCode.Decompiler
```

Then open `CodeFacts.csproj` and replace its content, **copying the exact `Version` NuGet resolved** (check with `grep ICSharpCode CodeFacts.csproj` first — keep that number, never a wildcard):

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <LangVersion>latest</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <InvariantGlobalization>true</InvariantGlobalization>
    <AnalysisMode>Recommended</AnalysisMode>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
    <DefaultItemExcludes>$(DefaultItemExcludes);tests/**</DefaultItemExcludes>
  </PropertyGroup>
  <ItemGroup>
    <!-- Pinned EXACTLY. Upgrading this is a deliberate, standalone commit
         (expect matcher churn); never combine with a game update. -->
    <PackageReference Include="ICSharpCode.Decompiler" Version="<RESOLVED-VERSION>" />
  </ItemGroup>
</Project>
```

Create `src/tools/CodeFacts/.gitignore`:

```
bin/
obj/
```

- [ ] **Step 3: Write the minimal Program.cs (args + exit-code contract only)**

```csharp
using CodeFacts;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: CodeFacts <assembly.dll> <specs.json> [--out <result.json>]");
    return 2;
}

string assemblyPath = Path.GetFullPath(args[0]);
string specsPath = Path.GetFullPath(args[1]);
string? outPath = args.Length >= 4 && args[2] == "--out" ? Path.GetFullPath(args[3]) : null;

if (!File.Exists(assemblyPath))
{
    Console.Error.WriteLine($"assembly not found: {assemblyPath}");
    return 2;
}
// Decision #3: only the shipped binary is authoritative.
if (!assemblyPath.Replace('\\', '/').Contains("/Managed/"))
{
    Console.Error.WriteLine($"refusing non-shipped assembly path (must be under .../Managed/): {assemblyPath}");
    return 2;
}
if (!File.Exists(specsPath))
{
    Console.Error.WriteLine($"specs not found: {specsPath}");
    return 2;
}

var result = Runner.Run(assemblyPath, specsPath); // Task 2
string json = result.ToJson();
if (outPath is null) Console.WriteLine(json);
else File.WriteAllText(outPath, json);
return result.Ok ? 0 : 1;
```

(`Runner`/`Specs` come in Task 2 — to make this compile now, add a temporary `Runner.Run` in `Specs.cs` that throws `NotImplementedException`. Task 2 replaces it.)

- [ ] **Step 4: Build**

Run: `dotnet build src/tools/CodeFacts -c Release`
Expected: `Build succeeded.`

- [ ] **Step 5: Update the AGENTS.md boundary**

In `AGENTS.md`, extend the modifiable-paths sentence to include `src/tools/`:
`**Only modify code in `src/Assets/Editor/`, `src/erenshor/`, `src/mods/`, `src/maps/`, and `src/tools/`.**`

- [ ] **Step 6: Commit**

```bash
git add src/tools/CodeFacts AGENTS.md
git commit -m "chore(export): scaffold CodeFacts analyzer tool"
```

---

### Task 2: Extract-mode matchers + hermetic fixture tests

**Files:**
- Create: `src/tools/CodeFacts/Specs.cs`, `src/tools/CodeFacts/Matchers.cs`
- Create: `src/tools/CodeFacts/tests/FixtureLib/FixtureLib.csproj`, `src/tools/CodeFacts/tests/FixtureLib/FixtureLoot.cs`
- Create: `tests/fixtures/code_facts/fixture-specs.json`
- Test: `tests/integration/test_code_facts_tool.py`

- [ ] **Step 1: Write the fixture library (known shapes, no Unity deps)**

`src/tools/CodeFacts/tests/FixtureLib/FixtureLib.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.0</TargetFramework>
    <Nullable>disable</Nullable>
  </PropertyGroup>
</Project>
```

`src/tools/CodeFacts/tests/FixtureLib/FixtureLoot.cs` — mirrors the game's guarded-roll and string-ID shapes:

```csharp
using System;
using System.Collections.Generic;

namespace FixtureLib
{
    public class FixtureLoot
    {
        public List<string> PoolA = new List<string>();
        public List<string> Drops = new List<string>();
        public string SingletonB = "b";
        public int Level;
        private static readonly Random Rng = new Random();
        private static float Roll => (float)Rng.NextDouble();

        public void Init()
        {
            float rate = 2f;
            if (Roll < 0.005f * rate)
            {
                Drops.Add(PoolA[Rng.Next(0, PoolA.Count)]);
            }
            if (Level > 20 && Roll < 0.0125f * rate)
            {
                Drops.Add(SingletonB);
            }
        }

        public bool Combine(string template, string fuel)
        {
            return template == "31377423" && fuel == "46289586";
        }
    }
}
```

- [ ] **Step 2: Write the fixture specs**

`tests/fixtures/code_facts/fixture-specs.json`:

```json
{
  "schema": 1,
  "facts": [
    {
      "id": "fixture.pool_a",
      "mode": "extract",
      "type": "FixtureLib.FixtureLoot",
      "method": "Init",
      "matcher": "guarded_member_roll",
      "args": { "member": "PoolA" },
      "keys": ["rate", "min_level"]
    },
    {
      "id": "fixture.singleton_b",
      "mode": "extract",
      "type": "FixtureLib.FixtureLoot",
      "method": "Init",
      "matcher": "guarded_member_roll",
      "args": { "member": "SingletonB" },
      "keys": ["rate", "min_level"]
    },
    {
      "id": "fixture.combine_ids",
      "mode": "extract",
      "type": "FixtureLib.FixtureLoot",
      "method": "Combine",
      "matcher": "string_constants",
      "args": {},
      "keys": ["strings"]
    }
  ]
}
```

- [ ] **Step 3: Write the failing integration test**

`tests/integration/test_code_facts_tool.py`:

```python
"""Hermetic tests for the CodeFacts analyzer against a fixture-built DLL."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "src" / "tools" / "CodeFacts"
FIXTURE_PROJ = TOOL / "tests" / "FixtureLib"
SPECS = REPO_ROOT / "tests" / "fixtures" / "code_facts" / "fixture-specs.json"


@pytest.fixture(scope="module")
def fixture_dll(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("fixture") / "Managed"  # satisfies the /Managed/ path gate
    subprocess.run(
        ["dotnet", "build", str(FIXTURE_PROJ), "-c", "Release", "-o", str(out)],
        check=True, capture_output=True, text=True,
    )
    return out / "FixtureLib.dll"


def run_tool(dll: Path, specs: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--project", str(TOOL), "--", str(dll), str(specs)],
        capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_extracts_guarded_rolls_and_strings(fixture_dll: Path) -> None:
    rc, out = run_tool(fixture_dll, SPECS)
    assert rc == 0, out
    facts = {f["id"]: f for f in out["facts"]}
    assert facts["fixture.pool_a"]["values"] == {"rate": "0.005", "min_level": "0"}
    assert facts["fixture.singleton_b"]["values"] == {"rate": "0.0125", "min_level": "20"}
    assert facts["fixture.combine_ids"]["values"] == {"strings": "31377423,46289586"}


def test_unmatched_spec_fails_loud(fixture_dll: Path, tmp_path: Path) -> None:
    specs = json.loads(SPECS.read_text())
    specs["facts"][0]["args"]["member"] = "NoSuchPool"
    bad = tmp_path / "bad-specs.json"
    bad.write_text(json.dumps(specs))
    rc, out = run_tool(fixture_dll, bad)
    assert rc == 1
    assert any("fixture.pool_a" in e for e in out["errors"])
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_code_facts_tool.py -v`
Expected: FAIL (`NotImplementedException` surfaced via non-zero exit / JSON parse error).

- [ ] **Step 5: Implement `Specs.cs`**

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

namespace CodeFacts;

internal sealed record FactSpec(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("method")] string Method,
    [property: JsonPropertyName("matcher")] string Matcher,
    [property: JsonPropertyName("args")] Dictionary<string, string> Args,
    [property: JsonPropertyName("keys")] List<string>? Keys);

internal sealed record SpecsFile(
    [property: JsonPropertyName("schema")] int Schema,
    [property: JsonPropertyName("facts")] List<FactSpec> Facts);

internal sealed record FactResult(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("values")] Dictionary<string, string>? Values,
    [property: JsonPropertyName("ok")] bool? AssertOk);

internal sealed class RunResult
{
    [JsonPropertyName("schema")] public int Schema { get; init; } = 1;
    [JsonPropertyName("assembly")] public required string Assembly { get; init; }
    [JsonPropertyName("facts")] public List<FactResult> Facts { get; } = new();
    [JsonPropertyName("errors")] public List<string> Errors { get; } = new();
    [JsonIgnore] public bool Ok => Errors.Count == 0 && Facts.All(f => f.AssertOk != false);

    public string ToJson() =>
        JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });

    public static SpecsFile LoadSpecs(string path)
    {
        var specs = JsonSerializer.Deserialize<SpecsFile>(File.ReadAllText(path))
            ?? throw new InvalidDataException($"empty specs file: {path}");
        if (specs.Schema != 1) throw new InvalidDataException($"unsupported specs schema {specs.Schema}");
        return specs;
    }
}
```

- [ ] **Step 6: Implement `Matchers.cs`**

```csharp
using System.Globalization;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.CSharp.Syntax;
using ICSharpCode.Decompiler.TypeSystem;

namespace CodeFacts;

internal static class Runner
{
    public static RunResult Run(string assemblyPath, string specsPath)
    {
        var specs = RunResult.LoadSpecs(specsPath);
        var result = new RunResult { Assembly = assemblyPath };
        var decompiler = new CSharpDecompiler(assemblyPath, new DecompilerSettings());

        foreach (var fact in specs.Facts)
        {
            try
            {
                var method = FindMethod(decompiler, fact);
                var values = fact.Matcher switch
                {
                    "guarded_member_roll" => Matchers.GuardedMemberRoll(method, fact),
                    "string_constants" => Matchers.StringConstants(method, fact),
                    "int_comparisons" => Matchers.IntComparisons(method, fact),
                    "statement_shape" => Matchers.StatementShape(method, fact),   // assert (Task 6)
                    "string_set" => Matchers.StringSet(method, fact),             // assert (Task 6)
                    _ => throw new InvalidDataException($"unknown matcher '{fact.Matcher}'"),
                };
                result.Facts.Add(fact.Mode == "assert"
                    ? new FactResult(fact.Id, fact.Mode, null, AssertOk: true)
                    : new FactResult(fact.Id, fact.Mode, values, null));
            }
            catch (Exception ex)
            {
                result.Errors.Add($"{fact.Id}: {ex.Message}");
            }
        }
        return result;
    }

    private static MethodDeclaration FindMethod(CSharpDecompiler decompiler, FactSpec fact)
    {
        SyntaxTree tree = decompiler.DecompileType(new FullTypeName(fact.Type));
        var matches = tree.Descendants.OfType<MethodDeclaration>()
            .Where(m => m.Name == fact.Method).ToList();
        if (matches.Count != 1)
            throw new InvalidDataException(
                $"method {fact.Type}::{fact.Method} bound {matches.Count} times (need exactly 1)");
        return matches[0];
    }
}

internal static class Matchers
{
    /// Binds the unique `if` whose then-branch references args["member"] in an
    /// Add(...) call and whose condition compares a float literal (optionally
    /// `* expr`). Emits rate (literal as invariant string) and min_level
    /// (from a `Level > N` conjunct, else "0").
    public static Dictionary<string, string> GuardedMemberRoll(MethodDeclaration method, FactSpec fact)
    {
        string member = fact.Args["member"];
        var hits = new List<(string Rate, string MinLevel)>();

        foreach (var ifs in method.Descendants.OfType<IfElseStatement>())
        {
            bool addsMember = ifs.TrueStatement.Descendants.OfType<InvocationExpression>().Any(inv =>
                inv.Target is MemberReferenceExpression { MemberName: "Add" }
                && inv.Arguments.Count == 1
                && NodeMentions(inv.Arguments.First(), member));
            if (!addsMember) continue;

            string? rate = ifs.Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                .Where(b => b.Operator == BinaryOperatorType.LessThan)
                .Select(b => FloatLiteralOf(b.Right) ?? FloatLiteralOf(b.Left))
                .FirstOrDefault(v => v is not null);
            if (rate is null) continue;

            string minLevel = ifs.Condition.DescendantsAndSelf.OfType<BinaryOperatorExpression>()
                .Where(b => b.Operator == BinaryOperatorType.GreaterThan
                    && b.Left is MemberReferenceExpression { MemberName: "Level" }
                    && b.Right is PrimitiveExpression { Value: int })
                .Select(b => ((PrimitiveExpression)b.Right).Value!.ToString()!)
                .FirstOrDefault() ?? "0";

            hits.Add((rate, minLevel));
        }

        if (hits.Count != 1)
            throw new InvalidDataException(
                $"guarded_member_roll('{member}') bound {hits.Count} times (need exactly 1)");
        return new() { ["rate"] = hits[0].Rate, ["min_level"] = hits[0].MinLevel };
    }

    /// All distinct string literals used in `==` comparisons in the method,
    /// in source order, joined with ','.
    public static Dictionary<string, string> StringConstants(MethodDeclaration method, FactSpec fact)
    {
        var strings = method.Descendants.OfType<BinaryOperatorExpression>()
            .Where(b => b.Operator == BinaryOperatorType.Equality)
            .SelectMany(b => new[] { b.Left, b.Right })
            .OfType<PrimitiveExpression>()
            .Where(p => p.Value is string)
            .Select(p => (string)p.Value!)
            .Distinct()
            .ToList();
        if (strings.Count == 0)
            throw new InvalidDataException("string_constants bound 0 literals (need >= 1)");
        return new() { ["strings"] = string.Join(",", strings) };
    }

    /// For each args entry "<MemberName>" -> "<key>", finds the unique integer
    /// comparison against that member and emits "<key>" = "<op> <int>".
    public static Dictionary<string, string> IntComparisons(MethodDeclaration method, FactSpec fact)
    {
        var values = new Dictionary<string, string>();
        foreach (var (memberName, key) in fact.Args)
        {
            var cmps = method.Descendants.OfType<BinaryOperatorExpression>()
                .Where(b => (NodeMentions(b.Left, memberName) && b.Right is PrimitiveExpression { Value: int })
                         || (NodeMentions(b.Right, memberName) && b.Left is PrimitiveExpression { Value: int }))
                .Select(b =>
                {
                    var lit = (b.Right as PrimitiveExpression ?? (PrimitiveExpression)b.Left).Value;
                    return $"{OpName(b.Operator)} {lit}";
                })
                .Distinct().ToList();
            if (cmps.Count != 1)
                throw new InvalidDataException(
                    $"int_comparisons('{memberName}') bound {cmps.Count} times (need exactly 1)");
            values[key] = cmps[0];
        }
        return values;
    }

    public static Dictionary<string, string> StatementShape(MethodDeclaration method, FactSpec fact)
        => throw new NotImplementedException("Task 6");

    public static Dictionary<string, string> StringSet(MethodDeclaration method, FactSpec fact)
        => throw new NotImplementedException("Task 6");

    private static bool NodeMentions(AstNode node, string member) =>
        node.DescendantsAndSelf.Any(n =>
            (n is MemberReferenceExpression mre && mre.MemberName == member)
            || (n is IdentifierExpression ide && ide.Identifier == member));

    private static string? FloatLiteralOf(Expression expr) =>
        expr.DescendantsAndSelf.OfType<PrimitiveExpression>()
            .Where(p => p.Value is float or double)
            .Select(p => Convert.ToString(p.Value, CultureInfo.InvariantCulture)!)
            .FirstOrDefault();

    private static string OpName(BinaryOperatorType op) => op switch
    {
        BinaryOperatorType.GreaterThan => ">",
        BinaryOperatorType.GreaterThanOrEqual => ">=",
        BinaryOperatorType.LessThan => "<",
        BinaryOperatorType.LessThanOrEqual => "<=",
        BinaryOperatorType.Equality => "==",
        BinaryOperatorType.InEquality => "!=",
        _ => op.ToString(),
    };
}
```

Remove the temporary `Runner.Run` stub from Task 1. Note: exact AST property names (`TrueStatement`, `DescendantsAndSelf`, `FullTypeName` ctor) must be validated against the pinned decompiler version — fix compile errors against its API, keeping the matcher contracts above intact.

- [ ] **Step 7: Build, run the tests, iterate until green**

Run: `dotnet build src/tools/CodeFacts -c Release && uv run pytest tests/integration/test_code_facts_tool.py -v`
Expected: both tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/tools/CodeFacts tests/integration/test_code_facts_tool.py tests/fixtures/code_facts
git commit -m "feat(export): add extract-mode AST matchers with fixture tests"
```

---

### Task 3: Seed the real fact specs

**Files:**
- Create: `src/tools/CodeFacts/specs/erenshor-facts.json`
- Test: `tests/integration/test_code_facts_real.py`

- [ ] **Step 1: Ground the auction envelope**

Run: `uv run python - <<'EOF'` — or simply read `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/AuctionHouse.cs` starting at line 508 (`UpdateAH`). Identify the exact member names used in the level/value/`SimPlayersCantGet` gates. Record them; they parameterize the `int_comparisons` spec below (adjust member names to what the source actually says — do NOT guess).

- [ ] **Step 2: Write the specs file**

`src/tools/CodeFacts/specs/erenshor-facts.json` — one `guarded_member_roll` fact per pool row in the grounded table above (ids `loot.world_drop.<member_snake_case>`; the masks fact targets member `Masks`; include `Empty2` — it extracts on every variant since the *constant* exists regardless of the `DemoBuild` runtime gate), plus:

```json
{
  "id": "smithing.upgrade_ids",
  "mode": "extract",
  "type": "Smithing",
  "method": "Combine",
  "matcher": "string_constants",
  "args": {},
  "keys": ["strings"]
},
{
  "id": "auction.envelope",
  "mode": "extract",
  "type": "AuctionHouse",
  "method": "UpdateAH",
  "matcher": "int_comparisons",
  "args": { "<LevelMemberFromStep1>": "item_level", "<ValueMemberFromStep1>": "item_value" },
  "keys": ["item_level", "item_value"]
}
```

`CommonWorldItems` does not fit `guarded_member_roll` (it's an inner `Random.Range(0,10) > 8` substitution, not a `< rate` roll) — give it `int_comparisons` on the containing method scoped via `args`, or defer it with a comment in the specs file if it cannot bind exactly-once; deferring is acceptable, silently mis-binding is not.

- [ ] **Step 3: Write the shape-assertion test (values stay golden's job — decision #6)**

`tests/integration/test_code_facts_real.py`:

```python
"""Shape assertions against the real main-variant binary (no exact values)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DLL = REPO_ROOT / "variants" / "main" / "game" / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
SPECS = REPO_ROOT / "src" / "tools" / "CodeFacts" / "specs" / "erenshor-facts.json"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed"),
    pytest.mark.skipif(not DLL.exists(), reason="main variant game files not present"),
]


def test_all_facts_extract_with_sane_shapes() -> None:
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--project",
         str(REPO_ROOT / "src" / "tools" / "CodeFacts"), "--", str(DLL), str(SPECS)],
        capture_output=True, text=True,
    )
    out = json.loads(proc.stdout)
    assert proc.returncode == 0, out.get("errors")

    spec_ids = {f["id"] for f in json.loads(SPECS.read_text())["facts"]}
    got = {f["id"]: f for f in out["facts"]}
    assert set(got) == spec_ids

    for fact in got.values():
        if fact["mode"] != "extract":
            continue
        values = fact["values"]
        if "rate" in values:
            assert 0.0 < float(values["rate"]) <= 1.0, fact["id"]
            assert int(values["min_level"]) >= 0, fact["id"]
        if "strings" in values:
            assert all(s.isdigit() for s in values["strings"].split(",")), fact["id"]
```

- [ ] **Step 4: Run until green**

Run: `uv run pytest tests/integration/test_code_facts_real.py -v`
Expected: PASS. Every binding failure here is a spec bug — fix the spec (e.g. two `0.001` pools both bind? The matcher keys on the *member*, so they must not collide; if one does, the error names it).

- [ ] **Step 5: Commit**

```bash
git add src/tools/CodeFacts/specs tests/integration/test_code_facts_real.py
git commit -m "feat(export): seed loot, auction, and smithing fact specs"
```

---

### Task 4: Python runner + raw-DB writer + CLI

**Files:**
- Create: `src/erenshor/application/code_facts/__init__.py`, `src/erenshor/application/code_facts/runner.py`
- Modify: `src/erenshor/cli/commands/extract.py` (new `code-facts` command in the existing `extract` Typer app)
- Test: `tests/test_code_facts_writer.py` (unit, no dotnet)

- [ ] **Step 1: Write the failing unit test for the raw-table writer**

```python
"""The writer owns the raw `code_facts` tables; tested with a fake tool payload."""

import sqlite3
from pathlib import Path

from erenshor.application.code_facts.runner import write_code_facts

PAYLOAD = {
    "schema": 1,
    "assembly": "/x/Managed/Assembly-CSharp.dll",
    "facts": [
        {"id": "loot.world_drop.maps", "mode": "extract",
         "values": {"rate": "0.0125", "min_level": "0"}, "ok": None},
        {"id": "loot.guarantee_one_drop", "mode": "assert", "values": None, "ok": True},
    ],
    "errors": [],
}


def test_writer_creates_and_replaces_only_its_tables(tmp_path: Path) -> None:
    db = tmp_path / "raw.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE other (x)")  # pre-existing export table must survive

    write_code_facts(db, PAYLOAD, assembly_sha256="abc123")
    write_code_facts(db, PAYLOAD, assembly_sha256="abc123")  # idempotent re-run

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT fact_id, key, value FROM code_facts ORDER BY fact_id, key"
        ).fetchall()
        assert ("loot.world_drop.maps", "min_level", "0") in rows
        assert ("loot.world_drop.maps", "rate", "0.0125") in rows
        assert ("loot.guarantee_one_drop", "ok", "true") in rows
        assert conn.execute("SELECT assembly_sha256 FROM code_facts_meta").fetchone()[0] == "abc123"
        assert conn.execute("SELECT count(*) FROM other").fetchone() is not None
```

Run: `uv run pytest tests/test_code_facts_writer.py -v` → FAIL (module missing).

- [ ] **Step 2: Implement `runner.py`**

```python
"""Run the CodeFacts analyzer and persist results into the raw database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

TOOL_PROJECT = Path("src/tools/CodeFacts")


def run_tool(repo_root: Path, assembly: Path) -> dict:
    """Invoke the analyzer; raise on any failure (fail fast, no fallbacks)."""
    if not assembly.exists():
        raise FileNotFoundError(f"shipped game assembly not found: {assembly}")
    specs = repo_root / TOOL_PROJECT / "specs" / "erenshor-facts.json"
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--project", str(repo_root / TOOL_PROJECT),
         "--", str(assembly), str(specs)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        payload = proc.stdout.strip()
        raise RuntimeError(
            f"CodeFacts analyzer failed (exit {proc.returncode}).\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"output: {payload}\n"
            "A binding failure means the game code changed shape: re-derive the "
            "affected fact spec (see .agent/skills/code-facts/SKILL.md)."
        )
    return json.loads(proc.stdout)


def write_code_facts(raw_db_path: Path, payload: dict, assembly_sha256: str) -> int:
    rows: list[tuple[str, str, str, str]] = []
    for fact in payload["facts"]:
        if fact["mode"] == "extract":
            for key, value in fact["values"].items():
                rows.append((fact["id"], key, value, "text"))
        else:
            rows.append((fact["id"], "ok", "true" if fact["ok"] else "false", "bool"))

    with sqlite3.connect(raw_db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS code_facts")
        conn.execute("DROP TABLE IF EXISTS code_facts_meta")
        conn.execute(
            "CREATE TABLE code_facts ("
            "fact_id TEXT NOT NULL, key TEXT NOT NULL, "
            "value TEXT NOT NULL, value_type TEXT NOT NULL, "
            "PRIMARY KEY (fact_id, key))"
        )
        conn.execute(
            "CREATE TABLE code_facts_meta ("
            "assembly_sha256 TEXT NOT NULL, extracted_at TEXT NOT NULL)"
        )
        conn.executemany("INSERT INTO code_facts VALUES (?, ?, ?, ?)", rows)
        conn.execute(
            "INSERT INTO code_facts_meta VALUES (?, ?)",
            (assembly_sha256, datetime.now(timezone.utc).isoformat()),
        )
    logger.info(f"code_facts written: {len(rows)} rows")
    return len(rows)


def extract_code_facts(repo_root: Path, assembly: Path, raw_db_path: Path) -> int:
    payload = run_tool(repo_root, assembly)
    sha = hashlib.sha256(assembly.read_bytes()).hexdigest()
    return write_code_facts(raw_db_path, payload, assembly_sha256=sha)
```

Run: `uv run pytest tests/test_code_facts_writer.py -v` → PASS.

- [ ] **Step 3: Add the CLI command**

In `src/erenshor/cli/commands/extract.py`, following the file's existing command style (cli_ctx, dry-run; see neighboring commands):

```python
@app.command("code-facts")
def code_facts(ctx: typer.Context) -> None:
    """Extract hardcoded game constants from the shipped assembly into the raw DB."""
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    assembly = (
        variant_config.resolved_game_files(cli_ctx.repo_root)
        / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
    )
    raw_db_path = variant_config.resolved_database_raw(cli_ctx.repo_root)
    if cli_ctx.dry_run:
        logger.info(f"[Dry-run] Would extract code facts: assembly={assembly}, raw_db={raw_db_path}")
        return
    if not raw_db_path.exists():
        raise typer.Exit(_fail(f"Raw DB missing ({raw_db_path}). Run 'erenshor extract export' first."))
    count = extract_code_facts(cli_ctx.repo_root, assembly, raw_db_path)
    logger.info(f"Extracted {count} code-fact rows. Run 'erenshor extract build' next.")
```

(Adapt the error/exit helper to whatever `extract.py` actually uses — mirror its neighbors, do not invent a new pattern.)

- [ ] **Step 4: Verify end-to-end**

Run: `uv run erenshor extract code-facts && sqlite3 variants/main/erenshor-main-raw.sqlite "SELECT * FROM code_facts ORDER BY fact_id, key"`
Expected: one row per fact/key; rates as decimal strings.

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/application/code_facts tests/test_code_facts_writer.py src/erenshor/cli/commands/extract.py
git commit -m "feat(pipeline): write code facts to the raw database"
```

---

### Task 5: Processor passthrough + ordering gate + skill update

**Files:**
- Create: `src/erenshor/application/processor/code_facts.py`
- Modify: `src/erenshor/application/processor/build.py`
- Modify: `.agent/skills/refreshing-game-data/SKILL.md` (**stage selectively — file has unrelated local edits**)

- [ ] **Step 1: Implement the processor (fail loud on missing tables — ordering gate)**

```python
"""Carry code_facts from raw to clean. The table's absence means the
extract step was skipped; that is an ordering error, not a soft case."""

from __future__ import annotations

import sqlite3

from loguru import logger


def process_code_facts(raw: sqlite3.Connection, writer) -> None:
    try:
        rows = raw.execute(
            "SELECT fact_id, key, value, value_type FROM code_facts"
        ).fetchall()
        meta = raw.execute(
            "SELECT assembly_sha256, extracted_at FROM code_facts_meta"
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError(
            "code_facts tables missing from raw DB. Run "
            "'erenshor extract code-facts' after 'erenshor extract export'."
        ) from exc
    # Mirror the writer-usage pattern of process_zones in entities.py
    # (same create-table + executemany flow through the shared Writer).
    ...
    logger.info(f"code_facts: {len(rows)} rows (assembly {meta['assembly_sha256'][:12]})")
```

The `...` is the table-create + insert through `Writer` — copy the exact idiom from `process_zones` in `application/processor/entities.py` (read it first; it is the canonical minimal processor). Schema: `code_facts(fact_id TEXT, key TEXT, value TEXT, value_type TEXT, PRIMARY KEY(fact_id, key))` plus `code_facts_meta` passthrough.

- [ ] **Step 2: Register in `build.py`** — import `process_code_facts`, call it first (step 0, no dependencies), and update the module docstring's processing-order list.

- [ ] **Step 3: Verify + golden**

Run: `uv run erenshor extract build && uv run erenshor golden capture`
Expected: build succeeds; golden diff shows exactly the new `code_facts` tables — review it; nothing else may change.

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 4: Update `refreshing-game-data` skill** — insert the step `erenshor extract code-facts` between `extract export` and `extract build` in the documented order, with one sentence: "Fails loudly if hardcoded game logic changed shape; see code-facts skill." Stage **only these hunks** (`git add -p .agent/skills/refreshing-game-data/SKILL.md`).

- [ ] **Step 5: Commit**

```bash
git add src/erenshor/application/processor/code_facts.py src/erenshor/application/processor/build.py
git add -p .agent/skills/refreshing-game-data/SKILL.md
git commit -m "feat(pipeline): carry code facts into the clean database"
```

---

### Task 6: Assert-mode structural invariants

**Files:**
- Modify: `src/tools/CodeFacts/Matchers.cs` (implement `StatementShape`, `StringSet`), `src/tools/CodeFacts/specs/erenshor-facts.json`
- Modify: `src/tools/CodeFacts/tests/FixtureLib/FixtureLoot.cs`, `tests/fixtures/code_facts/fixture-specs.json`, `tests/integration/test_code_facts_tool.py`

- [ ] **Step 1: Ground the trigger-display method** — search `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/ItemInfoWindow.cs` for the proc-trigger strings (the block found during Phase 3a review: shield→bash / Bracer→cast / else→attack wording). Record the exact method name and the exact string literal set.

- [ ] **Step 2: Failing tests first** — add to the fixture a `GuaranteeLike()` method containing exactly one `Drops.Add(PoolA[Rng.Next(0, PoolA.Count)])` statement, and fixture specs:

```json
{
  "id": "fixture.guarantee_shape",
  "mode": "assert",
  "type": "FixtureLib.FixtureLoot",
  "method": "GuaranteeLike",
  "matcher": "statement_shape",
  "args": { "statement": "Drops.Add(PoolA[Rng.Next(0, PoolA.Count)]);" }
},
{
  "id": "fixture.trigger_strings",
  "mode": "assert",
  "type": "FixtureLib.FixtureLoot",
  "method": "Combine",
  "matcher": "string_set",
  "args": { "strings": "31377423,46289586" }
}
```

Test additions: passing case asserts `ok: true`; a violating spec (statement that does not exist / extra string in the set) must exit 1 with the fact id in `errors`. Run → FAIL (`NotImplementedException`).

- [ ] **Step 3: Implement the two matchers**

```csharp
/// Asserts the method contains EXACTLY ONE statement whose normalized text
/// equals args["statement"]. One statement, not a body snapshot: stable under
/// the pinned decompiler, immune to neighboring edits.
public static Dictionary<string, string> StatementShape(MethodDeclaration method, FactSpec fact)
{
    string wanted = Normalize(fact.Args["statement"]);
    int count = method.Descendants.OfType<ExpressionStatement>()
        .Count(s => Normalize(s.ToString()) == wanted);
    if (count != 1)
        throw new InvalidDataException($"statement_shape bound {count} times (need exactly 1): {fact.Args["statement"]}");
    return new();
}

/// Asserts the method's ==-compared string literal set equals args["strings"] exactly.
public static Dictionary<string, string> StringSet(MethodDeclaration method, FactSpec fact)
{
    var expected = fact.Args["strings"].Split(',').ToHashSet();
    var actual = StringConstants(method, fact)["strings"].Split(',').ToHashSet();
    if (!expected.SetEquals(actual))
        throw new InvalidDataException(
            $"string_set mismatch: expected [{string.Join(",", expected)}], got [{string.Join(",", actual)}]");
    return new();
}

private static string Normalize(string s) =>
    string.Join(" ", s.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
```

- [ ] **Step 4: Add the real assert specs** — `loot.guarantee_one_drop` (`statement_shape` on `LootTable::InitLootTable` with the actual decompiled statement text — copy it verbatim from `LootTable.cs:52-197`'s guarantee block) and `iteminfo.proc_trigger_strings` (`string_set` with the literal set from Step 1). Note in the specs file why each exists: which pipeline/Lua code re-implements the semantics (`Drops` builder; `Item.lua` trigger table).

- [ ] **Step 5: Green + real run + commit**

Run: `uv run pytest tests/integration/test_code_facts_tool.py tests/integration/test_code_facts_real.py -v` → PASS.

```bash
git add src/tools/CodeFacts tests/fixtures/code_facts tests/integration/test_code_facts_tool.py
git commit -m "feat(export): assert structural invariants for re-implemented semantics"
```

---

### Task 7: Coverage cross-check

**Files:**
- Test: `tests/test_code_facts_coverage.py`

- [ ] **Step 1: Establish the reference convention** — any Python/Lua constant or rule derived from hardcoded game logic carries a `# code-fact: <id>` (Python) / `-- code-fact: <id>` (Lua) comment naming its spec id.

- [ ] **Step 2: Write the test**

```python
"""Every code-fact reference in the codebase must name a real spec id,
and every assert-mode spec must be referenced by at least one consumer."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS = REPO_ROOT / "src" / "tools" / "CodeFacts" / "specs" / "erenshor-facts.json"
REF = re.compile(r"(?:#|--)\s*code-fact:\s*([a-z0-9_.]+)")
SCAN_ROOTS = ["src/erenshor", "wiki/modules"]


def _references() -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for root in SCAN_ROOTS:
        for path in (REPO_ROOT / root).rglob("*"):
            if path.suffix not in {".py", ".lua"}:
                continue
            for m in REF.finditer(path.read_text(errors="ignore")):
                refs.setdefault(m.group(1), []).append(str(path.relative_to(REPO_ROOT)))
    return refs


def test_all_references_resolve_and_asserts_are_consumed() -> None:
    spec_ids = {f["id"]: f["mode"] for f in json.loads(SPECS.read_text())["facts"]}
    refs = _references()
    unknown = set(refs) - set(spec_ids)
    assert not unknown, f"code-fact comments referencing unknown spec ids: {unknown}"
    unconsumed_asserts = {
        i for i, mode in spec_ids.items() if mode == "assert" and i not in refs
    }
    assert not unconsumed_asserts, (
        f"assert specs with no consumer reference: {unconsumed_asserts} "
        "(tag the re-implementing code with a code-fact comment)"
    )
```

- [ ] **Step 3: Tag the two existing consumers** — the `Drops` builder code that relies on `IsGuaranteed` semantics (`# code-fact: loot.guarantee_one_drop`) and the `Item.lua` trigger table (`-- code-fact: iteminfo.proc_trigger_strings`).

- [ ] **Step 4: Run, commit**

Run: `uv run pytest tests/test_code_facts_coverage.py -v` → PASS.

```bash
git add tests/test_code_facts_coverage.py src/erenshor wiki/modules
git commit -m "test(pipeline): cross-check code-fact coverage"
```

---

### Task 8: Discovery layer + skills + docs

**Files:**
- Create: `.agent/skills/code-facts/SKILL.md` (read superpowers `writing-skills` first)
- Modify: `AGENTS.md` (Essential Commands), `.agent/skills/refreshing-game-data/SKILL.md` (discovery-diff step; selective staging again)

- [ ] **Step 1: Initialize the discovery repo** (one-time, lives inside the gitignored variant dir — zero main-repo churn):

```bash
cd variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp
git init && git add -A && git commit -m "game build $(date +%Y-%m-%d)"
```

Document in the refresh skill: after each re-rip, `git add -A && git commit -m "game build <version>"`, then review `git diff HEAD~1 --stat` for churn outside known fact targets — that's how *new* mechanics are discovered (this is exactly how the Level>30 `CrystallizedBalance`/`Planar` drops were found).

- [ ] **Step 2: Write `.agent/skills/code-facts/SKILL.md`** covering: what extract/assert modes are; the specs file as single registry; the `code-fact:` comment convention; what to do when `extract code-facts` fails (read the named spec, read the new game code, re-derive, update spec + consumers in one commit); decompiler-upgrade policy (standalone commit, never with a game update); the shipped-DLL-only rule.

- [ ] **Step 3: Add to `AGENTS.md` Essential Commands**: `uv run erenshor extract code-facts  # Shipped DLL -> raw code_facts (run between export and build)`

- [ ] **Step 4: Commit**

```bash
git add .agent/skills/code-facts AGENTS.md
git add -p .agent/skills/refreshing-game-data/SKILL.md
git commit -m "docs(pipeline): document code-facts workflow and discovery layer"
```

---

## Out of scope (explicitly)

- **Consumer cutover** (wiki Phase 3 consuming `code_facts` for `IsAuctionable`, world-drop pool display, `UsedIn` upgrade rows) — happens in the wiki-cargo Phase 3 plan, gated on its own spec review (`docs/plans/2026-06-04-wiki-cargo-data-architecture.md`).
- **playtest/demo seeding** — the command works per-variant; asserts/specs are validated against `main` only for now.
- **Opcode/basic-block analysis** — rejected during design; AST exact-once binding is the chosen granularity.

## Verification (final gate)

```bash
uv run pytest                          # all, including the new integration tests
uv run erenshor extract code-facts
uv run erenshor extract build
uv run erenshor golden capture        # review: only code_facts tables appear
```
