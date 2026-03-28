# Plan: Entity Graph for the Adventure Guide

**Clean cut.** This is a full rewrite, not a migration. No legacy code
paths, backward-compatible data formats, or fallback behaviors are
preserved. Old per-character config values are not migrated. If old code
is replaced, it is deleted, not wrapped.

## Problem

The Adventure Guide represents game knowledge through a quest-centric model
where items, characters, and zones exist only as properties of quests. This
creates structural problems:

1. **Dependencies are scattered.** Prerequisites, steps, required items,
   chain links, and unlock effects are five parallel mechanisms for the same
   concept: "to do X, you first need Y." Each has its own data shape,
   rendering logic, navigation code, and marker emission pattern. The result
   is fragmented: the Angler's Ring quest chain and Meet the Fisherman
   appear as two weakly-linked quests instead of a coherent dependency
   chain.

2. **Entity obtainability is shallow.** The Angler's Ring step says "Collect
   Angler's Ring" and shows it's crafted, but the ingredients (Luminstone,
   Vithean Ore, Sea Glass, Whispers of the Sea) are bare names with no
   source information. The item source tree is 1-level deep — ingredients
   don't resolve to their mining/fishing/vendor sources.

3. **Entities are not first-class.** Liani Bosh gives the mold via dialog
   AND receives the finished ring, but her marker only shows the turn-in.
   There is no "Liani Bosh page" that shows all her interactions. Items,
   characters, zones, and other entities can't be navigated to directly —
   only quest steps can be navigation targets.

4. **Custom scripted relationships are invisible.** Evadne the Corrupted is
   invulnerable until the player uses Tempestalia, Ring of Storms on a
   nearby brazier. The ring comes from completing Orion Mycon's quest chain.
   The quest chain requires Chunk of Citrine Sandsilver, which Evadne
   herself drops — but only once she's killable. The guide has no way to
   represent this circular dependency or the item-on-object interaction that
   breaks it.

These are symptoms of a structural issue: the guide treats quests as
islands with weak cross-references, rather than modelling the full
dependency graph where every entity is a node and every relationship is
an edge.

## Requirements

High-level features the system must deliver, from the player's perspective.

### R1. Dependency tree walkthrough

Every quest displays a single, recursive dependency tree that shows
everything the player needs to do, in order, with all sub-dependencies
inlined. No separate "Prerequisites" section. No 1-level-deep item
source lists. The tree expands transitively: sub-quests, crafting recipes,
ingredient sources, character unlock requirements, dialog-give interactions
— everything that has further outgoing dependencies is inlined.

Cycles in the dependency graph are pruned: only actionable paths are shown.
If all paths for a node are cycle-blocked, a note explains the situation.

### R2. World markers for all relevant entities

Every entity in the world that is relevant to any quest the player can work
on gets a floating marker — regardless of whether the player has selected
that quest for navigation. Markers are a world-state visualization, always
on, showing everything the player can interact with:

- **Quest givers**: NPCs who can give a quest the player is eligible to
  accept (all prerequisites met, quest not yet started). Always visible.
- **Turn-in NPCs**: NPCs who accept a turn-in for any active quest. Two
  visual states: items pending (dimmed) vs items ready (active).
- **Objectives**: every entity in the frontier of any active quest — NPCs
  to talk to/kill, mining nodes to mine, items to pick up, etc. All shown
  simultaneously for all active quests.
- **State overlays**: dead/respawning NPCs with timers, night-only spawns
  with time indicator, quest-locked spawns with unlock text.

Marker priority handles overlapping cases (same NPC is both a quest giver
and a turn-in target — show the highest-priority marker).

### R3. Navigation to any entity

Every entity in the graph that has a world position is a valid navigation
target. Not just quest steps — items, characters, zones, mining nodes,
forges, doors, zone lines, specific item sources, etc. Player agency is
paramount: if a player sees a node in the dependency tree and wants to go
there, they can navigate to it directly.

"Navigate to quest" resolves to the closest actionable frontier node of
that quest's dependency tree. "Navigate to item" resolves to the closest
obtainable source. "Navigate to character" resolves to their spawn
location. "Navigate to a specific mining node" goes directly there.

The player can also select a specific item source for navigation rather
than having the system always pick the closest frontier node. This matters
when a player prefers a particular source (e.g., mining in a safer zone
rather than the closest zone).

### R4. Multi-target navigation

The player can select one or more nodes for navigation simultaneously.
Navigation guides the player to the closest target across all selected
nodes. This enables efficient parallel quest completion and fine-grained
source selection.

- **Click** a NAV button: override mode — replaces the current navigation
  set with just this node (quest, item source, character, etc.).
- **Shift+click**: add/remove mode — toggles this node
  in the navigation set without affecting others.
- **NAV arrow**: points to the closest navigable position across all
  nodes in the navigation set.
- **Ground path**: connects the player to the closest target.
- **No selection**: no arrow or path, but all world markers still visible.

When a quest is in the navigation set, it expands to its frontier (all
simultaneously actionable leaf nodes). When a specific node (character,
mining node, item source) is in the set, it contributes its own position
directly. The combined target set is the union of all expanded positions.

### R5. Entity pages

Every entity type gets its own page showing all relationships:
- **Item page**: obtained from (crafting, drops, vendors, mining, fishing,
  dialog, pickup) + used in (quests that need it, recipes that use it)
- **Character page**: quests given/completed, items sold/dropped/given,
  spawn locations, faction, unlock requirements
- **Zone page**: NPCs, zone lines, mining nodes, fishing spots, forges,
  doors, quest triggers
- Every reference on every page is clickable, linking to that entity's page

### R6. Live game state integration

All displays reflect the live game state in real-time:
- Quest completion status (checkboxes in the tree)
- NPC alive/dead/respawning state with timers
- Item inventory counts
- Mining node available/mined state with regeneration timers
- Zone line accessibility (locked/unlocked with reason)
- Spawn point quest-gating status

### R7. Full obtainability chains

Item sources are resolved recursively. "You need Angler's Ring" expands to
"crafted from Mold + 4 ingredients." The mold expands to "talk to Liani
Bosh, say 'ring'." Each ingredient expands to "mine in Blacksalt Strand
(4 nodes), Port Azure (2 nodes)." No bare names without sources.

### R8. Custom scripted relationships

Non-standard game mechanics (Evadne's invulnerability via brazier,
ward-based boss fights, key-gated doors, inverse quest gates) are
represented in the graph and rendered identically to standard
relationships. Manual edge definitions support arbitrary relationship
types without code changes.

## Vision

The Adventure Guide becomes an in-game wiki backed by an entity graph.
Every game entity is a node. Every relationship is a typed, directed edge.
Any view — quest walkthrough, item page, character page, zone overview — is
a subgraph traversal rendered for that entity type. Navigation, markers,
and live game state all derive from graph queries, not ad hoc per-type code.

## Current Architecture

### Data flow

```
Clean SQLite DB (60+ tables, ~30 entity types)
  → repository.py (queries ~25 tables, builds QuestDataContext with ~30 lookup maps)
  → assembler.py (builds QuestGuide per quest, with steps/items/prereqs/rewards)
  → serializer.py (asdict + clean → JSON)
  → quest-guide.json (embedded in mod DLL as resource)
  → GuideData.cs (loads JSON, indexes by DBName/StableKey)
  → QuestDetailPanel.cs / NavigationController.cs / WorldMarkerSystem.cs
```

### What the guide currently captures

| Concept | Current representation | Navigable? |
|---|---|---|
| Quest dependency | `prerequisites[]` separate section | Click to jump to quest |
| Quest step | `steps[]` ordered list | NAV to character/zone/item |
| Item obtainability | `required_items[].sources[]` tree (1-level deep) | NAV to source location |
| Crafting ingredients | `ItemSource(type=ingredient, name, quantity)` | No — bare text only |
| Dialog-give items | `ItemSource(type=dialog_give, source_key)` | Yes — to NPC location |
| Quest chain | `chain[]` with prev/next/also_completes links | Click to jump |
| Quest unlock effects | `rewards.unlocked_zone_lines/characters` | No — display only |
| Zone line gating | `_zone_lines[].required_quest_groups` | Lock reason in nav |
| Character spawn gating | `_character_quest_unlocks` | Lock text on marker |

### Ad hoc patterns that need unification

1. Steps, prerequisites, chain links, unlock effects, and item sources
   are five separate mechanisms for the same concept: "to do X you need Y"
2. Navigation target resolution is a 3-way switch (character/zone/item)
   with completely separate code paths per type
3. Marker emission has separate Collect* methods per quest role
   (CollectQuestGiverMarkers, CollectTurnInMarkers, CollectObjectiveMarkers)
4. Source type formatting is a 10-way switch with bespoke strings
5. NAV button navigability check has 3 separate if/else branches
6. Sub-quest resolution is duplicated between StepProgress and
   QuestDetailPanel
7. Key prefixes ('mining-nodes:', 'fishing:') are ad hoc runtime hacks
8. Step rendering is recursive but through two separate code paths
   (DrawSubQuestSteps for complete_quest, DrawQuestRewardTree for
   quest_reward sources)

## Design

### Core insight: it's a graph

The game's dependency structure is a directed graph with cycles:
- Multiple quests can unlock the same zone line
- The same item can be required by multiple quests
- A character can be both a quest giver and a quest completer
- Crafting ingredients are items with their own full obtainability graphs
- Circular dependencies exist (Evadne drops an item needed for the quest
  that removes her invulnerability)

The guide needs a graph data model where:
- Every game entity is a **node** with a stable key
- Every dependency/relationship is a typed **edge**
- Any view (quest page, item page, character page) is a subgraph query
- The quest walkthrough is a depth-first traversal of the dependency
  subgraph, with cycles pruned to show only actionable paths

### Data model: Entity Graph

```
Node {
    key:          str         # stable_key with type prefix
                              #   quest:anglerring
                              #   item:ring - 6 - angler's ring
                              #   character:liani bosh:azure:135.62:31.82:303.95
                              #   zone:saltedstrand
                              #   zoneline:saltedstrand:stowaway:61.56:12.87:192.07
    type:         NodeType    # see exhaustive list below
    display_name: str
    properties:   dict        # type-specific, schema-validated per NodeType
}

Edge {
    source:       str         # from-node key
    target:       str         # to-node key
    type:         EdgeType    # see catalog below
    group:        str | null  # AND/OR grouping key (see semantics below)
    ordinal:      int | null  # ordering within a sequence (quest steps)
    negated:      bool        # true = active when target NOT satisfied
    properties:   dict        # type-specific (quantity, keyword, chance, note, etc.)
}
```

### Exhaustive node type list

Every entity that has a world position, gameplay state, or is referenced
by another entity must be a node.

| NodeType | DB source | Has world position? | Has live state? | Navigable? |
|---|---|---|---|---|
| `quest` | quests, quest_variants | No (via NPC/zone) | completed/active/not_started | Yes (→ closest frontier node) |
| `item` | items | No (via sources) | inventory count | Yes (→ closest obtainable source) |
| `character` | characters, character_spawns | Yes (spawn coords) | alive/dead/disabled/night_locked/quest_gated | Yes (→ live NPC or spawn, prefer alive) |
| `zone` | zones | No (abstract region) | current/other | Yes (→ route via zone graph) |
| `zone_line` | zone_lines | Yes | accessible/locked (with reason) | Yes (→ closest zone line position) |
| `spawn_point` | character_spawns | Yes | active/respawning(timer)/quest_gated/night_locked | Yes |
| `mining_node` | mining_nodes | Yes | available/mined(timer) | Yes (prefer available over mined) |
| `water` | waters | Yes (imprecise) | N/A | Zone-level only (individual spots not reliably navigable) |
| `forge` | forges | Yes | N/A (always available) | Yes |
| `item_bag` | item_bags | Yes | available/picked_up(respawn timer)/gone(unique) | Yes (prefer available over respawning) |
| `recipe` | crafting_recipes (template item) | No | N/A | No (via forge + ingredients) |
| `door` | doors | Yes | locked/unlocked (key item) | Yes |
| `faction` | factions | No | reputation value | No (informational) |
| `spell` | spells | No | known/unknown | No (informational) |
| `skill` | skills | No | known/unknown | No (informational) |
| `teleport` | teleports | Yes | usable (has teleport item) | Yes |
| `world_object` | manual (graph_overrides) | Yes | active/inactive | Yes |
| `achievement_trigger` | achievement_triggers | Yes | triggered/not | Yes |
| `secret_passage` | secret_passages | Yes | N/A | Yes |
| `wishing_well` | wishing_wells | Yes | N/A | Yes |
| `treasure_location` | treasure_locations | Yes | looted/not | Yes |
| `book` | books | No | read/unread | No (informational) |
| `class` | classes | No | N/A | No (informational) |
| `stance` | stances | No | N/A | No (informational) |
| `ascension` | ascensions | No | unlocked/locked | No (informational) |

Nodes without world positions (faction, spell, skill, book, class,
stance, ascension) are still graph nodes for crosslinking. They get
entity pages but are not navigation targets.

### AND/OR/NOT dependency semantics

The `group` field on edges encodes compound conditions:

- **Ungrouped** (`group = null`): unconditional, always applies.
- **Same group**: AND — all edges in the group must be satisfied.
- **Different groups** for the same (source, edge_type pattern): OR —
  any fully-satisfied group unlocks.
- **Negated** (`negated = true`): the edge condition is inverted.
  Handles PietyTrigger-style inverse gates where a spawn is active only
  when a quest is NOT completed.

Example — zone line with two unlock paths:
```
{s: "zoneline:X", t: "quest:A", type: "gated_by_quest", group: "g1"}
{s: "zoneline:X", t: "quest:B", type: "gated_by_quest", group: "g1"}
{s: "zoneline:X", t: "quest:C", type: "gated_by_quest", group: "g2"}
```
Zone line X is accessible when (A AND B) are complete, OR when C is
complete.

Example — inverse gate:
```
{s: "spawnpoint:guardian", t: "quest:piety", type: "gated_by_quest", negated: true}
```
Guardian spawns when piety quest is NOT complete.

### Edge type catalog

Edges are typed and directed. A→B means "A relates to B in this way."

**Quest edges** (outgoing from quest node):
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `requires_quest` | quest | Must complete this quest first | group |
| `requires_item` | item | Must obtain and turn in this item | quantity |
| `step_talk` | character | Talk to NPC (with keyword) | ordinal, keyword |
| `step_kill` | character | Kill this NPC | ordinal |
| `step_travel` | zone | Travel to this zone | ordinal |
| `step_shout` | character | Shout at NPC | ordinal, keyword |
| `step_read` | item | Read this item | ordinal |
| `completed_by` | character | Quest completed via this NPC | keyword |
| `assigned_by` | character | Quest given by this NPC | keyword |
| `rewards_item` | item | Completing quest gives this item | |
| `chains_to` | quest | Completing this quest starts next | |
| `also_completes` | quest | Completing this quest also completes | |
| `unlocks_zone_line` | zone_line | Completing enables this zone line | group |
| `unlocks_character` | character | Completing enables this NPC spawn | group |
| `affects_faction` | faction | Completing modifies reputation | amount |

**Item edges** (outgoing from item node):
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `crafted_from` | recipe | Crafted using this recipe | |
| `teaches_spell` | spell | Using this item teaches spell | |
| `assigns_quest` | quest | Reading this item starts quest | |
| `completes_quest` | quest | Reading this item completes quest | |
| `unlocks_door` | door | Key item opens door | |
| `enables_interaction` | world_object | Item used on world object | note |

**Character edges** (outgoing from character node):
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `drops_item` | item | Drops on death | chance |
| `sells_item` | item | Vendor sells this | |
| `gives_item` | item | Gives via dialog | keyword |
| `spawns_in` | zone | Spawns in this zone | |
| `has_spawn` | spawn_point | Has this specific spawn point | |
| `belongs_to_faction` | faction | Member of this faction | |
| `protects` | character | Invulnerability source | note |

**Recipe edges** (outgoing from recipe node):
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `requires_material` | item | Needs this ingredient | quantity, slot |
| `produces` | item | Creates this item | quantity |

**Zone edges**:
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `connects_to` | zone | Zone line to | |
| `contains` | mining_node/water/forge/item_bag | Has resource node | |

**Resource node edges**:
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `yields_item` | item | Mining/fishing/bag produces | chance |

**Spawn point edges**:
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `spawns_character` | character | NPC spawn | chance, is_rare |
| `gated_by_quest` | quest | Disabled until quest complete | group |
| `stops_after_quest` | quest | Despawns after quest complete | |

**Zone line edges**:
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `connects_zones` | zone | Destination | |
| `gated_by_quest` | quest | Locked until quest complete | group |

**World object edges** (for custom scripting):
| Edge type | Target type | Meaning | Properties |
|---|---|---|---|
| `removes_invulnerability` | character | Makes NPC killable | note |

### Custom scripted relationships

~5% of entity relationships come from custom scripts. These cannot be
auto-detected from DB data alone.

**Mechanism**: `graph_overrides.toml` defines manual nodes and edges
merged into the auto-generated graph. Same schema — no special treatment
in rendering or navigation.

```toml
[[nodes]]
key = "world_object:brazier_evadne"
type = "world_object"
display_name = "Brazier of Binding"
scene = "Bonepits"
x = 100.0
y = 20.0
z = 200.0

[[edges]]
source = "item:tempestalia ring of storms"
target = "world_object:brazier_evadne"
type = "enables_interaction"
note = "Use on the brazier near Evadne to remove her invulnerability"

[[edges]]
source = "world_object:brazier_evadne"
target = "character:evadne the corrupted"
type = "removes_invulnerability"
```

**Known custom patterns requiring manual edges**:

| Pattern | Script | Entities | Edge chain |
|---|---|---|---|
| Protector/NPCInvuln | NPCInvuln.cs | item → brazier → NPC | `enables_interaction` → `removes_invulnerability` |
| Ward invuln | ShiveringPhantomWardListener.cs | ward NPCs → boss NPC | `death_removes_invulnerability` |
| Fight events | PhantomFightEvent.cs, FernallaFightEvent.cs | boss → phase/ward spawns | `spawns_during_fight` |
| Essential guards | ReliquaryFiend.cs | guard spawn → boss invuln | `guards_invulnerability` |
| Doors | Door.cs | key item → door → zone access | `unlocks_door` |
| Inverse gates | PietyTrigger.cs | quest (NOT done) → guardian spawn | `gated_by_quest` (negated) |

### Cycle handling: filter, don't display

The game's dependency graph has real cycles. Example: Evadne drops Citrine
Sandsilver, which is needed for a quest that rewards the ring that removes
Evadne's invulnerability.

**Design principle**: the guide shows players what they CAN do. Cycle-blocked
paths are not actionable — they are noise.

During quest view construction, cycle detection via visited set:
1. Cycle-blocked path is pruned from the primary view.
2. Non-cycle paths for the same node shown normally.
3. If ALL paths for a node are cycle-blocked, a note explains the situation.

```
Obtain: Chunk of Citrine Sandsilver
├── [mined_at] Blacksalt Strand (4 nodes)    ← shown (actionable)
└── (Evadne drop path pruned — circular dependency)
```

Cycle-blocked sources still exist in the raw graph for entity pages (an
item page shows "also drops from Evadne") but don't appear in quest
dependency trees.

### Frontier: simultaneously actionable objectives

The **frontier** of a quest's dependency tree is the set of all leaf nodes
whose incoming dependencies are satisfied but which are not yet completed.
These are all the things the player can act on right now, simultaneously.

- Quest requires items A, B, C: all three are in the frontier if none
  are collected.
- Item A crafted from ingredients X and Y: both in frontier simultaneously.
- Item B drops from enemies in two zones: all source locations valid.

The frontier drives navigation and the arrow. Among the frontier nodes of
all selected-for-navigation quests, the closest by world distance is the
navigation target. This is greedy, not globally optimal, but dramatically
better than one-step-at-a-time.

A selected subtree narrows the frontier to that subtree's leaves. Selecting
the quest root considers all objectives.

### World markers: always-on world state visualization

Markers are NOT tied to navigation selection. They are a persistent world
overlay showing everything the player can interact with across ALL quests.
Any node in the graph gets a marker if its constraints are satisfied.

**Marker visibility rules by quest state:**

| Quest state | What shows markers | Marker types |
|---|---|---|
| **Available** (prerequisites met, not started) | `assigned_by` character | Quest giver marker |
| **Active** (in quest log) | All frontier nodes | Objective markers (type varies by edge/node) |
| **Active** | `completed_by` character | Turn-in marker: pending (items not ready) or ready (items ready) |
| **Active** | Dialog-give NPCs for needed items | Objective marker ("Talk to X: say 'keyword'") |
| **Completed** | Nothing | No markers |

**Key principle**: markers are computed for ALL eligible quests every
rebuild, not just navigated ones. This means quest givers for quests the
player hasn't even looked at yet still show in the world if the player
is eligible. Turn-in NPCs for all active quests show regardless of
navigation selection.

**Navigation markers vs context markers**: the only difference between
a navigated quest and a non-navigated quest is the arrow/path. Markers
appear identically for both. The player sees the full world state at all
times. Navigation selection just adds pathfinding on top.

**Priority dedup**: when the same world entity has markers from multiple
quests, the highest-priority marker wins (turn-in ready > objective >
quest giver > turn-in pending > state overlay). The marker text can
list the quest name to disambiguate.

### Multi-target navigation

The player maintains a **navigation set** — zero or more nodes actively
being navigated. Each entry is a node key. The NAV arrow/path guides to
the closest resolved position across all entries.

**Interaction model**:
- **Click NAV** on any node: override mode. Clears the navigation set
  and adds only this node. Most common action.
- **Shift+click NAV**: toggle mode. Adds or removes
  this node without affecting others. For parallel objective tracking.
- **No entries selected**: no arrow or path. All world markers still
  visible (markers are independent of navigation).

**Target resolution**: each node in the navigation set resolves to a set
of world positions based on its NodeType:
- Quest node → all frontier positions (simultaneously actionable leaves)
- Character node → NPC spawn position(s)
- Item node → closest obtainable source position(s)
- Mining node / forge / item_bag / door → direct coordinates
- Zone → entry zone line position

The combined target set is the union of all resolved positions across the
navigation set. The arrow points to the closest position in this set.

**Player agency**: the player can select a specific item source (e.g., a
particular mining node in a preferred zone) instead of letting the system
pick the closest. When a quest is selected, its frontier drives target
resolution. When a specific node is selected, it contributes directly.
Both can coexist in the same navigation set.

**Edge cases**:
- All targets are in other zones: arrow points to the zone line for the
  closest zone containing a target.
- A quest's frontier is empty (objectives done, not turned in): the
  turn-in NPC is in the frontier.
- The navigation set is empty: no arrow, no path, markers still visible.

### Navigation resolution by node type

| Node type | Resolution strategy |
|---|---|
| character | Live NPC position → spawn position fallback → closest spawn. Prefer alive over dead/respawning. |
| zone_line | Closest accessible zone line position in current zone. |
| zone | Route via zone graph to zone entry point. |
| mining_node | Closest node in zone. Prefer available (un-mined) over mined (respawning). |
| water | Zone-level only. Navigate to the zone containing the fishing spot. Individual water positions not reliably navigable. |
| forge | Closest forge position. |
| item_bag | Closest bag. Prefer available over respawning. Unique bags already picked up excluded. |
| item | Resolve to closest obtainable source node (recursive via graph edges). |
| quest | Resolve to closest frontier node of the quest's dependency tree. |
| spawn_point | Direct coordinates. |
| door | Direct coordinates. |
| world_object | Direct coordinates. |
| teleport | Direct coordinates. |
| achievement_trigger | Direct coordinates. |
| secret_passage | Direct coordinates. |
| wishing_well | Direct coordinates. |
| treasure_location | Direct coordinates. |

### Live game state

Each NodeType has a state resolver. State feeds into frontier computation,
rendering, and markers.

| Node type | States | Runtime source |
|---|---|---|
| quest | not_started / active / completed | GameData.CompletedQuests + QuestLog |
| character | alive / dead / disabled / night_locked / quest_gated | Live SpawnPoint + NPC components |
| item | inventory count | Player inventory check |
| zone_line | accessible / locked (with reason) | Quest completion on gate edges |
| mining_node | available / mined (with timer) | Live MiningNode component |
| spawn_point | active / respawning (with timer) / gated / night_locked | Live SpawnPoint component |
| item_bag | available / picked_up (timer) / gone (unique) | Live ItemBag component |
| door | locked / unlocked | Keyring check |
| teleport | usable / unusable | Inventory check for teleport item. Teleport locations with items in inventory can factor into navigation decisions — if the player owns a teleport item for a zone near the target, the navigator can suggest using it as a shortcut. |

State resolution is a unified system: `GetState(nodeKey) → NodeState`
with per-NodeType resolvers registered at startup. Replaces the scattered
SpawnPointBridge, MiningNodeTracker, StepProgress state checks.

### Rendering: subgraph views

Every entity page is a subgraph traversal from that entity's node,
producing a renderable tree. The renderer is a single recursive function
that takes a ViewNode (node key + edge type + children) and renders based
on (edge_type, node_type) template lookup. No per-type switch statements.
Adding a new edge or node type = adding a template entry.

All relationships with depth are inlined transitively: sub-quests,
crafting recipes, ingredient sources, character unlock requirements,
item obtainability chains. Cycles are the sole termination condition.

Expand/collapse by default: first level expanded, deeper levels collapsed.
Expanding a collapsed node lazily renders its sub-tree. No depth limits —
the player can expand as deep as they want.

#### Quest page rendering

```
The Angler's Ring
├── [obtain] Angler's Ring (×1)
│   └── [crafted_from] Recipe: Mold: Angler's Ring
│       ├── [obtain] Mold: Angler's Ring
│       │   └── [gives_item] Liani Bosh (Port Azure) — say "ring"
│       ├── [obtain] Luminstone (×1)
│       │   ├── [mined_at] Blacksalt Strand (4 nodes)
│       │   └── [mined_at] Port Azure (2 nodes)
│       ├── [obtain] Vithean Ore (×1)
│       │   └── [mined_at] Blacksalt Strand (4 nodes)
│       ├── [obtain] Sea Glass (×1)
│       │   └── [mined_at] Blacksalt Strand (2 nodes)
│       └── [obtain] Whispers of the Sea (×1)
│           └── [fished_at] Blacksalt Strand
└── [turn_in] Liani Bosh (Port Azure)

Meet the Fisherman
├── [requires_quest] The Angler's Ring
│   └── (inline: full Angler's Ring tree above)
├── [requires_character_unlock] Bassle Wavebreaker
│   └── [unlocked_by] Complete: The Angler's Ring
└── [talk] Bassle Wavebreaker (Blacksalt Strand, night) — say "taking"
```

#### Entity pages (after quest pages are working)

- **Item page**: incoming edges ("obtained from") + outgoing edges
  ("used in / required by")
- **Character page**: all edges (quests, items, faction, spawns)
- **Zone page**: all entities within zone

Same renderer. New page = new view builder + page registration.

### Level estimation

Level estimates from the quest's dependency subgraph:

- Zone-context nodes: zone median level
- `step_kill` target characters: max(zone_median, enemy_level). Kill
  steps involving high-level enemies exceed the zone's median.
- Inherited from deepest dependency: a quest requiring a sub-quest
  inherits at least the sub-quest's level estimate.
- Per-node estimates attached to ViewNodes for granular display.

### Serialization

```json
{
  "_version": 6,
  "_nodes": {
    "quest:anglerring": {
      "type": "quest",
      "display_name": "The Angler's Ring",
      "db_name": "ANGLERRING",
      "description": "...",
      "zone_context": "Port Azure",
      "xp_reward": 225
    },
    "item:ring - 6 - angler's ring": {
      "type": "item",
      "display_name": "Angler's Ring"
    },
    "character:liani bosh:azure:135.62:31.82:303.95": {
      "type": "character",
      "display_name": "Liani Bosh",
      "zone": "Port Azure",
      "scene": "Azure",
      "x": 135.62, "y": 31.82, "z": 303.95,
      "level": 11
    }
  },
  "_edges": [
    {"s": "quest:anglerring", "t": "item:ring - 6 - angler's ring",
     "type": "requires_item", "quantity": 1},
    {"s": "quest:anglerring", "t": "character:liani bosh:azure:...",
     "type": "completed_by"},
    {"s": "item:ring - 6 - angler's ring", "t": "recipe:template - anglers ring",
     "type": "crafted_from"},
    {"s": "recipe:template - anglers ring", "t": "item:luminstone",
     "type": "requires_material", "quantity": 1},
    {"s": "character:liani bosh:azure:...", "t": "item:template - anglers ring",
     "type": "gives_item", "keyword": "ring"}
  ]
}
```

Full graph — ALL entities. If JSON size becomes problematic, switch to
MessagePack. Design C# loader to accept either format.

The mod builds in-memory adjacency lists (outgoing + incoming) on load.

### Why not just extend the current model?

The current model is quest-centric: items, characters, and zones exist
only as quest properties. Adding entity pages would duplicate entity data
across every quest. With a graph:
- Each entity exists once as a node
- Cross-references are edges traversed in either direction
- A quest page queries outgoing edges; a character page queries incoming
- Adding a new entity type = adding a NodeType + its edges, no code changes
- Navigation, markers, and state are all uniform — no per-type switches

## Implementation plan

### Phase 1: Graph pipeline (Python)

Replace repository.py → assembler.py → serializer.py with:

1. **Node/Edge schema**: define dataclasses in schema.py. All NodeTypes,
   EdgeTypes, AND/OR/NOT semantics.

2. **Graph builder** (`graph_builder.py`): DB → nodes + edges. One
   function per entity type, one per relationship type. Covers all 25
   NodeTypes and all edge types. Merge manual edges from
   `graph_overrides.toml`.

3. **Serializer**: full graph (nodes + edges) → JSON.

4. **Tests**: graph construction from DB, edge completeness, AND/OR
   group correctness.

Quest view building, level estimation, and merge logic all move to C#
since they depend on live game state. The Python pipeline's sole job is:
DB → entity graph → JSON.

### Phase 2: Graph-aware mod (C#)

Replace quest-centric data model and all rendering/navigation/marker code:

1. **EntityGraph.cs**: load nodes + edges, adjacency lists.
   `GetNode(key)`, `OutEdges(key, type?)`, `InEdges(key, type?)`.

2. **GameState.cs**: unified state per NodeType. Single
   `GetState(nodeKey) → NodeState` interface with per-type resolvers.

3. **QuestViewBuilder.cs**: build quest dependency trees on-demand from
   EntityGraph + GameState. Depth-first traversal with cycle pruning,
   transitive inlining, OR-group alternatives, step ordering. Also
   handles level estimation (zone medians + enemy levels). Views are
   NOT pre-computed — they depend on live game state.

4. **Frontier.cs**: compute frontier (actionable leaves) for a quest's
   dependency tree given game state. Union frontiers across all quests
   in the navigation set. Non-quest nodes in the navigation set
   contribute their resolved positions directly.

5. **MarkerComputation.cs**: for ALL eligible quests (not just navigated),
   compute marker set: quest giver markers (available quests), turn-in
   markers (active quests, two states), objective markers (active quest
   frontier nodes). Markers independent of navigation selection.

6. **ViewRenderer.cs**: single recursive renderer. Template lookup by
   (edge_type, node_type). Expand/collapse, cycle-pruned views, state
   indicators, NAV buttons, clickable names.

7. **GraphNavigator.cs**: node key → world position(s). Quest keys →
   frontier positions. Item keys → obtainable source positions. Direct
   position nodes → coordinates. Union across all navigation set entries.
   Mining nodes → prefer available. Waters → zone-level.

8. **GraphMarkerSystem.cs**: render markers from MarkerComputation output.
   Priority dedup. Per-frame live state tracking. Two-state turn-in
   markers.

9. **Multi-target NAV**: navigation set management. Click = override
   (single node), Shift+click = toggle (add/remove). Any navigable
   node can be in the set — quests, characters, items, sources, etc.
   Arrow/path to closest resolved position across all entries.

10. **Remove old code**: QuestDetailPanel, NavigationController per-type
    switches, WorldMarkerSystem per-role collectors, StepProgress,
    Prerequisites section.

### Phase 3: Entity pages

Item, character, zone pages. New view builder per page type. Shared
renderer. No rendering code changes.

### Phase 4: Crosslinking

Every entity reference → clickable link → entity page. Back-navigation
stack. Full in-game wiki.

## Commit sequence

Phase 1 (Python):
1. Define Node, Edge, NodeType, EdgeType schema
2. Graph builder: all entity types + relationships from DB
3. Manual edge loader: graph_overrides.toml
4. Serializer: graph → JSON
5. Tests for graph construction
6. Wire CLI command, delete old pipeline, verify goldens

Phase 2 (C#):
7. EntityGraph data loader
8. GameState: unified state resolution
9. QuestViewBuilder: on-demand view construction from graph + state
10. Frontier computation + multi-target union
11. Marker computation: always-on, all-quest markers
12. ViewRenderer: recursive template rendering
13. GraphNavigator: node-based navigation, any-node targeting
14. GraphMarkerSystem: render computed markers
15. Multi-target NAV UX (click/shift+click, any node)
16. Wire up, remove old code, verify

Phase 3+4: separate planning when we get there.

## Open questions

1. **OR-group visualization**: visual design for alternative paths
   deferred to implementation. Graph captures them correctly.

2. **Binary serialization**: switch to MessagePack if JSON too large.

3. **graph_overrides.toml scope**: start with Evadne, doors, ward bosses.

4. **Marker performance**: computing markers for ALL quests every rebuild
   may need optimization (spatial indexing, only recompute changed quests).
   Profile first, optimize if needed.

## Resolved decisions

- **Quest views are built on-demand in C#, not pre-computed in Python.**
  Views depend on live game state (quest completion, inventory, spawn state)
  so pre-computed views would be stale. The JSON contains only the raw graph
  (nodes + edges). The mod builds ViewNode trees at runtime from the graph +
  current game state. This is simpler and more correct.

- **No manual quest override system.** The existing `merge.py` curation layer
  has no actual manual files. Dropped from the new pipeline. If manual data is
  needed in the future, it goes into `graph_overrides.toml` as manual edges,
  not as quest-level JSON overrides.

- **Implementation strategy**: build new pipeline files alongside old ones.
  Verify new output against goldens. Then delete old files in the same commit.
  No gradual migration — clean cut.