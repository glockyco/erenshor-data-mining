"""Safe deployment of repo-owned wiki pages."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import quote

from erenshor.application.wiki_deploy.manifest import (
    DeployAction,
    RepoWikiPageManifest,
    validate_repo_page_manifest_for_deploy,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot

EditAssertion = Literal["user", "bot"]


class WikiPageDeployClient(Protocol):
    """MediaWiki operations required by repo page deployment."""

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
) -> RepoPageDeployResult:
    """Deploy changed manifest pages through the safe MediaWiki edit path.

    All source hashes, remote snapshots, and rollback sidecars are prepared before
    the first mutation. Every safe edit uses the revision returned alongside the
    source text it was compared with.
    """
    validate_repo_page_manifest_for_deploy(manifest, include_templates=include_templates)
    if not manifest.entries:
        return RepoPageDeployResult(entries=())
    titles = [entry.title for entry in manifest.entries]
    source_texts: dict[str, str] = {}
    for entry in manifest.entries:
        source_path = repo_root / entry.source_path
        source_bytes = source_path.read_bytes()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        if actual_hash != entry.source_sha256:
            raise ValueError(
                f"Source hash mismatch for {entry.title}: expected {entry.source_sha256}, got {actual_hash}"
            )
        source_texts[entry.title] = source_bytes.decode("utf-8")

    snapshots = client.get_page_snapshots(titles, assertion=assertion, assert_user=assert_user)
    prepared_entries = []
    for entry in manifest.entries:
        snapshot = snapshots.get(entry.title)
        if snapshot is None:
            raise ValueError(f"Missing page snapshot for requested title: {entry.title}")
        remote_text = snapshot.source_text
        source_text = source_texts[entry.title]
        changed = remote_text is None or normalize_saved_text(remote_text) != normalize_saved_text(source_text)
        rollback_text_source = None
        old_revision_id = None
        old_revision_timestamp = None
        if changed and remote_text is not None:
            if snapshot.revision is None:
                raise ValueError(f"Remote page snapshot has no revision: {entry.title}")
            old_revision_id = snapshot.revision.revision_id
            old_revision_timestamp = snapshot.revision.timestamp
            if rollback_root is not None:
                rollback_path = rollback_root / f"{_safe_title_filename(entry.title)}.wiki"
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
        if remote_text is not None and normalize_saved_text(remote_text) == normalize_saved_text(source_text):
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


def _safe_title_filename(title: str) -> str:
    """Return a deterministic, collision-free filename segment for a MediaWiki title.

    Percent-encoding every reserved character keeps the mapping injective (distinct
    titles never share a sidecar file) and flat (title slashes do not become path
    separators), unlike a lossy "replace reserved runs with underscore" scheme.
    """
    return quote(title, safe="")


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
