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

from dataclasses import dataclass, field
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
    LOCATION = "location"


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
    AFFECTS_FACTION = "affects_faction"

    # -- Item edges (source = item) --
    CRAFTED_FROM = "crafted_from"
    TEACHES_SPELL = "teaches_spell"
    ASSIGNS_QUEST = "assigns_quest"
    COMPLETES_QUEST = "completes_quest"
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

    # -- Zone line edges --
    CONNECTS_ZONES = "connects_zones"

    # -- World object edges --
    REMOVES_INVULNERABILITY = "removes_invulnerability"
    STEP_TURN_IN = "step_turn_in"
    STEP_LOOT = "step_loot"
    STEP_BUY = "step_buy"
    STEP_GO_TO = "step_go_to"
    CREATES_ITEM = "creates_item"


# ---------------------------------------------------------------------------
# Gates — when a subject is available (see processor.gates)
# ---------------------------------------------------------------------------


class SubjectKind(str, Enum):
    """What a gate makes available."""

    ZONE_LINE = "zone_line"
    CHARACTER = "character"
    SPAWN_POINT = "spawn_point"
    VENDOR_ITEM = "vendor_item"
    ITEM_BAG = "item_bag"
    UI_ITEM_ACCESS_TARGET = "ui_item_access_target"
    DOOR = "door"


class AtomKind(str, Enum):
    """One fact of game state that a gate can require."""

    QUEST_DONE = "quest_done"
    QUEST_NOT_DONE = "quest_not_done"
    ITEM_HELD = "item_held"
    KEY_HELD = "key_held"
    ROOM_FURNISHED = "room_furnished"
    PLANNING_SLOT_ITEM = "planning_slot_item"
    ACCOUNT_STATE = "account_state"
    # Advisory: the mod cannot observe it reliably, so it guides and never hides.
    ENCOUNTER_WON = "encounter_won"
    WORLD_STATE = "world_state"
    # No game state satisfies it, such as a door whose key cannot be obtained.
    NEVER = "never"


@dataclass(frozen=True, slots=True)
class GateAtom:
    """A fact, naming a quest, item, furniture set, or character by stable key."""

    kind: AtomKind
    ref: str
    slot: str | None = None
    instruction: str | None = None
    actor: str | None = None
    value: str | None = None
    phase: str | None = None
    scope: str | None = None
    quantity: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Gate atom quantity must be a positive integer")
        if self.kind != AtomKind.ENCOUNTER_WON and self.quantity != 1:
            raise ValueError("Only an encounter defeat can have a gate atom quantity")


@dataclass(frozen=True, slots=True)
class Gate:
    """One rule on a subject: it holds when every atom of one group holds.

    ``item_key`` names the item of a vendor item subject, whose subject key is
    the vendor copy.
    """

    subject_kind: SubjectKind
    subject_key: str
    gate: str
    groups: tuple[tuple[GateAtom, ...], ...]
    item_key: str | None = None


# ---------------------------------------------------------------------------
# Workflow descriptors
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WorkflowTarget:
    stable_key: str
    quantity: int


@dataclass(slots=True)
class WorkflowCycle:
    trigger_item_stable_key: str
    trigger_item_quantity: int
    trigger_mode: str
    location_stable_key: str
    targets: list[WorkflowTarget]
    reward_container_stable_key: str | None = None
    reset_evidence: str = "targets_defeated"


@dataclass(slots=True)
class BackgroundSource:
    """Non-local item sources that do not contribute to obtainability levels."""

    type: str
    name: str
    chance: float | None
    level: int | None = None
    level_max: int | None = None
    chance_max: float | None = None
    source_key: str | None = None
    instruction: str | None = None
    provenance_key: str | None = None


# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """A node in the entity graph.

    Every field beyond key/type/display_name is optional and type-specific.
    Non-None fields are compiled into the guide binary; the C# Node class
    exposes them as typed nullable fields.
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
    step_note: str | None = None
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
    # Item.Id in the game, which the keyring stores.
    game_id: str | None = None
    stackable: bool = False
    is_unique: bool = False
    template: bool = False  # crafting recipe template item
    background_sources: list[BackgroundSource] = field(default_factory=list)
    obtainability_level: int | None = None

    # Character-specific
    is_vendor: bool = False
    is_friendly: bool = False
    invulnerable: bool = False
    faction_key: str | None = None
    # The clean database's npc, chest, boss, elite or enemy classification. A
    # chest is a TreasureChest-faction container: its level of 1 is no combat
    # level, so reaching it means reaching its zone.
    encounter_tier: str | None = None
    # Level of reaching the character: its zone's level raised by what
    # unlocks it. Talking to, trading with or turning in to a character uses
    # it; ``level`` stays its combat level for kills and drops.
    place_level: int | None = None

    # Spawn point specific
    spawn_chance: float | None = None
    is_rare: bool = False
    is_directly_placed: bool = False
    source_script: str | None = None
    is_trigger_spawn: bool = False
    respawn_delay: float | None = None
    furniture_item_key: str | None = None
    furniture_slot: str | None = None

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
    refname: str | None = None

    # Zone line specific
    destination_zone_key: str | None = None
    destination_display: str | None = None
    landing_x: float | None = None
    landing_y: float | None = None
    landing_z: float | None = None
    # Guide-only synthetic workflows and trigger locations
    guide_only: bool = False
    workflow_cycle: WorkflowCycle | None = None
    trigger_bounds_center_x: float | None = None
    trigger_bounds_center_y: float | None = None
    trigger_bounds_center_z: float | None = None
    trigger_bounds_extents_x: float | None = None
    trigger_bounds_extents_y: float | None = None
    trigger_bounds_extents_z: float | None = None


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
    # Fishing percentages per successful catch, not per cast.
    day_chance: float | None = None
    night_chance: float | None = None
    provenance_key: str | None = None
