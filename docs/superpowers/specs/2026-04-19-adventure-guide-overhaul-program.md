# AdventureGuide Overhaul — Program Spec

**Date:** 2026-04-19
**Status:** Approved in chat
**Scope:** Meta-document organizing how the AdventureGuide architecture overhaul proceeds. Addresses all 11 themes identified in the 2026-04-18 architecture audit plus the TimeOfDay correctness bug, and designs the extractable incremental engine that emerges from the reactive-core work.

---

## 1. Purpose and how to use this document

This spec decomposes the AdventureGuide architecture overhaul into coupled design groups, orders them by dependency, and records the meta-decisions (scope, ordering, extraction strategy, lifecycle gates) so each per-group brainstorming session can focus on real architectural calls instead of re-deciding shared structure.

**It does not make per-group design decisions.** Those happen in each group's own brainstorming session, which produces its own design spec at `docs/superpowers/specs/`.

This document is intended to be **readable cold** — a reader with no prior session context should be able to open it and understand what needs to happen, in what order, and why. It references but does not duplicate the companion document `docs/superpowers/specs/2026-04-18-adventure-guide-architecture-audit.md`, which carries the full per-finding evidence (file:line citations, "evidence of pain", "what this blocks", "shape of fix") for every theme.

## 2. Scope

**In scope:**
- All 11 audit themes (T1–T11), summarised in § 3
- TimeOfDay fact correctness bug (full specification in § 3.1)
- Extraction-friendly namespace design for the incremental engine that emerges from Group 1

**Deferred to after program completion:**
- **T9** ImGui/ILRepack spike — afternoon research task; outcome eliminates ~700 LOC of rendering code or confirms the workaround is structural
- Engine extraction to standalone repo — evaluated only after all 4 groups + cleanup stream complete; explicitly nice-to-have, abandonable without regret if the API did not generalize cleanly

**Out of scope forever (for this program):**
- Speculative roadmap features. The audit addresses what exists today; so does this program.

## 3. Findings catalogue

Each entry below is a brief orientation. Full per-theme evidence is in the audit document referenced above. The TimeOfDay bug is specified fully here because it is a small atomic deliverable that benefits from single-location specification.

### 3.1 TimeOfDay fact correctness bug (cleanup-stream item, ship early)

- **Location:** `src/mods/AdventureGuide/src/State/LiveStateTracker.cs`, emission at L952, dependent registration at L561
- **Current behaviour:** `BuildLiveChange` unconditionally emits `GuideFactKey(GuideFactKind.TimeOfDay, "night")` whenever time-of-day changes, regardless of direction (day→night or night→day). `ClassifySpawnPoint` registers a matching dependency on `TimeOfDay("night")` for any spawn point marked `NightSpawn`. Today the only dependent is night-spawn classification, and it happens to invalidate correctly because emitter and subscriber agree on the key — but the semantics are wrong.
- **Latent risk:** if any future derived view registers on `TimeOfDay("day")` (e.g. day-only spawn behaviour, day-locked quest objectives), it will never be invalidated because the emitter only ever sends `"night"`.
- **Audit-suggested fix (discard):** emit `"day"` or `"night"` based on `nowNight`. This would break the existing `NightSpawn` dependent because the dependent registers only on `"night"` — invalidation on night→day transitions would be lost unless the dependent is also updated to register on both keys.
- **Chosen fix:** match the `Scene` fact's pattern. Scene uses `GuideFactKey(Scene, "current")` — a single stable sub-key meaning "the current value of this fact." Change both the emitter (L952) and the dependent registration (L561) to use `GuideFactKey(TimeOfDay, "current")`. This is semantically parallel to Scene, invalidates on any transition, and survives future expansion (hypothetical dawn/dusk facts could use their own fact kinds or sub-keys if finer granularity is ever needed).
- **Test approach:** follow the existing source-text-inspection pattern in `tests/AdventureGuide.Tests/LiveStateTrackerTests.cs` (see `UpdateFrameState_DoesNotScanMiningNodes`) to assert the emitter uses `"current"` and that the `NightSpawn` classification registers on the same key. Direct behaviour testing is blocked by `IsNight()` being a static method dependent on the Unity runtime `GameData.Time` singleton.
- **Atomic scope:** one file, two line edits, one source-inspection test. Ships as a standalone `fix(mod)` commit.

### 3.2 T1 — `Node` and `MarkerEntry` as untyped data bags

`Node` has 60+ fields used inconsistently across 26 `NodeType` variants. `MarkerEntry` has 23+ fields with an implicit tagged-union shape. Consumers null-check everywhere; loader does not validate that type-specific invariants hold (e.g. a `Door` with `KeyItemKey=null` passes silently). Blocks every future feature that adds a node or marker type. Shape of fix: sealed discriminated unions with per-variant fields and pattern-match dispatch. Highest compounding-friction theme in the audit.

### 3.3 T2 — Facts system under-used (the marker-perf problem too)

A typed fact system (`GuideFactKey`, `GuideFactKind`, `GuideDependencyEngine`) is implemented and in-place but only **one** derived view uses it: `QuestResolutionService._cache`. `MarkerComputer` is not modelled as a derived view; its `MarkDirty` path always forces a full rebuild regardless of which fact changed. The resolution cache key bakes `currentScene` into the key, forcing `InvalidateAll` on scene change even though the frontier walk has no scene dependency. Shape of fix: split into two derived-view kinds — scene-independent `QuestCompiledTargets(questKey)` and scene-scoped `MarkerCandidatesForScene(sceneName)` — wire both through the existing dependency engine, retire `MarkDirty`'s full-rebuild behaviour.

### 3.4 T3 — Cache invalidation is a bag of patterns

Five distinct invalidation mechanisms coexist: version counters, reference identity (`ReferenceEquals`), dirty flags, implicit external-reference detection, fact-delta. Each is locally defensible; the mix is not. `ViewRenderer` alone maintains three cache layers with three different mechanisms. **Subsumed by T2's prescription** ("adopt fact-deltas everywhere"): once every cache is a `GuideDerivedView` with a declared fact-dependency set, the five patterns collapse to one.

### 3.5 T4 — `Plugin.Update()` as an undocumented state machine

762-line orchestrator with no tests. Ticks LiveStateTracker, QuestStateTracker, GuideDependencyEngine, QuestResolutionService, ZoneRouter, MarkerComputer, NavigationEngine, GroundPathRenderer, MarkerSystem, input handling, UI — in implicit ordering with no enforcement. Version-synchronisation logic (`_lastObservedQuestTrackerVersion`, `_lastResolutionVersion`, `_lastNavSetVersion`) spreads cache-invalidation across the class. Shape of fix: extract `UpdateOrchestrator` with five explicit phases — capture inputs → publish change deltas → invalidate → recompute → render — each with a single entry point and each testable in isolation.

### 3.6 T5 — Text formatting duplicated across four builders

Four text/semantic builders produce overlapping output: `NavigationExplanationBuilder`, `MarkerTextBuilder`, `ResolvedActionSemanticBuilder`, and `SpecTreeProjector.FormatXxxLabel` (6+ methods). A single quest target's "talk to X" / "kill N of Y" text is rendered three times by three systems. Shape of fix: one shared `InteractionLabelFormatter` (or `QuestIntentFormatter`) consuming a `ResolvedActionSemantic` (or the discriminated union from T1), producing a structured `InteractionLabel { Primary, Secondary, Tertiary, Kind }`. All four current builders become thin consumers. Pairs naturally with T1 — formatter dispatches on the discriminated-union cases.

### 3.7 T6 — Dead code and unearning abstractions

Small individually, collectively significant for cognitive load. Delete-outright items include `CreatePendingCompletionEntry`, `GetNodeType(int)`, the unread `zone_line_ids` field, a discarded constructor parameter in `QuestTargetProjector`, and unused public surface area in `SourceResolver`. Collapse-thin-indirection items include eight `State/Resolvers/*.cs` wrapper files, `LiveStateBackedPositionResolver` (two users), `CharacterMarkerPolicy`, `ItemSourceVisibilityPolicy`, and `NavigationDisplay`. Move-to-where-consumed items include four files (`NavigationHistory`, `NavigationSetPersistence`, `GameUIVisibility`, `GameWindowOverlap`) currently in `State/` that belong in `Navigation/` or `UI/`. Combined: ~12 files deleted, ~5 files moved, zero behaviour change.

### 3.8 T7 — Navigation split-brain resolution

`NavigationTargetSelector` (816 LOC) and `NavigationTargetResolver` (532 LOC) both perform quest-target resolution, with independent caches, independent version counters, and two distinct scoring approaches (`NavigationScore.Compute()` for cross-quest ranking, `SelectBestCore()` with an 8-tier algorithm for within-quest ranking). Relationship is undocumented. `TrackerPanel.DrawResolutionSummary` calls both resolvers in the same render frame with no coordination. Shape of fix: pick a single canonical entry point; the other becomes pure selection from pre-resolved data; the 8-tier algorithm moves to a shared `TargetRanker` utility consumed by both consumers.

### 3.9 T8 — Diagnostics spans bleed through every subsystem

Every major update path wraps work in `_diagnostics?.BeginSpan(...)` / `EndSpan(...)`. Subsystems take `DiagnosticsCore?` as a constructor dependency. `DebugAPI` is a static global with 15+ fields holding references to every major subsystem, initialised for HotRepl eval and requiring initialisation or mocking in tests. 12 diagnostics files, ~1800 LOC, heavily intrusive. Shape of fix depends on Group 1's `UpdateOrchestrator`: record spans at phase boundaries in the orchestrator, not inside each subsystem; subsystems stop taking `DiagnosticsCore`; incident capture becomes a wrapper/decorator. Consolidate under-50-LOC diagnostics files (target: ~5 files from ~12). Narrow `DebugAPI`'s subsystem registry.

### 3.10 T9 — Rendering: custom ImGui backend as build-system debt (deferred)

`Rendering/ImGuiRenderer.cs` (599 LOC) and `Rendering/CimguiNative.cs` (~700 LOC combined) exist because ILRepack's default merging creates a duplicate `System.Numerics.Vector2` type that breaks marshalling to ImGui. ~700 LOC of owned code for what should be library consumption. Spike determines whether ILRepack can be configured to not merge `System.Numerics`, or whether ImGui.NET can be used without ILRepack merging at all. **Deferred to post-program follow-up** per user direction — not necessary for the overhaul, and a distraction while the main work is in flight.

### 3.11 T10 — UI state fragmentation

Three distinct small fixes. `TrackerPanel` owns animation state (`_animations`, `_fadingOut`, `_completionTimers`) whose lifetimes are tied to quest-tracking events that `TrackerState` already emits — move ownership into `TrackerState`, make `TrackerPanel` a pure renderer. `FilterState` requires post-construction `LoadFrom(config)` — two-phase init. Convert to constructor-takes-config or a factory method; today's pattern risks silent loss of persisted filter settings. `SpecTreeProjector` cache keys are built by 14-field string concatenation — replace with a strongly-typed `record ProjectionCacheKey(...)` so the compiler enforces which fields participate. None of these are big individually; they generate bugs over time.

### 3.12 T11 — Resolution-pipeline polish (medium-low priority)

Four small items: `ResolutionSession` exposes public readonly collection fields whose contents remain mutable (footgun-if-anything-changes); `FrontierEntry.RequiredForQuestIndex` uses `-1` sentinel for "not required" where `int?` is the C# idiom; `SourceResolver.ResolveEntry` is 400+ lines with no top-level routing-strategy summary comment; `EffectiveFrontier.Phases` exposes the live-tracker reference without documenting live-vs-snapshot semantics. All documentation-and-encapsulation polish; no behaviour change.

## 4. Open audit questions

The audit identified six questions that cannot be answered from the code alone. Each question shapes exactly one group's brainstorming session and is resolved there.

### Q1 — `QuestResolutionRecord` snapshot canonicalization *(shapes Group 1)*

The resolution record snapshots `_questPhases` and `_itemCounts` at construction time (`QuestResolutionService.cs` L234-235). But resolution-time code (`SourceResolver`, `UnlockPredicateEvaluator`, `TrackerSummaryBuilder`) reads the **live** `QuestPhaseTracker` directly. If state changes between record creation and read, the two see different worlds. `QuestPhaseTracker.SnapshotPhases/SnapshotItemCounts` (L70-72) performs full array clones on every `BuildRecord`, which is wasted work for records that never touch phase state.

**Question:** should resolution-time code read from the record (making the snapshot the canonical view) or from the live tracker (making the snapshot copying wasted)? The answer determines Group 1's data-flow shape: either `QuestCompiledTargets(questKey)` carries the snapshot and all consumers read from it, or the snapshot disappears and live-tracker reads are factored as additional fact dependencies.

### Q2 — `NodeType` dead variants *(shapes Group 2)*

The `NodeType` enum has 26 variants: `Quest, Item, Character, Zone, ZoneLine, SpawnPoint, MiningNode, Water, Forge, ItemBag, Recipe, Door, Faction, Spell, Skill, Teleport, WorldObject, AchievementTrigger, SecretPassage, WishingWell, TreasureLocation, Book, Class, Stance, Ascension`, plus one I may be miscounting. Some variants are clearly produced by the Python extraction pipeline today; others appear aspirational.

**Question:** which variants are actually produced and flow through the mod today? The answer directly bounds Group 2's discriminated-union case list. An aspirational variant that isn't currently produced may not need a case at all until it is; a produced variant absolutely needs one. Answering requires checking either the Python pipeline source or the compiled-guide data itself (which variant IDs appear in the `raw.sqlite` or `guide.json` artifact).

### Q3 — `EdgeType` × `NodeType` taxonomy formalization *(shapes Group 2)*

The graph has 38 edge types. Which edges are legitimate between which node types? Today the pattern matching in `ResolvedActionSemanticBuilder.cs` L175-202 dispatches on edge/node combinations without a formal taxonomy. Invalid combinations fail silently or produce wrong text.

**Question:** is the taxonomy worth formalizing as a table (matrix of (src NodeType, edge, dst NodeType) → valid/invalid) and enforced at load time? The answer determines whether Group 2's work includes taxonomy validation in the compiled-guide loader, or whether that stays out-of-scope.

### Q4 — ImGui ILRepack spike feasibility *(shapes T9, deferred)*

Answered by user direction: **deferred to post-program follow-up.** Not necessary for overhaul work and risks distraction. Re-opens after Group 4 completes.

### Q5 — `MaintainedViewPlanner` role in a fact-driven world *(shapes Group 1)*

`MaintainedViewPlanner` today decides full-vs-partial marker rebuild from a `GuideChangeSet`. In a fact-driven world where `GuideDependencyEngine.InvalidateFacts(changedFacts)` already returns the precise set of affected derived views, the planner's decision becomes either redundant (dependency engine subsumes it) or a thin translator (it maps high-level events to fact changes).

**Question:** does `MaintainedViewPlanner` survive the Group 1 rework as a thin translator, or is it retired entirely? The answer determines whether Group 1 touches it as refactor-target or as delete-target.

### Q6 — Marker kinds planned for Doors / ZoneLines *(shapes Group 2)*

Some audit recommendations (the `MarkerEntry` discriminated-union case list, the `NodeType` taxonomy) are cheaper to design if we know whether Door and ZoneLine markers are planned. The user stated "no speculative roadmap" — confirming this locks the Group 2 design tighter by excluding these variants from the `MarkerEntry` union.

**Question:** confirmed no planned Door/ZoneLine markers? If yes, Group 2's `MarkerEntry` cases are definitely `RespawnTimerMarker`, `CharacterMarker`, `StaticMarker`, `MiningMarker`, `LootChestMarker`, `ZoneReentryMarker` — six cases total, closed set. If there's any ambiguity, Group 2 leaves room for extension.

## 5. Group decomposition

### Group 1 — Reactive core

- **Audit themes:** T2 (facts adoption), T3 (subsumed by T2's fact-delta prescription), T4 (`UpdateOrchestrator`)
- **Additional artifact:** extraction-friendly incremental engine in its own namespace (e.g. `AdventureGuide.Incremental`), zero Erenshor-specific types in its public API, isolated tests
- **Resolves audit questions:** Q1, Q5

### Group 2 — Type shapes

- **Audit themes:** T1 (Node + MarkerEntry discriminated unions), T5 (`InteractionLabelFormatter` consolidating four text builders)
- **Resolves audit questions:** Q2, Q3, Q6

### Group 3 — Navigation coherence

- **Audit theme:** T7 (split-brain resolution between `NavigationTargetSelector` and `NavigationTargetResolver`)
- No audit questions outstanding

### Group 4 — Diagnostics decoupling

- **Audit theme:** T8 (`DiagnosticsCore` intrusion, `DebugAPI` registry surface)
- **Dependency:** builds on Group 1's `UpdateOrchestrator` as the seam for recording spans at phase boundaries rather than inside each subsystem
- No audit questions outstanding

### Cleanup stream (opportunistic, no spec, one commit per item)

Interleaves between groups wherever convenient. Each item is small enough for a single commit without brainstorming.

- TimeOfDay bug fix (full spec in § 3.1 above; ship early, 1 commit)
- **T6 dead-code deletions:** `CreatePendingCompletionEntry` (MarkerComputer), `GetNodeType(int)` (CompiledGuide), `zone_line_ids` field (CompiledGuideData), discarded `positionResolvers` ctor param (QuestTargetProjector), unused public `ResolveTargets`/`ResolveUnlockTargets` (SourceResolver), 8 `State/Resolvers/*.cs` thin wrappers, `LiveStateBackedPositionResolver` base class, `CharacterMarkerPolicy`, `ItemSourceVisibilityPolicy`, `NavigationDisplay`
- **T6 file moves:** `State/NavigationHistory.cs`, `State/NavigationSetPersistence.cs`, `State/GameUIVisibility.cs`, `State/GameWindowOverlap.cs` out of `State/`
- **T10 fixes:** `TrackerPanel` animation ownership → `TrackerState`; `FilterState.LoadFrom` two-phase init → factory; `SpecTreeProjector` cache key → typed record
- **T11 fixes:** `ResolutionSession` public-mutable-collection encapsulation; `FrontierEntry.RequiredForQuestIndex` `-1` sentinel → `int?`; `SourceResolver.ResolveEntry` routing-strategy doc comment; `EffectiveFrontier.Phases` live-vs-snapshot doc

### Deferred to after program completion

- **T9** ImGui/ILRepack spike — afternoon research; may eliminate ~700 LOC or confirm the workaround is structural
- **Engine extraction evaluation** — if `AdventureGuide.Incremental` generalized cleanly, extract to a standalone repository; abandon without regret if not

## 6. Dependencies and ordering

```
TimeOfDay bug (standalone, anytime — recommended: now)

Group 1 ───► Group 2 ───► Group 3 ───► Group 4
   │                                       ▲
   └───────────────────────────────────────┘
   (Group 4 depends on Group 1's UpdateOrchestrator)

Cleanup stream interleaves between groups
T9 spike + extraction evaluation after Group 4 completes
```

**Order: 1 → 2 → 3 → 4.** Justification:

- **G1 first.** Load-bearing. Group 4 depends on G1's `UpdateOrchestrator` directly. T2's fact-driven views are the foundation that later groups build on.
- **G2 second.** Highest ongoing-feature leverage (every future node type, every new marker kind benefits). Doing G2 after G1 means derived-view pattern matching is rewritten **once** against the discriminated union types — doing G2 before G1 would force it to be rewritten twice.
- **G3 third.** Standalone, independent of the other groups. Runs after G2 because G2 may surface shared types (e.g. a canonical `ResolvedTarget`) that G3's unification consumes.
- **G4 last.** Natural follow-up to G1's orchestrator seam; lowest urgency in the sequence.

## 7. Per-group lifecycle

Each group follows the same lifecycle:

1. **Brainstorming session** (using the `superpowers:brainstorming` skill) → design spec at `docs/superpowers/specs/2026-MM-DD-ag-<group-short-name>-design.md`, committed
2. **Implementation plan** via the `superpowers:writing-plans` skill → plan doc at `docs/superpowers/plans/2026-MM-DD-ag-<group-short-name>.md`, committed
3. **Implementation** in incremental commits on the current branch or a sub-branch
4. **Per-commit gates:**
   - 283+ tests green: `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build`
   - Mod builds clean: `uv run erenshor mod build --mod adventure-guide`
   - F6 hot-reload deploys in a running game (see § Appendix B for the HotRepl reload snippet)
   - Incident dump shows no new `FrameStall` (> 250ms frame) or `FrameHitch` (> 100ms frame) under representative scene load (Stowaway zone, 5 active + 5 completed quests)
   - Golden diffs reviewed if any data-path changes: `uv run erenshor golden capture`
5. **Group exit:** all themes within the group's scope are materially resolved against the audit. The audit serves as the completion checklist — each theme's "what it blocks" / "evidence of pain" narrative should no longer hold.

## 8. Engine extraction (post-completion, nice-to-have)

After all 4 groups + cleanup stream complete:

- Evaluate whether the `AdventureGuide.Incremental` namespace generalized cleanly during continued use across Groups 2, 3, and 4.
- If it did: extract to a standalone repository (tentatively `IncC#` or similar), port tests, write a README honestly positioning it against Salsa (Rust), Incremental.NET (F#), and UniMob (Unity-coupled), and publish.
- If it did not: leave it in-mod. No regret. No forcing.

Extraction is explicitly **not a goal of the program.** Group 1's design should make extraction *possible* by keeping the engine in its own namespace with zero Erenshor type references in its public API, but it must not compromise Erenshor-specific ergonomics for hypothetical external consumers.

## 9. Success criteria

- All 11 audit themes addressed; each theme's "what it blocks" concerns materially resolved against the audit document
- TimeOfDay bug fixed
- Test count ≥ current baseline (283 at program start); any additions welcome, no net loss
- No new `FrameStall` or `FrameHitch` incidents under representative scene load (Stowaway zone, 5 active + 5 completed quests, with a quest selected that exercises the resolution summary)
- `AdventureGuide.Incremental` namespace exists with zero Erenshor type references in its public API surface
- Final extraction decision recorded (extract / abandon) with one-paragraph rationale

## 10. What happens next

Immediately after this program spec is approved:

1. Ship the TimeOfDay bug fix as a standalone commit (full spec in § 3.1; 1-line edits in two locations plus one source-inspection test).
2. Begin Group 1 brainstorming session — its spec will live at `docs/superpowers/specs/2026-MM-DD-ag-reactive-core-design.md`. Resolve Q1 and Q5 during that session.

After Group 1 ships, begin Group 2 brainstorming (resolves Q2, Q3, Q6). Then Group 3. Then Group 4. Then the T9 spike and engine extraction evaluation, in either order.

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| AG | AdventureGuide — the BepInEx companion mod at `src/mods/AdventureGuide/` |
| Fact | A typed primitive state observation (`GuideFactKey`). Seven kinds today: `InventoryItemCount`, `UnlockItemPossessed`, `QuestActive`, `QuestCompleted`, `Scene`, `SourceState`, `TimeOfDay` |
| Derived view | A memoised computation whose re-execution is gated on the fact keys it read. Only one in-mod today: `QuestResolutionService._cache` |
| Dependency engine | `GuideDependencyEngine` — the in-mod component that tracks which facts each derived view depends on and returns the affected-views set when facts change |
| GuideChangeSet | The per-frame bag of changes published by trackers (inventoryChanged, questLogChanged, sceneChanged, liveWorldChanged plus the `changedFacts` list) |
| Frontier walk | The quest-resolution algorithm that walks forward from a quest's current phase to compute reachable targets, implemented in `SourceResolver` |
| FrameStall | Incident class: a single frame > 250 ms |
| FrameHitch | Incident class: a single frame > 100 ms (but ≤ 250 ms) |
| HotRepl | The in-game C# REPL provided by BepInEx ScriptEngine, used for runtime inspection and prototyping |
| F6 hot-reload | The ScriptEngine hotkey that reloads all in-mod DLLs without restarting the game — used for fast dev iteration |
| Incident dump | Output of `DiagnosticsCore.FormatAllIncidents()`, used to verify no new FrameStalls / FrameHitches after a change |
| Golden diff | Output comparison against `tests/golden/` baselines — verifies data-pipeline changes don't silently alter outputs |

## Appendix B — File-path signposts

Canonical entry points by subsystem, for orientation during group brainstorming:

| Subsystem | Entry point | Notes |
|---|---|---|
| Plugin orchestrator | `src/mods/AdventureGuide/src/Plugin.cs` (Update at L465-650) | T4 extraction target |
| Quest resolution | `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs` | BuildRecord L208-257; cache key with scene-baking issue L331-334 |
| Resolution record | `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs` | Has lazy `NavigationTargets` factory from recent commit |
| Source resolver | `src/mods/AdventureGuide/src/Resolution/SourceResolver.cs` | 1594 LOC; `ResolutionSession` L112-177; `ResolveEntry` L338-750 |
| Marker computer | `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs` | 1151 LOC; `MarkDirty` always-rebuild at L150-165; dead `CreatePendingCompletionEntry` L489-532 |
| Marker entry | `src/mods/AdventureGuide/src/Markers/MarkerEntry.cs` | T1 target — 23+ field tagged-union |
| Marker system (per-frame) | `src/mods/AdventureGuide/src/Markers/MarkerSystem.cs` | `UpdateLiveState` L118-175 — falls-through dispatch |
| Fact keys | `src/mods/AdventureGuide/src/State/GuideFactKey.cs` | Seven fact kinds defined here |
| Dependency engine | `src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs` | `BeginCollection` / `RecordFact` / `InvalidateFacts` |
| Change set | `src/mods/AdventureGuide/src/State/GuideChangeSet.cs` | Coarse flags + fine `ChangedFacts` — T3 DRY target |
| Live state tracker | `src/mods/AdventureGuide/src/State/LiveStateTracker.cs` | TimeOfDay bug at L206-209, L950-952; emission at L952; dependent at L561 |
| Quest state tracker | `src/mods/AdventureGuide/src/State/QuestStateTracker.cs` | Scene fact emission at L266, L359 — reference pattern for TimeOfDay fix |
| Node (graph) | `src/mods/AdventureGuide/src/Graph/Node.cs` | T1 target — 60+ field god-object |
| Node types | `src/mods/AdventureGuide/src/Graph/NodeType.cs` | 26 variants (Q2 audit question) |
| Navigation selector | `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs` | 816 LOC; T7 target |
| Navigation resolver | `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs` | 532 LOC; T7 target |
| Text builders | `src/mods/AdventureGuide/src/Resolution/NavigationExplanationBuilder.cs`, `MarkerTextBuilder.cs`, `ResolvedActionSemanticBuilder.cs` + `src/UI/Tree/SpecTreeProjector.cs` L897-987 | T5 consolidation targets |
| Diagnostics core | `src/mods/AdventureGuide/src/Diagnostics/` (12 files, ~1800 LOC) | T8 decoupling target; DebugAPI at `DebugAPI.cs` 519 LOC |
| Rendering | `src/mods/AdventureGuide/src/Rendering/ImGuiRenderer.cs`, `CimguiNative.cs` | T9 target (deferred) — ~700 LOC ILRepack workaround |
| Tests | `src/mods/AdventureGuide/tests/AdventureGuide.Tests/` | 283 tests at program start |
| Decompiled game source | `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` | Read-only reference for game class definitions (NPC, Mob, SpawnPoint, MiningNode, RotChest, Npc, etc.) |

## Appendix C — Useful commands and snippets

### Verification commands

```bash
# Tests
dotnet test  src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo

# Build
dotnet build src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo

# Deploy mod for F6 hot-reload (ScriptEngine scripts mode)
uv run erenshor mod deploy --mod adventure-guide --scripts

# Deploy mod production-mode (requires game restart)
uv run erenshor mod deploy --mod adventure-guide

# Refresh golden baselines after data-path changes
uv run erenshor golden capture
```

### F6 hot-reload via HotRepl

```csharp
var asm  = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "ScriptEngine");
var type = asm.GetType("ScriptEngine.ScriptEngine");
var inst = UnityEngine.Object.FindObjectsOfTypeAll(type).First();
type.GetMethod("ReloadPlugins", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
    .Invoke(inst, null);
```

### Incident dump via HotRepl

```csharp
var bfAll = BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Public;
var ag = UnityEngine.Resources.FindObjectsOfTypeAll(typeof(MonoBehaviour))
    .First(o => o.GetType().FullName == "AdventureGuide.Plugin");
var diag = ag.GetType().GetField("_diagnostics", bfAll).GetValue(ag);
return (string)diag.GetType().GetMethod("FormatAllIncidents").Invoke(diag, null);
```

### BepInEx log location (macOS via CrossOver)

`~/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Erenshor/BepInEx/LogOutput.log`
