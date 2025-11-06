"""Quest repository for specialized quest queries."""

from loguru import logger

from erenshor.domain.entities.quest import Quest
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_quests_rewarding_item(self, item_stable_key: str) -> list[str]:
        """Get quests that reward the given item.

        Uses QuestRewards table to find quests rewarding this item.
        Only includes rewards of type 'Item'.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key

        Returns:
            List of quest stable keys

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT q.StableKey
            FROM Quests q
            JOIN QuestVariants qv ON q.StableKey = qv.QuestStableKey
            JOIN QuestRewards qr ON qv.ResourceName = qr.QuestVariantResourceName
            WHERE qr.RewardType = 'Item'
                AND qr.RewardValue = ?
            ORDER BY q.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} quests rewarding '{item_stable_key}'")
            return [str(row["StableKey"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest rewards for item '{item_stable_key}': {e}") from e

    def get_quests_requiring_item(self, item_stable_key: str) -> list[str]:
        """Get quests that require the given item.

        Uses QuestRequiredItems table to find quests requiring this item.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key

        Returns:
            List of quest stable keys

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT q.StableKey
            FROM Quests q
            JOIN QuestVariants qv ON q.StableKey = qv.QuestStableKey
            JOIN QuestRequiredItems qri ON qv.ResourceName = qri.QuestVariantResourceName
            WHERE qri.ItemStableKey = ?
            ORDER BY q.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} quests requiring '{item_stable_key}'")
            return [str(row["StableKey"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest requirements for item '{item_stable_key}': {e}") from e
