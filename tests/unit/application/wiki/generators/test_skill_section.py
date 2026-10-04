"""Unit tests for the legacy skill section."""

from __future__ import annotations

from unittest.mock import Mock

from tests.unit.application.wiki_lua.fakes import make_skill

from erenshor.application.wiki.generators.sections.skill import SkillSectionGenerator
from erenshor.domain.enriched_data.skill import EnrichedSkillData


def test_skill_cooldown_keeps_fractions_of_a_second() -> None:
    skill = make_skill(stable_key="skill:kick", display_name="Kick", type_of_skill="Attack", cooldown=800.0)
    class_display = Mock()
    class_display.get_display_name.side_effect = lambda name: name

    wikitext = SkillSectionGenerator(class_display).generate_template(
        EnrichedSkillData(skill=skill, items_with_effect=[], teaching_items=[]), "Kick"
    )

    assert "|cooldown=13.33 seconds\n" in wikitext
