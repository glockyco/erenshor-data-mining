"""Proc information value object."""

from dataclasses import dataclass

__all__ = ["ProcInfo"]


@dataclass
class ProcInfo:
    """Proc information for an item.

    Contains spell/skill stable key with proc-specific metadata.
    Template generators resolve the stable key to get ability name via resolver.
    """

    stable_key: str  # Spell/skill stable key
    description: str  # Spell/skill description
    proc_chance: str  # Proc chance percentage as string (e.g., "75")
    proc_style: str  # Style: "Attack", "Bash", "Cast", "Worn", "Activatable"
