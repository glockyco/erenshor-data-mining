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

## Character / spawn-point / corpse system

Read this section before touching `CharacterPositionResolver`, `LiveStateTracker`,
`MarkerComputer`, `MarkerSystem`, `QuestResolutionService`, or any `Patches/`
file that intercepts NPC death, spawn, or loot events.

### Graph model

Every killable character has **two graph nodes**:

| Node type | Key format | Role |
|---|---|---|
| `Character` | `character:{prefab_name}` (or `character:{name}:{zone}:{x}:{y}:{z}` for directly-placed) | Conceptual identity; holds loot/quest edges |
| `SpawnPoint` | `spawnpoint:{zone}:{x}:{y}:{z}` | Physical placement in a specific zone |

The `HasSpawn` edge runs **character → spawnpoint**. One character can have
multiple spawn nodes (multi-zone or multi-spawn). The `IsDirectlyPlaced` flag
on a spawn node means the export pipeline synthesised it for a character placed
directly in the Unity scene (no `SpawnPoint` component).

### Full character lifecycle

**1. Spawning** (`SpawnPoint.SpawnNPC`, patched by `SpawnPatch`)**:**
   NPC instantiated at spawn-point transform. `sp.SpawnedNPC = newNPC`,
   added to `NPCTable.LiveNPCs`. `EntityRegistry.Register(newNPC, sp)` then
   `LiveState.OnNPCSpawn(sp)` emitting a `liveWorldChanged` changeset keyed on
   the **spawn-point node key**.

**2. Alive:** `sp.SpawnedNPC` = live NPC; `EntityRegistry.FindClosest` returns
   it. `CharacterPositionResolver` emits `info.LiveNPC.transform.position`
   (follows the NPC as it wanders).

**3. Death** (`Character.DoDeath`, patched by `DeathPatch`)**:**
   `Alive = false`; removed from `NPCTable.LiveNPCs`.
   `NPC.ResetSpawnPoint()` saves `sp.corpsePos` and starts respawn timer.
   `CorpseDataManager.AddCorpseData(...)` persists loot+position for zone
   reentry. NPC game-object stays in scene as a **corpse**; `sp.SpawnedNPC`
   still references it. `EntityRegistry.Unregister(npc)`, then
   `LiveState.OnNPCDeath(npc)` changeset keyed on **spawn-point node key**.

**4. Corpse present** (`SpawnDead` state, `info.LiveNPC != null`):
   `ClassifySpawnPoint` returns `SpawnDead(respawnSeconds)` with
   `LiveNPC = sp.SpawnedNPC` (the dead game object). Corpse is at its
   **kill position**, which may differ from the spawn-point static coordinates.
   `info.LiveNPC.GetComponent<LootTable>().ActualDrops` holds the remaining
   loot and is the authoritative source for corpse loot checks.
   `MarkerSystem.UpdatePosition` tracks the corpse transform per-frame via
   `sp.SpawnedNPC`, so the marker follows the corpse correctly. A separate
   **respawn-timer marker** (`|respawn` node-key suffix) shows simultaneously
   at the static spawn coordinates. Both markers coexist; they use different
   node keys and do not compete for the same marker slot.

**5. Corpse looted:** items taken from the loot window trigger
   `Inventory.UpdatePlayerInventory` → `InventoryPatch` →
   `QuestStateTracker.OnInventoryChanged`. When all items are taken,
   `npc.ExpediteRot()` sets `rotTimer = 5f` and the corpse disappears within
   a few frames.

**6. Corpse rotted** (natural decay or post-loot): `rotTimer` hits 0,
   `Object.Destroy(npc.gameObject)`. `sp.SpawnedNPC.gameObject == null`.
   `CharacterPositionResolver` sees `corpsePresent = false` and emits the
   static spawn-point position with `isActionable = false`. Markers show
   the respawn timer only.

**7. Respawn** (`SpawnPoint.Update` → `SpawnNPC`):
   New NPC instantiated. `sp.SpawnedNPC = newNPC`. Old corpse (if still in
   scene) is no longer reachable via `sp.SpawnedNPC`. `SpawnPatch` fires;
   `UpdateSpawnState` transitions marker back to kill-type immediately.

**8. Zone exit with unlooted corpse:** `CorpseDataManager.CheckAllCorpses()`
   prunes expired entries. `CorpseData` (managed C# object, not a Unity
   scene component) persists in memory with the saved loot and position.

**9. Zone reentry** (`ZoneAnnounce.SpawnAllCorpses()`, patched by
   `CorpseChestPatch`):
   `CorpseData.SpawnMe` instantiates a `CorpseChest` prefab (`RotChest +
   LootTable`) at the saved corpse position. **`RotChest` and `ItemBag` are
   completely independent systems**; the chest uses `LootTable` for looting
   (not `ItemBag.PickUp`). `CorpseChestPatch.Postfix` calls
   `LiveState.OnAllCorpsesSpawned()`, which scans for `RotChest` objects and
   updates `_rotChests`. `GetRotChestPositionsWithItem` is then called live
   during resolution to check if any chest contains the required item.

### Directly-placed characters

Characters placed directly in the Unity scene have `MySpawnPoint = null` and
are **not** in `NPCTable.LiveNPCs`. The export pipeline creates a synthetic
`IsDirectlyPlaced = true` spawn node at the character's graph coordinates.

Live-state resolution for directly-placed NPCs goes through
`ResolveDirectlyPlacedSpawn` → `FindNpcByNameAndProximity`, which searches
`_npcByName` (populated at scene load via `FindObjectsOfType<NPC>()`, includes
all NPCs alive or dead). The character-with-position path in
`FindNpcByNameAndProximity` returns the closest NPC by name **regardless of
alive status**, so the dead NPC (corpse) is returned when it is still in the
scene. The resulting `SpawnInfo.LiveNPC` is the dead NPC game object, exactly
as for spawn-point NPCs. **Verified via HotRepl (Timothy Allorn):**
`GetSpawnState` on the synthetic spawn node returns
`SpawnDead, LiveNPC=Timothy Allorn, LiveSpawnPoint=null` when dead.

Directly-placed NPCs respawn via **zone reentry** (Unity re-instantiates scene
objects). The `ZoneReentry` marker (`MarkerType.ZoneReentry`) is shown when the
NPC is in `SpawnDead` state with no corpse (`LiveNPC == null`) AND the spawn
node is `IsDirectlyPlaced = true`.

### Corpses are their own entity

A corpse is an NPC game object with `Character.Alive = false`. It is a
first-class entity. **Do not think of a corpse as "the spawn point's dead
NPC".** The spawn node is only a lookup key to reach `info.LiveNPC`.

Loot checks are purely on the corpse game object:

```csharp
// Works for both spawn-point and directly-placed NPCs.
// No spawn-point mediation required.
var loot = info.LiveNPC.GetComponent<LootTable>();
bool hasItem = loot?.ActualDrops.Any(d => d != null &&
    "item:" + d.name.Trim().ToLowerInvariant() == itemStableKey) == true;
```

`LiveStateTracker.CorpseContainsItem(Node spawnNode, string itemKey)` encapsulates
this and is the single canonical method for the check.

### Position cache exclusion rule

`SourcePositionCache` does **not** cache positions for `NodeType.Character`.
Character positions depend on live NPC state (death, spawn, movement) and
must be re-resolved on every target-rebuild pass. All other source types
(item bags, mining nodes, zone lines) are cached as before.

This is enforced in `SourcePositionCache.Resolve(nodeKey)` via a node-type
check before the cache lookup. The old workaround of evicting by spawn-point
key has been removed; the exclusion rule makes it unnecessary.

### LootChest targets (zone-reentry chests)

`ResolvedActionKind.LootChest` and `NavigationTargetKind.LootChest` mark
targets produced from zone-reentry `RotChest` objects. Key properties:

- **Synthetic `TargetNodeKey`**: `"chest:{scene}:{x:F2}:{y:F2}:{z:F2}"`. Not
  present in the graph. `_graph.GetNode(key)` returns `null`, so
  `NavigationEngine.Track()` naturally skips `FindClosest` (the condition
  `targetNode?.Type == NodeType.Character` is false). `NavigationEngine.Resolve()`
  detects a target-identity change when switching between a live NPC and a
  chest because the key differs.
- **Static position**: chest does not move. `EffectiveTarget` is set once by
  `SetTarget`; `Track()` does not update it.
- **`ApplyLiveActionOverride` short-circuits** for `LootChest` action kind.
- **Marker**: `IsLootChestTarget = true` on `MarkerEntry`. `MarkerSystem`
  hides the marker per-frame when `LiveRotChest.gameObject == null` (chest
  has rotted). `UpdatePosition` is not called for chest entries.
- **Loot change detection**: `GetRotChestPositionsWithItem` is a live query.
  After the required item is picked up, `InventoryPatch` fires, the quest
  objective completes, and the target cache is evicted. On the next rebuild the
  chest target is no longer produced. No separate chest-loot changeset needed.

### Invariants to maintain

1. Death and spawn events emit facts keyed by the **spawn-point node key**.
   This is correct for `_targetCache` eviction via the dependency engine.
   Character positions are excluded from cache so no additional eviction is
   needed for position cache correctness.
2. `CorpseContainsItem` must be called inside a `BeginCollection` scope so
   the `GetSpawnState` call records its dependency fact correctly.
3. Synthetic `TargetNodeKey` values for chest targets must never collide with
   real graph node keys. The `chest:` prefix is not used by any graph node type.
4. `OnAllCorpsesSpawned` clears `_rotChests` before scanning. `OnSceneLoaded`
   also clears it so stale references from a previous scene session never leak.