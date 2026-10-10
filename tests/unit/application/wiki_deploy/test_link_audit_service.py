"""Focused tests for link-audit orchestration."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.link_audit_service import (
    DATA_LINK_TITLE,
    TRACKING_CATEGORIES,
    LinkAuditService,
    extract_catalog_sha256,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry

ENTRY = LinkCatalogEntry("item:a", "item", None, "A", "A", None)


def test_offline_audit_does_not_need_or_call_a_client() -> None:
    service = LinkAuditService((ENTRY,))

    report = service.audit(
        {"Generated": "{{ItemLink|stablekey=item:a}}"},
        ("A",),
        "main",
        online=False,
    )

    assert report.remote_checked is False
    assert report.findings == ()


def test_online_audit_enriches_deterministically_and_preserves_scope() -> None:
    client = MediaWikiFake()
    client.put_page(DATA_LINK_TITLE, '["catalogSha256"] = "' + "0" * 64 + '"')
    client.put_page("A", "")
    client.put_page("Fallback", "")
    client.put_page("A page", "{{ItemLink|A}}")
    client.put_page("z page", "{{ItemLink|A}}")
    client.put_page("Outside scope", "{{ItemLink|stablekey=item:missing}}")
    client.wanted_pages = ("Wanted B", "Wanted A", "Wanted A")
    client.linking_pages = {title: (f"Source for {title}",) for title in client.wanted_pages}
    client.category_members = dict.fromkeys(TRACKING_CATEGORIES, ("Runtime page",))
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    initial_categories = client.category_members.copy()
    generated = {
        "z page": "{{ItemLink|stablekey=item:a}}",
        "A page": "{{ItemLink|Fallback|stablekey=item:a}}",
    }
    planned = ("A",)

    report = LinkAuditService((ENTRY,), client).audit(generated, planned, "main", online=True)

    assert report.remote_checked is True
    assert report.generated_content_sha256
    assert [
        (occurrence.source_page, occurrence.supplied_target)
        for occurrence in report.occurrences
        if occurrence.origin == "live_wiki"
    ] == [("A page", "A"), ("z page", "A")]
    assert [
        (finding.source_page, finding.supplied_target)
        for finding in report.findings
        if finding.code == "manual_red_link"
    ] == [("Source for Wanted A", "Wanted A"), ("Source for Wanted B", "Wanted B")]
    assert {
        finding.supplied_target for finding in report.findings if finding.code == "runtime_tracking_category"
    } == set(TRACKING_CATEGORIES)
    assert not any(finding.code == "missing_generated_target_article" for finding in report.findings)
    client.wanted_pages = ("Wanted A", "Wanted B")
    reordered_report = LinkAuditService((ENTRY,), client).audit(
        dict(reversed(tuple(generated.items()))), planned, "main", online=True
    )
    assert reordered_report == report
    assert client.login_calls == 0
    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert client.category_members == initial_categories


def test_online_requires_a_client() -> None:
    with pytest.raises(ValueError, match="requires a MediaWikiClient"):
        LinkAuditService((ENTRY,)).audit({}, (), "main", online=True)


@pytest.mark.parametrize(
    "source",
    [None, 'return { ["catalogSha256"] = "not-a-digest" }'],
)
def test_absent_or_malformed_catalog_source_only_reports_stale_catalog(source: str | None) -> None:
    client = MediaWikiFake()
    if source is not None:
        client.put_page(DATA_LINK_TITLE, source)
    client.put_page("A", "")
    client.put_page("Generated", "")
    report = LinkAuditService((ENTRY,), client).audit(
        {"Generated": "{{ItemLink|stablekey=item:a}}"},
        ("A",),
        "main",
        online=True,
    )

    assert report.summary == {"live_link_catalog_stale": 1}


def test_wanted_linking_and_tracking_facts_reach_report() -> None:
    client = MediaWikiFake()
    client.put_page(DATA_LINK_TITLE, 'catalogSha256 = "' + "0" * 64 + '"')
    client.wanted_pages = ("Wanted B", "Wanted A", "Wanted A")
    client.linking_pages = {title: (f"Source for {title}",) for title in client.wanted_pages}
    client.category_members = dict.fromkeys(TRACKING_CATEGORIES, ("Runtime page",))
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    initial_categories = client.category_members.copy()

    def unexpected_live_pages_read(titles: Sequence[str]) -> dict[str, str | None]:
        raise AssertionError("link audit must not read live pages when disabled")

    client.get_pages = unexpected_live_pages_read
    report = LinkAuditService((ENTRY,), client).audit({}, (), "main", online=True, include_live_pages=False)

    assert report.summary["manual_red_link"] == 2
    assert report.summary["runtime_tracking_category"] == 3
    assert {finding.source_page for finding in report.findings if finding.code == "manual_red_link"} == {
        "Source for Wanted A",
        "Source for Wanted B",
    }
    assert client.login_calls == 0
    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert client.category_members == initial_categories


def test_extract_catalog_sha256_requires_exact_hex_digest() -> None:
    digest = "A" * 64
    assert extract_catalog_sha256(f'catalogSha256 = "{digest}"') == digest.lower()
    assert extract_catalog_sha256('catalogSha256 = "' + "f" * 63 + '"') is None
    assert extract_catalog_sha256('catalogSha256 = "' + "f" * 65 + '"') is None
