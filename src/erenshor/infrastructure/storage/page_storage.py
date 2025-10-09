"""Page storage system for wiki registry."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from erenshor.domain.entities.page import WikiPage
from erenshor.registry.core import WikiRegistry

__all__ = ["PageStorage"]


class PageStorage:
    """Handle file I/O for wiki pages using registry."""

    def __init__(self, registry: WikiRegistry, pages_dir: Optional[Path] = None):
        """Initialize with registry."""
        self.registry = registry
        self.pages_dir = pages_dir if pages_dir else registry.pages_dir
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def read(self, page: WikiPage) -> Optional[str]:
        """Read page content from disk."""
        path = self.pages_dir / page.safe_filename
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, page: WikiPage, content: str) -> None:
        """Write locally modified content to disk."""
        self._write_content(page, content, is_local_update=True)

    def write_fetched(self, page: WikiPage, content: str) -> None:
        """Write content fetched from wiki to disk."""
        self._write_content(page, content, is_local_update=False)

    def _write_content(
        self, page: WikiPage, content: str, is_local_update: bool
    ) -> None:
        """Write page content to disk with appropriate metadata updates."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Atomic write via temp file
        path = self.pages_dir / page.safe_filename
        temp = path.with_suffix(".tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)

        if is_local_update:
            page.updated_content_hash = content_hash
            page.last_updated = datetime.now(timezone.utc)
        else:
            # Fetched from wiki: reset both hashes to match remote
            page.original_content_hash = content_hash
            page.updated_content_hash = content_hash
            page.last_fetched = datetime.now(timezone.utc)

        self.registry.save()

    def exists(self, page: WikiPage) -> bool:
        """Check if page file exists."""
        path = self.pages_dir / page.safe_filename
        return path.exists()

    def delete(self, page: WikiPage) -> bool:
        """Delete page file if it exists."""
        path = self.pages_dir / page.safe_filename
        if path.exists():
            path.unlink()
            return True
        return False

    def get_path(self, page: WikiPage) -> Path:
        """Get filesystem path for a page."""
        return self.pages_dir / page.safe_filename
