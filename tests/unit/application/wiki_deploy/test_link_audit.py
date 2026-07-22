"""Focused tests for deterministic semantic-link auditing."""

from __future__ import annotations

from erenshor.application.wiki_deploy.link_audit import (
    audit_links,
    generated_content_sha256,
    local_catalog_sha256,
    parse_link_occurrences,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus


def entry(key: str, name: str, page: str) -> LinkCatalogEntry:
    return LinkCatalogEntry(key, "item", None, name, page, None)


def test_all_finding_codes_and_severities_are_reported() -> None:
    catalog = (
        entry("item:a", "A", "A"),
        entry("item:shared_a", "Shared", "Shared"),
        entry("item:shared_b", "Shared", "Shared"),
        entry("item:old", "Old", "Old"),
    )
    statuses = {
        "Missing": MediaWikiTitleStatus("Missing", "Missing", None, False),
        "Old": MediaWikiTitleStatus("Old", "Old", "New", False),
    }
    report = audit_links(
        generated_pages={
            "A source": "{{ItemLink|stablekey=item:a|link=Wrong}}",
            "B source": "{{ItemLink|stablekey=item:unknown|link=A}}",
            "C source": (
                "{{ItemLink|stablekey=item:a|link=A}} {{ItemLink|Shared}} {{ItemLink|Missing}} {{ItemLink|Old}}"
            ),
        },
        catalog_entries=catalog,
        planned_titles=set(),
        title_statuses=statuses,
        live_catalog_sha256="stale",
        wanted_pages=("Wanted",),
        linking_pages={"Wanted": ("Source",)},
        runtime_tracking_categories={"Category:Pages with unresolved Erenshor links": ("Runtime page",)},
        remote_checked=True,
    )
    by_code = {finding.code: finding for finding in report.findings}
    assert set(by_code) == {
        "missing_stable_key_data",
        "stable_key_target_mismatch",
        "missing_generated_target_article",
        "ambiguous_manual_semantic_link",
        "manual_red_link",
        "stale_manual_redirect",
        "live_link_catalog_stale",
        "runtime_tracking_category",
    }
    assert {code: finding.severity for code, finding in by_code.items()} == {
        "missing_stable_key_data": "error",
        "stable_key_target_mismatch": "error",
        "missing_generated_target_article": "error",
        "ambiguous_manual_semantic_link": "warning",
        "manual_red_link": "warning",
        "stale_manual_redirect": "warning",
        "live_link_catalog_stale": "warning",
        "runtime_tracking_category": "warning",
    }


def test_stable_key_only_invocation_resolves_from_catalog() -> None:
    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a}}"},
        catalog_entries=catalog,
        planned_titles={"A"},
    )

    assert report.findings == ()
    assert len(report.occurrences) == 1
    occurrence = report.occurrences[0]
    assert occurrence.stable_key == "item:a"
    assert occurrence.supplied_target is None
    assert occurrence.canonical_target == "A"


def test_wanted_page_uses_deterministic_linking_sources() -> None:
    report = audit_links(
        generated_pages={},
        catalog_entries=(),
        planned_titles=set(),
        wanted_pages=("Missing_target",),
        linking_pages={"Missing target": ("Z source", "A source", "A source")},
    )

    assert report.remote_checked is True
    assert [finding.source_page for finding in report.findings] == ["A source", "Z source"]
    assert {finding.supplied_target for finding in report.findings} == {"Missing_target"}


def test_keyed_target_mismatch_is_checked_despite_explicit_fallback() -> None:
    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a|link=Fallback|text=Fallback}}"},
        catalog_entries=catalog,
        planned_titles={"A"},
    )
    [finding] = [f for f in report.findings if f.code == "stable_key_target_mismatch"]
    assert finding.canonical_target == "A"
    assert finding.supplied_target == "Fallback"


def test_effective_page_filter_and_limit_are_missing_planned_target_errors() -> None:
    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a|link=A}}"},
        catalog_entries=catalog,
        planned_titles=set(),  # A was excluded by the effective page scope.
        known_generated_titles={"A"},
    )
    assert [finding.code for finding in report.findings] == ["missing_generated_target_article"]
    assert report.findings[0].severity == "error"


def test_offline_external_target_remains_unknown_until_remote_check() -> None:
    catalog = (entry("item:a", "A", "External page"),)
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a}}"},
        catalog_entries=catalog,
        planned_titles={"Source"},
        known_generated_titles={"Source"},
    )

    assert report.findings == ()
    assert report.remote_checked is False


def test_redirect_is_an_existing_keyed_target_but_stale_manual_target_warns() -> None:
    catalog = (entry("item:a", "A", "A"),)
    statuses = {"A": MediaWikiTitleStatus("A", "A", "New A", False)}
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a|link=A}} {{ItemLink|A}}"},
        catalog_entries=catalog,
        planned_titles=set(),
        title_statuses=statuses,
    )
    codes = [finding.code for finding in report.findings]
    assert "missing_generated_target_article" not in codes
    assert codes == ["stale_manual_redirect"]


def test_unique_manual_name_checks_the_rendered_catalog_page() -> None:
    catalog = (entry("item:a", "Display name", "Canonical page"),)
    statuses = {
        "Display name": MediaWikiTitleStatus("Display name", "Display name", None, False),
        "Canonical page": MediaWikiTitleStatus("Canonical page", "Canonical page", None, True),
    }
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|Display name}}"},
        catalog_entries=catalog,
        planned_titles=set(),
        title_statuses=statuses,
    )

    assert report.findings == ()
    assert report.occurrences[0].canonical_target == "Canonical page"


def test_duplicate_manual_names_and_pages_are_ambiguous_without_rewriting() -> None:
    catalog = (
        entry("item:first", "Shared", "Shared"),
        entry("item:second", "Shared", "Other"),
        entry("item:third", "Third", "Shared"),
    )
    source = "Before {{ItemLink|Shared}} after"
    occurrences = parse_link_occurrences("Source", source, catalog)
    assert occurrences[0].stable_key is None
    assert occurrences[0].canonical_target is None
    report = audit_links(generated_pages={"Source": source}, catalog_entries=catalog, planned_titles=set())
    assert [finding.code for finding in report.findings] == ["ambiguous_manual_semantic_link"]
    assert source == "Before {{ItemLink|Shared}} after"


def test_generated_content_hash_and_report_order_are_deterministic() -> None:
    pages_a = {"z": "z", "A": "a"}
    pages_b = {"A": "a", "z": "z"}
    assert generated_content_sha256(pages_a) == generated_content_sha256(pages_b)
    assert generated_content_sha256(pages_a) != generated_content_sha256({"A": "changed", "z": "z"})

    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={
            "Z source": "{{ItemLink|stablekey=item:a|link=Wrong}}",
            "A source": "{{ItemLink|stablekey=item:a|link=Wrong}}",
        },
        catalog_entries=catalog,
        planned_titles={"A"},
        variant="main",
    )
    assert [finding.source_page for finding in report.findings] == ["A source", "Z source"]
    data = report.to_dict()
    assert tuple(data) == (
        "schema_version",
        "variant",
        "remote_checked",
        "generated_content_sha256",
        "summary",
        "findings",
    )
    assert data["variant"] == "main"
    assert data["summary"] == {"stable_key_target_mismatch": 2}


def test_excluded_plain_text_has_no_occurrence() -> None:
    assert parse_link_occurrences("Source", "Excluded item", ()) == ()


def test_local_catalog_digest_matches_live_digest_without_warning() -> None:
    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={},
        catalog_entries=catalog,
        planned_titles=set(),
        live_catalog_sha256=local_catalog_sha256(catalog),
    )
    assert "live_link_catalog_stale" not in {finding.code for finding in report.findings}
