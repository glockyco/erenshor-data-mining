# AdventureGuide Architecture Audit — 2026-04-18

Full-mod audit of `src/mods/AdventureGuide/` (~23.5k LOC, 120 files, 283 tests). Triggered by marker-performance work; user asked for a holistic review beyond that focus. Findings clustered by architectural theme. Severity reflects "blocks or complicates future work", not just performance impact.

Five parallel read-only investigations produced ~80 findings. Full per-subsystem reports are preserved at `agent://0-ResolutionAudit` through `agent://4-FoundationAudit`.

---

## TL;DR — the five things that matter most

1. **One latent bug, four high-leverage architectural issues.** The bug is real and should be fixed regardless of the audit outcome.
2. **`Node` and `MarkerEntry` are untyped data bags.** 60+ nullable fields on `Node`, 23+ on `MarkerEntry`. Consumers null-check everywhere. Adding or changing a field requires knowing every call site. Both beg to become discriminated unions.
3. **The facts system exists but is under-used.** `QuestResolutionService._cache` is the only proper derived view. The cache key includes `currentScene`, which forces a full flush on scene change even though the frontier walk itself has no scene dependency. `MarkerComputer` is not modeled as a derived view at all. The `MarkDirty` path unconditionally forces a full rebuild on any live-world change, ignoring the fact deltas that are already available.
4. **Four cache-invalidation patterns coexist.** Version counters (NavigationTargetSelector, FilterState), reference identity (ViewRenderer), dirty flags (TrackerState), and implicit detection (CameraCache) — no unified protocol. Every new cache invents its own invalidation.
5. **`Plugin.Update()` is an undocumented 762-line orchestrator with no tests.** It ticks ten subsystems per frame with implicit ordering assumptions. The version fields (`_lastObservedQuestTrackerVersion`, `_lastResolutionVersion`, `_lastNavSetVersion`) spread cache-invalidation logic across the class. Refactoring anything upstream has no safety net.

---

## One bug to fix immediately

### `TimeOfDay` fact emits the same key for both directions

- **Location:** `src/State/LiveStateTracker.cs:206-209, 950-952`
- **Severity:** high (correctness)
- **Finding:** `BuildLiveChange` unconditionally emits `GuideFactKey(TimeOfDay, "night")` whenever time-of-day changes, whether the transition is day→night or night→day. Dependents cannot distinguish the two.
- **Fix:** emit `"day"` or `"night"` based on `nowNight`, or split into two fact kinds. Trivial patch.

This is not architectural — it's a one-line bug that's been shipping. Fix regardless of the rest of this report.

---

## Theme 1 — Type-safety: `Node` and `MarkerEntry` as untyped data bags

The single biggest source of compounding friction across the whole mod.

### `Node` has 60+ fields, used inconsistently across 26 NodeTypes
- **Location:** `src/Graph/Node.cs:1-160`
- **Evidence of pain:** null-checks on `X`/`Y`/`Z` scattered across 40+ sites. `CharacterPositionResolver.cs:139`, `MarkerComputer.cs:1043`, `QuestResolutionService.cs:283-300`, etc. No invariants validated at load time — a `Door` with `KeyItemKey=null` or a `ZoneLine` missing `DestinationZoneKey` is accepted by the loader and fails silently downstream.
- **What it blocks:** every future feature that adds a node type. Every position-dependent refactor. Every "does this node support marker X" question.
- **Shape of fix:** sealed discriminated union. `abstract Node` with `QuestNode`, `ItemNode`, `CharacterNode`, `ZoneNode`, `ZoneLineNode`, `SpawnPointNode`, `MiningNode`, `ItemBagNode`, `WorldObjectNode`, `DoorNode`, etc. Each carries only its relevant fields. Consumers pattern-match. Loader validates.
- **Cost:** large. Touches `CompiledGuide` projection (L496), every position/state resolver, `MarkerComputer` type-dispatch, SourceResolver emission, text builders. But all those sites already pattern-match on `Node.Type` — the change is mostly mechanical. The dual-representation issue (internal `CompiledNodeData[]` + projected `Node[]`) might go away in the same pass.

### `MarkerEntry` is an implicit tagged union (23+ fields)
- **Location:** `src/Markers/MarkerEntry.cs:1-95`
- **Evidence of pain:** `MarkerSystem.UpdateLiveState` (L118-175) dispatches via `if (LiveMiningNode != null) ... else if (LiveSpawnPoint != null) ... else if (IsLootChestTarget) ... else if (!IsSpawnTimer) ...`. ZoneReentry markers rely on *falling through every condition* to end up with no per-frame update (a silent invariant at `MarkerComputer.cs:467-488` + `MarkerSystem.cs:140-170`). `CreatePendingCompletionEntry` (MarkerComputer L489-532) is dead code, nearly identical to `CreateImplicitCompletionEntry` — leftover from the not-fully-made cutover.
- **What it blocks:** adding new marker kinds (doors, zone-lines, teleports as markers), refactoring the per-frame dispatch, making `MarkerSystem` testable in isolation.
- **Shape of fix:** same as Node. `abstract MarkerEntry` with `RespawnTimerMarker`, `CharacterMarker`, `StaticMarker`, `MiningMarker`, `LootChestMarker`, `ZoneReentryMarker`. Each implements its own `UpdateLiveState(MarkerInstance)`. Polymorphic dispatch replaces the conditional chain. The `CloneEntry` copy-on-publish can be sharpened to the mutable subset per type.

### `ResolvedActionSemantic` has 14 fields, 8 nullable
- **Location:** `src/Resolution/ResolvedActionSemantic.cs:10-25`
- **Severity:** low today, but it signals the same shape of problem. If the Node/MarkerEntry rewrite happens, this should get the same treatment — `GiverSemantic`, `ObjectiveSemantic`, `TurnInSemantic` subtypes — or stay as-is if its consumers tolerate the optional-field pattern.

**Why this theme is the top priority:** every future feature touches one of these types. Discriminated unions are a one-time cost that permanently reduces maintenance friction on everything downstream.

---

## Theme 2 — The facts system is under-used (this is the marker-perf problem too)

### The architecture is already in place; two consumers just haven't adopted it

Facts (`State/GuideFactKey.cs`): `InventoryItemCount`, `UnlockItemPossessed`, `QuestActive`, `QuestCompleted`, `Scene`, `SourceState(nodeKey)`, `TimeOfDay`.

Mechanism (`State/GuideDependencyEngine.cs`): `BeginCollection(derivedKey)` → reads call `RecordFact` → engine records reverse-dependencies → later `InvalidateFacts(changedFacts)` returns affected derived keys.

**Only one derived view uses it today** — `QuestResolutionService._cache`, registered via `BeginCollection(new GuideDerivedKey(QuestTargets, cacheKey))`. Everything else uses coarser mechanisms.

### Concrete failures of under-use

**`MarkerComputer` is not a derived view.** `Plugin.cs:534-541` runs `InvalidateFacts` → `InvalidateAffected` for the resolution service's cache, but then unconditionally calls `_markerComputer.ApplyGuideChangeSet(selectorChangeSet)` followed by `_markerComputer.Recompute()`. `MarkerComputer.MarkDirty` always sets `_fullRebuild = true` regardless of which fact changed. The fact deltas are available but discarded.

**The cache is scene-keyed.** `QuestResolutionService.cs:331-334`: `cacheKey = questKey + "\n" + currentScene`. On scene change, `Plugin.cs:529` calls `InvalidateAll`, flushing every entry. But the frontier walk in `SourceResolver` only reads facts of kind `QuestActive/QuestCompleted/InventoryItemCount/UnlockItemPossessed/SourceState` — none of which are scene-keyed. The scene is an output-filter concern (which targets are in this scene) not a frontier-walk input.

**Phase/item state has two sources of truth.** `QuestResolutionRecord` snapshots `_questPhases` and `_itemCounts` at construction (`QuestResolutionService.cs:234-235`). But `SourceResolver`, `UnlockPredicateEvaluator`, and `TrackerSummaryBuilder` read the live `QuestPhaseTracker` directly. If state changes between record creation and read, the two see different worlds. `QuestPhaseTracker.SnapshotPhases/SnapshotItemCounts` (L70-72) performs full array clones on every `BuildRecord`, wasted for records that never touch phase state.

### What the right shape looks like

Two distinct derived-view shapes.

**Quest-scoped, scene-independent: `QuestCompiledTargets(questKey)`.** Output: `IReadOnlyList<ResolvedTarget>`. Facts read: `QuestActive`, `QuestCompleted`, `InventoryItemCount`, `UnlockItemPossessed`, `SourceState(nodeKey)`. **Not `Scene`.** Invalidation: only when a fact the walk actually read changes. Scene change does not touch this cache.

**Scene-scoped, derived from the above: `MarkerCandidatesForScene(sceneName)`.** Output: `Dictionary<nodeKey, MarkerCandidate>` (or a list keyed by spawn point). Built by iterating active+tracked quests' `CompiledTargets` and filtering to `scene == sceneName`. Facts read: `Scene`, `SourceState(nodeKey-in-scene)`, plus a structural dependency on the quest-scoped views. Invalidation: on scene change, on source-state change, on quest set change.

`MarkerComputer` would consume the directory — pure lookup on scene change, no walk. `MarkDirty` disappears, replaced by fact-based invalidation.

### Pre-reqs and unknowns to resolve before committing

- Confirm `_questTargetResolver.Resolve(questIndex, currentScene, frontier, session, tracer)` only uses `currentScene` for output filtering (blocking-route awareness, cross-scene routing). If scene also affects which targets are *emitted*, the split is more complex. **Measurement needed.**
- `QuestTargetProjector.Project(compiledTargets, currentScene)` is the navigation-UI projection, already lazy on the record. Unaffected by the split.
- `MaintainedViewPlanner`'s role needs rethinking. Today it decides full-vs-partial marker rebuild from a `GuideChangeSet`. In the fact-driven world, the dependency engine tells us exactly which scenes/quests are affected — the planner becomes either unnecessary or a thin translator.

---

## Theme 3 — Cache invalidation is a bag of patterns

Inventoried across subsystems:

| Pattern | Used by |
|---|---|
| Version counter | `NavigationTargetSelector.Version`, `FilterState.Version`, `QuestResolutionService.Version`, `MarkerComputer.Version`, `NavigationSet.Version` |
| Reference identity (`ReferenceEquals`) | `ViewRenderer._lastRecordByQuest` |
| Dirty flag | `TrackerState.IsDirty`, `MarkerComputer._dirty`, `GuideConfig._configDirty` |
| Implicit external-reference detection | `CameraCache._lastCamPos` |
| Fact-delta | `QuestResolutionService.InvalidateAffected` |

Each pattern is locally defensible. The mix is not. `ViewRenderer` alone maintains three cache layers (`_lastRecordByQuest`, `_cachedRootChildrenByQuest`, `_cachedChildren + _cachedUnlockChildren`) and then calls through to `SpecTreeProjector.ResetProjectionCaches()` which clears three more.

### What to do

Option 1: **adopt fact-deltas everywhere.** If Theme 2's rework lands, extend it. Every cache becomes a `GuideDerivedView` with a declared fact-dependency set. `GuideDependencyEngine` is already the right mechanism.

Option 2: **centralize version propagation.** Keep version counters but have one authoritative source per concept (e.g. `QuestResolutionService.Version` is the canonical "anything quest-related changed"). All consumers key caches on it. Reference-identity and dirty-flag caches get converted.

Option 1 is a superset of Option 2 and dovetails with the marker-perf work. Option 2 only makes sense if Option 1 turns out to be infeasible.

---

## Theme 4 — `Plugin.Update()` as an undocumented state machine

- **Location:** `src/Plugin.cs:465-650`
- **What it ticks:** LiveStateTracker, QuestStateTracker, GuideDependencyEngine, QuestResolutionService, ZoneRouter, MarkerComputer, NavigationEngine, GroundPathRenderer, MarkerSystem, input handling, UI.
- **What's not enforced:** the order of invalidation → rebuild → recompute → render. Version synchronization across `_lastObservedQuestTrackerVersion`, `_lastResolutionVersion`, `_lastNavSetVersion`. Whether the UI tree reads post-recompute state.
- **No tests** for Plugin.Update. 53 test files cover subsystems but not the seam between them.

### Shape of fix

Extract an `UpdateOrchestrator` with explicit phases:
1. **Capture inputs** (game state, input events)
2. **Publish change deltas** (QuestStateTracker.Sync, LiveStateTracker.UpdateFrameState, producing a single merged `GuideChangeSet`)
3. **Invalidate** (dependency-engine fact invalidation → derived views evict)
4. **Recompute** (resolver warm, marker rebuild, navigation target selection)
5. **Render** (UI, markers, arrow, ground path)

Each phase has a single entry point. The orchestrator becomes testable — drop in fake subsystems, verify phase ordering, verify version consistency. The existing diagnostic span infrastructure (Plugin.cs uses `BeginSpan`/`EndSpan` around most of this) already half-reflects this structure.

---

## Theme 5 — Text formatting duplicated across four builders

Four text/semantic builders, all producing overlapping output:

- `Resolution/NavigationExplanationBuilder.cs` — navigation-detail text
- `Resolution/MarkerTextBuilder.cs` — marker subtext
- `Resolution/ResolvedActionSemanticBuilder.cs` — upstream semantic (consumed by the two above)
- `UI/Tree/SpecTreeProjector.cs:897-987` — 6+ `FormatXxxLabel` methods for the UI tree

The tree-projector's label logic is a *duplicate* of the Resolution-builder logic, not a reuse. `NavigationExplanationBuilder.BuildLootChestExplanation` and `MarkerTextBuilder.BuildInstruction` overlap in what they describe. A single quest target gets its "talk to X" or "kill N of Y" text rendered three times by three systems.

### Shape of fix

One shared text layer: `InteractionLabelFormatter` or `QuestIntentFormatter`. Takes a `ResolvedActionSemantic` (or the discriminated union from Theme 1), produces a structured `InteractionLabel { PrimaryText, SecondaryText, TertiaryText, Kind }`. All four current builders consume it. `SpecTreeProjector` becomes pure tree-construction. `NavigationExplanationBuilder` becomes a thin formatting shell.

This also lets the marker subtext, tracker subtext, and UI tree label be guaranteed-consistent by construction — a current fragility when any one of them is updated.

---

## Theme 6 — Dead code and unearning abstractions

Small individually, collectively significant for cognitive load.

### Delete outright
- `MarkerComputer.cs:489-532` — `CreatePendingCompletionEntry`, never called. Leftover of incomplete refactor.
- `CompiledGuide.cs:284` — `GetNodeType(int)`, single self-use at the definition line.
- `CompiledGuideData.cs:44-45` — `zone_line_ids` field, deserialized and never read; `ZoneRouter.cs:197` rebuilds from `NodesOfType(ZoneLine)`.
- `QuestTargetProjector.cs:21-23` — ctor accepts `PositionResolverRegistry positionResolvers` and immediately discards it.
- `SourceResolver.cs:271-287` — public `ResolveTargets()` / `ResolveUnlockTargets()` never called externally; internal session-aware variants are the only real entry points.

### Collapse thin indirection
- `State/Resolvers/*.cs` (8 files). Each is a 10–30 line wrapper over a single tracker method. The `Dictionary<NodeType, INodeStateResolver>` in `GameState` could be a switch or `Dictionary<NodeType, Func<Node, NodeState>>`. Delete eight files.
- `Position/Resolvers/LiveStateBackedPositionResolver.cs` — abstract base used by two subclasses (MiningNode, ItemBag), each ~30 lines. Inline the shared helper.
- `Markers/CharacterMarkerPolicy.cs` — four tiny predicates on `ResolvedQuestTarget`. Inline into `MarkerComputer.CreateActiveMarkerEntry` or convert to an extension method.
- `Resolution/ItemSourceVisibilityPolicy.cs` — 3-line decision in its own class. Inline into `SourceResolver.GetVisibleItemSources`.
- `Navigation/NavigationDisplay.cs` — one `public const float GroundOffset = 0.50f`. Move to `GuideConfig` (makes it tweakable) or inline at the three call sites.

### Move to where they're consumed
- `State/NavigationHistory.cs`, `State/NavigationSetPersistence.cs` — UI persistence, belong in `Navigation/` or `UI/`.
- `State/GameUIVisibility.cs`, `State/GameWindowOverlap.cs` — game-engine integration for HUD overlap; belong in `UI/` or a new `Integration/`.

**Combined impact:** ~12 files deleted, ~5 files moved, zero behavior change. Reduces the `State/` directory noise and clarifies that `State/` is runtime *guide* state, not "any state in the mod."

---

## Theme 7 — Navigation subsystem has split-brain resolution

- **Location:** `Navigation/NavigationTargetSelector.cs` (816 LOC) vs. `Resolution/NavigationTargetResolver.cs` (532 LOC)
- **Finding:** `NavigationTargetSelector` runs batch resolution (`L198-212`) and maintains its own cache + version counter, despite `NavigationTargetResolver` being the nominally-canonical entry point in `Resolution/`. Two scoring approaches coexist: `NavigationScore.Compute()` for ranking *across* quests, `NavigationTargetSelector.SelectBestCore()` for ranking *within* a quest (8-tier algorithm). The relationship is undocumented.
- **Also:** `TrackerPanel.DrawResolutionSummary` (L411-430) calls `_selector.TryGet()` and `_summaryResolver.Resolve()` separately in the same render frame — two independent resolution reads with no coordination.

### Shape of fix

Pick a single entry point. If `NavigationTargetResolver` is the canonical resolver, `NavigationTargetSelector` becomes pure selection from pre-resolved data. The 8-tier selection algorithm moves to a `TargetRanker` utility consumed by both the per-quest selector and the cross-quest ranker, ensuring consistent priority semantics.

---

## Theme 8 — Diagnostics spans bleed through every subsystem

Every major update path (`Plugin.Update`, `MarkerComputer.Recompute`, `SourceResolver.Resolve*`, `QuestResolutionService.BuildRecord`, `NavigationEngine.Resolve`) wraps its work in `_diagnostics?.BeginSpan(...) / EndSpan(...)`. Subsystems take `DiagnosticsCore?` as a constructor dependency.

- **Location:** `src/Diagnostics/` (12 files, ~1800 LOC), pervasive usage across business code.
- **DebugAPI** (`Diagnostics/DebugAPI.cs`, 519 LOC) is a static global with 15+ fields holding references to every major subsystem — used for HotRepl eval. Tests must initialize or mock it.

### Shape of fix

Two orthogonal moves:
1. **Thin out or merge.** Consolidate `DiagnosticsContext.cs`, `DiagnosticsTypes.cs`, `IIncidentSnapshotProvider.cs`, `StateSnapshot.cs`, `SubsystemSnapshots.cs`, `IncidentBundle.cs` — several are under 50 LOC. Target ~5 files from ~12.
2. **Decouple the recording from the business code.** The `UpdateOrchestrator` in Theme 4 gives a natural seam — record spans at phase boundaries in the orchestrator, not inside each subsystem. Subsystems stop taking `DiagnosticsCore`. Incident capture becomes a wrapper/decorator. This also makes `DebugAPI`'s subsystem registry narrower — it only needs the orchestrator reference plus whatever HotRepl actually pokes at.

---

## Theme 9 — Rendering: custom ImGui backend as build-system debt

- **Location:** `Rendering/ImGuiRenderer.cs` (599 LOC), `Rendering/CimguiNative.cs`
- **Finding:** custom ImGui backend and P/Invoke wrapper exist because ILRepack's merging creates a duplicate `System.Numerics.Vector2` type that breaks marshalling. ~700 LOC of ownership burden for what should be a library consumption.
- **Risk:** every Unity/System.Numerics version bump risks breaking marshalling again. Ownership distracts from the actual mod.

### What to investigate

Can ILRepack be configured to not merge `System.Numerics`? Can ImGui.NET be used without ILRepack merging at all? The answer is either a build-system fix (delete ~700 LOC) or a confirmation that the workaround is structural (make it less invasive — split `ImGuiRenderer` into `CimguiLibraryManager` + `ImGuiContextManager` + `ImGuiUnityRenderer`).

This is narrow and separable — worth a single-afternoon spike to determine feasibility before committing to either path.

---

## Theme 10 — UI state fragmentation

- **TrackerPanel owns animation state** (`TrackerPanel.cs:42-49`: `_animations`, `_fadingOut`, `_completionTimers`). These have lifetimes tied to quest-tracking events, which `TrackerState` already emits. Move the animation lifecycle into `TrackerState`; `TrackerPanel` becomes a pure renderer.
- **FilterState requires post-construction `LoadFrom(config)`** (`FilterState.cs:26-42`). Two-phase init. Either take `GuideConfig` in the constructor, or make it a factory (`FilterState.Create(config)`). Avoids silent loss of persisted filter settings.
- **SpecTreeProjector cache keys use 14-field string concatenation** (`SpecTreeProjector.cs:856-876`). A strongly-typed `record ProjectionCacheKey(...)` would let the compiler enforce which fields participate.

None of these are big changes individually. They're the kind of footguns that generate bugs over time.

---

## Theme 11 — Resolution-pipeline polish (medium-low priority)

Findings that don't cluster with the themes above but are real:

- **`ResolutionSession` exposes public mutable collections** (`SourceResolver.cs:112-177`). 10+ `public readonly` fields holding dictionaries/hashsets. `readonly` only prevents reassignment; the collections themselves can be mutated externally. It's `internal sealed` today, so not a live bug, but trivially footgun if anything changes. Wrap in private fields + controlled accessors.
- **`FrontierEntry.RequiredForQuestIndex` uses -1 sentinel for "not required"** (`Plan/FrontierEntry.cs`). `int?` is the C# idiom. Low-priority cleanup.
- **`SourceResolver.ResolveEntry` is 400+ lines** (L338-750). Not bad, but under-documented. A 5-line summary of the routing strategy at the top would cut onboarding time.
- **`EffectiveFrontier.Phases` exposes the live tracker reference** (`Plan/EffectiveFrontier.cs:15`). Documented as internal but the live-vs-snapshot semantic isn't stated. Minor doc gap.

---

## Open questions for the user

Some findings depend on answers I can't derive from the code.

1. **`QuestResolutionRecord` snapshots — canonical or redundant?** The phase/item snapshots are captured but not always read. Should resolution-time code (SourceResolver, UnlockPredicateEvaluator) read from the record (making it the canonical snapshot) or from the live tracker (making the snapshot copying wasted)?
2. **`NodeType` dead variants?** The enum has 26 variants (Quest, Item, Character, Zone, ZoneLine, SpawnPoint, MiningNode, Water, Forge, ItemBag, Recipe, Door, Faction, Spell, Skill, Teleport, WorldObject, AchievementTrigger, SecretPassage, WishingWell, TreasureLocation, Book, Class, Stance, Ascension). Are all 26 produced by the Python pipeline today, or are some aspirational?
3. **`EdgeType` taxonomy formalization.** 38 edge types. Which edges are legitimate between which node types? This would bound the pattern matching in `ResolvedActionSemanticBuilder.cs:175-202`.
4. **Is ImGui's ILRepack issue worth a spike?** Confirmed-unsolvable → keep as-is. Solvable → ~700 LOC of mod work disappears.
5. **`MaintainedViewPlanner` in a fact-driven world.** If `MarkerComputer` becomes a fact-dependent derived view, does `MaintainedViewPlanner` still have a role, or does the dependency engine subsume it?
6. **Marker types planned for Doors / ZoneLines?** You said "none speculative" for roadmap, but some audit items (NodeType taxonomy, MarkerEntry discrimination) are cheaper to design knowing the answer. Confirming "no" locks the design tighter.

---

## Recommended next step

We're done with audit; brainstorming is next. My suggestion for how to sequence that:

1. **Fix the `TimeOfDay` bug first** (one-line patch, regardless of where the rest goes).
2. **Brainstorm Theme 2 (facts system + scene-independent caching) with Theme 1 (Node/MarkerEntry discriminated unions) as a paired move.** These two are the load-bearing architectural changes. Lazy projection on records, the marker inversion you've been thinking about, and the per-scene directory all fall out naturally once the underlying types and invalidation shape are right. Doing Theme 1 first makes Theme 2 safer; doing them paired means callers only change once.
3. **Theme 4 (`UpdateOrchestrator`) either comes with Theme 2** (the orchestrator is where the phase sequence lives) **or is a separate follow-up refactor**.
4. **Themes 5-11 are cleanup** — each is separable and bite-sized, fair game to interleave.

**If we do Theme 1 + Theme 2 together as the next focused push, the quest-resolution/marker rewrite is the vehicle that carries it.** The performance issue resolves as a side-effect; the maintainability win is the real payoff.
