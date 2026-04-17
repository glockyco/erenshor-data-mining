# Adventure Guide Incident Diagnostics Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> skill://superpowers:writing-plans after this spec is approved to create the
> implementation plan.

**Goal:** Make AdventureGuide frame-stall diagnostics explain what actually
stalled, preserve short hitch incidents that matter to players, and expose the
same incident detail in both the in-game panel and copyable DebugAPI output.

**Architecture:** Keep the existing rolling event/span buffers, but add a small
incident-history buffer that captures trigger metadata and correlated context at
incident time. The in-game Incident Panel becomes an incident inspector over
that history, while DebugAPI and clipboard summaries reuse the same incident
formatter so pasted reports match the live UI.

**Tech Stack:** BepInEx, ImGui.NET, existing AdventureGuide diagnostics core,
C# `Stopwatch`, ring-buffer diagnostics data, DebugAPI runtime inspection.

---

## Problem Statement

The current diagnostics redesign surfaces only one `_lastIncident` plus a short
summary string. For frame stalls, `DiagnosticsCore.EndSpan(...)` replaces
`_lastIncident` with a `FrameStall` incident whose summary looks like:

- `Span SpecTreeProjectRoot (quest:lunchbag1) exceeded the frame stall threshold.`

That part is useful, but the supporting detail is not. `FormatRecentSummary()`
then appends the last five spans from the global rolling span buffer. Those
spans are often unrelated to the actual hitch because they are whatever ran
_after_ the stall. The result is a report that says something expensive
happened, but does not preserve the expensive context.

The current system also uses a single 250 ms stall threshold. That catches only
severe hitches. Player-visible but shorter frame spikes do not get preserved as
incidents, so the diagnostics surface under-reports problems the player can
still feel.

## Non-Goals

This redesign does not add:

- persistent on-disk profiling logs
- a timeline/profiler UI
- heavyweight subsystem snapshots for every hitch by default
- broad diagnostics changes outside AdventureGuide

The goal is incident-oriented debugging, not a general-purpose profiler.

## Current Constraints

- `DiagnosticsCore` already owns rolling event and span buffers. Those buffers
  remain the source of truth for recent activity.
- `DebugAPI.CaptureIncidentNow()` already knows how to build subsystem
  snapshots, but automatic incidents currently do not retain bundles.
- `IncidentPanel` currently renders a one-line summary plus `FormatRecentSummary()`.
- `DiagnosticOverlay` must stay terse and glanceable during live play.
- Existing instrumentation points already provide span kind, primary key,
  correlation id, parent span id, and elapsed ticks.

## Design Overview

The redesign keeps the rolling diagnostics buffers, but adds a second layer: a
small incident-history ring buffer. Each incident entry stores the triggering
facts plus a bounded snapshot of the spans and events that were relevant at the
moment the incident fired. The UI and DebugAPI will render from this history,
not from "whatever the global tail happens to contain later."

The redesign also splits frame timing into two severities:

- **Hitch**: visible but not catastrophic frame spike
- **Stall**: severe frame spike

Both severities are retained in incident history. Stall remains the higher
signal and should stay highlighted in the panel/overlay.

## Data Model Changes

### 1. Incident history

Replace the single `_lastIncident`-only mental model with:

- `_lastIncident` for quick access to the newest incident
- `_incidents` ring buffer for retained history, fixed-size (recommended: 8-16)

Each incident entry should capture:

- incident kind / severity
- timestamp ticks
- summary string
- triggering span kind
- triggering span primary key
- triggering elapsed ticks
- triggering threshold ticks
- triggering correlation id
- triggering parent span id
- related spans captured at trigger time
- related events captured at trigger time
- optional snapshots

This information must be stored on the incident record itself. It must not be
reconstructed later from the mutable global tail buffers.

### 2. Trigger metadata

Frame-based incidents should store explicit trigger metadata so the user can see
exactly what crossed the threshold:

- `SpecTreeProjectRoot`
- `quest:lunchbag1`
- `134.2 ms`
- `100 ms hitch threshold`

For future expensive paths, the same model should apply to any instrumented span
kind.

### 3. Related context capture

When an incident fires, capture a bounded context window from the rolling event
and span buffers.

The capture policy should prefer:

1. spans/events sharing the same correlation id as the triggering span
2. if correlation-matched entries are sparse, nearby recent entries as fallback

This prevents reports from being dominated by unrelated low-cost spans that ran
later in the frame.

### 4. Optional snapshots

The system already has manual snapshot capture support. Automatic incidents
should support optional snapshots, but they should be selective.

Recommended behavior:

- stall incidents may include lightweight subsystem snapshots
- hitch incidents should default to trigger metadata + related spans/events only
- manual capture still captures the richest snapshot set

This avoids turning every small hitch into an expensive diagnostic operation.

## Threshold Model

Replace the single opaque tick constant with named millisecond thresholds in
`Plugin.cs` and convert them to ticks once.

Recommended defaults:

- `DiagnosticsFrameHitchThresholdMs = 100`
- `DiagnosticsFrameStallThresholdMs = 250`

Behavior:

- spans >= hitch threshold produce a hitch incident
- spans >= stall threshold produce a stall incident
- stall is considered more severe than hitch in UI emphasis

A hitch threshold of roughly 100 ms is intentional. The current 250 ms setting
is too blunt for player-visible frame spikes.

## DiagnosticsCore Responsibilities

`DiagnosticsCore` should grow from a "last incident + ring buffers" holder into
an incident capture/orchestration layer.

Responsibilities after redesign:

- retain rolling span/event buffers
- create incident entries when thresholds are crossed
- retain incident history ring buffer
- expose newest incident
- expose incident history in newest-first order
- format compact and detailed incident reports
- support manual capture that can attach to the newest incident context

It should not become a generic logging system.

## UI Design

### DiagnosticOverlay

Keep it terse.

It should continue to show only brief health/status information such as:

- current marker/nav/tracker costs
- whether a recent severe incident exists
- maybe the newest incident kind/severity

It must not become a multiline incident dump.

### IncidentPanel

Turn the panel into an incident inspector.

Recommended layout:

1. **Incident list**
   - newest first
   - age / timestamp
   - kind or severity
   - triggering span kind
   - primary key
   - duration vs threshold

2. **Selected incident detail**
   - summary
   - triggering span metadata
   - correlation id / parent span id
   - related spans
   - related events
   - optional snapshots (collapsed sections)

3. **Actions**
   - Capture now
   - Clear counters/history
   - Copy compact summary
   - Copy detailed selected incident

The user should be able to distinguish:

- what triggered the incident
- what else happened in the same correlated work
- what the system state looked like at the time

## DebugAPI / Clipboard Output

The same richer incident model should back:

- `DebugAPI.DumpPerfSummary()`
- clipboard summary output in `IncidentPanel`
- any future `DumpLastIncidentDetailed()` style helper if needed

Recommended formatter split:

- **Compact summary**: newest incident + short related-span summary
- **Detailed incident report**: selected/newest incident with trigger metadata,
  related spans, related events, and optional snapshots

The important design rule is consistency: copied text must tell the same story
as the in-game panel.

## Span-Specific Improvement Hooks

Some expensive spans should surface more domain detail in incident context.

For `SpecTreeProjectRoot`, include any already-available tree diagnostics values
that explain why the projection was expensive, such as:

- projected node count
- child count
- pruned count
- cycle prune count
- whether this was root/detail/unlock projection if that distinction is already
  available cheaply

These values should be attached only where the data already exists or can be
captured cheaply at the span end. The redesign should not introduce invasive
cross-layer coupling just to enrich one report.

## Manual Capture Semantics

`Capture now` remains useful, but it should become incident-aware.

Recommended behavior:

- if an incident exists, manual capture should enrich/report the newest incident
- if no incident exists, manual capture should snapshot the current rolling state

This makes manual capture the "freeze more detail on the thing I just saw"
button instead of a separate unrelated code path.

## Testing Strategy

Add unit coverage for:

- hitch vs stall incident creation
- incident-history retention and eviction
- captured trigger metadata
- correlation-aware related span/event capture
- summary and detailed formatter output
- panel rendering helpers if they are factored into testable methods

Keep tests focused on diagnostics behavior. Do not require live Unity runtime
for core incident-history tests.

## Acceptance Criteria

The redesign is complete when all of the following are true:

1. A frame hitch/stall no longer reports only a summary string plus unrelated
   global-tail spans.
2. The incident surface retains a bounded history instead of only one last
   incident.
3. The Incident Panel shows trigger metadata and incident-specific related
   context.
4. DebugAPI / clipboard output includes the richer incident detail.
5. Hitches below the old 250 ms threshold can be retained as incidents using a
   named lower threshold.
6. The small overlay remains concise.
7. Manual capture still works and aligns with the new incident model.

## Recommended Implementation Order

1. Extend the diagnostics types and `DiagnosticsCore` incident data model.
2. Add history retention and context capture.
3. Add formatter APIs for compact vs detailed incident output.
4. Update `IncidentPanel` to inspect history and render selected incident detail.
5. Update `DebugAPI` / clipboard actions to use the new formatter paths.
6. Add named hitch/stall thresholds in `Plugin.cs`.
7. Add regression tests for history, formatting, and threshold behavior.
