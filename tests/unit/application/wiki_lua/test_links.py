from __future__ import annotations

from erenshor.application.wiki_lua.links import link_ref, link_refs
from erenshor.domain.value_objects.wiki_link import ItemLink


def test_shared_page_item_records_keep_stable_keys_in_lua_only() -> None:
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
        "{{ItemLink|Shared Item|image=Alpha.png|text=Alpha}}",
        "{{ItemLink|Shared Item|image=Beta.png|text=Beta}}",
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
