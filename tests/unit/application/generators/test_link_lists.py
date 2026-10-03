"""A generated list shows one entry for each linked page and label."""

from erenshor.application.wiki.generators.link_lists import format_chance_links, format_visible_links
from erenshor.domain.value_objects.wiki_link import CharacterLink


def _raider(stable_key: str) -> CharacterLink:
    return CharacterLink(page_title="A Highwayman Raider", display_name="A Highwayman Raider", stable_key=stable_key)


def _guard(element: str) -> CharacterLink:
    name = f"Braxonian Planar Guard ({element})"
    key = f"character:braxonian planar guardian {element}"
    return CharacterLink(page_title=name, display_name=name, stable_key=key)


def test_variants_that_share_a_page_and_label_form_one_entry() -> None:
    rows = [
        (_raider("character:a highwayman raider"), 3.0),
        (_raider("character:a highwayman raider (1)"), 3.0),
        (_raider("character:a highwayman raider (2)"), 3.0),
    ]

    assert format_chance_links(rows, decimals=1) == "{{CharacterLink|stablekey=character:a highwayman raider}} (3.0%)"


def test_variants_with_different_chances_show_the_lowest_and_highest_chance() -> None:
    rows = [(_raider("character:a highwayman raider (1)"), 4.5), (_raider("character:a highwayman raider"), 2.0)]

    assert format_chance_links(rows, decimals=1) == (
        "{{CharacterLink|stablekey=character:a highwayman raider (1)}} (2.0\u20134.5%)"
    )


def test_chances_equal_at_the_shown_precision_are_one_chance() -> None:
    rows = [(_raider("character:a highwayman raider"), 2.04), (_raider("character:a highwayman raider (1)"), 2.01)]

    assert format_chance_links(rows, decimals=1).endswith("(2.0%)")


def test_entities_with_their_own_labels_stay_apart() -> None:
    fire, ice = _guard("fire"), _guard("ice")

    assert format_chance_links([(fire, 1.5), (ice, 1.5)], decimals=1) == f"{fire} (1.5%)<br>{ice} (1.5%)"


def test_visible_links_are_sorted_by_label_once_per_page_and_label() -> None:
    hidden = CharacterLink(page_title=None, display_name="Hidden")
    links = [
        _guard("ice"),
        _raider("character:a highwayman raider (1)"),
        hidden,
        _raider("character:a highwayman raider"),
    ]

    assert format_visible_links(links) == (
        "{{CharacterLink|stablekey=character:a highwayman raider (1)}}"
        "<br>{{CharacterLink|stablekey=character:braxonian planar guardian ice}}"
    )
