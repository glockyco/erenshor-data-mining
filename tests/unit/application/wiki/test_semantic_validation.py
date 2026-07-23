"""Behavioral contracts for all-page semantic wiki validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from erenshor.application.wiki.semantic_validation import (
    REQUIRED_TEMPLATE_FIELDS,
    SemanticValidationError,
    WikiPageExpectation,
    derive_page_contract,
    validate_wiki_pages,
)
from erenshor.application.wiki.services.storage import PageMetadata
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry


def _template(template_name: str, **values: str) -> str:
    fields = dict.fromkeys(REQUIRED_TEMPLATE_FIELDS[template_name], "")
    fields.update(values)
    return "{{" + template_name + "\n" + "".join(f"|{key}={value}\n" for key, value in fields.items()) + "}}"


def _catalog() -> tuple[LinkCatalogEntry, ...]:
    return (
        LinkCatalogEntry("item:sword", "item", "weapon", "Sword", "Sword", None),
        LinkCatalogEntry("character:guard", "character", "NPC", "Guard", "Guard", None),
        LinkCatalogEntry("spell:flare", "ability", "spell", "Flare", "Flare", None),
        LinkCatalogEntry("zone:harbor", "zone", "Zone", "Harbor", "Harbor", None),
    )


def _expectation(
    title: str,
    keys: list[str],
    categories: tuple[str, ...],
    *,
    fetched_content: str | None = None,
    schema_kind: str | None = None,
) -> WikiPageExpectation:
    return WikiPageExpectation(
        title,
        PageMetadata(title, keys, [title] * len(keys)),
        fetched_content=fetched_content,
        expected_categories=categories,
        schema_kind=schema_kind,
    )


def _valid_corpus() -> tuple[dict[str, str], dict[str, WikiPageExpectation]]:
    old_item = (
        _template("Item", title="Sword", stablekey="item:sword", type="Manual", othersource="Editor source")
        + "\n\n"
        + _template("ItemTooltip")
    )
    item = (
        _template(
            "Item",
            title="Sword",
            stablekey="item:sword",
            type="Manual<br>Weapon",
            othersource="Editor source",
        )
        + "\n\n"
        + _template("ItemTooltip")
        + "\n\n[[Category:Items]]"
    )
    character = _template("Character", name="Guard") + "\n\n[[Category:Characters]]"
    ability = (
        _template("Ability", title="Flare")
        + "\n\n"
        + _template("SpellTooltip", stablekey="spell:flare")
        + "\n\n[[Category:Abilities]]"
    )
    zone = _template("Zone", title="Harbor") + "\n\n" + "{{Zone Navbox}}" + "\n\n[[Category:Zones]]"
    overview = (
        'Introductory prose.\n\n{| class="wikitable"\n|! Name\n|-\n|{{ItemLink|Sword}}\n|}\n\n[[Category:Overviews]]'
    )
    pages = {
        "Sword": item,
        "Guard": character,
        "Flare": ability,
        "Harbor": zone,
        "Equipment": overview,
    }
    expectations = {
        "Sword": _expectation("Sword", ["item:sword"], ("Category:Items",), fetched_content=old_item),
        "Guard": _expectation("Guard", ["character:guard"], ("Category:Characters",)),
        "Flare": _expectation("Flare", ["spell:flare"], ("Category:Abilities",)),
        "Harbor": _expectation("Harbor", ["zone:harbor"], ("Category:Zones",)),
        "Equipment": _expectation("Equipment", [], ("Category:Overviews",), schema_kind="overview"),
    }
    return pages, expectations


def _validate(pages: dict[str, str], expectations: dict[str, WikiPageExpectation]):
    return validate_wiki_pages(
        pages,
        expectations=expectations,
        catalog_entries=_catalog(),
        planned_titles=pages,
        known_generated_titles=pages,
    )


def test_mixed_corpus_passes_and_report_is_immutable_and_deterministic() -> None:
    pages, expectations = _valid_corpus()
    report = _validate(pages, expectations)

    assert not report.has_errors
    assert report.findings == ()
    assert (
        derive_page_contract("Sword", pages["Sword"], expectations["Sword"].metadata, _catalog()).schema_kind == "item"
    )
    with pytest.raises(SemanticValidationError):
        _validate(
            {**pages, "Sword": pages["Sword"].replace("stablekey=item:sword", "stablekey=item:missing")}, expectations
        ).raise_for_errors()


@pytest.mark.parametrize(
    ("family", "mutate"),
    [
        (
            "title_inventory",
            lambda pages, expectations: (pages, {**expectations, "Other": expectations["Sword"]}),
        ),
        (
            "parseability",
            lambda pages, expectations: ({**pages, "Sword": pages["Sword"] + "{{"}, expectations),
        ),
        (
            "required_schema",
            lambda pages, expectations: (
                {**pages, "Sword": pages["Sword"].replace("|droprates=\n", "")},
                expectations,
            ),
        ),
        (
            "stable_identity",
            lambda pages, expectations: (
                {**pages, "Sword": pages["Sword"].replace("stablekey=item:sword", "stablekey=item:other")},
                expectations,
            ),
        ),
        (
            "generated_manual_ownership",
            lambda pages, expectations: (
                {
                    **pages,
                    "Guard": pages["Guard"]
                    + "\n\n"
                    + _template("Item", stablekey="item:sword")
                    + "\n\n"
                    + _template("ItemTooltip"),
                },
                expectations,
            ),
        ),
        (
            "semantic_links",
            lambda pages, expectations: (
                {
                    **pages,
                    "Equipment": pages["Equipment"].replace(
                        "{{ItemLink|Sword}}", "{{ItemLink|stablekey=item:missing|Sword}}"
                    ),
                },
                expectations,
            ),
        ),
        (
            "manual_overrides",
            lambda pages, expectations: (
                {**pages, "Sword": pages["Sword"].replace("|othersource=Editor source", "|othersource=New source")},
                expectations,
            ),
        ),
        (
            "categories",
            lambda pages, expectations: (
                {
                    **pages,
                    "Sword": pages["Sword"].replace("[[Category:Items]]", "[[Category:Items]]\n[[Category:Items]]"),
                },
                expectations,
            ),
        ),
    ],
)
def test_each_invariant_family_blocks_a_plausible_mutation(family: str, mutate) -> None:
    pages, expectations = _valid_corpus()
    mutated_pages, mutated_expectations = mutate(pages, expectations)

    report = _validate(mutated_pages, mutated_expectations)

    assert report.has_errors
    assert any(finding.code == family for finding in report.findings)


def test_prefer_manual_sentinel_is_compared_using_existing_handler() -> None:
    pages, expectations = _valid_corpus()
    old = expectations["Sword"].fetched_content
    assert old is not None
    expectations["Sword"] = replace(
        expectations["Sword"],
        fetched_content=old.replace("|othersource=Editor source", "|othersource=-"),
    )
    pages["Sword"] = pages["Sword"].replace("|othersource=Editor source", "|othersource=-")

    assert not _validate(pages, expectations).has_errors


def test_malformed_fetched_content_fails_without_ownership_false_positive() -> None:
    pages, expectations = _valid_corpus()
    fetched = expectations["Sword"].fetched_content
    assert fetched is not None
    expectations["Sword"] = replace(expectations["Sword"], fetched_content=fetched + "{{")

    report = _validate(pages, expectations)

    assert any(finding.code == "parseability" for finding in report.findings)
    assert not any(finding.code == "generated_manual_ownership" for finding in report.findings)
