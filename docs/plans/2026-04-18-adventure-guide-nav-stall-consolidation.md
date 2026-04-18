**Superseded by `docs/plans/2026-04-18-adventure-guide-architecture-consolidation.md` on 2026-04-18.**

# AdventureGuide maintained-view consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove AdventureGuide startup, F6, and inventory-triggered hitches/stalls by replacing the current parallel maintained-view implementations with one robust core that computes quest state once, invalidates it precisely, and feeds navigation, tracker, markers, and detail UI as projections.

**Architecture:** Treat this as a start-from-scratch design exercise, then cut over cleanly. The dominant incidents today are in navigation, but the root problem is broader: multiple surfaces still own overlapping quest-resolution, caching, and invalidation behavior. The fix is one plugin-owned `QuestResolutionService` that owns scene-aware quest resolution, batching, and fact-driven invalidation; every surface consumes that service instead of instantiating or versioning its own parallel path. Diagnostics land first so the new architecture stays measurable.

**Tech Stack:** AdventureGuide mod runtime, C# / .NET, BepInEx + Harmony, current diagnostics core, `GuideChangeSet` / `GuideDependencyEngine`, xUnit, HotRepl (`uv run erenshor eval run`).

---

## Constraints and fixed decisions

- User explicitly wants a holistic architectural fix, not more piecemeal cache layers or ad hoc refresh rules.
- Consolidation is mandatory. If a new core replaces an old cache / resolver / projector layer, delete or narrow the old layer instead of keeping both reachable.
- Take a “how would I build this from scratch?” perspective. The current shape is not privileged just because it already exists.
- Use the existing fact and delta model (`GuideChangeSet`, `GuideDependencyEngine`) as the foundation instead of introducing a second invalidation system.
- Verification must cover the real cold paths: startup/F6, full tracked batch refresh, and a real inventory-triggered refresh.
- Keep implementation changes under `src/mods/AdventureGuide/`; write this plan to `docs/plans/`.
- Do not use worktrees.

## Current-system understanding this plan is based on

### Runtime evidence

- Marker cold rebuild is no longer the dominant issue. Fresh live profiling after reset measured `MarkerComputer.Recompute()` at roughly `4.399 ms` cold / `2.197 ms` hot, and `DumpLastIncidentDetailed()` returned `No incident captured.`
- Current tracker state has **12 tracked quests** and **0 explicit nav-set keys**, so the selector refresh path is effectively a tracked-quest batch path.
- Hot resolving the whole tracked batch costs about **1.233 ms total**.
- Clearing `NavigationTargetResolver` and `QuestTargetResolver` caches and resolving the same tracked batch cold costs about **2600.598 ms total**, matching the live incident pattern:
  - `quest:wally's moongill` ≈ `184.027 ms`
  - `quest:voldance` ≈ `336.843 ms`
  - `quest:percy's seaspice` ≈ `279.411 ms`
  - `quest:malarothfeedmade` ≈ `556.732 ms`
  - `quest:eldrichcrystalinfo` ≈ `1187.875 ms`
- The post-F6 incident stream is dominated by `NavSelectorTick` and nested `NavResolverResolve` spans. Marker spans are present but cheap.

### Architectural evidence from the codebase

- `Plugin.Update()` currently drives several maintained views every frame: live-state sync, marker recompute, forced selector refresh, navigation update, tracker summary reads, and detail-tree rendering.
- Inventory changes currently bump `QuestStateTracker.Version`; `Plugin.SyncCompiledQuestTracker()` mirrors that into `_compiledQuestTracker.Version`; `QuestTargetResolver` and `NavigationTargetResolver` both treat a version change as a global cache clear; `NavigationTargetSelector.Tick(...)` then re-resolves every tracked quest synchronously.
- `MarkerComputer` already has the best invalidation shape in the codebase: `GuideChangeSet` → `MarkerChangePlanner` → `AffectedQuestKeys` / incremental rebuild.
- Navigation does not. Its cold path still combines global invalidation with per-key synchronous re-resolution.
- Tracker and marker consumers already share some compiled resolution pieces, but they still allow parallel construction of quest-target infrastructure through consumer-owned constructors.
- `ViewRenderer` and `SpecTreeProjector` still maintain their own detail-projection caches and state-version rules, separate from navigation / tracker / marker resolution.
- `GuideDependencyEngine` already exists to track derived-view dependencies by fact, but quest-target caches do not currently use it as their invalidation authority.

## The design target

After this work, the system should have one answer to:

> For quest Q in scene S under current runtime facts, what is actionable, how should it be explained, and what should each surface render?

That answer should live in one maintained-view core. Surfaces should differ only in projection:
- navigation chooses and tracks a preferred target
- tracker renders a compact summary
- markers materialize scene-local instructions
- detail UI renders a tree / sectioned view

They should not each own their own cache invalidation policy, cold batching behavior, or quest-phase re-derivation.

## Planned commits

1. `feat(mod): add maintained-view batch diagnostics`
2. `refactor(mod): add shared quest resolution service`
3. `refactor(mod): move nav tracker and markers onto shared resolution`
4. `refactor(mod): move detail projection onto shared resolution`
5. `fix(mod): invalidate and refresh maintained views by facts`

These commits are sequential. Diagnostics first; then the shared core; then consumer cutovers; then fact-driven invalidation once there is only one place to invalidate.

---

### Task 1: Add diagnostics for maintained-view cold batches and invalidation scope

**Files:**
- Modify: `src/mods/AdventureGuide/src/Diagnostics/DiagnosticsTypes.cs`
- Modify: `src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs`
- Modify: `src/mods/AdventureGuide/src/Diagnostics/IncidentReportFormatter.cs`
- Modify: `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/UI/ViewRenderer.cs`
- Modify: `src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/IncidentReportFormatterTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/DebugAPIDiagnosticsTests.cs`

- [ ] **Step 1: Write failing diagnostics regressions**

Lock these behaviors in tests:
- diagnostics snapshots report the maintained-view batch scope (key count, surface, full vs partial refresh)
- navigation diagnostics expose top per-key cold costs instead of only total span duration
- detail/tree diagnostics expose cache invalidation scope, not just projected-node counts
- `DebugAPI` exposes explicit profiling helpers for maintained-view cold/hot batches

- [ ] **Step 2: Instrument maintained-view batch boundaries**

Add spans and snapshot fields for:
- selector key collection
- selector batch resolve loop
- per-key top-cost recording
- detail projection cache invalidation / rebuild scope
- cache hit / miss counts for the shared quest-resolution path once it exists

Add `DebugAPI.ProfileTrackedQuestRefresh()` and `DebugAPI.ProfileDetailProjectionRefresh()` so future debugging does not require reflection scripts.

- [ ] **Step 3: Run the diagnostics-focused cluster**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~MaintainedViewDiagnosticsTests|FullyQualifiedName~IncidentReportFormatterTests|FullyQualifiedName~DebugAPIDiagnosticsTests"
```

Expected: red before implementation, green after.

- [ ] **Step 4: Commit diagnostics first**

Run:
```bash
git add src/mods/AdventureGuide/src/Diagnostics/DiagnosticsTypes.cs \
        src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs \
        src/mods/AdventureGuide/src/Diagnostics/IncidentReportFormatter.cs \
        src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs \
        src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs \
        src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs \
        src/mods/AdventureGuide/src/UI/ViewRenderer.cs \
        src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/IncidentReportFormatterTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/DebugAPIDiagnosticsTests.cs

git commit -m "feat(mod): add maintained-view batch diagnostics"
```

---

### Task 2: Add one shared quest-resolution service and remove duplicate cache ownership

**Files:**
- Create: `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs`
- Create: `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs`
- Modify: `src/mods/AdventureGuide/src/State/GuideDerivedKey.cs`
- Modify: `src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/QuestTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs`
- Modify: `src/mods/AdventureGuide/src/UI/ViewRenderer.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionServiceTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs`

- [ ] **Step 1: Write failing service regressions**

Add tests that prove:
- one plugin-owned service caches quest-scene resolution records
- batch resolution shares one `SourceResolver.ResolutionSession` across the whole batch
- tracker, marker, navigation, and detail projection consumers do not instantiate private quest-target cache stacks anymore
- scene-aware cache keys are explicit and stable

- [ ] **Step 2: Create `QuestResolutionRecord` as the canonical maintained-view unit**

The record should carry the shared semantics surfaces need, for example:
- frontier entries
- compiled resolved targets
- precomputed tracker-summary inputs
- detail projection roots / reusable tree inputs if needed

The exact shape can adapt to the codebase, but the rule is fixed: if two surfaces need the same semantic answer, that answer lives here once.

- [ ] **Step 3: Create `QuestResolutionService` as the only cache owner**

Give the service responsibility for:
- `ResolveQuest(...)`
- `ResolveBatch(...)`
- scene-aware caching
- dependency collection for derived quest-scene records
- explicit invalidation hooks

If this service subsumes `QuestTargetResolver` cache ownership, delete the old cache boundary or reduce `QuestTargetResolver` to a pure compiler helper. Do not leave the old cache stack reachable beside the new service.

- [ ] **Step 4: Cut over consumer wiring to the service**

Rewire plugin-owned consumers so they all depend on the same service instance:
- `NavigationTargetResolver`
- `TrackerSummaryResolver`
- `MarkerQuestTargetResolver`
- `SpecTreeProjector` / `ViewRenderer`

Delete or narrow constructors that silently create their own quest-resolution stacks.

- [ ] **Step 5: Run the shared-core cluster**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~QuestResolutionServiceTests|FullyQualifiedName~NavigationTargetResolverTests|FullyQualifiedName~TrackerSummaryResolverTests|FullyQualifiedName~MarkerQuestTargetResolverTests"
```

Expected: one shared core exists before any invalidation policy changes land.

- [ ] **Step 6: Commit the core cutover**

Run:
```bash
git add src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs \
        src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs \
        src/mods/AdventureGuide/src/State/GuideDerivedKey.cs \
        src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs \
        src/mods/AdventureGuide/src/Resolution/QuestTargetResolver.cs \
        src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs \
        src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs \
        src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs \
        src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs \
        src/mods/AdventureGuide/src/UI/ViewRenderer.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionServiceTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs

git commit -m "refactor(mod): add shared quest resolution service"
```

---

### Task 3: Move navigation, tracker, and markers onto shared maintained-view projections

**Files:**
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs`
- Modify: `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetSelectorTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs`

- [ ] **Step 1: Write failing projection regressions**

Add tests that prove:
- selector forced refresh consumes batch results from the shared core, not `N` private resolves
- tracker summary uses the record produced by the shared core
- marker quest-target rebuild uses the same compiled targets / frontier record as navigation and tracker

- [ ] **Step 2: Reduce `NavigationTargetSelector` to ranking and live tracking**

Remove its ownership of the expensive per-key cold resolve loop. The selector should own:
- candidate partitioning
- mutable live-position refresh
- best-target selection

The shared core should own:
- target production
- batching
- cache reuse
- invalidation

- [ ] **Step 3: Cut tracker and markers over to shared records**

Remove duplicated summary/quest-target derivation from tracker and markers. They should read the same maintained quest record navigation reads.

- [ ] **Step 4: Run the cross-surface projection cluster**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~NavigationTargetSelectorTests|FullyQualifiedName~NavigationTargetResolverTests|FullyQualifiedName~TrackerSummaryResolverTests|FullyQualifiedName~MarkerQuestTargetResolverTests"
```

Expected: behavior stays aligned while ownership moves fully into the core.

- [ ] **Step 5: Commit the projection cutover**

Run:
```bash
git add src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs \
        src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs \
        src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs \
        src/mods/AdventureGuide/src/Markers/MarkerQuestTargetResolver.cs \
        src/mods/AdventureGuide/src/Markers/MarkerComputer.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetSelectorTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerQuestTargetResolverTests.cs

git commit -m "refactor(mod): move nav tracker and markers onto shared resolution"
```

---

### Task 4: Move detail projection onto the same shared resolution core

**Files:**
- Modify: `src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs`
- Modify: `src/mods/AdventureGuide/src/UI/ViewRenderer.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/SpecTreeProjectorTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/ViewRendererTests.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs`

- [ ] **Step 1: Write failing detail-projection regressions**

Add tests that prove:
- detail projection invalidates from the shared record / facts, not an independent projector version rule alone
- root children and detail-tree visibility are derived from the shared maintained-view inputs
- detail cache invalidation scope is observable in diagnostics

- [ ] **Step 2: Turn `SpecTreeProjector` into a projection layer**

It may still render tree refs, but it should stop acting like a second semantic-resolution owner. Feed it the shared frontier / target / visibility inputs from `QuestResolutionRecord` instead of letting it independently re-derive the maintained view from raw tracker / unlock state.

- [ ] **Step 3: Simplify `ViewRenderer` cache ownership**

After the projector cutover, `ViewRenderer` should cache rendered projection fragments only. It should no longer be the place where quest-state-version invalidation semantics are invented.

- [ ] **Step 4: Run the detail-surface cluster**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~SpecTreeProjectorTests|FullyQualifiedName~ViewRendererTests|FullyQualifiedName~MaintainedViewDiagnosticsTests"
```

Expected: detail UI becomes another projection of the shared core rather than a parallel semantic path.

- [ ] **Step 5: Commit the detail cutover**

Run:
```bash
git add src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs \
        src/mods/AdventureGuide/src/UI/ViewRenderer.cs \
        src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs \
        src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/SpecTreeProjectorTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/ViewRendererTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewDiagnosticsTests.cs

git commit -m "refactor(mod): move detail projection onto shared resolution"
```

---

### Task 5: Invalidate and refresh maintained views by facts instead of global versions

**Files:**
- Modify: `src/mods/AdventureGuide/src/State/GuideChangeSet.cs`
- Modify: `src/mods/AdventureGuide/src/State/QuestStateTracker.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/TargetSelectorRefreshPolicy.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs`
- Modify: `src/mods/AdventureGuide/src/UI/ViewRenderer.cs`
- Modify: `src/mods/AdventureGuide/src/UI/TrackerPanel.cs`
- Modify: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionServiceTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewInvalidationTests.cs`

- [ ] **Step 1: Write failing invalidation regressions**

Add tests that prove:
- inventory changes only invalidate affected quest-scene records
- unrelated tracked quests keep their cached maintained-view records
- selector refresh uses the affected subset when available
- detail / tracker caches refresh from the same invalidation authority as navigation
- full cache clears are reserved for scene changes or explicit global invalidation

- [ ] **Step 2: Feed changed facts into the shared service**

Use `GuideChangeSet.ChangedFacts` and `GuideDependencyEngine.InvalidateFacts(...)` as the cache-facing truth.

Keep the separation clean:
- fact invalidation decides which maintained-view records are stale
- `AffectedQuestKeys` decides which surface keys need refresh work
- do not invent extra ad hoc invalidation lists in individual surfaces

- [ ] **Step 3: Replace global startup / inventory / F6 refresh divergence with one batch refresh path**

In `Plugin`, route startup, F6, inventory change, quest-log change, and scene change through one helper that:
- determines key scope (`all tracked` vs affected subset)
- asks the shared core for the batch
- updates selector / tracker / detail caches from that same batch
- records diagnostics for the exact same path in every trigger case

Do not create a bespoke startup warmup path or a second inventory shortcut. One path only.

- [ ] **Step 4: Run the invalidation-focused cluster**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~QuestResolutionServiceTests|FullyQualifiedName~MaintainedViewInvalidationTests|FullyQualifiedName~NavigationTargetSelectorTests"
```

Expected: the maintained-view system refreshes narrowly when facts allow it.

- [ ] **Step 5: Commit fact-driven maintained-view refresh**

Run:
```bash
git add src/mods/AdventureGuide/src/State/GuideChangeSet.cs \
        src/mods/AdventureGuide/src/State/QuestStateTracker.cs \
        src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs \
        src/mods/AdventureGuide/src/Navigation/TargetSelectorRefreshPolicy.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs \
        src/mods/AdventureGuide/src/UI/ViewRenderer.cs \
        src/mods/AdventureGuide/src/UI/TrackerPanel.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionServiceTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MaintainedViewInvalidationTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetSelectorTests.cs

git commit -m "fix(mod): invalidate and refresh maintained views by facts"
```

---

### Task 6: End-to-end verification against the real hitch/stall scenarios

**Files:**
- Modify only if verification exposes a real defect; otherwise none.

- [ ] **Step 1: Run the full AdventureGuide test suite**

Run:
```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj
```

Expected: full suite passes.

- [ ] **Step 2: Deploy and hot reload the mod**

Run:
```bash
uv run erenshor mod deploy --mod adventure-guide --scripts
uv run erenshor eval run --timeout 30000 'var asm = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "ScriptEngine"); var type = asm.GetType("ScriptEngine.ScriptEngine"); var inst = UnityEngine.Object.FindObjectsOfTypeAll(type).First(); type.GetMethod("ReloadPlugins", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic).Invoke(inst, null); "reloaded"'
```

Expected: deploy succeeds and reload returns `reloaded`.

- [ ] **Step 3: Reproduce the tracked maintained-view batch profile**

Run the new profiling helpers hot and cold.

Expected:
- no multi-second cold tracked-quest batch
- no `NavResolverResolve` outliers in the hundreds of milliseconds for the current Stowaway tracked set
- diagnostics explicitly show full vs partial scope, top offenders, and cache behavior

- [ ] **Step 4: Verify a real inventory-triggered refresh**

Cause one real inventory change in-game, then inspect incidents and profiling output.

Expected:
- no `NavSelectorTick` / `NavResolverResolve` stall triggered by that inventory change
- tracker, detail, and markers refresh through the same maintained-view path without a second full cold rebuild

- [ ] **Step 5: Verify startup / F6 behavior**

After a fresh F6 reload, inspect incidents again.

Expected:
- no selector stall in the current Stowaway tracked-quest scenario
- startup / reload uses the same shared maintained-view batch refresh path as inventory change, not a bespoke warmup implementation

- [ ] **Step 6: Stage only intended files and verify commit format**

Run:
```bash
git status --short
git log --format=raw -1
```

Verification checklist:
- only intended AdventureGuide files are staged/committed
- generated metadata files are not committed
- latest commit formatting matches project rules
- final claims are backed by the observed full-test and runtime outputs above

---

## Definition of done

The work is complete only when all of the following are true:

- Startup, F6, and inventory-triggered refreshes all go through one shared maintained-view core rather than parallel per-surface implementations.
- The final design is a clean cutover: obsolete per-surface cache/version layers are removed or reduced to thin projections, not left reachable beside the new core.
- Navigation no longer globally clears and cold-resolves every tracked quest on routine inventory changes when changed facts identify a smaller affected subset.
- Cold tracked-quest refreshes reuse one shared resolution session across the batch, so shared prerequisite subgraphs are not recomputed once per tracked quest.
- Tracker summaries, marker quest-target rebuilds, and detail projection all consume the same maintained-view records as navigation.
- Diagnostics can show force reason, key scope, cache behavior, and top per-key batch costs for future investigations.
- Full AdventureGuide tests, hot deploy/reload, cold tracked-batch profiling, inventory-trigger verification, and startup/F6 verification have all been run and observed.
