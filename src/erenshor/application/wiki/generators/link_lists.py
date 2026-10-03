"""Generated link lists that show each linked page and label once.

Several entities can share one page and one label, such as the three variants of
A Highwayman Raider. A reader sees one entry for them, so a generated list shows
one entry for each page and label. The entry links the first member of its
group. The stable key of that member resolves to the same page and label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from erenshor.domain.value_objects.wiki_link import WikiLink

Row = TypeVar("Row")

RANGE_DASH = "\u2013"
"""En dash between the lowest and highest chance of a range."""


def group_by_page_and_label(rows: Iterable[Row], link: Callable[[Row], WikiLink]) -> list[list[Row]]:
    """Group rows whose links show the same page and label, in the order of their first rows."""
    groups: dict[tuple[str | None, str], list[Row]] = {}
    for row in rows:
        row_link = link(row)
        groups.setdefault((row_link.page_title, row_link.display_name), []).append(row)
    return list(groups.values())


def format_links(links: Iterable[WikiLink]) -> str:
    """Join one link for each page and label, in the given order."""
    groups = group_by_page_and_label(links, lambda link: link)
    return WIKITEXT_LINE_SEPARATOR.join(str(group[0]) for group in groups)


def format_visible_links(links: Iterable[WikiLink]) -> str:
    """Join one link for each page and label, sorted by label, without links that have no page."""
    return format_links(sorted(link for link in links if link.page_title is not None))


def format_chance(chances: Sequence[float], decimals: int) -> str:
    """Return a chance, or its lowest and highest value when they differ at this precision."""
    low = f"{min(chances):.{decimals}f}"
    high = f"{max(chances):.{decimals}f}"
    return f"{high}%" if low == high else f"{low}{RANGE_DASH}{high}%"


def format_chance_links(rows: Iterable[tuple[WikiLink, float]], decimals: int) -> str:
    """Join one ``link (chance)`` entry for each page and label, in the order of their first rows."""
    groups = group_by_page_and_label(rows, lambda row: row[0])
    return WIKITEXT_LINE_SEPARATOR.join(
        f"{group[0][0]} ({format_chance([chance for _, chance in group], decimals)})" for group in groups
    )
