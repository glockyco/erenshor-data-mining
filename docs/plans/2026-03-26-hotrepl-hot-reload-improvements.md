# HotRepl Hot Reload Improvements

## Problem

After F6 (ScriptEngine hot reload), HotRepl's Mono evaluator references ALL
loaded assemblies — including stale versions from previous reloads. Type
resolution picks the first-loaded assembly, causing:

1. **Stale type resolution**: `AdventureGuide.Diagnostics.DebugAPI` resolves to
   the first (oldest) assembly whose static fields were cleared by OnDestroy
2. **Cryptic cross-assembly errors**: "Field _state defined on type X is not a
   field on the target object which is of type X" — two types with identical
   names from different assemblies
3. **Unhelpful error messages**: `(1,1): InteractiveHost` with no context about
   what failed or why

## Root Cause

ScriptEngine renames assemblies with a timestamp suffix
(`MyMod-{DateTime.Now.Ticks}`) on each reload. Mono cannot unload assemblies,
so all versions accumulate in the AppDomain. HotRepl's evaluator references all
of them, and Mono.CSharp resolves types from the first-referenced (oldest)
version.

## Commit Plan

### Commit 1: Auto-reset evaluator on ScriptEngine reload (HotRepl)

**File**: `src/HotRepl.Core/Evaluator/MonoCSharpEvaluator.cs`

Detect ScriptEngine-style assembly loads in `OnAssemblyLoad`. When an assembly
name matches `{base}-{ticks}` and an older `{base}-{olderTicks}` was already
referenced, trigger an evaluator reset. The reset rebuilds the session from
scratch, and during `CreateSession`, `TryReference` filters out superseded
assemblies.

Detection heuristic: regex `^(.+)-(\d{17,19})$` where ticks >
630000000000000000 (~year 2000).

**File**: `src/HotRepl.Core/Evaluator/AssemblyFilter.cs`

Add `IsSuperseded(name, allAssemblies)` method. When multiple assemblies share
the same ScriptEngine base name, only the one with the highest ticks value
passes the filter. All older versions are filtered out.

**Result**: After F6, the evaluator auto-resets. Types resolve to the newest
assembly. REPL variable state is lost (acceptable — hot reload is a code change,
not a data continuation).

### Commit 2: Broadcast assembly reload notification to clients (HotRepl)

**File**: `src/HotRepl.Core/Protocol/Messages.cs`

Add `AssemblyReloadMessage` (type: `assembly_reload`) with fields:
`assemblyName` (base name), `oldVersion` (previous ticks), `newVersion` (new
ticks).

**File**: `src/HotRepl.Core/ReplEngine.cs`

After the auto-reset completes, broadcast the reload notification to all
connected clients. This lets the client display a user-friendly message.

**File**: `client/src/hotrepl/_client.py`

Handle the `assembly_reload` event in the subscribe handler. Log an informational
message like "Assembly 'AdventureGuide' reloaded — REPL state cleared."

**Result**: Users see a clear notification when hot reload resets the REPL,
instead of wondering why variables disappeared.

### Commit 3: Improve error messages for cross-assembly type mismatches (HotRepl)

**File**: `src/HotRepl.Core/Evaluator/MonoCSharpEvaluator.cs` or
`src/HotRepl.Core/ReplEngine.cs`

In `SendEvalOutcome`, detect common cross-assembly error patterns in runtime
errors:
- "is not a field on the target object" → append: "This may be caused by stale
  assembly references after hot reload. Try: `eval reset`"
- "InvalidCastException" with same type name → same suggestion

This is a runtime error enrichment layer, not a compile-time one. Pattern match
on `ex.Message` and append actionable guidance.

**Result**: Instead of a cryptic .NET reflection error, users see a clear
suggestion.

### Commit 4: Improve compile error formatting in Python client (HotRepl)

**File**: `client/src/hotrepl/cli.py`

Catch `EvalError` in `_cmd_eval` and format it cleanly:
- Compile errors: show the error message without the Python traceback
- Runtime errors: show message + relevant stack trace lines (filter out Mono
  internals)
- All errors: use stderr, not exception propagation

The current behavior shows a full Python traceback for every eval error, which
buries the actual compiler message.

**Result**: Clean, readable error output without Python noise.

### Commit 5: Revert DebugAPI to simple static fields (Erenshor)

**Files**:
- `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs`
- `src/mods/AdventureGuide/src/Plugin.cs`

With HotRepl handling assembly deduplication (Commit 1), DebugAPI no longer
needs cross-assembly workarounds. Revert to simple static properties set by
Plugin. Remove the reflection-based FindPlugin, cross-assembly WireDebugAPI,
and all the caching machinery.

The DebugAPI becomes what it was originally: a simple static API that Plugin
wires up, and HotRepl resolves to the correct (newest) assembly.

**Result**: Clean, maintainable DebugAPI without reflection hacks.

### Commit 6: Update skill documentation (Both repos)

**File (Erenshor)**: `.agent/skills/runtime-eval/SKILL.md`

Update the "ScriptEngine Cross-Assembly Gotchas" section:
- Note that HotRepl auto-resets on ScriptEngine reload
- Remove the warning about `FindObjectsOfType<T>()` returning empty (fixed)
- Update DebugAPI section (no longer needs cross-assembly workarounds)
- Keep the reflection pattern documented as fallback for edge cases

**File (HotRepl)**: `AGENTS.md` or a new skill

Document the ScriptEngine integration:
- How the assembly deduplication works
- The auto-reset behavior and its implications (REPL state loss)
- The `assembly_reload` protocol message

**Result**: Documentation matches the new behavior.

## Dependencies

Commits 1-4 are in the HotRepl repo. Commit 5 is in Erenshor. Commit 6 spans
both. Commits 1 and 3-4 are independent. Commit 2 depends on 1. Commit 5
depends on 1. Commit 6 depends on all others.

Commits 3 and 4 can be done in parallel with commit 1.

## Alternatives Considered

**Cross-assembly field wiring from Plugin**: Plugin uses reflection to set
DebugAPI statics on all loaded assemblies. Works but is fragile — every mod
needs to implement this pattern, and it breaks if field names change.

**DebugAPI self-resolving via FindPlugin**: DebugAPI reflects into Plugin to
find data. Doesn't work because DebugAPI itself is on the wrong assembly.

**Separate DebugAPI assembly**: Put DebugAPI in a non-hot-reloaded assembly.
Adds build complexity for a problem better solved at the HotRepl level.

All three are workarounds for the real problem (HotRepl resolving stale types),
which Commit 1 fixes at the source.
