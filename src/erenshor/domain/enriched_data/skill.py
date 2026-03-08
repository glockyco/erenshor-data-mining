"""Enriched skill data DTO."""

from erenshor.domain.entities.skill import Skill
from erenshor.domain.value_objects.wiki_link import AbilityLink, ItemLink

__all__ = ["EnrichedSkillData"]


class EnrichedSkillData:
    """Enriched skill data with related entities.

    Contains raw skill data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        skill: Skill,
        items_with_effect: list[ItemLink],
        teaching_items: list[ItemLink],
        activated_stance: AbilityLink | None = None,
    ) -> None:
        """Initialize enriched skill data.

        Args:
            skill: Skill entity
            items_with_effect: Pre-built ItemLink objects for items that grant this skill
            teaching_items: Pre-built ItemLink objects for items that teach this skill
            activated_stance: Pre-built AbilityLink for the stance this skill activates (if any)
        """
        self.skill = skill
        self.items_with_effect = items_with_effect
        self.teaching_items = teaching_items
        self.activated_stance = activated_stance
