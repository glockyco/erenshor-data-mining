# Adventure Guide Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AdventureGuide's fragmented debug/profiling stack with one incident-oriented diagnostics system that explains freezes, captures evidence automatically, and supports a big-bang cutover with atomic commits.

**Architecture:** Introduce a shared diagnostics core with bounded event/span buffers, causal metadata, incident detection, and typed snapshot providers. Cut producers and consumers over subsystem-by-subsystem on a feature branch, but merge only after the old diagnostics path (`GuideProfiler`, rebuild log spam, ad hoc `DebugAPI` profiling) is fully removed.

**Tech Stack:** C# (.NET / netstandard2.1 mod + net10.0 tests), BepInEx, ImGui.NET, xUnit

**Implementation strategy:** Big-bang cutover on a feature branch or worktree. Atomic commits are mandatory, but the final merged state must have exactly one diagnostics architecture.

**Planned atomic commits:**
1. `feat(mod): add incident-oriented diagnostics core`
2. `feat(mod): instrument marker rebuilds and incident snapshots`
3. `feat(mod): instrument navigation diagnostics and force reasons`
4. `feat(mod): instrument tracker and tree projection diagnostics`
5. `feat(mod): cut DebugAPI and diagnostics UI over to incident core`
6. `refactor(mod): remove legacy profiler and rebuild log spam`

---

## Task 1: Create the diagnostics core and incident model

**Files:**
- Create: `src/Diagnostics/DiagnosticsTypes.cs`
- Create: `src/Diagnostics/DiagnosticsContext.cs`
- Create: `src/Diagnostics/DiagnosticsCore.cs`
- Create: `src/Diagnostics/IncidentBundle.cs`
- Create: `src/Diagnostics/IIncidentSnapshotProvider.cs`
- Create: `src/Diagnostics/SubsystemSnapshots.cs`
- Modify: `src/Diagnostics/GuideDiagnostics.cs`
- Test: `tests/AdventureGuide.Tests/DiagnosticsCoreTests.cs`
- Test: `tests/AdventureGuide.Tests/IncidentBundleTests.cs`

All paths are relative to `src/mods/AdventureGuide/`.

- [ ] **Step 1: Write failing diagnostics core tests**

Create `tests/AdventureGuide.Tests/DiagnosticsCoreTests.cs` with tests that pin the required invariants before any implementation exists:

```csharp
using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class DiagnosticsCoreTests
{
    [Fact]
    public void RecordEvent_KeepsOnlyConfiguredRecentWindow()
    {
        var core = new DiagnosticsCore(eventCapacity: 4, spanCapacity: 4, incidentThresholds: IncidentThresholds.Disabled);

        for (int i = 0; i < 6; i++)
        {
            core.RecordEvent(new DiagnosticEvent(
                DiagnosticEventKind.NavSetChanged,
                DiagnosticsContext.Root(DiagnosticTrigger.NavSetChanged),
                timestampTicks: i,
                primaryKey: $"quest:{i}",
                value0: i,
                value1: 0));
        }

        var events = core.GetRecentEvents();
        Assert.Collection(
            events,
            e => Assert.Equal("quest:2", e.PrimaryKey),
            e => Assert.Equal("quest:3", e.PrimaryKey),
            e => Assert.Equal("quest:4", e.PrimaryKey),
            e => Assert.Equal("quest:5", e.PrimaryKey));
    }

    [Fact]
    public void EndSpan_PreservesTriggerReasonAndDuration()
    {
        var core = new DiagnosticsCore(eventCapacity: 8, spanCapacity: 8, incidentThresholds: IncidentThresholds.Disabled);
        var ctx = DiagnosticsContext.Root(DiagnosticTrigger.InventoryChanged, correlationId: 42);

        var token = core.BeginSpan(DiagnosticSpanKind.MarkerRecompute, ctx, primaryKey: "quest:a");
        core.EndSpan(token, elapsedTicks: 1234, value0: 7, value1: 1);

        var span = Assert.Single(core.GetRecentSpans());
        Assert.Equal(DiagnosticTrigger.InventoryChanged, span.Context.Trigger);
        Assert.Equal(42, span.Context.CorrelationId);
        Assert.Equal(1234, span.ElapsedTicks);
        Assert.Equal(7, span.Value0);
        Assert.Equal(1, span.Value1);
    }

    [Fact]
    public void RebuildStorm_TriggersIncidentBundleCapture()
    {
        var core = new DiagnosticsCore(
            eventCapacity: 64,
            spanCapacity: 64,
            incidentThresholds: new IncidentThresholds(frameStallTicks: long.MaxValue, rebuildStormCount: 3, rebuildStormWindowTicks: 100, resolutionExplosionTargetCount: int.MaxValue));

        for (int i = 0; i < 3; i++)
        {
            core.RecordEvent(new DiagnosticEvent(
                DiagnosticEventKind.MarkerRebuildRequested,
                DiagnosticsContext.Root(DiagnosticTrigger.LiveWorldChanged),
                timestampTicks: i * 10,
                primaryKey: "MarkerComputer",
                value0: 1,
                value1: 0));
        }

        var incident = Assert.NotNull(core.TryGetLastIncident());
        Assert.Equal(DiagnosticIncidentKind.RebuildStorm, incident.Kind);
    }
}
```

Create `tests/AdventureGuide.Tests/IncidentBundleTests.cs` with a failing export-shape test:

```csharp
using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class IncidentBundleTests
{
    [Fact]
    public void CreateBundle_CopiesEventsSpansAndSnapshots()
    {
        var bundle = IncidentBundle.Create(
            DiagnosticIncident.CreateForTests(DiagnosticIncidentKind.FrameStall, timestampTicks: 1000),
            new[] { new DiagnosticEvent(DiagnosticEventKind.SceneChanged, DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged), 900, "scene:stowaway", 0, 0) },
            new[] { new DiagnosticSpan(DiagnosticSpanKind.MarkerRecompute, DiagnosticsContext.Root(DiagnosticTrigger.SceneChanged), 910, 930, "MarkerComputer", 0, 0) },
            new SnapshotEnvelope[] { SnapshotEnvelope.Create("marker", new MarkerDiagnosticsSnapshot(fullRebuild: true, pendingQuestCount: 3, lastReason: DiagnosticTrigger.SceneChanged, lastDurationTicks: 20, topQuestCosts: Array.Empty<QuestCostSample>(), recentModes: Array.Empty<MarkerRebuildModeSample>())) });

        Assert.Equal(DiagnosticIncidentKind.FrameStall, bundle.Incident.Kind);
        Assert.Single(bundle.Events);
        Assert.Single(bundle.Spans);
        Assert.Single(bundle.Snapshots);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DiagnosticsCoreTests|FullyQualifiedName~IncidentBundleTests"
```

Expected: FAIL with missing `DiagnosticsCore`, `DiagnosticEvent`, `DiagnosticSpan`, `IncidentBundle`, and snapshot types.

- [ ] **Step 3: Implement the diagnostics substrate**

Create the shared types and bounded storage. The core API should look like this:

```csharp
namespace AdventureGuide.Diagnostics;

internal enum DiagnosticEventKind
{
    QuestLogChanged,
    InventoryChanged,
    SceneChanged,
    NavSetChanged,
    TrackedQuestSetChanged,
    GuideChangeSetProduced,
    MarkerRebuildRequested,
    SelectorRefreshForced,
    IncidentTriggered,
}

internal enum DiagnosticSpanKind
{
    LiveStateUpdateFrame,
    MarkerApplyGuideChangeSet,
    MarkerRecompute,
    MarkerRebuildCurrentScene,
    MarkerRebuildQuest,
    NavResolverResolve,
    NavSelectorTick,
    NavEngineUpdate,
    TrackerSummaryResolve,
    SpecTreeProjectRoot,
}

internal enum DiagnosticTrigger
{
    Unknown,
    SceneChanged,
    QuestLogChanged,
    InventoryChanged,
    LiveWorldChanged,
    NavSetChanged,
    TrackedQuestSetChanged,
    TargetSourceVersionChanged,
    ExplicitManualCapture,
    IncidentAutoCapture,
}

internal readonly record struct DiagnosticsContext(DiagnosticTrigger Trigger, int CorrelationId, int ParentSpanId)
{
    public static DiagnosticsContext Root(DiagnosticTrigger trigger, int correlationId = 0) => new(trigger, correlationId, parentSpanId: 0);
    public DiagnosticsContext Child(int parentSpanId) => new(Trigger, CorrelationId, parentSpanId);
}
```

`DiagnosticsCore` should own fixed-size ring buffers and incident detection:

```csharp
internal sealed class DiagnosticsCore
{
    public DiagnosticsCore(int eventCapacity, int spanCapacity, IncidentThresholds incidentThresholds) { ... }

    public void RecordEvent(DiagnosticEvent evt) { ... }
    public SpanToken BeginSpan(DiagnosticSpanKind kind, DiagnosticsContext context, string? primaryKey = null) { ... }
    public void EndSpan(SpanToken token, long elapsedTicks, int value0 = 0, int value1 = 0) { ... }

    public IReadOnlyList<DiagnosticEvent> GetRecentEvents() { ... }
    public IReadOnlyList<DiagnosticSpan> GetRecentSpans() { ... }
    public DiagnosticIncident? TryGetLastIncident() { ... }
    public IncidentBundle CaptureNow(IReadOnlyList<SnapshotEnvelope> snapshots) { ... }
}
```

`GuideDiagnostics` should stop pretending logging is the storage layer. Keep only lightweight delegates needed by logic-only code:

```csharp
internal static class GuideDiagnostics
{
    internal static Action<string>? LogInfo { get; set; }
    internal static Action<string>? LogWarning { get; set; }
    internal static Action<string>? LogError { get; set; }
}
```

Do not add any reflection-based provider lookup. Snapshot providers will be registered explicitly by `Plugin` in a later task.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DiagnosticsCoreTests|FullyQualifiedName~IncidentBundleTests"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mods/AdventureGuide/src/Diagnostics/GuideDiagnostics.cs \
        src/mods/AdventureGuide/src/Diagnostics/DiagnosticsTypes.cs \
        src/mods/AdventureGuide/src/Diagnostics/DiagnosticsContext.cs \
        src/mods/AdventureGuide/src/Diagnostics/DiagnosticsCore.cs \
        src/mods/AdventureGuide/src/Diagnostics/IncidentBundle.cs \
        src/mods/AdventureGuide/src/Diagnostics/IIncidentSnapshotProvider.cs \
        src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/DiagnosticsCoreTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/IncidentBundleTests.cs

git commit -m "feat(mod): add incident-oriented diagnostics core"
```

Commit body:

```text
AdventureGuide's current diagnostics are split across GuideProfiler,
DebugAPI helpers, overlay counters, and log spam. None of those pieces
captures causality or preserves evidence when the game wedges.

This introduces a shared diagnostics substrate with bounded event and
span buffers, typed trigger metadata, incident detection, and bundle
capture primitives. It establishes one canonical model that later
producer and consumer cutovers can build on.
```

---

## Task 2: Instrument marker invalidation and rebuilds, and expose marker snapshots

**Files:**
- Modify: `src/Markers/MarkerComputer.cs`
- Modify: `src/Plugin.cs`
- Test: `tests/AdventureGuide.Tests/MarkerDiagnosticsTests.cs`
- Test: `tests/AdventureGuide.Tests/MarkerChangePlannerTests.cs`

- [ ] **Step 1: Write failing marker diagnostics tests**

Create `tests/AdventureGuide.Tests/MarkerDiagnosticsTests.cs` with a failing test that proves full rebuild causes and top quest timings are captured:

```csharp
using AdventureGuide.Diagnostics;
using AdventureGuide.Markers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MarkerDiagnosticsTests
{
    [Fact]
    public void ApplyGuideChangeSet_RecordsFullRebuildReasonForSceneChanges()
    {
        var harness = MarkerHarness.Create();
        var core = new DiagnosticsCore(64, 64, IncidentThresholds.Disabled);
        var marker = harness.CreateMarkerComputer(core);

        marker.ApplyGuideChangeSet(new GuideChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: true,
            liveWorldChanged: false,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: Array.Empty<string>(),
            changedFacts: Array.Empty<GuideFactKey>()));

        var snapshot = marker.ExportDiagnosticsSnapshot();
        Assert.True(snapshot.FullRebuild);
        Assert.Equal(DiagnosticTrigger.SceneChanged, snapshot.LastReason);
    }

    [Fact]
    public void RebuildQuestMarkers_RecordsTopQuestCostSample()
    {
        var harness = MarkerHarness.CreateWithQuest("quest:a", dbName: "QUESTA");
        var core = new DiagnosticsCore(128, 128, IncidentThresholds.Disabled);
        var marker = harness.CreateMarkerComputer(core);

        marker.MarkDirty();
        marker.Recompute();

        var snapshot = marker.ExportDiagnosticsSnapshot();
        Assert.NotEmpty(snapshot.TopQuestCosts);
    }
}
```

If no harness exists yet, add a local one in the test file instead of introducing a new shared helper abstraction.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~MarkerDiagnosticsTests|FullyQualifiedName~MarkerChangePlannerTests"
```

Expected: FAIL because `MarkerComputer` has no diagnostics constructor path or snapshot export yet.

- [ ] **Step 3: Add marker diagnostics instrumentation**

Inject the diagnostics core into `MarkerComputer` and record:

- marker rebuild requests (`MarkerRebuildRequested`)
- `ApplyGuideChangeSet` span
- `Recompute` span
- `RebuildCurrentScene` span
- `RebuildQuestMarkers` span with per-quest timing

Add a typed marker snapshot method:

```csharp
public MarkerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
{
    return new MarkerDiagnosticsSnapshot(
        fullRebuild: _fullRebuild,
        pendingQuestCount: _pendingQuestKeys.Count,
        lastReason: _lastDiagnosticTrigger,
        lastDurationTicks: _lastRecomputeTicks,
        topQuestCosts: _recentQuestCosts.ToArray(),
        recentModes: _recentModes.ToArray());
}
```

In `Plugin`, create the core once and pass it into `MarkerComputer`.

Do not keep `GuideProfiler` writes in `MarkerComputer`. Marker diagnostics should flow only through the new core.

- [ ] **Step 4: Re-run tests**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~MarkerDiagnosticsTests|FullyQualifiedName~MarkerChangePlannerTests"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mods/AdventureGuide/src/Markers/MarkerComputer.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerDiagnosticsTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/MarkerChangePlannerTests.cs

git commit -m "feat(mod): instrument marker rebuilds and incident snapshots"
```

Commit body:

```text
The current freezes are dominated by marker invalidation and rebuild churn,
but the code does not capture why a full rebuild was requested or which
quests dominated the cost.

This instruments MarkerComputer with causal diagnostics events and spans,
and exposes a typed snapshot that can be captured live or on incident.
That gives the new diagnostics core the information needed to explain
rebuild storms instead of merely logging that they happened.
```

---

## Task 3: Instrument navigation diagnostics and expose force-refresh reasons

**Files:**
- Modify: `src/Navigation/NavigationTargetSelector.cs`
- Modify: `src/Navigation/NavigationEngine.cs`
- Modify: `src/Resolution/NavigationTargetResolver.cs`
- Modify: `src/Navigation/TargetSelectorRefreshPolicy.cs`
- Modify: `src/Plugin.cs`
- Test: `tests/AdventureGuide.Tests/NavigationDiagnosticsTests.cs`
- Modify: `tests/AdventureGuide.Tests/NavigationTargetSelectorTests.cs`
- Modify: `tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs`

- [ ] **Step 1: Write failing navigation diagnostics tests**

Create `tests/AdventureGuide.Tests/NavigationDiagnosticsTests.cs`:

```csharp
using AdventureGuide.Diagnostics;
using AdventureGuide.Navigation;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationDiagnosticsTests
{
    [Fact]
    public void Tick_RecordsForcedRefreshReason_WhenNavSetVersionChanges()
    {
        var core = new DiagnosticsCore(128, 128, IncidentThresholds.Disabled);
        var selector = NavigationHarness.CreateSelector(core);

        selector.Tick(0, 0, 0, "Stowaway", new[] { "quest:a" }, force: true, forceReason: DiagnosticTrigger.NavSetChanged);

        var span = Assert.Single(core.GetRecentSpans());
        Assert.Equal(DiagnosticSpanKind.NavSelectorTick, span.Kind);
        Assert.Equal(DiagnosticTrigger.NavSetChanged, span.Context.Trigger);
    }

    [Fact]
    public void Resolve_RecordsTargetCount_ForResolutionExplosionAccounting()
    {
        var harness = NavigationHarness.CreateResolver(coreTargets: 5);
        var results = harness.Resolver.Resolve("quest:a", "Stowaway");

        var snapshot = harness.ExportNavSnapshot();
        Assert.True(snapshot.LastResolvedTargetCount >= results.Count);
    }
}
```

Update selector/resolver tests if constructor signatures change.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~NavigationDiagnosticsTests|FullyQualifiedName~NavigationTargetSelectorTests|FullyQualifiedName~NavigationTargetResolverTests"
```

Expected: FAIL because the navigation classes do not yet accept diagnostics dependencies or expose snapshots.

- [ ] **Step 3: Add navigation instrumentation**

Make the refresh reason explicit instead of inferring it from booleans later.

Change `TargetSelectorRefreshPolicy` from a bare bool to a structured result:

```csharp
internal readonly record struct TargetSelectorRefreshDecision(bool Force, DiagnosticTrigger Reason)
{
    public static readonly TargetSelectorRefreshDecision No = new(false, DiagnosticTrigger.Unknown);
}

internal static class TargetSelectorRefreshPolicy
{
    public static TargetSelectorRefreshDecision Decide(
        bool liveWorldChanged,
        int targetSourceVersion,
        int lastTargetSourceVersion,
        int navSetVersion,
        int lastNavSetVersion)
    {
        if (liveWorldChanged)
            return new(true, DiagnosticTrigger.LiveWorldChanged);
        if (targetSourceVersion != lastTargetSourceVersion)
            return new(true, DiagnosticTrigger.TargetSourceVersionChanged);
        if (navSetVersion != lastNavSetVersion)
            return new(true, DiagnosticTrigger.NavSetChanged);
        return TargetSelectorRefreshDecision.No;
    }
}
```

Instrument:

- `NavigationTargetSelector.Tick`
- `NavigationTargetResolver.Resolve`
- `NavigationEngine.Update`

Expose a navigation snapshot with:

- last force reason
- cache entry count
- current engine target
- last resolved target count
- selected target summaries

- [ ] **Step 4: Re-run tests**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~NavigationDiagnosticsTests|FullyQualifiedName~NavigationTargetSelectorTests|FullyQualifiedName~NavigationTargetResolverTests"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs \
        src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs \
        src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs \
        src/mods/AdventureGuide/src/Navigation/TargetSelectorRefreshPolicy.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationDiagnosticsTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetSelectorTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/NavigationTargetResolverTests.cs

git commit -m "feat(mod): instrument navigation diagnostics and force reasons"
```

Commit body:

```text
NAV-all freezes are not diagnosable with the current selector and resolver
code because force-refresh reasons are implicit and target fan-out is not
captured.

This makes selector refresh decisions explicit, records navigation spans
and counts into the diagnostics core, and exposes a typed navigation
snapshot so incidents can explain whether the freeze came from selector
churn, target resolution fan-out, or engine target updates.
```

---

## Task 4: Instrument tracker and tree projection diagnostics

**Files:**
- Modify: `src/Resolution/TrackerSummaryResolver.cs`
- Modify: `src/UI/TrackerPanel.cs`
- Modify: `src/UI/Tree/SpecTreeProjector.cs`
- Modify: `src/Plugin.cs`
- Test: `tests/AdventureGuide.Tests/TrackerDiagnosticsTests.cs`
- Modify: `tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs`
- Modify: `tests/AdventureGuide.Tests/SpecTreeProjectorTests.cs`

- [ ] **Step 1: Write failing tracker/tree diagnostics tests**

Create `tests/AdventureGuide.Tests/TrackerDiagnosticsTests.cs`:

```csharp
using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerDiagnosticsTests
{
    [Fact]
    public void Resolve_RecordsPreferredTargetUsageInSnapshot()
    {
        var harness = TrackerHarness.Create();
        var summary = harness.Resolver.Resolve("QUESTA", "QUESTA", "Stowaway", preferredTarget: harness.PreferredTarget, tracker: harness.StateTracker);

        var snapshot = harness.ExportTrackerSnapshot();
        Assert.True(snapshot.LastResolveUsedPreferredTarget);
        Assert.NotNull(summary);
    }

    [Fact]
    public void ProjectRoot_RecordsPruneAndCycleCounts()
    {
        var harness = SpecTreeHarness.CreateRecursiveCase();
        var roots = harness.Projector.GetRootChildren(harness.RootQuestIndex);

        var snapshot = harness.ExportTreeSnapshot();
        Assert.True(snapshot.LastProjectedNodeCount >= roots.Count);
        Assert.True(snapshot.LastCyclePruneCount >= 1);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~TrackerDiagnosticsTests|FullyQualifiedName~TrackerSummaryResolverTests|FullyQualifiedName~SpecTreeProjectorTests"
```

Expected: FAIL because tracker/tree diagnostics exports do not exist yet.

- [ ] **Step 3: Add tracker and tree diagnostics**

Instrument `TrackerSummaryResolver.Resolve` and `SpecTreeProjector` projection entry points. Expose typed snapshots instead of ad hoc booleans on the UI layer:

```csharp
public TrackerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
{
    return new TrackerDiagnosticsSnapshot(
        trackedQuestCount: _trackerState.TrackedQuests.Count,
        lastResolveQuestKey: _lastResolveQuestKey,
        lastResolveUsedPreferredTarget: _lastResolveUsedPreferredTarget,
        lastSummaryText: _lastSummaryText);
}

public SpecTreeDiagnosticsSnapshot ExportDiagnosticsSnapshot()
{
    return new SpecTreeDiagnosticsSnapshot(
        lastProjectedNodeCount: _lastProjectedNodeCount,
        lastChildCount: _lastChildCount,
        lastPrunedCount: _lastPrunedCount,
        lastCyclePruneCount: _lastCyclePruneCount);
}
```

Do not put diagnostics state into `TrackerPanel`. The UI should consume typed snapshots from the logic components.

- [ ] **Step 4: Re-run tests**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~TrackerDiagnosticsTests|FullyQualifiedName~TrackerSummaryResolverTests|FullyQualifiedName~SpecTreeProjectorTests"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs \
        src/mods/AdventureGuide/src/UI/TrackerPanel.cs \
        src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerDiagnosticsTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSummaryResolverTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/SpecTreeProjectorTests.cs

git commit -m "feat(mod): instrument tracker and tree projection diagnostics"
```

Commit body:

```text
Marker and navigation captures are not enough on their own. The tracker and
detail tree are two other surfaces where transitive requirement work can fan
out and become expensive.

This instruments tracker summary resolution and detail-tree projection,
exposes typed snapshots for both subsystems, and keeps the state anchored in
logic-layer components rather than the IMGUI views that render them.
```

---

## Task 5: Cut DebugAPI and the diagnostics UI over to the new core

**Files:**
- Modify: `src/Diagnostics/DebugAPI.cs`
- Modify: `src/UI/DiagnosticOverlay.cs`
- Create: `src/UI/IncidentPanel.cs`
- Modify: `src/Config/GuideConfig.cs`
- Modify: `src/Plugin.cs`
- Modify: `src/Diagnostics/TextResolutionTracer.cs` (only if naming/signatures need cleanup)
- Test: `tests/AdventureGuide.Tests/DebugAPIDiagnosticsTests.cs`
- Modify: `tests/AdventureGuide.Tests/ResolutionTracerTests.cs`

- [ ] **Step 1: Write failing DebugAPI diagnostics tests**

Create `tests/AdventureGuide.Tests/DebugAPIDiagnosticsTests.cs`:

```csharp
using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class DebugAPIDiagnosticsTests
{
    [Fact]
    public void DumpPerfSummary_ReturnsIncidentAwareSummary()
    {
        var core = DiagnosticsHarness.CreateCoreWithIncident();
        DebugAPI.Diagnostics = core;

        string text = DebugAPI.DumpPerfSummary();

        Assert.Contains("last incident", text, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("MarkerRecompute", text, StringComparison.Ordinal);
    }

    [Fact]
    public void DumpLastIncident_ReturnsNoIncident_WhenNothingCaptured()
    {
        DebugAPI.Diagnostics = new DiagnosticsCore(16, 16, IncidentThresholds.Disabled);

        Assert.Contains("No incident", DebugAPI.DumpLastIncident(), StringComparison.OrdinalIgnoreCase);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DebugAPIDiagnosticsTests|FullyQualifiedName~ResolutionTracerTests"
```

Expected: FAIL because `DebugAPI` does not yet route through the diagnostics core.

- [ ] **Step 3: Replace bespoke DebugAPI profiling and expand the diagnostics UI**

Refactor `DebugAPI` to read from the diagnostics core and snapshot providers instead of owning profiling logic itself:

```csharp
public static class DebugAPI
{
    internal static DiagnosticsCore? Diagnostics { get; set; }
    internal static Func<MarkerDiagnosticsSnapshot>? MarkerSnapshot { get; set; }
    internal static Func<NavigationDiagnosticsSnapshot>? NavSnapshot { get; set; }
    internal static Func<TrackerDiagnosticsSnapshot>? TrackerSnapshot { get; set; }
    internal static Func<SpecTreeDiagnosticsSnapshot>? TreeSnapshot { get; set; }

    public static string DumpPerfSummary() => Diagnostics == null
        ? "Not initialized"
        : Diagnostics.FormatRecentSummary();

    public static string DumpLastIncident() => Diagnostics == null
        ? "Not initialized"
        : Diagnostics.FormatLastIncidentSummary();

    public static string CaptureIncidentNow() => Diagnostics == null
        ? "Not initialized"
        : Diagnostics.CaptureNow(BuildSnapshots()).Summary;
}
```

Change `DiagnosticOverlay` into the thin status strip only. Add `IncidentPanel` for:

- last incident type and time
- top spans
- cause chain
- counters
- manual capture / clear buttons

Add one config entry for toggling the incident panel, but do not add a large diagnostics feature matrix. Keep the UI deliberately small.

- [ ] **Step 4: Re-run tests**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DebugAPIDiagnosticsTests|FullyQualifiedName~ResolutionTracerTests"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs \
        src/mods/AdventureGuide/src/UI/DiagnosticOverlay.cs \
        src/mods/AdventureGuide/src/UI/IncidentPanel.cs \
        src/mods/AdventureGuide/src/Config/GuideConfig.cs \
        src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/src/Diagnostics/TextResolutionTracer.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/DebugAPIDiagnosticsTests.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/ResolutionTracerTests.cs

git commit -m "feat(mod): cut DebugAPI and diagnostics UI over to incident core"
```

Commit body:

```text
The old diagnostics consumers were islands: DebugAPI had its own profiling
logic, the overlay showed one coarse line of text, and neither surface could
explain the last stall coherently.

This cuts both DebugAPI and the in-game diagnostics UI over to the shared
incident-oriented core so they present one consistent view of recent work,
last incident, and typed subsystem snapshots.
```

---

## Task 6: Remove legacy profiler/log spam and verify the big-bang cutover

**Files:**
- Delete: `src/Diagnostics/GuideProfiler.cs`
- Modify: `src/Plugin.cs`
- Modify: `src/Markers/MarkerComputer.cs`
- Modify: `src/UI/DiagnosticOverlay.cs`
- Modify: `src/Diagnostics/DebugAPI.cs`
- Test: `tests/AdventureGuide.Tests/DiagnosticsLoggingTests.cs`

- [ ] **Step 1: Write a failing no-spam logging test**

Create `tests/AdventureGuide.Tests/DiagnosticsLoggingTests.cs`:

```csharp
using AdventureGuide.Diagnostics;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class DiagnosticsLoggingTests
{
    [Fact]
    public void RepeatedMarkerRecomputes_DoNotEmitPerLoopColdRebuildSpam()
    {
        var logs = new List<string>();
        GuideDiagnostics.LogInfo = logs.Add;

        var core = new DiagnosticsCore(64, 64, IncidentThresholds.Disabled);
        var harness = MarkerHarness.Create();
        var marker = harness.CreateMarkerComputer(core);

        for (int i = 0; i < 5; i++)
        {
            marker.MarkDirty();
            marker.Recompute();
        }

        Assert.DoesNotContain(logs, line => line.Contains("Cold marker rebuild", StringComparison.Ordinal));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DiagnosticsLoggingTests"
```

Expected: FAIL while the old repeated logging path still exists.

- [ ] **Step 3: Delete the legacy profiler and replace log spam with summaries**

Remove `GuideProfiler.cs` entirely. Remove `GuideProfiler.*.Record(...)` calls and the repeated `Cold marker rebuild` logging pattern.

Keep only:

- one startup diagnostics summary
- one incident summary per captured incident
- optional thresholded slow-path summaries

`Plugin.Update()` should use the new diagnostics core instead of `GuideProfiler`:

```csharp
var ctx = DiagnosticsContext.Root(DiagnosticTrigger.LiveWorldChanged, correlationId: _frameCorrelationId++);
var token = _diagnostics.BeginSpan(DiagnosticSpanKind.NavSelectorTick, ctx, primaryKey: _navEngine!.CurrentScene);
_targetSelector?.Tick(...);
_diagnostics.EndSpan(token, Stopwatch.GetTimestamp() - startTick, value0: _navSet!.Count, value1: _targetSelector!.Version);
```

- [ ] **Step 4: Run targeted diagnostics tests**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --filter "FullyQualifiedName~DiagnosticsCoreTests|FullyQualifiedName~IncidentBundleTests|FullyQualifiedName~MarkerDiagnosticsTests|FullyQualifiedName~NavigationDiagnosticsTests|FullyQualifiedName~TrackerDiagnosticsTests|FullyQualifiedName~DebugAPIDiagnosticsTests|FullyQualifiedName~DiagnosticsLoggingTests"
```

Expected: PASS.

- [ ] **Step 5: Run the full AdventureGuide test suite**

Run:

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj
```

Expected: PASS.

- [ ] **Step 6: Manual runtime verification in the CrossOver Steam bottle**

Verify all of the following in the running game:

1. F6 reload produces a single startup diagnostics summary and no repeating `Cold marker rebuild` spam.
2. Triggering `NAV all` either remains responsive or captures an incident bundle with:
   - incident type
   - top spans
   - causal chain
   - marker/nav snapshot data
3. `AdventureGuide.Diagnostics.DebugAPI.DumpPerfSummary()` returns recent diagnostics-state text rather than timing counters from the deleted profiler.
4. `AdventureGuide.Diagnostics.DebugAPI.DumpLastIncident()` returns the captured incident summary after a forced reproduction.

- [ ] **Step 7: Commit**

```bash
git add src/mods/AdventureGuide/src/Plugin.cs \
        src/mods/AdventureGuide/src/Markers/MarkerComputer.cs \
        src/mods/AdventureGuide/src/UI/DiagnosticOverlay.cs \
        src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs \
        src/mods/AdventureGuide/tests/AdventureGuide.Tests/DiagnosticsLoggingTests.cs

git rm src/mods/AdventureGuide/src/Diagnostics/GuideProfiler.cs

git commit -m "refactor(mod): remove legacy profiler and rebuild log spam"
```

Commit body:

```text
The old diagnostics path survived too long as a parallel truth source. The
shared incident-oriented diagnostics core is now the canonical model, so the
legacy GuideProfiler and repeated cold-rebuild logging are design debt.

This removes the old profiler, replaces steady-state log spam with concise
summaries, and completes the big-bang cutover to a single diagnostics
architecture.
```

---

## Final verification checklist

- [ ] `GuideProfiler.cs` is deleted and no `GuideProfiler.` references remain.
- [ ] `DebugAPI` reads diagnostics state from the shared core and typed snapshot providers.
- [ ] `MarkerComputer`, `NavigationTargetSelector`, `NavigationTargetResolver`, `NavigationEngine`, `TrackerSummaryResolver`, and `SpecTreeProjector` all emit diagnostics data through the shared core.
- [ ] The diagnostics UI consists of a slim status strip plus the incident panel; no large always-on observability suite was added.
- [ ] The CrossOver Steam bottle log no longer floods with repeated `Cold marker rebuild` messages.
- [ ] The final branch state contains one diagnostics architecture with no compatibility shims.
