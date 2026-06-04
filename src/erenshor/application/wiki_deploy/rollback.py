"""Manifest-backed rollback for repo-owned wiki pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest
    from erenshor.infrastructure.wiki import MediaWikiPageRevision

EditAssertion = Literal["user", "bot"]


class WikiRollbackClient(Protocol):
    """MediaWiki operations required by rollback."""

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
class RollbackResultEntry:
    """Rollback result for one repo-owned page."""

    title: str
    restored_revision_id: int | None
    new_revision_id: int


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """Rollback result for a deploy manifest."""

    entries: tuple[RollbackResultEntry, ...]


def rollback_repo_pages(
    *,
    manifest: RepoWikiPageManifest,
    repo_root: Path,
    client: WikiRollbackClient,
    summary: str,
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> RollbackResult:
    """Restore previous page text recorded by a deploy manifest."""
    entries: list[RollbackResultEntry] = []
    for entry in manifest.entries:
        if entry.rollback_text_source is None:
            continue

        rollback_text = (repo_root / entry.rollback_text_source).read_text(encoding="utf-8")
        base_revision = client.get_page_revision_metadata(entry.title, assertion=assertion, assert_user=assert_user)
        if base_revision is None:
            raise ValueError(f"Cannot roll back missing repo-owned page: {entry.title}")

        new_revision_id = client.safe_edit_page(
            title=entry.title,
            content=rollback_text,
            base_revision=base_revision,
            summary=summary,
            assertion=assertion,
            assert_user=assert_user,
        )
        entries.append(
            RollbackResultEntry(
                title=entry.title,
                restored_revision_id=entry.old_revision_id,
                new_revision_id=new_revision_id,
            )
        )

    return RollbackResult(entries=tuple(entries))
