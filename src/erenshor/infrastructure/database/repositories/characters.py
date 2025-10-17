"""Character repository for specialized character queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_vendors() -> for wiki vendor lists
- get_quest_givers() -> for wiki quest giver tables
- get_spawn_data(character_id) -> for wiki spawn location sections
- get_character_abilities(character_id) -> for wiki ability tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.character import Character
from erenshor.infrastructure.database.repository import BaseRepository


class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
