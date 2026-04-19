# AdventureGuide Reactive Core — Group 1 Design Spec

**Date:** 2026-04-19
**Status:** Approved in chat
**Scope:** Design of the incremental engine, the derived views that replace the current caching bag, and the Plugin update orchestrator that drives them. Resolves audit themes T2, T3, T4 and audit questions Q1, Q5. Sits under the program spec `2026-04-19-adventure-guide-overhaul-program.md`.

This spec records design decisions only. The migration itself — the ordered sequence of commits that ships these decisions without breaking the mod — lives in the companion implementation plan at `docs/superpowers/plans/`.

---

## 1. Purpose

AdventureGuide today mixes five distinct cache-invalidation patterns (version counters, reference identity, dirty flags, implicit detection, fact deltas) across its subsystems. Only one derived view (`QuestResolutionService._cache`) participates in the typed fact system; the rest invalidate coarsely. A long orchestrator in `Plugin.Update()` threads these patterns together with implicit ordering and no tests.

This spec replaces all of that with one incremental engine, five derived views expressed as engine queries, and an explicit five-phase orchestrator. Every consumer that needs computed state reads the engine; facts are the only invalidation currency. The five patterns collapse to one.

The engine is also designed under the program's extraction constraints (§ 8 of the program spec): own namespace, zero Erenshor types on its public API surface. This keeps a future extraction open without committing the program to one.

## 2. Audit question resolutions

### Q1 — `QuestResolutionRecord` snapshots

**Resolved: drop the snapshots.**

`QuestResolutionRecord` today snapshots quest phase and item counts at construction time, but resolution-time code paths read the live trackers directly. The two representations diverge whenever state changes between record creation and read.

Under the new model the update loop is synchronous and single-threaded. Consumers reading computed state read engine queries; the engine records fact dependencies for whatever the query touches. The record no longer owns snapshots — it holds only the composed result for one `(questKey, currentScene)` pair. Staleness is impossible because the engine invalidates the record when any fact it depended on changes.

### Q5 — `MaintainedViewPlanner`

**Resolved: retire entirely.**

The planner's job today is to decide full-vs-partial marker rebuild from a coarse change set. The engine's dependency graph returns the precise set of affected queries for any fact delta, and re-renders read from the engine. Every Full / Partial / None branch the planner currently produces is subsumed by lazy recomputation of exactly the affected queries. No translator survives; the planner and its plan type are deleted.

## 3. The incremental engine

### 3.1 Shape

Salsa-shaped, not signals-shaped. The engine holds a collection of **query definitions**. A query is a function `(QueryContext, TKey) -> TValue`. The engine memoises each `(query, key)` pair and recomputes it on read iff some fact the last computation depended on has changed since.

Parametric views (one query per quest, one per scene) map onto `(query, key)` cache entries naturally. Signal/atom models would need a memo-factory per parameterised family and lose the uniform cache shape.

### 3.2 Public API surface

```csharp
namespace AdventureGuide.Incremental;

public sealed class IncrementalEngine<TFactKey> where TFactKey : notnull
{
    public Query<TKey, TValue> DefineQuery<TKey, TValue>(
        string name,
        Func<QueryContext<TFactKey>, TKey, TValue> compute);

    public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key);

    public IReadOnlyCollection<QueryRef> InvalidateFacts(IEnumerable<TFactKey> changed);
}

public sealed class QueryContext<TFactKey>
{
    public void RecordFact(TFactKey fact);
    public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key);
}
```

The engine is generic over the fact key type. Erenshor's `GuideFactKey` appears nowhere on this surface. An Erenshor-specific thin wrapper in `AdventureGuide.State` (working name `GuideQueryReader`) holds a `QueryContext<GuideFactKey>` and exposes typed accessors per fact kind (e.g. `ReadInventoryCount(string itemId)`), which call `RecordFact` under the hood.

### 3.3 Recording facts

Fact reads and query reads are asymmetric by design:

- **Facts are recorded explicitly** via `RecordFact(TFactKey)`. Fact values live in the trackers — the engine does not own them. The wrapper pattern (`GuideQueryReader.ReadQuestPhase(key)`) makes the explicit record ergonomic: the wrapper records the dep and forwards to the tracker.
- **Query-to-query reads are transparent** via `QueryContext.Read(query, key)`. The engine sees every query read and stitches the dependency automatically. Query return types are strongly typed.

Heterogeneous fact value types (ints, strings, bools, structs) would force the engine into an untyped `object`-based API if it owned facts. Keeping fact values in trackers preserves the typed accessor pattern where each accessor returns the natural type.

### 3.4 Revisions, backdating, lazy recomputation

Every fact change bumps a monotonic revision. Each cached query entry records the revisions of the facts and sub-queries it read. On `Read`, the engine walks the dependency graph: if any recorded dep is stale, the query recomputes; otherwise the cached value is returned.

After recomputation the engine compares the new value against the previous one by value equality. If equal, the revision stays unchanged and no dependent is marked stale. This is **backdating**. It is load-bearing: it is what lets a fine-grained fact delta collapse the bag of five invalidation patterns into one — upstream fires a fact delta, the engine recomputes the small set of queries that depended on it, and only the queries whose output actually changed ripple further.

Recomputation is **lazy**. `InvalidateFacts` marks affected entries stale without recomputing them. The actual work happens on the next `Read` from a consumer. Consumers that don't read during a given frame pay nothing for invalidations that touched their queries.

### 3.5 Equality discipline (acceptance criterion)

Backdating only works when query return types implement value equality. This is a hard design criterion for Group 1:

- Every type used as a query return value **must** provide value equality.
- Domain types (`QuestResolutionRecord`, `MarkerCandidate`, compiled frontiers, etc.) become `record` or `record struct`.
- Collection return values use engine-provided structural comparers, or return `ImmutableArray<T>`/`ImmutableDictionary<TK,TV>` with structural equality helpers.

A query that returns a reference type without value equality silently defeats backdating — every recompute looks like a change, every dependent re-fires. This criterion is non-negotiable; a violation is a design bug, not a performance tuning knob.

### 3.6 Engine lifetime and eviction

One engine per plugin lifetime. The engine outlives scene changes; scene-scoped cache entries for old scenes stay resident. No eviction policy in v1 — cache growth is bounded by the number of quests and the number of scenes the player visits in one session. If growth becomes a concern, eviction is additive and designed later.

### 3.7 Threading

Single-threaded, synchronous. Driven entirely from the Unity main thread via `Plugin.Update`. No reentrancy, no concurrent queries, no locks.

### 3.8 Cycle detection

Cycles in the dependency graph indicate a design bug, not a runtime condition to recover from. The engine throws on detection. Cycles are caught during development, not tolerated at runtime.

## 4. The five queries

The current quest-resolution pipeline becomes five engine queries. Names are illustrative; final names are decided during implementation.

### 4.1 `QuestCompiledTargets(questKey)` — frontier and compiled targets

Walks the frontier for one quest and produces the compiled target list. Reads facts: `QuestActive(questKey)`, `QuestCompleted(questKey)`, `InventoryItemCount(*)` and `UnlockItemPossessed(*)` touched during the walk, `SourceState(*)` for nodes visited.

**No `Scene` dependency.** The frontier walk is scene-independent; scene filtering happens downstream. This is an audit pre-req (see § 7) — confirmed by reading `QuestTargetResolver.Resolve` during implementation.

### 4.2 `BlockingZonesForScene(currentScene)` — zone-line blockers

For a given scene, returns the map of zone-line nodes the player currently cannot cross, keyed by target scene with the blocking reason. Reads facts: `SourceState(zoneLineNodeKey)` for each zone line in the scene, plus whatever the blocker evaluation touches (item possession, unlock state).

Keyed on scene. One cache entry per scene the player visits.

### 4.3 `NavigableQuestKeys()` — singleton quest set

The set of quest keys that contribute navigation targets. Reads facts: all `QuestActive(*)` plus tracker-state facts that gate inclusion. Singleton (no key parameter).

### 4.4 `QuestResolution(questKey, currentScene)` — composed record

Composes `QuestCompiledTargets(questKey)` and `BlockingZonesForScene(currentScene)` into a `QuestResolutionRecord` for the requested `(quest, scene)` pair. Reads no facts directly — its deps are exactly the two sub-queries. This is where scene filtering collapses the scene-independent frontier into a scene-specific resolution.

### 4.5 `MarkerCandidatesForScene(currentScene)` — marker projection

Produces the marker-candidate list for the current scene. Reads `NavigableQuestKeys()` to iterate navigable quests, reads `QuestResolution(questKey, currentScene)` for each, plus `SourceState` for each scene node it considers materialising as a marker.

Keyed on scene.

### 4.6 Dependency topology

```
MarkerCandidatesForScene(scene)
  ├── NavigableQuestKeys()
  │     └── facts: QuestActive(*), TrackerState(*)
  └── QuestResolution(questKey, scene)
        ├── QuestCompiledTargets(questKey)
        │     └── facts: QuestActive, QuestCompleted, Inventory, Unlock, SourceState
        └── BlockingZonesForScene(scene)
              └── facts: SourceState(zoneLineNode)
```

`MarkerComputer` no longer holds `_dirty`, `_fullRebuild`, `MarkDirty`, or `ApplyGuideChangeSet`. Its per-frame work is: read `MarkerCandidatesForScene(currentScene)` from the engine, apply the result to the rendering layer.

## 5. The Plugin update orchestrator

### 5.1 Five phases

`Plugin.Update` becomes an orchestrator that runs five named phases per frame, in order:

1. **Capture** — trackers read live game state into their internal representations. No engine interaction.
2. **Publish** — trackers emit the `GuideFactKey` set that changed this frame. Scene change is part of this set (`GuideFactKey(Scene, "current")`) — it is not a special path.
3. **Invalidate** — `engine.InvalidateFacts(changedFacts)` marks affected entries stale. Returns the affected set for diagnostics only; no branching logic depends on it.
4. **Recompute (lazy)** — consumers read what they need. Each read triggers recomputation only for entries whose deps are actually stale, with backdating cutting ripples.
5. **Render** — per-frame rendering/UI work consumes the results.

Each phase is a method; each method gets a diagnostics span. Phase boundaries become the seam Group 4 builds on.

### 5.2 Scene change handling

Scene change is a fact, not a special path. `Plugin.Update` today branches on scene equality to call `InvalidateAll`; that branch is deleted. The trackers emit `GuideFactKey(Scene, "current")` when the scene changes; the engine invalidates every cached entry that read the `Scene` fact; next read produces a fresh resolution against the new scene. Entries for other scenes stay cached.

### 5.3 Version counters and dirty flags removed

Every version counter and dirty flag currently coordinating cache freshness across `Plugin`, `QuestResolutionService`, `MaintainedViewPlanner`, `MarkerComputer`, `NavigationTargetSelector` is deleted. The engine's revision-based invalidation replaces all of them.

## 6. Extraction-friendliness (reiterated)

The engine lives in its own namespace `AdventureGuide.Incremental`. Its public API (§ 3.2) is generic over `TFactKey` and names no Erenshor types. Internal implementation details may reference whatever is convenient — the constraint is about the surface an external consumer would depend on.

The thin wrapper `GuideQueryReader` in `AdventureGuide.State` is the single location that binds the engine to Erenshor. Query *definitions* live in mod code (e.g. `AdventureGuide.Resolution.Queries`); they are consumers of the engine, not part of it.

Extraction itself is not a goal of Group 1 or of the overhaul program. The constraint only ensures that an extraction decision, if made later, is not blocked by incidental coupling.

## 7. Audit pre-requisite

Before the query signatures are finalised, one detail must be confirmed by reading the source: `QuestTargetResolver.Resolve(questIndex, currentScene, ...)` receives `currentScene` as a parameter. If it uses scene only for filtering the compiled target list, § 4.1 stands — `QuestCompiledTargets(questKey)` is truly scene-independent, scene filtering lives in `QuestResolution(questKey, scene)`. If it uses scene during emission (the walk itself differs by scene), `QuestCompiledTargets` must key on `(questKey, scene)` instead, multiplying cache entries by scene count.

This is a short, bounded read during implementation. The outcome shapes cache structure, not the rest of the design.

## 8. Acceptance criteria

Group 1 is complete when all of the following hold against a running mod:

- `AdventureGuide.Incremental` namespace exists; its public API references no Erenshor types.
- Every invalidation path in the mod goes through the engine. No version counters, dirty flags, reference-identity checks, or implicit-detection patterns remain coordinating cache freshness.
- `GuideDependencyEngine`, `GuideDerivedKey`, `GuideDerivedKind`, `MaintainedViewPlanner`, and `MaintainedViewPlan` are deleted. `QuestResolutionRecord` no longer holds phase or item-count snapshots.
- `Plugin.Update` is a five-phase orchestrator; each phase is a named method; each has a diagnostics span.
- Every type used as a query return value provides value equality.
- Test suite stays green. New tests cover engine semantics (memoisation, lazy recompute, backdating, fact invalidation, cycle detection throw) and at least one query end-to-end.
- Incident dump under representative scene load shows no new `FrameStall` or `FrameHitch` compared to program-start behaviour.
- The audit's T2, T3, T4 "what this blocks" narratives no longer hold.

---

## Appendix A — Design alternatives considered and rejected

### Signals/atoms model (Jotai-shaped)

Each derived view an atom; reading an atom inside another subscribes transparently. Rejected: parametric views (one resolution per quest, one marker set per scene) need a memo-factory per family, losing the uniform cache shape that Salsa's `(query, key)` table provides. Equality-backed backdating is the same in both models.

### Engine owns fact values

The engine would expose `GetFact<T>(key)` and trackers would push values in. Rejected: `GuideFactKey` carries heterogeneous value types. A generic `T` on the key type forces boxing or an untyped `object`-valued API. Keeping values in trackers preserves natural typed accessors.

### Eager recomputation on invalidation

`InvalidateFacts` recomputes stale entries immediately. Rejected: consumers that skip a frame (panel closed, marker system disabled) would pay for work no one reads. Laziness is free correctness-wise (single-threaded, no cross-frame visibility) and lets consumer structure drive cost.

### `MaintainedViewPlanner` as thin translator

Keep the planner as a translator between engine affected-sets and marker-system rebuild hints. Rejected: the engine already returns the affected-views set; the planner would forward it untouched. Every line of the planner becomes dead.

## Appendix B — Related documents

| Document | Role |
|---|---|
| `docs/superpowers/specs/2026-04-19-adventure-guide-overhaul-program.md` | Program spec — Group 1 is one of four groups |
| `docs/superpowers/specs/2026-04-18-adventure-guide-architecture-audit.md` | Audit — authoritative evidence for T2, T3, T4, Q1, Q5 |
| `docs/superpowers/plans/` (forthcoming) | Implementation plan for this design |
