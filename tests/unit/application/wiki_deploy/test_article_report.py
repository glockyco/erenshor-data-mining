"""Tests for the review report of an article deploy plan."""

from __future__ import annotations

from erenshor.application.wiki_deploy.article_report import TierChange, describe_change
from erenshor.application.wiki_deploy.articles import PlannedArticle
from erenshor.application.wiki_deploy.link_audit import LinkTargets
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry

LINKS = LinkTargets(
    (
        LinkCatalogEntry(key="zone:brake", kind="zone", subtype=None, name="The Brake", page="The Brake", image=None),
        LinkCatalogEntry(key="zone:azure", kind="zone", subtype=None, name="Port Azure", page="Port Azure", image=None),
    )
)


def _describe(fetched: str | None, generated: str, kept_roots: tuple[str, ...] = ()):
    action = "create" if fetched is None else "edit"
    article = PlannedArticle(title="Page", action=action, generated_text=generated, fetched_revision_id=10)
    return describe_change(article, fetched, kept_roots, LINKS)


def test_values_compare_with_link_syntax_ignored() -> None:
    fetched = "{{Character\n|name=Alpha\n|type=Rare\n|zones=[[The Brake]]\n|level=10\n}}\n"
    generated = (
        "{{Character\n|name=Alpha\n|stablekey=character:alpha\n|type=Elite\n"
        "|zones={{ZoneLink|stablekey=zone:brake}}\n|level=12\n}}\n"
    )

    change = _describe(fetched, generated)

    assert change.kinds == frozenset({"encounter tier", "stable key", "links", "field values"})
    assert change.tier_changes == (TierChange("Alpha", "Rare", "Elite"),)
    assert change.fields == frozenset({"Character.level"})


def test_a_link_to_another_page_is_a_value_change() -> None:
    fetched = "{{Character\n|name=Alpha\n|zones=[[The Brake]]\n}}\n"
    generated = "{{Character\n|name=Alpha\n|zones={{ZoneLink|stablekey=zone:azure}}\n}}\n"

    assert _describe(fetched, generated).fields == frozenset({"Character.zones"})


def test_an_unlinked_tier_is_a_value_change_but_not_a_tier_change() -> None:
    fetched = "{{Character\n|name=Alpha\n|type=[[Enemies|Boss]]\n}}\n"
    generated = "{{Character\n|name=Alpha\n|type=Boss\n}}\n"

    change = _describe(fetched, generated)

    assert change.kinds == frozenset({"field values"})
    assert change.fields == frozenset({"Character.type"})
    assert change.tier_changes == ()


def test_structure_categories_and_kept_roots_are_reported() -> None:
    fetched = (
        "{{Item\n|title=Frost\n}}\nOld prose.\n{{Character\n|name=A Raider\n}}\n"
        "{{Character\n|name=Braxonian Chest\n}}\n[[Category:Items]]\n"
    )
    generated = (
        "{{Item\n|title=Frost\n}}\n{{ItemTooltip\n|title=Frost\n}}\nNew prose.\n"
        "{{Character\n|name=Braxonian Chest\n}}\n[[Category:Items]]\n[[Category:Weapons]]\n"
    )

    change = _describe(fetched, generated, kept_roots=("Character: Braxonian Chest",))

    assert change.kinds == frozenset({"categories", "structure"})
    assert change.structure == (
        "added ItemTooltip",
        "removed Character: A Raider",
        "changed the text outside the generated templates",
    )
    assert change.kept_roots == ("Character: Braxonian Chest",)


def test_a_formatting_change_is_still_reported() -> None:
    fetched = "{{Item|title=Frost|level=1}}\n"
    generated = "{{Item\n|level=1\n|title=Frost\n}}\n"

    change = _describe(fetched, generated)

    assert change.kinds == frozenset({"structure"})
    assert change.structure == ("changed only the formatting of the generated templates",)


def test_a_page_without_a_fetched_copy_is_a_new_page() -> None:
    assert _describe(None, "{{Item\n|title=New\n}}\n").kinds == frozenset({"new page"})
