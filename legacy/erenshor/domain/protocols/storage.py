"""Storage protocols (interfaces for persistence)."""

from __future__ import annotations

from typing import Protocol

from erenshor.domain.entities.page import WikiPage

__all__ = ["PageStorage"]


class PageStorage(Protocol):
    """Protocol for reading and writing wiki pages."""

    def read(self, page: WikiPage) -> str | None:
        """Read page content from storage."""
        ...

    def write(self, page: WikiPage, content: str) -> None:
        """Write page content to storage."""
        ...

    def exists(self, page: WikiPage) -> bool:
        """Check if page exists in storage."""
        ...
