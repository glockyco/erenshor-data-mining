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
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
            context: Shared repositories, storage, and rendering configuration
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
                    page_title = item.wiki_page_name
                    if page_title:
                        page_titles.add(page_title)
                return list(page_titles)
            ```
        """

    @abstractmethod
    def generate_pages(self, *, page_titles: frozenset[str] | None = None) -> Iterator[GeneratedPage]:
        """Generate complete wiki pages.

        Called during the generate phase. Should yield GeneratedPage objects
        with complete wikitext content and metadata.
        ``page_titles`` limits assembly and rendering to exact page titles.
        Every entity sharing a selected title must still contribute to that page.

        Yields:
            GeneratedPage objects with title, content, and metadata
        """

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template from the generators/templates/ directory.

        Uses the same template directory as SectionGeneratorBase. Page generators
        that need Jinja2 rendering use this instead of inheriting from
        SectionGeneratorBase (which is scoped to section-level generation).

        Args:
            template_name: Template filename (e.g., 'zone.jinja2')
            context: Template context variables

        Returns:
            Rendered string
        """
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
            autoescape=False,
        )
        return str(env.get_template(template_name).render(**context))
