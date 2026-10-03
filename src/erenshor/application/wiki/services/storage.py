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
    ...     content="{{Item|...}}",
    ...     entity_names=["Cloth Sleeves"],
    ...     revision_id=123
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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from loguru import logger

from erenshor.application.wiki.services.helpers import normalise_generated_page_content
from erenshor.infrastructure.wiki.content import normalize_saved_text


class WikiMetadataError(Exception):
    """Metadata could not be read or decoded."""


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
        fetched_revision_id: Wiki revision ID of the cached text.
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
    fetched_revision_id: int | None = None
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
            "fetched_revision_id": self.fetched_revision_id,
            "generated_at": self.generated_at,
            "generated_hash": self.generated_hash,
            "deployed_at": self.deployed_at,
            "deployed_hash": self.deployed_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageMetadata:
        """Create page metadata from a JSON object."""
        if not isinstance(data, dict):
            raise ValueError("page metadata must be an object")
        if not isinstance(data.get("page_title"), str):
            raise ValueError("page_title must be text")
        for field in ("stable_keys", "entity_names"):
            values = data.get(field)
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"{field} must be a list of text")
        for field in (
            "fetched_at",
            "fetched_hash",
            "generated_at",
            "generated_hash",
            "deployed_at",
            "deployed_hash",
        ):
            value = data.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be text or null")
        revision_id = data.get("fetched_revision_id")
        if revision_id is not None and (type(revision_id) is not int or revision_id <= 0):
            raise ValueError("fetched_revision_id must be a positive integer or null")
        return cls(
            page_title=data["page_title"],
            stable_keys=data["stable_keys"],
            entity_names=data["entity_names"],
            fetched_at=data.get("fetched_at"),
            fetched_hash=data.get("fetched_hash"),
            fetched_revision_id=revision_id,
            generated_at=data.get("generated_at"),
            generated_hash=data.get("generated_hash"),
            deployed_at=data.get("deployed_at"),
            deployed_hash=data.get("deployed_hash"),
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
        >>> storage.save_fetched_by_title(
        ...     page_title="Iron Sword",
        ...     stable_keys=["item:iron sword"],
        ...     content="{{Item|...}}",
        ...     entity_names=["Iron Sword"],
        ...     revision_id=123
        ... )
        >>> content = storage.read_fetched_by_title("Iron Sword")
        >>> storage.save_generated_by_title(
        ...     page_title="Iron Sword",
        ...     stable_keys=["item:iron sword"],
        ...     content="{{Item|...}}"
        ... )
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
        """Load metadata from JSON file, or fail if an existing file is invalid."""
        try:
            with self._metadata_file.open(encoding="utf-8") as metadata_file:
                data = json.load(metadata_file)
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return {key: PageMetadata.from_dict(value) for key, value in data.items()}
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise WikiMetadataError(f"Cannot read {self._metadata_file}: {error}") from error

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
        revision_id: int,
    ) -> None:
        """Save fetched page from MediaWiki.

        Args:
            page_title: MediaWiki page title.
            stable_keys: Stable identifiers for all entities on this page.
            content: Wiki page content (wikitext).
            entity_names: Human-readable names for all entities on this page.
            revision_id: Revision ID returned with the fetched content.
        """
        metadata = self._load_metadata()
        existing = metadata.get(page_title)
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._fetched_dir / f"{safe_filename}.txt"
        file_path.write_text(content, encoding="utf-8")

        # Compute content hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        metadata[page_title] = PageMetadata(
            page_title=page_title,
            stable_keys=stable_keys,
            entity_names=entity_names,
            fetched_at=datetime.now().isoformat(),
            fetched_hash=content_hash,
            fetched_revision_id=revision_id,
            # Preserve generation and deployment info
            generated_at=existing.generated_at if existing else None,
            generated_hash=existing.generated_hash if existing else None,
            deployed_at=existing.deployed_at if existing else None,
            deployed_hash=existing.deployed_hash if existing else None,
        )
        self._save_metadata(metadata)

        logger.debug(f"Saved fetched page: {page_title} ({len(stable_keys)} entities)")

    def has_fetched_by_title(self, page_title: str) -> bool:
        """Check whether the fetched page content exists locally."""
        filename = self._encode_page_title_for_filename(page_title)
        return (self._fetched_dir / f"{filename}.txt").is_file()

    def remove_fetched_by_title(self, page_title: str) -> None:
        """Remove stale fetched text and its revision after a wiki deletion."""
        metadata = self._load_metadata()
        existing = metadata.get(page_title)
        filename = self._encode_page_title_for_filename(page_title)
        (self._fetched_dir / f"{filename}.txt").unlink(missing_ok=True)
        if existing is not None:
            existing.fetched_at = None
            existing.fetched_hash = None
            existing.fetched_revision_id = None
            self._save_metadata(metadata)

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
        metadata = self._load_metadata()
        safe_filename = self._encode_page_title_for_filename(page_title)
        file_path = self._generated_dir / f"{safe_filename}.txt"
        normalized_content = normalise_generated_page_content(content)
        file_path.write_text(normalized_content, encoding="utf-8")

        # Compute content hash
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        content_changed = False
        entity_names = [stable_key.split(":", 1)[1].replace("_", " ").title() for stable_key in stable_keys]

        if page_title in metadata:
            # Check if content actually changed
            old_hash = metadata[page_title].generated_hash
            content_changed = old_hash != content_hash

            metadata[page_title].stable_keys = list(stable_keys)
            metadata[page_title].entity_names = entity_names
            metadata[page_title].generated_at = datetime.now().isoformat()
            metadata[page_title].generated_hash = content_hash
        else:
            logger.warning(f"Creating metadata for {page_title} without fetch info")
            metadata[page_title] = PageMetadata(
                page_title=page_title,
                stable_keys=list(stable_keys),
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

    def generated_path(self, page_title: str) -> Path:
        """Return the file that holds the generated content of a page."""
        return self._generated_dir / f"{self._encode_page_title_for_filename(page_title)}.txt"

    def list_generated_titles(self) -> tuple[str, ...]:
        """Return all generated article titles in deterministic order."""
        metadata = self._load_metadata()
        return tuple(
            sorted(
                (title for title, page in metadata.items() if page.generated_at is not None),
                key=lambda title: (title.casefold(), title),
            )
        )

    def read_generated_pages(self, page_titles: Sequence[str] | None = None) -> dict[str, str]:
        """Return one deterministic snapshot of generated page contents.

        Metadata and files are one storage contract. A generated metadata row
        without its content file is corruption and fails instead of silently
        weakening deployment preflight checks.
        """
        requested = None if page_titles is None else set(page_titles)
        metadata = self._load_metadata()
        titles = sorted(
            (
                title
                for title, page_metadata in metadata.items()
                if page_metadata.generated_at is not None and (requested is None or title in requested)
            ),
            key=lambda title: (title.casefold(), title),
        )
        pages: dict[str, str] = {}
        for title in titles:
            content = self.read_generated_by_title(title)
            if content is None:
                raise FileNotFoundError(f"Generated wiki content missing for {title!r}")
            pages[title] = content
        return pages

    def get_metadata_by_title(self, page_title: str) -> PageMetadata | None:
        """Get metadata for a page by title.

        Args:
            page_title: MediaWiki page title.

        Returns:
            PageMetadata if exists, None otherwise.
        """
        metadata = self._load_metadata()
        return metadata.get(page_title)

    def get_metadata_by_titles(self, titles: Sequence[str]) -> dict[str, PageMetadata]:
        """Read metadata once for the requested page titles."""
        metadata = self._load_metadata()
        return {title: metadata[title] for title in titles if title in metadata}

    def record_deployed(self, page_title: str, content: str, revision_id: int) -> None:
        """Record that the live page now holds ``content`` at ``revision_id``.

        The fetched copy becomes the text that MediaWiki saved, so the next
        deploy plan compares against the live page, and the next fetch keeps
        the copy while the live revision stays the same.

        Raises:
            WikiMetadataError: The page has no metadata.
        """
        metadata = self._load_metadata()
        existing = metadata.get(page_title)
        if existing is None:
            raise WikiMetadataError(f"Cannot record a deploy for unknown page: {page_title}")

        saved_text = normalize_saved_text(content)
        safe_filename = self._encode_page_title_for_filename(page_title)
        (self._fetched_dir / f"{safe_filename}.txt").write_text(saved_text, encoding="utf-8")
        now = datetime.now().isoformat()
        existing.fetched_at = now
        existing.fetched_hash = hashlib.sha256(saved_text.encode("utf-8")).hexdigest()
        existing.fetched_revision_id = revision_id
        existing.deployed_at = now
        existing.deployed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self._save_metadata(metadata)
        logger.debug(f"Recorded deploy of {page_title} at revision {revision_id}")

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

    def remove_stale_pages(self, valid_page_titles: set[str]) -> int:
        """Remove metadata and files for page titles that no longer exist.

        Compares stored metadata against a set of currently valid page titles
        and removes any entries that are no longer valid. This prevents stale
        pages (e.g., from before name normalization fixes) from being deployed
        and overwriting correct content on the wiki.

        Args:
            valid_page_titles: Set of page titles that are currently valid.

        Returns:
            Number of stale entries removed.
        """
        metadata = self._load_metadata()
        stale_titles = [title for title in metadata if title not in valid_page_titles]

        if not stale_titles:
            return 0

        for title in stale_titles:
            del metadata[title]

            # Remove associated files
            safe_filename = self._encode_page_title_for_filename(title)
            for directory in (self._generated_dir, self._fetched_dir):
                file_path = directory / f"{safe_filename}.txt"
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Removed stale file: {file_path}")

            logger.info(f"Removed stale page: {title!r}")

        self._save_metadata(metadata)
        logger.info(f"Removed {len(stale_titles)} stale pages from metadata")
        return len(stale_titles)
