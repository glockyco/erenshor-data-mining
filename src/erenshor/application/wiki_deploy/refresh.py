"""Dependency-derived refresh of pages that transclude repo-owned templates/modules.

After repo-owned templates or data modules deploy, the pages that transclude
them keep stale link, category, and Cargo data until each dependent page is
reparsed. Template/module dependents are discovered through MediaWiki's
embeddedin API and purged with ``forcelinkupdate``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from loguru import logger

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
        logger.info(
            "Discovering pages transcluding {} in namespaces {}",
            dependency_title,
            ", ".join(str(namespace) for namespace in namespaces),
        )
        target_titles.update(
            client.get_embeddedin_pages(
                dependency_title,
                namespaces=namespaces,
                assertion=assertion,
                assert_user=assert_user,
            )
        )
        logger.info("Discovered {} unique embedded pages so far", len(target_titles))

    requested = tuple(sorted(target_titles))
    if not requested:
        return EmbeddedRefreshResult(requested=(), refreshed=())

    logger.info("Refreshing {} embedded pages with forced link updates", len(requested))
    refreshed = client.purge_pages(
        requested,
        force_link_update=True,
        assertion=assertion,
        assert_user=assert_user,
    )
    return EmbeddedRefreshResult(requested=requested, refreshed=tuple(refreshed))
