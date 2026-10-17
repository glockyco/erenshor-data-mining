"""Focused tests for deterministic semantic-link auditing."""

from __future__ import annotations

from erenshor.application.wiki_deploy.link_audit import (
    LinkTargets,
    audit_links,
    catalog_sha256,
    generated_content_sha256,
    parse_link_occurrences,
)
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.client import MediaWikiTitleStatus


def entry(key: str, name: str, page: str) -> LinkCatalogEntry:
    return LinkCatalogEntry(key, "item", None, name, page, None)


def test_entities_that_share_a_page_and_an_image_are_not_ambiguous() -> None:
    catalog = (
        LinkCatalogEntry("quest:line_1", "quest", None, "Quest Line", "Quest Line", None),
        LinkCatalogEntry("quest:line_2", "quest", None, "Quest Line", "Quest Line", None),
        LinkCatalogEntry("spell:bolt", "ability", "spell", "Bolt", "Bolt", "Bolt icon.png"),
        LinkCatalogEntry("skill:bolt", "ability", "skill", "Bolt", "Bolt", "Bolt icon.png"),
    )
    statuses = {
        "Quest Line": MediaWikiTitleStatus("Quest Line", "Quest Line", None, True),
        "Bolt": MediaWikiTitleStatus("Bolt", "Bolt", None, True),
    }
    report = audit_links(
        generated_pages={"Page": "{{QuestLink|link=Quest Line}} {{AbilityLink|Bolt}}"},
        catalog_entries=catalog,
        planned_titles=set(),
        title_statuses=statuses,
        remote_checked=True,
    )

    # Quests of one quest line link their page; abilities on one page still need a key for their tooltips.
    ambiguous = [finding.kind for finding in report.findings if finding.code == "ambiguous_manual_semantic_link"]
    assert ambiguous == ["ability"]


def test_all_finding_codes_and_severities_are_reported() -> None:
    catalog = (
        entry("item:a", "A", "A"),
        # Two items on one page with different icons cannot render one link.
        LinkCatalogEntry("item:shared_a", "item", None, "Shared", "Shared", "Shared A icon.png"),
        LinkCatalogEntry("item:shared_b", "item", None, "Shared", "Shared", "Shared B icon.png"),
        entry("item:old", "Old", "Old"),
        LinkCatalogEntry("quest:q", "quest", None, "Q", "Q", None),
    )
    statuses = {
        "Missing": MediaWikiTitleStatus("Missing", "Missing", None, False),
        "Old": MediaWikiTitleStatus("Old", "Old", "New", False),
    }
    report = audit_links(
        generated_pages={
            "A source": "{{ItemLink|stablekey=item:a|link=Wrong}}",
            "B source": "{{ItemLink|stablekey=item:unknown|link=A}} {{QuestLink|stablekey=quest:q}}",
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
        "missing_manual_target_article",
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
        "missing_manual_target_article": "warning",
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


def test_missing_quest_article_is_a_red_link_unless_generation_owns_it() -> None:
    catalog = (LinkCatalogEntry("quest:q", "quest", None, "Q", "Q", None),)
    statuses = {"Q": MediaWikiTitleStatus("Q", "Q", None, False)}

    def codes(known_generated_titles: set[str]) -> list[tuple[str, str]]:
        report = audit_links(
            generated_pages={"Source": "{{QuestLink|stablekey=quest:q}}"},
            catalog_entries=catalog,
            planned_titles={"Source"},
            known_generated_titles=known_generated_titles,
            title_statuses=statuses,
        )
        return [(finding.code, finding.severity) for finding in report.findings]

    assert codes({"Source"}) == [("missing_manual_target_article", "warning")]
    assert codes({"Source", "Q"}) == [("missing_generated_target_article", "error")]


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


def test_manual_entity_name_is_not_a_page_alias() -> None:
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

    assert [finding.code for finding in report.findings] == ["manual_red_link"]
    assert report.occurrences[0].canonical_target == "Display name"


def test_names_on_other_pages_do_not_make_a_shared_page_ambiguous() -> None:
    catalog = (
        entry("item:first", "Shared", "Shared"),
        entry("item:second", "Shared", "Other"),
        entry("item:third", "Third", "Shared"),
    )
    source = "Before {{ItemLink|Shared}} after"
    occurrences = parse_link_occurrences("Source", source, catalog)
    assert occurrences[0].stable_key is None
    assert occurrences[0].canonical_target == "Shared"
    report = audit_links(generated_pages={"Source": source}, catalog_entries=catalog, planned_titles=set())
    assert report.findings == ()
    assert source == "Before {{ItemLink|Shared}} after"


def test_positional_fallback_is_not_a_named_key_target_mismatch() -> None:
    catalog = (entry("item:a", "A", "A"),)
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a|Legacy target}}"},
        catalog_entries=catalog,
        planned_titles={"A"},
    )
    assert report.findings == ()


def test_link_targets_keep_editor_targets_even_when_keys_are_present() -> None:
    targets = LinkTargets((entry("item:a", "A", "A"),))
    assert targets.target("{{ItemLink|stablekey=item:a|page=Editor target}}") == "Editor target"
    assert targets.target("{{ItemLink|stablekey=item:missing|Editor fallback}}") == "Editor fallback"
    assert targets.target("{{ItemLink|stablekey=item:a}}") == "A"


def test_wrong_case_planned_page_does_not_satisfy_a_generated_target() -> None:
    report = audit_links(
        generated_pages={"Source": "{{ItemLink|stablekey=item:a}}"},
        catalog_entries=(entry("item:a", "A", "A Quest"),),
        planned_titles={"A quest"},
        title_statuses={"A Quest": MediaWikiTitleStatus("A Quest", "A Quest", None, False)},
        remote_checked=True,
    )

    assert "missing_generated_target_article" in {finding.code for finding in report.findings}


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
        live_catalog_sha256=catalog_sha256(catalog),
    )
    assert "live_link_catalog_stale" not in {finding.code for finding in report.findings}
