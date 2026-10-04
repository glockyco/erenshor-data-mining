"""Guarded application and rollback of reviewed historical pages."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage, LifecycleRename, LifecycleSplit
from erenshor.application.wiki_deploy.manifest import read_repo_page_manifest
from erenshor.application.wiki_deploy.retired_apply import apply_retired_edits, plan_retired_edits
from erenshor.application.wiki_deploy.retired_pages import RetiredPage, RetiredPageReport
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import MediaWikiEditConflictError, MediaWikiPageRevision, MediaWikiPageSnapshot


def _revision(title: str, revision_id: int) -> MediaWikiPageRevision:
    return MediaWikiPageRevision(title, 1, revision_id, "2026-10-04T00:00:00Z", "2026-10-04T01:00:00Z", "WoWBot")


def _review() -> tuple[ContentLifecycle, RetiredPageReport]:
    lifecycle = ContentLifecycle(
        pages={
            "Reckless": LifecyclePage(
                "Reckless",
                "stance:reckless",
                "removed",
                "stance",
                "Planar March",
                "2026-07-13",
                "https://notes.test",
                "notes",
            )
        },
        renames={"Old Book": LifecycleRename("Old Book", "item:book", "New Book", "identity")},
        splits={
            "Old Guard": LifecycleSplit("Old Guard", ("Fire Guard", "Ice Guard"), ("char:fire", "char:ice"), "split")
        },
    )
    texts = {
        "Reckless": "{{Stance|title=Reckless}}\nPeople wrote this paragraph.\n",
        "Old Book": "{{Item|title=Old Book}}\n",
        "Old Guard": "{{Character|name=Old Guard}}\n",
    }
    pages = (
        RetiredPage("Reckless", "stance:reckless", None, "removed notice", "pending notice"),
        RetiredPage("Old Book", "item:book", "New Book", "redirect", "pending redirect"),
        RetiredPage(
            "Old Guard", "char:fire, char:ice", "Fire Guard, Ice Guard", "disambiguation", "pending disambiguation"
        ),
    )
    snapshots = {
        title: MediaWikiPageSnapshot(title, text, _revision(title, 10), "2026-10-04T01:00:00Z")
        for title, text in texts.items()
    }
    return lifecycle, RetiredPageReport(checked=3, pages=pages, reviewed_non_bot=(), snapshots=snapshots)


def _wiki(report: RetiredPageReport) -> tuple[MagicMock, dict[str, str], dict[str, int]]:
    texts = {title: snapshot.source_text or "" for title, snapshot in report.snapshots.items()}
    revisions = dict.fromkeys(texts, 10)
    client = MagicMock()

    def edit(title, content, base_revision, **_kwargs):
        if revisions[title] != base_revision.revision_id:
            raise MediaWikiEditConflictError("The page changed after review")
        revisions[title] += 1
        texts[title] = content
        return revisions[title]

    client.safe_edit_page.side_effect = edit
    client.get_page_revision_metadata.side_effect = lambda title, **_kwargs: _revision(title, revisions[title])
    return client, texts, revisions


def test_planned_notice_redirect_and_split_text() -> None:
    lifecycle, report = _review()
    edits = plan_retired_edits(report, lifecycle)
    assert [edit.action for edit in edits] == ["redirect", "disambiguation", "notice"]
    planned = {edit.title: edit.content for edit in edits}
    assert planned["Reckless"] == (
        "{{Historical Content|state=removed|thing=stance|update=Planar March|date=July 13, 2026|url=https://notes.test}}\n"
        "{{Stance|title=Reckless}}\nPeople wrote this paragraph.\n"
    )
    assert planned["Old Book"] == "#REDIRECT [[New Book]]"
    assert planned["Old Guard"] == "Old Guard may refer to:\n\n* [[Fire Guard]]\n* [[Ice Guard]]\n\n__DISAMBIG__\n"


def test_outdated_notice_is_replaced_instead_of_repeated() -> None:
    fact = LifecyclePage("Holy Corpse", None, "unused", "character", None, None, None, "Chat names it", chat=True)
    lifecycle = ContentLifecycle(pages={"Holy Corpse": fact}, renames={}, splits={})
    text = "{{Historical Content|state=unused|thing=character}}\n{{Character|name=Holy Corpse}}\n\n[[Category:Enemies]]"
    report = RetiredPageReport(
        checked=1,
        pages=(
            RetiredPage(
                "Holy Corpse", None, None, "unused notice", "pending notice", "The notice has an outdated chat."
            ),
        ),
        reviewed_non_bot=(),
        snapshots={
            "Holy Corpse": MediaWikiPageSnapshot(
                "Holy Corpse", text, _revision("Holy Corpse", 10), "2026-10-04T01:00:00Z"
            )
        },
    )

    [edit] = plan_retired_edits(report, lifecycle)

    assert edit.content == (
        "{{Historical Content|state=unused|thing=character|chat=yes}}\n"
        "{{Character|name=Holy Corpse}}\n\n[[Category:Enemies]]"
    )


def test_unclean_or_incomplete_review_cannot_plan_a_write(tmp_path: Path) -> None:
    lifecycle, report = _review()
    unclean = RetiredPageReport(
        checked=report.checked,
        pages=(*report.pages, RetiredPage("Mystery", None, None, "review needed", "unexplained")),
        reviewed_non_bot=(),
        snapshots=report.snapshots,
    )
    with pytest.raises(ValueError, match="unexplained"):
        plan_retired_edits(unclean, lifecycle)
    incomplete = RetiredPageReport(report.checked, report.pages, (), {})
    with pytest.raises(ValueError, match="incomplete"):
        plan_retired_edits(incomplete, lifecycle)
    assert not (tmp_path / "retired-page-deploys").exists()


def test_changed_page_is_skipped_and_manifest_restores_written_pages(tmp_path: Path) -> None:
    lifecycle, report = _review()
    edits = plan_retired_edits(report, lifecycle)
    client, texts, revisions = _wiki(report)
    originals = texts.copy()
    revisions["Old Book"] = 11
    texts["Old Book"] = "An editor changed the book."

    run_dir = tmp_path / "wiki" / "retired-page-deploys" / "run"
    saved_edit = client.safe_edit_page.side_effect

    def observed_edit(title, content, base_revision, **kwargs):
        checkpoint = read_repo_page_manifest(run_dir / "manifest.json")
        assert len(checkpoint.entries) == 3
        if title == "Reckless":
            prior = {entry.title: entry for entry in checkpoint.entries}
            assert prior["Old Guard"].new_revision_id == 11
        return saved_edit(title, content, base_revision, **kwargs)

    client.safe_edit_page.side_effect = observed_edit
    result = apply_retired_edits(edits, repo_root=tmp_path, run_dir=run_dir, client=client)
    assert result.failed and result.stopped is None
    assert result.edited == ("Old Guard", "Reckless")
    assert result.conflicts == ("Old Book: The page changed after review",)
    assert texts["Old Book"] == "An editor changed the book."
    assert [call.kwargs["summary"] for call in client.safe_edit_page.call_args_list] == [
        "Redirect to the current title",
        "List the current versions",
        "Mark historical content",
    ]
    manifest = read_repo_page_manifest(result.manifest_path)
    by_title = {entry.title: entry for entry in manifest.entries}
    assert by_title["Old Book"].new_revision_id is None
    assert by_title["Old Guard"].new_revision_id == 11
    assert by_title["Reckless"].new_revision_id == 11
    assert (tmp_path / by_title["Reckless"].rollback_text_source).read_text() == originals["Reckless"]

    rolled_back = rollback_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Restore historical pages",
        assertion="bot",
    )
    assert {entry.title for entry in rolled_back.entries} == {"Old Guard", "Reckless"}
    assert texts["Old Guard"] == originals["Old Guard"]
    assert texts["Reckless"] == originals["Reckless"]
    assert texts["Old Book"] == "An editor changed the book."
