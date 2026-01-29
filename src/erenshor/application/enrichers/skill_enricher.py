"""Skill enrichment service for wiki generation.

This service aggregates skill-related data from multiple tables:
- Items that grant this skill as an effect (procs, click effects, worn effects, etc.)
- Teaching items (skill books)
- Stance activated by this skill
"""

from loguru import logger

from erenshor.domain.enriched_data.skill import EnrichedSkillData
from erenshor.domain.entities.skill import Skill
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.stances import StanceRepository

__all__ = ["EnrichedSkillData", "SkillEnricher"]


class SkillEnricher:
    """Service for enriching skills with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        item_repo: ItemRepository,
        stance_repo: StanceRepository,
    ) -> None:
        """Initialize skill enricher.

        Args:
            item_repo: Repository for item data (teaching items, obtainability)
            stance_repo: Repository for stance data
        """
        self._item_repo = item_repo
        self._stance_repo = stance_repo

    def enrich(self, skill: Skill) -> EnrichedSkillData:
        """Enrich skill with related data from other tables.

        Args:
            skill: Skill entity

        Returns:
            EnrichedSkillData with items with effect, teaching items, and activated stance
        """
        logger.debug(f"Enriching skill: {skill.skill_name}")

        # Get items that teach this skill (returns list of stable keys)
        teaching_item_keys = self._item_repo.get_items_that_teach_skill(skill.stable_key)

        # Filter to only obtainable teaching items
        obtainable_teaching_items = [key for key in teaching_item_keys if self._item_repo.is_item_obtainable(key)]

        # Get items that grant this skill as an effect
        items_with_effect = self._item_repo.get_items_with_skill_effect(skill.stable_key)
        logger.debug(f"Skill '{skill.skill_name}' has {len(items_with_effect)} items with effect")

        # Get stance activated by this skill (if any)
        activated_stance = None
        if skill.stance_to_use_stable_key:
            activated_stance = self._stance_repo.get_by_stable_key(skill.stance_to_use_stable_key)

        return EnrichedSkillData(
            skill=skill,
            items_with_effect=items_with_effect,
            teaching_items=obtainable_teaching_items,
            activated_stance=activated_stance,
        )
