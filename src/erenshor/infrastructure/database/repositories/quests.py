"""Quest repository for specialized quest queries."""

from loguru import logger

from erenshor.domain.entities.quest import Quest
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, UsedInInfo
from erenshor.domain.value_objects.wiki_link import QuestLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class QuestRepository(BaseRepository[Quest]):
    """Repository for quest-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_quests_for_wiki_generation(self) -> list[Quest]:
        """Get all quests for local Lua data module generation."""
        query = """
            SELECT *
            FROM quests
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            quests = [Quest.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(quests)} quests for wiki generation")
            return quests
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quests for wiki: {e}") from e

    def get_faction_changes_for_quests(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]:
        """Get display-ready faction changes for Lua quest data."""
        if not stable_keys:
            return {}

        placeholders = ",".join("?" for _ in stable_keys)
        query = f"""
            SELECT
                qv.quest_stable_key,
                qfa.faction_stable_key,
                qfa.modifier_value,
                f.display_name AS faction_display_name,
                f.wiki_page_name AS faction_wiki_page_name
            FROM quest_variants qv
            JOIN quest_faction_affects qfa ON qfa.quest_variant_resource_name = qv.resource_name
            JOIN factions f ON f.stable_key = qfa.faction_stable_key
            WHERE qv.quest_stable_key IN ({placeholders})
            ORDER BY qv.quest_stable_key, f.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, tuple(stable_keys))
            changes: dict[str, list[FactionModifier]] = {stable_key: [] for stable_key in stable_keys}
            for row in rows:
                changes[str(row["quest_stable_key"])].append(
                    FactionModifier(
                        faction_stable_key=str(row["faction_stable_key"]),
                        modifier_value=int(row["modifier_value"]),
                        faction_display_name=str(row["faction_display_name"]),
                        faction_wiki_page_name=row["faction_wiki_page_name"],
                    )
                )
            return changes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest faction changes: {e}") from e

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

    def get_quest_reward_sources(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return stable-keyed quests that reward an item."""
        query = """
            SELECT DISTINCT q.stable_key
            FROM quests q
            JOIN quest_variants qv ON q.stable_key = qv.quest_stable_key
            WHERE qv.item_on_complete_stable_key = ?
            ORDER BY q.stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [ObtainedFromInfo(source_type="quest", source_key=str(row["stable_key"])) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stable quest sources for '{item_stable_key}': {e}") from e

    def get_quest_requirement_sources(self, item_stable_key: str) -> list[UsedInInfo]:
        """Return quests that require an item, with required quantities."""
        query = """
            SELECT q.stable_key, MAX(qri.quantity) AS quantity
            FROM quests q
            JOIN quest_variants qv ON q.stable_key = qv.quest_stable_key
            JOIN quest_required_items qri ON qv.resource_name = qri.quest_variant_resource_name
            WHERE qri.item_stable_key = ?
            GROUP BY q.stable_key
            ORDER BY q.stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                UsedInInfo(
                    use_type="quest_requirement",
                    target_key=f"quest:{row['stable_key']}",
                    quantity=int(row["quantity"]) if row["quantity"] is not None else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest uses for '{item_stable_key}': {e}") from e
