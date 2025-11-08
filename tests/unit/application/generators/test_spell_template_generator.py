"""Unit tests for SpellSectionGenerator.

Tests spell page generation including XP bonus conditional display.
"""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.sections.spell import SpellSectionGenerator
from erenshor.domain.enriched_data.spell import EnrichedSpellData
from erenshor.domain.entities.spell import Spell


@pytest.fixture
def enrich_spell():
    """Helper to wrap spells in EnrichedSpellData."""

    def _enrich(
        spell: Spell,
        classes: list[str] | None = None,
        items_with_effect: list[str] | None = None,
        teaching_items: list[str] | None = None,
    ) -> EnrichedSpellData:
        return EnrichedSpellData(
            spell=spell,
            classes=classes or [],
            items_with_effect=items_with_effect or [],
            teaching_items=teaching_items or [],
        )

    return _enrich


@pytest.fixture
def mock_resolver():
    """Mock registry resolver."""

    def resolve_image_name(stable_key: str | None) -> str:
        """Resolve image name from stable key."""
        if not stable_key:
            return ""
        if ":" in stable_key:
            return stable_key.split(":")[-1]
        return stable_key

    resolver = Mock()
    resolver.resolve_image_name.side_effect = resolve_image_name
    return resolver


@pytest.fixture
def generator(mock_resolver):
    """Create spell template generator."""
    return SpellSectionGenerator(mock_resolver)


class TestSpellSectionGenerator:
    """Test suite for SpellSectionGenerator."""

    def test_xp_bonus_displayed_when_spell_has_duration(self, generator, enrich_spell):
        """Test XP bonus is displayed only when spell has duration."""

        # Spell with duration AND xp_bonus - should display xp_bonus
        spell_with_duration = Spell(
            spell_db_index=1,
            id="1",
            resource_name="BuffSpell",
            stable_key="spell:buffspell",
            spell_name="XP Buff",
            spell_desc="Grants XP bonus",
            spell_duration_in_ticks=100,  # Has duration
            xp_bonus=1.5,
        )

        enriched = enrich_spell(spell_with_duration)
        result = generator.generate_template(enriched, page_title="XP Buff")
        assert "|xp_bonus=1.5" in result

    def test_xp_bonus_not_displayed_when_spell_has_no_duration(self, generator, enrich_spell):
        """Test XP bonus is NOT displayed when spell has no duration."""

        # Spell without duration but WITH xp_bonus - should NOT display xp_bonus
        spell_without_duration = Spell(
            spell_db_index=2,
            id="2",
            resource_name="InstantSpell",
            stable_key="spell:instantspell",
            spell_name="Instant Buff",
            spell_desc="Instant effect",
            spell_duration_in_ticks=None,  # No duration
            xp_bonus=1.5,
        )

        enriched = enrich_spell(spell_without_duration)
        result = generator.generate_template(enriched, page_title="Instant Buff")
        # XP bonus should be empty since spell has no duration
        assert "|xp_bonus=\n" in result or "|xp_bonus=|" in result

    def test_duration_formatting(self, generator, enrich_spell):
        """Test spell duration is formatted in seconds (3 seconds per tick)."""

        spell = Spell(
            spell_db_index=3,
            id="3",
            resource_name="TimedSpell",
            stable_key="spell:timedspell",
            spell_name="Timed Spell",
            spell_duration_in_ticks=180,
        )

        enriched = enrich_spell(spell)
        result = generator.generate_template(enriched, page_title="Timed Spell")
        # 180 ticks * 3 seconds/tick = 540 seconds
        assert "|duration=540 seconds" in result

    def test_instant_cast_time_formatting(self, generator, enrich_spell):
        """Test instant cast time formatting."""

        # None cast time should be "Instant"
        spell_none = Spell(
            spell_db_index=4,
            id="4",
            resource_name="InstantSpell1",
            stable_key="spell:instantspell1",
            spell_name="Instant Spell 1",
            spell_charge_time=None,
        )

        enriched = enrich_spell(spell_none)
        result = generator.generate_template(enriched, page_title="Instant Spell 1")
        assert "|casttime=Instant" in result

        # Zero cast time should be "Instant"
        spell_zero = Spell(
            spell_db_index=5,
            id="5",
            resource_name="InstantSpell2",
            stable_key="spell:instantspell2",
            spell_name="Instant Spell 2",
            spell_charge_time=0,
        )

        enriched = enrich_spell(spell_zero)
        result = generator.generate_template(enriched, page_title="Instant Spell 2")
        assert "|casttime=Instant" in result

    def test_cast_time_formatting(self, generator, enrich_spell):
        """Test cast time is converted from ticks to seconds."""

        # 60 ticks = 1.0 seconds
        spell = Spell(
            spell_db_index=6,
            id="6",
            resource_name="SlowSpell",
            stable_key="spell:slowspell",
            spell_name="Slow Spell",
            spell_charge_time=60,
        )

        enriched = enrich_spell(spell)
        result = generator.generate_template(enriched, page_title="Slow Spell")
        assert "|casttime=1.0 seconds" in result

    def test_boolean_fields_formatting(self, generator, enrich_spell):
        """Test boolean fields are formatted as 'True' or empty."""

        # Spell with taunt flag
        taunt_spell = Spell(
            spell_db_index=7,
            id="7",
            resource_name="TauntSpell",
            stable_key="spell:tauntspell",
            spell_name="Taunt",
            taunt_spell=1,
        )

        enriched = enrich_spell(taunt_spell)
        result = generator.generate_template(enriched, page_title="Taunt")
        assert "|is_taunt=True" in result

        # Spell without taunt flag
        normal_spell = Spell(
            spell_db_index=8,
            id="8",
            resource_name="NormalSpell",
            stable_key="spell:normalspell",
            spell_name="Normal",
            taunt_spell=0,
        )

        enriched = enrich_spell(normal_spell)
        result = generator.generate_template(enriched, page_title="Normal")
        assert "|is_taunt=\n" in result or "|is_taunt=|" in result

    def test_generate_page_handles_none_values(self, generator, enrich_spell):
        """Test that generator handles None values gracefully."""

        spell = Spell(
            spell_db_index=9,
            id="9",
            resource_name="MinimalSpell",
            stable_key="spell:minimalspell",
            spell_name="Minimal",
            # Most fields are None
            spell_desc=None,
            spell_duration_in_ticks=None,
            xp_bonus=None,
        )

        enriched = enrich_spell(spell)
        result = generator.generate_template(enriched, page_title="Minimal")

        # Should generate valid wikitext even with minimal data
        assert "{{Ability" in result
        assert "|title=Minimal" in result
        # Empty fields should be present but empty
        assert "|description=" in result
        assert "|duration=" in result
        assert "|xp_bonus=" in result
