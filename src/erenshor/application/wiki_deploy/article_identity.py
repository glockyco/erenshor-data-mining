"""Authoritative article identity maps for wiki override review."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class WikiPageEntity(Protocol):
    """Entity fields needed to map generated wiki pages to stable keys."""

    stable_key: str
    wiki_page_name: str | None


def build_article_identity_map(entities: Iterable[WikiPageEntity]) -> dict[str, tuple[str, ...]]:
    """Group entity stable keys by wiki page name.

    This mirrors the entity page generator's core contract: ``wiki_page_name``
    decides which exported stable-key entities belong on an article, and a null
    page name excludes the entity from article generation.
    """
    grouped: dict[str, list[str]] = {}
    for entity in entities:
        page_title = entity.wiki_page_name
        if page_title is None:
            continue
        grouped.setdefault(page_title, []).append(entity.stable_key)
    return {title: tuple(stable_keys) for title, stable_keys in grouped.items()}
