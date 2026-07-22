"""Focused tests for link-audit orchestration."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from erenshor.application.wiki_deploy.link_audit_service import (
    TRACKING_CATEGORIES,
    LinkAuditService,
    extract_catalog_sha256,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus

ENTRY = LinkCatalogEntry("item:a", "item", None, "A", "A", None)


class FakeClient:
    def __init__(
        self,
        *,
        catalog_source: str | None = None,
        wanted_pages: tuple[str, ...] = ("Wanted B", "Wanted A", "Wanted A"),
        category_members: tuple[str, ...] = (),
    ) -> None:
        self.catalog_source = catalog_source
        self.wanted_pages = wanted_pages
        self.category_members = category_members
        self.calls: list[tuple[object, ...]] = []
        self.mutated = False

    def get_page(self, title: str) -> str | None:
        self.calls.append(("get_page", title))
        return self.catalog_source

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]:
        self.calls.append(("get_pages", tuple(titles)))
        return dict.fromkeys(titles, "")

    def get_title_statuses(self, titles: Sequence[str]) -> dict[str, MediaWikiTitleStatus]:
        requested = tuple(titles)
        self.calls.append(("get_title_statuses", requested))
        return {title: MediaWikiTitleStatus(title, title, None, True) for title in requested}

    def get_wanted_pages(self, namespace: int = 0) -> tuple[str, ...]:
        self.calls.append(("get_wanted_pages", namespace))
        return self.wanted_pages

    def get_linking_pages_by_title(self, titles: Sequence[str], namespace: int = 0) -> dict[str, tuple[str, ...]]:
        requested = tuple(titles)
        self.calls.append(("get_linking_pages_by_title", requested, namespace))
        return {title: (f"Source for {title}",) for title in requested}

    def get_category_members(self, title: str, namespace: int = 0) -> tuple[str, ...]:
        self.calls.append(("get_category_members", title, namespace))
        return self.category_members

    def login(self) -> None:
        self.mutated = True
        raise AssertionError("link audit must not login")

    def edit_page(self, *args: object, **kwargs: object) -> None:
        self.mutated = True
        raise AssertionError("link audit must not edit")


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
    client = FakeClient(catalog_source='["catalogSha256"] = "' + "0" * 64 + '"')
    generated = {
        "z page": "{{ItemLink|stablekey=item:a}}",
        "A page": "{{ItemLink|Fallback|stablekey=item:a}}",
    }
    planned = ("A",)

    report = LinkAuditService((ENTRY,), client).audit(generated, planned, "main", online=True)

    assert report.remote_checked is True
    assert report.generated_content_sha256
    assert ("get_title_statuses", ("A", "Fallback")) in client.calls
    assert ("get_wanted_pages", 0) in client.calls
    assert ("get_linking_pages_by_title", ("Wanted A", "Wanted B"), 0) in client.calls
    assert [call[1] for call in client.calls if call[0] == "get_category_members"] == list(TRACKING_CATEGORIES)
    assert ("get_pages", ("A page", "z page")) in client.calls
    assert not client.mutated


def test_online_requires_a_client() -> None:
    with pytest.raises(ValueError, match="requires a MediaWikiClient"):
        LinkAuditService((ENTRY,)).audit({}, (), "main", online=True)


@pytest.mark.parametrize(
    "source",
    [None, 'return { ["catalogSha256"] = "not-a-digest" }'],
)
def test_absent_or_malformed_catalog_source_only_reports_stale_catalog(source: str | None) -> None:
    client = FakeClient(catalog_source=source, wanted_pages=())
    report = LinkAuditService((ENTRY,), client).audit(
        {"Generated": "{{ItemLink|stablekey=item:a}}"},
        ("A",),
        "main",
        online=True,
    )

    assert report.summary == {"live_link_catalog_stale": 1}


def test_wanted_linking_and_tracking_facts_reach_report() -> None:
    client = FakeClient(catalog_source='catalogSha256 = "' + "0" * 64 + '"', category_members=("Runtime page",))
    report = LinkAuditService((ENTRY,), client).audit({}, (), "main", online=True, include_live_pages=False)

    assert report.summary["manual_red_link"] == 2
    assert report.summary["runtime_tracking_category"] == 3
    assert {finding.source_page for finding in report.findings if finding.code == "manual_red_link"} == {
        "Source for Wanted A",
        "Source for Wanted B",
    }
    assert not any(call[0] == "get_pages" for call in client.calls)
    assert not client.mutated


def test_extract_catalog_sha256_requires_exact_hex_digest() -> None:
    digest = "A" * 64
    assert extract_catalog_sha256(f'catalogSha256 = "{digest}"') == digest.lower()
    assert extract_catalog_sha256('catalogSha256 = "' + "f" * 63 + '"') is None
    assert extract_catalog_sha256('catalogSha256 = "' + "f" * 65 + '"') is None
