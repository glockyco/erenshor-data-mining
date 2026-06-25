# Adventure Guide: Product & Architecture Specification

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Full product spec + architecture decision record for the Adventure Guide BepInEx mod

---

## 1. Overview

Adventure Guide is a BepInEx companion mod for Erenshor that adds quest guidance,
world-space markers, GPS navigation, and a quest tracker overlay. It processes a
static entity graph (exported from the game database) alongside live game state to
answer the question "what should the player do next?" and render that answer across
four surfaces: a guide window, a quest tracker, world markers, and a navigation arrow.

**Target users:** Erenshor players who want quest guidance without alt-tabbing to a wiki.

**Feature inventory:**

| Feature | Hotkey | Description |
|---|---|---|
| Guide Window | L | Split-panel: quest list (filter/sort) + detail tree (objectives, sources, prerequisites) |
| Quest Tracker | K | Compact overlay showing pinned quests with live progress and distance |
| World Markers | -- | Floating billboards above NPCs: quest givers, objectives, turn-ins, respawn timers |
| NAV Arrow | -- | GPS arrow pointing to the nearest relevant target for each navigated entity |
| Ground Path | P | NavMesh path line on the ground to the target |

All features are independently toggleable via BepInEx ConfigurationManager (F1) or
config file.

---

## 2. Data Foundation

### 2.1 Entity graph

The entity graph is the mod's immutable world model. It represents every quest, item,
character, zone, spawn point, recipe, mining node, and other game entity as typed nodes
connected by typed edges. Loaded once at startup from an embedded JSON resource.

**Node types (25):** Quest, Item, Character, Zone, ZoneLine, SpawnPoint, MiningNode,
Water, Forge, ItemBag, Recipe, Door, Faction, Spell, Skill, Teleport, WorldObject,
AchievementTrigger, SecretPassage, WishingWell, TreasureLocation, Book, Class, Stance,
Ascension.

**Edge types (30):** RequiresQuest, RequiresItem, StepTalk, StepKill, StepTravel,
StepShout, StepRead, CompletedBy, AssignedBy, RewardsItem, ChainsTo, AlsoCompletes,
UnlocksZoneLine, UnlocksCharacter, AffectsFaction, UnlocksVendorItem, CraftedFrom,
TeachesSpell, AssignsQuest, CompletesQuest, UnlocksDoor, EnablesInteraction, DropsItem,
SellsItem, GivesItem, SpawnsIn, HasSpawn, BelongsToFaction, Protects, RequiresMaterial,
Produces, ConnectsTo, Contains, YieldsItem, SpawnsCharacter, GatedByQuest,
StopsAfterQuest, ConnectsZones, RemovesInvulnerability.

### 2.2 Stable key formats

All entity keys use the format `{type}:{identifier}`, normalized to lowercase with
trimmed whitespace. Coordinates use two decimal places.

| Entity type | Key format | Example |
|---|---|---|
| Quest | `quest:{db_name}` | `quest:a way to erenshor` |
| Item | `item:{resource_name}` | `item:iron ore` |
| Character (prefab) | `character:{object_name}` | `character:islander bandit` |
| Character (placed) | `character:{object_name}:{scene}:{x}:{y}:{z}` | `character:guard:stowaway:342.23:52.52:490.37` |
| Character (variant) | `...:{index}` appended to above | `character:islander bandit:2` |
| Spawn point | `spawn:{scene}:{x}:{y}:{z}` | `spawn:stowaway:342.23:52.52:490.37` |
| Trigger spawn | `trigger:{scene}:{x}:{y}:{z}` | `trigger:stowaway:100.00:5.00:200.00` |
| Zone | `zone:{scene}` | `zone:stowaway` |
| Zone line | `zoneline:{source}:{dest}:{x}:{y}:{z}` | `zoneline:stowaway:azure:50.00:5.00:100.00` |
| Mining node | `mining:{scene}:{x}:{y}:{z}` | `mining:azure:100.00:5.00:200.00` |
| Water | `water:{scene}:{x}:{y}:{z}` | `water:stowaway:50.00:0.00:100.00` |
| Door | `door:{scene}:{x}:{y}:{z}` | `door:stowaway:10.00:5.00:20.00` |
| Forge | `forge:{scene}:{x}:{y}:{z}` | |
| Item bag | `itembag:{scene}:{x}:{y}:{z}` | |
| Faction | `faction:{refname}` | `faction:dawnfolk` |
| Spell | `spell:{resource_name}` | |
| Skill | `skill:{resource_name}` | |
| Other | `{type}:{resource_name}` or `{type}:{scene}:{x}:{y}:{z}` | |

**Disambiguation:** When multiple game objects produce the same base key, a `:{index}`
suffix is appended (index starting at 1 for the second instance). This applies
primarily to characters.

### 2.3 Identity model -- three layers

| Layer | Key source | Example | Purpose |
|---|---|---|---|
| Conceptual source | Character node key | `character:islander bandit` | Loot edges, quest semantics, display name |
| Physical source | SpawnPoint node key | `spawn:stowaway:342.23:52.52:490.37` | Concrete world placement in one scene |
| Target instance | `SourceKey ?? TargetNodeKey` | Derived at resolution time | Canonical identity for markers, NAV, change detection |

A character can have many physical sources. Multiple character nodes may share the same
physical source (common for NPC variants with identical loot/display). The target
instance key is the physical source when one exists, falling back to the conceptual key.

**This identity model is non-negotiable.** Markers, NAV cutover, same-target change
detection, and contribution-based deduplication all operate on the target instance key,
never the conceptual character key alone.

### 2.4 Compiled source index

`CompiledSourceIndex` precomputes at startup the complete set of source-site blueprints:
which entities provide which items, through which edge types, at which positions. These
blueprints are immutable and shared across all quest resolutions. This avoids redundant
graph traversal during target materialization.

### Acceptance criteria

1. Graph loads in <100ms for the full game dataset
2. All node/edge types from the export pipeline are represented
3. Identity layers are used consistently throughout the codebase
4. CompiledSourceIndex produces deterministic results for identical graphs
5. Stable key format matches between export pipeline (C#/Python) and mod (C#)

---

## 3. State & Change Propagation

The state layer tracks two categories: **quest journal state** (which quests are
active/completed, inventory counts) and **live world state** (NPC spawn/death, corpse
lifecycle, mining node availability, item bags, doors, time-of-day).

### 3.1 Quest state tracking

`QuestStateTracker` mirrors the game's quest journal via Harmony patches on
`GameData.AssignQuest`, `GameData.FinishQuest`, and inventory changes. It maintains:

- Active quests (set of DB names)
- Completed quests (set of DB names)
- Item counts (from `GameData.PlayerInv.StoredSlots`)
- Implicitly available quests (no assignment step)
- A version counter that increments on any change

### 3.2 Live world state tracking

`LiveStateTracker` tracks the NPC lifecycle and other live entities:

1. **Spawn** -- `SpawnPatch` calls `OnNPCSpawn(sp)`, fact keyed by physical source
2. **Alive** -- live NPC transform tracked per-frame
3. **Death** -- `DeathPatch` calls `OnNPCDeath(npc)`, corpse remains as game object
4. **Corpse present** -- loot checked from `LootTable.ActualDrops` on the corpse object
5. **Corpse rot** -- Unity destroys corpse, source becomes SpawnEmpty
6. **Respawn** -- `SpawnPoint.Update` creates new NPC, source returns to Alive
7. **Zone exit with unlooted corpse** -- `CorpseDataManager` persists data
8. **Zone reentry chest** -- `CorpseData.SpawnMe` creates `RotChest` with loot table

**Occupancy states:**

| State | Meaning | Position anchor |
|---|---|---|
| Alive | Live NPC, `Character.Alive` is true | Live NPC transform |
| CorpsePresent | NPC dead but game object still exists | Corpse transform at kill position |
| SpawnEmpty | No game object at spawn point | Static spawn coordinates |
| NightLocked | Night-only spawn, currently daytime | Static spawn coordinates |
| UnlockBlocked | Gated by quest/world state | Static spawn coordinates |
| Disabled | Cannot spawn for gameplay reasons | Static spawn coordinates |
| Unknown | Out of scene or state unavailable | Static/exported coordinates |

### 3.3 Game state aggregation

`GameState` is a central registry delegating state resolution to per-NodeType resolvers.
Each node type (Quest, Item, Character, SpawnPoint, MiningNode, ItemBag, Door, ZoneLine)
has a dedicated resolver that queries the appropriate tracker.

### 3.4 Change propagation

Changes flow through the system as **events**, not cache invalidation:

| Event | Producer | Consumers |
|---|---|---|
| Quest assigned/completed | QuestStateTracker (via Harmony patches) | Marker computer, NAV selector |
| Inventory changed | QuestStateTracker (via Harmony patches) | Marker computer, NAV selector |
| NPC spawned/died | LiveStateTracker (via Harmony patches) | Marker computer, NAV selector |
| Mining/bag/door changed | LiveStateTracker (via Harmony patches) | Marker computer, NAV selector |
| Scene changed | Plugin.OnSceneLoaded | All components |

When an event occurs, affected consumers re-request fresh resolution from the stateless
resolution pipeline. Impact analysis uses the immutable graph structure to determine
which quests are affected (see Section 6.3).

### 3.5 Directly-placed characters

Directly-placed NPCs have `MySpawnPoint = null` and no real `SpawnPoint` component. The
export pipeline creates a synthetic spawn node with `IsDirectlyPlaced = true`. This
synthetic node is treated identically to any other physical source for NAV and marker
identity. Live-state lookup goes through name + proximity matching. Respawn happens via
zone reentry, not `SpawnPoint.Update`.

### Acceptance criteria

1. Quest assign/finish patches fire synchronously and update tracker before the next frame
2. NPC spawn/death facts are keyed by physical source node, never conceptual character key
3. Scene change clears all live state indexes and re-scans
4. Corpse loot checks read `LootTable.ActualDrops` from the corpse game object, not static tables
5. Directly-placed NPCs use synthetic spawn nodes as their physical source identity

### Known defects

- Proximity-based NPC matching (2.0f threshold) can bind the wrong NPC when multiple
  exist at similar positions
- `OnAllCorpsesSpawned` rebuilds all spawn sources (not selective)

---

## 4. Architecture: Compiled Guide

### 4.1 The problem

The mod must answer "what should the player do next?" for many quests simultaneously.
Quest dependency trees include transitive chains: quest -> required items -> item sources
(characters, quests, recipes) -> recipe materials -> more items -> more sources -> unlock
chains -> more quests. Early in the game, most entities are blocked by unlock chains,
causing these trees to balloon to hundreds or thousands of nodes.

Previous approaches oscillated between correctness and performance: rebuilding plans from
scratch on every change was correct but slow; caching plans with selective invalidation
was fast but produced stale data (30+ fix commits in the recent rewrite traced back to
cache invalidation bugs).

### 4.2 Key insight: structure is static, state is dynamic

The entity graph never changes at runtime. Which quests depend on which quests, which
items come from which sources, which zone lines are unlocked by which quests -- all of
this is determined by graph edges and known at export time. What changes at runtime is
*status*: which quests are completed, which items the player has, which NPCs are alive.

The previous plan builder mixed these concerns: it built the structural dependency graph
AND applied runtime state in the same pass. This meant whenever state changed, structure
had to be rebuilt too -- even though structure hadn't changed.

### 4.3 Solution: compile structure at build time, overlay state at runtime

The **compiled guide** approach separates structural computation from runtime state by
moving plan building, frontier analysis, and source indexing to a Python build step.

**Build time** (`erenshor guide compile`):

The Python compiler reads the clean SQLite database and produces `guide.json` containing:

- **Nodes and edges** as dense integer-indexed arrays with forward/reverse adjacency
- **Quest specs** per quest: prerequisite quest IDs, required items (with quantities and
  groups), step sequence (type + target + ordinal), giver/completer node IDs, chain-to
  IDs, implicit/infeasible flags
- **Item sources** per item: source sites with edge type, positions, spawn IDs, direct
  item ID for transitive crafting chains
- **Unlock predicates** per locked entity: which quests/items are required to unlock
- **Scene-indexed blueprints** for quest givers, completion targets, and static sources
- **Dependency indexes**: item-to-quest, quest-to-dependent-quest, source-to-quest
  reverse maps for impact analysis
- **Zone connectivity**: zone adjacency graph with zone line IDs for cross-zone routing
- **Topological order** and **infeasible node IDs** for structural analysis

This is computed once per game version, not per session. The expensive DFS, cycle
detection, transitive expansion, infeasibility propagation, and source indexing all
happen here.

**Load time** (mod startup):

`CompiledGuide` deserializes `guide.json` and projects `Node[]` and `Edge[]` from the
DTO arrays. It builds all derived indexes: nodes by type, quests by db-name,
item-to-quest and quest-to-quest dependency maps, source-to-quest reverse index, and
scene-indexed blueprints. The public API mirrors the previous EntityGraph + GraphIndexes
surface: `GetNode(string)`, `NodesOfType`, `OutEdges`, `InEdges`, `GetQuestByDbName`,
`GetQuestsDependingOnItem`, `GetQuestsDependingOnQuest`, `GetQuestsTouchingSource`, and
scene-scoped blueprint lookups.

**Runtime** (on events, cheap):

When state changes, the runtime overlay is lightweight:

1. `QuestPhaseTracker` classifies each quest's current phase (not-started, active,
   completed) from the quest journal. Frontier entries are derived from the precomputed
   quest spec + current phase -- no plan traversal needed.
2. `SourceResolver` materializes targets from precomputed item sources + live position
   resolvers. Hostile drop filtering uses the precomputed source site data.
3. `UnlockPredicateEvaluator` evaluates precomputed unlock predicates against current
   quest/item state -- no graph traversal needed.
4. `NavigationTargetResolver` produces resolved targets for the NAV system.
5. `TrackerSummaryResolver` produces tracker text from resolved targets.
6. `SpecTreeProjector` projects the detail panel tree from precomputed quest specs.

All runtime resolvers are stateless. They query current state fresh on each call.

### 4.4 What this eliminates

| Previous component | Replacement |
|---|---|
| EntityGraph + GraphIndexes | CompiledGuide (loaded from guide.json) |
| QuestPlanBuilder | Python compiler (build time) |
| QuestPlanProjection + Builder | QuestPhaseTracker + precomputed specs |
| QuestResolutionService (5 caches) | SourceResolver + NavigationTargetResolver (stateless) |
| FrontierResolver | Quest spec frontier entries + phase classification |
| GuideDependencyEngine | Graph-based impact analysis via compiled dependency indexes |
| SourcePositionCache | Live types queried fresh; static positions in compiled data |
| CompiledSourceIndex | Item sources precomputed in guide.json |

### 4.5 Performance budget

| Operation | Budget | Frequency |
|---|---|---|
| Guide compilation (Python) | <30s | Once per game version (developer build step) |
| Guide loading + index building | <200ms | Once at mod startup |
| Quest frontier evaluation | <0.5ms | On events, per affected quest |
| Target materialization | <1ms | On events, per affected quest |
| Per-frame rendering | <1ms total | Every frame |
| Scene change (live state rebuild) | <50ms | During loading screen |
| NPC death event | <3ms | Rare events |

### 4.6 Existing implementation

The `quest-frontier-architecture` worktree (HEAD: `64cf76a6`) has 24 commits
implementing this architecture. Key milestones:

- Compiled guide C# types and loader
- Quest phase tracker and frontier
- Source resolver, navigation target resolver, tracker summary resolver
- Marker, tracker, and detail panel cutover to compiled guide
- Legacy plan builder, projection, and resolution service deleted
- Entity graph replaced by CompiledGuide API

This work compiles and does not crash, but has widespread correctness issues observed
in-game. Markers appear for wrong targets, navigation resolves to stale positions,
tracker displays inaccurate progress, and frontier computation produces incorrect
results in many scenarios. The cutover from legacy code to the compiled guide API is
structurally complete but functionally untrustworthy -- every component that was
touched during the transition should be treated with suspicion until verified against
the acceptance criteria in this spec.

The implementation plan should not limit itself to polishing and testing. Where
architectural improvements would produce cleaner, more correct, or more performant
code, they should be pursued. The goal is the best possible architecture, not
preservation of what was written during the cutover.

### Acceptance criteria

1. `guide.json` contains all structural data needed for runtime resolution
2. No runtime plan building -- structure comes from compiled data, state is queried fresh
3. CompiledGuide public API covers all consumer needs without fallback to raw DTOs
4. Compiled dependency indexes correctly identify affected quests for all event types
5. Guide compilation is idempotent for identical database inputs
6. Mod loads and renders correctly with only `guide.json` -- no entity-graph.json

---

## 5. Quest Plans & Frontier

### 5.1 Plan compilation

The Python guide compiler (`erenshor guide compile`) performs a DFS traversal of the
entity graph starting from each quest node, expanding dependencies into a quest spec:

- **Cycle detection:** Entities on the current DFS path create infeasible stubs.
  Fully processed entities are memoized across quest builds (shared subtrees).
- **Infeasibility propagation:** Specs with all sources infeasible are marked infeasible.
- **Unlock predicates:** Blocked entities (zone lines, characters, doors) get
  precomputed unlock predicates listing which quests/items are required.
- **Output:** `CompiledQuestSpecData` per quest with prereqs, required items, steps,
  givers, completers, chain-to targets, implicit/infeasible flags.

The mod loads these precomputed specs at startup. No plan building occurs at runtime.

### 5.2 Dependency semantic kinds

| Semantic Kind | Graph edges | Frontier role |
|---|---|---|
| `AssignmentSource` | AssignedBy | Acceptance -- quest not yet started |
| `CompletionTarget` | CompletedBy | Turn-in -- quest ready to complete |
| `StepTalk` | StepTalk | Objective -- talk to an NPC |
| `StepKill` | StepKill | Objective -- kill target(s) |
| `StepTravel` | StepTravel | Objective -- travel to zone |
| `StepShout` | StepShout | Objective -- shout keyword |
| `StepRead` | StepRead | Objective -- read an item |
| `RequiredItem` | RequiresItem | Objective -- obtain item (count-checked) |
| `RequiredMaterial` | RequiresMaterial | Objective -- obtain crafting material |
| `PrerequisiteQuest` | RequiresQuest | Container -- prerequisite chain |
| `ItemSource` | DropsItem, SellsItem, GivesItem, YieldsItem | Source -- where to get an item |
| `CraftedFrom` | CraftedFrom | Source -- recipe ingredient |
| `Reward` | RewardsItem | Source -- quest reward |
| `UnlockTarget` | UnlocksZoneLine, UnlocksCharacter, UnlocksDoor | Source -- unlock trigger |

### 5.3 Acceptance and turn-in varieties

**Acceptance** (AssignmentSource) covers multiple interaction types:
- Talking to an NPC quest giver (most common; `NPCDialog.QuestToAssign`)
- Reading an item that starts a quest (`Item.AssignQuestOnRead`)
- Entering a zone (`ZoneAnnounce.AssignQuestOnEnter` -- quest assigned automatically
  on scene load)
- Quest chain auto-assignment (`Quest.AssignNewQuestOnComplete` -- completing a
  quest automatically assigns the next quest in the chain)
- Implicit quests (no assignment step -- `QuestImplicitlyAvailable`)

**Scripted quest triggers** (not yet exported; see Phase 3 export gaps):
- Boss death (`ReliquaryFiend` -- quest completes when specific boss dies)
- NPC shout keyword match (`NPCShoutListener.CheckShout`)
- Duration-based proximity (`SivTorchLight` -- quest completes after sustained
  presence in a trigger zone)
- Timed event sequences (`ShiverEvent` -- multi-phase event that assigns/completes
  quests at phase transitions)
- Multi-objective completion (`AngelScript` -- quest completes when all sub-objectives
  are satisfied)

These scripted triggers represent acceptance and completion mechanisms the export
pipeline does not yet capture. Until their gating conditions are exported (Phase 3),
quests that depend on them will have incomplete dependency chains in the compiled
guide -- the guide knows the quest exists but cannot fully direct the player through
its acceptance or completion steps.

**Turn-in** (CompletionTarget) similarly covers:
- Talking to an NPC (dialogue completion; `NPCDialog.QuestToComplete`)
- Giving items to an NPC (item turn-in via `TradeWindow`)
- Traveling to a zone (`ZoneAnnounce.CompleteQuestOnEnter`)
- Reading an item (`Item.CompleteOnRead`)
- Killing the turn-in holder (`KillTurnInHolder`)
- Destroying the turn-in holder (`DestroyTurnInHolder`)
- Partial item turn-in (`Item.AssignThisQuestOnPartialComplete` -- completes
  current quest and assigns the next stage)

### 5.4 Frontier resolution

`QuestPhaseTracker` determines the effective frontier at runtime by combining the
precomputed quest spec with the current quest phase. The classification logic:

1. **Acceptance edges** -- if quest has acceptance steps and quest is not yet started,
   these are the frontier (stop here)
2. **Objectives** -- kill/talk/collect/travel/read steps that are not yet satisfied
   (always collect all)
3. **Turn-in** -- only if no objectives produced frontier items (quest ready for turn-in)
4. **Fallback** -- quest root node itself

**Implicit quest phasing:** 71 of 174 quests have no quest giver and can never be
formally accepted. `QuestPhaseTracker` handles these at the phase level:
in `Initialize` and `ApplyCompleted`, when an implicit quest's prerequisites are
satisfied, its phase is set directly to `Accepted` (never `ReadyToAccept`).
This is the single seam where implicit/explicit semantics diverge. All downstream
resolvers (`EffectiveFrontier`, `TrackerSummaryBuilder`, `SourceResolver`) then
handle implicit quests uniformly via the `Accepted` path — no special-casing
required. Implicit quests never appear in the game journal; `IsActive()` reads
the journal and always returns false for them. Marker behavior is unaffected:
`MarkerComputer.RebuildQuestMarkers` gates on `IsActive()`, so implicit quests
follow the separate implicit-completion marker path.

### 5.5 Plan group kinds

- `AllOf` -- all children required (prerequisites, materials)
- `AnyOf` -- any child satisfies (alternative quest paths)
- `ItemSources` -- specialized item-source grouping; semantics identical to AnyOf for
  feasibility, but identified by kind so the UI can apply source visibility filtering

### Acceptance criteria

1. Compiled specs are deterministic for identical database inputs
2. Cycles never cause infinite recursion in the compiler -- every cycle detected and pruned
3. Infeasibility propagates correctly at compile time
4. Runtime frontier correctly sequences acceptance -> objectives -> turn-in
5. Implicit quests skip acceptance phase
6. Compiled specs do not contain source-visibility filtering (belongs in runtime resolvers)
7. Shared subtrees: the same item/character entity is deduplicated in compiled data
8. No runtime plan building -- `QuestPhaseTracker` + precomputed specs only

### Known defects

- `quest:a way to erenshor` resolves to 1815 targets (Erenshor-zf8) -- the compiler
  must fully resolve all transitive dependencies to ensure the player is directed
  through every prerequisite step. Bounded expansion is NOT acceptable as it would
  produce incorrect guidance by omission. The fix must be smarter plan building:
  pruning structurally unreachable branches, deduplicating shared subtrees more
  aggressively, or collapsing equivalent source groups. The target count itself may
  be correct for a quest with deep transitive chains -- the real question is whether
  the resolution and UI can present 1815 targets usefully.

---

## 6. Quest Resolution Engine

### 6.1 Resolution pipeline

The runtime resolution stack consists of stateless resolvers operating on compiled data:

1. `QuestPhaseTracker` classifies quest phase from journal state + precomputed spec
2. `SourceResolver` materializes targets from precomputed item sources + live positions
3. Applies corpse loot filter: for DropsItem targets, checks if corpse still contains
   the required item
4. Applies hostile drop filter: suppresses friendly DropsItem sources when hostile exist
5. Resolves zone-reentry chest targets: scans for `RotChest` objects containing items
6. `UnlockPredicateEvaluator` evaluates precomputed unlock predicates for blocked routes
7. `NavigationTargetResolver` produces `ResolvedQuestTarget` for the NAV system
8. `TrackerSummaryResolver` produces tracker text from resolved targets

All resolvers are **stateless**. No internal caches, no invalidation logic. Each call
computes from compiled data + current game state.

**Non-quest entity resolution:** The NAV set can contain any navigable node key, not
just quests (e.g., characters, items, mining nodes). When the resolution service
receives a non-quest entity, it builds a single-node plan, resolves positions directly
from the source index and position resolvers, and returns targets without frontier
computation. This supports "go mine Iron Ore" or "find Islander Bandit" independent
of any specific quest.
### 6.2 ResolvedQuestTarget

Each resolved target carries:

| Field | Purpose |
|---|---|
| `TargetNodeKey` | Graph node identity |
| `SourceKey` | Positioned physical source (spawn point key) |
| `TargetInstanceKey` | `SourceKey ?? TargetNodeKey` (canonical identity) |
| `Semantic` | Shared action description (action/goal/target kinds, text fields, marker kind) |
| `IsActionable` | Mutable, updated per-frame for character targets |
| `IsBlockedPath` | True for unlock-chain targets |
| `IsGuaranteedLoot` | True for corpses with confirmed loot or zone-reentry chests |
| `RequiredForQuestKey` | Sub-quest context for tracker ("Needed for: Shield of Dawn") |
| `X, Y, Z` | Mutable world position, updated per-frame for moving NPCs |

### 6.3 Graph-based impact analysis

When an event occurs, affected quests are determined by querying the immutable graph:

| Event | Affected quests | Lookup method |
|---|---|---|
| Quest assigned/completed | That quest + quests chaining from it | ChainsTo, RequiresQuest edges |
| Item count changed | Quests with RequiresItem edges for that item | Graph index lookup |
| NPC spawned/died | Quests with character targets at that spawn's character | Source index lookup |
| Mining/bag/door changed | Quests referencing that entity | Graph index lookup |
| Scene changed | All quests with targets in the new scene | Full re-resolution |

These lookups query immutable data. They cannot produce stale results.

### 6.4 Unlock evaluation

`UnlockEvaluator` evaluates whether a target entity is accessible. Unlock chains apply
to three entity types:

| Target type | Unlock edge | Example |
|---|---|---|
| ZoneLine | UnlocksZoneLine | Quest completion unlocks a zone line |
| Character | UnlocksCharacter | Quest completion makes an NPC appear |
| Door | UnlocksDoor | Item key or quest unlocks a door |

When a target is blocked, the evaluator returns the blocking sources (quests, items).
These appear as Gate-kind requirement groups in the plan tree and as blocked-path targets
in the resolution output.

**Door unlock condition resolution:** Doors gate access to characters and zone lines
via `UnlocksCharacter` and `UnlocksZoneLine` edges where the source is a door node.
Every door in the data has a `key_item_key` referencing the item needed to open it.
The compiler resolves door conditions at compile time: when the unlock condition source
is a door node, it emits `check_type=1` (item possession) with the door's key item
node_id as the source. After compilation, no door nodes appear as unlock condition
sources — they become ordinary item-possession checks. The display label becomes
`Requires: {key item name}` (e.g., "Requires: Dockhouse Key") and evaluation uses
the existing `FindItemIndex` + `GetItemCount > 0` path.

### 6.5 Source visibility policy

When at least one hostile `DropsItem` source exists for an item, friendly `DropsItem`
sources are suppressed. Non-drop sources (SellsItem, GivesItem, etc.) are always shown.

Applied in two paths:
- Resolution service (blueprint path): `ApplyHostileDropFilter`
- UI tree (plan-tree path): `LazyTreeProjector.CollectVisibleRefs`

Policy is stateless; constructed fresh by each consumer.

### 6.6 Position resolution

Each node type has a dedicated position resolver:

| Node type | Position source |
|---|---|
| Character | Live NPC transform -> corpse transform -> static spawn coordinates |
| SpawnPoint | Graph node coordinates |
| MiningNode | Live mining node position |
| ItemBag | Live item bag position |
| Water | Live water surface shore points (scanned on scene load) |
| Zone | Zone entry point from graph |
| Other static | Graph node X/Y/Z |

Position resolution for Character, MiningNode, and ItemBag always queries live state
(never stale). Cross-zone targets resolve to the nearest zone entry point.

### Acceptance criteria

1. Resolution produces correct results without any cached intermediate state
2. Corpse loot checks use `LootTable.ActualDrops` from the corpse game object
3. Hostile drop filter suppresses friendly DropsItem sources only when hostile exist
4. Zone-reentry chests are modeled as `LootChest` action/target kinds, not as NPCs
5. `TargetInstanceKey` uses physical source when available -- multi-spawn characters
   do not collapse
6. Blocked-path targets are visible but ranked below direct targets
7. Unlock chains expand correctly for zone lines, characters, AND doors
8. Graph-based impact analysis correctly identifies affected quests for all event types

### Known defects

- Nav shows nothing for targets behind locked zone lines (Erenshor-1cg) — correct
	behavior specified in §7.4, implementation pending
- Guide shows wrong respawn hint for disabled NPCs (Erenshor-qhi) — correct behavior
	specified in §8.3, implementation pending

---

## 7. Navigation System

### 7.1 Components

- **NavigationSet** -- the set of node keys the player has chosen to navigate. Any
  navigable node can be in the set (quests, characters, items, mining nodes, etc.).
  Multiple simultaneous targets supported. Persisted per character.
  Click = override (clear + add single). Shift+click = toggle (add/remove).
- **NavigationTargetSelector** -- for each navigated entity, selects the best physical
  target using an 8-tier priority system.
- **NavigationEngine** -- tracks the globally selected target (best across all navigated
  entities), computes effective position, handles cross-zone routing.
- **ArrowRenderer** -- directional arrow toward target with action text.
- **GroundPathRenderer** -- NavMesh path line on ground.

### 7.2 Target selection priority (8 tiers)

| Tier | Direct/Blocked | Same Zone | Actionable |
|---|---|---|---|
| 0 | Direct | Same zone | Actionable |
| 1 | Direct | Same zone | Non-actionable |
| 2 | Direct | Cross zone | Actionable |
| 3 | Direct | Cross zone | Non-actionable |
| 4 | Blocked | Same zone | Actionable |
| 5 | Blocked | Same zone | Non-actionable |
| 6 | Blocked | Cross zone | Actionable |
| 7 | Blocked | Cross zone | Non-actionable |

Within a tier: guaranteed loot (corpses with confirmed items, zone-reentry chests) ranks
above alive NPCs. Within same loot priority: nearest by Euclidean distance.

### 7.3 Per-frame vs. event-driven work

**Per-frame (hot path):**
- Read live NPC transforms for current-scene character targets
- Compute distance-squared to player for same-zone targets
- Select best target per navigated entity, then best across all
- Update arrow direction and ground path endpoint

**Event-driven:**
- On resolution change: re-materialize targets from frontier, re-partition, re-select
- On scene change: all targets re-evaluate zone membership
- On nav set change: add/remove entity from selector

### 7.4 Cross-zone routing

When the best target is in another zone, `NavigationEngine` resolves the effective
position as the nearest zone line on the route. `ZoneRouter` computes hop counts via BFS
on the zone connectivity graph at scene load time.

**Locked zone line handling:** `ZoneRouter.FindRoute` tries accessible-only BFS first,
then falls back to a BFS that includes locked zone lines. When the fallback finds a
route, `Route.IsLocked` is true. `NavigationEngine.SetTarget` detects this and annotates
the explanation: it calls `FindFirstLockedHop` to identify the blocking zone line, then
`UnlockEvaluator.GetRequirementReason` to get the human-readable reason (e.g.,
"Requires: Meet the Fisherman, Angler's Ring"). The reason replaces the explanation's
tertiary text. The arrow points to the locked zone line's position; the player sees
what quests to complete before the route opens.

### Acceptance criteria

1. 8-tier priority is strict -- tier-0 always beats tier-1 regardless of distance
2. Guaranteed loot preferred over alive NPC within same tier
3. Per-frame work limited to position reads and distance math
4. Cross-zone targets route through zone lines
5. Target identity uses `TargetInstanceKey` -- multi-spawn characters pin to selected source
6. When tracked NPC dies, NAV updates to next best target
7. Multiple simultaneous NAV targets supported via shift+click
8. NAV set persisted per character across sessions
9. Locked zone line routes show arrow to zone line with unlock reason in tertiary text

### Known defects

- Nav shows nothing for targets behind locked zone lines (Erenshor-1cg) — correct
	behavior specified in §7.4, implementation pending

---

## 8. World Markers

### 8.1 Marker types

| Type | Glyph | Color | Meaning |
|---|---|---|---|
| QuestGiver | Star `\uf005` | Gold | NPC offers an available quest |
| QuestGiverRepeat | Star `\uf005` | Blue | NPC offers a repeatable quest |
| QuestGiverBlocked | Star `\uf005` | Grey | NPC offers a quest the player can't start yet |
| Objective | CircleDot `\uf192` | Orange | Kill/talk/interact target for active quest |
| TurnInPending | CircleQuestion `\uf059` | Grey | Turn-in NPC, quest not yet completable |
| TurnInReady | CircleQuestion `\uf059` | Gold | Turn-in NPC, quest ready to complete |
| TurnInRepeatReady | CircleQuestion `\uf059` | Blue | Repeatable quest ready to turn in |
| DeadSpawn | Clock `\uf017` | MutedRed | Respawn timer for dead NPC |
| NightSpawn | Moon `\uf186` | PaleBlue | Night-only spawn, currently unavailable |
| QuestLocked | CircleQuestion `\uf059` | Amber | Quest-gated spawn, not yet accessible |
| ZoneReentry | Clock `\uf017` | Grey | Zone-reentry loot chest |

All icons use Font Awesome 7 Free-Regular weight. Only the five glyphs listed above
(CircleQuestion, Star, CircleDot, Clock, Moon) are validated at init time. Adding new
icons requires verifying availability in the Free-Regular weight.

### 8.2 Contribution model

Multiple quests can emit markers for the same physical source (spawn point). The marker
computer tracks contributions per source key. When multiple quests want different marker
types at the same position, the highest-priority type wins. Priority order (highest
first): TurnInReady > TurnInRepeatReady > Objective > QuestGiver > QuestGiverRepeat >
QuestGiverBlocked > TurnInPending.

### 8.3 Character marker policy

- **Kill targets:** Active quest marker exists only while source is actionable (alive NPC
  or lootable corpse). When dead and non-actionable, active marker disappears and only
  the static respawn-timer marker remains.
- **Non-kill character targets** (talk, give): Follow the same dual-marker pattern as
  kill targets. When the NPC is dead and non-actionable, the active quest marker
  disappears and only the static respawn-timer marker remains. When the NPC is alive,
  the active quest marker is shown. The only difference from kill targets is that
  corpse loot checks do not apply (there is no lootable corpse for talk/give targets).
- **Quest-locked NPCs** (`SpawnUnlockBlocked`): The character marker path shows a
  `QuestLocked` marker with the unlock reason text (e.g., "Requires: Meet the Fisherman").
  The respawn timer path suppresses (returns null) — no timer is meaningful for a
  quest-gated spawn.
- **Disabled NPCs** (`SpawnDisabled`): Both marker paths suppress. No useful info to
  show. The character marker returns null at the `SpawnDisabled` check; the respawn
  timer also returns null.
- **Dual markers:** A single physical source can legitimately have two entries: the live
  quest marker (anchored to NPC/corpse) and the static respawn-timer marker (at spawn
  coordinates). These are different by design.
- **Respawn timer eligibility:** Respawn timers are only created for `SpawnDead` (with a
  real timer) and `SpawnNightLocked` (time-based gate). All other non-alive states
  (`SpawnDisabled`, `SpawnUnlockBlocked`) suppress the timer marker.
- **Suppression:** Blocked markers (QuestGiverBlocked, QuestLocked) suppressed at
  positions where non-blocked markers exist.

### 8.4 Per-frame rendering

- Position tracking: quest-kind markers follow live NPC transform; spawn-timer markers
  use static coordinates
- State transitions: alive->dead (switch to respawn timer text), dead->alive (restore
  quest marker), mined->available
- Distance-based alpha fading
- Height offset from CapsuleCollider
- When game's built-in markers are replaced (ShowWorldMarkers=true), game markers
  suppressed via `QuestMarkerPatch`

### 8.5 Marker text projection

All three player-facing surfaces (markers, tracker, arrow) derive text from a shared
`ResolvedActionSemantic` model. Each surface projects the subset appropriate to its role.

**Semantic layers** (carried by `ResolvedActionSemantic`):

| Layer | Field(s) | Example |
|---|---|---|
| Action | `ActionKind` | Kill, Talk, SayKeyword, Read, Travel, Give, Buy, Collect, Mine, Fish, LootChest |
| Payload | `PayloadText` | "Dock Pass", "Iron Ore" (the object of the action) |
| Target identity | `TargetIdentityText` | "Spark Beetle", "Controller Wendyl" |
| Keyword | `KeywordText` | "lighthouse" (phrase to say or shout) |
| Context | `ContextText` | Quest name for giver markers |
| Rationale | `RationaleText` | "Drops Iron Ore", "Rewards A Rolled Note" |
| Zone | `ZoneText` | "Port Azure" |
| Availability | `AvailabilityText` | Overrides primary text when set (dead, locked, etc.) |
| Goal | `GoalKind`, `GoalQuantity`, `GoalNodeKey` | CollectItem, CompleteBlockingQuest |
| Marker hint | `PreferredMarkerKind`, `MarkerPriority` | QuestGiver priority 2, Objective priority 1 |

**Surface projections:**

| Surface | Primary | Secondary | Tertiary | Role |
|---|---|---|---|---|
| **Marker** | Action verb only (no target name — NPC name is on the billboard). `AvailabilityText` overrides if set. Kill shows quantity when > 1. | `PayloadText` if set, else `ContextText` for givers, else `RationaleText` | — | Local action affordance: what can I do *here*? |
| **Tracker** | Action + target identity + progress. CollectItem shows `({have}/{need})`. CompleteBlockingQuest shows `Complete {name}`. | `RationaleText` (when applicable), else `Needed for {quest}` (sub-quest context), else `Needed for {frontier node}` | — | Quest-level planning summary: what is next for this quest? |
| **Arrow** | Action + target identity. Give/Buy lead with payload. | Target identity (if not in primary) or zone. | Rationale (if different from secondary). | Immediate steering: what should I do *right now*? |

**Runtime state overrides** (applied per-frame by `MarkerSystem` and `MarkerComputer`):

| State | Marker text | Icon |
|---|---|---|
| Alive | Original instruction text | Original quest kind |
| Corpse (lootable) | Original instruction text (kept via `KeepWhileCorpsePresent`) | Original quest kind |
| Dead (timer) | `{name}\n~M:SS` | DeadSpawn (clock) |
| Dead (respawning) | `{name}\nRespawning...` | DeadSpawn (clock) |
| Night-locked | `{name}\nNight only (23:00-04:00)\nNow: {hour}:{min}` | NightSpawn (moon) |
| Quest-locked | `{name}\n{unlock reason}` | QuestLocked (amber question) |
| Zone reentry | `{name}\nRe-enter zone` | ZoneReentry (grey clock) |
| Disabled | No marker | — |

**Arrow runtime overrides** (applied by `NavigationEngine`):

| Override | Trigger | Effect |
|---|---|---|
| Corpse loot | Kill target is dead with corpse present | Primary becomes `Loot {payload}` |
| Source gate | Target's source has unsatisfied unlock | Tertiary becomes unlock reason |
| Zone lock | Route goes through locked zone line | Tertiary becomes zone line unlock reason |

### Acceptance criteria

1. Each spawn point shows at most one quest-semantic marker (highest priority) plus
   optionally one respawn-timer marker
2. All character targets (kill AND non-kill): quest marker disappears when NPC dead
   and non-actionable; respawn timer appears instead. Non-kill targets skip corpse
   loot checks but otherwise follow the same dead/alive marker transitions.
3. Corpse markers persist ONLY for actionable loot targets (corpse contains required item)
4. Blocked markers suppressed where actionable markers exist
5. Markers track live NPC position per-frame without calling into resolution pipeline
6. Respawn timer text updates per-frame from SpawnPoint timer fields
7. Quest-locked NPCs (`SpawnUnlockBlocked`) show `QuestLocked` marker with unlock reason;
   respawn timer suppressed. Disabled NPCs (`SpawnDisabled`) show no marker at all.
8. Marker text derived from `ResolvedActionSemantic`; markers show action verb only
   (no target name), arrow shows action + target identity, tracker shows action +
   progress

### Known defects

- Guide shows wrong respawn hint for disabled NPCs (Erenshor-qhi) — correct behavior
	specified in §8.3, implementation pending

---

## 9. Guide Window

### 9.1 Layout

Split panel opened with L key. Left panel: quest list. Right panel: quest detail tree.

### 9.2 Quest list panel

**Filter modes:**
- **Active** -- quests currently in the journal
- **Available** -- quests the player has not yet accepted or completed (Active + Available + Completed = All)
- **Completed** -- finished quests
- **All** -- every quest in the game

**Sort modes:** By Level (ascending, alphabetical secondary), Alphabetical, By Zone
(zone name, then level).

**Zone filter:** Optional, limits to quests in a specific zone.

**Search:** Filters by quest name, zone, assigned-by NPCs, required items, step target
names.

### 9.2.1 Quest display states

Every quest in the list and detail header shows a badge and color:

| State | Badge | Color | Condition |
|---|---|---|---|
| Completed | `[COMPLETED]` | Green | Quest is done |
| Active | `[ACTIVE]` | Yellow | In the game journal (explicit quests only) |
| Implicitly available | `[AVAILABLE]` | Teal | `IsImplicitlyAvailable` — completion target in current scene |
| Available | `[AVAILABLE]` | Secondary text | Not active, not completed |

`[COMPLETABLE]` and `[NOT STARTED]` do not exist. `IsImplicitlyAvailable` drives
only the teal color hint ("something for this quest is here"), not a completion
guarantee — it checks only whether the turn-in target is in the current scene,
not whether all objectives are achievable.

**Tooltip text:** Completed → "Completed", Active → "Active",
ImplicitlyAvailable → "Completable here", Default → "Available".
### 9.3 Quest detail tree

Shows the selected quest's dependency tree:

- **Header:** Quest name, level, zone, description
- **Objectives section:** Step-by-step tree of what the player needs to do. Each node
  shows type icon, display name, status (satisfied/in-progress/blocked), and details
  (item counts, zone name, NPC name, keyword)
- **Prerequisite expansion:** Prerequisite nodes expand to show the prerequisite quest's
  full requirement tree. This lets players traverse the full dependency chain.
- **Source visibility:** When hostile drop sources exist for an item, friendly drop
  sources hidden; non-drop sources always shown
- **Unlock requirements:** Shown as sub-trees under blocked nodes
- **Rewards section:** XP, gold, item rewards, faction changes, quest chains, unlocks

**Label format rules:**

Action labels use verb phrase form with no colon — they describe what the player does:

| Context | Label format | Examples |
|---|---|---|
| Step labels | `{verb} {name}` | Kill Bandit, Travel to Port Azure, Read Tome, Talk to Garrey, Shout near Stone |
| Completer labels | `{verb} {name}` | Turn in to Garrey, Read Tome, Enter Port Azure, Travel to Blacksalt, Complete Shield of Dawn |
| Giver labels | `Talk to {name}` or `Talk to {name} — say "{keyword}"` | Talk to Bassle Wavebreaker |

Source labels use category form with colon — they name the source type, not the player action:

| Edge type | Label format | Example |
|---|---|---|
| DropsItem | `Drops from: {name}` | Drops from: Islander Bandit |
| SellsItem | `Vendor: {name}` | Vendor: Garrey Ambrose |
| GivesItem | `Talk to {name}` or `Talk to {name} — say "{keyword}"` | Talk to Garrey Ambrose — say "lighthouse" |
| Contains | `Collect from: {name}` | Collect from: Iron Deposit |
| YieldsItem (mine) | `Mine at: {name}` | Mine at: Iron Vein |
| YieldsItem (water) | `Fish at: {name}` | Fish at: Stowaway Shore |
| Produces | `Crafted via: {name}` | Crafted via: Iron Ingot Recipe |

GivesItem uses instruction form (not category form) because the player must perform
a specific action. When a keyword is required, it is shown as
`Talk to {name} — say "{keyword}"`.

### 9.4 Lazy tree projection

`LazyTreeProjector` materializes the plan tree one level at a time (on expand). It uses
the precomputed structural plan forest with fresh state lookups:

- Structural groups with no label are flattened (children promoted to parent level)
- `ItemSources` groups apply source visibility filtering
- Cycle stubs are not rendered to the player
- Path-local cycle pruning via ancestry set

### 9.5 Navigation integration

- Each actionable node has a NAV button
- Click = override navigation to that entity
- Shift+click = toggle that entity in/out of the NAV set
- Currently navigated target is highlighted
- Navigation history (back/forward) for quest selection

### Acceptance criteria

1. Quest list filtering correct for all mode combinations
2. Available = not active AND not completed (not just "prerequisites met")
3. Detail tree accurately reflects dependency structure with current state
4. Source visibility policy correct
5. Item counts show current/required (e.g., "Iron Ore (2/5)")
6. Unlock requirements appear as sub-trees under blocked nodes
7. NAV buttons correctly toggle navigation
8. Search covers quest name, zone, NPC names, item names
9. Window state persists across sessions
10. Badges show `[COMPLETED]`/`[ACTIVE]`/`[AVAILABLE]` with correct colors; no
    `[COMPLETABLE]` or `[NOT STARTED]` badges exist
11. Action labels use verb phrase form (no colon); source labels use `Category: {name}` form
12. GivesItem sources with keywords show `Talk to {name} — say "{keyword}"`
13. Prerequisite nodes expand to show the prerequisite quest's full requirement tree

---

## 10. Quest Tracker Overlay

### 10.1 Layout

Compact always-visible panel (default 340x260px). Compact mode hides title bar, uses
translucent background with configurable opacity.

### 10.2 Tracked quests

- Auto-tracked on quest accept (configurable via TrackerAutoTrack)
- Manually tracked/untracked via pin button in guide or click in tracker
- Auto-untracked on completion (configurable via TrackerUntrackOnComplete)
- Per-character persistence (keyed by save slot index)

### 10.3 Per-quest display

- Quest name
- Current objective summary from frontier ("Kill Islander Bandit", "Collect Iron Ore (2/5)")
- Distance/zone indicator for closest target
- Sub-quest context ("Needed for: Shield of Dawn") when target is for a prerequisite
- NAV integration: click = override, shift+click = toggle

### 10.4 Sort modes

- Proximity -- same-zone first by distance, cross-zone by hop count
- Level -- quest level ascending
- Alphabetical -- quest name

### 10.5 Animation

- Fade-in on track (0.3s)
- Fade-out on untrack (0.3s)
- Completion flash (1.5s flash + 2.0s linger before removal)

### Acceptance criteria

1. Tracked quests persist per character across sessions
2. Auto-track/untrack respect config settings
3. Objective summary reflects current frontier state
4. Distance updates reflect current player position
5. Sub-quest context shows immediate prerequisite quest name
6. Click/shift+click NAV interactions work
7. Tracker suppresses rendering behind overlapping game windows
8. Compact mode renders with configurable background opacity

---

## 11. Configuration & Input

### 11.1 User-facing config entries

| Section | Setting | Default | Description |
|---|---|---|---|
| General | ToggleKey | L | Open/close guide window |
| General | ReplaceQuestLog | false | J opens Adventure Guide instead |
| General | UiScale | -1 (auto) | UI scale; -1 auto-detects from resolution |
| General | HistoryMaxSize | 100 | Max pages in navigation history |
| General | ResetWindowLayout | false | Toggle to reset window positions |
| Navigation | ShowArrow | true | GPS arrow toward target |
| Navigation | ShowGroundPath | false | NavMesh path line |
| Navigation | GroundPathToggleKey | P | Toggle ground path |
| World Markers | Enabled | true | Floating quest markers (replaces game markers) |
| World Markers | Scale | 1.0 | Overall marker scale |
| World Markers | IconSize | 7 | Icon glyph font size |
| World Markers | SubTextSize | 3.5 | Sub-text font size |
| World Markers | SubTextYOffset | -1 | Sub-text Y offset |
| World Markers | IconYOffset | 1 | Icon Y offset |
| Tracker | Enabled | true | Quest tracker overlay |
| Tracker | ToggleKey | K | Toggle tracker |
| Tracker | AutoTrack | true | Auto-track new quests |
| Tracker | SortMode | Proximity | Proximity/Level/Alphabetical |
| Tracker | BackgroundOpacity | 0.40 | Tracker background transparency |
| Tracker | UntrackOnComplete | true | Auto-untrack completed quests |

### 11.2 Hidden config entries

- FilterMode, SortMode, ZoneFilter -- quest list panel state
- Per-character tracked quests (by save slot)
- Per-character navigation set (by save slot)

### 11.3 Input isolation

- `PointerOverUIPatch` patches `EventSystem.IsPointerOverGameObject()` to return true
  when cursor over any ImGui window
- Drag state tracking: latch on mouse-down inside window, release on mouse-up
- Skip hit-testing when `Cursor.lockState` is locked (camera drag)
- `GameData.PlayerTyping = true` when ImGui wants text input (prevents movement)
- F7 game UI hide toggle respected

### Acceptance criteria

1. All config entries work via F1 ConfigurationManager and config file
2. Per-character state persists correctly across save slots
3. Input isolation prevents game interaction when using mod UI
4. UI scale auto-detection correct for 1080p, 1440p, 4K
5. ResetWindowLayout resets all window positions and sizes

---

## 12. Diagnostics & Debug Tooling

### 12.1 Layer 1: Resolution trace (developer, via HotRepl)

Structured trace capturing every decision in the resolution pipeline for a given quest.
The resolution pipeline accepts an optional `IResolutionTracer` that receives callbacks
at each decision point. Normal operation passes null (zero overhead).

Example output:
```
TraceQuest("a way to erenshor") ->
  Plan: 847 nodes, 12 groups, 3 cycle stubs
  Frontier: 4 refs [StepKill:character:bandit, RequiredItem:item:iron-ore, ...]
  Target materialization:
    character:bandit -> 3 sources via DropsItem
      spawn:stowaway:342:52:490 -> Alive, actionable, distance=45.2
      spawn:stowaway:100:10:200 -> Dead (corpse), has item: YES -> guaranteed loot
      spawn:azure:50:5:100 -> cross-zone, 2 hops
    item:iron-ore -> 5 sources via DropsItem, 2 via SellsItem
      hostile filter: 5 hostile drops, suppressing 0 friendly
  Best target: spawn:stowaway:100:10:200 (tier 0, guaranteed loot, distance=12.1)
```

### 12.2 Layer 2: Diagnostic overlay (in-game, for testers and users)

Toggleable overlay (hidden by default in config):

- **Status bar:** "AG: 5 active, 12 markers, 3 NAV targets, last event 2.1s ago, 0.3ms"
- **Marker tooltip:** Hold modifier key + hover on marker -> shows contributing quests,
  priority resolution, character state, source key
- **Quest debug section:** Collapsible section in detail panel showing frontier refs,
  target count, plan node count, resolution time

### 12.3 Layer 3: Compile-time safe debug API

Replace reflection-based access to internals with explicit debug interfaces. Each
component exposing debug state provides a typed property or method. No more
`GetField("_planCache", bf)?.GetValue(Resolution)`.

### Acceptance criteria

1. Resolution trace produces complete explanation for any quest resolution
2. Trace has zero overhead when not active (null tracer)
3. Diagnostic overlay toggleable and hidden by default
4. Marker tooltip shows source key, contributing quests, character state
5. Debug API has compile-time safety, no reflection
6. ~~State snapshot export continues working for test fixtures~~ -- REMOVED.
   `ExportStateSnapshot()` in DebugAPI is implemented but never called by any
   automated system. Tests build `StateSnapshot` objects programmatically via
   `SnapshotHarness`, not by loading exported JSON. The export method may be kept
   as a manual debugging convenience but is not a required deliverable. The
   `StateSnapshot` data model and `SnapshotHarness` test infrastructure remain
   (they are actively used by 13+ test files).

---

## 13. Open Issues & Roadmap

### Phase 1: Architecture foundation

- Implement precomputed structural plan forest (build all plans once at startup with
  shared subtrees)
- Implement runtime state overlay (frontier resolver queries state fresh)
- Implement graph-based impact analysis (replace dependency engine with graph lookups)
- Implement stateless resolution service (no internal caches)
- Validate performance against budgets (Section 4.5)

### Phase 2: Correctness fixes

- Fix NAV for targets behind locked zone lines (Erenshor-1cg) — behavior specified in
  §7.4, implementation pending
- Fix respawn hint for disabled NPCs (Erenshor-qhi) — behavior specified in §8.3,
  implementation pending
- Fix "a way to erenshor" 1815-target explosion (Erenshor-zf8) — smarter plan building
  (prune unreachable branches, deduplicate shared subtrees, collapse equivalent sources);
  bounded expansion is NOT acceptable (correctness by omission is not correctness)
- Validate all character lifecycle states produce correct markers/NAV/tracker

### Phase 3: Export pipeline gaps

- Export PietyTrigger inverse quest gating (Erenshor-0ab)
- ~~Export Door item/key gating (Erenshor-hv2)~~ -- resolved at compile time: door
  unlock conditions map to key-item possession checks (§6.4)
- Export AngelScript quest+puzzle gating (Erenshor-ar6)
- Export ShiverEvent quest gating (Erenshor-c5r)
- Export JawsStatueStartup+SivTorchLight gating (Erenshor-q80)
- Export BellsieWineTrigger and MemorySphere item gating (Erenshor-mib)
- Export ShiverEvent NPC gating (Erenshor-dno)

### Phase 4: Feature completion

- Full guide/NAV support for scripted/unknown quests (Erenshor-e6g)
- Reliable quest chain detection for detail panel (Erenshor-69b)
- Bank item awareness in quest detail panel (Erenshor-amm)
- Zone-based prerequisite inference (Erenshor-nzd)
- Progress panel: zone completion, repeatable quests (Erenshor-8ju)
- Quest tracker overlay improvements (Erenshor-kcd)
- Minimap marker integration (Erenshor-4gy)

### Housekeeping

- Audit bd issues for staleness; close resolved, update stale descriptions
- Audit capture pipeline for silent fallbacks (Erenshor-cur)
