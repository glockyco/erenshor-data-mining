"""Registry database schema definitions using SQLModel.

This module defines the database schema for the entity registry system.
The registry stores manual overrides for wiki page titles, display names, and
image names. These overrides are loaded from mapping.json during initial setup.

The registry provides:
- Manual override storage (wiki page title, display name, image name)
- Conflict detection and resolution for name collisions

Database Tables:
- entities: Manual overrides for wiki page titles, display names, and image names
- conflicts: Detection and resolution of name collisions and ambiguous references

Entity resolution:
- page_title: Use override if present, else fall back to entity name
- display_name: Use override if present, else fall back to entity name
- image_name: Use override if present, else fall back to entity name
"""

from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlmodel import Column, Field, SQLModel
from sqlmodel import Enum as SQLEnum


class EntityType(str, PyEnum):
    """Game entity types tracked by the registry.

    Each entity type represents a distinct category of game data that requires
    tracking across versions. The resource_name format varies by type but must
    be stable and unique within each type.

    Common resource name patterns:
    - Items: Internal name from game data (e.g., "SwordOfFlames")
    - Spells: Spell identifier (e.g., "Fireball")
    - Characters: NPC/creature name (e.g., "GoblinWarrior")
    - Quests: Quest identifier (e.g., "MainQuest_01")
    - Locations: Zone or area name (e.g., "Elderwood")
    """

    ITEM = "item"
    SPELL = "spell"
    SKILL = "skill"
    CHARACTER = "character"
    QUEST = "quest"
    FACTION = "faction"
    ZONE = "zone"


class EntityRecord(SQLModel, table=True):
    """Entity registry table for manual overrides.

    Stores manual overrides for wiki page titles, display names, and image names.
    Uses stable_key as the primary key (format: "entity_type:resource_name").

    The stable_key directly matches the StableKey column from the game database,
    ensuring consistency across the entire system. The entity_type is stored
    separately for efficient querying by type.
    """

    __tablename__ = "entities"

    stable_key: str = Field(
        primary_key=True,
        max_length=255,
        description="Stable key from game database (format: 'entity_type:resource_name')",
    )

    entity_type: EntityType = Field(
        sa_column=Column(SQLEnum(EntityType), nullable=False, index=True),
        description="Type of game entity (item, spell, character, etc.) - extracted from stable_key",
    )

    page_title: str | None = Field(
        default=None,
        max_length=255,
        description="Custom wiki page title override (null = use entity name)",
    )

    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Custom display name override (null = use entity name)",
    )

    image_name: str | None = Field(
        default=None,
        max_length=255,
        description="Custom image filename override (null = use entity name)",
    )

    excluded: bool = Field(
        default=False,
        description="True if entity should be excluded from wiki (mapping.json has null wiki_page_name)",
    )


class ConflictRecord(SQLModel, table=True):
    """Conflict tracking table for name collisions requiring resolution.

    Detects and tracks situations where multiple entities share the same name
    or identifier, requiring manual or automated resolution. Common conflict types:

    - name_collision: Multiple entities with identical display names
    - ambiguous_reference: Unclear which entity a wiki reference points to
    - duplicate_resource_name: Same resource_name with different entity_types

    The entity_stable_keys field stores a JSON array of entity stable keys involved
    in the conflict. Resolution workflow:
    1. Conflict detected and recorded with resolved=False
    2. Manual or automated resolution chooses one entity
    3. resolution_stable_key set to chosen entity's stable key
    4. resolved=True and resolved_at timestamp recorded

    Indexes:
    - Primary key on id (auto-increment)
    - Index on resolved for filtering unresolved conflicts
    - Foreign key on resolution_stable_key referencing entities.stable_key
    """

    __tablename__ = "conflicts"

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key",
    )

    entity_stable_keys: str = Field(
        max_length=1000,
        description='JSON array of entity stable keys involved in conflict (e.g., \'["item:sword", "item:blade"]\')',
    )

    conflict_type: str = Field(
        max_length=50,
        description="Type of conflict: 'name_collision', 'ambiguous_reference', or 'duplicate_resource_name'",
    )

    resolved: bool = Field(
        default=False,
        index=True,
        description="True if conflict has been resolved",
    )

    resolution_stable_key: str | None = Field(
        default=None,
        foreign_key="entities.stable_key",
        description="Stable key of chosen entity if conflict is resolved (references entities.stable_key)",
    )

    resolution_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Notes explaining how conflict was resolved",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when conflict was first detected",
    )

    resolved_at: datetime | None = Field(
        default=None,
        description="Timestamp when conflict was resolved (null if unresolved)",
    )
