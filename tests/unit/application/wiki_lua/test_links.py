from __future__ import annotations

import pytest

from erenshor.application.wiki_lua.links import class_link_ref, class_link_refs, link_ref, link_refs
from erenshor.domain.value_objects.wiki_link import (
    AbilityLink,
    CharacterLink,
    ClassLink,
    FactionLink,
    ItemLink,
    QuestLink,
    StandardLink,
    ZoneLink,
)


def test_class_link_ref_carries_identity_and_canonical_fallback() -> None:
    assert class_link_ref("Duelist", "Windblade") == {
        "stablekey": "class:duelist",
        "page": "Windblade",
        "text": "Windblade",
    }


@pytest.mark.parametrize(
    ("class_names", "display_names", "message"),
    [
        (["Duelist"], {}, "has no display-name mapping"),
        (["   "], {"   ": "Windblade"}, "nonblank internal name"),
        (["Duelist"], {"Duelist": "   "}, "blank display name"),
    ],
)
def test_class_link_refs_reject_malformed_identity(
    class_names: list[str], display_names: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        class_link_refs(class_names, display_names)


def test_shared_page_item_records_keep_stable_keys_in_wikitext_and_lua() -> None:
    links = [
        ItemLink(
            page_title="Shared Item",
            display_name="Alpha",
            image_name="Alpha",
            stable_key="item:alpha",
        ),
        ItemLink(
            page_title="Shared Item",
            display_name="Beta",
            image_name="Beta",
            stable_key="item:beta",
        ),
    ]

    assert [str(link) for link in links] == [
        "{{ItemLink|stablekey=item:alpha|link=Shared Item|text=Alpha|image=Alpha.png}}",
        "{{ItemLink|stablekey=item:beta|link=Shared Item|text=Beta|image=Beta.png}}",
    ]
    assert link_refs(links) == [
        {"kind": "item", "page": "Shared Item", "text": "Alpha", "image": "Alpha", "stablekey": "item:alpha"},
        {"kind": "item", "page": "Shared Item", "text": "Beta", "image": "Beta", "stablekey": "item:beta"},
    ]


def test_excluded_item_link_stays_plain_text_without_lua_reference() -> None:
    link = ItemLink(page_title=None, display_name="Hidden Item", stable_key="item:hidden")

    assert str(link) == "Hidden Item"
    assert link_ref(link) is None


def test_item_link_without_identity_does_not_guess_one_from_page_text() -> None:
    link = ItemLink("Shared Item", "Alpha", "Alpha")

    assert str(link) == "{{ItemLink|Shared Item|image=Alpha.png|text=Alpha}}"
    assert link_ref(link) == {"kind": "item", "page": "Shared Item", "text": "Alpha", "image": "Alpha"}


@pytest.mark.parametrize(
    ("link_type", "kind", "key_prefix"),
    [
        (ItemLink, "Item", "item"),
        (AbilityLink, "Ability", "spell"),
        (QuestLink, "Quest", "quest"),
        (CharacterLink, "Character", "character"),
        (ZoneLink, "Zone", "zone"),
        (FactionLink, "Faction", "faction"),
        (ClassLink, "Class", "class"),
    ],
)
def test_each_semantic_link_renders_keyed_identity(link_type: type[ItemLink], kind: str, key_prefix: str) -> None:
    link = link_type("Shared Page", "Display Name", "Icon", f"{key_prefix}:stable")

    assert str(link) == (
        f"{{{{{kind}Link|stablekey={key_prefix}:stable|link=Shared Page|text=Display Name|image=Icon.png}}}}"
    )


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        (ItemLink("Page", "Display", "Display"), "{{ItemLink|Page|image=Display.png|text=Display}}"),
        (AbilityLink("Page", "Display", "Display"), "{{AbilityLink|Page|image=Display.png|text=Display}}"),
        (QuestLink("Page", "Display"), "{{QuestLink|link=Page{{!}}Display}}"),
        (CharacterLink("Page", "Display"), "[[Page|Display]]"),
        (ZoneLink("Page", "Display"), "[[Page|Display]]"),
        (FactionLink("Page", "Display"), "[[Page|Display]]"),
        (ClassLink("Page", "Display"), "[[Page|Display]]"),
    ],
)
def test_unkeyed_semantic_links_preserve_legacy_rendering(link: object, expected: str) -> None:
    assert str(link) == expected


def test_standard_link_remains_ordinary_even_with_stable_key() -> None:
    link = StandardLink("Page", "Display", None, "page:stable")

    assert str(link) == "[[Page|Display]]"
    assert link_ref(link) == {
        "kind": "page",
        "page": "Page",
        "text": "Display",
        "stablekey": "page:stable",
    }


@pytest.mark.parametrize(
    ("link_type", "key_prefix"),
    [
        (ItemLink, "item"),
        (AbilityLink, "spell"),
        (QuestLink, "quest"),
        (CharacterLink, "character"),
        (ZoneLink, "zone"),
        (FactionLink, "faction"),
        (ClassLink, "class"),
    ],
)
def test_excluded_semantic_links_are_plain_text(link_type: type[ItemLink], key_prefix: str) -> None:
    link = link_type(None, "Excluded", "Icon", f"{key_prefix}:hidden")

    assert str(link) == "Excluded"
    assert link_ref(link) is None


@pytest.mark.parametrize(
    ("link_type", "kind", "key_prefix"),
    [
        (ItemLink, "item", "item"),
        (AbilityLink, "ability", "spell"),
        (QuestLink, "quest", "quest"),
        (CharacterLink, "character", "character"),
        (ZoneLink, "zone", "zone"),
        (FactionLink, "faction", "faction"),
        (ClassLink, "class", "class"),
    ],
)
def test_link_ref_maps_each_semantic_kind(link_type: type[ItemLink], kind: str, key_prefix: str) -> None:
    assert link_ref(link_type("Page", "Display", stable_key=f"{key_prefix}:stable")) == {
        "kind": kind,
        "page": "Page",
        "text": "Display",
        "stablekey": f"{key_prefix}:stable",
    }


@pytest.mark.parametrize(
    ("link_type", "key_prefix"),
    [
        (ItemLink, "item"),
        (AbilityLink, "spell"),
        (QuestLink, "quest"),
        (CharacterLink, "character"),
        (ZoneLink, "zone"),
        (FactionLink, "faction"),
        (ClassLink, "class"),
    ],
)
def test_stable_key_is_fourth_positional_field(link_type: type[ItemLink], key_prefix: str) -> None:
    link = link_type("Page", "Display", "Icon", f"{key_prefix}:stable")

    assert link.page_title == "Page"
    assert link.display_name == "Display"
    assert link.image_name == "Icon"
    assert link.stable_key == f"{key_prefix}:stable"
