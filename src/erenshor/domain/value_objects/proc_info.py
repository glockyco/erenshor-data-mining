"""Proc information value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.entities.spell import Spell
    from erenshor.domain.value_objects.wiki_link import AbilityLink

__all__ = ["ProcInfo"]


@dataclass
class ProcInfo:
    """Proc information for an item.

    Contains a pre-built link to the proc spell/skill, proc-specific metadata,
    and the full Spell entity for detailed tooltip display.

    proc_link is constructed at assembly time from spell.wiki_page_name,
    spell.display_name, and spell.image_name — no resolver lookup needed.
    The spell entity is retained to provide the 40+ stat fields rendered
    in the tooltip template.
    """

    proc_link: AbilityLink
    description: str  # Spell/skill description
    proc_chance: str  # Proc chance percentage as string (e.g., "75")
    proc_style: str  # Style: "Attack", "Bash", "Cast", "Worn", "Activatable"
    spell: Spell | None = None  # Full spell entity for detailed tooltip display
