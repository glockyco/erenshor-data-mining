"""Quest repository for specialized quest queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_quest_chain(quest_id) -> for wiki quest chain sections
- get_quests_by_faction(faction_id) -> for wiki faction quest lists
- get_quest_rewards(quest_id) -> for wiki quest reward tables
- get_quest_prerequisites(quest_id) -> for wiki quest requirement sections

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.quest import Quest
from erenshor.infrastructure.database.repository import BaseRepository


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
