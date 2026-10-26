"""Manifest-backed rollback for deployed wiki pages."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from erenshor.application.wiki_deploy.pages import record_verification_receipt, remote_write_rejected
from erenshor.infrastructure.wiki import MediaWikiAPIError
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest
    from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot

EditAssertion = Literal["user", "bot"]


class WikiRollbackClient(Protocol):
    """MediaWiki operations required by rollback."""

    @property
    def edit_account(self) -> str: ...

    def get_page_snapshots(
        self,
        titles: list[str],
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]: ...

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
        *,
        bot: bool = True,
        assertion: EditAssertion = "bot",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class RollbackResultEntry:
    """Rollback result for one deployed page."""

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
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
) -> RollbackResult:
    """Restore previous page text recorded by a deploy manifest.

    Rollback refuses to overwrite a page that has changed since the deploy it is
    undoing: if the live revision no longer matches the revision the deploy
    created, restoring would silently discard an intervening edit. Pass
    ``force=True`` to restore anyway.
    """
    if manifest.api_url is not None and manifest.api_url != getattr(client, "api_url", None):
        raise ValueError("Rollback endpoint does not match the native manifest")
    manifest = recover_pending_mutations(
        manifest=manifest,
        repo_root=repo_root,
        client=client,
        assertion=assertion,
        assert_user=assert_user,
        checkpoint=checkpoint,
    )
    manifest_entries = list(manifest.entries)

    def save_manifest() -> None:
        if checkpoint is not None:
            checkpoint(replace(manifest, entries=tuple(manifest_entries)))

    entries: list[RollbackResultEntry] = []
    created_titles: list[str] = []
    for index, entry in enumerate(manifest.entries):
        if entry.rollback_revision_id is not None:
            continue
        if entry.deploy_action == "created":
            # The deploy created this page, so its prior state was non-existence.
            # The deploy bot has no delete right, so report it for manual deletion
            # rather than editing it to an empty or stale body.
            created_titles.append(entry.title)
            continue
        if entry.rollback_text_source is None or entry.new_revision_id is None:
            # An entry without a receipt and without a pending request never wrote.
            continue
        if entry.requires_rollback and not entry.rollback_content_model:
            raise ValueError(
                f"Cannot restore verified-write failure without its actual parent content model: {entry.title}"
            )

        rollback_text = (repo_root / entry.rollback_text_source).read_bytes().decode("utf-8")
        base_revision = client.get_page_revision_metadata(entry.title, assertion=assertion, assert_user=assert_user)
        if base_revision is None:
            raise ValueError(f"Cannot roll back missing page: {entry.title}")

        if not force and base_revision.revision_id != entry.new_revision_id:
            raise ValueError(
                f"Page changed since deploy: {entry.title} is at revision {base_revision.revision_id} "
                f"but the deploy left revision {entry.new_revision_id}. "
                f"Re-deploy or pass force to roll back anyway."
            )

        manifest_entries[index] = replace(
            entry,
            pending_mutation=True,
            pending_operation="rollback",
            pending_base_revision_id=base_revision.revision_id,
            pending_acknowledged_revision_id=None,
        )
        save_manifest()
        try:
            new_revision_id = client.safe_edit_page(
                title=entry.title,
                content=rollback_text,
                base_revision=base_revision,
                summary=summary,
                assertion=assertion,
                assert_user=assert_user,
                content_model=entry.rollback_content_model,
            )
        except MediaWikiEditVerificationError as error:
            manifest_entries[index] = record_verification_receipt(manifest_entries[index], error)
            save_manifest()
            raise
        except MediaWikiAPIError as error:
            if remote_write_rejected(error):
                manifest_entries[index] = replace(manifest_entries[index], pending_mutation=False)
                save_manifest()
            raise
        manifest_entries[index] = replace(
            manifest_entries[index],
            pending_mutation=False,
            rollback_revision_id=new_revision_id,
            requires_rollback=False,
        )
        save_manifest()
        entries.append(
            RollbackResultEntry(
                title=entry.title,
                restored_revision_id=entry.old_revision_id,
                new_revision_id=new_revision_id,
            )
        )
    return RollbackResult(entries=tuple(entries), created_titles=tuple(created_titles))


def recover_pending_mutations(
    *,
    manifest: RepoWikiPageManifest,
    repo_root: Path,
    client: WikiRollbackClient,
    assertion: EditAssertion,
    assert_user: str | None = None,
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
) -> RepoWikiPageManifest:
    """Reconcile uncertain writes only from revision-bound source and account evidence."""
    pending = [entry.title for entry in manifest.entries if entry.pending_mutation]
    if not pending:
        return manifest
    if manifest.api_url is not None and manifest.api_url != getattr(client, "api_url", None):
        raise ValueError("Recovery endpoint does not match the native manifest")
    snapshots = client.get_page_snapshots(pending, assertion=assertion, assert_user=assert_user)
    entries = list(manifest.entries)
    for index, entry in enumerate(entries):
        if not entry.pending_mutation:
            continue
        if entry.pending_operation is None or entry.pending_base_revision_id is None:
            raise ValueError(f"Cannot reconcile pending remote mutation without durable request intent: {entry.title}")
        snapshot = snapshots[entry.title]
        revision = snapshot.revision
        current_revision_id = 0 if revision is None else revision.revision_id
        if (
            entry.pending_acknowledged_revision_id is not None
            and current_revision_id != entry.pending_acknowledged_revision_id
        ):
            raise ValueError(f"Cannot reconcile pending remote mutation after its acknowledged revision: {entry.title}")
        if current_revision_id == entry.pending_base_revision_id:
            raise ValueError(f"Cannot settle pending remote mutation from an unchanged base: {entry.title}")
        if entry.pending_operation == "deploy":
            source = (repo_root / entry.source_path).read_bytes()
            if hashlib.sha256(source).hexdigest() != entry.source_sha256:
                raise ValueError(f"Cannot reconcile pending remote mutation with changed source: {entry.title}")
            expected_text = source.decode("utf-8")
        else:
            if entry.rollback_text_source is None:
                raise ValueError(f"Cannot reconcile pending rollback without preimage: {entry.title}")
            expected_text = (repo_root / entry.rollback_text_source).read_bytes().decode("utf-8")
        expected_model = entry.content_model if entry.pending_operation == "deploy" else entry.rollback_content_model
        if (
            revision is None
            or revision.parent_revision_id is None
            or revision.parent_revision_id != entry.pending_base_revision_id
            or not client.edit_account
            or revision.user != client.edit_account
            or snapshot.source_text is None
            or expected_model is None
            or snapshot.content_model != expected_model
            or normalize_saved_text(snapshot.source_text) != normalize_saved_text(expected_text)
        ):
            raise ValueError(f"Cannot reconcile pending remote mutation. Inspect live revisions: {entry.title}")
        if entry.pending_operation == "deploy":
            entries[index] = replace(
                entry,
                pending_mutation=False,
                new_revision_id=revision.revision_id,
                new_revision_timestamp=revision.timestamp,
                deploy_action="created" if entry.old_revision_id is None else "edited",
            )
        else:
            entries[index] = replace(
                entry, pending_mutation=False, rollback_revision_id=revision.revision_id, requires_rollback=False
            )
        manifest = replace(manifest, entries=tuple(entries))
        if checkpoint is not None:
            checkpoint(manifest)
    return manifest
