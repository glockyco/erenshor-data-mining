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
    created_titles: tuple[str, ...] = ()


def rollback_repo_pages(
    *,
    manifest: RepoWikiPageManifest,
    repo_root: Path,
    client: WikiRollbackClient,
    summary: str,
    assertion: EditAssertion,
    assert_user: str | None = None,
    force: bool = False,
) -> RollbackResult:
    """Restore previous page text recorded by a deploy manifest.

    Rollback refuses to overwrite a page that has changed since the deploy it is
    undoing: if the live revision no longer matches the revision the deploy
    created, restoring would silently discard an intervening edit. Pass
    ``force=True`` to restore anyway.
    """
    entries: list[RollbackResultEntry] = []
    created_titles: list[str] = []
    for entry in manifest.entries:
        if entry.deploy_action == "created":
            # The deploy created this page, so its prior state was non-existence.
            # The deploy bot has no delete right, so report it for manual deletion
            # rather than editing it to an empty or stale body.
            created_titles.append(entry.title)
            continue
        if entry.rollback_text_source is None:
            continue

        rollback_text = (repo_root / entry.rollback_text_source).read_text(encoding="utf-8")
        base_revision = client.get_page_revision_metadata(entry.title, assertion=assertion, assert_user=assert_user)
        if base_revision is None:
            raise ValueError(f"Cannot roll back missing repo-owned page: {entry.title}")

        if not force and entry.new_revision_id is not None and base_revision.revision_id != entry.new_revision_id:
            raise ValueError(
                f"Page changed since deploy: {entry.title} is at revision {base_revision.revision_id} "
                f"but the deploy left revision {entry.new_revision_id}. "
                f"Re-deploy or pass force to roll back anyway."
            )

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
    return RollbackResult(entries=tuple(entries), created_titles=tuple(created_titles))
