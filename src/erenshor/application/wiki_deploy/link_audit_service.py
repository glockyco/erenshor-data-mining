"""Orchestration for offline and read-only online semantic-link audits."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

from .link_audit import LinkAuditReport, LinkOccurrence, audit_links, parse_link_occurrences

if TYPE_CHECKING:
    from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
    from erenshor.infrastructure.wiki.client import MediaWikiClient, MediaWikiTitleStatus


_DATA_LINK_TITLE = "Module:Erenshor/Data/Links"
_TRACKING_CATEGORIES: tuple[str, ...] = (
    "Category:Pages with ambiguous Erenshor links",
    "Category:Pages with mismatched Erenshor link targets",
    "Category:Pages with unresolved Erenshor links",
)
_CATALOG_SHA_PATTERN = re.compile(
    r"(?:\[\s*[\"']catalogSha256[\"']\s*\]|[\"']catalogSha256[\"']|catalogSha256)"
    r"\s*[:=]\s*[\"']([0-9a-fA-F]{64})[\"']"
)


class _AuditClient(Protocol):
    """Read-only MediaWiki calls needed by :class:`LinkAuditService`."""

    def get_page(self, title: str) -> str | None: ...

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]: ...

    def get_title_statuses(self, titles: Sequence[str]) -> dict[str, MediaWikiTitleStatus]: ...

    def get_wanted_pages(self, namespace: int = 0) -> tuple[str, ...]: ...

    def get_linking_pages_by_title(self, titles: Sequence[str], namespace: int = 0) -> dict[str, tuple[str, ...]]: ...

    def get_category_members(self, title: str, namespace: int = 0) -> tuple[str, ...]: ...


def extract_catalog_sha256(source: str | None) -> str | None:
    """Extract a valid ``catalogSha256`` value from generated Lua source.

    Missing, non-text, and malformed values are deliberately represented as
    ``None`` so the core audit reports the single stale-catalog warning.
    """
    if not isinstance(source, str):
        return None
    match = _CATALOG_SHA_PATTERN.search(source)
    return match.group(1).lower() if match is not None else None


def _deterministic_unique(values: Collection[str] | Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=lambda value: (value.casefold(), value)))


class LinkAuditService:
    """Run the pure link audit with optional read-only MediaWiki enrichment."""

    def __init__(
        self,
        catalog_entries: Sequence[LinkCatalogEntry],
        client: MediaWikiClient | None = None,
    ) -> None:
        self._catalog_entries = tuple(catalog_entries)
        self._client = client

    @property
    def catalog_entries(self) -> tuple[LinkCatalogEntry, ...]:
        """Return the immutable catalog snapshot used by this service."""
        return self._catalog_entries

    def audit(
        self,
        generated_pages: Mapping[str, str],
        planned_titles: Collection[str],
        variant: str,
        online: bool,
        include_live_pages: bool = True,
        known_generated_titles: Collection[str] | None = None,
    ) -> LinkAuditReport:
        """Audit exact generated scope, optionally enriching it from MediaWiki."""
        if not online:
            return audit_links(
                generated_pages=generated_pages,
                catalog_entries=self._catalog_entries,
                planned_titles=planned_titles,
                known_generated_titles=known_generated_titles,
                variant=variant,
                remote_checked=False,
            )

        client = self._client
        if client is None:
            raise ValueError("Online link audit requires a MediaWikiClient")

        occurrences = self._generated_occurrences(generated_pages)
        target_titles = _deterministic_unique(
            tuple(
                target
                for occurrence in occurrences
                for target in (occurrence.canonical_target, occurrence.supplied_target)
                if target is not None
            )
        )
        title_statuses = client.get_title_statuses(target_titles)

        catalog_source = client.get_page(_DATA_LINK_TITLE)
        live_catalog_sha256 = extract_catalog_sha256(catalog_source)

        wanted_pages = _deterministic_unique(client.get_wanted_pages(namespace=0))
        linking_pages = client.get_linking_pages_by_title(wanted_pages, namespace=0)
        runtime_tracking_categories = {
            category: client.get_category_members(category, namespace=0) for category in _TRACKING_CATEGORIES
        }

        live_pages: dict[str, str] | None = None
        if include_live_pages:
            live_pages = {
                title: source
                for title, source in client.get_pages(_deterministic_unique(tuple(generated_pages))).items()
                if isinstance(source, str)
            }

        return audit_links(
            generated_pages=generated_pages,
            catalog_entries=self._catalog_entries,
            planned_titles=planned_titles,
            known_generated_titles=known_generated_titles,
            title_statuses=title_statuses,
            live_pages=live_pages,
            live_catalog_sha256=live_catalog_sha256,
            wanted_pages=wanted_pages,
            linking_pages=linking_pages,
            runtime_tracking_categories=runtime_tracking_categories,
            variant=variant,
            remote_checked=True,
        )

    def _generated_occurrences(self, generated_pages: Mapping[str, str]) -> tuple[LinkOccurrence, ...]:
        occurrences = tuple(
            occurrence
            for title in sorted(generated_pages, key=lambda value: (value.casefold(), value))
            for occurrence in parse_link_occurrences(title, generated_pages[title], self._catalog_entries)
        )
        return occurrences


__all__ = ["LinkAuditService", "extract_catalog_sha256"]


# Keep the constants available to focused integrations without making callers
# duplicate the category spellings owned by the Lua link modules.
DATA_LINK_TITLE = _DATA_LINK_TITLE
TRACKING_CATEGORIES = _TRACKING_CATEGORIES
