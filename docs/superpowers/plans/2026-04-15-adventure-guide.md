# Adventure Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Adventure Guide mod implementation by fixing correctness issues, closing performance gaps, implementing missing features, and adding diagnostics -- all per the spec at `docs/superpowers/specs/2026-04-14-adventure-guide-design.md`.

**Architecture:** The compiled guide architecture is structurally in place (24 commits on the `quest-frontier-architecture` worktree). This plan fixes what's broken and implements what's missing. The worktree code compiles and does not crash but has widespread correctness issues that must be verified against the spec's acceptance criteria.

**Tech Stack:** C# (.NET), BepInEx, Harmony, xUnit, Python (guide compiler)

**Worktree:** `/Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture`

**Out of scope:**
- Export pipeline changes (C# Unity export scripts in `src/Assets/Editor/`). Scripted quest gating (ShiverEvent, ReliquaryFiend, etc.) is either manually defined via graph overrides or deferred.

---

## Phase A: Performance & Correctness Foundations

### Task 1: Replace O(n) linear lookups with CompiledGuide O(1) methods

Every resolver reimplements `FindQuestIndex()` and `FindItemIndex()` as O(n) linear scans over `guide.Nodes`. `CompiledGuide` already exposes `FindQuestIndex(int nodeId)` and `FindItemIndex(int nodeId)` using dictionary lookups at lines 425-430 of `CompiledGuide.cs`. This is a systematic fix across 5 files.

**Files:**
- Modify: `src/Resolution/SourceResolver.cs`
- Modify: `src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/Resolution/TrackerSummaryResolver.cs`
- Modify: `src/Resolution/UnlockPredicateEvaluator.cs`
- Modify: `src/Plan/EffectiveFrontier.cs`

All paths relative to `src/mods/AdventureGuide/`.

- [ ] **Step 1: Read each file, identify the local FindItemIndex/FindQuestIndex methods**

Each file contains a private method like:
```csharp
private int FindQuestIndex(int nodeId)
{
    for (int i = 0; i < _guide.QuestNodeIds.Length; i++)
        if (_guide.QuestNodeIds[i] == nodeId) return i;
    return -1;
}
```

Verify the exact method names and signatures in each file before editing.

- [ ] **Step 2: In each file, replace the private lookup methods with calls to CompiledGuide**

Delete the private `FindQuestIndex`/`FindItemIndex` methods and replace all call sites with `_guide.FindQuestIndex(nodeId)` and `_guide.FindItemIndex(nodeId)`. Same contract (returns -1 for missing keys).

- [ ] **Step 3: Build and run existing tests**

Run: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/`
Expected: All existing tests pass. Pure refactor with identical behavior.

- [ ] **Step 4: Commit**

```
refactor(mod): replace O(n) index lookups with CompiledGuide O(1) methods

Five resolvers reimplemented FindQuestIndex/FindItemIndex as linear scans
over guide.Nodes and guide.QuestNodeIds. CompiledGuide already provides
dictionary-backed O(1) versions of these lookups. This matters because
these methods are called per-quest during resolution, and some quests
have deep transitive dependency chains.
```

---

### Task 2: Fix SourceResolver item-not-found correctness bug

When a required item's `nodeId` is not in the guide (`FindItemIndex` returns -1), `SourceResolver` skips it with `continue` without setting `emittedObjective = true`. If ALL required items are missing and no step edges exist, the resolver falls through to emit turn-in targets, making the quest appear completable.

**Files:**
- Modify: `src/Resolution/SourceResolver.cs`
- Modify: `src/Resolution/TrackerSummaryBuilder.cs`
- Test: `tests/.../SourceResolverTests.cs`

- [ ] **Step 1: Write a failing test in SourceResolverTests.cs**

Create a quest with a required item whose nodeId does not exist in the guide's item index. Verify the resolver does NOT emit turn-in targets. Read `CompiledGuideBuilder.cs` for the exact fluent API to construct the scenario.

- [ ] **Step 2: Run the test to verify it fails**

- [ ] **Step 3: Fix SourceResolver**

When `itemIndex < 0`, set `emittedObjective = true` before continuing:

```csharp
if (itemIndex < 0)
{
    emittedObjective = true; // Unknown item is still a requirement
    continue;
}
```

- [ ] **Step 4: Fix TrackerSummaryBuilder**

When `itemIndex < 0`, emit text like "Collect [Unknown Item] (0/N)" rather than silently showing wrong progress. Read the file around lines 40-45 for the exact location.

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```
fix(mod): prevent false turn-in when required items are missing from guide

When a quest's RequiresItem edge references a node not indexed as an item
in the compiled guide, SourceResolver skipped it without marking that an
objective was emitted. This caused fallthrough to turn-in emission.

Set emittedObjective=true for missing items. Fix TrackerSummaryBuilder
to show unknown items rather than producing wrong progress text.
```

---

## Phase B: Marker Correctness

### Task 3: Add respawn markers for non-kill character targets

Per spec section 8.3: all character targets (kill AND non-kill) show respawn timer markers when dead. Currently, `CreateRespawnTimerEntry` returns null for non-kill targets and `CharacterMarkerPolicy.ShouldEmitActiveMarker` always returns true for non-kill non-actionable targets.

**Files:**
- Modify: `src/Markers/CharacterMarkerPolicy.cs`
- Modify: `src/Markers/MarkerComputer.cs`
- Modify: `src/Markers/MarkerSystem.cs`
- Test: `tests/.../CharacterMarkerPolicyTests.cs`

- [ ] **Step 1: Update CharacterMarkerPolicy tests**

Update `NonKillCharacterTarget_StillEmitsActiveMarkerWhenNonActionable` to assert `false` -- non-kill targets should NOT emit active markers when dead. Add:

```csharp
[Fact]
public void NonKillTarget_Alive_EmitsActiveMarker()
{
    var target = MakeTarget(ResolvedActionKind.Talk, isActionable: true);
    Assert.True(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
}

[Fact]
public void NonKillTarget_Dead_DoesNotEmitActiveMarker()
{
    var target = MakeTarget(ResolvedActionKind.Talk, isActionable: false);
    Assert.False(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
}
```

- [ ] **Step 2: Run tests, verify they fail**

- [ ] **Step 3: Update CharacterMarkerPolicy.ShouldEmitActiveMarker**

All non-actionable character targets suppress active markers:

```csharp
public static bool ShouldEmitActiveMarker(ResolvedQuestTarget target)
{
    if (target.TargetNode.Node.Type != NodeType.Character)
        return true;
    return target.IsActionable;
}
```

And the overload:
```csharp
public static bool ShouldEmitActiveMarker(ResolvedTarget target)
{
    return target.IsActionable;
}
```

`ShouldKeepQuestMarkerOnCorpse` stays kill-only.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Remove kill-only guard from MarkerComputer.CreateRespawnTimerEntry**

The method has `if (target.Semantic.ActionKind != ResolvedActionKind.Kill) return null;`. Remove this check. Read the rest of the method to verify no kill-specific logic below would break for non-kill targets. If there is kill-specific text formatting (e.g., corpse-related text), condition it on ActionKind rather than returning null for the whole method.

- [ ] **Step 6: Update MarkerSystem.UpdateSpawnState**

Read MarkerSystem.cs around lines 175-210. Update the per-frame alive↔dead transition logic so non-kill targets also transition to respawn timer display when dead. Non-kill targets do NOT set `KeepWhileCorpsePresent`.

- [ ] **Step 7: Add test for non-kill respawn timer emission**

Add a test verifying a Talk-semantic character target at a dead spawn produces a `DeadSpawn` marker entry. Use the most appropriate test file (read `MarkerChangePlannerTests.cs` first).

- [ ] **Step 8: Run all marker tests, verify pass**

- [ ] **Step 9: Commit**

```
fix(mod): emit respawn timer markers for non-kill character targets

Talk and give targets previously showed no respawn information when their
NPC was dead. Remove the kill-only guard from CreateRespawnTimerEntry.
Update CharacterMarkerPolicy to suppress active markers for ALL dead
character targets. Update MarkerSystem per-frame transitions accordingly.
Non-kill targets skip corpse loot handling (KeepWhileCorpsePresent stays
kill-only).
```

---

## Phase C: Missing Features

### Task 4: Implement non-quest entity navigation

Per spec sections 6.1 and 7: the NAV set can hold any navigable node key (characters, items, mining nodes), not just quests. `NavigationTargetResolver.Resolve()` currently returns empty for all non-quest keys with the comment "Non-quest keys are intentionally unsupported after the clean-cut runtime migration."

**Files:**
- Modify: `src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/Resolution/SourceResolver.cs` (if needed for non-quest target materialization)
- Test: `tests/.../NavigationTargetResolverTests.cs`

- [ ] **Step 1: Read NavigationTargetResolverTests.cs for existing patterns**

Understand how tests create guide fixtures and call Resolve().

- [ ] **Step 2: Write failing test for non-quest navigation**

Test that navigating to a character key (e.g., `character:bandit`) resolves to targets using the source index and position resolvers. The spec says: "it builds a single-node plan, resolves positions directly from the source index and position resolvers, and returns targets without frontier computation."

- [ ] **Step 3: Run test, verify failure**

- [ ] **Step 4: Implement non-quest resolution path**

In `NavigationTargetResolver.Resolve()`, when the node key is not a quest:
1. Look up the node in the compiled guide
2. For character/item/mining nodes: resolve positions from the source index (item sources for items, spawn points for characters)
3. Build `ResolvedQuestTarget` objects with appropriate semantics (no frontier, no quest context)
4. Return the targets

The exact approach depends on the node type. Characters need spawn point resolution. Items need source site resolution. Mining nodes need direct position resolution.

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```
feat(mod): support non-quest entity navigation

NavigationTargetResolver now resolves character, item, and mining node
keys in addition to quests. Non-quest entities skip frontier computation
and resolve positions directly from the source index and position
resolvers, per spec section 6.1.
```

---

### Task 5: Add tracker sub-quest context

Per spec section 10.3: when a tracked quest's frontier resolves to a prerequisite quest's target, the tracker should show "Needed for: [Quest Name]". `FrontierEntry` already carries `RequiredForQuestIndex` but `TrackerSummaryBuilder` ignores it.

**Files:**
- Modify: `src/Resolution/TrackerSummaryBuilder.cs`
- Modify: `src/Resolution/TrackerSummary.cs` (if it lacks a field for context text)
- Test: `tests/.../TrackerSummaryBuilderTests.cs`

- [ ] **Step 1: Read TrackerSummaryBuilder.cs and TrackerSummary.cs**

Understand the current output format and where `RequiredForQuestIndex` is available but unused.

- [ ] **Step 2: Write failing test**

Create a scenario where quest A requires quest B as a prerequisite. Track quest A. Verify the tracker summary includes context text like "Needed for: Quest A Name".

- [ ] **Step 3: Run test, verify failure**

- [ ] **Step 4: Implement sub-quest context**

When `FrontierEntry.RequiredForQuestIndex >= 0`, add a `RequiredForQuestName` field (or similar) to the `TrackerSummary` output. Look up the quest name from the compiled guide using the index.

- [ ] **Step 5: Update TrackerPanel rendering**

Read `TrackerPanel.cs` to find where tracker summaries are rendered. Add rendering of the sub-quest context text (e.g., smaller/dimmer text below the objective line).

- [ ] **Step 6: Run tests, verify pass**

- [ ] **Step 7: Commit**

```
feat(mod): show sub-quest context in tracker overlay

When a tracked quest's frontier resolves through a prerequisite chain,
the tracker now shows "Needed for: [Quest Name]" below the objective
summary. FrontierEntry already carried RequiredForQuestIndex; this commit
wires it through TrackerSummaryBuilder to the tracker panel rendering.
```

---

## Phase D: Diagnostics

### Task 6: Remove reflection from DebugAPI

Per spec section 12.3: compile-time safe debug API, no reflection. `DebugAPI.DumpZoneRouterAdj()` and `ExportStateSnapshot()` use `BindingFlags` / `GetField`.

**Files:**
- Modify: `src/Diagnostics/DebugAPI.cs`
- Modify: affected components to expose debug state via typed properties

- [ ] **Step 1: Read DebugAPI.cs, identify all reflection usage**

Find every `GetField`, `BindingFlags`, `GetType().GetField()` call. Note what data each reflection call accesses.

- [ ] **Step 2: Add typed debug properties to the accessed components**

For each field accessed via reflection, add a public read-only property or method to the owning class. For example, if `DumpZoneRouterAdj` accesses `ZoneRouter._adjacency` via reflection, add `public IReadOnlyDictionary<string, ...> DebugAdjacency => _adjacency;` to `ZoneRouter`.

- [ ] **Step 3: Replace reflection in DebugAPI with typed access**

Replace `GetField("_adjacency", BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(router)` with `router.DebugAdjacency`.

- [ ] **Step 4: Build and run tests**

- [ ] **Step 5: Commit**

```
refactor(mod): replace reflection with typed debug properties in DebugAPI

DumpZoneRouterAdj and ExportStateSnapshot accessed internal state via
reflection. Add explicit debug properties to ZoneRouter and the affected
components, then use typed access in DebugAPI. No runtime behavior change.
```

---

### Task 7: Implement IResolutionTracer (resolution trace)

Per spec section 12.1: structured trace capturing every decision in the resolution pipeline. The pipeline accepts an optional `IResolutionTracer` that receives callbacks at each decision point. Normal operation passes null (zero overhead).

**Files:**
- Create: `src/Resolution/IResolutionTracer.cs`
- Modify: `src/Resolution/SourceResolver.cs`
- Modify: `src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/Plan/EffectiveFrontier.cs`
- Modify: `src/Resolution/UnlockPredicateEvaluator.cs`
- Modify: `src/Diagnostics/DebugAPI.cs`

- [ ] **Step 1: Define IResolutionTracer interface**

```csharp
namespace AdventureGuide.Resolution;

/// <summary>
/// Receives callbacks during resolution for diagnostic tracing.
/// Normal operation passes null (zero overhead via null checks).
/// </summary>
public interface IResolutionTracer
{
    void OnQuestPhase(int questIndex, string dbName, QuestPhase phase);
    void OnFrontierEntry(FrontierEntry entry, string questDbName);
    void OnTargetMaterialized(string targetKey, string sourceKey, bool isActionable, bool isBlocked);
    void OnHostileDropFilter(string itemKey, int hostileCount, int suppressedCount);
    void OnUnlockEvaluation(int nodeId, string nodeKey, bool isUnlocked);
    void OnBestTarget(string targetKey, int tier, float distance);
}
```

- [ ] **Step 2: Thread tracer through resolvers**

Add an optional `IResolutionTracer tracer = null` parameter to the resolution entry points. At each decision point, call the tracer method behind a null check:

```csharp
tracer?.OnQuestPhase(questIndex, dbName, phase);
```

This ensures zero overhead when tracing is not active.

- [ ] **Step 3: Implement a concrete TextResolutionTracer**

A simple implementation that builds a formatted string (like the spec's example output). Add a `TraceQuest(string questDbName)` method to `DebugAPI` that creates a tracer, runs resolution with it, and returns the formatted output.

- [ ] **Step 4: Write test verifying tracer receives callbacks**

Create a test that passes a mock tracer to resolution and verifies callbacks are received in the expected order.

- [ ] **Step 5: Commit**

```
feat(mod): implement IResolutionTracer for resolution pipeline diagnostics

Add optional tracer interface threaded through SourceResolver,
NavigationTargetResolver, EffectiveFrontier, and UnlockPredicateEvaluator.
Normal operation passes null (zero overhead via null checks). Add
TextResolutionTracer and DebugAPI.TraceQuest() for HotRepl diagnostics.
```

---

### Task 8: Implement diagnostic overlay

Per spec section 12.2: toggleable in-game overlay (hidden by default) showing status bar, marker tooltip, and quest debug section.

**Files:**
- Create: `src/UI/DiagnosticOverlay.cs`
- Modify: `src/Markers/MarkerSystem.cs` (marker tooltip on hover)
- Modify: `src/Config/GuideConfig.cs` (add config toggle)
- Modify: `src/Plugin.cs` (wire overlay)

- [ ] **Step 1: Add DiagnosticOverlay config toggle**

Add `DiagnosticOverlay` bool config entry (default false, hidden) to `GuideConfig.cs`.

- [ ] **Step 2: Implement DiagnosticOverlay.cs**

ImGui overlay rendering:
- **Status bar:** "AG: {activeCount} active, {markerCount} markers, {navCount} NAV targets, last event {elapsed}s ago, {frameMs}ms"
- Data sourced from existing components: `QuestPhaseTracker` for active count, `MarkerSystem` for marker count, `NavigationSet` for nav count, `GuideProfiler` for timing.

- [ ] **Step 3: Implement marker tooltip**

When diagnostic overlay is enabled and modifier key (e.g., Alt) is held while hovering near a marker, show tooltip with: source key, contributing quests, priority resolution, character occupancy state. Read `MarkerComputer` to find how to expose contribution data.

- [ ] **Step 4: Wire into Plugin.cs**

Instantiate `DiagnosticOverlay` in `Plugin.Awake()`, render in `Plugin.Update()` when enabled.

- [ ] **Step 5: Commit**

```
feat(mod): add diagnostic overlay for in-game debugging

Toggleable overlay (hidden by default) showing active quest count,
marker count, NAV target count, last event timing, and frame cost.
Marker tooltip shows source key, contributing quests, and character
state when modifier key held during hover.
```

---

## Phase E: Verification

### Task 9: Full build verification and acceptance test pass

- [ ] **Step 1: Run the full C# test suite**

Run: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/`
Expected: All tests pass

- [ ] **Step 2: Run the full Python test suite**

Run: `uv run pytest tests/unit/application/guide/ tests/integration/test_entity_graph.py -v`
Expected: All tests pass

- [ ] **Step 3: Build the mod**

Run: `cd /Users/joaichberger/Projects/Erenshor && uv run erenshor mod build --mod adventure-guide`
Expected: Build succeeds

- [ ] **Step 4: Review all changes**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Verify: all changes are intentional, no unintended modifications.

- [ ] **Step 5: Walk the spec acceptance criteria**

For each section of the spec (2-12), verify each numbered acceptance criterion is satisfied by the implementation. Note any remaining gaps as bd issues.

---

## Summary

| Phase | Task | Type | What |
|---|---|---|---|
| A | 1 | Performance | O(n) → O(1) index lookups across 5 resolvers |
| A | 2 | Correctness | SourceResolver item-not-found → false turn-in |
| B | 3 | Spec alignment | Non-kill character respawn markers |
| C | 4 | Feature | Non-quest entity navigation (characters, items, mining) |
| C | 5 | Feature | Tracker sub-quest context ("Needed for: X") |
| D | 6 | Refactor | Remove reflection from DebugAPI |
| D | 7 | Feature | IResolutionTracer for resolution diagnostics |
| D | 8 | Feature | Diagnostic overlay (status bar, marker tooltip) |
| E | 9 | Verification | Full build + test + spec acceptance walk |
