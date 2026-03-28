# Class Architecture: Entity Graph Adventure Guide

Companion document to the entity graph plan. Defines the component
architecture for both the Python pipeline and C# mod.

**Clean cut.** This is a full rewrite, not a migration. No legacy code
paths, backward-compatible data formats, or fallback behaviors are
preserved. Existing per-character config values (tracked quests,
navigation state) are not migrated — players re-add tracked quests after
update. If old code is replaced, it is deleted, not wrapped.

## Python Pipeline

### Current structure (replaced)

```
src/erenshor/application/guide/
├── schema.py        # QuestGuide, QuestStep, ItemSource, etc.
├── repository.py    # QuestDataContext, 30 SQL fetch functions
├── assembler.py     # Per-quest assembly (steps, prereqs, rewards)
├── levels.py        # Level estimation
├── merge.py         # Manual override merging
├── generator.py     # Orchestrator
└── serializer.py    # asdict + clean
```

### New structure

```
src/erenshor/application/guide/
├── schema.py              # Node, Edge, NodeType, EdgeType
├── graph.py               # EntityGraph class (in-memory graph)
├── graph_builder.py       # DB → EntityGraph
├── graph_overrides.py     # graph_overrides.toml → manual nodes/edges
├── generator.py           # Orchestrator (rewritten)
└── serializer.py          # EntityGraph → JSON (rewritten)
```

### Components

#### `schema.py` — Data model

```python
class NodeType(Enum):
    QUEST = "quest"
    ITEM = "item"
    CHARACTER = "character"
    ZONE = "zone"
    ZONE_LINE = "zone_line"
    SPAWN_POINT = "spawn_point"
    MINING_NODE = "mining_node"
    WATER = "water"
    FORGE = "forge"
    ITEM_BAG = "item_bag"
    RECIPE = "recipe"
    DOOR = "door"
    FACTION = "faction"
    SPELL = "spell"
    SKILL = "skill"
    TELEPORT = "teleport"
    WORLD_OBJECT = "world_object"
    ACHIEVEMENT_TRIGGER = "achievement_trigger"
    SECRET_PASSAGE = "secret_passage"
    WISHING_WELL = "wishing_well"
    TREASURE_LOCATION = "treasure_location"
    BOOK = "book"
    CLASS = "class_"
    STANCE = "stance"
    ASCENSION = "ascension"

class EdgeType(Enum):
    # Quest edges
    REQUIRES_QUEST = "requires_quest"
    REQUIRES_ITEM = "requires_item"
    STEP_TALK = "step_talk"
    STEP_KILL = "step_kill"
    STEP_TRAVEL = "step_travel"
    STEP_SHOUT = "step_shout"
    STEP_READ = "step_read"
    COMPLETED_BY = "completed_by"
    ASSIGNED_BY = "assigned_by"
    REWARDS_ITEM = "rewards_item"
    CHAINS_TO = "chains_to"
    ALSO_COMPLETES = "also_completes"
    UNLOCKS_ZONE_LINE = "unlocks_zone_line"
    UNLOCKS_CHARACTER = "unlocks_character"
    AFFECTS_FACTION = "affects_faction"
    # Item edges
    CRAFTED_FROM = "crafted_from"
    TEACHES_SPELL = "teaches_spell"
    ASSIGNS_QUEST = "assigns_quest"
    COMPLETES_QUEST = "completes_quest"
    UNLOCKS_DOOR = "unlocks_door"
    ENABLES_INTERACTION = "enables_interaction"
    # Character edges
    DROPS_ITEM = "drops_item"
    SELLS_ITEM = "sells_item"
    GIVES_ITEM = "gives_item"
    SPAWNS_IN = "spawns_in"
    HAS_SPAWN = "has_spawn"
    BELONGS_TO_FACTION = "belongs_to_faction"
    PROTECTS = "protects"
    # Recipe edges
    REQUIRES_MATERIAL = "requires_material"
    PRODUCES = "produces"
    # Zone edges
    CONNECTS_TO = "connects_to"
    CONTAINS = "contains"
    # Resource edges
    YIELDS_ITEM = "yields_item"
    # Spawn point edges
    SPAWNS_CHARACTER = "spawns_character"
    GATED_BY_QUEST = "gated_by_quest"
    STOPS_AFTER_QUEST = "stops_after_quest"
    # Zone line edges
    CONNECTS_ZONES = "connects_zones"
    # World object edges
    REMOVES_INVULNERABILITY = "removes_invulnerability"

@dataclass
class Node:
    key: str
    type: NodeType
    display_name: str
    properties: dict[str, Any]

@dataclass
class Edge:
    source: str
    target: str
    type: EdgeType
    group: str | None = None
    ordinal: int | None = None
    negated: bool = False
    properties: dict[str, Any] = field(default_factory=dict)

@dataclass
class ViewNode:
    """A node in the rendered dependency tree."""
    node_key: str
    edge_type: EdgeType | None    # null for root
    children: list[ViewNode]
    properties: dict[str, Any]    # merged from edge + node for rendering
    is_cycle_ref: bool = False    # true if this is a pruned cycle back-ref
```

#### `graph.py` — EntityGraph

The in-memory graph. Wraps nodes dict + edge lists + adjacency indexes.

```python
class EntityGraph:
    _nodes: dict[str, Node]                    # key → Node
    _edges: list[Edge]                         # all edges
    _out: dict[str, list[Edge]]                # key → outgoing edges
    _in: dict[str, list[Edge]]                 # key → incoming edges

    def add_node(node: Node) -> None
    def add_edge(edge: Edge) -> None
    def get_node(key: str) -> Node | None
    def out_edges(key: str, type: EdgeType | None = None) -> list[Edge]
    def in_edges(key: str, type: EdgeType | None = None) -> list[Edge]
    def nodes_of_type(type: NodeType) -> Iterable[Node]
    def build_indexes() -> None                # build _out/_in from _edges
```

#### `graph_builder.py` — DB → Graph

One function per entity type, one per relationship type. Called by
`build_graph(db_path) → EntityGraph`.

```python
def build_graph(db_path: Path) -> EntityGraph:
    """Build the full entity graph from the clean SQLite DB."""
    graph = EntityGraph()
    conn = connect(db_path)

    # Entity nodes (one function each)
    _add_quest_nodes(conn, graph)
    _add_item_nodes(conn, graph)
    _add_character_nodes(conn, graph)
    _add_zone_nodes(conn, graph)
    _add_zone_line_nodes(conn, graph)
    _add_spawn_point_nodes(conn, graph)
    _add_mining_node_nodes(conn, graph)
    _add_water_nodes(conn, graph)
    _add_forge_nodes(conn, graph)
    _add_item_bag_nodes(conn, graph)
    _add_recipe_nodes(conn, graph)
    _add_door_nodes(conn, graph)
    _add_faction_nodes(conn, graph)
    _add_spell_nodes(conn, graph)
    _add_skill_nodes(conn, graph)
    _add_teleport_nodes(conn, graph)
    _add_achievement_trigger_nodes(conn, graph)
    _add_secret_passage_nodes(conn, graph)
    _add_wishing_well_nodes(conn, graph)
    _add_treasure_location_nodes(conn, graph)
    _add_book_nodes(conn, graph)
    _add_class_nodes(conn, graph)
    _add_stance_nodes(conn, graph)
    _add_ascension_nodes(conn, graph)

    # Relationship edges (one function per junction table / FK relationship)
    _add_quest_step_edges(conn, graph)          # quest → character/zone/item steps
    _add_quest_required_item_edges(conn, graph) # quest → item
    _add_quest_acquisition_edges(conn, graph)   # quest → character (assigned_by)
    _add_quest_completion_edges(conn, graph)    # quest → character (completed_by)
    _add_quest_chain_edges(conn, graph)         # quest → quest (chains_to, also_completes)
    _add_quest_reward_edges(conn, graph)        # quest → item (rewards_item)
    _add_quest_faction_edges(conn, graph)       # quest → faction
    _add_quest_unlock_edges(conn, graph)        # quest → zone_line, quest → character
    _add_character_drop_edges(conn, graph)      # character → item
    _add_character_vendor_edges(conn, graph)    # character → item
    _add_character_dialog_give_edges(conn, graph) # character → item
    _add_character_spawn_edges(conn, graph)     # character → spawn_point, spawn_point → character
    _add_spawn_point_gate_edges(conn, graph)    # spawn_point → quest (gated_by, stops_after)
    _add_spawn_point_protector_edges(conn, graph) # character → character (protects)
    _add_zone_line_gate_edges(conn, graph)      # zone_line → quest
    _add_zone_line_connect_edges(conn, graph)   # zone_line → zone
    _add_zone_contain_edges(conn, graph)        # zone → mining_node/water/forge/item_bag
    _add_mining_yield_edges(conn, graph)        # mining_node → item
    _add_water_yield_edges(conn, graph)         # water → item
    _add_item_bag_yield_edges(conn, graph)      # item_bag → item
    _add_crafting_edges(conn, graph)            # recipe → item (requires_material, produces)
    _add_item_craft_edges(conn, graph)          # item → recipe (crafted_from)
    _add_item_quest_edges(conn, graph)          # item → quest (assigns_quest, completes_quest)
    _add_item_spell_edges(conn, graph)          # item → spell (teaches_spell)
    _add_item_door_edges(conn, graph)           # item → door (unlocks_door)
    _add_character_faction_edges(conn, graph)   # character → faction

    graph.build_indexes()
    return graph
```

#### `graph_overrides.py` — Manual edges

```python
def load_overrides(path: Path) -> tuple[list[Node], list[Edge]]:
    """Parse graph_overrides.toml → manual nodes and edges."""

def merge_overrides(graph: EntityGraph, overrides_path: Path) -> None:
    """Merge manual nodes/edges into the graph."""
```

#### `generator.py` — Orchestrator

```python
def generate(db_path: Path, overrides_path: Path | None) -> EntityGraph:
    graph = build_graph(db_path)
    if overrides_path:
        merge_overrides(graph, overrides_path)
    return graph
```

The Python pipeline emits only the raw graph (nodes + edges). Quest view
trees are built on-demand in C# by QuestViewBuilder from the graph +
live game state. Level estimation also moves to C# since it depends on
which nodes are reachable from a quest (which varies with game state).

Removed from Python pipeline:
- `quest_view.py` — view building moved to C# (QuestViewBuilder.cs)
- `level_estimator.py` — level estimation moved to C# (lives in QuestViewBuilder)
- `merge.py` — no manual override files exist; dropped

---

## C# Mod

### Current structure (replaced)

```
AdventureGuide/src/
├── Plugin.cs                        # Lifecycle, wiring
├── Config/GuideConfig.cs            # BepInEx config
├── Data/
│   ├── GuideData.cs                 # JSON loader, quest indexes
│   ├── QuestEntry.cs                # Quest/step/item data classes
│   └── StepSceneResolver.cs         # Step → scene mapping
├── State/
│   ├── QuestStateTracker.cs         # Active/completed quest tracking
│   ├── StepProgress.cs              # Current step resolution
│   ├── TrackerState.cs              # Pinned quest list
│   ├── NavigationHistory.cs         # Back/forward history
│   ├── GameUIVisibility.cs          # UI toggle state
│   └── GameWindowOverlap.cs         # Overlap detection
├── Navigation/
│   ├── NavigationController.cs      # 1343-line monolith
│   ├── NavigationTarget.cs          # Target DTO
│   ├── WorldMarkerSystem.cs         # Marker emission
│   ├── SpawnPointBridge.cs          # Spawn state resolution
│   ├── EntityRegistry.cs            # Live NPC index
│   ├── ZoneGraph.cs                 # Cross-zone routing
│   ├── ArrowRenderer.cs             # Directional arrow
│   ├── GroundPathRenderer.cs        # NavMesh path
│   ├── MarkerPool.cs                # Billboard pooling
│   ├── MarkerFonts.cs               # Font loading
│   ├── NavigationDisplay.cs         # Constants
│   ├── SpawnTimerTracker.cs         # Respawn timers
│   ├── MiningNodeTracker.cs         # Mining state
│   └── LootScanner.cs              # Corpse/chest scanning
├── UI/
│   ├── GuideWindow.cs               # Main window host
│   ├── QuestDetailPanel.cs          # Quest page (920 lines)
│   ├── QuestListPanel.cs            # Quest browser
│   ├── TrackerWindow.cs             # Tracker sidebar
│   ├── FilterState.cs               # Search/filter
│   ├── StepDistance.cs              # Distance display
│   ├── TrackerSorter.cs            # Sort logic
│   ├── TrackerSortMode.cs          # Sort enum
│   └── Theme.cs                     # Visual constants
├── Rendering/
│   ├── ImGuiRenderer.cs             # ImGui integration
│   └── CimguiNative.cs              # Native bindings
├── Patches/                         # 8 Harmony patches
└── Diagnostics/DebugAPI.cs
```

### New structure

```
AdventureGuide/src/
├── Plugin.cs                        # Lifecycle, wiring (rewritten)
│
├── Config/
│   └── GuideConfig.cs               # BepInEx config (extended)
│
├── Graph/
│   ├── EntityGraph.cs               # In-memory graph: nodes + adjacency
│   ├── Node.cs                      # Node record (key, type, name, props)
│   ├── Edge.cs                      # Edge record (source, target, type, group, props)
│   ├── NodeType.cs                  # Enum (25 types)
│   ├── EdgeType.cs                  # Enum (~35 types)
│   └── GraphLoader.cs              # JSON → EntityGraph
│
├── Views/
│   ├── ViewNode.cs                  # Renderable tree node
│   ├── QuestViewBuilder.cs         # Build quest views on-demand from graph + state
│   └── EntityViewBuilder.cs        # Build item/character/zone views (future)
│
├── State/
│   ├── GameState.cs                 # Unified state registry
│   ├── INodeStateResolver.cs        # Per-type resolver interface
│   ├── NodeState.cs                 # State value types
│   ├── Resolvers/
│   │   ├── QuestStateResolver.cs    # quest → completed/active/not_started
│   │   ├── CharacterStateResolver.cs # character → alive/dead/disabled/etc
│   │   ├── ItemStateResolver.cs     # item → inventory count
│   │   ├── ZoneLineStateResolver.cs # zone_line → accessible/locked
│   │   ├── SpawnPointStateResolver.cs # spawn → active/respawning/gated/night
│   │   ├── MiningNodeStateResolver.cs # mining → available/mined(timer)
│   │   ├── ItemBagStateResolver.cs  # item_bag → available/respawning/gone
│   │   └── DoorStateResolver.cs     # door → locked/unlocked
│   ├── QuestTracker.cs              # Active/completed quest tracking (from QuestStateTracker)
│   ├── TrackerState.cs              # Pinned quest list (rewritten, no migration)
│   ├── NavigationHistory.cs         # Back/forward history (kept)
│   ├── GameUIVisibility.cs          # UI toggle state (kept)
│   └── GameWindowOverlap.cs         # Overlap detection (kept)
│
├── Frontier/
│   ├── FrontierComputer.cs          # ViewNode tree + state → actionable leaf set
│   ├── MarkerComputer.cs            # All quests + state → marker entries
│   └── NavigationSet.cs             # Player's selected nav targets (any node keys)
│
├── Navigation/
│   ├── NavigationEngine.cs          # Arrow + path: closest target in nav set
│   ├── IPositionResolver.cs         # node key → world position(s)
│   ├── PositionResolverRegistry.cs  # Dispatches by NodeType
│   ├── Resolvers/
│   │   ├── CharacterPositionResolver.cs  # live NPC → spawn fallback
│   │   ├── ZoneLinePositionResolver.cs   # closest accessible zone line
│   │   ├── ZonePositionResolver.cs       # zone graph routing
│   │   ├── DirectPositionResolver.cs     # for any node with x/y/z
│   │   ├── ItemPositionResolver.cs       # recursive source resolution
│   │   └── QuestPositionResolver.cs      # → closest frontier node
│   ├── ZoneRouter.cs                # Cross-zone BFS routing (from ZoneGraph)
│   ├── EntityRegistry.cs            # Live NPC index (kept, minor changes)
│   ├── ArrowRenderer.cs             # Directional arrow (kept)
│   ├── GroundPathRenderer.cs        # NavMesh path (kept)
│   └── NavigationDisplay.cs         # Constants (kept)
│
├── Markers/
│   ├── MarkerSystem.cs              # Renders computed markers as billboards
│   ├── MarkerEntry.cs               # Marker data (position, type, text, node key)
│   ├── MarkerType.cs                # Priority enum (kept, possibly extended)
│   ├── MarkerPool.cs                # Billboard pooling (kept)
│   ├── MarkerFonts.cs               # Font loading (kept)
│   └── LiveStateTracker.cs          # Per-frame: spawn/death transitions, timers
│                                    # (absorbs SpawnTimerTracker + MiningNodeTracker
│                                    #  + SpawnPointBridge + LootScanner into one)
│
├── UI/
│   ├── GuideWindow.cs               # Main window host (adapted)
│   ├── ViewRenderer.cs              # Single recursive tree renderer (replaces QuestDetailPanel)
│   ├── RenderTemplates.cs           # Template lookup by (EdgeType, NodeType)
│   ├── QuestListPanel.cs            # Quest browser (adapted)
│   ├── TrackerPanel.cs              # Tracker sidebar (compact: 2 lines per quest)
│   ├── FilterState.cs               # Search/filter (kept)
│   ├── Theme.cs                     # Visual constants (kept)
│   └── TrackerSortMode.cs           # Sort enum (kept)
│
├── Rendering/
│   ├── ImGuiRenderer.cs             # ImGui integration (kept)
│   └── CimguiNative.cs              # Native bindings (kept)
│
├── Patches/                         # Harmony patches (adapted, same hooks)
│   ├── SpawnPatch.cs                # → EntityRegistry + LiveStateTracker
│   ├── DeathPatch.cs                # → EntityRegistry + LiveStateTracker
│   ├── QuestAssignPatch.cs          # → QuestTracker + NavigationEngine
│   ├── QuestFinishPatch.cs          # → QuestTracker + NavigationEngine
│   ├── InventoryPatch.cs            # → QuestTracker + NavigationEngine
│   ├── QuestMarkerPatch.cs          # → suppress native markers (kept)
│   ├── PointerOverUIPatch.cs        # → ImGui capture (kept)
│   └── QuestLogPatch.cs             # → journal override (kept)
│
└── Diagnostics/DebugAPI.cs          # (adapted)
```

### Component responsibilities

#### Graph layer (`Graph/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `Node` | Immutable record: key, type, display_name, properties dict | — |
| `Edge` | Immutable record: source, target, type, group, ordinal, negated, properties | — |
| `NodeType` | Enum of all 25 entity types | — |
| `EdgeType` | Enum of all ~35 edge types | — |
| `EntityGraph` | In-memory graph. Adjacency lists (out + in) indexed by node key. API: `GetNode`, `OutEdges`, `InEdges`, `NodesOfType`. Built once on load, immutable thereafter. | Node, Edge |
| `GraphLoader` | Deserializes `_nodes` + `_edges` from JSON into EntityGraph. Builds adjacency indexes. | EntityGraph, Node, Edge |

#### Views layer (`Views/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `ViewNode` | Tree node for rendering: node_key, edge_type, children, properties, is_cycle_ref. The universal rendering unit — every UI tree is made of ViewNodes. | — |
| `QuestViewBuilder` | Builds quest view trees on-demand from EntityGraph + GameState via depth-first traversal with cycle pruning. Called each time a quest page is opened or game state changes. Views are NOT pre-computed — they depend on live game state (quest completion, inventory) so pre-computing would produce stale trees. | EntityGraph, GameState, ViewNode |
| `EntityViewBuilder` | Builds entity page views (item, character, zone) from EntityGraph. Future — but the interface is defined now. | EntityGraph, ViewNode |

#### State layer (`State/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `GameState` | Central state registry. Maps NodeType → INodeStateResolver. Single `GetState(nodeKey) → NodeState` entry point. Lazy evaluation — state resolved on query, not pre-computed. | EntityGraph, INodeStateResolver |
| `INodeStateResolver` | Interface: `Resolve(node) → NodeState`. One implementation per NodeType that has live state. | Node |
| `NodeState` | Discriminated union / enum + data. Values: `Completed`, `Active`, `NotStarted` (quests); `Alive`, `Dead(timer)`, `Disabled`, `NightLocked`, `QuestGated(questName)` (characters/spawns); `Available`, `Mined(timer)` (mining); `Count(n)` (items); `Accessible`, `Locked(reason)` (zone lines); etc. | — |
| `QuestTracker` | Tracks active/completed quests + inventory counts. Publishes version int for change detection. Absorbs current QuestStateTracker with minor changes. | EntityGraph |
| `TrackerState` | Pinned quest list per character. Rewritten from scratch — no migration of existing config values (players re-add tracked quests). References node keys for future entity tracking. | — |

#### Frontier layer (`Frontier/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `FrontierComputer` | Pure function: `(ViewNode tree, GameState) → Set<nodeKey>`. Walks the view tree depth-first, collecting leaf nodes whose parent dependencies are satisfied. These are the simultaneously actionable objectives. | ViewNode, GameState |
| `MarkerComputer` | Pure function: `(EntityGraph, QuestTracker, GameState) → List<MarkerEntry>`. For ALL eligible quests: computes frontier nodes (objective markers) + awareness nodes (quest giver markers for available quests, turn-in markers for active quests with two states). Single pass, single output. | EntityGraph, QuestTracker, GameState, FrontierComputer |
| `NavigationSet` | Stateful: player's selected navigation targets. `Set<nodeKey>`. API: `Override(key)` (click — clear + add), `Toggle(key)` (shift+click — add/remove), `Clear()`, `Contains(key)`, `Keys`. Accepts any navigable node key — quest, character, item, mining node, etc. | — |

#### Navigation layer (`Navigation/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `NavigationEngine` | Per-frame: resolves all nav-set entries to world positions via PositionResolverRegistry, finds closest. Drives arrow + ground path. Replaces NavigationController (1343 lines → ~300). | NavigationSet, PositionResolverRegistry, ZoneRouter |
| `IPositionResolver` | Interface: `Resolve(node, context) → List<WorldPosition>`. Per-NodeType. | Node, EntityGraph |
| `PositionResolverRegistry` | Maps NodeType → IPositionResolver. Dispatches `Resolve(nodeKey)`. | EntityGraph, IPositionResolver |
| `CharacterPositionResolver` | Live NPC via EntityRegistry → static spawn fallback. Prefers alive. | EntityRegistry, EntityGraph |
| `ZoneLinePositionResolver` | Closest accessible zone line in current zone. | EntityGraph, GameState |
| `ZonePositionResolver` | Route via ZoneRouter to zone entry. | ZoneRouter |
| `DirectPositionResolver` | For nodes with x/y/z in properties: forge, door, item_bag, mining_node, spawn_point, teleport, achievement_trigger, secret_passage, wishing_well, treasure_location, world_object. Prefers available state for mining nodes and item bags. | EntityGraph, GameState |
| `ItemPositionResolver` | Walks item's incoming edges (drops_from, mined_at, fished_at, sold_by, dialog_give, pickup) recursively to find navigable source positions. | EntityGraph, PositionResolverRegistry |
| `QuestPositionResolver` | Computes frontier of quest's view tree, then resolves each frontier node, returns all positions. Closest wins in NavigationEngine. | FrontierComputer, PositionResolverRegistry |
| `ZoneRouter` | Cross-zone BFS routing. Zone line accessibility via quest gate edges. From current ZoneGraph, adapted to read from EntityGraph instead of ZoneLineEntry list. | EntityGraph, GameState |
| `EntityRegistry` | Live NPC index. Kept from current implementation. Fed by SpawnPatch/DeathPatch. | — |
| `ArrowRenderer` | Directional arrow overlay. Kept — reads position from NavigationEngine instead of NavigationController. | NavigationEngine |
| `GroundPathRenderer` | NavMesh ground path. Kept — reads target from NavigationEngine. | NavigationEngine |

#### Markers layer (`Markers/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `MarkerSystem` | Renders MarkerEntries as world-space billboards. Handles priority dedup (same position, multiple markers → highest priority wins). Per-frame live state updates (NPC alive→dead transitions, timer text refresh). Absorbs WorldMarkerSystem but reads from MarkerComputer output instead of doing its own per-quest iteration. | MarkerComputer, MarkerPool, LiveStateTracker |
| `MarkerEntry` | Data: position, MarkerType, display_name, sub_text, node_key, quest_context. | — |
| `MarkerType` | Priority enum: TurnInReady > Objective > QuestGiver > TurnInPending > DeadSpawn > NightSpawn > QuestLocked > ... (possibly extended). | — |
| `MarkerPool` | Billboard object pooling. Kept as-is. | — |
| `LiveStateTracker` | Per-frame: tracks NPC spawn/death, mining node state, item bag state, respawn timers. Absorbs SpawnTimerTracker + MiningNodeTracker + SpawnPointBridge + LootScanner into one component with a unified interface. Marks MarkerComputer dirty on state changes. | EntityRegistry, EntityGraph |

#### UI layer (`UI/`)

| Component | Responsibility | Depends on |
|---|---|---|
| `GuideWindow` | Main ImGui window. Hosts QuestListPanel + ViewRenderer in a split layout. Adapted to work with EntityGraph + ViewNode instead of QuestEntry. | EntityGraph, QuestTracker, ViewRenderer |
| `ViewRenderer` | Single recursive renderer. Given a ViewNode tree, renders it with templates looked up by (EdgeType, NodeType). Handles: expand/collapse, cycle-ref indicators, state checkboxes/timers/locks, NAV buttons (with click/shift+click), clickable entity names. Replaces QuestDetailPanel (920 lines) with a data-driven approach (~400 lines). | EntityGraph, GameState, NavigationSet, RenderTemplates |
| `RenderTemplates` | Static template definitions. Maps (EdgeType, NodeType) → rendering function. Each template defines: icon, label format, sub-text, whether children are shown, indentation style. Adding a new edge/node type = adding a template entry, no other code changes. | — |
| `QuestListPanel` | Quest browser with search/filter. Adapted to read from EntityGraph (quest nodes) instead of GuideData.All. | EntityGraph, QuestTracker, FilterState |
| `TrackerPanel` | Sidebar quest tracker. Compact two-line display per quest: line 1 is quest name + status, line 2 is the closest frontier node summary (what the player would navigate to if they selected this quest — essentially the "next action" for that quest). Does NOT show full dependency trees, drop sources, or all frontier nodes — that detail lives in the main ViewRenderer panel. NAV button per quest for quick navigation. | EntityGraph, QuestTracker, TrackerState, FrontierComputer, PositionResolverRegistry, GameState |
| `FilterState` | Search/filter state. Kept. | — |
| `Theme` | Visual constants. Kept. | — |

#### Patches (`Patches/`)

Same 8 Harmony hooks on the same game methods. Static-field DI (Harmony
limitation). Component targets change:

| Patch | Current targets | New targets |
|---|---|---|
| SpawnPatch | EntityRegistry, SpawnTimerTracker, WorldMarkerSystem, LootScanner | EntityRegistry, LiveStateTracker |
| DeathPatch | EntityRegistry, SpawnTimerTracker, WorldMarkerSystem, LootScanner | EntityRegistry, LiveStateTracker |
| QuestAssignPatch | QuestStateTracker, NavigationController, LootScanner, TrackerState | QuestTracker, NavigationEngine, LiveStateTracker, TrackerState |
| QuestFinishPatch | QuestStateTracker, NavigationController, LootScanner, TrackerState | QuestTracker, NavigationEngine, LiveStateTracker, TrackerState |
| InventoryPatch | QuestStateTracker, NavigationController, LootScanner | QuestTracker, NavigationEngine, LiveStateTracker |
| QuestMarkerPatch | (bool gate) | (bool gate — unchanged) |
| PointerOverUIPatch | ImGuiRenderer | ImGuiRenderer (unchanged) |
| QuestLogPatch | (bool gate) | (bool gate — unchanged) |

### Component lifecycle

#### Initialization (Plugin.Awake)

```
1. GuideConfig
2. GraphLoader → EntityGraph (from embedded JSON)
3. (no pre-loading of views — QuestViewBuilder builds on-demand from graph + state)
4. QuestTracker(EntityGraph)
5. TrackerState + LoadFromConfig
6. GameState(EntityGraph) + register all NodeType resolvers
7. ImGuiRenderer
8. EntityRegistry, LiveStateTracker
9. FrontierComputer
10. MarkerComputer(EntityGraph, QuestTracker, GameState, FrontierComputer)
11. NavigationSet
12. PositionResolverRegistry + register all NodeType resolvers
13. NavigationEngine(NavigationSet, PositionResolverRegistry, ZoneRouter)
14. ArrowRenderer(NavigationEngine)
15. GroundPathRenderer(NavigationEngine)
16. MarkerSystem(MarkerComputer, MarkerPool, LiveStateTracker)
17. NavigationHistory
18. GuideWindow, QuestListPanel, ViewRenderer, TrackerPanel
19. Inject static fields into Harmony patches
20. Harmony.PatchAll()
21. Initial sync
```

#### Per-frame update (Plugin.Update)

```
1. LiveStateTracker.Update()          // NPC spawn/death, mining, bags, timers
2. QuestTracker.Update()              // lazy inventory/implicit quest refresh
3. MarkerComputer.Recompute()         // if dirty: all quests → marker set
4. NavigationEngine.Update()          // resolve nav set → closest target
5. GroundPathRenderer.Update()        // NavMesh path to target
6. MarkerSystem.Update()              // render markers, live state overlays
7. Keybind checks                     // toggle windows, toggle path
```

#### Per-frame render (Plugin.OnGUI → ImGui)

```
1. GuideWindow.Draw()                 // quest list + ViewRenderer tree
2. TrackerPanel.Draw()                // compact: quest name + closest frontier summary
3. ArrowRenderer.Draw()               // directional arrow overlay
```

#### Scene change (OnSceneLoaded)

```
1. EntityRegistry.Clear()
2. LiveStateTracker.OnSceneLoaded()   // clear timers, rescan mining/bags
3. QuestTracker.OnSceneChanged()      // sync from GameData
4. TrackerState.OnCharacterLoaded()
5. MarkerComputer.MarkDirty()         // full recompute on next frame
6. NavigationEngine.OnSceneChanged()  // reload per-character nav state
```

### What's kept, adapted, or replaced

| Current file | Disposition | New equivalent |
|---|---|---|
| Plugin.cs | Rewritten | Plugin.cs (same lifecycle, new wiring) |
| GuideData.cs | Replaced | GraphLoader.cs + EntityGraph.cs |
| QuestEntry.cs (20+ classes) | Replaced | Node.cs + Edge.cs + ViewNode.cs |
| StepSceneResolver.cs | Removed | Node properties carry scene directly |
| QuestStateTracker.cs | Adapted | QuestTracker.cs (same logic, graph-aware) |
| StepProgress.cs | Replaced | FrontierComputer.cs |
| TrackerState.cs | Kept | Minor: track node keys, not just quest DBNames |
| NavigationHistory.cs | Kept | Unchanged |
| GameUIVisibility.cs | Kept | Unchanged |
| GameWindowOverlap.cs | Kept | Unchanged |
| NavigationController.cs (1343 lines) | Replaced | NavigationEngine (~300) + PositionResolverRegistry + 6 resolvers + ZoneRouter |
| NavigationTarget.cs | Replaced | NavigationSet.cs (set of node keys) |
| WorldMarkerSystem.cs (766 lines) | Replaced | MarkerSystem (~200) + MarkerComputer (~300) |
| SpawnPointBridge.cs | Absorbed | CharacterStateResolver + SpawnPointStateResolver |
| EntityRegistry.cs | Kept | Minor: same interface, updated patch wiring |
| ZoneGraph.cs | Adapted | ZoneRouter.cs (reads from EntityGraph) |
| ArrowRenderer.cs | Kept | Reads from NavigationEngine |
| GroundPathRenderer.cs | Kept | Reads from NavigationEngine |
| MarkerPool.cs | Kept | Unchanged |
| MarkerFonts.cs | Kept | Unchanged |
| NavigationDisplay.cs | Kept | Unchanged |
| SpawnTimerTracker.cs | Absorbed | LiveStateTracker |
| MiningNodeTracker.cs | Absorbed | LiveStateTracker |
| LootScanner.cs | Absorbed | LiveStateTracker |
| QuestDetailPanel.cs (920 lines) | Replaced | ViewRenderer (~400) + RenderTemplates |
| QuestListPanel.cs | Adapted | Reads EntityGraph quest nodes |
| TrackerWindow.cs | Rewritten | TrackerPanel (compact 2-line per quest, closest frontier summary) |
| GuideWindow.cs | Adapted | Same structure, new components |
| FilterState.cs | Kept | Unchanged |
| StepDistance.cs | Removed | Distance computed in NavigationEngine |
| Theme.cs | Kept | Unchanged |
| TrackerSorter.cs | Adapted | Works with quest node properties |
| TrackerSortMode.cs | Kept | Unchanged |
| ImGuiRenderer.cs | Kept | Unchanged |
| CimguiNative.cs | Kept | Unchanged |
| All 8 patches | Adapted | Same hooks, new targets |
| DebugAPI.cs | Adapted | Graph-aware debug queries |

### Line count estimates

| Layer | Current | New (estimated) | Delta |
|---|---|---|---|
| Data model (QuestEntry, GuideData) | ~700 | ~250 (Node, Edge, ViewNode, EntityGraph, GraphLoader) | -450 |
| State (QuestStateTracker, StepProgress) | ~450 | ~500 (QuestTracker, GameState, 8 resolvers) | +50 |
| Navigation (NavigationController, SpawnPointBridge, ZoneGraph) | ~1800 | ~900 (NavigationEngine, 6 resolvers, ZoneRouter) | -900 |
| Markers (WorldMarkerSystem) | ~770 | ~600 (MarkerSystem, MarkerComputer, LiveStateTracker) | -170 |
| UI (QuestDetailPanel, TrackerWindow) | ~1600 | ~800 (ViewRenderer, RenderTemplates, TrackerPanel) | -800 |
| Frontier | 0 | ~200 (FrontierComputer, NavigationSet) | +200 |
| Infrastructure (kept) | ~1800 | ~1800 | 0 |
| **Total** | **~7120** | **~5050** | **~-2070** |

The reduction comes from eliminating ad hoc per-type switches and
duplicated traversal logic. The graph's uniform edge/node model means
one code path handles all types, replacing N separate implementations.
