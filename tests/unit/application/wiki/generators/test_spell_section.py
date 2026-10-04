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
