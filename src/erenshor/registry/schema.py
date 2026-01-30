"""Registry database schema definitions using SQLModel.

This module defines the database schema for the entity registry system.
The registry stores manual overrides for wiki page titles, display names, and
image names. These overrides are loaded from mapping.json during initial setup.

The registry provides:
- Manual override storage (wiki page title, display name, image name)
- Conflict detection for display_name collisions

Database Tables:
- entities: Manual overrides for wiki page titles, display names, and image names

Entity resolution:
- page_title: Use override if present, else fall back to entity name
- display_name: Use override if present, else fall back to entity name
- image_name: Use override if present, else fall back to entity name
"""

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
    STANCE = "stance"
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
