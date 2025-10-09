"""Core registry classes for wiki page and entity management."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, cast

from erenshor.domain.entities.page import EntityRef, WikiPage
from erenshor.domain.value_objects.entity_type import EntityType

__all__ = [
    "WikiRegistry",
    # Re-exports from domain layer
    "EntityRef",
    "EntityType",
    "WikiPage",
]


class WikiRegistry:
    """Central registry for all wiki page and entity mappings."""

    def __init__(self, registry_dir: Path):
        """Initialize registry with given directory."""
        self.registry_dir = registry_dir
        self.registry_file = registry_dir / "registry.json"
        self.pages_dir = registry_dir / "pages"

        # Core data structures
        self.pages: Dict[str, WikiPage] = {}  # title -> WikiPage
        self.by_entity: Dict[str, WikiPage] = {}  # entity.uid -> WikiPage
        self.by_page_id: Dict[str, WikiPage] = {}  # page_id -> WikiPage

        # Manual mappings from mapping.json
        self.manual_mappings: Dict[str, str] = {}  # entity.stable_key -> page_title
        self.display_name_overrides: Dict[str, str] = {}  # entity.uid -> display_name
        self.image_name_overrides: Dict[str, str] = {}  # entity.uid -> image_name

        # Metadata
        self.next_page_id: int = 1
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    def load(self) -> None:
        """Load registry from disk."""
        if not self.registry_file.exists():
            return

        data = json.loads(self.registry_file.read_text())

        for page_data in data.get("pages", []):
            page = self._page_from_dict(page_data)
            self.pages[page.title] = page
            self.by_page_id[page.page_id] = page

            for entity_data in page_data.get("entities", []):
                entity = self._entity_from_dict(entity_data)
                self.by_entity[entity.uid] = page

        self.next_page_id = data.get("next_page_id", 1)
        self.manual_mappings = data.get("manual_mappings", {})
        self.display_name_overrides = data.get("display_name_overrides", {})
        self.image_name_overrides = data.get("image_name_overrides", {})
        self.created_at = (
            datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None
        )
        self.updated_at = (
            datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None
        )

    def save(self) -> None:
        """Save registry to disk."""
        from datetime import timezone

        self.registry_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "2.0",
            "created_at": self.created_at.isoformat()
            if self.created_at
            else datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "next_page_id": self.next_page_id,
            "manual_mappings": self.manual_mappings,
            "display_name_overrides": self.display_name_overrides,
            "image_name_overrides": self.image_name_overrides,
            "pages": [self._page_to_dict(p) for p in self.pages.values()],
        }

        # Atomic write via temp file
        temp = self.registry_file.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2))
        temp.replace(self.registry_file)

    def register_entity(
        self, entity: EntityRef, page_title: str, create_if_missing: bool = True
    ) -> WikiPage:
        """Register an entity to a wiki page."""
        existing = self.by_entity.get(entity.uid)
        if existing and existing.title != page_title:
            raise ValueError(f"Entity {entity.uid} already mapped to {existing.title}")

        page = self.pages.get(page_title)
        if not page:
            if not create_if_missing:
                raise ValueError(f"Page '{page_title}' not found")
            page = self.create_page(page_title)

        page.add_entity(entity)
        self.by_entity[entity.uid] = page

        return page

    def resolve_entity(self, entity: EntityRef) -> Optional[WikiPage]:
        """Find wiki page for an entity, checking manual mappings first."""
        manual_title = self.manual_mappings.get(entity.stable_key)
        if manual_title:
            return self.pages.get(manual_title)

        return self.by_entity.get(entity.uid)

    def get_page_by_title(self, title: str) -> Optional[WikiPage]:
        """Get page by exact title."""
        return self.pages.get(title)

    def get_page_by_id(self, page_id: str) -> Optional[WikiPage]:
        """Get page by ID."""
        return self.by_page_id.get(page_id)

    def create_page(self, title: str) -> WikiPage:
        """Create new wiki page with generated ID."""
        if title in self.pages:
            return self.pages[title]

        page_id = f"{self.next_page_id:07d}"
        self.next_page_id += 1

        page = WikiPage(title=title, page_id=page_id)
        self.pages[title] = page
        self.by_page_id[page_id] = page

        return page

    def get_or_create_page(self, title: str) -> WikiPage:
        """Get existing page or create new one."""
        return self.pages.get(title) or self.create_page(title)

    def list_pages(self) -> List[WikiPage]:
        """List all registered pages."""
        return list(self.pages.values())

    def list_pages_by_entity_type(self, entity_type: EntityType) -> List[WikiPage]:
        """List pages that contain entities of the specified type.

        Args:
            entity_type: The type of entity to filter by

        Returns:
            List of WikiPage objects containing at least one entity of the specified type
        """
        filtered_pages = []
        for page in self.pages.values():
            if any(entity.entity_type == entity_type for entity in page.entities):
                filtered_pages.append(page)
        return filtered_pages

    def list_entities_for_page(self, page_title: str) -> List[EntityRef]:
        """Get all entities mapped to a page."""
        page = self.pages.get(page_title)
        return page.entities if page else []

    def set_manual_mapping(self, entity_key: str, page_title: str) -> None:
        """Set a manual entity->page mapping."""
        self.manual_mappings[entity_key] = page_title

    def get_display_name(self, entity: EntityRef) -> str:
        """Get display name for entity (override if present, otherwise db_name)."""
        return self.display_name_overrides.get(entity.uid, entity.db_name)

    def set_display_name_override(self, entity_uid: str, display_name: str) -> None:
        """Set display name override for an entity."""
        self.display_name_overrides[entity_uid] = display_name

    def get_image_name(self, entity: EntityRef) -> str:
        """Get image name with fallback: image_name → display_name → page_title → db_name.

        MediaWiki accepts raw special characters in [[File:...]] references,
        so no URL encoding is needed. Always returns an explicit name.
        """
        if entity.uid in self.image_name_overrides:
            return self.image_name_overrides[entity.uid]

        if entity.uid in self.display_name_overrides:
            return self.display_name_overrides[entity.uid]

        page = self.resolve_entity(entity)
        if page:
            return page.title

        return entity.db_name

    def set_image_name_override(self, entity_uid: str, image_name: str) -> None:
        """Set image name override for an entity."""
        self.image_name_overrides[entity_uid] = image_name

    def clear_entity_mappings(self) -> None:
        """Clear all entity mappings (for rebuild)."""
        self.by_entity.clear()
        for page in self.pages.values():
            page.entities.clear()

    def remove_orphaned_pages(self) -> int:
        """Remove pages with no entities, return count removed."""
        orphaned_titles = [
            page.title for page in self.pages.values() if not page.entities
        ]

        for title in orphaned_titles:
            page = self.pages.pop(title)
            self.by_page_id.pop(page.page_id, None)

        return len(orphaned_titles)

    # Helper methods for serialization
    def _page_to_dict(self, page: WikiPage) -> dict[str, object]:
        """Convert page to JSON-serializable dict."""
        return {
            "title": page.title,
            "page_id": page.page_id,
            "namespace": page.namespace,
            "entities": [self._entity_to_dict(e) for e in page.entities],
            "last_fetched": page.last_fetched.isoformat()
            if page.last_fetched
            else None,
            "last_updated": page.last_updated.isoformat()
            if page.last_updated
            else None,
            "last_pushed": page.last_pushed.isoformat() if page.last_pushed else None,
            "original_content_hash": page.original_content_hash,
            "updated_content_hash": page.updated_content_hash,
        }

    def _page_from_dict(self, data: dict[str, object]) -> WikiPage:
        """Reconstruct page from dict."""
        page = WikiPage(
            title=cast(str, data["title"]),
            page_id=cast(str, data["page_id"]),
            namespace=cast(int, data.get("namespace", 0)),
        )
        if data.get("last_fetched"):
            page.last_fetched = datetime.fromisoformat(cast(str, data["last_fetched"]))
        if data.get("last_updated"):
            page.last_updated = datetime.fromisoformat(cast(str, data["last_updated"]))
        if data.get("last_pushed"):
            page.last_pushed = datetime.fromisoformat(cast(str, data["last_pushed"]))
        page.original_content_hash = cast(
            Optional[str], data.get("original_content_hash")
        )
        page.updated_content_hash = cast(
            Optional[str], data.get("updated_content_hash")
        )

        # Registry v1 used 'content_hash', v2 split into original/updated hashes
        if data.get("content_hash") and not page.updated_content_hash:
            page.updated_content_hash = cast(Optional[str], data.get("content_hash"))

        # Load entities
        entities_list = cast(list[dict[str, object]], data.get("entities", []))
        for entity_data in entities_list:
            entity = self._entity_from_dict(entity_data)
            page.add_entity(entity)

        return page

    def _entity_to_dict(self, entity: EntityRef) -> dict[str, object]:
        """Convert entity to JSON-serializable dict."""
        return {
            "type": entity.entity_type.value,
            "db_id": entity.db_id,
            "db_name": entity.db_name,
            "resource_name": entity.resource_name,
        }

    def _entity_from_dict(self, data: dict[str, object]) -> EntityRef:
        """Reconstruct entity from dict.

        Preserves SPELL and SKILL types from registry. Legacy "ability" types
        cannot be reliably migrated (no way to know if it was a spell or skill),
        so they remain as ABILITY type for backward compatibility.
        """
        type_value = cast(str, data["type"])

        return EntityRef(
            entity_type=EntityType(type_value),
            db_id=cast(Optional[str], data.get("db_id")),
            db_name=cast(str, data["db_name"]),
            resource_name=cast(Optional[str], data.get("resource_name")),
        )
