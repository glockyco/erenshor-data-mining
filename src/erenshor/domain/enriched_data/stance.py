"""Enriched stance data DTO."""

from erenshor.domain.entities.stance import Stance
from erenshor.domain.value_objects.wiki_link import AbilityLink

__all__ = ["EnrichedStanceData"]


class EnrichedStanceData:
    """Enriched stance data with related entities.

    Contains raw stance data plus skills that activate this stance.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        stance: Stance,
        activated_by_skills: list[AbilityLink],
    ) -> None:
        """Initialize enriched stance data.

        Args:
            stance: Stance entity
            activated_by_skills: Pre-built AbilityLink objects for skills that activate this stance
        """
        self.stance = stance
        self.activated_by_skills = activated_by_skills
