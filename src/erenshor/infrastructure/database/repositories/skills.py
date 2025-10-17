"""Skill repository for specialized skill queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_class_skills(class_name) -> for wiki class skill lists
- get_weapon_skills() -> for wiki weapon skill tables
- get_skill_requirements(skill_id) -> for wiki skill requirement sections

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.skill import Skill
from erenshor.infrastructure.database.repository import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """Repository for skill-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
