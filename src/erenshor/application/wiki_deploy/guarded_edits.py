"""Write reviewed page texts with revision guards and a rollback manifest."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from os.path import relpath
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from erenshor.application.wiki_deploy.manifest import (
    ContentModel,
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    durable_write_text,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.pages import (
    capture_verified_parent,
    record_verification_receipt,
    remote_write_rejected,
    rollback_filename,
)
from erenshor.infrastructure.wiki import MediaWikiAPIError, MediaWikiEditConflictError
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki import MediaWikiPageRevision


class GuardedEditClient(Protocol):
    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        *,
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class GuardedPageEdit:
    """A reviewed new text for a page, bound to the revision it was planned from."""

    title: str
    summary: str
    content: str
    original: str
    revision: MediaWikiPageRevision
    content_model: ContentModel = "wikitext"


@dataclass(frozen=True, slots=True)
class GuardedEditResult:
    manifest_path: Path
    edited: tuple[str, ...]
    conflicts: tuple[str, ...]
    stopped: str | None

    @property
    def failed(self) -> bool:
        return bool(self.conflicts or self.stopped)


def apply_guarded_edits(
    edits: Sequence[GuardedPageEdit],
    *,
    repo_root: Path,
    run_dir: Path,
    client: GuardedEditClient,
    assert_user: str | None = None,
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
    variant: str | None = None,
    wiki_root: Path | None = None,
    assertion: Literal["user", "bot"] = "bot",
    stop_on_conflict: bool = False,
) -> GuardedEditResult:
    """Write a rollback manifest before editing and checkpoint each guarded write.

    A page that changed after its planned revision is a conflict and keeps its
    text. ``wiki rollback-repo-pages`` restores the edited pages from the
    manifest.
    """
    manifest_path = run_dir / "manifest.json"
    rollback_dir = run_dir / "rollback"
    planned_dir = run_dir / "planned"
    rollback_dir.mkdir(parents=True, exist_ok=False)
    planned_dir.mkdir()

    entries: list[RepoWikiPageManifestEntry] = []
    for edit in edits:
        filename = rollback_filename(edit.title)
        rollback_path = rollback_dir / filename
        planned_path = planned_dir / filename
        durable_write_text(rollback_path, edit.original)
        durable_write_text(planned_path, edit.content)
        entries.append(
            RepoWikiPageManifestEntry(
                title=edit.title,
                source_path=relpath(planned_path, repo_root),
                source_sha256=hashlib.sha256(edit.content.encode("utf-8")).hexdigest(),
                ownership_class="article",
                upload_stage="article",
                content_model=edit.content_model,
                old_revision_id=edit.revision.revision_id,
                old_revision_timestamp=edit.revision.timestamp,
                rollback_text_source=relpath(rollback_path, repo_root),
                rollback_content_model=edit.content_model,
            )
        )

    def save_manifest() -> None:
        manifest = RepoWikiPageManifest(
            entries=tuple(entries),
            api_url=getattr(client, "api_url", None),
            variant=variant,
            wiki_root=None if wiki_root is None else str(wiki_root.resolve()),
        )
        write_repo_page_manifest(manifest, manifest_path)
        if checkpoint is not None:
            checkpoint(manifest)

    save_manifest()

    edited: list[str] = []
    conflicts: list[str] = []
    stopped: str | None = None
    for index, edit in enumerate(edits):
        entries[index] = replace(
            entries[index],
            pending_mutation=True,
            pending_operation="deploy",
            pending_base_revision_id=edit.revision.revision_id,
            pending_acknowledged_revision_id=None,
        )
        save_manifest()
        try:
            revision_id = client.safe_edit_page(
                title=edit.title,
                content=edit.content,
                base_revision=edit.revision,
                summary=edit.summary,
                assertion=assertion,
                assert_user=assert_user,
                content_model=edit.content_model,
            )
        except MediaWikiEditVerificationError as error:
            entries[index] = record_verification_receipt(entries[index], error)
            save_manifest()
            entries[index] = capture_verified_parent(entries[index], error, repo_root)
            save_manifest()
            edited.append(edit.title)
            stopped = f"{edit.title}: {error}"
            break
        except MediaWikiEditConflictError as error:
            entries[index] = replace(entries[index], pending_mutation=False)
            save_manifest()
            conflicts.append(f"{edit.title}: {error}")
            if stop_on_conflict:
                break
            continue
        except MediaWikiAPIError as error:
            if remote_write_rejected(error):
                entries[index] = replace(entries[index], pending_mutation=False)
                save_manifest()
            stopped = f"{edit.title}: {error}"
            break
        if revision_id == edit.revision.revision_id:
            entries[index] = replace(entries[index], pending_mutation=False, deploy_action="unchanged")
            save_manifest()
            conflicts.append(f"{edit.title}: the page did not change")
            if stop_on_conflict:
                break
            continue
        entries[index] = replace(
            entries[index], new_revision_id=revision_id, deploy_action="edited", pending_mutation=False
        )
        save_manifest()
        edited.append(edit.title)
    return GuardedEditResult(manifest_path, tuple(edited), tuple(conflicts), stopped)
