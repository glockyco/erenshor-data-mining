import pytest

from erenshor.application.wiki_tooltips.tmp import Span, Tone, parse_tmp


def parse(text: str):
    return parse_tmp(text, source="SpellbookSlot.ToggleSelect", stable_key="spell:haste", field="Desc")


def test_preserves_modifier_and_percent_tones():
    assert parse("Haste <color=#00FF00>+3</color>%") == (
        (Span("Haste ", Tone.NORMAL), Span("+3", Tone.POSITIVE), Span("%", Tone.NORMAL)),
    )


def test_retains_nested_color_italics_and_blank_lines():
    assert parse("<color=yellow>Use <i><color=white>this</color></i> now</color>\n\n") == (
        (Span("Use ", Tone.EMPHASIS), Span("this", Tone.NORMAL, True), Span(" now", Tone.EMPHASIS)),
        (),
        (),
    )


def test_charm_may_leave_colors_open():
    assert parse("<color=#16EC00>Charm Item\n<color=white>Modifiers") == (
        (Span("Charm Item", Tone.POSITIVE),),
        (Span("Modifiers", Tone.NORMAL),),
    )


@pytest.mark.parametrize("token", ["<size=5>", "</i>", "<color=#010203>"])
def test_unsupported_token_identifies_field(token):
    with pytest.raises(ValueError, match=r"spell:haste.*SpellbookSlot.ToggleSelect.Desc") as error:
        parse(token)
    assert token[7:-1] in str(error.value) if token.startswith("<color=") else token in str(error.value)
