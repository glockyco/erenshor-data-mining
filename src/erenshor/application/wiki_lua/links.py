"""Typed link references for generated Lua data modules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from erenshor.application.wiki_lua.link_catalog import class_stable_key
from erenshor.domain.value_objects.wiki_link import (
    AbilityLink,
    CharacterLink,
    ClassLink,
    FactionLink,
    ItemLink,
    QuestLink,
    StandardLink,
    ZoneLink,
)

if TYPE_CHECKING:
    from erenshor.domain.value_objects.wiki_link import WikiLink

LuaData = dict[str, object]


def class_link_ref(internal_name: str, display_name: str) -> LuaData:
    """Return one class identity resolved through the shared link catalog."""
    canonical_page = display_name.strip()
    if not canonical_page:
        raise ValueError(f"Class {internal_name!r} has a blank display name")
    return {
        "kind": "class",
        "stablekey": class_stable_key(internal_name),
    }


def mapped_class_link_ref(internal_name: str, display_names: Mapping[str, str]) -> LuaData:
    """Return one class reference, failing when its catalog display name is absent."""
    try:
        display_name = display_names[internal_name]
    except KeyError as error:
        raise ValueError(f"Class {internal_name!r} has no display-name mapping") from error
    return class_link_ref(internal_name, display_name)


def class_link_refs(class_names: Iterable[str], display_names: Mapping[str, str]) -> list[LuaData]:
    """Return class references with their canonical display-name mappings."""
    return [mapped_class_link_ref(class_name, display_names) for class_name in class_names]


def link_ref(link: WikiLink, kind: str | None = None) -> LuaData | None:
    """Return a primitive typed reference table for a visible wiki link."""
    if link.page_title is None:
        return None
    ref_kind = kind or _kind_for_link(link)
    if link.stable_key and ref_kind != "page":
        return {
            "kind": ref_kind,
            "stablekey": link.stable_key,
        }

    ref: LuaData = {
        "kind": ref_kind,
        "page": link.page_title,
        "text": link.display_name,
    }
    if link.stable_key:
        ref["stablekey"] = link.stable_key
    if link.image_name:
        ref["image"] = link.image_name
    return ref


def link_refs(links: Iterable[WikiLink], kind: str | None = None) -> list[LuaData]:
    """Return sorted visible typed references."""
    return [ref for link in sorted(links) if (ref := link_ref(link, kind)) is not None]


_LINK_KIND_BY_TYPE = (
    (ItemLink, "item"),
    (AbilityLink, "ability"),
    (CharacterLink, "character"),
    (QuestLink, "quest"),
    (ZoneLink, "zone"),
    (FactionLink, "faction"),
    (ClassLink, "class"),
    (StandardLink, "page"),
)


def _kind_for_link(link: WikiLink) -> str:
    return next(
        (kind for link_type, kind in _LINK_KIND_BY_TYPE if isinstance(link, link_type)),
        "page",
    )
