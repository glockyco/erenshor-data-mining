"""Spell repository for specialized spell queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_class_spells(class_name) -> for wiki class spell lists
- get_spell_effects(spell_id) -> for wiki spell effect sections
- get_damage_spells() -> for wiki damage spell tables
- get_buff_spells() -> for wiki buff spell tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repository import BaseRepository


class SpellRepository(BaseRepository[Spell]):
    """Repository for spell-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    pass  # Add query methods when actually needed
