"""Safe deployment of repo-owned wiki pages."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import quote

from erenshor.application.wiki_deploy.manifest import (
    DeployAction,
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    validate_repo_page_manifest_for_deploy,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot

EditAssertion = Literal["user", "bot"]


class WikiPageDeployClient(Protocol):
    """MediaWiki operations required by repo page deployment."""

    @property
    def edit_account(self) -> str: ...

    def get_page_snapshots(
        self,
        titles: list[str],
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]: ...

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

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: EditAssertion = "bot",
        assert_user: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class RepoPageDrift:
    """A target page whose latest revision is by another account and whose text differs from its source."""

    title: str
    revision_id: int
    user: str | None


class RepoPageDriftError(ValueError):
    """Raised before the first write when another account changed target pages."""

    def __init__(self, drift: Sequence[RepoPageDrift]) -> None:
        self.drift = tuple(drift)
        pages = ", ".join(
            f"{item.title} (revision {item.revision_id} by {item.user or 'a hidden user'})" for item in self.drift
        )
        super().__init__(f"Another account made the latest revision of pages that differ from the repository: {pages}")


def repo_page_action(snapshot: MediaWikiPageSnapshot, source_text: str) -> DeployAction:
    """Return what a deploy does with one page: create it, edit it, or leave it unchanged."""
    if snapshot.source_text is None:
        return "created"
    if normalize_saved_text(snapshot.source_text) == normalize_saved_text(source_text):
        return "unchanged"
    return "edited"


def read_repo_page_sources(manifest: RepoWikiPageManifest, repo_root: Path) -> dict[str, str]:
    """Return the source text of each manifest page, after checking its recorded hash."""
    source_texts: dict[str, str] = {}
    for entry in manifest.entries:
        source_bytes = (repo_root / entry.source_path).read_bytes()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        if actual_hash != entry.source_sha256:
            raise ValueError(
                f"Source hash mismatch for {entry.title}: expected {entry.source_sha256}, got {actual_hash}"
            )
        source_texts[entry.title] = source_bytes.decode("utf-8")
    return source_texts


def find_drift(
    entries: Sequence[RepoWikiPageManifestEntry],
    source_texts: Mapping[str, str],
    snapshots: Mapping[str, MediaWikiPageSnapshot],
    *,
    deploy_account: str,
    accepted: Collection[str] = (),
) -> tuple[RepoPageDrift, ...]:
    """Return the pages that a deploy would overwrite after another account's edit.

    A page drifted when its latest revision is by an account other than
    ``deploy_account`` and its text differs from the source. A page that
    ``accepted`` names was reviewed, so it is not drift.

    Raises:
        ValueError: The deploying account is unknown, or ``accepted`` names a
            page outside ``entries``.
    """
    if not deploy_account:
        raise ValueError("The deploying account is unknown. Set bot_username in the local configuration.")
    outside = sorted(set(accepted) - {entry.title for entry in entries})
    if outside:
        raise ValueError(f"Accepted drift names pages outside this deploy: {', '.join(outside)}")
    drift: list[RepoPageDrift] = []
    for entry in entries:
        snapshot = snapshots[entry.title]
        revision = snapshot.revision
        if revision is None or repo_page_action(snapshot, source_texts[entry.title]) != "edited":
            continue
        if revision.user != deploy_account and entry.title not in accepted:
            drift.append(RepoPageDrift(entry.title, revision.revision_id, revision.user))
    return tuple(drift)


@dataclass(frozen=True, slots=True)
class RepoPageDeployResultEntry:
    """Deployment result for one manifest page."""

    title: str
    status: DeployAction
    old_revision_id: int | None
    old_revision_timestamp: str | None
    new_revision_id: int | None
    rollback_text_source: str | None = None


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
    rollback_root: Path | None = None,
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
    known_live_titles: set[str] | None = None,
    accept_drift: Collection[str] = (),
) -> RepoPageDeployResult:
    """Deploy changed manifest pages through the safe MediaWiki edit path.

    All source hashes, remote snapshots, and rollback sidecars are prepared before
    the first mutation. Every safe edit uses the revision returned alongside the
    source text it was compared with. A page that another account changed and
    that ``accept_drift`` does not name stops the deploy before the first
    mutation (see ``find_drift``).

    Raises:
        RepoPageDriftError: Another account made the latest revision of pages
            that differ from their sources.
    """
    validate_repo_page_manifest_for_deploy(
        manifest,
        include_templates=include_templates,
        include_generated_data=include_generated_data,
        include_content_pages=include_content_pages,
        known_live_titles=known_live_titles,
    )
    if not manifest.entries:
        return RepoPageDeployResult(entries=())
    titles = [entry.title for entry in manifest.entries]
    source_texts = read_repo_page_sources(manifest, repo_root)

    snapshots = client.get_page_snapshots(titles, assertion=assertion, assert_user=assert_user)
    missing = [title for title in titles if title not in snapshots]
    if missing:
        raise ValueError(f"Missing page snapshot for requested title: {missing[0]}")
    drift = find_drift(
        manifest.entries, source_texts, snapshots, deploy_account=client.edit_account, accepted=accept_drift
    )
    if drift:
        raise RepoPageDriftError(drift)

    prepared_entries = []
    for entry in manifest.entries:
        snapshot = snapshots[entry.title]
        remote_text = snapshot.source_text
        changed = repo_page_action(snapshot, source_texts[entry.title]) != "unchanged"
        rollback_text_source = None
        old_revision_id = None
        old_revision_timestamp = None
        if changed and remote_text is not None:
            if snapshot.revision is None:
                raise ValueError(f"Remote page snapshot has no revision: {entry.title}")
            old_revision_id = snapshot.revision.revision_id
            old_revision_timestamp = snapshot.revision.timestamp
            if rollback_root is not None:
                rollback_path = rollback_root / rollback_filename(entry.title)
                rollback_path.parent.mkdir(parents=True, exist_ok=True)
                rollback_path.write_text(remote_text, encoding="utf-8")
                rollback_text_source = rollback_path.relative_to(repo_root).as_posix()
        prepared_entries.append(
            replace(
                entry,
                old_revision_id=old_revision_id,
                old_revision_timestamp=old_revision_timestamp,
                new_revision_id=None,
                new_revision_timestamp=None,
                rollback_text_source=rollback_text_source,
                deploy_action=None,
            )
        )

    prepared_manifest = RepoWikiPageManifest(entries=tuple(prepared_entries))
    if checkpoint is not None:
        checkpoint(prepared_manifest)

    result_entries: list[RepoPageDeployResultEntry] = []
    for entry, prepared_entry in zip(manifest.entries, prepared_manifest.entries, strict=True):
        snapshot = snapshots[entry.title]
        source_text = source_texts[entry.title]
        remote_text = snapshot.source_text
        if repo_page_action(snapshot, source_text) == "unchanged":
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="unchanged",
                    old_revision_id=None,
                    old_revision_timestamp=None,
                    new_revision_id=None,
                    rollback_text_source=None,
                )
            )
            continue

        if remote_text is None:
            new_revision_id = client.safe_create_page(
                title=entry.title,
                content=source_text,
                start_timestamp=snapshot.start_timestamp,
                summary=summary,
                assertion=assertion,
                assert_user=assert_user,
            )
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="created",
                    old_revision_id=None,
                    old_revision_timestamp=None,
                    new_revision_id=new_revision_id,
                    rollback_text_source=None,
                )
            )
        else:
            base_revision = snapshot.revision
            if base_revision is None:
                raise ValueError(f"Remote page snapshot has no revision: {entry.title}")
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
                    status="edited",
                    old_revision_id=prepared_entry.old_revision_id,
                    old_revision_timestamp=prepared_entry.old_revision_timestamp,
                    new_revision_id=new_revision_id,
                    rollback_text_source=prepared_entry.rollback_text_source,
                )
            )

        if checkpoint is not None:
            checkpoint(build_deployed_manifest(prepared_manifest, RepoPageDeployResult(entries=tuple(result_entries))))

    return RepoPageDeployResult(entries=tuple(result_entries))


def rollback_filename(title: str) -> str:
    """Return a deterministic, collision-free rollback file name for a MediaWiki title.

    Percent-encoding every reserved character keeps the mapping injective (distinct
    titles never share a sidecar file) and flat (title slashes do not become path
    separators), unlike a lossy "replace reserved runs with underscore" scheme.
    """
    return f"{quote(title, safe='')}.wiki"


def build_deployed_manifest(manifest: RepoWikiPageManifest, result: RepoPageDeployResult) -> RepoWikiPageManifest:
    """Merge deploy outcomes into the source manifest to produce a rollback manifest.
    Source-of-truth fields (title, source path, hash, ownership, Cargo metadata)
    are preserved; the revision IDs and rollback text source observed during the
    deploy are recorded so a later rollback can restore the prior page text.
    """
    result_by_title = {entry.title: entry for entry in result.entries}
    merged_entries = []
    for entry in manifest.entries:
        result_entry = result_by_title.get(entry.title)
        if result_entry is None:
            merged_entries.append(entry)
            continue
        merged_entries.append(
            replace(
                entry,
                old_revision_id=result_entry.old_revision_id,
                old_revision_timestamp=result_entry.old_revision_timestamp,
                new_revision_id=result_entry.new_revision_id,
                rollback_text_source=result_entry.rollback_text_source,
                deploy_action=result_entry.status,
            )
        )
    return RepoWikiPageManifest(entries=tuple(merged_entries))
