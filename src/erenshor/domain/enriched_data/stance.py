"""Enriched stance data DTO."""

from erenshor.domain.entities.stance import Stance

__all__ = ["EnrichedStanceData"]


class EnrichedStanceData:
    """Enriched stance data with related entities.

    Contains raw stance data plus skills that activate this stance.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        stance: Stance,
        activated_by_skills: list[str],
    ) -> None:
        """Initialize enriched stance data.

        Args:
            stance: Stance entity
            activated_by_skills: Skill stable keys that activate this stance
        """
        self.stance = stance
        self.activated_by_skills = activated_by_skills
