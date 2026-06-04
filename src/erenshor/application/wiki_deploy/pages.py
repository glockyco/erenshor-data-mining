"""Safe deployment of repo-owned wiki pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest
    from erenshor.infrastructure.wiki import MediaWikiPageRevision

DeployStatus = Literal["unchanged", "changed"]
EditAssertion = Literal["user", "bot"]


class WikiPageDeployClient(Protocol):
    """MediaWiki operations required by repo page deployment."""

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
class RepoPageDeployResultEntry:
    """Deployment result for one manifest page."""

    title: str
    status: DeployStatus
    old_revision_id: int | None
    old_revision_timestamp: str | None
    new_revision_id: int | None


@dataclass(frozen=True, slots=True)
class RepoPageDeployResult:
    """Deployment result for a repo-owned page manifest."""

    entries: tuple[RepoPageDeployResultEntry, ...]


def deploy_repo_pages(
    *,
    manifest: RepoWikiPageManifest,
    repo_root: Path,
    client: WikiPageDeployClient,
    summary: str,
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> RepoPageDeployResult:
    """Deploy changed manifest pages through the safe MediaWiki edit path."""
    titles = [entry.title for entry in manifest.entries]
    current_pages = client.get_pages(titles)
    result_entries: list[RepoPageDeployResultEntry] = []

    for entry in manifest.entries:
        source_text = (repo_root / entry.source_path).read_text(encoding="utf-8")
        if current_pages.get(entry.title) == source_text:
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="unchanged",
                    old_revision_id=None,
                    old_revision_timestamp=None,
                    new_revision_id=None,
                )
            )
            continue

        base_revision = client.get_page_revision_metadata(entry.title, assertion=assertion, assert_user=assert_user)
        if base_revision is None:
            raise ValueError(f"Cannot safely deploy missing repo-owned page without base revision: {entry.title}")

        new_revision_id = client.safe_edit_page(
            title=entry.title,
            content=source_text,
            base_revision=base_revision,
            summary=summary,
            assertion=assertion,
            assert_user=assert_user,
        )
        result_entries.append(
            RepoPageDeployResultEntry(
                title=entry.title,
                status="changed",
                old_revision_id=base_revision.revision_id,
                old_revision_timestamp=base_revision.timestamp,
                new_revision_id=new_revision_id,
            )
        )

    return RepoPageDeployResult(entries=tuple(result_entries))
