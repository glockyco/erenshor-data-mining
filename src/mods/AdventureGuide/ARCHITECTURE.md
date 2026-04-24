# AdventureGuide Architecture

This file is the current architecture reference for the AdventureGuide mod.
It describes what is true in the code now. Historical plans and temporary
execution docs are not the source of truth.

Related durable decisions live in `src/mods/AdventureGuide/docs/adr/`.

## Documentation model

- Current architecture: this file.
- Durable decisions: ADRs in `docs/adr/`.
- Temporary execution notes: plans/specs outside the subsystem; they should be
  deleted from `HEAD` once implemented or superseded.

## Layer hierarchy

The mod is organised into strict layers. Each layer may only import from layers
below it. No upward or lateral dependencies.

| Layer | Namespaces | Responsibility |
|---|---|---|
| Graph | `AdventureGuide.Graph`, `AdventureGuide.CompiledGuide` | Immutable world data: `Node`, `Edge`, compiled guide, blueprints |
| State | `AdventureGuide.State` | Runtime game conditions: quest journal, inventory, live scene objects, source snapshots, source categories |
| Frontier | `AdventureGuide.Frontier` | Quest phase and frontier tracking |
| Position | `AdventureGuide.Position` | World coordinate resolution per node type; cross-zone routing |
| Resolution | `AdventureGuide.Resolution` | Compiled target resolution, explanations, tracker summaries |
| Navigation | `AdventureGuide.Navigation` | Target selection, arrow renderer, ground path |
| Markers | `AdventureGuide.Markers` | World-space candidate projection and live marker presentation |
| UI | `AdventureGuide.UI`, `AdventureGuide.UI.Tree` | Guide window, tracker, detail tree |
| Rendering | `AdventureGuide.Rendering` | ImGui/Unity backend |
| Config | `AdventureGuide.Config` | BepInEx config entries |
| Incremental | `AdventureGuide.Incremental` | Generic query engine and recompute tracing used by maintained views |

`Diagnostics/` and `Patches/` are cross-cutting. `Plugin.cs` is the
composition root and frame orchestrator.

## Current runtime data flow

### 1. Capture and publish

`QuestStateTracker`, `LiveStateTracker`, `NavigationSet`, and `TrackerState`
observe game events and produce `ChangeSet` / `FactKey` deltas.

Key types:
- `State/FactKey.cs`
- `State/ChangeSet.cs`
- `State/QuestStateTracker.cs`
- `State/LiveStateTracker.cs`

### 2. Maintained/query-backed truth

The incremental engine owns derived views. Most top-level consumers read them
through `State/GuideReader.cs`; marker projection owns its marker-candidate query
read directly so State does not depend upward on Markers.

Important queries:
- `Resolution/Queries/CompiledTargetsQuery.cs`
- `Resolution/Queries/QuestResolutionQuery.cs`
- `Navigation/Queries/NavigableQuestsQuery.cs`
- `Navigation/Queries/SelectorTargetSetQuery.cs`
- `Navigation/Queries/NavigableQuestResolutionsQuery.cs`
  - defines `NavigationTargetSnapshotsQuery`
- `Position/Queries/ZoneLineAccessibilityQuery.cs`
- `Resolution/Queries/BlockingZonesQuery.cs`
- `Markers/Queries/MarkerCandidatesQuery.cs`

### 3. Consumers

Consumers do not invent alternate truth.

- `NavigationTargetSelector` consumes maintained navigation target snapshots and
  reranks locally using player position and live source snapshots.
- `NavigationEngine` follows the currently selected concrete source.
- `TrackerSummaryResolver` reads the same resolution truth used by navigation.
- `MarkerProjector` consumes marker candidates plus live source snapshots and owns
    marker-specific render-state projection.
- `SpecTreeProjector` consumes shared resolution/query-backed data for the
  detail tree.

## Incremental diagnostics

`Incremental/Engine.cs` is the maintained-view cache. It reports successful
recomputes, invalidations, and failed recomputes through `IEngineTracer`.
Failed recompute tracing must preserve the original exception path while
recording the query name, key, exception, and compute duration for diagnostics.

## Identity model

Three identities matter and must not be conflated.

| Layer | Canonical key | Meaning |
|---|---|---|
| Conceptual source | character/item/quest node key | Domain entity and semantics |
| Physical source | spawn/itembag/mining node key | One concrete world placement |
| Concrete target instance | `ResolvedQuestTarget.SourceKey ?? TargetNodeKey` | The specific world object NAV and markers cut over between |

`TargetNodeKey` is not a world-instance identity when a target has multiple
spawns. Physical source keys win whenever one exists.

## Live source model

`LiveStateTracker` is the only owner of live source truth.

Primary types:
- `State/LiveSourceSnapshot.cs`
- `State/SpawnCategory.cs`
- `Markers/MarkerLiveRenderState.cs`

`LiveSourceSnapshot` carries source-keyed occupancy, actionability, live/static
anchor information, respawn timing, and unlock reason. `SpawnCategory` is source
state used by maintained marker-candidate queries. `NavigationTargetSelector`
and `MarkerProjector` consume `LiveSourceSnapshot`; only the marker layer may
derive `MarkerLiveRenderState` presentation from it.

Important consequence: consumers may rank or present targets differently, but
none of them may independently decide whether a source is alive, lootable,
mined, picked up, blocked, or out of scene.

## Navigation architecture

Navigation is split cleanly between resolution, selection, and tracking.

- `Resolution/NavigationTargetResolver.cs` resolves targets from graph/query
  truth. Quest and non-quest targets both flow through this layer.
- `NavigationTargetSelector` chooses the best target per selected key. It reads
  `NavigationTargetSnapshots`, then applies proximity and live-source-aware
  reranking.
- `NavigationEngine` owns the current active target, route hop state, and live
  tracking of the selected source.

The selector must never rediscover resolution truth by ad hoc polling. The
maintained snapshot query is the canonical change surface.

## Marker architecture

Markers are a projection of shared resolution truth plus current live render
state.

- `MarkerCandidatesQuery` produces scene-scoped static candidates.
- `MarkerProjector` turns candidates and `LiveSourceSnapshot` values into
    stable `MarkerEntry` rows and marker presentation state.
- `MarkerRenderer` renders projected entries. It does not own source truth.

`MarkerProjector.InvalidateProjection()` exists for scene-reload rebinding. It
is a projector-local cache reset, not a second truth source.

`MarkerEntry.Type` and `MarkerLiveRenderState` are presentation state, not
source-state authority.

## Source visibility policy

When at least one hostile `DropsItem` source exists for an item, friendly
`DropsItem` sources are suppressed. Non-drop sources (`SellsItem`, `GivesItem`,
etc.) are always shown.

There is one owner for this rule:
- `Resolution/ItemSourceVisibilityPolicy.Filter`

Callers delegate to that policy; they do not reimplement it.

## Character, corpse, and re-entry lifecycle

Every character source resolves to one of these effective states:
- alive in scene
- corpse present
- spawn empty / waiting for respawn
- night locked
- unlock blocked
- disabled
- unknown / out of scene
- zone re-entry chest (for persisted corpses)

Rules that must remain true:
1. Death/spawn/corpse facts are keyed by the physical source node.
2. `CorpseContainsItem` and corpse/RotChest loot-position reads must run inside
   dependency collection so source-state facts are recorded correctly.
3. A dead character source and its loot opportunities are distinct projections:
   spawn-point respawn markers stay at the static spawn point, directly placed
   zone-reentry markers stay at the directly placed location, and corpse/chest
   loot markers may appear at the corpse/chest only when that live container
   holds a required item.
4. Live-state-dependent source types (`Character`, `MiningNode`, `ItemBag`)
   must not be hidden behind stale position caches.
5. Non-actionable character targets do not emit an active character marker.
   Dead/empty representation belongs to the runtime overlay state.
6. If two resolved lifecycle targets share the same physical source key, NAV and
   markers treat them as one concrete source instance. Confirmed loot targets do
   not collapse into the lifecycle source marker.

## Off-scene and current-scene rules

Only the loaded scene has live Unity objects. Off-scene targets must not borrow
live NPCs, corpses, mining nodes, or item bags from the current scene.

Relevant code:
- `State/LiveSceneScope.cs`
- `Position/Resolvers/CharacterPositionResolver.cs`
- `State/LiveStateTracker.cs`

When debugging a target that appears in the wrong scene, inspect these first.

## Directly placed characters

Directly placed NPCs use synthetic spawn-node identities. Treat those synthetic
spawn keys exactly like normal physical source keys for NAV and markers.

When dead with no corpse present, directly placed characters fall back to a
zone-reentry state rather than `SpawnPoint.Update`-style respawn handling.

## What to update when architecture changes

Update this file when you change:
- layer ownership
- maintained/query-backed truth surfaces
- source identity or live-state invariants
- selector/tracker/marker truth boundaries
- any rule that future changes must preserve to avoid reintroducing regressions
