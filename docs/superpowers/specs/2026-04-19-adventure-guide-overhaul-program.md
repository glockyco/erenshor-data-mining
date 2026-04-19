# AdventureGuide Overhaul — Program Spec

**Date:** 2026-04-19
**Status:** Approved in chat
**Scope:** Meta-document organizing how the AdventureGuide architecture overhaul proceeds. Addresses all 11 themes identified in the 2026-04-18 architecture audit plus the TimeOfDay correctness bug, and sets the constraints under which the incremental engine that emerges from the reactive-core work is designed for possible future extraction.

---

## 1. Purpose

This spec decomposes the AdventureGuide architecture overhaul into coupled design groups, orders them by dependency, and records the meta-decisions (scope, ordering, extraction constraints, lifecycle gates) so each per-group brainstorming session can focus on real architectural calls instead of re-deciding shared structure.

It does **not** make per-group design decisions. Those happen in each group's own brainstorming session, which produces its own design spec at `docs/superpowers/specs/`.

Full per-theme evidence (file:line citations, "evidence of pain", "what this blocks", detailed suggested fixes) lives in the companion document `docs/superpowers/specs/2026-04-18-adventure-guide-architecture-audit.md`. This program spec summarises each theme only deeply enough to orient someone starting a group session; they consult the audit for detail.

## 2. Scope

**In scope:**
- All 11 audit themes (T1–T11), summarised in § 3
- TimeOfDay fact correctness bug (§ 3.1)
- An incremental engine — emerging from Group 1 — designed under constraints (§ 8) that keep future extraction possible

**Deferred to after program completion:**
- **T9** ImGui/ILRepack spike — research task; outcome may eliminate ~700 LOC of rendering code or confirm the workaround is structural
- Engine extraction to a standalone repository — evaluated only after all 4 groups + cleanup stream complete; explicitly nice-to-have, abandonable without regret if the API did not generalize cleanly

**Out of scope:**
- Speculative roadmap features. The audit addresses what exists today; so does this program.

## 3. Findings catalogue

Each entry below is a brief orientation. The audit is the authoritative source for evidence and detailed shape-of-fix; direction notes here are high-level steers that each group's brainstorming session may revisit.

### 3.1 TimeOfDay fact correctness bug *(cleanup-stream)*

The `TimeOfDay` fact in `LiveStateTracker` emits the same sub-key on both day→night and night→day transitions, so dependents cannot distinguish the direction, and a dependent registered on the opposite sub-key would never be invalidated. The sole current dependent (`NightSpawn` classification) happens to work only because emitter and subscriber agree on the same sub-key by coincidence. Latent bug; correctness-only fix.

### 3.2 T1 — `Node` and `MarkerEntry` as untyped data bags

`Node` has 60+ fields used inconsistently across 26 `NodeType` variants; `MarkerEntry` has 23+ fields with an implicit tagged-union shape. Consumers null-check everywhere; the loader does not validate that type-specific invariants hold. Blocks every future feature that adds a node or marker type. The audit flags this as the highest compounding-friction theme. Addressed by Group 2.

### 3.3 T2 — Facts system under-used

A typed fact system (`GuideFactKey`, `GuideDependencyEngine`) is implemented but only one derived view uses it (`QuestResolutionService._cache`). `MarkerComputer` is not modelled as a derived view; its invalidation path always forces full rebuilds regardless of which fact changed. The resolution cache key bakes the current scene into itself, forcing complete invalidation on scene change even though the frontier walk has no scene dependency. Addressed by Group 1.

### 3.4 T3 — Cache invalidation is a bag of patterns

Five distinct invalidation mechanisms coexist across the mod (version counters, reference identity, dirty flags, implicit detection, fact-delta). Each is locally defensible; the mix is not. Subsumed by T2: if every cache becomes a derived view registered with the dependency engine, the five patterns collapse to one. Falls out of Group 1; no separate work.

### 3.5 T4 — `Plugin.Update()` as an undocumented orchestrator

A long orchestrator in `Plugin.cs` ticks ten subsystems per frame with implicit ordering assumptions and no tests. Version-synchronisation logic spreads cache-invalidation across the class. Addressed by Group 1 as part of the reactive-core extraction.

### 3.6 T5 — Text formatting duplicated across four builders

Four separate text/semantic builders produce overlapping output. A single quest target's "talk to X" / "kill N of Y" text is rendered by three systems. Pairs with T1: a unified formatter consumes whatever shape T1 produces. Addressed by Group 2.

### 3.7 T6 — Dead code and unearning abstractions

~12 files of dead code and thin wrappers, plus ~5 files misplaced in `State/` that belong elsewhere. Combined: ~12 deletions and ~5 file moves with zero behaviour change. Each item ships as an independent cleanup-stream commit.

### 3.8 T7 — Navigation split-brain resolution

`NavigationTargetSelector` and `NavigationTargetResolver` both perform quest-target resolution with independent caches, independent version counters, and two distinct scoring approaches. The relationship is undocumented; some render-frame call-sites invoke both without coordination. Addressed by Group 3.

### 3.9 T8 — Diagnostics spans bleed through every subsystem

Every major update path wraps work in diagnostics `BeginSpan`/`EndSpan` calls; subsystems take `DiagnosticsCore?` as a constructor dependency. `DebugAPI` is a static global registry referencing every major subsystem. Addressed by Group 4, which depends on Group 1's orchestrator as the seam.

### 3.10 T9 — Rendering: custom ImGui backend as build-system debt *(deferred)*

~700 LOC of custom ImGui backend and native interop exist as a workaround for ILRepack merging `System.Numerics.Vector2` incorrectly. Every Unity/System.Numerics version bump risks breaking marshalling again. Deferred to a post-program research spike.

### 3.11 T10 — UI state fragmentation

Three distinct small fixes: `TrackerPanel` owns animation state whose lifetime belongs in `TrackerState`; `FilterState` uses a two-phase init that risks silent loss of persisted settings; `SpecTreeProjector` cache keys are built by string concatenation across many fields. Each ships as an independent cleanup-stream commit.

### 3.12 T11 — Resolution-pipeline polish

Four small documentation-and-encapsulation items (public readonly collection fields that allow mutation of their contents, a `-1` sentinel where `int?` is idiomatic, a long method without a routing-strategy summary comment, a live-tracker reference with no live-vs-snapshot documentation). No behaviour change. Each ships as an independent cleanup-stream commit.

## 4. Open audit questions

Six questions cannot be answered from code alone. Each shapes exactly one group's brainstorming session and is resolved there.

### Q1 — `QuestResolutionRecord` snapshot canonicalization *(shapes Group 1)*

The resolution record snapshots quest phase and item counts at construction time, but resolution-time code reads the live trackers directly. If state changes between record creation and read, the two see different worlds. Should the record be the canonical snapshot (all consumers read from it) or is the snapshot copying wasted? The answer determines Group 1's data-flow shape.

### Q2 — `NodeType` dead variants *(shapes Group 2)*

The `NodeType` enum has 26 variants. Some are clearly produced by the Python extraction pipeline today; others appear aspirational. Which variants are actually produced and flow through the mod? The answer bounds Group 2's discriminated-union case list.

### Q3 — `EdgeType` × `NodeType` taxonomy *(shapes Group 2)*

The graph has 38 edge types. Which edges are legitimate between which node types? Today invalid combinations fail silently or produce wrong text. Is the taxonomy worth formalizing and enforcing at load time? The answer determines whether Group 2 includes taxonomy validation.

### Q4 — ImGui ILRepack feasibility *(shapes T9, deferred)*

Answered by user direction: **deferred to post-program follow-up.** Re-opens after Group 4 completes.

### Q5 — `MaintainedViewPlanner` role in a fact-driven world *(shapes Group 1)*

`MaintainedViewPlanner` today decides full-vs-partial marker rebuild from a change set. Once the dependency engine returns the precise affected-views set for each fact delta, the planner's decision becomes either redundant or a thin translator. Does it survive as a translator, or is it retired entirely?

### Q6 — Marker kinds planned for Doors / ZoneLines *(shapes Group 2)*

The user stated "no speculative roadmap." Confirming no planned Door/ZoneLine markers locks Group 2's `MarkerEntry` union case list to a closed set (RespawnTimer, Character, Static, Mining, LootChest, ZoneReentry). Any ambiguity leaves room for extension and slightly loosens the design.

## 5. Group decomposition

### Group 1 — Reactive core

- **Audit themes:** T2 (facts adoption), T3 (subsumed by T2), T4 (`Plugin.Update()` orchestrator extraction)
- **Additional artifact:** an incremental engine in its own namespace (e.g. `AdventureGuide.Incremental`) designed under the extraction constraints in § 8
- **Resolves audit questions:** Q1, Q5

### Group 2 — Type shapes

- **Audit themes:** T1 (`Node` and `MarkerEntry` shape cleanup), T5 (text formatter consolidation)
- **Resolves audit questions:** Q2, Q3, Q6

### Group 3 — Navigation coherence

- **Audit theme:** T7 (split-brain resolution between `NavigationTargetSelector` and `NavigationTargetResolver`)

### Group 4 — Diagnostics decoupling

- **Audit theme:** T8 (`DiagnosticsCore` intrusion, `DebugAPI` registry)
- **Dependency:** builds on Group 1's orchestrator as the seam for recording spans at phase boundaries rather than inside each subsystem

### Cleanup stream (opportunistic, no spec, one commit per item)

- TimeOfDay bug fix (§ 3.1)
- **T6 dead-code deletions and file moves**
- **T10 UI state fixes**
- **T11 resolution-pipeline polish items**

Each cleanup item is small enough for a single commit without its own brainstorming session.

### Deferred to after program completion

- **T9** ImGui/ILRepack spike
- Engine extraction evaluation

## 6. Dependencies and ordering

```
Group 1 ───► Group 2 ───► Group 3 ───► Group 4
   │                                       ▲
   └───────────────────────────────────────┘
   (Group 4 depends on Group 1's orchestrator)

Cleanup stream interleaves between groups.
T9 spike + extraction evaluation after Group 4 completes.
```

**Order: 1 → 2 → 3 → 4.**

- **G1 first.** Load-bearing. Group 4 depends on G1's orchestrator directly. T2's fact-driven views are the foundation that later groups build on.
- **G2 second.** Highest ongoing-feature leverage (every future node type, every new marker kind benefits). Doing G2 after G1 means derived-view pattern matching is rewritten once against the new shapes — doing G2 before G1 would force two rewrites.
- **G3 third.** Standalone, independent of the other groups. Runs after G2 because G2 may surface shared types that G3's unification consumes.
- **G4 last.** Natural follow-up to G1's orchestrator seam; lowest urgency in the sequence.

## 7. Per-group lifecycle

Each group follows the same lifecycle:

1. **Brainstorming session** (using the `superpowers:brainstorming` skill) → design spec committed under `docs/superpowers/specs/`
2. **Implementation plan** (using the `superpowers:writing-plans` skill) → plan committed under `docs/superpowers/plans/`
3. **Implementation** in incremental commits
4. **Per-commit gates:**
   - Test suite passes
   - Mod builds clean
   - Hot-reload deploys in a running game (see `mod-pipeline` and `runtime-eval` skills)
   - Incident dump shows no new `FrameStall` or `FrameHitch` under representative scene load (see `in-game-performance-profiling` skill)
   - Golden diffs reviewed if any data-path changes
5. **Group exit:** all themes within the group's scope are materially resolved against the audit. The audit serves as the completion checklist — each theme's "what it blocks" narrative should no longer hold.

## 8. Engine extraction constraints

The incremental engine that emerges from Group 1 is designed under two constraints that keep future extraction possible:

- **Own namespace** (e.g. `AdventureGuide.Incremental`) isolating engine types from mod types
- **Zero Erenshor-specific types in the engine's public API surface**

Erenshor-specific ergonomics inside the engine's internal use are unaffected by these constraints. The engine may reference Erenshor types in private implementation details; the constraint is about the public surface that an external consumer would depend on.

Extraction itself is **not a goal of this program.** After all 4 groups + cleanup stream complete, evaluate whether the engine generalized cleanly through continued use; if yes, extract to a standalone repository with honest positioning against prior art (Salsa in Rust, Incremental.NET in F#, UniMob in Unity-coupled C#); if no, leave it in-mod without regret.

## 9. Success criteria

- All 11 audit themes addressed; each theme's "what it blocks" concerns materially resolved against the audit
- TimeOfDay bug fixed
- Test count not reduced from program-start baseline; new coverage welcome
- No new `FrameStall` or `FrameHitch` incidents under representative scene load (Stowaway zone with a non-trivial active+completed quest set and the resolution summary exercised)
- `AdventureGuide.Incremental` namespace exists with zero Erenshor type references in its public API surface
- Final extraction decision recorded (extract / abandon) with rationale

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| AG | AdventureGuide — the BepInEx companion mod at `src/mods/AdventureGuide/` |
| Fact | A typed primitive state observation (`GuideFactKey`). Seven kinds: `InventoryItemCount`, `UnlockItemPossessed`, `QuestActive`, `QuestCompleted`, `Scene`, `SourceState`, `TimeOfDay` |
| Derived view | A memoised computation whose re-execution is gated on the fact keys it read |
| Dependency engine | `GuideDependencyEngine` — tracks which facts each derived view depends on and returns the affected-views set when facts change |
| Frontier walk | The quest-resolution algorithm that walks forward from a quest's current phase to compute reachable targets, implemented in `SourceResolver` |
| FrameStall | Incident class: a single frame > 250 ms |
| FrameHitch | Incident class: a single frame > 100 ms (but ≤ 250 ms) |
| HotRepl | The in-game C# REPL provided by BepInEx ScriptEngine |
| F6 hot-reload | ScriptEngine hotkey that reloads mod DLLs without restarting the game |
| GuideChangeSet | The per-frame bag of changes published by trackers (coarse flags plus fine `ChangedFacts` list) |
| Golden diff | Output comparison against `tests/golden/` baselines — verifies data-pipeline changes don't silently alter outputs |

## Appendix B — File-path signposts

Canonical entry points by subsystem, for orientation during group brainstorming. Line numbers are intentionally omitted — the audit carries them as a dated snapshot; use LSP `definition` / `references` or grep to locate specific positions at the time you need them.

| Subsystem | Path |
|---|---|
| Plugin orchestrator | `src/mods/AdventureGuide/src/Plugin.cs` |
| Quest resolution | `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs` |
| Resolution record | `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs` |
| Source resolver | `src/mods/AdventureGuide/src/Resolution/SourceResolver.cs` |
| Marker computer | `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs` |
| Marker entry | `src/mods/AdventureGuide/src/Markers/MarkerEntry.cs` |
| Marker system (per-frame) | `src/mods/AdventureGuide/src/Markers/MarkerSystem.cs` |
| Fact keys | `src/mods/AdventureGuide/src/State/GuideFactKey.cs` |
| Dependency engine | `src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs` |
| Change set | `src/mods/AdventureGuide/src/State/GuideChangeSet.cs` |
| Live state tracker | `src/mods/AdventureGuide/src/State/LiveStateTracker.cs` |
| Quest state tracker | `src/mods/AdventureGuide/src/State/QuestStateTracker.cs` |
| Node (graph) | `src/mods/AdventureGuide/src/Graph/Node.cs` |
| Node types | `src/mods/AdventureGuide/src/Graph/NodeType.cs` |
| Navigation selector | `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs` |
| Navigation resolver | `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs` |
| Text builders | `src/mods/AdventureGuide/src/Resolution/NavigationExplanationBuilder.cs`, `MarkerTextBuilder.cs`, `ResolvedActionSemanticBuilder.cs` + `src/UI/Tree/SpecTreeProjector.cs` |
| Diagnostics | `src/mods/AdventureGuide/src/Diagnostics/` |
| Rendering | `src/mods/AdventureGuide/src/Rendering/` |
| Tests | `src/mods/AdventureGuide/tests/AdventureGuide.Tests/` |
| Decompiled game source (read-only reference) | `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` |
