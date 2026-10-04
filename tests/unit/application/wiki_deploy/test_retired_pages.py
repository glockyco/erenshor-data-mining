"""Behavior of the read-only retired article review."""

from unittest.mock import MagicMock

import pytest

from erenshor.application.wiki.lifecycle import ContentLifecycle, LifecyclePage, LifecycleRename
from erenshor.application.wiki_deploy.retired_pages import audit_retired_pages
from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus


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
    )


def _client(pages: dict[str, str | None], created: tuple[str, ...]) -> MagicMock:
    client = MagicMock()
    client.list_user_created_pages.return_value = created
    client.get_title_statuses.side_effect = lambda titles: {
        title: MediaWikiTitleStatus(title, title, None, pages.get(title, "generated target") is not None)
        for title in titles
    }
    client.get_pages.side_effect = lambda titles: {title: pages[title] for title in titles}
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
    lifecycle = ContentLifecycle(pages={}, renames=_lifecycle().renames)
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
    lifecycle = ContentLifecycle(pages=_lifecycle().pages, renames={})
    assert audit_retired_pages(client, {}, lifecycle).pages[0].state == "pending notice"
    pages["Reckless"] += (
        "\n{{Historical Content|state=removed|thing=stance|update=Planar March"
        "|date=July 13, 2026|url=https://notes.test}}"
    )
    report = audit_retired_pages(client, {}, lifecycle)
    assert report.pages[0].state == "marked"
    assert report.pending == 0


def test_unexplained_and_invalid_dispositions_fail() -> None:
    client = _client({"Mystery": "{{Item|stablekey=item:unknown}}"}, ("Mystery",))
    report = audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}))
    assert report.has_errors and report.unexplained == 1
    assert report.pages[0].title == "Mystery"

    client = _client({"Reckless": "{{Historical Content|state=unobtainable}}"}, ("Reckless",))
    report = audit_retired_pages(client, {}, ContentLifecycle(pages=_lifecycle().pages, renames={}))
    assert report.has_errors and report.pages[0].reason == "The notice has an incorrect state."


def test_unreviewed_rename_names_matching_generated_identity() -> None:
    client = _client({"Old Book": "{{Item|stablekey=item:book}}"}, ("Old Book",))
    report = audit_retired_pages(
        client,
        {"New Book": "{{Item|stablekey=item:book}}"},
        ContentLifecycle(pages={}, renames={}),
    )
    assert report.pages[0].current_title == "New Book"
    assert report.pages[0].state == "unexplained"


def test_incomplete_title_or_source_results_fail_closed() -> None:
    client = _client({"Lost": "{{Item}}"}, ("Lost",))
    client.get_title_statuses.side_effect = None
    client.get_title_statuses.return_value = {}
    with pytest.raises(ValueError, match="incomplete"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}))
    client.get_title_statuses.return_value = {"Lost": MediaWikiTitleStatus("Lost", "Lost", None, True)}
    client.get_pages.side_effect = None
    client.get_pages.return_value = {}
    with pytest.raises(ValueError, match="incomplete"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}))
    client.get_pages.return_value = {"Lost": None}
    with pytest.raises(ValueError, match="source for 'Lost' is missing"):
        audit_retired_pages(client, {}, ContentLifecycle(pages={}, renames={}))
