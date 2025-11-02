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

from sqlmodel import Column, Field, Index, SQLModel
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
    CHARACTER = "character"  # NPCs and creatures
    QUEST = "quest"
    FACTION = "faction"
    LOCATION = "location"
    ACHIEVEMENT = "achievement"
    CRAFTING_RECIPE = "crafting_recipe"
    LOOT_TABLE = "loot_table"
    DIALOG = "dialog"
    OTHER = "other"  # Catch-all for uncategorized entities


class EntityRecord(SQLModel, table=True):
    """Entity registry table for manual overrides.

    Stores manual overrides for wiki page titles, display names, and image names.
    Only entities with custom mappings are stored in this table.

    The entity_type and resource_name combination must be unique, preventing
    duplicate registrations.

    Indexes:
    - Primary key on id (auto-increment)
    - Unique composite index on (entity_type, resource_name)
    """

    __tablename__ = "entities"

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key",
    )

    entity_type: EntityType = Field(
        sa_column=Column(SQLEnum(EntityType), nullable=False),
        description="Type of game entity (item, spell, character, etc.)",
    )

    resource_name: str = Field(
        index=True,
        max_length=255,
        description="Stable resource identifier from game data (unique within entity_type)",
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

    __table_args__ = (
        Index(
            "ix_entity_type_resource_name",
            "entity_type",
            "resource_name",
            unique=True,
        ),
    )


class ConflictRecord(SQLModel, table=True):
    """Conflict tracking table for name collisions requiring resolution.

    Detects and tracks situations where multiple entities share the same name
    or identifier, requiring manual or automated resolution. Common conflict types:

    - name_collision: Multiple entities with identical display names
    - ambiguous_reference: Unclear which entity a wiki reference points to
    - duplicate_resource_name: Same resource_name with different entity_types

    The entity_ids field stores a JSON array of entity IDs involved in the
    conflict. Resolution workflow:
    1. Conflict detected and recorded with resolved=False
    2. Manual or automated resolution chooses one entity
    3. resolution_entity_id set to chosen entity
    4. resolved=True and resolved_at timestamp recorded

    Indexes:
    - Primary key on id (auto-increment)
    - Index on resolved for filtering unresolved conflicts
    - Foreign key on resolution_entity_id referencing entities table
    """

    __tablename__ = "conflicts"

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key",
    )

    entity_ids: str = Field(
        max_length=1000,
        description="JSON array of entity IDs involved in conflict (e.g., '[1, 2, 3]')",
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

    resolution_entity_id: int | None = Field(
        default=None,
        foreign_key="entities.id",
        description="ID of chosen entity if conflict is resolved (references entities.id)",
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
