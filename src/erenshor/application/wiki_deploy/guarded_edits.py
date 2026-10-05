"""Write reviewed page texts with revision guards and a rollback manifest."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.pages import rollback_filename
from erenshor.infrastructure.wiki import MediaWikiAPIError, MediaWikiEditConflictError

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
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class GuardedPageEdit:
    """A reviewed new text for a page, bound to the revision it was planned from."""

    title: str
    summary: str
    content: str
    original: str
    revision: MediaWikiPageRevision


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
        rollback_path.write_text(edit.original, encoding="utf-8")
        planned_path.write_text(edit.content, encoding="utf-8")
        entries.append(
            RepoWikiPageManifestEntry(
                title=edit.title,
                source_path=planned_path.relative_to(repo_root).as_posix(),
                source_sha256=hashlib.sha256(edit.content.encode("utf-8")).hexdigest(),
                ownership_class="article",
                upload_stage="article",
                content_model="wikitext",
                declares_cargo_table=False,
                cargo_tables=(),
                old_revision_id=edit.revision.revision_id,
                old_revision_timestamp=edit.revision.timestamp,
                rollback_text_source=rollback_path.relative_to(repo_root).as_posix(),
            )
        )
    write_repo_page_manifest(RepoWikiPageManifest(entries=tuple(entries)), manifest_path)

    edited: list[str] = []
    conflicts: list[str] = []
    stopped: str | None = None
    for index, edit in enumerate(edits):
        try:
            revision_id = client.safe_edit_page(
                title=edit.title,
                content=edit.content,
                base_revision=edit.revision,
                summary=edit.summary,
                assertion="bot",
            )
        except MediaWikiEditConflictError as error:
            conflicts.append(f"{edit.title}: {error}")
            continue
        except MediaWikiAPIError as error:
            stopped = f"{edit.title}: {error}"
            break
        if revision_id == edit.revision.revision_id:
            conflicts.append(f"{edit.title}: the page did not change")
            continue
        entries[index] = replace(entries[index], new_revision_id=revision_id, deploy_action="edited")
        write_repo_page_manifest(RepoWikiPageManifest(entries=tuple(entries)), manifest_path)
        edited.append(edit.title)
    return GuardedEditResult(manifest_path, tuple(edited), tuple(conflicts), stopped)
