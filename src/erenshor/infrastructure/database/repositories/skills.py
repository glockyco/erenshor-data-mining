"""Skill repository for specialized skill queries."""

from loguru import logger

from erenshor.domain.entities.skill import Skill
from erenshor.domain.value_objects.wiki_link import AbilityLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class SkillRepository(BaseRepository[Skill]):
    """Repository for skill-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_skills_for_wiki_generation(self) -> list[Skill]:
        """Get all skills for wiki page generation.

        Returns all skills with basic fields populated.

        Used by: Skill page generators (combat skills, abilities, etc.)

        Returns:
            List of Skill entities with basic fields populated.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT *
            FROM skills
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            skills = [Skill.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(skills)} skills for wiki generation")
            return skills
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skills for wiki: {e}") from e

    def get_skill_by_stable_key(self, stable_key: str) -> Skill | None:
        """Get a skill by its stable key.

        Args:
            stable_key: Skill stable key (e.g., "skill:Backstab")

        Returns:
            Skill entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT *
            FROM skills
            WHERE stable_key = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Skill not found: {stable_key}")
                return None
            return Skill.model_validate(dict(rows[0]))
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skill {stable_key}: {e}") from e

    def get_skills_using_stance(self, stance_stable_key: str) -> list[AbilityLink]:
        """Get all skills that activate a specific stance.

        Used for bidirectional linking on stance wiki pages.

        Args:
            stance_stable_key: Stance stable key (e.g., "stance:Aggressive")

        Returns:
            List of AbilityLink objects for skills that activate this stance,
            sorted by display name.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT display_name, wiki_page_name, image_name
            FROM skills
            WHERE stance_to_use_stable_key = ?
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (stance_stable_key,))
            links = [
                AbilityLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                    image_name=str(row["image_name"]) if row["image_name"] else None,
                )
                for row in rows
            ]
            logger.debug(f"Retrieved {len(links)} skills using stance {stance_stable_key}")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skills for stance {stance_stable_key}: {e}") from e
