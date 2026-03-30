"""Entity graph data model.

The guide's knowledge is an entity graph: every game entity is a Node,
every relationship is a typed Edge.  The Python pipeline builds the raw
graph from the clean SQLite DB and serializes it to JSON.  The C# mod
deserializes it, builds view trees on demand from the graph + live game
state, and handles rendering, navigation, and markers.

Design:
- Node and Edge use typed fields (not dicts) for compile-time safety on
  the C# side and clarity on the Python side.
- NodeType and EdgeType are exhaustive enums covering every entity and
  relationship the game contains.
- AND/OR/NOT dependency semantics are encoded via Edge.group and
  Edge.negated (see plan doc for full semantics).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Node types — every entity that is a node in the graph
# ---------------------------------------------------------------------------


class NodeType(str, Enum):
    """Every entity type that exists as a graph node."""

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


# ---------------------------------------------------------------------------
# Edge types — every relationship between nodes
# ---------------------------------------------------------------------------


class EdgeType(str, Enum):
    """Every typed, directed relationship in the graph.

    Convention: A → B means "A relates to B in this way."
    """

    # -- Quest edges (source = quest) --
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
    UNLOCKS_VENDOR_ITEM = "unlocks_vendor_item"

    # -- Item edges (source = item) --
    CRAFTED_FROM = "crafted_from"
    TEACHES_SPELL = "teaches_spell"
    ASSIGNS_QUEST = "assigns_quest"
    COMPLETES_QUEST = "completes_quest"
    UNLOCKS_DOOR = "unlocks_door"
    ENABLES_INTERACTION = "enables_interaction"

    # -- Character edges (source = character) --
    DROPS_ITEM = "drops_item"
    SELLS_ITEM = "sells_item"
    GIVES_ITEM = "gives_item"
    SPAWNS_IN = "spawns_in"
    HAS_SPAWN = "has_spawn"
    BELONGS_TO_FACTION = "belongs_to_faction"
    PROTECTS = "protects"

    # -- Recipe edges (source = recipe) --
    REQUIRES_MATERIAL = "requires_material"
    PRODUCES = "produces"

    # -- Zone edges (source = zone) --
    CONNECTS_TO = "connects_to"
    CONTAINS = "contains"

    # -- Resource node edges (source = mining_node / water / item_bag) --
    YIELDS_ITEM = "yields_item"

    # -- Spawn point edges --
    SPAWNS_CHARACTER = "spawns_character"
    GATED_BY_QUEST = "gated_by_quest"
    STOPS_AFTER_QUEST = "stops_after_quest"

    # -- Zone line edges --
    CONNECTS_ZONES = "connects_zones"

    # -- World object edges --
    REMOVES_INVULNERABILITY = "removes_invulnerability"


# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """A node in the entity graph.

    Every field beyond key/type/display_name is optional and type-specific.
    The serializer emits all non-None fields; the C# GraphLoader maps them
    to typed nullable fields on the C# Node class.
    """

    key: str
    type: NodeType
    display_name: str

    # Position (character spawns, zone lines, mining nodes, etc.)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    scene: str | None = None

    # Identity
    db_name: str | None = None  # quest db_name, item id, etc.
    description: str | None = None

    # Game data
    level: int | None = None
    zone: str | None = None  # display name of containing zone
    zone_key: str | None = None  # stable key of containing zone
    keyword: str | None = None
    night_spawn: bool = False
    is_enabled: bool = True

    # Quest-specific
    xp_reward: int | None = None
    gold_reward: int | None = None
    reward_item_key: str | None = None
    repeatable: bool = False
    disabled: bool = False
    disabled_text: str | None = None
    implicit: bool = False  # completable without formal acceptance
    kill_turn_in_holder: bool = False
    destroy_turn_in_holder: bool = False
    drop_invuln_on_holder: bool = False
    once_per_spawn_instance: bool = False

    # Item-specific
    item_level: int | None = None
    stackable: bool = False
    is_unique: bool = False
    template: bool = False  # crafting recipe template item

    # Character-specific
    is_vendor: bool = False
    is_friendly: bool = False
    invulnerable: bool = False
    faction_key: str | None = None

    # Spawn point specific
    spawn_chance: float | None = None
    is_rare: bool = False
    is_directly_placed: bool = False
    respawn_delay: float | None = None

    # Mining node / water / item_bag specific
    respawn_time: float | None = None

    # Item bag specific
    respawns: bool = True

    # Door specific
    key_item_key: str | None = None

    # Teleport specific
    teleport_item_key: str | None = None

    # Zone specific
    is_dungeon: bool = False
    level_min: int | None = None
    level_max: int | None = None

    # Book specific
    book_title: str | None = None

    # Achievement trigger
    achievement_name: str | None = None

    # Faction specific
    default_value: float | None = None

    # Zone line specific
    destination_zone_key: str | None = None
    destination_display: str | None = None
    landing_x: float | None = None
    landing_y: float | None = None
    landing_z: float | None = None


@dataclass
class Edge:
    """A typed, directed relationship between two nodes.

    AND/OR semantics are encoded via ``group``:
    - group=None: unconditional, always applies.
    - Same group value: AND — all edges in the group must be satisfied.
    - Different groups for the same (source, edge_type pattern): OR —
      any fully-satisfied group unlocks.

    ``negated=True`` inverts the condition (e.g., PietyTrigger: spawn
    active when quest is NOT completed).
    """

    source: str
    target: str
    type: EdgeType
    group: str | None = None
    ordinal: int | None = None
    negated: bool = False
    quantity: int | None = None
    keyword: str | None = None
    note: str | None = None
    chance: float | None = None
    amount: int | None = None
    slot: int | None = None
    time_restriction: str | None = None  # "day" or "night"; None = always
