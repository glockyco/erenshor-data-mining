"""Skill repository for specialized skill queries."""

import json
from collections.abc import Mapping

from loguru import logger

from erenshor.domain.entities.skill import Skill
from erenshor.domain.value_objects.wiki_link import AbilityLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

_SKILL_COLUMNS = """
    s.*,
    (SELECT json_group_object(sc.class_name, sc.required_level)
     FROM skill_classes sc WHERE sc.skill_stable_key = s.stable_key) AS class_levels
"""


def _skill_from_row(row: Mapping[str, object]) -> Skill:
    values = dict(row)
    values["class_levels"] = json.loads(str(values["class_levels"]))
    return Skill.model_validate(values)


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
        query = f"""
            SELECT {_SKILL_COLUMNS}
            FROM skills s
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            skills = [_skill_from_row(dict(row)) for row in rows]
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
        query = f"""
            SELECT {_SKILL_COLUMNS}
            FROM skills s
            WHERE stable_key = ?
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Skill not found: {stable_key}")
                return None
            return _skill_from_row(dict(rows[0]))
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skill {stable_key}: {e}") from e

    def get_class_display_names(self) -> dict[str, str]:
        """Get internal class name to wiki display name mapping."""
        query = """
            SELECT class_name, display_name
            FROM classes
            WHERE class_name != 'Default'
            ORDER BY class_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            names = {}
            for row in rows:
                class_name = str(row["class_name"])
                display_name = row["display_name"]
                if not display_name or not str(display_name).strip():
                    raise ValueError(f"Class {class_name} has no display name")
                names[class_name] = str(display_name)
            return names
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve class display names: {e}") from e

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
            SELECT stable_key, display_name, wiki_page_name, image_name
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
                    stable_key=str(row["stable_key"]),
                )
                for row in rows
            ]
            logger.debug(f"Retrieved {len(links)} skills using stance {stance_stable_key}")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skills for stance {stance_stable_key}: {e}") from e
