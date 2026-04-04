# AdventureGuide — Architecture Notes

This file is read by any agent working in the AdventureGuide mod. Read it
before touching source files under `src/` or `tests/`.

---

## Layer hierarchy

The mod is organised into strict layers. Each layer may only import from layers
below it. No upward or lateral dependencies.

| Layer | Namespaces | Responsibility |
|---|---|---|
| **Graph** | `AdventureGuide.Graph` | Immutable world data: `Node`, `Edge`, `EntityGraph`, `CompiledSourceIndex`, blueprints |
| **State** | `AdventureGuide.State` | Runtime game conditions: quest journal, inventory, live scene objects, per-type node state |
| **Plan** | `AdventureGuide.Plan`, `.Plan.Semantics` | Derived dependency structure: plan tree, feasibility propagation, frontier, faction rules |
| **Position** | `AdventureGuide.Position` | World coordinate resolution per node type; cross-zone routing |
| **Resolution** | `AdventureGuide.Resolution` | Answers "what should the player do now?": plan caching, target resolution, position lookup |
| **Navigation** | `AdventureGuide.Navigation` | Arrow renderer, ground path, proximity-based target selection |
| **Markers** | `AdventureGuide.Markers` | World-space billboard markers from resolution outputs |
| **UI** | `AdventureGuide.UI`, `.UI.Tree` | Dear ImGui windows: guide panel, tracker, detail tree via `LazyTreeProjector` |
| **Rendering** | `AdventureGuide.Rendering` | ImGui/Unity backend; no AG dependencies |
| **Config** | `AdventureGuide.Config` | BepInEx config entries |
| **Frontier** | `AdventureGuide.Frontier` | Selected navigation target set; no AG dependencies |

`Diagnostics/` and `Patches/` are cross-cutting: they depend on many layers
above but have no callers. `Plugin.cs` is the composition root.

---

## Source-visibility policy

### The rule

When at least one hostile `DropsItem` source exists for an item, friendly
`DropsItem` sources are suppressed. Non-drop sources (SellsItem, GivesItem,
etc.) are always shown.

### Where it lives

`Plan/SourceVisibilityPolicy.cs` — in the **Plan** layer alongside
`FactionChecker`, which it delegates to. Both `Resolution` and `UI.Tree`
already depend on `Plan`, so neither creates a new cross-layer edge by
importing this class.

```mermaid
flowchart LR
    MC["Markers / NAV / Tracker"]
    VP["Quest detail panel"]
    QRS(["★ QuestResolutionService"])
    CSI["CompiledSourceIndex"]
    QP["QuestPlan · LazyTreeProjector"]

    MC -->|targets| QRS
    VP -->|source lists| QRS
    VP -->|objective tree| QP
    QRS -->|source sites| CSI
```

### Two rendering paths

| Surface | Code path | Filter mechanism |
|---|---|---|
| Markers, NAV arrow, tracker | `QuestResolutionService.ApplyHostileDropFilter` | delegates to `SourceVisibilityPolicy.FilterBlueprints` |
| Quest detail panel | `LazyTreeProjector.CollectVisibleRefs` flatten branch for `PlanGroupKind.ItemSources` groups | two-pass loop using `SourceVisibilityPolicy.IsHostileDropSource` |

`ViewRenderer` constructs its own `SourceVisibilityPolicy` and passes it to
`LazyTreeProjector`. `QuestResolutionService` constructs its own.
The policy is stateless; shared instances are not required.

### Adding a new visibility rule

1. Add the rule to `SourceVisibilityPolicy` (new method or extend existing).
2. Apply in `QuestResolutionService.ApplyHostileDropFilter` (blueprint path).
3. Apply in `LazyTreeProjector.CollectVisibleRefs` (plan-tree path) using the
   predicate or new method.
4. Add tests to `Plan/SourceVisibilityPolicyTests.cs`.
5. Update this AGENTS.md if the topology changes.

### Do not add filter logic elsewhere

`QuestPlanBuilder` builds unfiltered structure. `CompiledSourceIndex` is
pure precompiled data. Source-visibility policy belongs exclusively in
`SourceVisibilityPolicy`.

---

## `PlanGroupKind.ItemSources`

Source groups for items use `PlanGroupKind.ItemSources` (not `AnyOf`). This
lets `LazyTreeProjector.CollectVisibleRefs` identify them by kind for the
visibility filter without key-string matching. Semantics for feasibility
propagation are identical to `AnyOf`: infeasible when all children are
infeasible.

The group key is still `{itemKey}:sources:anyof` (internal deduplication
string, not the kind enum). Do not rely on the key string to detect source
groups — use `GroupKind == PlanGroupKind.ItemSources`.

---

## Known architectural debt

These pre-existing violations should be fixed in separate dedicated changes.
They do not affect correctness today but should not be compounded.

| Violation | Files affected | Correct location |
|---|---|---|
| `Graph` → `Markers` | `GraphIndexes.cs`, `QuestGiverBlueprint.cs`, `QuestCompletionBlueprint.cs` import `MarkerInteraction` | `MarkerInteraction` belongs in `Graph/` |
| `Config` ↔ `UI` circular | `GuideConfig` uses `QuestFilterMode`/`QuestSortMode` from `UI/` | Move enums to `Config/` |
| `State` → `UI` | `TrackerState` uses `TrackerSortMode` from `UI/` | Move `TrackerSortMode` to `State/` |
| `Navigation` → `UI` | `ArrowRenderer` imports `Theme` for two color constants | Inline constants or move to `Rendering/` |
| `Navigation` ↔ `Resolution` circular | `NavigationGoalKind`, `NavigationTargetKind`, `TrackerSummary` in `Navigation/` but embedded in `Resolution` types | Move to `Resolution/` |
