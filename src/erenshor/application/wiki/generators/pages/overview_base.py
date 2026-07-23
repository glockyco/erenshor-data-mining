"""Base class for overview page generators.

Overview pages are large wikitable data tables listing all items of a category
(weapons or armor) with their stats in sortable tables.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from erenshor.application.wiki.generators.base import PageGenerator
from erenshor.domain.value_objects.wiki_link import ClassLink

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext


class OverviewPageGeneratorBase(PageGenerator, ABC):
    """Base class for overview page generators.

    Overview pages are large tables listing all items of a certain category
    (weapons or armor) with their stats.
    """

    def __init__(self, context: GeneratorContext) -> None:
        """Initialize overview page generator.

        Args:
            context: Shared context with repositories and resolver
        """
        super().__init__(context)

    def _format_stat(self, value: int | float | None) -> str:
        """Format stat value for wiki table.

        Args:
            value: Stat value to format

        Returns:
            Formatted string:
            - Empty string for None or 0
            - Integer string for whole numbers
            - Float string (no trailing zeros) for decimals
            - Negative numbers use &minus; HTML entity

        Examples:
            >>> self._format_stat(None)
            ''
            >>> self._format_stat(0)
            ''
            >>> self._format_stat(10)
            '10'
            >>> self._format_stat(-5)
            '&minus;5'
            >>> self._format_stat(1.5)
            '1.5'
        """
        if value is None or value == 0:
            return ""

        # Convert to string
        if isinstance(value, float):
            # Remove trailing zeros
            if abs(value - int(value)) < 1e-9:
                s = str(int(value))
            else:
                s = f"{value:g}"
        else:
            s = str(value)

        # Replace minus sign with HTML entity
        if s.startswith("-"):
            s = "&minus;" + s[1:]

        return s

    def _format_classes(self, classes: list[str]) -> str:
        """Format class list as wiki links.

        Args:
            classes: List of class names

        Returns:
            Comma-separated semantic class links like:
            "{{ClassLink|stablekey=class:arcanist}},
            {{ClassLink|stablekey=class:druid}}"
            or empty string if no classes

        Examples:
            >>> self._format_classes(["Arcanist", "Druid"])
            '{{ClassLink|stablekey=class:arcanist}},
            {{ClassLink|stablekey=class:druid}}'
            >>> self._format_classes([])
            ''
        """
        if not classes:
            return ""

        # Sort and deduplicate by the internal class name.  ClassLink keeps the
        # internal name as the stable identity while rendering the mapped wiki
        # display name.
        unique_classes = sorted(set(classes), key=str.casefold)
        class_links = []
        for class_name in unique_classes:
            display_name = self.context.class_display.get_display_name(class_name)
            class_links.append(
                str(
                    ClassLink(
                        page_title=display_name,
                        display_name=display_name,
                        stable_key=f"class:{class_name.casefold()}",
                    )
                )
            )
        return ", ".join(class_links)
