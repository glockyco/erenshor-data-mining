"""Plan and apply reviewed retired-page changes with revision and rollback guards."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from erenshor.application.wiki.lifecycle import render_split_disambiguation
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.pages import rollback_filename
from erenshor.infrastructure.wiki import MediaWikiAPIError, MediaWikiEditConflictError
from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage
    from erenshor.application.wiki_deploy.retired_pages import RetiredPageReport
    from erenshor.infrastructure.wiki import MediaWikiPageRevision

RetiredAction = Literal["notice", "redirect", "disambiguation"]
_SUMMARIES: dict[RetiredAction, str] = {
    "notice": "Mark historical content",
    "redirect": "Redirect to the current title",
    "disambiguation": "List the current versions",
}


class RetiredEditClient(Protocol):
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
class PendingRetiredEdit:
    title: str
    action: RetiredAction
    content: str
    original: str
    revision: MediaWikiPageRevision


@dataclass(frozen=True, slots=True)
class RetiredApplyResult:
    manifest_path: Path
    edited: tuple[str, ...]
    conflicts: tuple[str, ...]
    stopped: str | None

    @property
    def failed(self) -> bool:
        return bool(self.conflicts or self.stopped)


def _historical_notice(fact: LifecyclePage) -> str:
    params = [f"state={fact.state}", f"thing={fact.thing}"]
    if fact.update is not None:
        params.append(f"update={fact.update}")
    if fact.date is not None:
        release = date.fromisoformat(fact.date)
        params.append(f"date={release.strftime('%B')} {release.day}, {release.year}")
    if fact.patch_notes_url is not None:
        params.append(f"url={fact.patch_notes_url}")
    if fact.chat:
        params.append("chat=yes")
    return "{{Historical Content|" + "|".join(params) + "}}"


def _with_notice(title: str, source: str, notice: str) -> str:
    """Replace the page's one historical notice, or put the notice on the first line."""
    parser = TemplateParser()
    code = parser.parse(source)
    existing = parser.find_templates(code, ("Historical Content",))
    if len(existing) > 1:
        raise ValueError(f"{title!r} has more than one historical notice")
    if not existing:
        return f"{notice}\n{source}"
    code.replace(existing[0], notice)
    return str(code)


def plan_retired_edits(report: RetiredPageReport, lifecycle: ContentLifecycle) -> tuple[PendingRetiredEdit, ...]:
    """Plan only reviewed pending pages from their revision-bound audit text."""
    if report.has_errors:
        raise ValueError("Retired page review has unexplained titles. No pages were changed.")
    edits: list[PendingRetiredEdit] = []
    for page in (*report.pages, *report.reviewed_non_bot):
        if not page.state.startswith("pending"):
            continue
        snapshot = report.snapshots.get(page.title)
        if snapshot is None or snapshot.source_text is None or snapshot.revision is None:
            raise ValueError(f"Retired page review is incomplete for {page.title!r}")
        if page.state == "pending notice":
            fact = lifecycle.pages.get(page.title)
            if fact is None:
                raise ValueError(f"No reviewed notice exists for {page.title!r}")
            action: RetiredAction = "notice"
            content = _with_notice(page.title, snapshot.source_text, _historical_notice(fact))
        elif page.state == "pending redirect":
            rename = lifecycle.renames.get(page.title)
            if rename is None:
                raise ValueError(f"No reviewed redirect exists for {page.title!r}")
            action = "redirect"
            content = f"#REDIRECT [[{rename.current_title}]]"
        elif page.state == "pending disambiguation":
            split = lifecycle.splits.get(page.title)
            if split is None:
                raise ValueError(f"No reviewed split exists for {page.title!r}")
            action = "disambiguation"
            content = render_split_disambiguation(split)
        else:
            raise ValueError(f"Unknown pending disposition for {page.title!r}: {page.state}")
        edits.append(PendingRetiredEdit(page.title, action, content, snapshot.source_text, snapshot.revision))
    return tuple(sorted(edits, key=lambda edit: (edit.title.casefold(), edit.title)))


def apply_retired_edits(
    edits: Sequence[PendingRetiredEdit],
    *,
    repo_root: Path,
    run_dir: Path,
    client: RetiredEditClient,
) -> RetiredApplyResult:
    """Write a rollback manifest before editing and checkpoint each guarded write."""
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
                summary=_SUMMARIES[edit.action],
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
    return RetiredApplyResult(manifest_path, tuple(edited), tuple(conflicts), stopped)
