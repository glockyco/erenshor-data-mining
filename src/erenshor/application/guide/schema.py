"""Quest guide data schema (v3).

These dataclasses define the quest guide JSON structure consumed by both
the BepInEx mod (at runtime) and the manual curation layer (at author time).

Design principles:
- All obtainability data lives in a single polymorphic ItemSource type.
  Each source carries its own level inline. No parallel factor lists.
- Sources are sorted by level ascending (easiest first) after level
  estimation, and pre-aggregated to zone granularity (mining/fishing/pickup).
- Prerequisites are structured data with stable keys, not opaque strings.
- Optional fields are None when absent. Present fields are always
  serialized, including zero and false values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class QuestType(str, Enum):
    """How the quest is primarily completed. Drives step auto-generation."""

    FETCH = "fetch"  # Has required items + item turn-in
    KILL = "kill"  # QuestCompleteOnDeath
    DIALOG = "dialog"  # QuestToComplete on NPCDialog
    ZONE_TRIGGER = "zone_trigger"  # CompleteQuestOnEnter
    SHOUT = "shout"  # NPCShoutListener.TriggerQuest
    ITEM_READ = "item_read"  # CompleteOnRead
    UNKNOWN = "unknown"  # No completion data or mechanism known yet
    CHAIN = "chain"  # Only completed via CompleteOtherQuests
    HYBRID = "hybrid"  # Multiple completion methods


class StepAction(str, Enum):
    """What the player does in a quest step."""

    TALK = "talk"
    KILL = "kill"
    COLLECT = "collect"
    TRAVEL = "travel"
    USE_ITEM = "use_item"
    SHOUT = "shout"
    TURN_IN = "turn_in"
    READ = "read"
    COMPLETE_QUEST = "complete_quest"
    CUSTOM = "custom"


class AcceptanceMode(str, Enum):
    """How a quest enters the player's quest log."""

    EXPLICIT = "explicit"  # Requires dialog, item read, zone entry, etc.
    IMPLICIT = "implicit"  # Always completable, no formal acceptance


class AcquisitionMethod(str, Enum):
    """How a player obtains a quest."""

    DIALOG = "dialog"
    ITEM_READ = "item_read"
    ZONE_ENTRY = "zone_entry"
    QUEST_CHAIN = "quest_chain"
    PARTIAL_TURNIN = "partial_turnin"
    SCRIPTED = "scripted"


class CompletionMethod(str, Enum):
    """How a player completes a quest."""

    ITEM_TURNIN = "item_turnin"
    TALK = "talk"
    ZONE = "zone"
    READ = "read"
    SHOUT = "shout"
    DEATH = "death"
    SCRIPTED = "scripted"
    CHAIN = "chain"


# ---------------------------------------------------------------------------
# Obtainability
# ---------------------------------------------------------------------------


@dataclass
class ItemSource:
    """A single way to obtain an item, with inline level and count data.

    Replaces the v2 DropSource, VendorSource, FishingSource, MiningSource,
    BagSource, CraftingSource, and QuestRewardSource types. Each source
    carries its own level so the UI doesn't need to join against a separate
    factor list.

    Sources are sorted by level ascending (easiest first) after level
    estimation. Zone-level sources (mining, fishing, pickup) are
    pre-aggregated per zone.

    ``children`` is populated for quest_reward (rewarding quest's required-item
    sources) and crafting (mold sources + ingredient entries) to provide one
    level of acquisition sub-tree expansion.
    """

    type: str  # "drop", "vendor", "fishing", "mining", "pickup", "crafting", "quest_reward", "dialog_give"
    name: str | None = None  # entity name (enemy, vendor, recipe item, quest name)
    zone: str | None = None  # zone display name
    scene: str | None = None  # scene name for spawn lookup (e.g., "Rockshade")
    level: int | None = None  # recommended level to use this source
    source_key: str | None = (
        None  # character stable_key, mining-nodes:{scene}, pickup-nodes:{item_key}:{scene}, or forge:{scene}
    )
    quest_key: str | None = None  # for quest_reward: rewarding quest's stable_key
    node_count: int | None = None  # for mining/fishing/pickup: nodes per zone
    spawn_count: int | None = None  # for drop: enemy spawn points in this zone
    recipe_key: str | None = None  # for crafting: recipe item stable_key
    children: list[ItemSource] = field(default_factory=list)


@dataclass
class RequiredItemInfo:
    """A required item with quantity and unified obtainability sources.

    When ``or_group`` is set, this item is one of several alternatives
    sharing the same group name (e.g. multiple item_read triggers).
    The player only needs one item from the group, not all of them.
    ``or_group = None`` means the item is mandatory.
    """

    item_name: str
    item_stable_key: str
    quantity: int = 1
    or_group: str | None = None
    sources: list[ItemSource] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Quest structure
# ---------------------------------------------------------------------------


@dataclass
class QuestStep:
    """A single step in the quest walkthrough.

    When ``or_group`` is set, this step is one of several alternatives
    sharing the same group name. The player only needs to complete one
    step from each group. ``or_group = None`` means the step is mandatory.
    """

    order: int
    action: str  # StepAction value
    description: str
    target_name: str | None = None  # NPC/item/zone name
    target_type: str | None = None  # "character", "item", "zone"
    target_key: str | None = None  # stable key for spawn/entity lookup
    quantity: int | None = None  # for collect/kill steps
    zone_name: str | None = None  # where this step happens
    keyword: str | None = None  # for talk/shout steps requiring a specific phrase
    or_group: str | None = None
    tips: list[str] = field(default_factory=list)
    level_estimate: LevelEstimate | None = None


@dataclass
class AcquisitionSource:
    """How the player obtains this quest."""

    method: str  # AcquisitionMethod value
    source_name: str | None = None
    source_type: str | None = None  # "character", "item", "zone", "quest"
    source_stable_key: str | None = None
    zone_name: str | None = None
    keyword: str | None = None  # dialog keyword to say to the NPC
    note: str | None = None


@dataclass
class CompletionSource:
    """How the player completes this quest."""

    method: str  # CompletionMethod value
    source_name: str | None = None
    source_type: str | None = None
    source_stable_key: str | None = None
    zone_name: str | None = None
    keyword: str | None = None
    note: str | None = None


@dataclass
class Prerequisite:
    """A quest that must be completed before this one.

    Covers both explicit prerequisites from the game data and implicit
    prerequisites detected from item dependencies (when a required item
    is obtainable ONLY as a reward from another quest).
    """

    type: str = "quest"  # currently always "quest"; extensible for future types
    quest_key: str = ""  # stable_key of the prerequisite quest
    quest_name: str = ""  # display name for rendering
    item: str | None = None  # connecting item name (for implicit prerequisites)
    note: str | None = None  # explanation (for character unlock prerequisites)


@dataclass
class UnlockedZoneLine:
    """A zone transition unlocked by completing this quest."""

    from_zone: str = ""
    to_zone: str = ""
    co_requirements: list[str] = field(default_factory=list)  # other quest names needed


@dataclass
class UnlockedCharacter:
    """An NPC that spawns when this quest is completed."""

    name: str = ""
    zone: str | None = None


@dataclass
class VendorUnlockInfo:
    """An item unlocked for vendor purchase on quest completion."""

    item_name: str = ""
    vendor_name: str = ""


@dataclass
class Rewards:
    """Quest completion rewards."""

    xp: int = 0
    gold: int = 0
    item_name: str | None = None
    item_stable_key: str | None = None
    next_quest_name: str | None = None
    next_quest_stable_key: str | None = None
    also_completes: list[str] = field(default_factory=list)
    vendor_unlock: VendorUnlockInfo | None = None
    unlocked_zone_lines: list[UnlockedZoneLine] = field(default_factory=list)
    unlocked_characters: list[UnlockedCharacter] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    faction_effects: list[FactionEffect] = field(default_factory=list)


@dataclass
class FactionEffect:
    """Faction reputation change on quest completion."""

    faction_name: str = ""
    faction_stable_key: str = ""
    amount: int = 0


@dataclass
class ChainLink:
    """A link in a quest chain."""

    quest_name: str = ""
    quest_stable_key: str = ""
    relationship: str = ""  # "previous", "next", "also_completes", "completed_by"


@dataclass
class QuestFlags:
    """Behavioral flags that affect gameplay."""

    repeatable: bool = False
    disabled: bool = False
    disabled_text: str | None = None
    kill_turn_in_holder: bool = False
    destroy_turn_in_holder: bool = False
    drop_invuln_on_holder: bool = False
    once_per_spawn_instance: bool = False


# ---------------------------------------------------------------------------
# Level estimation
# ---------------------------------------------------------------------------


@dataclass
class LevelFactor:
    """A contributing factor to a level estimate.

    For non-collect steps (talk, travel, shout, turn_in): the zone median.
    For quest-level estimates: the driving step reference.
    Not used for collect/read steps — their levels come from ItemSource.level.
    """

    source: str  # e.g. "zone_median", "step_3"
    name: str | None = None
    level: int = 0


@dataclass
class LevelEstimate:
    """Recommended level for a quest or step.

    For steps: min(source.level) for collect/read, zone median for others.
    For quests: max(step.level) across all steps.
    """

    recommended: int | None = None
    factors: list[LevelFactor] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------


@dataclass
class SpawnPoint:
    """A character spawn location."""

    scene: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    night_spawn: bool = False


@dataclass
class ZoneInfo:
    """Zone metadata for the lookup table."""

    display_name: str = ""
    stable_key: str = ""
    level_min: int | None = None
    level_max: int | None = None
    level_median: int | None = None


@dataclass
class ZoneLine:
    """A zone transition point."""

    scene: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    is_enabled: bool = True
    destination_zone_key: str = ""
    destination_display: str = ""
    landing_x: float | None = None
    landing_y: float | None = None
    landing_z: float | None = None
    required_quest_groups: list[list[str]] = field(default_factory=list)


@dataclass
class ChainGroup:
    """A pre-computed quest chain."""

    name: str = ""
    quests: list[str] = field(default_factory=list)  # ordered db_names


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


@dataclass
class QuestGuide:
    """Complete guide entry for a single quest."""

    # Identity — always present
    db_name: str = ""
    stable_key: str = ""
    display_name: str = ""
    description: str | None = None

    # Classification — inferred
    quest_type: str | None = None  # QuestType value
    acceptance: str | None = None  # AcceptanceMode value
    zone_context: str | None = None  # primary zone, inferred from NPC locations

    # Structured data
    acquisition: list[AcquisitionSource] = field(default_factory=list)
    prerequisites: list[Prerequisite] = field(default_factory=list)
    steps: list[QuestStep] = field(default_factory=list)
    required_items: list[RequiredItemInfo] = field(default_factory=list)
    completion: list[CompletionSource] = field(default_factory=list)
    rewards: Rewards = field(default_factory=Rewards)
    chain: list[ChainLink] = field(default_factory=list)
    flags: QuestFlags = field(default_factory=QuestFlags)
    level_estimate: LevelEstimate | None = None

    # Manual curation fields
    difficulty: str | None = None  # trivial|easy|moderate|hard|epic
    estimated_time: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class GuideOutput:
    """Complete guide output with lookup tables and quest entries."""

    version: int = 5
    zone_lookup: dict[str, ZoneInfo] = field(default_factory=dict)
    character_spawns: dict[str, list[SpawnPoint]] = field(default_factory=dict)
    zone_lines: list[ZoneLine] = field(default_factory=list)
    chain_groups: list[ChainGroup] = field(default_factory=list)
    character_quest_unlocks: dict[str, list[list[str]]] = field(default_factory=dict)
    quests: list[QuestGuide] = field(default_factory=list)
