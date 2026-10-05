"""Plan and apply reviewed retired-page changes with revision and rollback guards."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from erenshor.application.wiki.lifecycle import render_split_disambiguation
from erenshor.application.wiki_deploy.guarded_edits import (
    GuardedEditClient,
    GuardedEditResult,
    GuardedPageEdit,
    apply_guarded_edits,
)
from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from pathlib import Path

    from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage
    from erenshor.application.wiki_deploy.retired_pages import RetiredPageReport
    from erenshor.infrastructure.wiki import MediaWikiPageRevision

RetiredAction = Literal["notice", "redirect", "disambiguation"]
_SUMMARIES: dict[RetiredAction, str] = {
    "notice": "Mark historical content",
    "redirect": "Redirect to the current title",
    "disambiguation": "List the current versions",
}


@dataclass(frozen=True, slots=True)
class PendingRetiredEdit:
    title: str
    action: RetiredAction
    content: str
    original: str
    revision: MediaWikiPageRevision


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
    client: GuardedEditClient,
) -> GuardedEditResult:
    """Write the retired-page edits with the summary of their action."""
    return apply_guarded_edits(
        [
            GuardedPageEdit(edit.title, _SUMMARIES[edit.action], edit.content, edit.original, edit.revision)
            for edit in edits
        ],
        repo_root=repo_root,
        run_dir=run_dir,
        client=client,
    )
