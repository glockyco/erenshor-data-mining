"""Base classes for wiki page and section generators.

This module defines the foundational interfaces for the wiki generator system:
- PageGenerator: Generates complete wiki pages
- SectionGenerator: Generates sections/components within pages
- GeneratedPage: Container for generated content with metadata
- PageMetadata: Metadata for wiki page updates
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext


@dataclass
class PageMetadata:
    """Metadata for how to update a wiki page.

    Attributes:
        summary: Edit summary for MediaWiki
        minor: Whether this is a minor edit
        tags: Optional tags for categorization/tracking
    """

    summary: str
    minor: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class GeneratedPage:
    """A generated wiki page with metadata.

    Attributes:
        title: Wiki page title
        content: Complete wikitext content
        metadata: Update metadata (summary, minor flag, tags)
        stable_keys: Entity stable keys for this page (for storage tracking)
    """

    title: str
    content: str
    metadata: PageMetadata
    stable_keys: list[str] = field(default_factory=list)


class SectionGenerator:
    """Base class for wiki section generators.

    Section generators create reusable components within wiki pages,
    such as templates ({{Item}}, {{Character}}), tables, or category tags.

    Section generators are composed by PageGenerators to build complete pages.

    Note: This is not an ABC because section generators have different
    interfaces depending on their purpose. Use composition over inheritance.
    """

    def __init__(self, context: GeneratorContext) -> None:
        """Initialize section generator with shared context.

        Args:
            context: Shared context with repositories and resolver
        """
        self.context = context


class PageGenerator(ABC):
    """Abstract base class for wiki page generators.

    Page generators are responsible for:
    1. Declaring which pages to fetch from the wiki (for content preservation)
    2. Generating complete wiki pages with all sections

    Each generator is registered in the wiki generator registry and can be
    selected individually via CLI flags.
    """

    def __init__(self, context: GeneratorContext) -> None:
        """Initialize page generator with shared context.

        Args:
            context: Shared context with repositories and resolver
        """
        self.context = context

    @abstractmethod
    def get_pages_to_fetch(self) -> list[str]:
        """Return page titles to fetch from wiki.

        Called during the fetch phase, before generation. This allows generators
        to preserve manual edits by fetching existing content.

        Returns:
            List of wiki page titles to fetch

        Example:
            ```python
            def get_pages_to_fetch(self) -> list[str]:
                items = self.context.item_repo.get_items_for_wiki_generation()
                # Group entities by page title and return unique titles
                page_titles = set()
                for item in items:
                    page_title = self.context.resolver.resolve_page_title(item.stable_key)
                    if page_title:
                        page_titles.add(page_title)
                return list(page_titles)
            ```
        """

    @abstractmethod
    def generate_pages(self) -> Iterator[GeneratedPage]:
        """Generate complete wiki pages.

        Called during the generate phase. Should yield GeneratedPage objects
        with complete wikitext content and metadata.

        Yields:
            GeneratedPage objects with title, content, and metadata

        Example:
            ```python
            def generate_pages(self) -> Iterator[GeneratedPage]:
                items = self.context.item_repo.get_items_for_wiki_generation()
                for item in items:
                    content = self._generate_item_page(item)
                    yield GeneratedPage(
                        title=self.context.resolver.resolve_page_title(item.stable_key),
                        content=content,
                        metadata=PageMetadata(
                            summary="Update item data from game export",
                            minor=False,
                        ),
                    )
            ```
        """
