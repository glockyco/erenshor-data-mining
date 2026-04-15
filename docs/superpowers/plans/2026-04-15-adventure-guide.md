# Adventure Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix correctness issues, close performance gaps, and align marker/navigation behavior with the spec in the quest-frontier-architecture worktree.

**Architecture:** The compiled guide architecture is structurally in place (24 commits). This plan fixes what's broken: O(n) lookups that should be O(1), incorrect marker behavior for non-kill targets, wrong priority ordering, a silent correctness bug in item resolution, and missing test coverage. Export pipeline changes are explicitly out of scope.

**Tech Stack:** C# (.NET), BepInEx, Harmony, xUnit

**Worktree:** `/Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture`

**Spec:** `docs/superpowers/specs/2026-04-14-adventure-guide-design.md`

**Out of scope:**
- Export pipeline changes (Phase 3 of spec roadmap)
- Python compiler changes (unless needed for C# compatibility)
- New features not in the spec (Phase 4)

---

## File Map

### Files to modify

| File | Change |
|---|---|
| `src/Markers/MarkerPool.cs` | Swap TurnInPending/QuestGiverBlocked enum order |
| `src/Markers/CharacterMarkerPolicy.cs` | Non-kill targets: suppress active marker when dead |
| `src/Markers/MarkerComputer.cs` | Emit respawn timers for non-kill targets |
| `src/Markers/MarkerSystem.cs` | Handle dead→alive transitions for non-kill targets |
| `src/Resolution/SourceResolver.cs` | Use CompiledGuide lookups; fix item-not-found bug |
| `src/Resolution/NavigationTargetResolver.cs` | Use CompiledGuide lookups |
| `src/Resolution/TrackerSummaryResolver.cs` | Use CompiledGuide lookups |
| `src/Resolution/UnlockPredicateEvaluator.cs` | Use CompiledGuide lookups |
| `src/Plan/EffectiveFrontier.cs` | Use CompiledGuide lookups |
| `src/Resolution/TrackerSummaryBuilder.cs` | Fix item-not-found text |

All paths are relative to `src/mods/AdventureGuide/`.

### Test files to modify

| File | Change |
|---|---|
| `tests/.../CharacterMarkerPolicyTests.cs` | Update non-kill tests for new dead behavior |
| `tests/.../SourceResolverTests.cs` | Add item-not-found regression test |
| `tests/.../MarkerChangePlannerTests.cs` | Add non-kill respawn timer test |

All test paths are relative to `src/mods/AdventureGuide/`.

---

## Task 1: Replace O(n) linear lookups with CompiledGuide O(1) methods

Every resolver reimplements `FindQuestIndex()` and `FindItemIndex()` as O(n) linear scans over `guide.Nodes`. `CompiledGuide` already exposes `FindQuestIndex(int nodeId)` and `FindItemIndex(int nodeId)` using dictionary lookups. This is a systematic fix across 5 files.

**Files:**
- Modify: `src/Resolution/SourceResolver.cs`
- Modify: `src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/Resolution/TrackerSummaryResolver.cs`
- Modify: `src/Resolution/UnlockPredicateEvaluator.cs`
- Modify: `src/Plan/EffectiveFrontier.cs`

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

For each file, delete the private `FindQuestIndex`/`FindItemIndex` methods and replace all call sites with `_guide.FindQuestIndex(nodeId)` and `_guide.FindItemIndex(nodeId)`.

The `CompiledGuide` methods (verified at lines 425-430 of CompiledGuide.cs) use `_nodeIdToQuestIndex` and `_nodeIdToItemIndex` dictionaries and return `-1` for missing keys -- same contract as the local methods.

- [ ] **Step 3: Build and run existing tests**

Run: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/`
Expected: All existing tests pass. This is a pure refactor with identical behavior.

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

## Task 2: Fix SourceResolver item-not-found correctness bug

When a required item's `nodeId` is not in the guide (`FindItemIndex` returns -1), `SourceResolver` skips it with `continue` without setting `emittedObjective = true`. If ALL required items are missing from the guide and no step edges exist, the resolver falls through to emit turn-in targets, making the quest appear completable when it is not.

**Files:**
- Modify: `src/Resolution/SourceResolver.cs`
- Modify: `src/Resolution/TrackerSummaryBuilder.cs`
- Test: `tests/.../SourceResolverTests.cs`

- [ ] **Step 1: Write a failing test**

Add a test to `SourceResolverTests.cs` that creates a quest with a required item whose nodeId does not exist in the guide's item index. Verify the resolver does NOT emit turn-in targets.

```csharp
[Fact]
public void RequiredItem_NotInGuide_DoesNotEmitTurnIn()
{
    // Build a guide where quest requires item node 999, but 999 is not indexed as an item
    var builder = new CompiledGuideBuilder()
        .AddQuest("quest:test", "Test Quest")
        .AddItem("item:real", "Real Item");
    // Add a RequiresItem edge to a non-existent item node
    // ... (use builder to create the scenario)

    var harness = SnapshotHarness.FromBuilder(builder);
    // Set quest as active
    // Resolve and assert no turn-in targets emitted
}
```

The exact builder API calls depend on `CompiledGuideBuilder`'s fluent interface -- read the file to get the exact method signatures.

- [ ] **Step 2: Run the test to verify it fails**

Run: `dotnet test --filter RequiredItem_NotInGuide_DoesNotEmitTurnIn`
Expected: FAIL (currently emits turn-in when it shouldn't)

- [ ] **Step 3: Fix SourceResolver**

In `SourceResolver.cs`, when `itemIndex < 0` (item not in guide), set `emittedObjective = true` before continuing. This prevents the fallthrough to turn-in emission. The item is a real requirement that cannot be satisfied -- the quest is not ready for turn-in.

```csharp
if (itemIndex < 0)
{
    emittedObjective = true; // Unknown item is still a requirement
    continue;
}
```

- [ ] **Step 4: Fix TrackerSummaryBuilder**

In `TrackerSummaryBuilder.cs`, when `itemIndex < 0`, emit text like "Collect [Unknown Item] (0/N)" rather than silently showing wrong progress. Read the file to find the exact location -- the agent report says lines 40-45.

- [ ] **Step 5: Run the test to verify it passes**

Run: `dotnet test --filter RequiredItem_NotInGuide`
Expected: PASS

- [ ] **Step 6: Commit**

```
fix(mod): prevent false turn-in when required items are missing from guide

When a quest's RequiresItem edge references a node not indexed as an item
in the compiled guide, SourceResolver skipped it without marking that an
objective was emitted. This allowed the resolver to fall through to turn-in
emission, making the quest appear completable when it has unsatisfied
requirements.

Set emittedObjective=true for missing items so the turn-in fallthrough
is blocked. Also fix TrackerSummaryBuilder to show unknown items rather
than silently producing wrong progress text.
```

---

## Task 3: Swap TurnInPending and QuestGiverBlocked priority

The spec defines priority order: TurnInReady > TurnInRepeatReady > Objective > QuestGiver > QuestGiverRepeat > TurnInPending > QuestGiverBlocked. The current enum has QuestGiverBlocked(5) above TurnInPending(6). The spec wants TurnInPending above QuestGiverBlocked because TurnInPending is at least attached to an active quest, while QuestGiverBlocked is entirely non-actionable.

**Files:**
- Modify: `src/Markers/MarkerPool.cs`

- [ ] **Step 1: Swap the enum values**

In `MarkerPool.cs`, swap the enum member order:

Before:
```csharp
QuestGiverBlocked,   // star grey — prerequisites not met
TurnInPending,       // circle-question grey — quest active, missing items
```

After:
```csharp
TurnInPending,       // circle-question grey — quest active, missing items
QuestGiverBlocked,   // star grey — prerequisites not met
```

- [ ] **Step 2: Search for any code that uses integer values of these enum members**

`grep -rn 'MarkerType\.' src/mods/AdventureGuide/src/` -- verify no code compares these by integer value or persists them. The priority system uses enum ordering (lower = higher priority), so swapping the declaration order is the complete fix.

- [ ] **Step 3: Build and run tests**

Run: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/`
Expected: All tests pass. If any test hardcodes priority expectations, update them.

- [ ] **Step 4: Commit**

```
fix(mod): demote QuestGiverBlocked below TurnInPending in marker priority

TurnInPending represents an active quest's turn-in NPC where the player
has not yet collected all items. QuestGiverBlocked is a quest the player
cannot start yet. TurnInPending is more actionable (the player is working
toward it) and should win when both markers compete for the same NPC.

Swap enum declaration order so TurnInPending(5) outranks
QuestGiverBlocked(6).
```

---

## Task 4: Add respawn markers for non-kill character targets

Per spec section 8.3: all character targets (kill AND non-kill) show respawn timer markers when the NPC is dead. Non-kill targets differ from kill targets only in that corpse loot checks don't apply. Currently, `CreateRespawnTimerEntry` returns null for non-kill targets and `CharacterMarkerPolicy` always emits active markers for non-kill targets regardless of alive/dead state.

**Files:**
- Modify: `src/Markers/CharacterMarkerPolicy.cs`
- Modify: `src/Markers/MarkerComputer.cs`
- Modify: `src/Markers/MarkerSystem.cs`
- Test: `tests/.../CharacterMarkerPolicyTests.cs`
- Test: `tests/.../MarkerChangePlannerTests.cs`

### Sub-task 4a: Update CharacterMarkerPolicy

- [ ] **Step 1: Update tests for new non-kill behavior**

In `CharacterMarkerPolicyTests.cs`, the existing test `NonKillCharacterTarget_StillEmitsActiveMarkerWhenNonActionable` currently asserts `true` (marker shown when dead). Update it to assert `false` -- non-kill targets should NOT emit active markers when non-actionable (dead), matching kill target behavior.

Add a new test:
```csharp
[Fact]
public void NonKillTarget_Alive_EmitsActiveMarker()
{
    // Non-kill target, NPC alive → active marker shown
    var target = MakeTarget(ResolvedActionKind.Talk, isActionable: true);
    Assert.True(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
}

[Fact]
public void NonKillTarget_Dead_DoesNotEmitActiveMarker()
{
    // Non-kill target, NPC dead → no active marker (respawn timer instead)
    var target = MakeTarget(ResolvedActionKind.Talk, isActionable: false);
    Assert.False(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: `NonKillTarget_Dead_DoesNotEmitActiveMarker` fails because current policy returns `true` for non-kill non-actionable targets.

- [ ] **Step 3: Update CharacterMarkerPolicy**

Change `ShouldEmitActiveMarker` to suppress active markers for ALL non-actionable character targets, not just kill targets:

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

`ShouldKeepQuestMarkerOnCorpse` stays kill-only (corpse loot is only relevant for kill targets).

- [ ] **Step 4: Run tests to verify they pass**

Run: `dotnet test --filter CharacterMarkerPolicy`
Expected: PASS

- [ ] **Step 5: Commit**

```
fix(mod): suppress active markers for dead non-kill character targets

Non-kill character targets (talk, give) previously showed their active
quest marker regardless of whether the NPC was alive or dead. This was
inconsistent with the player's experience: you cannot talk to a dead NPC.

All character targets now suppress the active quest marker when the NPC
is non-actionable. The respawn timer marker (added in the next commit)
replaces it, giving the player useful information about when the NPC
will be available again.
```

### Sub-task 4b: Emit respawn timers for non-kill targets

- [ ] **Step 6: Update MarkerComputer.CreateRespawnTimerEntry**

Remove the early return that suppresses respawn timers for non-kill targets. The method currently has:

```csharp
if (target.Semantic.ActionKind != ResolvedActionKind.Kill)
    return null;
```

Remove this check. Respawn timer markers apply to ALL character targets. The rest of the method (checking spawn state, formatting timer text) applies equally to non-kill targets.

Read the method carefully to verify no kill-specific logic exists below the guard that would break for non-kill targets (e.g., corpse-specific text). If there is kill-specific text formatting, condition it on `ActionKind == Kill` rather than returning null.

- [ ] **Step 7: Update MarkerSystem.UpdateSpawnState**

Read `MarkerSystem.cs` around lines 175-210 to understand the per-frame alive↔dead transition logic. Currently non-kill targets are handled differently (quest marker stays on death). Update the logic so non-kill targets also transition to respawn timer display when dead, matching kill target behavior.

The key difference: non-kill targets do NOT set `KeepWhileCorpsePresent` (there's no lootable corpse to track). When the NPC dies, the marker transitions directly to respawn timer.

- [ ] **Step 8: Add test for non-kill respawn timer emission**

Add a test to `MarkerChangePlannerTests.cs` (or the most appropriate test file -- read it first) that verifies a Talk-semantic character target at a dead spawn point produces a `DeadSpawn` marker entry.

- [ ] **Step 9: Run all marker tests**

Run: `dotnet test --filter "Marker"`
Expected: All pass

- [ ] **Step 10: Commit**

```
fix(mod): emit respawn timer markers for non-kill character targets

Talk and give targets previously showed no respawn information when their
NPC was dead. The player had no way to know when a quest-giver or
talk-objective NPC would respawn.

Remove the kill-only guard from CreateRespawnTimerEntry so all character
targets get respawn timer markers when dead. Update MarkerSystem per-frame
transitions to handle non-kill dead→alive the same way as kill targets.
Non-kill targets skip corpse loot handling (KeepWhileCorpsePresent stays
kill-only) since there is no lootable corpse for talk/give semantics.
```

---

## Task 5: Build verification and final test pass

- [ ] **Step 1: Run the full test suite**

Run: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/`
Expected: All tests pass

- [ ] **Step 2: Build the mod**

Run: `cd /Users/joaichberger/Projects/Erenshor && uv run erenshor mod build --mod adventure-guide`
Expected: Build succeeds with no errors

- [ ] **Step 3: Review all changes**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Verify: 4 new commits, no unintended changes, all file modifications are intentional.

---

## Summary

| Task | Type | What |
|---|---|---|
| 1 | Performance | O(n) → O(1) index lookups across 5 resolvers |
| 2 | Correctness | SourceResolver item-not-found bug → false turn-in |
| 3 | Spec alignment | TurnInPending/QuestGiverBlocked priority swap |
| 4 | Spec alignment | Non-kill character respawn markers |
| 5 | Verification | Full build + test pass |
