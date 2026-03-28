# NavigationEngine Redesign

## Problem

Current NavigationEngine does everything per-frame: builds view trees,
computes frontiers, resolves all positions via registry (allocating lists),
runs BFS routing, picks closest target. This is O(N*M) per frame where
N = nav set size and M = graph edges per quest. The old NavigationController
separated expensive resolution (on state change) from cheap per-frame work
(live NPC tracking + distance).

## Design

### Two-phase architecture

**Phase 1: Resolve** — runs on state change, not per frame.
Triggered by: NavigationSet.Version change, QuestStateTracker.Version
change, scene change.

1. For each key in NavigationSet:
   - Quest keys: build view tree, compute frontier
   - Non-quest keys: use directly
2. For each frontier/direct key: resolve to (nodeKey, position, scene)
   candidates via PositionResolverRegistry
3. Pick the best candidate (same-scene preferred, closest by distance)
4. Store the resolved target state: node key, position, scene, display name

**Phase 2: Track** — runs per frame, must be cheap.
1. If target is a character: call EntityRegistry.FindClosest to get live
   transform position. Update TargetPosition in place.
2. If target is dead: read respawn timer from LiveStateTracker for display.
3. Compute distance + direction from player to effective target.
4. Cross-zone: use cached route (already committed).

### State model

```csharp
// Resolved target — set by Resolve(), read by Track()
private string? _targetNodeKey;
private string? _targetScene;
private Vector3 _targetPosition;
private string? _targetDisplayName;
private NavigationTarget.Kind _targetKind; // Character, ZoneLine, Zone, Position

// Cross-zone state
private Vector3? _effectiveTarget; // zone line position when cross-zone
private string? _effectiveDisplayName;

// Change detection
private int _lastNavSetVersion;
private int _lastStateVersion;
private string _lastScene = "";
```

### Resolver allocation fix

Change IPositionResolver.Resolve to write into a caller-provided list
instead of allocating. NavigationEngine owns a single reusable buffer.

```csharp
public interface IPositionResolver
{
    void Resolve(Node node, List<ResolvedPosition> results);
}
```

This eliminates all per-frame list allocations.

### Per-frame cost after redesign

One EntityRegistry.FindClosest call + one distance calc + one direction
calc. Zero allocations. O(1) per frame.

### Files changed

- `IPositionResolver.cs` — change return type to void + list parameter
- All 6 resolvers — adapt to write into list
- `PositionResolverRegistry.cs` — pass buffer through
- `NavigationEngine.cs` — full rewrite with two-phase architecture
- `Plugin.cs` — pass QuestStateTracker to NavigationEngine

### Not in scope (separate commits)

- Navigation persistence (P1-1)
- NAV toggle behavior (P1-2)  
- Respawn timer fallback (P1-3)
- Mining node tracking (P1-4)
- Corpse priority (P1-5)
- Zone line alternatives (P1-6)
- Requirement text (P1-7)

These build ON TOP of the redesigned engine. The engine provides the
foundation; these are features that plug into it.
