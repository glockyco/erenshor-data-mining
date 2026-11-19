from erenshor.application.wiki_tooltips.compare import (
    ObservedLine,
    line_differences,
    normalize_damage,
    viewer_exclusion,
)
from erenshor.application.wiki_tooltips.tmp import Span, Tone


def line(text: str, tone: Tone = Tone.NORMAL) -> ObservedLine:
    return ObservedLine("source window", "field", 1, (Span(text, tone),))


def test_exact_match_passes_but_missing_resist_and_tone_do_not() -> None:
    game = [line("Resist Type: Magic", Tone.MAGIC)]
    assert line_differences(game, list(game)) == []
    assert line_differences(game, [line("Resist Type: Magic")])[0]["kind"] == "replace"
    assert line_differences(game, [])[0]["game"][0]["spans"][0]["text"] == "Resist Type: Magic"


def test_damage_interval_exception_does_not_rewrite_the_description() -> None:
    assert normalize_damage(line("Damage: 15 / tick")).text == "Damage: 15 / 3 sec"
    description = line("Apply a DOT that does 15 damage / tick for 6 ticks")
    assert normalize_damage(description) == description


def test_base_dps_is_neither_excluded_nor_accepted_as_an_extra_line() -> None:
    dps = ObservedLine("ItemInfoWindow.DisplayItem", "OtherTextParent", 1, (Span("Base DPS: 4", Tone.NORMAL),))
    assert viewer_exclusion(dps, level_scaled_mana=False) is None
    assert line_differences([], [dps])[0]["kind"] == "insert"


def test_book_requirement_remains_visible_without_known_state() -> None:
    source = "ItemInfoWindow.DisplayItem"
    known = ObservedLine(source, "ReqLvl", 1, (Span("YOU ALREADY KNOW THIS SKILL", Tone.NEGATIVE),))
    requirement = ObservedLine(source, "ReqLvl", 1, (Span("Required Level: 5", Tone.NORMAL),))
    assert viewer_exclusion(known, level_scaled_mana=False) == "viewer book knowledge"
    assert viewer_exclusion(requirement, level_scaled_mana=False) is None
