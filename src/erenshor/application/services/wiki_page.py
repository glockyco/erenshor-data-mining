"""WikiPage model for multi-entity page support.

This module defines the WikiPage dataclass which represents a wiki page
that may contain one or more entities, and the OperationResult dataclass
which represents the result of wiki operations.
"""

from dataclasses import dataclass

from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.skill import Skill
from erenshor.domain.entities.spell import Spell

# Type alias for entities that can appear on wiki pages
Entity = Item | Character | Spell | Skill


@dataclass
class WikiPage:
    """Represents a wiki page with one or more contributing entities.

    A wiki page may contain multiple entities. For example, "Lingering Inferno"
    is both a spell and a skill, so both entities contribute to the same page.

    Attributes:
        title: Wiki page title (e.g., "Lingering Inferno").
        stable_keys: List of all entity stable keys for this page.
        entities: List of all entities contributing to this page.
    """

    title: str
    stable_keys: list[str]
    entities: list[Entity]

    def is_multi_entity(self) -> bool:
        """Check if this page contains multiple entities.

        Returns:
            True if page has more than one entity, False otherwise.
        """
        return len(self.entities) > 1


@dataclass
class OperationResult:
    """Result of a wiki operation (fetch/generate/deploy).

    Attributes:
        total: Total number of pages processed.
        succeeded: Number of pages successfully processed.
        failed: Number of pages that failed to process.
        skipped: Number of pages skipped (e.g., no changes needed).
        warnings: List of warning messages.
        errors: List of error messages.
    """

    total: int
    succeeded: int
    failed: int
    skipped: int
    warnings: list[str]
    errors: list[str]

    def has_warnings(self) -> bool:
        """Check if result has warnings."""
        return len(self.warnings) > 0

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0
