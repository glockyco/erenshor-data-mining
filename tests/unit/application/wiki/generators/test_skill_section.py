"""Unit tests for the legacy skill section."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
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


@pytest.mark.parametrize(("name", "capacity"), [("Simple Song", 2), ("Elrehon's Cacophony", 5)])
def test_song_capacity_is_not_target_damage(name: str, capacity: int) -> None:
    skill = make_skill(display_name=name, type_of_skill="Other", bard_song=1, skill_power=capacity)
    wikitext = SkillSectionGenerator(Mock()).generate_template(
        EnrichedSkillData(skill=skill, items_with_effect=[], teaching_items=[]), name
    )
    assert f"|song_capacity={capacity}\n" in wikitext
    assert "|target_damage=\n" in wikitext
    assert "|casttime=\n" in wikitext


def test_hum_has_no_activated_skill_cooldown() -> None:
    skill = make_skill(display_name="Hum", type_of_skill="Other", bard_song=1, hum=1, skill_power=1, cooldown=360.0)
    wikitext = SkillSectionGenerator(Mock()).generate_template(
        EnrichedSkillData(skill=skill, items_with_effect=[], teaching_items=[]), "Hum"
    )
    assert "|song_capacity=1\n" in wikitext
    assert "|cooldown=\n" in wikitext
    assert "every 10 seconds without spending mana" in wikitext


def test_caesura_reports_runtime_mana_in_separate_details() -> None:
    skill = make_skill(
        id="1361600",
        display_name="Caesura",
        type_of_skill="Other",
        skill_power=1,
        skill_desc="Restore 50% of your missing mana",
    )
    wikitext = SkillSectionGenerator(Mock()).generate_template(
        EnrichedSkillData(skill=skill, items_with_effect=[], teaching_items=[]), "Caesura"
    )
    assert "|description=Restore 50% of your missing mana\n" in wikitext
    assert "|bard_skill_details=Restores 50% of maximum mana" in wikitext
    assert "|target_damage=\n" in wikitext
