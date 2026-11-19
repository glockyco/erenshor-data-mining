"""Unit tests for the legacy spell section."""

from __future__ import annotations

from unittest.mock import Mock

from tests.unit.application.wiki_lua.fakes import make_spell

from erenshor.application.wiki.generators.sections.spell import SpellSectionGenerator
from erenshor.domain.enriched_data.spell import EnrichedSpellData


def _cooldown_line(cooldown: float) -> str:
    class_display = Mock()
    class_display.get_display_name.side_effect = lambda name: name
    spell = make_spell(stable_key="spell:dark_pact", display_name="Dark Pact", cooldown=cooldown)
    wikitext = SpellSectionGenerator(class_display).generate_template(
        EnrichedSpellData(spell=spell, classes=[], items_with_effect=[], teaching_items=[], used_by_characters=[]),
        "Dark Pact",
    )
    return next(line for line in wikitext.splitlines() if line.startswith("|cooldown="))


def test_a_one_second_cooldown_is_singular() -> None:
    assert _cooldown_line(1.0) == "|cooldown=1 second"


def test_spell_cooldowns_are_seconds_not_ticks() -> None:
    assert _cooldown_line(8.0) == "|cooldown=8 seconds"


def test_spell_article_keeps_base_values_and_status_modifiers_separate() -> None:
    spell = make_spell(
        display_name="Test Spell",
        cooldown=8.0,
        spell_duration_in_ticks=6,
        max_level_target=40,
        cdr=0.20000000298023224,
        increase_haste_cap=10,
        amplify_damage=0.019999999552965164,
        channeling_focus=0.10000000149011612,
    )
    wikitext = SpellSectionGenerator(Mock()).generate_template(
        EnrichedSpellData(spell=spell, classes=[], items_with_effect=[], teaching_items=[], used_by_characters=[]),
        "Test Spell",
    )

    assert {
        "|cooldown=8 seconds",
        "|duration=18 seconds",
        "|max_level_target=40",
        "|cooldown_reduction=20%",
        "|haste_cap_increase=+10%",
        "|amplify_damage=+2%",
        "|channeling_focus=+10%",
    } <= set(wikitext.splitlines())


def test_spell_article_omits_absent_or_zero_modifiers() -> None:
    spell = make_spell(cdr=0.0, increase_haste_cap=0)
    wikitext = SpellSectionGenerator(Mock()).generate_template(
        EnrichedSpellData(spell=spell, classes=[], items_with_effect=[], teaching_items=[], used_by_characters=[]),
        "Test Spell",
    )

    assert not any(
        f"|{field}=" in wikitext
        for field in ("cooldown_reduction", "haste_cap_increase", "amplify_damage", "channeling_focus")
    )
