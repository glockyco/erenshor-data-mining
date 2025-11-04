"""Unit tests for SpellTemplateGenerator.

Tests spell page generation including XP bonus conditional display.
"""

from erenshor.application.generators.spell_template_generator import SpellTemplateGenerator
from erenshor.domain.entities.spell import Spell


class TestSpellTemplateGenerator:
    """Test suite for SpellTemplateGenerator."""

    def test_xp_bonus_displayed_when_spell_has_duration(self):
        """Test XP bonus is displayed only when spell has duration."""
        generator = SpellTemplateGenerator()

        # Spell with duration AND xp_bonus - should display xp_bonus
        spell_with_duration = Spell(
            spell_db_index=1,
            id="1",
            resource_name="BuffSpell",
            spell_name="XP Buff",
            spell_desc="Grants XP bonus",
            spell_duration_in_ticks=100,  # Has duration
            xp_bonus=1.5,
        )

        result = generator.generate_template(spell_with_duration, page_title="XP Buff")
        assert "|xp_bonus=1.5" in result

    def test_xp_bonus_not_displayed_when_spell_has_no_duration(self):
        """Test XP bonus is NOT displayed when spell has no duration."""
        generator = SpellTemplateGenerator()

        # Spell without duration but WITH xp_bonus - should NOT display xp_bonus
        spell_without_duration = Spell(
            spell_db_index=2,
            id="2",
            resource_name="InstantSpell",
            spell_name="Instant Buff",
            spell_desc="Instant effect",
            spell_duration_in_ticks=None,  # No duration
            xp_bonus=1.5,
        )

        result = generator.generate_template(spell_without_duration, page_title="Instant Buff")
        # XP bonus should be empty since spell has no duration
        assert "|xp_bonus=\n" in result or "|xp_bonus=|" in result

    def test_duration_formatting(self):
        """Test spell duration is formatted in ticks."""
        generator = SpellTemplateGenerator()

        spell = Spell(
            spell_db_index=3,
            id="3",
            resource_name="TimedSpell",
            spell_name="Timed Spell",
            spell_duration_in_ticks=180,
        )

        result = generator.generate_template(spell, page_title="Timed Spell")
        assert "|duration=180 ticks" in result

    def test_instant_cast_time_formatting(self):
        """Test instant cast time formatting."""
        generator = SpellTemplateGenerator()

        # None cast time should be "Instant"
        spell_none = Spell(
            spell_db_index=4,
            id="4",
            resource_name="InstantSpell1",
            spell_name="Instant Spell 1",
            spell_charge_time=None,
        )

        result = generator.generate_template(spell_none, page_title="Instant Spell 1")
        assert "|casttime=Instant" in result

        # Zero cast time should be "Instant"
        spell_zero = Spell(
            spell_db_index=5,
            id="5",
            resource_name="InstantSpell2",
            spell_name="Instant Spell 2",
            spell_charge_time=0,
        )

        result = generator.generate_template(spell_zero, page_title="Instant Spell 2")
        assert "|casttime=Instant" in result

    def test_cast_time_formatting(self):
        """Test cast time is converted from ticks to seconds."""
        generator = SpellTemplateGenerator()

        # 60 ticks = 1.0 seconds
        spell = Spell(
            spell_db_index=6,
            id="6",
            resource_name="SlowSpell",
            spell_name="Slow Spell",
            spell_charge_time=60,
        )

        result = generator.generate_template(spell, page_title="Slow Spell")
        assert "|casttime=1.0 seconds" in result

    def test_boolean_fields_formatting(self):
        """Test boolean fields are formatted as 'True' or empty."""
        generator = SpellTemplateGenerator()

        # Spell with taunt flag
        taunt_spell = Spell(
            spell_db_index=7,
            id="7",
            resource_name="TauntSpell",
            spell_name="Taunt",
            taunt_spell=1,
        )

        result = generator.generate_template(taunt_spell, page_title="Taunt")
        assert "|is_taunt=True" in result

        # Spell without taunt flag
        normal_spell = Spell(
            spell_db_index=8,
            id="8",
            resource_name="NormalSpell",
            spell_name="Normal",
            taunt_spell=0,
        )

        result = generator.generate_template(normal_spell, page_title="Normal")
        assert "|is_taunt=\n" in result or "|is_taunt=|" in result

    def test_generate_page_handles_none_values(self):
        """Test that generator handles None values gracefully."""
        generator = SpellTemplateGenerator()

        spell = Spell(
            spell_db_index=9,
            id="9",
            resource_name="MinimalSpell",
            spell_name="Minimal",
            # Most fields are None
            spell_desc=None,
            spell_duration_in_ticks=None,
            xp_bonus=None,
        )

        result = generator.generate_template(spell, page_title="Minimal")

        # Should generate valid wikitext even with minimal data
        assert "{{Ability" in result
        assert "|title=Minimal" in result
        # Empty fields should be present but empty
        assert "|description=" in result
        assert "|duration=" in result
        assert "|xp_bonus=" in result
