"""Typed link references for generated Lua data modules."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from erenshor.domain.value_objects.wiki_link import AbilityLink, ItemLink, QuestLink, StandardLink

if TYPE_CHECKING:
    from erenshor.domain.value_objects.wiki_link import WikiLink

LuaData = dict[str, object]


def link_ref(link: WikiLink, kind: str | None = None) -> LuaData | None:
    """Return a primitive typed reference table for a visible wiki link."""
    if link.page_title is None:
        return None
    ref: LuaData = {
        "kind": kind or _kind_for_link(link),
        "page": link.page_title,
        "text": link.display_name,
    }
    if isinstance(link, ItemLink) and link.stable_key:
        ref["stablekey"] = link.stable_key
    if link.image_name:
        ref["image"] = link.image_name
    return ref


def link_refs(links: Iterable[WikiLink], kind: str | None = None) -> list[LuaData]:
    """Return sorted visible typed references."""
    return [ref for link in sorted(links) if (ref := link_ref(link, kind)) is not None]


def _kind_for_link(link: WikiLink) -> str:
    if isinstance(link, ItemLink):
        return "item"
    if isinstance(link, AbilityLink):
        return "ability"
    if isinstance(link, QuestLink):
        return "quest"
    if isinstance(link, StandardLink):
        return "page"
    return "page"
