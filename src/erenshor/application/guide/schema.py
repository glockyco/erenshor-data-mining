"""Quest guide data schema.

These dataclasses define the quest guide JSON structure consumed by both
the BepInEx mod (at runtime) and the manual curation layer (at author time).

Design principles:
- No provenance tracking in the output schema. Provenance is a pipeline
  concern handled by the merge algorithm, not a runtime concern.
- All fields nullable except identity fields. A null field means "no data
  available" and the mod renders it accordingly.
- Flat where possible. Nesting is reserved for genuinely composite data
  (steps, drop sources) not for categorization.
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
    SCRIPTED = "scripted"  # Hardcoded in C# event scripts
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
    CUSTOM = "custom"


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
# Sub-schemas
# ---------------------------------------------------------------------------


@dataclass
class QuestStep:
    """A single step in the quest walkthrough."""

    order: int
    action: str  # StepAction value
    description: str
    target_name: str | None = None  # NPC/item/zone name
    target_type: str | None = None  # "character", "item", "zone"
    quantity: int | None = None  # for collect/kill steps
    zone_name: str | None = None  # where this step happens
    keyword: str | None = None  # for shout steps
    tips: list[str] = field(default_factory=list)


@dataclass
class DropSource:
    """Where a required item drops."""

    character_name: str
    character_stable_key: str
    zone_name: str | None = None


@dataclass
class VendorSource:
    """Where a required item can be purchased."""

    character_name: str
    character_stable_key: str
    zone_name: str | None = None
    requires_quest: str | None = None  # quest that unlocks this vendor stock


@dataclass
class RequiredItemInfo:
    """A required item with quantity and known sources."""

    item_name: str
    item_stable_key: str
    quantity: int
    drop_sources: list[DropSource] = field(default_factory=list)
    vendor_sources: list[VendorSource] = field(default_factory=list)


@dataclass
class AcquisitionSource:
    """How the player obtains this quest."""

    method: str  # AcquisitionMethod value
    source_name: str | None = None
    source_type: str | None = None  # "character", "item", "zone", "quest"
    source_stable_key: str | None = None
    zone_name: str | None = None
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
class Rewards:
    """Quest completion rewards."""

    xp: int = 0
    gold: int = 0
    item_name: str | None = None
    item_stable_key: str | None = None
    next_quest_name: str | None = None
    next_quest_stable_key: str | None = None
    also_completes: list[str] = field(default_factory=list)  # quest display names
    vendor_unlock_item: str | None = None
    achievements: list[str] = field(default_factory=list)
    faction_effects: list[FactionEffect] = field(default_factory=list)


@dataclass
class FactionEffect:
    """Faction reputation change on quest completion."""

    faction_name: str
    faction_stable_key: str
    amount: int


@dataclass
class ChainLink:
    """A link in a quest chain."""

    quest_name: str
    quest_stable_key: str
    relationship: str  # "previous", "next", "also_completes", "completed_by"


@dataclass
class QuestFlags:
    """Behavioral flags that affect gameplay. Surfaced in the guide as warnings."""

    repeatable: bool = False
    disabled: bool = False
    disabled_text: str | None = None
    kill_turn_in_holder: bool = False
    destroy_turn_in_holder: bool = False
    drop_invuln_on_holder: bool = False
    once_per_spawn_instance: bool = False


# ---------------------------------------------------------------------------
# Top-level quest guide entry
# ---------------------------------------------------------------------------


@dataclass
class QuestGuide:
    """Complete guide entry for a single quest.

    One of these exists per unique quest DBName. The BepInEx mod loads
    a JSON array of these at startup.
    """

    # Identity -- always present
    db_name: str
    stable_key: str
    display_name: str
    description: str | None = None

    # Classification -- inferred
    quest_type: str | None = None  # QuestType value
    zone_context: str | None = None  # primary zone, inferred from NPC locations

    # Structured data
    acquisition: list[AcquisitionSource] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)  # human-readable strings
    steps: list[QuestStep] = field(default_factory=list)
    required_items: list[RequiredItemInfo] = field(default_factory=list)
    completion: list[CompletionSource] = field(default_factory=list)
    rewards: Rewards = field(default_factory=Rewards)
    chain: list[ChainLink] = field(default_factory=list)
    flags: QuestFlags = field(default_factory=QuestFlags)

    # Manual curation fields -- nullable, only populated from manual layer
    difficulty: str | None = None  # trivial|easy|moderate|hard|epic
    estimated_time: str | None = None
    tags: list[str] = field(default_factory=list)
