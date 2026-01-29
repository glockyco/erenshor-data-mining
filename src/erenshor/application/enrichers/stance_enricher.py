"""Stance enrichment service for wiki generation.

This service aggregates stance-related data from multiple tables:
- Skills that activate this stance
"""

from loguru import logger

from erenshor.domain.enriched_data.stance import EnrichedStanceData
from erenshor.domain.entities.stance import Stance
from erenshor.infrastructure.database.repositories.skills import SkillRepository

__all__ = ["EnrichedStanceData", "StanceEnricher"]


class StanceEnricher:
    """Service for enriching stances with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        skill_repo: SkillRepository,
    ) -> None:
        """Initialize stance enricher.

        Args:
            skill_repo: Repository for skill data (bidirectional linking)
        """
        self._skill_repo = skill_repo

    def enrich(self, stance: Stance) -> EnrichedStanceData:
        """Enrich stance with related data from other tables.

        Args:
            stance: Stance entity

        Returns:
            EnrichedStanceData with skills that activate this stance
        """
        logger.debug(f"Enriching stance: {stance.display_name}")

        # Get skills that activate this stance
        activating_skills = self._skill_repo.get_skills_using_stance(stance.stable_key)
        skill_names = [skill.skill_name for skill in activating_skills if skill.skill_name]

        logger.debug(f"Stance '{stance.display_name}' activated by {len(skill_names)} skills")

        return EnrichedStanceData(
            stance=stance,
            activated_by_skills=skill_names,
        )
