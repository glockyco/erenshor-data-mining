"""Replacement of the generated table on an overview page.

The ``Weapons`` and ``Armor`` overview pages hold one generated table among
text that editors write. Regeneration replaces that table and nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mwparserfromhell.nodes import Tag

from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from mwparserfromhell.wikicode import Wikicode


class GeneratedTableError(ValueError):
    """Raised when a page does not hold exactly one table with the generated header."""


def replace_generated_table(old_wikitext: str, new_wikitext: str) -> str:
    """Replace the live table that has the generated header with the generated table.

    The generated text is one table. The header row identifies it: the kind
    and the text of each cell in the first row. Cell attributes do not count,
    so an editor can restyle the header. The text and the other tables of the
    live page stay unchanged.

    Raises:
        GeneratedTableError: The generated text is not one table, or the live
            page has no table or several tables with the generated header.
    """
    parser = TemplateParser()
    new_tables = _tables(parser.parse(new_wikitext))
    if len(new_tables) != 1:
        raise GeneratedTableError(f"The generated text holds {len(new_tables)} tables instead of one.")
    header = _header(new_tables[0])

    old_code = parser.parse(old_wikitext)
    matches = [table for table in _tables(old_code) if _header(table) == header]
    if not matches:
        labels = ", ".join(label for _, label in header)
        raise GeneratedTableError(
            f"The live page has no table with the generated header ({labels}). "
            "Make the header of the live table equal to the generated header."
        )
    if len(matches) > 1:
        raise GeneratedTableError(
            f"The live page has {len(matches)} tables with the generated header. Keep only the generated table."
        )
    old_code.replace(matches[0], str(new_tables[0]))
    return parser.render(old_code)


def _tables(code: Wikicode) -> list[Tag]:
    return [node for node in code.filter_tags(recursive=True) if _name(node) == "table"]


def _header(table: Tag) -> tuple[tuple[str, str], ...]:
    """Return the kind and text of each cell in the first row of a table."""
    cells: list[Tag] = []
    for node in table.contents.nodes:
        if not isinstance(node, Tag):
            continue
        if _name(node) == "tr":
            if not cells:
                cells = [cell for cell in node.contents.nodes if isinstance(cell, Tag) and _name(cell) in _CELLS]
            break
        if _name(node) in _CELLS:
            cells.append(node)
    return tuple((_name(cell), str(cell.contents).strip()) for cell in cells)


_CELLS = frozenset({"th", "td"})


def _name(tag: Tag) -> str:
    return str(tag.tag).strip().lower()
