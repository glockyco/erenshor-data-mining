"""Quest repository for specialized quest queries."""

from loguru import logger

from erenshor.domain.entities.quest import Quest
from erenshor.domain.value_objects.wiki_link import QuestLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_quests_rewarding_item(self, item_stable_key: str) -> list[QuestLink]:
        """Get quests that reward the given item.

        Uses quest_variants.item_on_complete_stable_key to find quests
        rewarding this item.

        Args:
            item_stable_key: Item stable key

        Returns:
            List of QuestLink objects, sorted by display name

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT q.display_name, q.wiki_page_name
            FROM quests q
            JOIN quest_variants qv ON q.stable_key = qv.quest_stable_key
            WHERE qv.item_on_complete_stable_key = ?
            ORDER BY q.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            links = [
                QuestLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} quests rewarding '{item_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest rewards for item '{item_stable_key}': {e}") from e

    def get_quests_requiring_item(self, item_stable_key: str) -> list[QuestLink]:
        """Get quests that require the given item.

        Uses quest_required_items table to find quests requiring this item.

        Args:
            item_stable_key: Item stable key

        Returns:
            List of QuestLink objects, sorted by display name

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT q.display_name, q.wiki_page_name
            FROM quests q
            JOIN quest_variants qv ON q.stable_key = qv.quest_stable_key
            JOIN quest_required_items qri ON qv.resource_name = qri.quest_variant_resource_name
            WHERE qri.item_stable_key = ?
            ORDER BY q.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            links = [
                QuestLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} quests requiring '{item_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest requirements for item '{item_stable_key}': {e}") from e
