"""Skill repository for specialized skill queries."""

from erenshor.domain.entities.skill import Skill
from erenshor.infrastructure.database.repository import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """Repository for skill-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
