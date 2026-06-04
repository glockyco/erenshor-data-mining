"""Dependency-derived MediaWiki null edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki import MediaWikiPageRevision

EditAssertion = Literal["user", "bot"]


class WikiNullEditClient(Protocol):
    """MediaWiki operations required for dependency-derived null edits."""

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: tuple[int, ...],
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...

    def get_pages(self, titles: list[str]) -> dict[str, str | None]: ...

    def get_page_revision_metadata(
        self,
        title: str,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> MediaWikiPageRevision | None: ...

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: EditAssertion = "bot",
        assert_user: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class NullEditResultEntry:
    """Result for one null-edited page."""

    title: str
    old_revision_id: int
    old_revision_timestamp: str
    new_revision_id: int


@dataclass(frozen=True, slots=True)
class NullEditResult:
    """Result for a dependency-derived null-edit pass."""

    entries: tuple[NullEditResultEntry, ...]


def null_edit_embedded_pages(
    *,
    client: WikiNullEditClient,
    dependency_titles: tuple[str, ...],
    namespaces: tuple[int, ...],
    summary: str,
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> NullEditResult:
    """Null-edit pages discovered through reverse transclusion dependencies."""
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

    ordered_titles = sorted(target_titles)
    current_pages = client.get_pages(ordered_titles)
    entries: list[NullEditResultEntry] = []

    for title in ordered_titles:
        content = current_pages.get(title)
        if content is None:
            raise ValueError(f"Cannot null-edit missing dependency page: {title}")

        base_revision = client.get_page_revision_metadata(title, assertion=assertion, assert_user=assert_user)
        if base_revision is None:
            raise ValueError(f"Cannot null-edit missing dependency page revision: {title}")

        new_revision_id = client.safe_edit_page(
            title=title,
            content=content,
            base_revision=base_revision,
            summary=summary,
            assertion=assertion,
            assert_user=assert_user,
        )
        entries.append(
            NullEditResultEntry(
                title=title,
                old_revision_id=base_revision.revision_id,
                old_revision_timestamp=base_revision.timestamp,
                new_revision_id=new_revision_id,
            )
        )

    return NullEditResult(entries=tuple(entries))
