"""Faction repository for specialized faction queries."""

from dataclasses import dataclass

from loguru import logger

from erenshor.domain.entities.faction import Faction
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


@dataclass(frozen=True, slots=True)
class FactionWikiRecord:
    """Faction identity fields needed by generated wiki semantic links."""

    stable_key: str
    display_name: str | None
    wiki_page_name: str | None
    image_name: str | None

    @property
    def faction_name(self) -> str | None:
        """Compatibility alias for callers using the raw faction field name."""
        return self.display_name


class FactionRepository(BaseRepository[Faction]):
    """Repository for faction-specific database queries."""

    def get_factions_for_wiki_generation(self) -> list[FactionWikiRecord]:
        """Get all faction identities used by generated wiki links."""
        query = """
            SELECT stable_key, display_name, wiki_page_name, image_name
            FROM factions
            ORDER BY stable_key
        """
        try:
            rows = self._execute_raw(query)
            return [
                FactionWikiRecord(
                    stable_key=str(row["stable_key"]),
                    display_name=str(row["display_name"]) if row["display_name"] is not None else None,
                    wiki_page_name=str(row["wiki_page_name"]) if row["wiki_page_name"] is not None else None,
                    image_name=str(row["image_name"]) if row["image_name"] is not None else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve factions for wiki generation: {e}") from e

    def get_by_stable_key(self, stable_key: str) -> Faction | None:
        """Get a faction by its stable key."""
        query = """
            SELECT *
            FROM factions
            WHERE stable_key = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Faction not found: {stable_key}")
                return None
            return Faction.model_validate(dict(rows[0]))
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction {stable_key}: {e}") from e
