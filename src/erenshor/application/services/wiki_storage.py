"""Wiki page storage for local fetch/generate/deploy workflow.

This module provides file-based storage for wiki pages during the three-stage
workflow:
1. Fetch: Download pages from MediaWiki and save to fetched/ directory
2. Generate: Create new pages locally and save to generated/ directory
3. Deploy: Upload pages from generated/ directory to MediaWiki

Files are stored using stable keys (entity_type:resource_name) to maintain
consistency across game versions and avoid issues with special characters or
page title changes.

Directory structure:
    variants/{variant}/wiki/
    ├── fetched/          # Pages fetched from wiki
    │   ├── item:iron_sword.txt
    │   ├── character:rat.txt
    │   └── spell:fireball.txt
    ├── generated/        # Generated pages ready to deploy
    │   ├── item:iron_sword.txt
    │   └── character:rat.txt
    └── metadata.json     # Fetch timestamps, page title mappings

Example:
    >>> from pathlib import Path
    >>> storage = WikiStorage(Path("variants/main/wiki"))
    >>>
    >>> # Save fetched page
    >>> storage.save_fetched("item:iron_sword", "Item:Iron Sword", "{{Item|...}}")
    >>>
    >>> # Read fetched page
    >>> content = storage.read_fetched("item:iron_sword")
    >>>
    >>> # Save generated page
    >>> storage.save_generated("item:iron_sword", "{{Item|...}}")
    >>>
    >>> # List all generated pages
    >>> pages = storage.list_generated()
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from loguru import logger


@dataclass
class PageMetadata:
    """Metadata for a wiki page (supports multi-entity pages).

    A wiki page may contain multiple entities (e.g., spell + skill sharing one page).
    This metadata tracks all entities that contribute to a single page.

    Attributes:
        page_title: MediaWiki page title (e.g., "Lingering Inferno").
        stable_keys: List of stable identifiers contributing to this page
            (e.g., ["spell:lingering_inferno", "skill:lingering_inferno"]).
        entity_names: List of human-readable entity names (parallel to stable_keys).
        fetched_at: ISO timestamp when page was fetched from wiki.
        generated_at: ISO timestamp when page was generated locally.
    """

    page_title: str
    stable_keys: list[str]
    entity_names: list[str]
    fetched_at: str | None = None
    generated_at: str | None = None
    wiki_revision_id: int | None = None  # Latest revision ID from wiki when fetched

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "page_title": self.page_title,
            "stable_keys": self.stable_keys,
            "entity_names": self.entity_names,
            "fetched_at": self.fetched_at,
            "generated_at": self.generated_at,
            "wiki_revision_id": self.wiki_revision_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageMetadata:
        """Create from dictionary after JSON deseriization."""
        return cls(
            page_title=data["page_title"],
            stable_keys=data["stable_keys"],
            entity_names=data["entity_names"],
            fetched_at=data.get("fetched_at"),
            generated_at=data.get("generated_at"),
            wiki_revision_id=data.get("wiki_revision_id"),
        )


class WikiStorage:
    """File-based storage for wiki pages during fetch/generate/deploy workflow.

    This class manages local storage of wiki pages using stable keys as filenames.
    It handles:
    - Fetched pages (downloaded from MediaWiki)
    - Generated pages (created locally, ready to deploy)
    - Metadata (page titles, timestamps)

    Example:
        >>> storage = WikiStorage(Path("variants/main/wiki"))
        >>> storage.save_fetched("item:iron_sword", "Item:Iron Sword", content)
        >>> content = storage.read_fetched("item:iron_sword")
        >>> storage.save_generated("item:iron_sword", new_content)
        >>> pages = storage.list_generated()
    """

    def __init__(self, wiki_dir: Path) -> None:
        """Initialize wiki storage.

        Args:
            wiki_dir: Root directory for wiki storage (e.g., variants/main/wiki).
        """
        self._wiki_dir = wiki_dir
        self._fetched_dir = wiki_dir / "fetched"
        self._generated_dir = wiki_dir / "generated"
        self._metadata_file = wiki_dir / "metadata.json"

        # Create directories if they don't exist
        self._fetched_dir.mkdir(parents=True, exist_ok=True)
        self._generated_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"WikiStorage initialized: {wiki_dir}")

    def _load_metadata(self) -> dict[str, PageMetadata]:
        """Load metadata from JSON file."""
        if not self._metadata_file.exists():
            return {}

        try:
            data = json.loads(self._metadata_file.read_text(encoding="utf-8"))
            return {key: PageMetadata.from_dict(value) for key, value in data.items()}
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load metadata: {e}, returning empty dict")
            return {}

    def _save_metadata(self, metadata: dict[str, PageMetadata]) -> None:
        """Save metadata to JSON file."""
        data = {key: value.to_dict() for key, value in metadata.items()}
        self._metadata_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _encode_page_title_for_filename(self, page_title: str) -> str:
        """Encode page title for safe filesystem storage.

        Uses URL encoding while preserving common readable characters.

        Args:
            page_title: MediaWiki page title

        Returns:
            URL-encoded filename
        """
        return quote(page_title, safe="_-.")

    def save_fetched_by_title(
        self,
        page_title: str,
        stable_keys: list[str],
        content: str,
        entity_names: list[str],
    ) -> None:
        """Save fetched page from MediaWiki.

        Args:
            page_title: MediaWiki page title.
            stable_keys: Stable identifiers for all entities on this page.
            content: Wiki page content (wikitext).
            entity_names: Human-readable names for all entities on this page.
        """
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._fetched_dir / f"{safe_filename}.txt"
        file_path.write_text(content, encoding="utf-8")

        metadata = self._load_metadata()
        metadata[page_title] = PageMetadata(
            page_title=page_title,
            stable_keys=stable_keys,
            entity_names=entity_names,
            fetched_at=datetime.now().isoformat(),
        )
        self._save_metadata(metadata)

        logger.debug(f"Saved fetched page: {page_title} ({len(stable_keys)} entities)")

    def read_fetched_by_title(self, page_title: str) -> str | None:
        """Read fetched page content by title.

        Args:
            page_title: MediaWiki page title.

        Returns:
            Page content if exists, None otherwise.
        """
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._fetched_dir / f"{safe_filename}.txt"
        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def save_generated_by_title(
        self,
        page_title: str,
        stable_keys: list[str],
        content: str,
    ) -> None:
        """Save generated page.

        Args:
            page_title: MediaWiki page title.
            stable_keys: Stable identifiers for all entities on this page.
            content: Generated wiki page content (wikitext).
        """
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._generated_dir / f"{safe_filename}.txt"
        file_path.write_text(content, encoding="utf-8")

        metadata = self._load_metadata()
        if page_title in metadata:
            metadata[page_title].generated_at = datetime.now().isoformat()
        else:
            logger.warning(f"Creating metadata for {page_title} without fetch info")
            entity_names = [sk.split(":", 1)[1].replace("_", " ").title() for sk in stable_keys]
            metadata[page_title] = PageMetadata(
                page_title=page_title,
                stable_keys=stable_keys,
                entity_names=entity_names,
                generated_at=datetime.now().isoformat(),
            )
        self._save_metadata(metadata)

        logger.debug(f"Saved generated page: {page_title} ({len(stable_keys)} entities)")

    def read_generated_by_title(self, page_title: str) -> str | None:
        """Read generated page content by title.

        Args:
            page_title: MediaWiki page title.

        Returns:
            Page content if exists, None otherwise.
        """
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._generated_dir / f"{safe_filename}.txt"
        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def get_metadata_by_title(self, page_title: str) -> PageMetadata | None:
        """Get metadata for a page by title.

        Args:
            page_title: MediaWiki page title.

        Returns:
            PageMetadata if exists, None otherwise.
        """
        metadata = self._load_metadata()
        return metadata.get(page_title)

    def clear_fetched(self) -> int:
        """Clear all fetched pages.

        Returns:
            Number of files deleted.
        """
        count = 0
        if self._fetched_dir.exists():
            for file_path in self._fetched_dir.glob("*.txt"):
                file_path.unlink()
                count += 1

        logger.info(f"Cleared {count} fetched pages")
        return count

    def clear_generated(self) -> int:
        """Clear all generated pages.

        Returns:
            Number of files deleted.
        """
        count = 0
        if self._generated_dir.exists():
            for file_path in self._generated_dir.glob("*.txt"):
                file_path.unlink()
                count += 1

        logger.info(f"Cleared {count} generated pages")
        return count
