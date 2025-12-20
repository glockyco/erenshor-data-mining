"""Proc information value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.entities.spell import Spell

__all__ = ["ProcInfo"]


@dataclass
class ProcInfo:
    """Proc information for an item.

    Contains spell/skill stable key with proc-specific metadata.
    Template generators resolve the stable key to get ability name via resolver.

    The optional `spell` field contains the full Spell entity when available,
    enabling template generators to include all spell details (40+ fields)
    in the tooltip display.
    """

    stable_key: str  # Spell/skill stable key
    description: str  # Spell/skill description
    proc_chance: str  # Proc chance percentage as string (e.g., "75")
    proc_style: str  # Style: "Attack", "Bash", "Cast", "Worn", "Activatable"
    spell: Spell | None = None  # Full spell entity for detailed tooltip display
