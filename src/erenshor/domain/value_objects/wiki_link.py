"""Wiki link value objects.

This module provides value objects for representing MediaWiki links with proper
separation of display name and page title, enabling correct alphabetical sorting
by display name rather than page title.

All link types support disambiguation where the display name differs from the page title.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WikiLink:
    """Base class for MediaWiki links.

    Attributes:
        page_title: Wiki page title (e.g., "The Duskenlight Ritual (Quest)")
                    If None, entity is excluded from wiki (renders as plain text)
        display_name: Display text shown to user (e.g., "The Duskenlight Ritual")
        image_name: Optional image filename (without .png extension)

    The display_name is used for sorting, while page_title is the actual wiki page.

    For excluded entities (page_title=None), __str__ returns plain display_name text
    without any link markup.
    """

    page_title: str | None
    display_name: str
    image_name: str | None = None

    def __str__(self) -> str:
        """Render as MediaWiki wikitext.

        Subclasses must implement this to return the appropriate wikitext format.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement __str__")

    def __lt__(self, other: object) -> bool:
        """Compare links by display name for sorting.

        Args:
            other: Another WikiLink instance

        Returns:
            True if this link's display name comes before other's alphabetically
        """
        if not isinstance(other, WikiLink):
            return NotImplemented
        return self.display_name < other.display_name


@dataclass(frozen=True)
class ItemLink(WikiLink):
    """Wiki link for items using {{ItemLink}} template.

    Format: {{ItemLink|PageTitle|image=ImageName.png|text=DisplayText}}

    Example:
        >>> link = ItemLink("Broken Key Blade (2)", "Broken Key Blade", "Broken Key Blade")
        >>> str(link)
        '{{ItemLink|Broken Key Blade (2)|image=Broken Key Blade.png|text=Broken Key Blade}}'

        >>> link = ItemLink("Sword", "Sword", "Sword")
        >>> str(link)
        '{{ItemLink|Sword}}'

        >>> link = ItemLink(None, "Excluded Item", None)
        >>> str(link)
        'Excluded Item'
    """

    def __str__(self) -> str:
        """Render as {{ItemLink}} template wikitext, or plain text if excluded."""
        # Excluded entity - return plain display name
        if self.page_title is None:
            return self.display_name

        params = []

        # Add image param if different from page title
        if self.image_name and self.image_name != self.page_title:
            img = self.image_name if self.image_name.endswith(".png") else f"{self.image_name}.png"
            params.append(f"image={img}")

        # Add text param if different from page title
        if self.display_name != self.page_title:
            params.append(f"text={self.display_name}")

        if params:
            return f"{{{{ItemLink|{self.page_title}|{'|'.join(params)}}}}}"
        return f"{{{{ItemLink|{self.page_title}}}}}"


@dataclass(frozen=True)
class AbilityLink(WikiLink):
    """Wiki link for spells/skills using {{AbilityLink}} template.

    Format: {{AbilityLink|PageTitle|image=ImageName.png|text=DisplayText}}

    Example:
        >>> link = AbilityLink("Fireball (Spell)", "Fireball", "Fireball")
        >>> str(link)
        '{{AbilityLink|Fireball (Spell)|text=Fireball}}'

        >>> link = AbilityLink("Heal", "Heal", None)
        >>> str(link)
        '{{AbilityLink|Heal}}'

        >>> link = AbilityLink(None, "Excluded Spell", None)
        >>> str(link)
        'Excluded Spell'
    """

    def __str__(self) -> str:
        """Render as {{AbilityLink}} template wikitext, or plain text if excluded."""
        # Excluded entity - return plain display name
        if self.page_title is None:
            return self.display_name

        params = []

        # Add image param if different from page title
        if self.image_name and self.image_name != self.page_title:
            img = self.image_name if self.image_name.endswith(".png") else f"{self.image_name}.png"
            params.append(f"image={img}")

        # Add text param if different from page title
        if self.display_name != self.page_title:
            params.append(f"text={self.display_name}")

        if params:
            return f"{{{{AbilityLink|{self.page_title}|{'|'.join(params)}}}}}"
        return f"{{{{AbilityLink|{self.page_title}}}}}"


@dataclass(frozen=True)
class QuestLink(WikiLink):
    """Wiki link for quests using {{QuestLink}} template.

    Format: {{QuestLink|link=PageTitle{{!}}DisplayName}} or {{QuestLink|PageTitle}}

    Example:
        >>> link = QuestLink("The Duskenlight Ritual (Quest)", "The Duskenlight Ritual", None)
        >>> str(link)
        '{{QuestLink|link=The Duskenlight Ritual (Quest){{!}}The Duskenlight Ritual}}'

        >>> link = QuestLink("Simple Quest", "Simple Quest", None)
        >>> str(link)
        '{{QuestLink|Simple Quest}}'

        >>> link = QuestLink(None, "Excluded Quest", None)
        >>> str(link)
        'Excluded Quest'
    """

    def __str__(self) -> str:
        """Render as {{QuestLink}} template wikitext, or plain text if excluded."""
        # Excluded entity - return plain display name
        if self.page_title is None:
            return self.display_name

        if self.display_name != self.page_title:
            return f"{{{{QuestLink|link={self.page_title}{{{{!}}}}{self.display_name}}}}}"
        return f"{{{{QuestLink|{self.page_title}}}}}"


@dataclass(frozen=True)
class StandardLink(WikiLink):
    """Standard MediaWiki link using [[Page|Display]] syntax.

    Used for characters, factions, and zones.

    Example:
        >>> link = StandardLink("A Brackish Croc", "Brackish Crocodile", None)
        >>> str(link)
        '[[A Brackish Croc|Brackish Crocodile]]'

        >>> link = StandardLink("Goblin", "Goblin", None)
        >>> str(link)
        '[[Goblin]]'

        >>> link = StandardLink(None, "Excluded Character", None)
        >>> str(link)
        'Excluded Character'
    """

    def __str__(self) -> str:
        """Render as [[Page]] or [[Page|Display]] wikitext, or plain text if excluded."""
        # Excluded entity - return plain display name
        if self.page_title is None:
            return self.display_name

        if self.display_name != self.page_title:
            return f"[[{self.page_title}|{self.display_name}]]"
        return f"[[{self.page_title}]]"


# Type aliases for clarity
CharacterLink = StandardLink
FactionLink = StandardLink
ZoneLink = StandardLink
