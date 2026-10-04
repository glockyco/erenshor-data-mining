"""Behavior of the read-only retired article review."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.lifecycle import (
    ContentLifecycle,
    LifecyclePage,
    LifecycleRename,
    LifecycleSplit,
    render_split_disambiguation,
)
from erenshor.application.wiki_deploy.retired_pages import audit_retired_pages
from erenshor.infrastructure.wiki.client import MediaWikiPageRevision, MediaWikiPageSnapshot, MediaWikiTitleStatus


def _lifecycle() -> ContentLifecycle:
    return ContentLifecycle(
        pages={
            "Reckless": LifecyclePage(
                "Reckless",
                "skill:reckless",
                "removed",
                "stance",
                "Planar March",
                "2026-07-13",
                "https://notes.test",
                "notes",
            )
        },
        renames={"Skill Book: Old": LifecycleRename("Skill Book: Old", "item:book", "Skill Book: New", "identity")},
        splits={},
    )


def _client(pages: dict[str, str | None], created: tuple[str, ...]) -> MagicMock:
    client = MagicMock()
    client.list_user_created_pages.return_value = created
    client.get_title_statuses.side_effect = lambda titles: {
        title: MediaWikiTitleStatus(title, title, None, pages.get(title, "generated target") is not None)
        for title in titles
    }

    def snapshots(titles: list[str]) -> dict[str, MediaWikiPageSnapshot]:
        result = {}
        for title in titles:
            source = pages[title]
            revision = (
                MediaWikiPageRevision(title, 1, 10, "2026-10-04T00:00:00Z", "2026-10-04T01:00:00Z", "WoWBot")
                if source is not None
                else None
            )
            result[title] = MediaWikiPageSnapshot(title, source, revision, "2026-10-04T01:00:00Z")
        return result

    client.get_page_snapshots.side_effect = snapshots
    return client


def test_person_created_page_is_not_reported() -> None:
    client = _client(
        {
            "Reckless": "{{Ability|stablekey=skill:reckless}}",
            "Skill Book: Old": "{{Item|stablekey=item:book}}",
            "Person's Article": "Handwritten work",
        },
        ("Current", "Reckless"),
    )
    report = audit_retired_pages(
        client,
        {"Current": "{{Item|stablekey=item:current}}", "Skill Book: New": "{{Item|stablekey=item:book}}"},
        _lifecycle(),
    )
    assert [page.title for page in report.pages] == ["Reckless"]
    assert [page.title for page in report.reviewed_non_bot] == ["Skill Book: Old"]
    assert report.unexplained == 0


def test_rename_uses_stable_key_and_reports_pending_then_resolved() -> None:
    pages = {"Skill Book: Old": "{{Item|stablekey=item:book}}"}
    client = _client(pages, ("Skill Book: Old",))
    generated = {"Skill Book: New": "{{Item|stablekey=item:book}}"}
    lifecycle = ContentLifecycle(pages={}, renames=_lifecycle().renames, splits={})
    pending = audit_retired_pages(client, generated, lifecycle)
    assert (pending.pages[0].current_title, pending.pages[0].state) == ("Skill Book: New", "pending redirect")

    client.get_title_statuses.side_effect = lambda titles: {
        title: MediaWikiTitleStatus(title, title, "Skill Book: New" if title == "Skill Book: Old" else None, True)
        for title in titles
    }
    pages["Skill Book: Old"] = "#REDIRECT [[Skill Book: New]]"
    resolved = audit_retired_pages(client, generated, lifecycle)
    assert resolved.pages[0].state == "redirect"

    client.get_title_statuses.side_effect = lambda titles: {
        title: MediaWikiTitleStatus(title, title, None, title != "Skill Book: New") for title in titles
    }
    assert audit_retired_pages(client, generated, lifecycle).pages[0].state == "unexplained"


def test_removed_notice_is_pending_then_marked() -> None:
    pages = {"Reckless": "{{Ability|stablekey=skill:reckless}}"}
    client = _client(pages, ("Reckless",))
    lifecycle = ContentLifecycle(pages=_lifecycle().pages, renames={}, splits={})
    assert audit_retired_pages(client, {}, lifecycle).pages[0].state == "pending notice"
    pages["Reckless"] += (
        "\n{{Historical Content|state=removed|thing=stance|update=Planar March"
        "|date=July 13, 2026|url=https://notes.test}}"
    )
    report = audit_retired_pages(client, {}, lifecycle)
    assert report.pages[0].state == "marked"
    assert report.pending == 0


def test_unused_page_has_pending_and_marked_states() -> None:
    fact = LifecyclePage("Queen Evadne", None, "unused", "character", None, None, None, "No live spawn")
    lifecycle = ContentLifecycle(pages={"Queen Evadne": fact}, renames={}, splits={})
    pages = {"Queen Evadne": "{{Character|name=Queen Evadne}}"}
    client = _client(pages, ("Queen Evadne",))
    pending = audit_retired_pages(client, {}, lifecycle)
    assert pending.pages[0].expected == "unused notice"
    assert pending.pages[0].state == "pending notice"

    pages["Queen Evadne"] += "\n{{Historical Content|state=unused|thing=character}}"
    marked = audit_retired_pages(client, {}, lifecycle)
    assert marked.pages[0].state == "marked"
    assert marked.unexplained == 0


def test_split_requires_both_links_without_an_infobox() -> None:
    split = LifecycleSplit("Old Guard", ("Fire Guard", "Ice Guard"), ("character:fire", "character:ice"), "split")
    lifecycle = ContentLifecycle(pages={}, renames={}, splits={"Old Guard": split})
    pages = {"Old Guard": "{{Character|name=Old Guard}}"}
    client = _client(pages, ("Old Guard",))
    generated = {
        "Fire Guard": "{{Character|stablekey=character:fire}}",
        "Ice Guard": "{{Character|stablekey=character:ice}}",
    }
    pending = audit_retired_pages(client, generated, lifecycle)
    assert pending.pages[0].state == "pending disambiguation"
    assert pending.pages[0].current_title == "Fire Guard, Ice Guard"

    pages["Old Guard"] = render_split_disambiguation(split)
    resolved = audit_retired_pages(client, generated, lifecycle)
    assert resolved.pages[0].state == "disambiguation"
    assert resolved.pending == 0

    pages["Old Guard"] += "{{Character|name=Old Guard}}"
    assert audit_retired_pages(client, generated, lifecycle).pages[0].state == "pending disambiguation"
    pages["Old Guard"] = render_split_disambiguation(split)
    client.get_title_statuses.side_effect = lambda titles: {
        title: MediaWikiTitleStatus(title, title, None, title != "Ice Guard") for title in titles
    }
    missing_target = audit_retired_pages(client, generated, lifecycle)
    assert missing_target.pages[0].state == "unexplained"
    assert missing_target.pages[0].reason == "The reviewed target Ice Guard is not live."


def test_unexplained_and_invalid_dispositions_fail() -> None:
    client = _client({"Mystery": "{{Item|stablekey=item:unknown}}"}, ("Mystery",))
    report = audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}, splits={}))
    assert report.has_errors and report.unexplained == 1
    assert report.pages[0].title == "Mystery"

    two_notices = "{{Historical Content|state=removed|thing=stance}}\n{{Historical Content|state=removed|thing=stance}}"
    client = _client({"Reckless": two_notices}, ("Reckless",))
    report = audit_retired_pages(client, {}, ContentLifecycle(pages=_lifecycle().pages, renames={}, splits={}))
    assert report.has_errors and report.pages[0].reason == "The page has more than one historical notice."


def test_notice_that_differs_from_the_facts_is_pending_until_it_matches() -> None:
    fact = LifecyclePage("Queen Evadne", None, "unused", "character", None, None, None, "Chat names her", chat=True)
    lifecycle = ContentLifecycle(pages={"Queen Evadne": fact}, renames={}, splits={})
    pages = {"Queen Evadne": "{{Historical Content|state=unused|thing=character}}\n{{Character|name=Queen Evadne}}"}
    client = _client(pages, ("Queen Evadne",))
    outdated = audit_retired_pages(client, {}, lifecycle)
    assert (outdated.pages[0].state, outdated.pages[0].reason) == ("pending notice", "The notice has an outdated chat.")
    assert not outdated.has_errors

    pages["Queen Evadne"] = (
        "{{Historical Content|state=unused|thing=character|chat=yes}}\n{{Character|name=Queen Evadne}}"
    )
    assert audit_retired_pages(client, {}, lifecycle).pages[0].state == "marked"


def test_unreviewed_rename_names_matching_generated_identity() -> None:
    client = _client({"Old Book": "{{Item|stablekey=item:book}}"}, ("Old Book",))
    report = audit_retired_pages(
        client,
        {"New Book": "{{Item|stablekey=item:book}}"},
        ContentLifecycle(pages={}, renames={}, splits={}),
    )
    assert report.pages[0].current_title == "New Book"
    assert report.pages[0].state == "unexplained"


def test_incomplete_title_or_source_results_fail_closed() -> None:
    client = _client({"Lost": "{{Item}}"}, ("Lost",))
    client.get_title_statuses.side_effect = None
    client.get_title_statuses.return_value = {}
    with pytest.raises(ValueError, match="incomplete"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}, splits={}))
    client.get_title_statuses.return_value = {"Lost": MediaWikiTitleStatus("Lost", "Lost", None, True)}
    client.get_page_snapshots.side_effect = None
    client.get_page_snapshots.return_value = {}
    with pytest.raises(ValueError, match="incomplete"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}, splits={}))
    client.get_page_snapshots.return_value = {"Lost": MediaWikiPageSnapshot("Lost", None, None, "now")}
    with pytest.raises(ValueError, match="source for 'Lost' is missing"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}, splits={}))
