"""Dependency-derived refresh of pages that transclude repo-owned templates/modules.

After repo-owned templates or data modules deploy, the pages that transclude
them keep stale link, category, and Cargo data until each dependent page is
reparsed. This pass discovers those dependents through MediaWiki's embeddedin
API and forces a synchronous link/Cargo update on each via ``action=purge``
with ``forcelinkupdate``. A no-op edit is not used: MediaWiki treats identical
content as a non-change, performs no save, and therefore runs no LinksUpdate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

EditAssertion = Literal["user", "bot"]


class WikiEmbeddedRefreshClient(Protocol):
    """MediaWiki operations required to refresh transcluding pages."""

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...

    def purge_pages(
        self,
        titles: Sequence[str],
        force_link_update: bool = True,
        force_recursive_link_update: bool = False,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class EmbeddedRefreshResult:
    """Result of a dependency-derived refresh pass."""

    requested: tuple[str, ...]
    refreshed: tuple[str, ...]


def refresh_embedded_pages(
    *,
    client: WikiEmbeddedRefreshClient,
    dependency_titles: tuple[str, ...],
    namespaces: tuple[int, ...],
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> EmbeddedRefreshResult:
    """Refresh every page that transcludes any of the given dependencies."""
    target_titles: set[str] = set()
    for dependency_title in dependency_titles:
        target_titles.update(
            client.get_embeddedin_pages(
                dependency_title,
                namespaces=namespaces,
                assertion=assertion,
                assert_user=assert_user,
            )
        )

    requested = tuple(sorted(target_titles))
    if not requested:
        return EmbeddedRefreshResult(requested=(), refreshed=())

    refreshed = client.purge_pages(
        requested,
        force_link_update=True,
        assertion=assertion,
        assert_user=assert_user,
    )
    return EmbeddedRefreshResult(requested=requested, refreshed=tuple(refreshed))
