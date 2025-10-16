"""Wiki page and entity reference domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from erenshor.domain.value_objects.entity_type import EntityType

__all__ = ["EntityRef", "WikiPage"]


@dataclass(frozen=True)
class EntityRef:
    """Immutable reference to a database entity or system page."""

    entity_type: EntityType
    db_id: Optional[str]  # Items.Id, Characters.Guid, etc. None for system pages
    db_name: str  # Display name from DB or system page name
    resource_name: Optional[str] = None  # For Items.ResourceName, Spells.ResourceName

    @property
    def uid(self) -> str:
        """Unique identifier within current DB version."""
        if self.db_id is not None:
            return f"{self.entity_type.value}:{self.db_id}"
        return f"{self.entity_type.value}:{self.db_name}"

    @property
    def stable_key(self) -> str:
        """Key for manual mappings (uses resource_name when available)."""
        if self.resource_name:
            return f"{self.entity_type.value}:{self.resource_name}"
        return f"{self.entity_type.value}:{self.db_name}"

    @classmethod
    def from_item(cls, item: Any) -> "EntityRef":
        """Create from database item."""
        return cls(
            entity_type=EntityType.ITEM,
            db_id=item.Id,
            db_name=item.ItemName,
            resource_name=item.ResourceName,
        )

    @classmethod
    def from_character(cls, char: Any) -> "EntityRef":
        """Create from database character.

        Uses char.Guid as the stable identifier (never Id).
        All characters in the database have a non-null Guid.
        """
        # Distinguish between prefab and non-prefab characters
        if char.IsPrefab and char.ObjectName:
            # Prefab characters use ObjectName only
            resource_name = char.ObjectName
        else:
            # Non-prefab characters use composite key with coordinates
            x = char.X or 0.0
            y = char.Y or 0.0
            z = char.Z or 0.0
            scene = char.Scene or "Unknown"
            resource_name = f"{char.ObjectName}|{scene}|{x:.2f}|{y:.2f}|{z:.2f}"

        return cls(
            entity_type=EntityType.CHARACTER,
            db_id=char.Guid,
            db_name=char.NPCName,
            resource_name=resource_name,
        )

    @classmethod
    def from_spell(cls, spell: Any) -> "EntityRef":
        """Create from database spell.

        Uses EntityType.SPELL (not ABILITY) to maintain backend type distinction.
        Registry layer maps this to unified "ability" wiki namespace.
        """
        return cls(
            entity_type=EntityType.SPELL,
            db_id=spell.Id,
            db_name=spell.SpellName,
            resource_name=spell.ResourceName,
        )

    @classmethod
    def from_skill(cls, skill: Any) -> "EntityRef":
        """Create from database skill.

        Uses EntityType.SKILL (not ABILITY) to maintain backend type distinction.
        Registry layer maps this to unified "ability" wiki namespace.
        """
        return cls(
            entity_type=EntityType.SKILL,
            db_id=skill.Id,
            db_name=skill.SkillName,
            resource_name=skill.ResourceName,
        )


@dataclass
class WikiPage:
    """Represents a wiki page with metadata."""

    title: str  # Exact wiki page title
    page_id: str  # Stable ID like "0001234"
    namespace: int = 0  # MediaWiki namespace (0=main)
    entities: List[EntityRef] = field(default_factory=list)
    last_fetched: Optional[datetime] = None  # When fetched from wiki
    last_updated: Optional[datetime] = None  # When modified locally
    last_pushed: Optional[datetime] = None  # When uploaded to wiki
    original_content_hash: Optional[str] = None  # Hash of original wiki content
    updated_content_hash: Optional[str] = None  # Hash of current local content

    @property
    def safe_filename(self) -> str:
        """Generate filesystem-safe filename."""
        import urllib.parse

        # URL-encode problematic characters
        safe_title = urllib.parse.quote(self.title, safe=" ()[]")
        # Replace forward slashes to avoid directory issues
        safe_title = safe_title.replace("/", "_")
        return f"{self.page_id}_{safe_title}.txt"

    def add_entity(self, entity: EntityRef) -> None:
        """Add an entity mapping to this page."""
        if entity not in self.entities:
            self.entities.append(entity)

    def remove_entity(self, entity: EntityRef) -> None:
        """Remove an entity mapping from this page."""
        if entity in self.entities:
            self.entities.remove(entity)

    def needs_upload(self) -> bool:
        """Check if page has changes that need uploading."""
        # Skip if no content hash (not safe to upload)
        if not self.updated_content_hash:
            return False

        # Never uploaded
        if self.last_pushed is None:
            return True

        # Local changes since last upload
        if (
            self.last_updated
            and self.last_pushed
            and self.last_updated > self.last_pushed
        ):
            return True

        # Content differs from original wiki content
        if (
            self.original_content_hash
            and self.original_content_hash != self.updated_content_hash
        ):
            return True

        # No original hash - can't verify wiki state, need to check
        if not self.original_content_hash:
            return True

        return False

    def is_locally_modified(self) -> bool:
        """Check if page has been modified locally since last fetch."""
        if not self.original_content_hash or not self.updated_content_hash:
            return False
        return self.original_content_hash != self.updated_content_hash

    def upload_status(self) -> str:
        """Get human-readable upload status."""
        if not self.updated_content_hash:
            return "no content hash"

        if self.last_pushed is None:
            return "never uploaded"

        if (
            self.last_updated
            and self.last_pushed
            and self.last_updated > self.last_pushed
        ):
            return "local changes pending"

        if self.is_locally_modified():
            return "modified from original"

        return "up to date"
