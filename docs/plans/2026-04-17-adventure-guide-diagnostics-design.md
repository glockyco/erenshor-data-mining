# Adventure Guide Diagnostics Redesign

**Date:** 2026-04-17
**Status:** Approved in chat
**Scope:** Replace AdventureGuide's current ad hoc profiling/debugging stack with a single incident-oriented diagnostics architecture that explains freezes, captures evidence automatically, and stays cheap enough to leave enabled during normal play.

---

## 1. Problem statement

AdventureGuide's current diagnostics are fragmented across four disconnected tools:

- `DebugAPI` for ad hoc HotRepl inspection
- `GuideProfiler` for per-frame timing samples
- `DiagnosticOverlay` for one-line status text
- repeated BepInEx log output from marker rebuilds

This tooling is inadequate for current failures.

### 1.1 Observed failures

The active CrossOver Steam bottle log for the running game shows repeated `Cold marker rebuild` runs after startup rather than a single isolated cold-start event. Recent player-visible failures include:

- F6 reload freezing the game for roughly a minute
- `NAV all` freezing the game for well over a minute
- HotRepl becoming unusable during the freeze window, so post hoc `eval` is not a reliable primary diagnosis path

### 1.2 Current blind spots

The current stack cannot answer the questions that matter:

- What exact event triggered the expensive work?
- Why did the work choose a full rebuild instead of an incremental path?
- Which subsystem dominated the time budget?
- How many times did the same expensive rebuild repeat during one user action?
- Did the fan-out come from marker invalidation, selector churn, target resolution, tree projection, or some combination?

### 1.3 Design goal

Make AdventureGuide self-explanatory under failure. A developer should be able to answer "what just froze the game and why?" from one coherent diagnostics system, without relying on reflection spelunking, log archaeology, or luck.

---

## 2. Goals and non-goals

### 2.1 Goals

1. Explain live freezes in the running game.
2. Preserve actionable evidence when the game becomes unresponsive.
3. Make invalidation causality explicit: every expensive span should have a trigger chain.
4. Keep normal-play overhead low and bounded.
5. Replace reflection-heavy debugging with compile-time-safe snapshot contracts for the few subsystems we actually inspect.
6. Support a **big-bang implementation cutover** on the feature branch while still landing the work as atomic commits.

### 2.2 Non-goals

1. Generic telemetry platform.
2. Remote reporting, dashboards, or streaming.
3. Persistent time-series storage.
4. Large always-on debug UIs.
5. Capturing full subsystem snapshots continuously.
6. Instrumenting every helper method in the codebase.

---

## 3. Product decision: big-bang cutover with atomic commits

The implementation should be planned as a **big-bang cutover**: the old diagnostics model and the new diagnostics model must not coexist long-term behind compatibility shims. The final branch state should have one diagnostics architecture.

That does **not** mean one giant undifferentiated commit.

### 3.1 Required commit strategy

Use atomic commits that each represent one coherent design step, for example:

1. Introduce diagnostics core types and tests.
2. Cut `Plugin` and timing paths over to the new core.
3. Cut marker/NAV producers and snapshots over.
4. Cut tracker/tree producers and snapshots over.
5. Cut UI/DebugAPI consumers over.
6. Remove `GuideProfiler`-style leftovers and repeated rebuild log spam.

### 3.2 Forbidden rollout patterns

Do not introduce:

- long-lived dual write paths
- compatibility wrappers kept "for now"
- parallel old/new profiler APIs
- stringly typed bridges from old logs to new incident records

The code should tell the truth: once the new diagnostics core exists, it becomes the only canonical source of diagnostics state.

---

## 4. Architecture overview

The redesign consists of four layers.

### 4.1 Diagnostics core

A shared runtime service owned by `Plugin`.

Responsibilities:

- store recent events and timed spans in bounded ring buffers
- manage incident detection thresholds and policies
- coordinate on-demand capture and incident bundle export
- expose recent-history and last-incident queries to UI and DebugAPI

This layer owns timing, retention, and export policy. No gameplay subsystem should implement those independently.

### 4.2 Instrumentation adapters

Small typed entry points used by hot-path systems to report events and spans to the diagnostics core.

Responsibilities:

- record cheap structured events
- wrap meaningful hot-path spans
- attach causal metadata
- avoid allocations on the common path

These adapters are not a second logging framework. They are write-only producers into the diagnostics core.

### 4.3 Typed snapshot providers

A narrow pull-based interface for subsystems worth inspecting.

Responsibilities:

- expose current subsystem state in a compile-time-safe way
- materialize snapshots only on explicit request or incident trigger
- keep snapshot scope minimal and use-case driven

This replaces reflection-heavy access as the primary debugging contract.

### 4.4 Incident consumers

Read-only views over the shared diagnostics model:

- in-game status strip
- in-game incident panel
- `DebugAPI`
- incident bundle files
- concise log summaries

The consumers present the shared data; they do not invent their own profiling state.

---

## 5. Capture model

The system records three data shapes.

### 5.1 Events

Discrete timestamped facts with small payloads.

Examples:

- `QuestLogChanged`
- `InventoryChanged`
- `SceneChanged`
- `NavSetChanged`
- `TrackedQuestSetChanged`
- `GuideChangeSetProduced`
- `MarkerRebuildRequested`
- `SelectorRefreshForced`
- `IncidentTriggered`

Events answer: **what happened?**

### 5.2 Spans

Timed begin/end records around meaningful work.

Examples:

- `LiveState.UpdateFrameState`
- `Marker.ApplyGuideChangeSet`
- `Marker.Recompute`
- `Marker.RebuildCurrentScene`
- `Marker.RebuildQuestMarkers`
- `NavResolver.Resolve`
- `NavSelector.Tick`
- `NavEngine.Update`
- `TrackerSummary.Resolve`
- `SpecTree.ProjectRoot`

Spans answer: **what was slow?**

### 5.3 Snapshots

Typed state captures gathered only on demand or on incident trigger.

Examples:

- marker invalidation state
- last `GuideChangeSet` summary
- selector cache summary
- current NAV explanation and selected target summary
- tracked quest ordering / summary inputs
- last detail-tree projection summary

Snapshots answer: **what state produced this behavior?**

---

## 6. Causality model

Causality is the key design decision. Timings without trigger chains are insufficient.

Every expensive span must carry a compact trigger reason and, where applicable, a parent operation or correlation id.

### 6.1 Example causal chain

A useful capture should be able to show something like:

- `NavSetChanged`
- `MarkerRebuildRequested(full=true, reason=NavSetChanged)`
- `Marker.Recompute`
- `Marker.RebuildCurrentScene`
- `NavSelector.Tick(force=true, reason=NavSetVersionChanged)`
- `NavResolver.Resolve(key=quest:wyland's note, targets=18)`

### 6.2 Required trigger taxonomy

Use enums or compact tagged structs, not free-text strings, for trigger reasons such as:

- `SceneChanged`
- `QuestLogChanged`
- `InventoryChanged`
- `LiveWorldChanged`
- `NavSetChanged`
- `TrackedQuestSetChanged`
- `TargetSourceVersionChanged`
- `ExplicitManualCapture`
- `IncidentAutoCapture`

Human-readable text is derived at presentation time.

---

## 7. Incident detection

The diagnostics core detects three incident classes.

### 7.1 Frame stall

Trigger when total profiled update work crosses a threshold in one frame or a short consecutive window.

Purpose:

- catch obvious hitches
- catch F6 reload freezes that block interaction

### 7.2 Rebuild storm

Trigger when the same expensive rebuild repeats too many times within a short window.

Purpose:

- directly target the repeated `Cold marker rebuild` pattern visible in the live bottle log

### 7.3 Resolution explosion

Trigger when one user action or forced refresh produces abnormal fan-out.

Examples:

- too many resolver calls from one trigger
- one resolve materializes an extreme number of targets
- `NAV all` expands into unexpectedly large per-quest target sets

### 7.4 Incident response

When an incident triggers, the system must:

1. freeze a recent window from the event/span ring buffers
2. gather typed subsystem snapshots
3. persist an incident bundle to disk
4. expose the incident as `last incident` to UI and `DebugAPI`
5. emit one concise log summary

---

## 8. Performance and retention budget

The diagnostics redesign only succeeds if it remains safe to leave enabled.

### 8.1 Retention rules

- fixed-size ring buffers only
- bounded recent-history windows
- no database
- no background uploader
- no always-on full snapshots

### 8.2 Hot-path rules

- no heap allocation in normal record calls
- no hot-path string building except fixed labels / cached names
- do not serialize JSON during ordinary operation
- expensive per-quest detail is collected only when a threshold is crossed or when incident mode is active

### 8.3 Interaction with AdventureGuide performance budget

This system is specifically intended to help verify the spec's existing performance targets, especially:

- quest frontier evaluation `<0.5ms` per affected quest
- target materialization `<1ms` per affected quest
- per-frame rendering `<1ms total`
- scene change rebuild `<50ms`

Diagnostics must not become the reason those budgets are missed.

---

## 9. Instrumentation scope

Instrument only subsystem boundaries with real diagnostic value.

### 9.1 Required producers

- `QuestStateTracker`
  - quest assigned / completed
  - inventory changed
  - scene changed
  - emitted `GuideChangeSet` summary
- `LiveStateTracker`
  - frame-state update span
  - change counts by live-world source kind
- `MarkerComputer`
  - `ApplyGuideChangeSet`
  - `Recompute`
  - `RebuildCurrentScene`
  - `RebuildQuestMarkers`
- `NavigationTargetResolver`
  - resolve count
  - target count
  - unlock-cutover count
- `NavigationTargetSelector`
  - tick span
  - forced-refresh reasons
  - key and target-entry counts
- `NavigationEngine`
  - update span
  - target changes
- `TrackerSummaryResolver`
  - resolve span
  - selected-target usage
- `SpecTreeProjector`
  - projection span
  - child/prune/cycle counts

### 9.2 Explicit exclusions

Do not instrument every internal helper or every individual tree-building branch. That would add noise and overhead without improving decision-making.

---

## 10. Snapshot scope

Only the subsystems we already inspect in debugging sessions should provide typed snapshots.

### 10.1 Marker snapshot

Must include:

- dirty/full-rebuild flags
- pending quest count
- last rebuild reason
- last rebuild total duration
- top recent expensive quest rebuilds
- recent rebuild mode history

### 10.2 NAV snapshot

Must include:

- navigation set keys
- selector version and last force reason
- cache/entry counts
- selected target summary per key
- current engine target and explanation

### 10.3 Tracker/detail snapshot

Must include:

- tracked quest count and ordering inputs
- last tracker summary inputs / selected-target usage
- last detail-tree projection summary:
  - root count
  - child count
  - pruned count
  - cycle-pruned count

Do not add snapshot providers for every subsystem by default.

---

## 11. UI and developer workflows

### 11.1 Status strip

A minimal always-available strip that shows:

- last total profiled update cost
- last marker recompute cost
- last recompute mode (`incremental` / `full`)
- tracked quest count
- NAV target count
- incident indicator

This is a health indicator, not a dashboard.

### 11.2 Incident panel

A toggleable in-game panel focused on "what just went wrong?"

Must show:

- last incident type
- trigger time
- top costly spans
- causal chain summary
- counters for:
  - full rebuild count
  - forced selector refresh count
  - resolver call count
  - targets materialized

Must provide actions for:

- capture now
- clear counters
- copy summary

### 11.3 `DebugAPI`

`DebugAPI` becomes a typed read-only adapter over the diagnostics core and snapshot providers. It should expose methods such as:

- `DumpPerfSummary()`
- `DumpLastIncident()`
- `CaptureIncidentNow()`
- `ResetPerfCounters()`
- `DumpMarkerDebugState()`
- `DumpNavDebugState()`
- `DumpTrackerDebugState()`
- `TraceQuestResolution(...)`

`TraceQuestResolution(...)` stays because it already aligns with the product spec and existing tests.

### 11.4 Offline workflow

When the game stalls or recovers after a freeze-like incident, the developer should be able to inspect one incident bundle containing:

- summary
- event/span timeline
- typed subsystem snapshots

This is necessary because HotRepl can be unavailable during the actual incident.

---

## 12. Logging policy

The current repeated marker rebuild logging pattern is not acceptable as a steady-state diagnostic strategy.

### 12.1 Required logging behavior

Keep:

- one startup diagnostics summary
- one incident summary per incident capture
- optional thresholded slow-path summaries

Remove:

- repeated "Cold marker rebuild" log spam during ordinary operation
- any logging pattern whose primary effect is to create noise without capturing causality

Logs should summarize incidents, not act as the storage layer for diagnostics.

---

## 13. File and API boundaries

### 13.1 New or expanded diagnostics files

- `src/mods/AdventureGuide/src/Diagnostics/DiagnosticsCore.cs`
- `src/mods/AdventureGuide/src/Diagnostics/DiagnosticsTypes.cs`
- `src/mods/AdventureGuide/src/Diagnostics/DiagnosticsContext.cs`
- `src/mods/AdventureGuide/src/Diagnostics/IncidentBundle.cs`
- `src/mods/AdventureGuide/src/Diagnostics/IIncidentSnapshotProvider.cs`
- `src/mods/AdventureGuide/src/Diagnostics/SubsystemSnapshots.cs`
- `src/mods/AdventureGuide/src/UI/IncidentPanel.cs`

### 13.2 Existing files to cut over

- `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs`
- `src/mods/AdventureGuide/src/Diagnostics/GuideProfiler.cs` (expected to be removed or absorbed)
- `src/mods/AdventureGuide/src/UI/DiagnosticOverlay.cs`
- `src/mods/AdventureGuide/src/Plugin.cs`
- `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs`
- `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs`
- `src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs`
- `src/mods/AdventureGuide/src/Resolution/TrackerSummaryResolver.cs`
- `src/mods/AdventureGuide/src/UI/Tree/SpecTreeProjector.cs`

### 13.3 Tests to add or update

- diagnostics core / incident detection tests
- snapshot provider tests
- `DebugAPI` diagnostics summary tests
- logging threshold / no-spam tests
- updated tracing tests if signatures change

---

## 14. Acceptance criteria

1. A live freeze or hitch produces a diagnosable incident record without relying on HotRepl responsiveness during the freeze.
2. Every expensive diagnostics span can be tied back to a causal trigger reason.
3. Marker/NAV churn can be explained from one shared diagnostics model rather than multiple disconnected tools.
4. `DebugAPI` no longer depends on reflection for core diagnostics state.
5. The status strip and incident panel expose the current health state and the last captured incident without duplicating logic.
6. Repeated rebuild log spam is removed.
7. The final branch state has one diagnostics architecture; no long-lived old/new diagnostics duality remains.
8. The work is implemented as atomic commits even though the branch strategy is a big-bang cutover.

---

## 15. Implementation guidance

Implementation should prioritize marker/NAV instrumentation first because that is where the current freezes and rebuild storms are visible. Tracker/detail-tree instrumentation should follow once incident capture works for the hot path.

The implementation plan should explicitly map each atomic commit to a coherent slice of the big-bang cutover so the branch remains reviewable even though the final merge replaces the diagnostics stack wholesale.
