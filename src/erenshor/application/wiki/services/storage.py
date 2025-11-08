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
    ├── fetched/          # Pages fetched from wiki (URL-encoded page titles)
    │   ├── Cloth%20Sleeves.txt
    │   ├── A%20Beaktooth.txt
    │   └── Hydrated.txt
    ├── generated/        # Generated pages ready to deploy (URL-encoded page titles)
    │   ├── Cloth%20Sleeves.txt
    │   └── A%20Beaktooth.txt
    └── metadata.json     # Maps page titles to stable keys, fetch timestamps, hashes

Example:
    >>> from pathlib import Path
    >>> storage = WikiStorage(Path("variants/main/wiki"))
    >>>
    >>> # Save fetched page (files stored by page title, metadata tracks stable keys)
    >>> storage.save_fetched_by_title(
    ...     page_title="Cloth Sleeves",
    ...     stable_keys=["item:arm - 1 - cloth sleeves"],
    ...     content="{{Item|...}}"
    ... )
    >>>
    >>> # Read fetched page by title
    >>> content = storage.read_fetched_by_title("Cloth Sleeves")
    >>>
    >>> # Save generated page
    >>> storage.save_generated_by_title(
    ...     page_title="Cloth Sleeves",
    ...     stable_keys=["item:arm - 1 - cloth sleeves"],
    ...     content="{{Item|...}}"
    ... )
    >>>
    >>> # List all generated pages
    >>> pages = storage.list_generated()
"""

from __future__ import annotations

import hashlib
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
        page_title: MediaWiki page title (e.g., "Cloth Sleeves").
        stable_keys: List of stable identifiers contributing to this page
            (e.g., ["item:arm - 1 - cloth sleeves"] or ["spell:all - hydrated"]).
        entity_names: List of human-readable entity names (parallel to stable_keys)
            (e.g., ["Cloth Sleeves"] or ["Hydrated"]).
        fetched_at: ISO timestamp when page was fetched from wiki.
        fetched_hash: SHA256 hash of fetched wiki content.
        generated_at: ISO timestamp when page was generated locally.
        generated_hash: SHA256 hash of generated content.
        deployed_at: ISO timestamp when page was deployed to wiki.
        deployed_hash: SHA256 hash of deployed content.
    """

    page_title: str
    stable_keys: list[str]
    entity_names: list[str]
    fetched_at: str | None = None
    fetched_hash: str | None = None
    generated_at: str | None = None
    generated_hash: str | None = None
    deployed_at: str | None = None
    deployed_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "page_title": self.page_title,
            "stable_keys": self.stable_keys,
            "entity_names": self.entity_names,
            "fetched_at": self.fetched_at,
            "fetched_hash": self.fetched_hash,
            "generated_at": self.generated_at,
            "generated_hash": self.generated_hash,
            "deployed_at": self.deployed_at,
            "deployed_hash": self.deployed_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageMetadata:
        """Create from dictionary after JSON deseriization."""
        return cls(
            page_title=data["page_title"],
            stable_keys=data["stable_keys"],
            entity_names=data["entity_names"],
            fetched_at=data.get("fetched_at"),
            fetched_hash=data.get("fetched_hash"),
            generated_at=data.get("generated_at"),
            generated_hash=data.get("generated_hash"),
            deployed_at=data.get("deployed_at"),
            deployed_hash=data.get("deployed_hash"),
        )

    def should_deploy(self) -> tuple[bool, str]:
        """Check if page should be deployed based on metadata.

        Returns:
            Tuple of (should_deploy, reason)
            - (True, "") if page should be deployed
            - (False, reason) if page should be skipped with explanation
        """
        # Must have generated content
        if self.generated_at is None:
            return False, "not generated"

        # Skip if not regenerated since last deployment
        if self.deployed_at is not None and self.generated_at <= self.deployed_at:
            return False, "not regenerated since deployment"

        # Skip if older than fetched content (prevents overwriting wiki edits)
        if self.fetched_at is not None and self.generated_at <= self.fetched_at:
            return False, "older than fetched (fetch and regenerate first)"

        # Skip if content unchanged
        if self.generated_hash == self.deployed_hash:
            return False, "content unchanged"

        return True, ""


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

        # Compute content hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        metadata = self._load_metadata()

        # Preserve existing metadata if it exists
        existing = metadata.get(page_title)

        metadata[page_title] = PageMetadata(
            page_title=page_title,
            stable_keys=stable_keys,
            entity_names=entity_names,
            fetched_at=datetime.now().isoformat(),
            fetched_hash=content_hash,
            # Preserve generation and deployment info
            generated_at=existing.generated_at if existing else None,
            generated_hash=existing.generated_hash if existing else None,
            deployed_at=existing.deployed_at if existing else None,
            deployed_hash=existing.deployed_hash if existing else None,
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

        # Compute content hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        metadata = self._load_metadata()
        content_changed = False

        if page_title in metadata:
            # Check if content actually changed
            old_hash = metadata[page_title].generated_hash
            content_changed = old_hash != content_hash

            metadata[page_title].generated_at = datetime.now().isoformat()
            metadata[page_title].generated_hash = content_hash
        else:
            logger.warning(f"Creating metadata for {page_title} without fetch info")
            entity_names = [sk.split(":", 1)[1].replace("_", " ").title() for sk in stable_keys]
            metadata[page_title] = PageMetadata(
                page_title=page_title,
                stable_keys=stable_keys,
                entity_names=entity_names,
                generated_at=datetime.now().isoformat(),
                generated_hash=content_hash,
            )
            content_changed = True  # New page counts as changed

        self._save_metadata(metadata)

        # Only log at INFO level when content actually changed
        if content_changed:
            logger.info(f"Updated: {page_title}")
        else:
            logger.debug(f"No changes: {page_title}")

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

    def update_deployed(
        self,
        page_title: str,
        content: str,
    ) -> None:
        """Update deployment metadata after successful wiki upload.

        Args:
            page_title: MediaWiki page title that was deployed.
            content: Content that was deployed.
        """
        # Compute content hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        metadata = self._load_metadata()
        if page_title not in metadata:
            logger.warning(f"Cannot update deployed metadata for unknown page: {page_title}")
            return

        metadata[page_title].deployed_at = datetime.now().isoformat()
        metadata[page_title].deployed_hash = content_hash

        self._save_metadata(metadata)
        logger.debug(f"Updated deployment metadata for: {page_title}")

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
