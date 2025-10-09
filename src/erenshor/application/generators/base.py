"""Base protocols and types for content generation.

Content generators transform database entities into rendered wiki content blocks
ready for page insertion. They define a streaming interface that yields one
entity's content at a time, enabling progress tracking and memory efficiency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Protocol

from sqlalchemy.engine import Engine

from erenshor.application.models import RenderedBlock
from erenshor.infrastructure.templates.engine import Renderer
from erenshor.registry.core import EntityRef, WikiRegistry

__all__ = ["BaseGenerator", "ContentGenerator", "GeneratedContent"]


@dataclass(frozen=True)
class GeneratedContent:
    """Output from a content generator for a single entity.

    Represents all wiki content generated for one database entity,
    including the page it should go to and all template blocks to insert.

    Attributes:
        entity_ref: Immutable reference to the source database entity
        page_title: Target wiki page title (resolved via registry)
        rendered_blocks: List of template blocks (infobox, tables, etc.)
    """

    entity_ref: EntityRef
    page_title: str
    rendered_blocks: list[RenderedBlock]

    @property
    def total_bytes(self) -> int:
        """Calculate total size of rendered content in bytes."""
        return sum(len(block.text) for block in self.rendered_blocks)


class ContentGenerator(Protocol):
    """Protocol for content generators.

    Responsibilities:
    1. Querying the database for entities
    2. Building template contexts from entity data
    3. Rendering Jinja2 templates
    4. Yielding GeneratedContent one entity at a time

    Streaming design enables:
    - Progress tracking (emit events per entity)
    - Memory efficiency (don't load all entities at once)
    - Early termination (stop on errors without wasting work)

    Example:
        ```python
        class ItemGenerator:
            def __init__(self, renderer: Renderer):
                self._renderer = renderer

            def generate(
                self,
                engine: Engine,
                registry: WikiRegistry
            ) -> Iterator[GeneratedContent]:
                for item in get_items(engine):
                    contexts = self._build_contexts(item, engine)
                    blocks = [self._render_block(ctx) for ctx in contexts]
                    page_title = self._resolve_title(item, registry)
                    yield GeneratedContent(
                        entity_ref=EntityRef.from_item(item),
                        page_title=page_title,
                        rendered_blocks=blocks
                    )
        ```

    Notes:
        - Generators handle database queries internally
        - Registry is used for link resolution during rendering
        - Entity-level errors should be logged/raised, not silently skipped
    """

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate wiki content for all entities of this type.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for entity-to-page resolution and link building
            filter: Optional filter string (name or 'id:1234') to process specific entities

        Yields:
            GeneratedContent for each entity, one at a time

        Raises:
            Any database or rendering errors should propagate to caller
        """
        ...


class BaseGenerator(ABC):
    """Abstract base class for content generators with common patterns.

    Provides shared initialization and filter logic that all generators need,
    eliminating duplication across ItemGenerator, CharacterGenerator, etc.

    Attributes:
        _renderer: Jinja2 renderer for template rendering
    """

    def __init__(self, renderer: Renderer) -> None:
        """Initialize generator with renderer.

        Args:
            renderer: Jinja2 renderer for template rendering
        """
        self._renderer = renderer

    @abstractmethod
    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate content. Must be implemented by subclasses.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or ID) to process specific entities

        Yields:
            GeneratedContent for each entity, one at a time
        """
        ...

    def _matches_filter(
        self,
        entity_name: str,
        entity_id: int | str,
        filter_str: str | None,
    ) -> bool:
        """Common filter logic - check name or ID match.

        Supports two filter formats:
        - Name-based: case-insensitive substring match (e.g., "Time Stone")
        - ID-based: exact match with "id:" prefix (e.g., "id:1234")

        Args:
            entity_name: Display name of the entity
            entity_id: Unique ID of the entity (int for items, str for characters/spells)
            filter_str: Filter string from command line

        Returns:
            True if entity matches filter, or if filter is None (match all)

        Examples:
            >>> self._matches_filter("Time Stone", 1234, "stone")
            True
            >>> self._matches_filter("Time Stone", 1234, "id:1234")
            True
            >>> self._matches_filter("Time Stone", 1234, "sword")
            False
            >>> self._matches_filter("Time Stone", 1234, None)
            True
        """
        if not filter_str:
            return True

        filter_str = filter_str.strip()

        # ID-based filter: "id:1234"
        if filter_str.lower().startswith("id:"):
            target_id = filter_str[3:].strip()
            return str(entity_id) == target_id

        # Name-based filter: case-insensitive substring match
        return filter_str.lower() in entity_name.lower()
