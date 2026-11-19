import importlib

import pytest


@pytest.fixture
def parity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend("wiki-dev")
    return importlib.import_module("tooltip_parity")


def test_missing_wiki_key_is_named(parity) -> None:
    root = parity._build_dom('<div class="erenshor-ability-tooltip" data-erenshor-key="spell:spark"></div>')
    with pytest.raises(ValueError, match=r"Missing keys:.*spell:lightning"):
        parity.eligible_wiki_roots(root, ["spell:spark", "spell:lightning"], "")


def test_duplicate_standard_card_fails_even_with_other_qualities(parity) -> None:
    root = parity._build_dom(
        "".join(f'<div data-erenshor-quality="{label}"></div>' for label in ("Standard", "Standard", "Blessed"))
    )
    with pytest.raises(ValueError, match="Duplicate rendered quality card: Standard"):
        parity.quality_cards(root, (1, 2))


def test_wrong_quality_card_is_not_paired_by_order(parity) -> None:
    root = parity._build_dom('<div data-erenshor-quality="Standard"></div><div data-erenshor-quality="Ascended"></div>')
    with pytest.raises(ValueError, match=r"Expected quality cards.*Blessed.*Ascended"):
        parity.quality_cards(root, (1, 2))


def test_css_tone_is_read_from_renderer_declaration(parity) -> None:
    positive = ".item-spell-positive { color: #00ff00; }"
    assert parity.stylesheet_tones(positive)["item-spell-positive"] == parity.Tone.POSITIVE
    negative = positive.replace("#00ff00", "#ff6666")
    assert parity.stylesheet_tones(negative)["item-spell-positive"] == parity.Tone.NEGATIVE


def test_item_projection_preserves_game_class_order_and_tone(parity) -> None:
    line = parity.ObservedLine(
        "ItemInfoWindow.DisplayItem", "Usable", 1, (parity.Span(" Arcanist  Windblade  Druid  ", parity.Tone.NORMAL),)
    )
    root = parity._build_dom(
        '<div class="item-tooltip-classes"><span class="item-tooltip-class">Arcanist</span>'
        '<span class="item-tooltip-class">Druid</span><span class="item-tooltip-class">Windblade</span></div>'
    )
    expected = parity._item_field_lines([line])
    actual = parity.rendered_lines(root, "Item tooltip")
    assert expected == [line]
    assert parity.line_differences(expected, actual)[0]["kind"] == "replace"


def test_item_projection_reads_slot_links_and_zero_stats_from_css(parity, monkeypatch: pytest.MonkeyPatch) -> None:
    source = """
        .item-tooltip-type { color: #ffffff; }
        .item-tooltip .item-tooltip-type a:any-link { color: #ff6666; }
        .item-tooltip-stat-value { color: #f5e5a0; }
        .item-tooltip-stat-value[data-value="0"] { color: #606b80; }
    """
    monkeypatch.setattr(parity, "_stylesheet_tones", lambda: parity.stylesheet_tones(source))
    root = parity._build_dom(
        '<div class="item-tooltip-type"><a class="new" href="/Weapons">Primary</a> - Relic Item</div>'
        '<div><span class="item-tooltip-stat-value" data-value="0">+0%</span></div>'
        '<div><span class="item-tooltip-stat-value">0x</span></div>'
    )
    slot, resist, multiplier = parity.rendered_lines(root, "Item tooltip")
    assert slot.spans == (
        parity.Span("Primary", parity.Tone.NEGATIVE),
        parity.Span(" - Relic Item", parity.Tone.NORMAL),
    )
    assert resist.spans == (parity.Span("+0%", parity.Tone.MUTED),)
    assert multiplier.spans == (parity.Span("0x", parity.Tone.VALUE),)
