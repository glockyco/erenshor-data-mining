"""Value objects for faction system."""

from dataclasses import dataclass

__all__ = ["FactionModifier"]


@dataclass(frozen=True)
class FactionModifier:
    """Faction relationship modifier for a character.

    Represents the reputation change that occurs when this character is killed.
    Positive values increase reputation (become more friendly), negative values
    decrease reputation (become more hostile).

    faction_display_name and faction_wiki_page_name are populated by the
    repository via JOIN on the factions table. Section generators construct
    a FactionLink from these fields — no resolver lookup needed.
    faction_wiki_page_name is None when the faction is excluded from the wiki.

    Example:
        >>> modifier = FactionModifier(
        ...     faction_stable_key="faction:guards",
        ...     modifier_value=-5,
        ...     faction_display_name="City Guards",
        ...     faction_wiki_page_name="City Guards",
        ... )
        >>> # Killing this character decreases Guards reputation by 5 points
    """

    faction_stable_key: str
    modifier_value: int
    faction_display_name: str
    faction_wiki_page_name: str | None  # None when faction is excluded from wiki
