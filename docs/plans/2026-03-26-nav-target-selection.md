# Navigation Target Selection Redesign

## Problem

Navigation currently picks a **single** item source and points the arrow/path at it. Three issues:

1. **No zone preference**: `TryNavigateToAnySource` iterates sources in pipeline order (lowest-level first) and picks the first with spawn data. A level-1 mob in another zone is chosen over a level-5 mob in the player's current zone.

2. **Single-source tunnel vision**: Even when multiple enemy types in the current zone can drop the needed item, only one gets the arrow/path. Markers already show all of them, creating an inconsistency.

3. **No manual override**: The step-level [NAV] button auto-selects a source. Clicking a specific source row overrides it, but there's no way to select *multiple* sources or return to auto mode without clearing navigation entirely.

## Current Architecture

```
NavigationController
  Target: NavigationTarget (single point)
    - Kind, Position (mutable), SourceId, Scene, QuestDBName, StepOrder
  ZoneLineWaypoint: NavigationTarget? (cross-zone intermediate)
  
Update() each frame:
  - Live NPC tracking via EntityRegistry.FindClosest(Target.SourceId)
  - Corpse/loot scanning via LootScanner
  - Mining node routing via MiningNodeTracker
  - Cross-zone routing via ZoneGraph + zone line selection
  
Arrow/Path renderers:
  - Read _nav.ZoneLineWaypoint ?? _nav.Target → single position
  - Arrow: screen-space diamond/directional arrow with label
  - Path: NavMesh.CalculatePath to single point
```

## Design

### Core concept: "active source set"

Replace the single SourceId with a **set of active source keys**. The navigation system considers all sources in the active set when picking which spawn point to navigate to.

**Default behavior (auto mode):**
- Collect all sources for the quest item
- If any source has spawns in the current zone → active set = all in-zone sources
- If no in-zone sources → active set = {lowest-level source} (existing behavior)

**Manual override (source toggle):**
- Clicking a source row toggles it in/out of the active set
- The active set persists until: step-level [NAV] is clicked (resets to auto), navigation is cleared, or step advances
- Clicking [NAV] on the step always resets to auto mode

### Navigation target resolution

The arrow/path point at the **closest alive spawn among all spawns from the active source set**. This is the same pattern already used for zone lines (closest of N zone line candidates).

```
Periodically (~250ms) in Update():
  candidates = all spawns from active source keys that are in current scene
  pick closest to player (prefer alive, fallback to shortest respawn)
  set Target.Position = winner
```

This means the arrow dynamically switches to whichever active source NPC is closest to the player. If a player walks past Stoneman A toward Stoneman B, the arrow/path smoothly transitions.

**Update frequency**: The closest-source resolution runs on a throttled interval (~250ms), not every frame. The per-frame live NPC position tracking (which already exists for individual NPCs) still runs every frame to keep the arrow smooth — but which *source* we're pointing at only re-evaluates periodically. This keeps the cost bounded: the expensive part is iterating all spawns from N sources, while tracking a single NPC's transform is trivial.

No hysteresis needed. Enemies barely move, and the arrow/distance display hide within 15m anyway. Better to keep target switching responsive so the player doesn't feel the nav is stuck on the wrong target.

### UI changes

**Source highlighting — visual distinction between auto and manual mode:**
- **Auto mode**: active sources highlighted in the standard nav color (gold)
- **Manual mode**: active sources highlighted in a distinct color (e.g., cyan/teal) to signal the player has overridden auto-selection
- Sources not in the active set but available for toggling are shown normally
- Non-navigable sources (crafting, no scene/spawn data) are visually dimmed

**Source click behavior:**
- Currently: clicking a source calls `NavigateToSource` (replaces target)
- New: clicking a source toggles it in/out of the active set. If the active set becomes empty, revert to auto mode.

**[NAV] button behavior:**
- Currently: toggle between auto-navigate and clear
- New: first click → auto mode (compute active set from zone rules). Click again → clear navigation. This is unchanged externally but resets any manual source overrides.

### Data model changes

```csharp
// NavigationController additions
private HashSet<string> _activeSourceKeys = new();
private bool _manualOverride = false;  // true when user toggled sources

// New methods
public void ToggleSource(string sourceKey);
public bool IsSourceActive(string sourceKey);
```

`NavigationTarget` stays as a single point — no structural change. The controller resolves closest-of-N internally and writes the winner's position to `Target.Position`.

### What stays the same

- **Arrow/Path renderers**: consume single Target.Position — unchanged
- **Cross-zone routing**: unchanged (ZoneLineWaypoint system)
- **WorldMarkerSystem**: already multi-source — unchanged
- **StepProgress**: unchanged
- **IsNavigating(quest, step)**: unchanged — still checks quest+step

### What changes

| Component | Change |
|---|---|
| `NavigationController` | Active source set, zone-preference auto-selection, throttled closest-of-N resolution, ToggleSource/IsSourceActive API |
| `NavigationTarget` | No structural change. SourceId becomes the currently-closest source's key (for display name) |
| `QuestDetailPanel` | Source click → ToggleSource instead of NavigateToSource. Highlight all active sources. |
| `TrackerWindow` | No change needed (uses step-level [NAV] which resets to auto) |

### Implementation phases

1. **Zone-preference auto-selection**: Change `TryNavigateToAnySource` to prefer in-zone sources. Introduce active source set. No UI changes yet.
2. **Throttled closest-of-N**: Change `Update()` to resolve closest spawn among all active sources on a ~250ms interval.
3. **Source toggle UI**: Change `DrawSource` click handler to toggle. Update highlighting for multi-active. Add auto/manual color distinction.
4. **Polish**: Auto-clear manual override on step advance. Ensure zone change recalculates auto set. Dim non-navigable sources.

## Concerns and tradeoffs

**Update throttling and performance**: The closest-source scan iterates all spawns from all active source keys. With N sources averaging M spawns each, this is O(N·M) per evaluation. Throttled to ~250ms (4 evaluations/second) this is negligible — even 10 sources with 30 spawns each is only 300 distance comparisons. The per-frame cost is just tracking one NPC's transform position (already existing). Cache the filtered spawn list on source set or zone change to avoid re-filtering from the full CharacterSpawns dict each tick.

**Source set persistence across zone changes**: When the player changes zones, the auto set should recompute (different sources may be in-zone now). Manual overrides should persist across zone changes (the user explicitly chose those sources).

**Mining nodes**: Mining node sources use zone-level keys (`mining-nodes:{scene}`). The active source set should include these. The existing `UpdateMiningTarget` in Update() handles position resolution for mining nodes — this runs on the same throttled interval as the general closest-source scan, since `FindClosestAlive` iterates all cached nodes.

**Children sources**: Item sources can have `Children` (e.g., quest_reward source with transitive drop sources). The active set should operate at the leaf source level (the actual droppable/obtainable source), not the parent quest_reward level. The current `TryNavigateToAnySource` already recurses into children.
