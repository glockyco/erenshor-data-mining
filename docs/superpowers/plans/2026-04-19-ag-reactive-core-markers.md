# AdventureGuide Reactive Core — Markers, Planner, Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Group 1 of the Adventure Guide reactive-core overhaul by projecting markers through the engine, deleting the planner, making `Plugin.Update` a five-phase orchestrator, and applying a focused naming-discipline sweep to every class this plan touches. After this plan, every acceptance criterion in spec § 9 is satisfied.

**Architecture:** `MarkerCandidates(scene)` becomes an engine query that composes `NavigableQuests()` + `QuestResolution(questKey, scene)` + `SourceState` facts into an immutable, value-equal candidate list. The class currently named `MarkerComputer` is renamed to `MarkerProjector`, stripped of `_dirty`/`_fullRebuild`/`_pendingQuestKeys`/`MarkDirty`/`ApplyChangeSet`/`Recompute`, and reduced to a per-frame live-state overlay between the engine's candidate list and the rendering layer. `MarkerSystem` is renamed to `MarkerRenderer` to join the existing `*Renderer` family. `MaintainedViewPlanner` and `MaintainedViewPlan` are deleted — their role (deciding when `NavigationTargetSelector` must do a forced rebuild) collapses into a reference-equality check on the engine-returned `NavigableQuestSet`. `Plugin.Update` fans out into five named methods, each wrapped in a diagnostics span. Namespaces are consolidated: `AdventureGuide.Plan` is renamed to `AdventureGuide.Frontier` (pure frontier-computation code after planner deletion), and `NavigationSet` moves from the old `AdventureGuide.Frontier` to `AdventureGuide.Navigation` where it belongs.

**Spec:** `docs/superpowers/specs/2026-04-19-ag-reactive-core-design.md` §§ 4.5, 5, 6, 9.

**Prior plan:** `docs/superpowers/plans/2026-04-19-ag-reactive-core-foundation.md` — Plan A; landed in `1076b957`. Plan B depends on its queries (`CompiledTargets`, `BlockingZones`, `NavigableQuests`, `QuestResolution`), the `Engine<FactKey>` instance in `Plugin`, `GuideReader`, and the ambient `ReadContext`.

**Tech Stack:** C# 10, .NET Framework 4.7.2 (BepInEx), xUnit, Unity 2021.3.45f2.

---

## Scope Contract

**In scope for this plan:**
- `MarkerCandidates(scene)` query in `AdventureGuide.Markers.Queries`
- `MarkerCandidate` immutable value-equal record + `MarkerCandidateList` wrapper
- `MarkerComputer` → `MarkerProjector` rename
- `MarkerSystem` → `MarkerRenderer` rename (joins `ArrowRenderer`/`GroundPathRenderer`/`ImGuiRenderer`/`ViewRenderer` family)
- `MarkerProjector.Update()` → `Project()`; `MarkerRenderer.Update()` → `Render()` (method names match class roles)
- Delete `MarkerQuestTargetResolver` (orphaned after `MarkerComputer` deletion)
- `MarkerProjector` loses all dirty/pending/mark-dirty/apply-change-set machinery
- `MaintainedViewPlanner` / `MaintainedViewPlan` / `MaintainedViewRefreshKind` deleted
- `NavigableQuestsResult` → `NavigableQuestSet` (Plan A residue; "Result" is ceremony)
- `NavigationTargetSelector.Version` deleted; `force` decision derived from `NavigableQuestSet` reference-equality plus live-world change
- `MarkerRenderer._lastConfiguredVersion` deleted; reconfiguration triggered by `MarkerCandidateList` reference-equality
- `Plugin.Update` refactored into `Capture` / `Publish` / `Invalidate` / `Consume` / `Render` methods, each with a diagnostics span
- Namespace consolidation: `AdventureGuide.Plan/*` → `AdventureGuide.Frontier/*`; `Frontier/NavigationSet.cs` → `Navigation/NavigationSet.cs` (`AdventureGuide.Navigation`)
- `MarkerRebuildMode`, `MarkerRebuildModeSample`, marker-side `QuestCostSample` usage deleted with the diagnostics-snapshot shape change
- `DiagnosticOverlay` migrated to the new shape
- `SubsystemSnapshots.MarkerDiagnosticsSnapshot` simplified to what the new pipeline actually reports

**Out of scope:**
- Groups 2-4 of the broader overhaul (tracker summarisation, spec-tree projector, navigation resolver refactor)
- `TrackerState`/`NavigationSet` fact-emission gap (separate bd issue; documented in Plan A handoff and re-flagged as R3 blocker below)
- Renaming `TrackerState`, `NavigationSet`, `QuestStateTracker`, `LiveStateTracker`, `QuestPhaseTracker` — consistent internal naming, not touched here
- Any in-game behavioural change — this is a pure architecture refactor, observable output unchanged

**Per-task acceptance gate:**
- Test suite stays green (`dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo`)
- Mod builds clean (`dotnet build src/mods/AdventureGuide/AdventureGuide.csproj -v quiet -nologo`)
- Each commit is atomic (one design decision per commit)
- No backwards-compat shims, no parallel implementations, no rename aliases

---

## Load-Bearing Design Decisions

These decisions shape the plan. They are not negotiable inside the plan; they can only change by rewriting the plan.

### D1. MarkerCandidates dependency shape

`MarkerCandidates(scene)` depends on:
- `NavigableQuests()` result (via `ctx.Read` — record as query dep)
- `QuestResolution(questKey, scene)` for every quest key it materialises (via `ctx.Read`)
- `SourceState(sourceNodeKey)` fact for every scene-local source node it considers (ambient-recorded via `GuideReader.ReadSourceCategory` — see D6)
- `Scene("current")` fact (ambient-recorded via `GuideReader.ReadCurrentScene`)
- `QuestActive` / `QuestCompleted` for quest-giver fallback paths (ambient-recorded)

The candidate list is a `MarkerCandidateList` wrapping `IReadOnlyList<MarkerCandidate>` with value equality via `SequenceEqual` + element value equality. A recompute that produces the same list backdates — zero ripple to `MarkerRenderer`.

### D2. What lives in `MarkerCandidate` vs what `MarkerRenderer` reads at render time

**In `MarkerCandidate` (engine-cached, scene-level, immutable, value-equal):**
- `QuestKey`, `TargetNodeKey`, `PositionNodeKey`, `SourceNodeKey`
- `QuestKind` (typed as existing `QuestMarkerKind` — quest-semantic, not render-visual)
- `SpawnCategory` (new enum — derived from `SourceState` fact: `Alive` / `Dead` / `Disabled` / `UnlockBlocked` / `NightLocked` / `NotApplicable`)
- `Priority`, `SubText` (base values; renderer may override timer/text)
- `Scene`, `StaticPosition` (Vector3)
- `KeepWhileCorpsePresent`, `CorpseSubText` (constants from the quest, not live)
- `IsNightSpawnNode` (static property of the SpawnPoint)
- `IsSpawnTimerSlot` (boolean — "this marker exists only while spawn is dead")
- `DisplayName`
- `UnlockBlockedReason` (string?, non-null only when `SpawnCategory == UnlockBlocked`)

**Computed per frame by `MarkerRenderer` (live):**
- `MarkerType` — the final visual type, derived from `(QuestKind, SpawnCategory, current time-of-day, live NPC alive/dead, mining state, bag state)`
- Respawn timer seconds (`FormatTimer(RespawnSeconds)` text)
- Live NPC position tracking (reads `entry.LiveSpawnPoint.SpawnedNPC.transform`)
- Current time-of-day for night-locked subtext
- Distance to player → alpha fade
- Mining node `MyRender.enabled` transitions
- ItemBag "picked up" → ZoneReentry transition
- Character aliveness inside `KeepWhileCorpsePresent` window

Net effect: `MarkerCandidates` changes only when quest state, inventory, scene, or categorical spawn state changes. Per-frame timer text and position updates never invalidate the cache.

**Enum reuse:** `QuestMarkerKind` (existing, in `AdventureGuide.Resolution`) stays as-is and is what `MarkerCandidate.QuestKind` carries. `MarkerType` (existing, in `AdventureGuide.Markers`) stays as-is and is what `MarkerRenderer` produces per frame. No new "MarkerCandidateKind" enum is introduced — the two existing enums already cover both axes.

### D3. `GuideReader` vs `ctx.Read` inside query computes

`GuideReader.ReadQuestResolution` forwards to `_engine.Read`, which does **not** record a query dep in the ambient `ReadContext`. That's fine for top-level consumers but wrong for queries-composing-queries.

`MarkerCandidatesQuery.Compute` therefore takes `NavigableQuestsQuery` and `QuestResolutionQuery` as constructor deps and calls `ctx.Read(_navigableQuestsQuery.Query, Unit.Value)` / `ctx.Read(_questResolutionQuery.Query, (questKey, scene))` directly. `GuideReader` is only used for fact-carrying reads (`ReadSourceCategory`, `ReadCurrentScene`, `ReadQuestActive`, `ReadQuestCompleted`), which ambient-record correctly.

This reveals a latent asymmetry in `GuideReader`: it ambient-records facts but silently drops query deps. Task 1 documents the asymmetry with an XML doc comment on `GuideReader.ReadQuestResolution` stating it is for top-level consumers only. Fixing the asymmetry properly — e.g. by detecting ambient context and routing through `ctx.Read` automatically — is a separate concern and belongs with Plan A follow-up, not here.

### D4. `NavigationTargetSelector` force trigger after planner deletion

The planner decides today: "did `navSet` version bump / scene change / target-source version bump / live world change ⇒ force full rebuild." With the engine, all of this folds into one check: **did the `NavigableQuestSet` reference change since last tick?**

- Scene changes invalidate `NavigableQuests` (depends on `Scene("current")` transitively through `QuestActive` reads).
- NavSet or TrackerState changes invalidate `NavigableQuests` via `FactKey(QuestActive, "*")` — same wildcard shortcut Plan A uses.
- Target-source version bumps become immaterial, because `QuestResolution(questKey, scene)` is what the selector reads now, and its cache is engine-managed.

The selector keeps a reference to the last `NavigableQuestSet` it consumed. Per tick: read fresh result through `GuideReader.ReadNavigableQuests` (new top-level helper). If `ReferenceEquals(last, fresh)` ⇒ rescore-only. Otherwise ⇒ forced rebuild. The "live world changed" signal feeds in through the same path: live-state changes emit `SourceState` facts, which invalidate the composed `NavigableQuests` / `QuestResolution` chain, which bumps the reference.

The one exception: mining-node / item-bag availability updates that currently use `preserveUntouchedEntries=true` to avoid wiping unrelated cached entries. Task 3 replaces this with a simpler rule — the selector's per-key `_entries` cache persists across non-forced ticks; any forced rebuild flushes the whole thing. Partial preservation was a performance hack around the planner's coarse signals; the engine's per-entry freshness makes it redundant.

### D5. Five-phase orchestrator boundary definition

Each phase is a method on `Plugin` with a diagnostics span bracketing its body. Ordering is total: phase N cannot start until phase N-1 returns.

1. **Capture** — `_liveState.UpdateFrameState()`, `_questTracker.OnSceneChanged(...)` when scene differs. No engine interaction. Returns the composed `ChangeSet` for this frame.
2. **Publish** — `_engine.InvalidateFacts(changeSet.ChangedFacts)`. The "publish" verb names the outbound data flow from tracker representations into the engine's fact-revision map.
3. **Invalidate** — empty body in Plan B, because step 2 already invalidated. Reserved as a named phase for Group 2+ work that may need to invalidate engine entries based on signals the trackers don't emit as facts. Plan B leaves this method body empty with a comment explaining its reservation.

   **Alternative considered and rejected:** collapse Capture+Publish+Invalidate into two phases. Rejected because spec § 5.1 is explicit about five phases and the rename-and-slot structure pays off in Group 2 (tracker summarisation) where Invalidate gets actual content.

4. **Consume** — every consumer that needs data reads it: `_targetSelector.Tick(...)`, `_navEngine.Update(playerPos)`, `_groundPath.Update()`, `_markerProjector.Project()`, `_markerRenderer.Render()`, the tracker panel, the guide window. Engine reads happen here; everything is lazy, so an engine read only recomputes if the consumer's query deps are stale.
5. **Render** — UI-only concerns that don't touch state: input handling (toggle keys). The ImGui layout callback runs under `OnGUI` (separate Unity entry point), not under Render phase.

`Plugin.Update` becomes a five-line driver: `var change = CapturePhase(); PublishPhase(change); InvalidatePhase(change); ConsumePhase(); RenderPhase();`.

### D6. Naming sweep (summary — details per task)

The spec's § 6 naming discipline is re-applied to every class this plan touches. The new rules from § 6:
- Prefix `Guide*` only when simple name collides with non-mod types.
- Suffix preference: role nouns (`Engine`, `Query`, `Reader`, `Context`, `Resolver`, `Tracker`, `Projector`, `Renderer`, `Builder`). One-off suffixes (`Service`, `Computer`, `Planner`, `System`) not extended.
- Query-return types are noun phrases; `*Result` is not a pattern.

Renames in Plan B:
- `MarkerComputer` → `MarkerProjector` (spec §6)
- `MarkerSystem` → `MarkerRenderer` (spec §6; joins existing `*Renderer` family)
- `MaintainedViewPlanner`/`MaintainedViewPlan`/`MaintainedViewRefreshKind` deleted (spec §6, Q5)
- `NavigableQuestsResult` → `NavigableQuestSet` (Plan A residue)
- `MarkerProjector.Update()` → `Project()`
- `MarkerRenderer.Update()` → `Render()`
- `MarkerRebuildMode`, `MarkerRebuildModeSample` deleted (dead concept after projector simplification)

Directory/namespace consolidation:
- `src/Plan/EffectiveFrontier.cs`, `FrontierEntry.cs`, `QuestPhaseTracker.cs` → `src/Frontier/` (after `MaintainedView*` deletion). Namespace `AdventureGuide.Plan` → `AdventureGuide.Frontier`.
- `src/Frontier/NavigationSet.cs` → `src/Navigation/NavigationSet.cs`. Namespace `AdventureGuide.Frontier` → `AdventureGuide.Navigation`.
- The old `AdventureGuide.Frontier` (holding `NavigationSet`) ceases to exist; the new `AdventureGuide.Frontier` (holding frontier-computation classes) takes its place. This is a single atomic move; callers' `using` statements may break either way during the move, so it's one commit.

Deliberately out of scope in this naming pass: `TrackerState`, `NavigationSet` (moved but not renamed), `QuestStateTracker`, `LiveStateTracker`, `QuestPhaseTracker`, `QuestTargetResolver`, `NavigationTargetResolver`, `SourceResolver` — these are consistent internally, not touched by this plan's behavioural changes.

---

## File Structure

**New files:**
- `src/mods/AdventureGuide/src/Markers/Queries/MarkerCandidatesQuery.cs`
- `src/mods/AdventureGuide/src/Markers/MarkerCandidate.cs`
- `src/mods/AdventureGuide/src/Markers/MarkerCandidateList.cs` (wrapper for engine value-equality)
- `src/mods/AdventureGuide/src/Markers/SpawnCategory.cs` (new enum for SourceState-derived category)
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Markers/MarkerCandidatesQueryTests.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Markers/MarkerCandidateTests.cs`

**Renamed (file + symbol):**
- `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs` → `MarkerProjector.cs` (class `MarkerComputer` → `MarkerProjector`)
- `src/mods/AdventureGuide/src/Markers/MarkerSystem.cs` → `MarkerRenderer.cs` (class `MarkerSystem` → `MarkerRenderer`)
- `src/mods/AdventureGuide/src/Navigation/Queries/NavigableQuestsQuery.cs` — internal type `NavigableQuestsResult` → `NavigableQuestSet` (filename stays)

**Moved (directory/namespace):**
- `src/mods/AdventureGuide/src/Plan/EffectiveFrontier.cs` → `src/Frontier/EffectiveFrontier.cs`
- `src/mods/AdventureGuide/src/Plan/FrontierEntry.cs` → `src/Frontier/FrontierEntry.cs`
- `src/mods/AdventureGuide/src/Plan/QuestPhaseTracker.cs` → `src/Frontier/QuestPhaseTracker.cs`
- `src/mods/AdventureGuide/src/Frontier/NavigationSet.cs` → `src/Navigation/NavigationSet.cs`

**Modified (behavioural):**
- `src/mods/AdventureGuide/src/Markers/MarkerProjector.cs` — gutted and rebuilt as an engine-reader; method is now `Project()`
- `src/mods/AdventureGuide/src/Markers/MarkerRenderer.cs` — reads candidates, drops `_lastConfiguredVersion`, overlays live state; method is now `Render()`
- `src/mods/AdventureGuide/src/Markers/MarkerEntry.cs` — fields redundant with `MarkerCandidate` drop; holds a reference to the candidate plus per-frame-mutable state
- `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs` — drops `Version`, accepts a `NavigableQuestSet` reference instead of a plan
- `src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs` — loses its `Func<int>` target-source version dependency
- `src/mods/AdventureGuide/src/Plugin.cs` — five-phase orchestrator refactor; deletes `MaintainedViewPlanner.Plan` call; deletes scene-change branch in `OnSceneLoaded` that reached into `_markerComputer`
- `src/mods/AdventureGuide/src/UI/DiagnosticOverlay.cs` — switches to `MarkerProjector`
- `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs` — `Markers` property retyped to `MarkerProjector?`
- `src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs` — `MarkerDiagnosticsSnapshot` shape updated
- `src/mods/AdventureGuide/src/State/GuideReader.cs` — add `ReadSourceCategory(Node)`, `ReadNavigableQuests()`, and a non-recording `CurrentScene` property
- `src/mods/AdventureGuide/src/State/LiveStateTracker.cs` — expose `ISourceStateFactSource` if `SourceCategory` reads need a narrow interface (decision in Task 1)
- Every file that had `using AdventureGuide.Plan;` or `using AdventureGuide.Frontier;` — namespace imports update (LSP rename)
- Test files covering `MarkerComputer`, `MaintainedViewPlanner`, `MaintainedViewPlan`, `MarkerQuestTargetResolver`, `MarkerSystem` — rewritten, renamed, or deleted

**Deleted:**
- `src/mods/AdventureGuide/src/Plan/MaintainedViewPlanner.cs`
- `src/mods/AdventureGuide/src/Plan/MaintainedViewPlan.cs` (and the `MaintainedViewRefreshKind` enum inside)
- `src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs` (orphaned)
- `MarkerRebuildMode`, `MarkerRebuildModeSample` types (inline in whatever file defines them; grep during Task 2)
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs` (paired with the deletion)
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewPlannerTests.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs` (or rewritten; decision per Task 3)
- The now-empty `src/mods/AdventureGuide/src/Plan/` directory (after move)

---

### Task 1: `MarkerCandidates` query definition

**Goal:** Introduce `MarkerCandidate`, `MarkerCandidateList`, `SpawnCategory`, and `MarkerCandidatesQuery` with full test coverage. No consumer cutover yet — `MarkerComputer` still drives rendering. This task establishes the query, its semantics, its fact-dep shape, and the enum reuse discipline (`QuestMarkerKind` + new `SpawnCategory`; no new overlapping enum).

**Files:**
- Create: `src/mods/AdventureGuide/src/Markers/MarkerCandidate.cs`
- Create: `src/mods/AdventureGuide/src/Markers/MarkerCandidateList.cs`
- Create: `src/mods/AdventureGuide/src/Markers/SpawnCategory.cs`
- Create: `src/mods/AdventureGuide/src/Markers/Queries/MarkerCandidatesQuery.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Markers/MarkerCandidateTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Markers/MarkerCandidatesQueryTests.cs`
- Modify: `src/mods/AdventureGuide/src/State/GuideReader.cs` — add `ReadSourceCategory(Node)` and `ReadNavigableQuests()`; add non-recording `CurrentScene` property; document `ReadQuestResolution` as top-level-only
- Modify: `src/mods/AdventureGuide/src/State/LiveStateTracker.cs` or introduce an `ISourceStateFactSource` interface — whichever preserves the narrow-interface discipline

- [ ] **Step 1.1: Define `SpawnCategory`**

```csharp
namespace AdventureGuide.Markers;

/// <summary>Category derived from the SourceState fact for a source node.
/// Describes the node's availability at the moment the query ran. Renderer
/// composes this with QuestMarkerKind and live per-frame state to produce
/// the final MarkerType.</summary>
public enum SpawnCategory
{
	/// <summary>Source has no spawn semantics (e.g. item bag, mining node,
	/// character with no SpawnPoint). Renderer handles those paths directly.</summary>
	NotApplicable,
	Alive,
	Dead,
	Disabled,
	UnlockBlocked,
	NightLocked,
}
```

- [ ] **Step 1.2: Write `MarkerCandidateTests.cs`**

Value equality + hash tests. Two candidates with identical field values are `Equals` and share `GetHashCode`. Difference in any field (including `Vector3` position, `SpawnCategory`, `UnlockBlockedReason`) breaks equality. A `MarkerCandidateList` with the same wrapped sequence `Equals` another `MarkerCandidateList` wrapping an equal sequence.

- [ ] **Step 1.3: Implement `MarkerCandidate`**

```csharp
namespace AdventureGuide.Markers;

public sealed class MarkerCandidate : IEquatable<MarkerCandidate>
{
	public MarkerCandidate(
		string questKey, string targetNodeKey, string positionNodeKey, string? sourceNodeKey,
		string scene, QuestMarkerKind questKind, SpawnCategory spawnCategory,
		int priority, string subText, UnityEngine.Vector3 staticPosition,
		bool keepWhileCorpsePresent, string? corpseSubText,
		bool isNightSpawnNode, bool isSpawnTimerSlot,
		string displayName, string? unlockBlockedReason) { /* assign */ }

	public string QuestKey { get; }
	public string TargetNodeKey { get; }
	public string PositionNodeKey { get; }
	public string? SourceNodeKey { get; }
	public string Scene { get; }
	public QuestMarkerKind QuestKind { get; }
	public SpawnCategory SpawnCategory { get; }
	public int Priority { get; }
	public string SubText { get; }
	public UnityEngine.Vector3 StaticPosition { get; }
	public bool KeepWhileCorpsePresent { get; }
	public string? CorpseSubText { get; }
	public bool IsNightSpawnNode { get; }
	public bool IsSpawnTimerSlot { get; }
	public string DisplayName { get; }
	public string? UnlockBlockedReason { get; }

	public bool Equals(MarkerCandidate? other) { /* field-by-field */ }
	public override bool Equals(object? obj) => Equals(obj as MarkerCandidate);
	public override int GetHashCode() { /* HashCode.Combine across all fields */ }
}
```

- [ ] **Step 1.4: Implement `MarkerCandidateList`**

```csharp
namespace AdventureGuide.Markers;

public sealed class MarkerCandidateList : IEquatable<MarkerCandidateList>
{
	public MarkerCandidateList(IReadOnlyList<MarkerCandidate> candidates) =>
		Candidates = candidates;
	public IReadOnlyList<MarkerCandidate> Candidates { get; }
	public bool Equals(MarkerCandidateList? other) =>
		other != null && Candidates.SequenceEqual(other.Candidates);
	public override bool Equals(object? obj) => Equals(obj as MarkerCandidateList);
	public override int GetHashCode() => Candidates.Count;
}
```

Wrapper preserves `IEquatable`-driven backdating through the engine's `Equals` check.

- [ ] **Step 1.5: Write `MarkerCandidatesQueryTests.cs`**

Use `EngineTests.cs`, `QueriesTests.cs`, and `NavigableQuestsQueryTests.cs` as templates. Build a minimal harness (compiled guide, fact sources, pre-seeded quest/scene state). Assertions:

- Compute produces the expected list for a one-quest-one-scene fixture.
- Invalidating `SourceState(spawn-point-node-key)` causes recompute; result reflects the new `SpawnCategory`.
- Invalidating `InventoryItemCount` for a non-required item does not recompute (the query never read it).
- Two successive reads with unchanged facts return the same reference (memoisation proof).
- Flipping a spawn from Alive → Dead produces a candidate with `SpawnCategory = Dead`; flipping back produces the original `SpawnCategory = Alive`.
- If `NavigableQuestSet` is reference-unchanged, `MarkerCandidates` does not re-read sub-queries (backdating test via compute-counter).
- An identical recompute result backdates: `MarkerCandidateList` reference stays the same across a no-op fact bump.

- [ ] **Step 1.6: Add `GuideReader.ReadSourceCategory(Node)`**

Wires `FactKey(SourceState, node.Key)` to an ambient-recording accessor that returns `SpawnCategory`. Implementation delegates to `LiveStateTracker` through a narrow `ISourceStateFactSource` interface (parallel to `IInventoryFactSource` etc. introduced in Plan A). Non-spawn nodes (item bag, mining, character-without-spawn) return `SpawnCategory.NotApplicable` and record the fact anyway — the query's decision may still branch on "is this actionable" and needs the invalidation hook.

- [ ] **Step 1.7: Add `GuideReader.ReadNavigableQuests()` and non-recording `CurrentScene`**

```csharp
/// <summary>Top-level read. Do not call from inside a query compute —
/// use `ctx.Read(navigableQuestsQuery.Query, Unit.Value)` instead so the
/// query-to-query dep is recorded.</summary>
public NavigableQuestSet ReadNavigableQuests() { ... }

/// <summary>Non-recording accessor for top-level callers that need the
/// current scene string without establishing a fact dependency. Use this
/// in MarkerProjector.Project, NavigationTargetSelector.Tick, and
/// Plugin.Update phases. Inside a query compute, use ReadCurrentScene()
/// instead.</summary>
public string CurrentScene => RequireQuestState().CurrentScene;
```

Document `ReadQuestResolution` with the same top-level-only caveat.

- [ ] **Step 1.8: Implement `MarkerCandidatesQuery`**

```csharp
namespace AdventureGuide.Markers.Queries;

public sealed class MarkerCandidatesQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly GuideReader _reader;
	private readonly NavigableQuestsQuery _navigableQuests;
	private readonly QuestResolutionQuery _questResolution;

	public Query<string, MarkerCandidateList> Query { get; }

	public MarkerCandidatesQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		GuideReader reader,
		NavigableQuestsQuery navigableQuests,
		QuestResolutionQuery questResolution)
	{
		_guide = guide;
		_reader = reader;
		_navigableQuests = navigableQuests;
		_questResolution = questResolution;
		Query = engine.DefineQuery<string, MarkerCandidateList>(
			name: "MarkerCandidates",
			compute: Compute);
	}

	private MarkerCandidateList Compute(ReadContext<FactKey> ctx, string scene)
	{
		var navigable = ctx.Read(_navigableQuests.Query, Unit.Value);
		var candidates = new List<MarkerCandidate>();

		// Union: navigable quests + quest-givers-in-scene + quest-completions-in-scene.
		// The latter two come from compiled-guide blueprints and aren't fact-driven —
		// they're static for the lifetime of the mod.
		var questKeys = new HashSet<string>(navigable.Keys, StringComparer.Ordinal);
		foreach (var bp in _guide.GetQuestGiversInScene(scene))
			questKeys.Add(bp.QuestKey);
		foreach (var bp in _guide.GetQuestCompletionsInScene(scene))
			questKeys.Add(bp.QuestKey);

		foreach (var questKey in questKeys)
		{
			var resolution = ctx.Read(_questResolution.Query, (questKey, scene));
			EmitCandidatesForQuest(ctx, scene, questKey, resolution, candidates);
		}

		SuppressBlockedMarkersAtOccupiedPositions(candidates);
		return new MarkerCandidateList(candidates.AsReadOnly());
	}

	private void EmitCandidatesForQuest(
		ReadContext<FactKey> ctx, string scene, string questKey,
		QuestResolutionRecord resolution, List<MarkerCandidate> sink)
	{
		// Mirrors MarkerComputer.RebuildQuestMarkers but emits MarkerCandidate
		// values. All spawn-state reads go through `_reader.ReadSourceCategory(node)`,
		// which ambient-records `FactKey(SourceState, node.Key)`. No direct
		// `_liveState.*` access inside this query.
		//
		// Subtext for timers/night is NOT baked in; the renderer fills that per frame.
	}
}
```

**Explicit non-goal:** this query does not read per-frame mutable state (`NPC.transform.position`, `sp.actualSpawnDelay`, `MiningNode.Respawn`, time-of-day). Any such read would corrupt the cache by making every frame a new result. Grep the finished compute for direct `_liveState.` access or UnityEngine time/position reads — there should be none.

- [ ] **Step 1.9: Wire the query into `Plugin.Awake` but do not call it yet**

Add a `MarkerCandidatesQuery _markerCandidatesQuery;` field, construct it right after `_questResolutionQuery` is built, hand it to nobody yet. This keeps the commit self-contained — the query is registered with the engine but has zero readers, so no behaviour changes. Tests alone validate correctness.

- [ ] **Step 1.10: Build clean; run tests; commit**

```
dotnet build src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo
git add src/mods/AdventureGuide/src/Markers src/mods/AdventureGuide/src/State src/mods/AdventureGuide/tests/AdventureGuide.Tests/Markers src/mods/AdventureGuide/src/Plugin.cs
git commit
```

Message: `feat(mod): define MarkerCandidates engine query`

**Task 1 acceptance:**
- `MarkerCandidate`, `MarkerCandidateList`, `SpawnCategory`, `MarkerCandidatesQuery` exist.
- `QuestMarkerKind` is reused; no overlapping `MarkerCandidateKind` enum was introduced.
- `GuideReader` has `ReadSourceCategory`, `ReadNavigableQuests`, and a non-recording `CurrentScene`.
- Query tests cover memoisation, fact invalidation, backdating, spawn-state transitions.
- Query is registered with the engine but unread.
- Full test suite green; mod builds.

---

### Task 2: `MarkerProjector` / `MarkerRenderer` rename + cutover

**Goal:** Rename `MarkerComputer` → `MarkerProjector` and `MarkerSystem` → `MarkerRenderer`. Strip every piece of state that coordinates cache freshness. `MarkerProjector.Project()` reads `MarkerCandidates(currentScene)` from the engine and materialises an `IReadOnlyList<MarkerEntry>` by overlaying live state. `MarkerRenderer.Render()` reconfigures the pool when the projector's candidate-list reference changes and runs per-frame live updates. Delete orphaned `MarkerQuestTargetResolver`. Drop the `MarkerRebuildMode` / `MarkerRebuildModeSample` concepts with the diagnostics snapshot simplification.

**Files:**
- Rename: `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs` → `MarkerProjector.cs` (via `git mv`)
- Rename: `src/mods/AdventureGuide/src/Markers/MarkerSystem.cs` → `MarkerRenderer.cs` (via `git mv`)
- Modify: `MarkerProjector.cs` — gut and rebuild; method is `Project()`
- Modify: `MarkerRenderer.cs` — swap `_computer` for `_projector`, delete `_lastConfiguredVersion`, drive pool reconfig off candidate-list reference; method is `Render()`
- Modify: `src/mods/AdventureGuide/src/Markers/MarkerEntry.cs` — fields redundant with `MarkerCandidate` drop; entry carries a `Candidate` reference plus per-frame-mutable render state
- Modify: `src/mods/AdventureGuide/src/UI/DiagnosticOverlay.cs`
- Modify: `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs`
- Modify: `src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs` (rewrite `MarkerDiagnosticsSnapshot`)
- Modify: `src/mods/AdventureGuide/src/Plugin.cs` — construction, wiring, deletion of `ApplyChangeSet`/`Recompute`/`MarkDirty` calls
- Delete: `src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs`
- Delete: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs`
- Delete: `MarkerRebuildMode`, `MarkerRebuildModeSample` — grep for their definition files
- Modify: every test that referenced `MarkerComputer` / `MarkerSystem` / `MarkerQuestTargetResolver`

- [ ] **Step 2.1: Enumerate every `MarkerComputer`, `MarkerSystem`, `MarkerQuestTargetResolver` reference**

Run `lsp references` on each class and on each public member of `MarkerComputer` (`ApplyChangeSet`, `MarkDirty`, `Recompute`, `Markers`, `Version`, `Destroy`, `ExportDiagnosticsSnapshot`, `GetContributingQuestKeys`). Record every hit. Cutover must update all of them atomically.

- [ ] **Step 2.2: Delete `MarkerQuestTargetResolver`**

`lsp references MarkerQuestTargetResolver` — confirm the only production caller is `MarkerComputer` (deleted in this task). The test file `MarkerQuestTargetResolverTests.cs` is tied to this class and goes with it. `git rm` both.

If `MarkerQuestTargetResolver` has any remaining caller outside `MarkerComputer`, stop and reassess — its contract (`dbName → compiledTargets`) is a thin wrapper over `_reader.ReadQuestResolution(...).CompiledTargets` and should inline at the caller, not survive.

- [ ] **Step 2.3: Define `MarkerProjector`'s new shape**

```csharp
namespace AdventureGuide.Markers;

public sealed class MarkerProjector
{
	private readonly GuideReader _reader;
	private readonly MarkerCandidatesQuery _query;
	private readonly LiveStateTracker _liveState;
	private readonly CompiledGuideModel _guide;
	private readonly DiagnosticsCore? _diagnostics;

	private MarkerCandidateList? _lastCandidates;
	private readonly List<MarkerEntry> _entries = new();

	public IReadOnlyList<MarkerEntry> Markers => _entries;

	public MarkerProjector(
		GuideReader reader,
		MarkerCandidatesQuery query,
		LiveStateTracker liveState,
		CompiledGuideModel guide,
		DiagnosticsCore? diagnostics)
	{
		_reader = reader;
		_query = query;
		_liveState = liveState;
		_guide = guide;
		_diagnostics = diagnostics;
	}

	/// <summary>Reads MarkerCandidates through the engine and materialises
	/// per-frame MarkerEntry instances when the candidate list reference
	/// changes. Called from Plugin.ConsumePhase.</summary>
	public void Project()
	{
		var currentScene = _reader.CurrentScene;
		var candidates = _reader.ReadMarkerCandidates(currentScene);
		if (ReferenceEquals(candidates, _lastCandidates))
			return;

		_entries.Clear();
		foreach (var c in candidates.Candidates)
			_entries.Add(BuildEntry(c));
		_lastCandidates = candidates;
	}

	private MarkerEntry BuildEntry(MarkerCandidate c)
	{
		// Bind LiveSpawnPoint / TrackedNPC / LiveMiningNode from _liveState
		// by looking up PositionNodeKey. Copy StaticPosition into X/Y/Z. Set
		// initial Type from QuestMarkerKind + SpawnCategory. Fill timers/
		// night-lock text from live values here only for the first frame;
		// MarkerRenderer refreshes them per frame.
	}

	public MarkerDiagnosticsSnapshot ExportDiagnosticsSnapshot() => /* minimal — see Step 2.8 */;
	public IReadOnlyCollection<string>? GetContributingQuestKeys(string nodeKey) => /* preserved */;
}
```

`_dirty`, `_fullRebuild`, `_pendingQuestKeys`, `MarkDirty`, `ApplyChangeSet`, `Recompute`, `Version`, `_lastRecomputeTicks`, `_recentQuestCosts`, `_recentModes`, `_lastDiagnosticTrigger`, `_nodesByQuest`, `_contributionsByNode` — all gone. `GetContributingQuestKeys` is preserved because the overlay uses it; back it with a lazy lookup over `_lastCandidates`.

- [ ] **Step 2.4: Define `MarkerRenderer`'s new shape**

```csharp
namespace AdventureGuide.Markers;

public sealed class MarkerRenderer
{
	private readonly MarkerProjector _projector;
	private readonly MarkerPool _pool;
	private readonly GuideConfig _config;

	private bool _enabled;
	private bool _configDirty;
	private string _currentScene = "";
	private IReadOnlyList<MarkerEntry>? _lastConfiguredEntries;

	public bool Enabled { /* same as MarkerSystem */ }

	public MarkerRenderer(MarkerProjector projector, MarkerPool pool, GuideConfig config)
	{
		_projector = projector;
		_pool = pool;
		_config = config;
		// same SettingChanged subscriptions as MarkerSystem today
	}

	/// <summary>Per-frame render: reconfigure pool when projector output
	/// reference changes; update live per-frame state (timers, NPC positions,
	/// alpha, dead/alive transitions). Called from Plugin.ConsumePhase after
	/// MarkerProjector.Project.</summary>
	public void Render()
	{
		if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
			return;

		var entries = _projector.Markers;
		if (!ReferenceEquals(entries, _lastConfiguredEntries) || _configDirty)
		{
			ConfigureMarkers(entries);
			_lastConfiguredEntries = entries;
			_configDirty = false;
		}

		UpdateLiveState(entries);
	}

	public void OnSceneChanged(string scene) { /* same */ }
	public void Destroy() { /* same */ }

	// ConfigureMarkers, UpdateLiveState, UpdateSpawnState, UpdateSpawnTimerState,
	// UpdateMiningState, UpdatePosition, SetPositionFromNPC, ReconfigureInstance,
	// FormatDeadSubText, GetMiningRespawnSeconds — all preserved from MarkerSystem.
}
```

Key behavioural change: `_lastConfiguredVersion` (an int) becomes `_lastConfiguredEntries` (an `IReadOnlyList<MarkerEntry>?` reference). The projector's `Project()` replaces its `_entries` list in-place on reference change — no, wait. Ensure the projector produces a **new** list reference each time candidates change, not a cleared-and-refilled single list. Otherwise reference-equality fails.

**Option A:** `MarkerProjector._entries` is rebuilt into a new `List<MarkerEntry>` each time candidates change; `Markers` property returns the current list reference. Reference changes on update ⇒ renderer detects via `ReferenceEquals`.

**Option B:** Projector clears and refills the same list; renderer stores `_lastConfiguredCandidates` (the `MarkerCandidateList` reference) instead of the entry-list reference.

Pick **B** — fewer allocations per frame, and the semantic signal ("has the projection changed?") matches the engine's contract exactly.

Update `MarkerRenderer` sketch: compare `_projector.LastCandidates` (expose as a property) or take the candidate reference directly from the reader.

Simpler refinement:

```csharp
public sealed class MarkerProjector
{
	public MarkerCandidateList? LastCandidates { get; private set; }
	// ...existing...
}

public sealed class MarkerRenderer
{
	private MarkerCandidateList? _lastConfiguredCandidates;

	public void Render()
	{
		// ...existing checks...
		var entries = _projector.Markers;
		var candidates = _projector.LastCandidates;
		if (!ReferenceEquals(candidates, _lastConfiguredCandidates) || _configDirty)
		{
			ConfigureMarkers(entries);
			_lastConfiguredCandidates = candidates;
			_configDirty = false;
		}
		UpdateLiveState(entries);
	}
}
```

Document this coordination in both classes' doc comments.

- [ ] **Step 2.5: Decide `MarkerEntry` shape**

Current `MarkerEntry` has ~20 fields. After Task 2, `MarkerEntry` holds *only* the per-frame mutable render state and a reference to its source `MarkerCandidate`.

Proposed:
```csharp
public sealed class MarkerEntry
{
	public MarkerEntry(MarkerCandidate candidate) {
		Candidate = candidate;
		X = candidate.StaticPosition.x;
		Y = candidate.StaticPosition.y;
		Z = candidate.StaticPosition.z;
	}

	public MarkerCandidate Candidate { get; }

	// Live render state (mutated per frame by MarkerRenderer):
	public float X { get; set; }
	public float Y { get; set; }
	public float Z { get; set; }
	public MarkerType Type { get; set; }
	public int Priority { get; set; }
	public string SubText { get; set; } = "";

	// Live game-object references (bound once by MarkerProjector, read per frame):
	public SpawnPoint? LiveSpawnPoint { get; set; }
	public NPC? TrackedNPC { get; set; }
	public MiningNode? LiveMiningNode { get; set; }
	public RotChest? LiveRotChest { get; set; }
	public bool IsLootChestTarget { get; set; }

	// Convenience forwards (read-only — derived from Candidate):
	public string QuestKey => Candidate.QuestKey;
	public string Scene => Candidate.Scene;
	public string NodeKey => Candidate.PositionNodeKey;
	public string DisplayName => Candidate.DisplayName;

	internal static MarkerType ToMarkerType(QuestMarkerKind kind) => /* preserved */;
}
```

Drops from the old `MarkerEntry`: `QuestKind` (read via `Candidate.QuestKind`), `QuestPriority` (via `Candidate.Priority`), `QuestSubText` (via `Candidate.SubText`), `KeepWhileCorpsePresent` (via `Candidate.KeepWhileCorpsePresent`), `CorpseSubText` (via `Candidate.CorpseSubText`), `IsSpawnTimer` (via `Candidate.IsSpawnTimerSlot`), `SourceNodeKey` (via `Candidate.SourceNodeKey`).

Document the field mapping clearly in the commit body; the renderer's per-frame code needs to be audited for every old-field access and rerouted to the candidate reference.

- [ ] **Step 2.6: Simplify `MarkerDiagnosticsSnapshot`**

```csharp
internal sealed class MarkerDiagnosticsSnapshot
{
	public MarkerDiagnosticsSnapshot(int candidateCount, int entryCount, long lastProjectionTicks)
	{
		CandidateCount = candidateCount;
		EntryCount = entryCount;
		LastProjectionTicks = lastProjectionTicks;
	}
	public int CandidateCount { get; }
	public int EntryCount { get; }
	public long LastProjectionTicks { get; }
}
```

Delete: `fullRebuild`, `pendingQuestCount`, `lastReason`, `topQuestCosts`, `recentModes`. Delete the supporting types `MarkerRebuildMode` and `MarkerRebuildModeSample` at their definition site (grep). `QuestCostSample` may still be used by the navigation selector's diagnostics; if so, keep it in place — it's legitimate navigation-side instrumentation.

- [ ] **Step 2.7: Update `DiagnosticOverlay`**

Replace `MarkerComputer` field with `MarkerProjector`. Update text format to reflect the new snapshot shape — no more `mode={Full|Incremental}` (that distinction is gone); replace with `candidates={count}` or similar.

- [ ] **Step 2.8: Update `Plugin.Awake` construction order**

```csharp
_markerCandidatesQuery = new MarkerCandidatesQuery(_engine, _compiledGuide, _reader, _navigableQuestsQuery, _questResolutionQuery);
_markerProjector = new MarkerProjector(_reader, _markerCandidatesQuery, _liveState, _compiledGuide, _diagnostics);
_markerRenderer = new MarkerRenderer(_markerProjector, _markerPool, _config);
```

Delete:
- The `_markerComputer.ApplyChangeSet(initialChangeSet)` call in Awake.
- The `_markerComputer.Recompute()` call in Awake (engine is lazy; first consumer read triggers compute).
- The warmup log lines tied to the first recompute, or rewire them to `_markerProjector.Project()` + `_reader.ReadMarkerCandidates(...)` to produce the startup warm.

- [ ] **Step 2.9: Delete `MarkerComputer`/`MarkerSystem` references in `Plugin.Update` and `Plugin.OnSceneLoaded`**

The inline `_markerComputer?.ApplyChangeSet(...)` + `_markerComputer?.Recompute()` lines in `Update` become `_markerProjector?.Project()` + `_markerRenderer?.Render()` (Task 4 formalises phase split). The `_markerComputer?.ApplyChangeSet(sceneChangeSet)` call in `OnSceneLoaded` goes away entirely — scene-change facts are already published via `_engine.InvalidateFacts`. `_markerSystem?.OnSceneChanged(scene.name)` becomes `_markerRenderer?.OnSceneChanged(scene.name)`.

- [ ] **Step 2.10: Update `DebugAPI`**

`DebugAPI.Markers` retype from `MarkerComputer?` to `MarkerProjector?`. `DebugAPI.MarkerSnapshot` wires to `_markerProjector.ExportDiagnosticsSnapshot`. Any `DebugAPI.Markers.MarkDirty()` call sites (profiling shortcuts) — either replace with `_engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "*") })` or delete the shortcut entirely if it no longer makes sense.

- [ ] **Step 2.11: Update patches**

`SpawnPatch`, `MiningNodePatch`, `ItemBagPatch`, `DeathPatch`, `CorpseChestPatch` — verify each still routes live-state changes through `_liveState` (which publishes `SourceState` facts in its next frame). The fact-routing was installed in Plan A; confirm nothing regressed. Any remaining `MarkDirty` call through `DebugAPI.Markers` is dead — delete.

- [ ] **Step 2.12: Rewrite marker tests**

- `MarkerComputerTests.cs` (or similar) → renamed to `MarkerProjectorTests.cs`; coverage narrows to "projector reads candidates and materialises entries with correct live-state binding."
- `MarkerSystemTests.cs` (if present) → `MarkerRendererTests.cs`; same coverage.
- Algorithmic marker-emission coverage moves to `MarkerCandidatesQueryTests.cs` (Task 1).
- Delete assertions on `_dirty`, `_fullRebuild`, `MarkDirty`, `ApplyChangeSet`, `Version`, `MarkerRebuildMode`.

- [ ] **Step 2.13: Build clean; run tests**

Iteratively fix compile errors. Expected trouble spots:
- Fields named `_markerComputer` or `_markerSystem` in subsystems not yet renamed.
- Test helpers that took `MarkerComputer` / `MarkerSystem` as a parameter.
- Patches that called into `MarkerComputer` via `DebugAPI.Markers.MarkDirty`.

- [ ] **Step 2.14: Commit**

```
git add src/mods/AdventureGuide/src src/mods/AdventureGuide/tests
git commit
```

Message: `refactor(mod): rename MarkerComputer to MarkerProjector, MarkerSystem to MarkerRenderer, drive both off MarkerCandidates`

Body (paragraphs, not bullets):
- Describe the role split: `MarkerCandidates` is the engine query that materialises scene-level marker descriptors from quest state + `SourceState` facts; `MarkerProjector` binds candidates to live Unity objects once per candidate-list change; `MarkerRenderer` runs per-frame pool configuration and live state updates.
- Describe the naming alignment: `MarkerComputer` and `MarkerSystem` were one-off suffixes; the new names join the existing `Projector` and `Renderer` families.
- Note that `_dirty`, `_fullRebuild`, `_pendingQuestKeys`, `MarkDirty`, `ApplyChangeSet`, `Recompute`, `Version`, `MarkerRebuildMode`, `MarkerRebuildModeSample`, and `MarkerQuestTargetResolver` are deleted because the engine's revision-based invalidation subsumes them all.
- Note that `MarkerDiagnosticsSnapshot` is narrowed because the old fields described a rebuild policy that no longer exists.

**Task 2 acceptance:**
- `MarkerComputer`, `MarkerSystem`, `MarkerQuestTargetResolver`, `MarkerRebuildMode`, `MarkerRebuildModeSample` do not exist in the codebase.
- `MarkerProjector.Project()` is the only entry point for candidate materialisation; `MarkerRenderer.Render()` is the only per-frame render entry point.
- Pool reconfiguration is reference-equality-driven, not counter-driven.
- `DebugAPI.Markers` is typed `MarkerProjector?`.
- `MaintainedViewPlanner` is still present and still called (Task 3 deletes it).
- Tests green; mod builds; in-game marker rendering unchanged (sanity: deploy and eyeball one quest).

---

### Task 3: Delete `MaintainedViewPlanner`, simplify selector, consolidate namespaces

**Goal:** Remove the planner and the `MaintainedViewPlan` it produced. `NavigationTargetSelector`'s force-rebuild decision becomes: "did the engine's `NavigableQuestSet` reference change since last tick?" Rename `NavigableQuestsResult` → `NavigableQuestSet` (Plan A residue). Consolidate namespaces: `AdventureGuide.Plan` → `AdventureGuide.Frontier`; move `NavigationSet` from the old `AdventureGuide.Frontier` to `AdventureGuide.Navigation`.

**Files:**
- Delete: `src/mods/AdventureGuide/src/Plan/MaintainedViewPlanner.cs`
- Delete: `src/mods/AdventureGuide/src/Plan/MaintainedViewPlan.cs` (drops `MaintainedViewRefreshKind` too)
- Move: `src/mods/AdventureGuide/src/Plan/EffectiveFrontier.cs` → `src/Frontier/EffectiveFrontier.cs`
- Move: `src/mods/AdventureGuide/src/Plan/FrontierEntry.cs` → `src/Frontier/FrontierEntry.cs`
- Move: `src/mods/AdventureGuide/src/Plan/QuestPhaseTracker.cs` → `src/Frontier/QuestPhaseTracker.cs`
- Move: `src/mods/AdventureGuide/src/Frontier/NavigationSet.cs` → `src/Navigation/NavigationSet.cs`
- Delete: now-empty `src/mods/AdventureGuide/src/Plan/` directory
- Modify: every `.cs` file with `using AdventureGuide.Plan;` or `using AdventureGuide.Frontier;` — update to `using AdventureGuide.Frontier;` or `using AdventureGuide.Navigation;` as appropriate
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs` — drop `Version`, rewrite `Tick` signature
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs` — drop `Func<int>` target-source-version callback
- Modify: `src/mods/AdventureGuide/src/Navigation/Queries/NavigableQuestsQuery.cs` — rename `NavigableQuestsResult` → `NavigableQuestSet`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs` — delete planner call; rename rippled through phase methods
- Delete: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewPlannerTests.cs`
- Modify or delete: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs` (review content; likely delete since it tested planner wiring)

Order the sub-steps so the namespace move happens *after* the planner deletion, to avoid moving dead files.

- [ ] **Step 3.1: Map every consumer**

`lsp references` on `MaintainedViewPlanner`, `MaintainedViewPlan`, `MaintainedViewRefreshKind`, `NavigableQuestsResult`. Expected hits: `Plugin.Update` (1 planner call), selector tests, marker tests (removed in Task 2 cleanup), and `NavigationTargetSelector.Version` (if referenced externally — expect it isn't after Task 3's own edits).

- [ ] **Step 3.2: Rename `NavigableQuestsResult` → `NavigableQuestSet`**

Use `lsp rename` to catch every reference. The rename touches:
- `src/Navigation/Queries/NavigableQuestsQuery.cs` (type def + return type)
- Any field/variable typed `NavigableQuestsResult`
- Test fixtures

- [ ] **Step 3.3: Update `NavigationTargetSelector.Tick` signature**

```csharp
internal void Tick(
	float playerX, float playerY, float playerZ, string currentZone,
	NavigableQuestSet navigable,
	bool liveWorldChanged)
```

Selector compares `ReferenceEquals(navigable, _lastNavigable)`. Reference changed ⇒ force rebuild. `liveWorldChanged` only ⇒ rescore-only with live-position refresh. Neither ⇒ rescore-only (respect `_rerankInterval`). `Version` is deleted from the selector. `_lastBatchWasPartialRefresh` is deleted (no more partial refreshes). Diagnostic fields that remain (`_lastResolvedTargetCount`, `_lastBatchKeyCount`, `_lastForceReason`, `_topQuestCosts`) stay; document them as diagnostics-only, not cache-coordinators.

- [ ] **Step 3.4: `NavigationEngine` cleanup**

Delete the `Func<int>` target-source-version parameter from its ctor. If its cache-validity was keyed on that counter, switch to whatever the new invariant is (likely: "did the selector's `Version` change" — but we just deleted that too). Replace with reference-equality on `NavigableQuestSet` or simply always-update (navigation engine's work is cheap). The clean choice depends on code inspection during execution.

- [ ] **Step 3.5: Rewire `Plugin.Update`**

Replace this block:
```csharp
var plan = MaintainedViewPlanner.Plan(AllNavigableNodeKeys(), selectorChangeSet, ...);
if (plan.RequiresRefresh) { ... _targetSelector?.Tick(..., force: true, forceReason: plan.Reason, ...); }
```
With:
```csharp
var navigable = _reader.ReadNavigableQuests();
_targetSelector?.Tick(playerPos.x, playerPos.y, playerPos.z, currentZone, navigable, liveChangeSet.HasMeaningfulChanges);
```

`AllNavigableNodeKeys()` iterator in `Plugin` is redundant; delete.

- [ ] **Step 3.6: Delete planner files**

```
git rm src/mods/AdventureGuide/src/Plan/MaintainedViewPlanner.cs
git rm src/mods/AdventureGuide/src/Plan/MaintainedViewPlan.cs
git rm src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewPlannerTests.cs
# MaintainedViewDiagnosticsTests.cs — inspect; if it purely tested planner wiring, git rm it; otherwise rewrite
```

- [ ] **Step 3.7: Move `Plan/*` → `Frontier/*` (namespace sweep)**

```
git mv src/mods/AdventureGuide/src/Plan/EffectiveFrontier.cs src/mods/AdventureGuide/src/Frontier/EffectiveFrontier.cs
git mv src/mods/AdventureGuide/src/Plan/FrontierEntry.cs src/mods/AdventureGuide/src/Frontier/FrontierEntry.cs
git mv src/mods/AdventureGuide/src/Plan/QuestPhaseTracker.cs src/mods/AdventureGuide/src/Frontier/QuestPhaseTracker.cs
```

But wait — the target directory `src/Frontier/` already exists (it holds `NavigationSet.cs`). Step 3.8 moves `NavigationSet` out; `git mv` in steps 3.7 and 3.8 together produce the final state. Order doesn't strictly matter; do them back-to-back and fix imports in one pass.

Update each moved file's namespace declaration: `namespace AdventureGuide.Plan;` → `namespace AdventureGuide.Frontier;`.

- [ ] **Step 3.8: Move `NavigationSet.cs` out of the old `Frontier`**

```
git mv src/mods/AdventureGuide/src/Frontier/NavigationSet.cs src/mods/AdventureGuide/src/Navigation/NavigationSet.cs
```

Update `NavigationSet.cs`'s namespace: `namespace AdventureGuide.Frontier;` → `namespace AdventureGuide.Navigation;`.

- [ ] **Step 3.9: Update every `using` statement**

Files that imported `AdventureGuide.Plan` (quest-phase / frontier code) ⇒ now import `AdventureGuide.Frontier`.
Files that imported `AdventureGuide.Frontier` *for NavigationSet* ⇒ now import `AdventureGuide.Navigation`.
Files that imported `AdventureGuide.Frontier` for `EffectiveFrontier` etc. ⇒ keep as-is (same namespace name, different contents).

Run both renames via find-replace within the `using` statements:
- `using AdventureGuide.Plan;` → `using AdventureGuide.Frontier;` (bulk)
- For files that still need `NavigationSet`: add `using AdventureGuide.Navigation;`

LSP rename on the namespace is cleaner if supported; otherwise grep the `using` statements as a targeted text pass.

- [ ] **Step 3.10: Add `GuideReader.ReadNavigableQuests()` setter wiring**

If Task 1 landed `ReadNavigableQuests()`, ensure `GuideReader`'s constructor / setter accepts `NavigableQuestsQuery` analogous to `SetQuestResolutionQuery`. `Plugin.Awake` calls the setter after constructing the query.

- [ ] **Step 3.11: Update tests**

- `NavigationTargetSelectorTests` — rewrite `force=true` paths to call `Tick` with a fresh `NavigableQuestSet` reference.
- `NavigableQuestsQueryTests` — type rename to `NavigableQuestSet`.
- Tests that constructed `MaintainedViewPlan` directly — update or delete.

- [ ] **Step 3.12: Build, test, commit**

```
dotnet build src/mods/AdventureGuide/AdventureGuide.csproj -v quiet -nologo
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo
git add src/mods/AdventureGuide
git commit
```

Message: `refactor(mod): delete MaintainedViewPlanner, derive selector refresh from engine, consolidate namespaces`

Body: describe the replacement (reference-equality on `NavigableQuestSet`), the `NavigableQuestsResult` → `NavigableQuestSet` rename dropping the Plan-A "Result" suffix, the `Plan` → `Frontier` namespace merge, and the `NavigationSet` move into `Navigation`. Note that the partial-refresh `preserveUntouchedEntries` hack was collapsed into unconditional full rebuild on reference change.

**Task 3 acceptance:**
- `MaintainedViewPlanner`, `MaintainedViewPlan`, `MaintainedViewRefreshKind`, `NavigableQuestsResult` don't exist.
- `NavigationTargetSelector.Version`, `_lastBatchWasPartialRefresh` don't exist.
- `Plugin.Update` never mentions `MaintainedViewPlanner`.
- `AdventureGuide.Plan` namespace doesn't exist.
- `AdventureGuide.Frontier` namespace contains `EffectiveFrontier`, `FrontierEntry`, `QuestPhaseTracker` only.
- `AdventureGuide.Navigation` namespace contains `NavigationSet`.
- Tests green; mod builds.

---

### Task 4: Five-phase orchestrator extraction

**Goal:** Decompose `Plugin.Update` into five named methods — `CapturePhase`, `PublishPhase`, `InvalidatePhase`, `ConsumePhase`, `RenderPhase` — each bracketed by a diagnostics span. `Update` becomes a ~10-line driver.

**Files:**
- Modify: `src/mods/AdventureGuide/src/Plugin.cs` — `Update` method rewrites
- Modify: `src/mods/AdventureGuide/src/Diagnostics/DiagnosticsTypes.cs` — add `DiagnosticSpanKind` entries: `UpdatePhaseCapture`, `UpdatePhasePublish`, `UpdatePhaseInvalidate`, `UpdatePhaseConsume`, `UpdatePhaseRender`

- [ ] **Step 4.1: Add the new `DiagnosticSpanKind` values**

Grep `DiagnosticSpanKind` enum definition. Add the five new entries at the end preserving existing numbers so incident dumps don't scramble.

- [ ] **Step 4.2: Define phase methods**

```csharp
private (ChangeSet Change, bool LiveWorldChanged) CapturePhase()
{
	using var span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseCapture, "Capture");
	var liveChange = _liveState?.UpdateFrameState() ?? ChangeSet.None;
	ChangeSet questChange = ChangeSet.None;
	if (_questTracker != null && _lastObservedQuestTrackerVersion != _questTracker.Version)
	{
		questChange = _questTracker.BuildSyncChangeSet();
		_lastObservedQuestTrackerVersion = _questTracker.Version;
	}
	return (questChange.Merge(liveChange), liveChange.HasMeaningfulChanges);
}

private void PublishPhase(ChangeSet change)
{
	using var span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhasePublish, "Publish");
	if (change.HasMeaningfulChanges)
		_engine?.InvalidateFacts(change.ChangedFacts);
	if (change.SceneChanged)
		_zoneRouter?.Rebuild();
}

private void InvalidatePhase(ChangeSet change)
{
	using var span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseInvalidate, "Invalidate");
	// Reserved phase: Group 2+ may invalidate engine entries for signals the
	// trackers don't express as facts. Plan B leaves this empty. The span
	// still fires so frame-budget telemetry has a stable slot.
	_ = change;
}

private void ConsumePhase(bool liveWorldChanged)
{
	using var span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseConsume, "Consume");
	if (!_inGameplay) return;
	var playerPos = GameData.PlayerControl?.transform.position ?? Vector3.zero;
	var currentZone = _reader!.CurrentScene;
	var navigable = _reader.ReadNavigableQuests();
	_targetSelector?.Tick(playerPos.x, playerPos.y, playerPos.z, currentZone, navigable, liveWorldChanged);
	_navEngine?.Update(playerPos);
	_groundPath?.Update();
	_markerProjector?.Project();
	_markerRenderer?.Render();
}

private void RenderPhase()
{
	using var span = _diagnostics.OpenSpan(DiagnosticSpanKind.UpdatePhaseRender, "Render");
	// Input handling that affects next-frame rendering state.
	if (_config == null || _window == null) return;
	if (!_inGameplay) return;
	if (GameData.PlayerTyping) return;
	if (Input.GetKeyDown(_config.ToggleKey.Value)) _window.Toggle();
	if (_config.ReplaceQuestLog.Value && Input.GetKeyDown(InputManager.Journal)) _window.Toggle();
	if (_config.TrackerEnabled.Value && Input.GetKeyDown(_config.TrackerToggleKey.Value)) _trackerPanel?.Toggle();
	if (Input.GetKeyDown(_config.GroundPathToggleKey.Value)) _config.ShowGroundPath.Value = !_config.ShowGroundPath.Value;
}
```

- [ ] **Step 4.3: Refactor `Update` to the driver**

```csharp
private void Update()
{
	UpdateGameUiVisibility();
	UpdateEditUiMode();
	UpdatePlayerTyping();

	var (change, liveWorldChanged) = CapturePhase();
	PublishPhase(change);
	InvalidatePhase(change);
	ConsumePhase(liveWorldChanged);
	RenderPhase();
}
```

Move the game-UI-visibility, edit-UI-mode, and player-typing blocks into small private helpers above so the driver is pure phase orchestration. If that pushes too many helpers, inline them into `CapturePhase` instead.

- [ ] **Step 4.4: Audit `OnSceneLoaded`**

`OnSceneLoaded` fires scene-change facts out-of-band (Unity event, not Update). Keep its structure — it needs to publish facts before the next `Update` tick for correctness. Add a single-line comment: `// Out-of-band fact publication for scene load; mirrors Plugin.Update's Capture/Publish without phase spans.` Do not reshape it into the phase model.

- [ ] **Step 4.5: Build, test, commit**

Message: `refactor(mod): decompose Plugin.Update into Capture/Publish/Invalidate/Consume/Render phases`

Body: describe phase boundaries; note `InvalidatePhase` is an empty-body seam reserved for Group 2+; note the decision to keep `OnSceneLoaded`'s out-of-band fact publish.

**Task 4 acceptance:**
- `Plugin.Update` is the five-phase driver; body fits in ~10 lines plus preamble helpers.
- Each phase method is bracketed by a diagnostics span.
- The incident dump under representative scene load shows new `UpdatePhase*` spans without regressing pre-existing ones.
- Tests green; mod builds.

---

### Task 5: Version-counter sweep

**Goal:** Audit and delete every remaining version counter or dirty flag that coordinates cache freshness. Spec § 5.3 lists the targets: `Plugin`, `QuestResolutionService` (done in Plan A), `MaintainedViewPlanner` (Task 3), `MarkerComputer` (Task 2), `NavigationTargetSelector` (Task 3). This task finds and kills everything else that matches the pattern.

**Files:**
- Modify: `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs` — has a `Version` field; is it still read?
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs` — confirm no residual version
- Modify: `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs` — any `version` hooks
- Modify: any subsystem with `_lastObservedX`/`_lastConfiguredX`/`_dirty` patterns

- [ ] **Step 5.1: Grep**

```
grep -rn "Version" src/mods/AdventureGuide/src --include='*.cs'
grep -rn "_dirty\b\|_fullRebuild\b\|_pending\b\|_lastConfigured\|_lastObserved" src/mods/AdventureGuide/src --include='*.cs'
```

Catalogue every hit. Classify: (a) cache-freshness coordinator — delete; (b) legitimate monotonic counter — keep (e.g. a tracker's internal revision); (c) diagnostic-only — reduce to a read-only counter or delete.

- [ ] **Step 5.2: `_lastObservedQuestTrackerVersion`**

Plugin.cs uses this to detect "did `_questTracker` observe new game events since last frame?" The engine doesn't directly replace this because the tracker's sync ChangeSet is built by diffing tracker state. Keep — it's the *outside* edge, not internal cache coordination.

Document with a code comment: "Tracker-internal revision; not a cache-freshness coordinator."

- [ ] **Step 5.3: `NavigationTargetResolver.Version`**

Counter bumped on Plan A's deleted `InvalidateAll` / `InvalidateAffected` calls. After Plan A those bumps stopped; Task 3 deleted the only consumer (`NavigationEngine`'s `Func<int>`). The counter is orphaned. Delete the field and any remaining increments.

- [ ] **Step 5.4: Selector diagnostic fields**

`_lastForceReason`, `_lastResolvedTargetCount`, `_lastBatchKeyCount`, `_lastBatchWasPartialRefresh`, `_topQuestCosts`. After Task 3, `_lastBatchWasPartialRefresh` is dead (delete). The rest are diagnostic snapshot inputs — keep the ones the overlay / `NavigationDiagnosticsSnapshot` reads; delete orphans.

- [ ] **Step 5.5: Other flags**

Any `_dirty`/`_pending` in other subsystems: inspect. Most should already be dealt with. Document or delete.

- [ ] **Step 5.6: Build, test, commit**

Message: `refactor(mod): delete orphaned version counters and cache-freshness flags`

**Task 5 acceptance:**
- Every counter that coordinated cache freshness is either deleted or documented as an external-state edge.
- Spec § 9 acceptance "no version counters, dirty flags, reference-identity checks, or implicit-detection patterns remain coordinating cache freshness" is literally true.

---

### Task 6: Integration, verification, ship

**Goal:** End-to-end verify nothing regressed. Deploy. Eyeball in-game. Ship.

- [ ] **Step 6.1: Full test suite**

```
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo
```

Expected: count may have decreased (obsolete tests deleted) or increased (new query tests). All green.

- [ ] **Step 6.2: Build clean**

```
dotnet build src/mods/AdventureGuide/AdventureGuide.csproj -v quiet -nologo
```

- [ ] **Step 6.3: Deploy and F6-reload**

```
uv run erenshor mod deploy --mod adventure-guide --scripts
```

User F6-reloads. Verify:
- Quest tracker UI updates on quest assign/complete.
- Marker positions, kinds, and subtexts match pre-Plan-B behaviour for: one alive quest, one implicitly-available quest, one blocked quest-giver.
- Marker timers count down; NPC positions track live.
- Scene transition produces correct markers in the new zone.
- Incident dump shows new `UpdatePhase*` spans; no new `FrameStall` / `FrameHitch` compared to pre-Plan-B.

If any regression: investigate before shipping.

- [ ] **Step 6.4: Verify spec § 9 acceptance**

Walk the acceptance list explicitly. Confirm each criterion.

- [ ] **Step 6.5: Final commit (if any residual work)**

Only if integration surfaced wiring gaps or doc updates.

- [ ] **Step 6.6: Push**

```
git push
```

**Task 6 acceptance:**
- All tests green; build clean; in-game smoke test clean; incident dump clean.
- Spec § 9 acceptance criteria fully satisfied.
- Commits pushed to origin.

---

## Spec Coverage Check

| Spec section | Covered by |
|---|---|
| § 2 Q5 (retire planner) | Task 3 |
| § 4.5 MarkerCandidates | Task 1 |
| § 5.1 five phases | Task 4 |
| § 5.3 version counters removed | Tasks 2, 3, 5 |
| § 6 naming: `MarkerComputer` → `MarkerProjector` | Task 2 |
| § 6 naming: `MarkerSystem` → `MarkerRenderer` | Task 2 |
| § 6 naming: planner + plan deleted | Task 3 |
| § 6 naming: `NavigableQuestsResult` → `NavigableQuestSet` | Task 3 |
| § 6 naming: `Plan/` → `Frontier/` namespace merge | Task 3 |
| § 9 acceptance — MarkerCandidates query exists | Task 1 |
| § 9 acceptance — MarkerProjector replaces MarkerComputer | Task 2 |
| § 9 acceptance — planner + plan deleted | Task 3 |
| § 9 acceptance — five-phase orchestrator | Task 4 |
| § 9 acceptance — no cache-coordinator counters | Tasks 2, 3, 5 |
| § 9 acceptance — suite green + incident dump clean | Task 6 |

---

## Risks and Open Questions

### R1. Hot-path regression from engine-mediated marker projection

Today's `MarkerComputer.Recompute` under full rebuild iterates scene quest keys once, batch-resolves targets, builds entries. Engine-mediated `MarkerCandidates` does the same work but under the query's compute context, with `ctx.Read` calls and fact recording overhead. Estimated per-frame overhead: negligible (single-digit microseconds for ambient HashSet adds). Confirm in-game via the incident dump after Task 2. If regression, optimise before Task 6 ships.

**Mitigation:** Task 1 tests include a memoisation assertion — reads with unchanged facts return instantly. Hot path is the *cached* read; the expensive compute fires only on actual fact change.

### R2. Live-state leakage into cache

If any live-state read sneaks into `MarkerCandidatesQuery.Compute` without going through a `SourceState` fact, the cached candidate list goes silently stale. Symptom: markers stop reflecting spawn state until next scene change.

**Mitigation:** Every live-state read in the query must go through `GuideReader.ReadSourceCategory(node)`, which ambient-records. Code-review gate: grep the query compute for any direct `_liveState.` access or UnityEngine time/position reads — there should be none. The query takes `GuideReader` + static compiled-guide accessors only.

### R3. `TrackerState`/`NavigationSet` fact emissions (landed in `b6870343`)

`MarkerComputer` today subscribes to `_navSet.Changed`, `_trackerState.Tracked`, `_trackerState.Untracked` and calls `MarkDirty` on each. `MarkerProjector` has no `MarkDirty`. For engine-driven invalidation to fire on nav-pin / tracker-pin changes, `NavigationSet` mutations and `TrackerState.Track`/`Untrack` must emit facts.

**Resolved in commit `b6870343`.** Dedicated `FactKind.NavSet` and `FactKind.TrackerSet` were introduced (Option B from the original choice). Each set class holds a `_factPending` flag set on any mutation and exposes `DrainPendingFacts()` which returns the single wildcard `FactKey(NavSet, "*")` or `FactKey(TrackerSet, "*")` once per batch and clears the flag. `Plugin.Update` drains both sets each frame and concatenates the drained facts onto the selector change set before invalidation; `Plugin.Awake` does the same after `OnCharacterLoaded` so first-frame restore-from-config is captured in a single invalidation batch.

Option B was chosen over the originally recommended Option A because a nav-pin change semantically has nothing to do with quest-log membership; overloading `FactKey(QuestActive, "*")` would have invalidated every subscriber to quest-log-membership on every nav click, wasting recomputation. Two dedicated enum entries cost nothing.

Corresponding `GuideReader` accessors (`ReadNavSetKeys`, `ReadTrackedQuests`) record the new fact kinds instead of `(QuestActive, "*")`. `NavigableQuestsQuery` now has clean dep tracking: `(QuestActive, "*")`, per-key `(QuestActive, dbName)`, `(NavSet, "*")`, `(TrackerSet, "*")`.

Covered by 19 new tests: `NavigationSetTests` (9), `TrackerStateTests` (8), and two `NavigableQuestsQueryTests` invalidation tests. No-op mutations (e.g. `Clear()` on empty, `Track()` of an already-tracked quest) do not emit facts — asserted in tests.

### R4. `GuideReader.ReadCurrentScene` throws outside compute

D4 introduces a non-recording `CurrentScene` property. Every top-level caller (`MarkerProjector.Project`, `NavigationTargetSelector.Tick`, `Plugin` phase methods, `Plugin.OnSceneLoaded`) must use the non-recording accessor; every in-compute caller must use `ReadCurrentScene()`. Mistaken usage throws at runtime.

**Mitigation:** `lsp references` sweep on `ReadCurrentScene` before committing Task 2. In-compute callers live in `*Query.cs` compute methods; everywhere else uses `CurrentScene`.

### R5. `MaintainedViewPlanner` tests carry coverage Task 3 doesn't directly replace

Some tests may assert specific `DiagnosticTrigger` values in plan output. Selector no longer exposes triggers that granularly. Coverage loss is acceptable if engine tests (fact→invalidation→recompute) subsume the behaviour. Any test whose assertion doesn't fit the new model: flag it, decide whether to migrate to a selector-level test or accept the coverage loss explicitly.

### R6. Namespace move breaks test discovery

`AdventureGuide.Plan` → `AdventureGuide.Frontier` rename touches ~15 test files' `using` statements. If LSP rename isn't supported for namespaces, doing it by hand is tedious and error-prone. Mitigation: treat the move as a single commit with a dedicated pre-flight check (grep `using AdventureGuide.Plan;` — should match zero files post-commit; grep `namespace AdventureGuide.Plan` — should match zero files). Test suite green is the final gate.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-ag-reactive-core-markers.md`.

All Plan-B prerequisites are satisfied. R3 (the `NavigationSet` / `TrackerState` fact-emission gap) landed in `b6870343`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Task 1 and Task 2 are the substantial tasks; Tasks 3–5 are bounded; Task 6 is integration. Plan A used this model and it worked.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`. Works but context will fill up around Task 2.

Task 1 is TDD-heavy; Task 2 is a cutover + two renames + two deletions; Task 3 is deletion + namespace sweep; Task 4 is mechanical decomposition; Task 5 is a cleanup sweep; Task 6 is verification.
