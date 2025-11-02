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

from loguru import logger


@dataclass
class PageMetadata:
    """Metadata for a wiki page.

    Attributes:
        stable_key: Stable identifier (entity_type:resource_name).
        wiki_title: MediaWiki page title (e.g., "Item:Iron Sword").
        entity_name: Human-readable entity name (e.g., "Iron Sword").
        fetched_at: ISO timestamp when page was fetched from wiki.
        generated_at: ISO timestamp when page was generated locally.
    """

    stable_key: str
    wiki_title: str
    entity_name: str
    fetched_at: str | None = None
    generated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stable_key": self.stable_key,
            "wiki_title": self.wiki_title,
            "entity_name": self.entity_name,
            "fetched_at": self.fetched_at,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageMetadata:
        """Create from dictionary after JSON deserialization."""
        return cls(
            stable_key=data["stable_key"],
            wiki_title=data["wiki_title"],
            entity_name=data["entity_name"],
            fetched_at=data.get("fetched_at"),
            generated_at=data.get("generated_at"),
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

    def _get_fetched_path(self, stable_key: str) -> Path:
        """Get file path for fetched page."""
        return self._fetched_dir / f"{stable_key}.txt"

    def _get_generated_path(self, stable_key: str) -> Path:
        """Get file path for generated page."""
        return self._generated_dir / f"{stable_key}.txt"

    def save_fetched(self, stable_key: str, wiki_title: str, content: str, entity_name: str) -> None:
        """Save fetched page from MediaWiki.

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").
            wiki_title: MediaWiki page title (e.g., "Item:Iron Sword").
            content: Wiki page content (wikitext).
            entity_name: Human-readable entity name (e.g., "Iron Sword").
        """
        # Save content to file
        file_path = self._get_fetched_path(stable_key)
        file_path.write_text(content, encoding="utf-8")

        # Update metadata
        metadata = self._load_metadata()
        metadata[stable_key] = PageMetadata(
            stable_key=stable_key,
            wiki_title=wiki_title,
            entity_name=entity_name,
            fetched_at=datetime.now().isoformat(),
        )
        self._save_metadata(metadata)

        logger.debug(f"Saved fetched page: {stable_key} -> {file_path}")

    def read_fetched(self, stable_key: str) -> str | None:
        """Read fetched page content.

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").

        Returns:
            Page content if exists, None otherwise.
        """
        file_path = self._get_fetched_path(stable_key)
        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def save_generated(self, stable_key: str, content: str) -> None:
        """Save generated page (ready to deploy).

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").
            content: Generated wiki page content (wikitext).
        """
        # Save content to file
        file_path = self._get_generated_path(stable_key)
        file_path.write_text(content, encoding="utf-8")

        # Update metadata timestamp
        metadata = self._load_metadata()
        if stable_key in metadata:
            metadata[stable_key].generated_at = datetime.now().isoformat()
        else:
            # Create minimal metadata if not exists (shouldn't happen normally)
            logger.warning(f"Creating metadata for {stable_key} without fetch info")
            metadata[stable_key] = PageMetadata(
                stable_key=stable_key,
                wiki_title=stable_key.replace(":", ":", 1).title(),  # Placeholder
                entity_name=stable_key.split(":", 1)[1].replace("_", " ").title(),
                generated_at=datetime.now().isoformat(),
            )
        self._save_metadata(metadata)

        logger.debug(f"Saved generated page: {stable_key} -> {file_path}")

    def read_generated(self, stable_key: str) -> str | None:
        """Read generated page content.

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").

        Returns:
            Page content if exists, None otherwise.
        """
        file_path = self._get_generated_path(stable_key)
        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def list_fetched(self) -> list[str]:
        """List all fetched stable keys.

        Returns:
            List of stable keys for fetched pages.
        """
        if not self._fetched_dir.exists():
            return []

        return [p.stem for p in self._fetched_dir.glob("*.txt")]

    def list_generated(self) -> list[str]:
        """List all generated stable keys.

        Returns:
            List of stable keys for generated pages.
        """
        if not self._generated_dir.exists():
            return []

        return [p.stem for p in self._generated_dir.glob("*.txt")]

    def get_metadata(self, stable_key: str) -> PageMetadata | None:
        """Get metadata for a page.

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").

        Returns:
            PageMetadata if exists, None otherwise.
        """
        metadata = self._load_metadata()
        return metadata.get(stable_key)

    def get_wiki_title(self, stable_key: str) -> str | None:
        """Get MediaWiki page title for a stable key.

        Args:
            stable_key: Stable identifier (e.g., "item:iron_sword").

        Returns:
            Wiki page title if exists, None otherwise.
        """
        meta = self.get_metadata(stable_key)
        return meta.wiki_title if meta else None

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
