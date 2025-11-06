"""Enriched skill data DTO."""

from erenshor.domain.entities.skill import Skill

__all__ = ["EnrichedSkillData"]


class EnrichedSkillData:
    """Enriched skill data with related entities.

    Contains raw skill data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        skill: Skill,
        items_with_effect: list[str],
        teaching_items: list[str],
    ) -> None:
        """Initialize enriched skill data.

        Args:
            skill: Skill entity
            items_with_effect: Item stable keys that grant this skill as an effect
            teaching_items: Item stable keys that teach this skill
        """
        self.skill = skill
        self.items_with_effect = items_with_effect
        self.teaching_items = teaching_items
