"""Unit tests for ItemSectionGenerator._build_spell_details_context().

Tests spell field extraction for item tooltips, including:
- Basic field extraction with all fields populated
- None/zero value handling (should produce empty strings)
- Different prefix values (proc_, effect_, aura_)
- Special cases like add_proc and status_effect resolution
"""

from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.domain.entities.spell import Spell


@pytest.fixture
def mock_resolver():
    """Mock registry resolver."""
    resolver = Mock()
    resolver.ability_link.return_value = "{{AbilityLink|Soul Tap}}"
    # Configure methods used by _build_spell_details_context for spell name resolution
    resolver.resolve_display_name.return_value = "Fireball"
    resolver.resolve_page_title.return_value = "Fireball"
    resolver.resolve_image_name.return_value = "Fireball"
    return resolver


@pytest.fixture
def generator(mock_resolver):
    """Create ItemSectionGenerator with mocked resolver."""
    return ItemSectionGenerator(mock_resolver)


@pytest.fixture
def full_spell():
    """Create a spell with all fields populated for testing."""
    return Spell(
        stable_key="spell:fireball",
        spell_name="Fireball",
        spell_desc="Hurls a ball of fire",
        special_descriptor="A powerful fire attack",
        type="Damage",
        line="Direct_Damage",
        required_level=10,
        mana_cost=50,
        aggro=100,
        spell_charge_time=60.0,  # 1 second cast time
        cooldown=5.0,
        spell_duration_in_ticks=180,  # 9 seconds (180 * 3 / 60)
        spell_range=30.0,
        target_damage=150,
        target_healing=0,
        damage_type="Fire",
        lifetap=1,
        group_effect=0,
        stun_target=0,
        charm_target=0,
        root_target=0,
        taunt_spell=0,
        hp=0,
        ac=10,
        mana=25,
        str_=5,
        dex=3,
        end_=0,
        agi=2,
        wis=0,
        int_=8,
        cha=0,
        mr=15,
        er=20,
        pr=0,
        vr=5,
        movement_speed=1.2,
        damage_shield=25,
        haste=1.1,
        percent_lifesteal=0.05,
        atk_roll_modifier=10,
        resonate_chance=15,
        add_proc_stable_key="spell:soultap",
        add_proc_chance=25,
        status_effect_to_apply_stable_key="effect:burning",
    )


@pytest.fixture
def minimal_spell():
    """Create a spell with minimal fields (most are None/0)."""
    return Spell(
        stable_key="spell:basic",
        spell_name="Basic Attack",
    )


class TestBuildSpellDetailsContext:
    """Test suite for _build_spell_details_context() method."""

    # -------------------------------------------------------------------------
    # Basic Field Extraction Tests
    # -------------------------------------------------------------------------

    def test_extracts_spell_name(self, generator, full_spell):
        """Test spell name is extracted as wiki link."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        # Spell name is rendered as a wiki link [[DisplayName]] when page exists
        assert result["proc_spell_name"] == "[[Fireball]]"

    def test_extracts_numeric_fields(self, generator, full_spell):
        """Test numeric fields are extracted as strings."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_spell_level"] == "10"
        assert result["proc_spell_duration_ticks"] == "180"
        assert result["proc_target_damage"] == "150"
        assert result["proc_cooldown"] == "5.0"
        assert result["proc_spell_range"] == "30.0"
        assert result["proc_aggro"] == "100"

    def test_extracts_string_fields(self, generator, full_spell):
        """Test string fields are extracted correctly."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_spell_type"] == "Damage"
        assert result["proc_spell_line"] == "Direct_Damage"
        assert result["proc_damage_type"] == "Fire"
        assert result["proc_special_descriptor"] == "A powerful fire attack"

    def test_extracts_stat_modifiers(self, generator, full_spell):
        """Test stat modifier fields are extracted."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_ac"] == "10"
        assert result["proc_mana"] == "25"
        assert result["proc_str"] == "5"
        assert result["proc_dex"] == "3"
        assert result["proc_int"] == "8"
        assert result["proc_agi"] == "2"

    def test_extracts_resistance_modifiers(self, generator, full_spell):
        """Test resistance modifier fields are extracted."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_mr"] == "15"
        assert result["proc_er"] == "20"
        assert result["proc_vr"] == "5"

    def test_extracts_combat_modifiers(self, generator, full_spell):
        """Test combat modifier fields are extracted."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_movement_speed"] == "1.2"
        assert result["proc_damage_shield"] == "25"
        assert result["proc_haste"] == "1.1"
        assert result["proc_percent_lifesteal"] == "0.05"
        assert result["proc_atk_roll_modifier"] == "10"
        assert result["proc_resonate_chance"] == "15"

    # -------------------------------------------------------------------------
    # Boolean Field Tests
    # -------------------------------------------------------------------------

    def test_boolean_true_becomes_true_string(self, generator, full_spell):
        """Test boolean fields with value 1 become 'True'."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_lifetap"] == "True"

    def test_boolean_false_becomes_empty_string(self, generator, full_spell):
        """Test boolean fields with value 0 become empty string."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_group_effect"] == ""
        assert result["proc_stun_target"] == ""
        assert result["proc_charm_target"] == ""
        assert result["proc_root_target"] == ""
        assert result["proc_taunt_spell"] == ""

    def test_all_boolean_fields_when_true(self, generator):
        """Test all boolean fields return 'True' when set to 1."""
        spell = Spell(
            stable_key="spell:cc",
            spell_name="Crowd Control",
            lifetap=1,
            group_effect=1,
            stun_target=1,
            charm_target=1,
            root_target=1,
            taunt_spell=1,
        )

        result = generator._build_spell_details_context(spell, prefix="proc")

        assert result["proc_lifetap"] == "True"
        assert result["proc_group_effect"] == "True"
        assert result["proc_stun_target"] == "True"
        assert result["proc_charm_target"] == "True"
        assert result["proc_root_target"] == "True"
        assert result["proc_taunt_spell"] == "True"

    # -------------------------------------------------------------------------
    # None and Zero Value Handling Tests
    # -------------------------------------------------------------------------

    def test_none_spell_returns_all_empty_strings(self, generator):
        """Test passing None spell returns dict with all empty strings."""
        result = generator._build_spell_details_context(None, prefix="proc")

        # Should have all expected keys
        assert "proc_spell_name" in result
        assert "proc_target_damage" in result
        assert "proc_hp" in result

        # All values should be empty strings
        for key, value in result.items():
            assert value == "", f"Expected empty string for {key}, got {value!r}"

    def test_zero_numeric_values_become_empty_strings(self, generator, full_spell):
        """Test zero numeric values are converted to empty strings."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        # target_healing is 0 in full_spell
        assert result["proc_target_healing"] == ""
        # hp is 0 in full_spell
        assert result["proc_hp"] == ""
        # end_ is 0 in full_spell
        assert result["proc_end"] == ""
        # pr is 0 in full_spell
        assert result["proc_pr"] == ""

    def test_minimal_spell_has_mostly_empty_values(self, generator, minimal_spell):
        """Test spell with minimal fields has mostly empty values."""
        result = generator._build_spell_details_context(minimal_spell, prefix="proc")

        # Name should be set (as wiki link since mock resolver returns "Fireball")
        assert result["proc_spell_name"] == "[[Fireball]]"

        # Most fields should be empty
        assert result["proc_spell_level"] == ""
        assert result["proc_target_damage"] == ""
        assert result["proc_spell_type"] == ""
        assert result["proc_hp"] == ""
        assert result["proc_lifetap"] == ""

    def test_none_string_fields_become_empty_strings(self, generator, minimal_spell):
        """Test None string fields are converted to empty strings."""
        result = generator._build_spell_details_context(minimal_spell, prefix="proc")

        assert result["proc_spell_type"] == ""
        assert result["proc_spell_line"] == ""
        assert result["proc_damage_type"] == ""
        assert result["proc_special_descriptor"] == ""

    # -------------------------------------------------------------------------
    # Prefix Tests
    # -------------------------------------------------------------------------

    def test_proc_prefix(self, generator, full_spell):
        """Test 'proc' prefix is applied to all field names."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        # All keys should start with proc_
        for key in result:
            assert key.startswith("proc_"), f"Key {key} should start with 'proc_'"

    def test_effect_prefix(self, generator, full_spell):
        """Test 'effect' prefix is applied to all field names."""
        result = generator._build_spell_details_context(full_spell, prefix="effect")

        # All keys should start with effect_
        for key in result:
            assert key.startswith("effect_"), f"Key {key} should start with 'effect_'"

        # Verify specific fields (spell name is wiki link)
        assert result["effect_spell_name"] == "[[Fireball]]"
        assert result["effect_target_damage"] == "150"

    def test_aura_prefix(self, generator, full_spell):
        """Test 'aura' prefix is applied to all field names."""
        result = generator._build_spell_details_context(full_spell, prefix="aura")

        # All keys should start with aura_
        for key in result:
            assert key.startswith("aura_"), f"Key {key} should start with 'aura_'"

        # Verify specific fields (spell name is wiki link)
        assert result["aura_spell_name"] == "[[Fireball]]"
        assert result["aura_target_damage"] == "150"

    def test_custom_prefix(self, generator, full_spell):
        """Test custom prefix is applied correctly."""
        result = generator._build_spell_details_context(full_spell, prefix="worn")

        # All keys should start with worn_
        for key in result:
            assert key.startswith("worn_"), f"Key {key} should start with 'worn_'"

        # Spell name is wiki link
        assert result["worn_spell_name"] == "[[Fireball]]"

    # -------------------------------------------------------------------------
    # Special Field Handling Tests
    # -------------------------------------------------------------------------

    def test_add_proc_resolved_via_ability_link(self, generator, mock_resolver, full_spell):
        """Test add_proc_stable_key is resolved via ability_link."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        # Should call ability_link with the stable key
        mock_resolver.ability_link.assert_called_once_with("spell:soultap")

        # Should return the resolved link
        assert result["proc_add_proc_name"] == "{{AbilityLink|Soul Tap}}"

    def test_add_proc_empty_when_no_stable_key(self, generator, mock_resolver, minimal_spell):
        """Test add_proc_name is empty when no add_proc_stable_key."""
        result = generator._build_spell_details_context(minimal_spell, prefix="proc")

        # Should not call ability_link
        mock_resolver.ability_link.assert_not_called()

        # Should be empty
        assert result["proc_add_proc_name"] == ""

    def test_add_proc_chance_extracted(self, generator, full_spell):
        """Test add_proc_chance is extracted correctly."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        assert result["proc_add_proc_chance"] == "25"

    def test_status_effect_name_uses_stable_key(self, generator, full_spell):
        """Test status_effect_to_apply_stable_key is resolved to wiki link."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        # Mock resolver returns "Fireball" for display_name and page_title
        # So the result is a wiki link with <br> prefix
        assert result["proc_status_effect_name"] == "<br>[[Fireball]]"

    def test_status_effect_empty_when_no_stable_key(self, generator, minimal_spell):
        """Test status_effect_name is empty when no stable key."""
        result = generator._build_spell_details_context(minimal_spell, prefix="proc")

        assert result["proc_status_effect_name"] == ""

    # -------------------------------------------------------------------------
    # Context Dictionary Structure Tests
    # -------------------------------------------------------------------------

    def test_returns_dict_with_expected_keys(self, generator, full_spell):
        """Test returned dict has all expected keys."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        expected_keys = [
            "proc_spell_name",
            "proc_spell_level",
            "proc_spell_duration_ticks",
            "proc_spell_type",
            "proc_spell_line",
            "proc_target_damage",
            "proc_target_healing",
            "proc_damage_type",
            "proc_cast_time",
            "proc_cooldown",
            "proc_spell_range",
            "proc_lifetap",
            "proc_group_effect",
            "proc_stun_target",
            "proc_charm_target",
            "proc_root_target",
            "proc_taunt_spell",
            "proc_aggro",
            "proc_status_effect_name",
            "proc_hp",
            "proc_ac",
            "proc_mana",
            "proc_str",
            "proc_dex",
            "proc_end",
            "proc_agi",
            "proc_wis",
            "proc_int",
            "proc_cha",
            "proc_mr",
            "proc_er",
            "proc_pr",
            "proc_vr",
            "proc_movement_speed",
            "proc_damage_shield",
            "proc_haste",
            "proc_percent_lifesteal",
            "proc_atk_roll_modifier",
            "proc_resonate_chance",
            "proc_add_proc_name",
            "proc_add_proc_chance",
            "proc_special_descriptor",
        ]

        for key in expected_keys:
            assert key in result, f"Missing expected key: {key}"

    def test_all_values_are_strings(self, generator, full_spell):
        """Test all values in returned dict are strings."""
        result = generator._build_spell_details_context(full_spell, prefix="proc")

        for key, value in result.items():
            assert isinstance(value, str), f"Value for {key} should be string, got {type(value)}"

    def test_none_spell_has_same_keys_as_populated_spell(self, generator, full_spell):
        """Test None spell returns same keys as populated spell."""
        result_none = generator._build_spell_details_context(None, prefix="proc")
        result_full = generator._build_spell_details_context(full_spell, prefix="proc")

        assert set(result_none.keys()) == set(result_full.keys())

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_spell_name(self, mock_resolver):
        """Test spell with empty string name returns empty when resolver returns empty."""
        # Configure resolver to return empty for this spell
        mock_resolver.resolve_display_name.return_value = ""
        mock_resolver.resolve_page_title.return_value = None
        mock_resolver.resolve_image_name.return_value = None

        generator = ItemSectionGenerator(mock_resolver)
        spell = Spell(
            stable_key="spell:empty",
            spell_name="",
        )

        result = generator._build_spell_details_context(spell, prefix="proc")

        # Empty display name with no page = empty string (plain text)
        assert result["proc_spell_name"] == ""

    def test_negative_numeric_values(self, generator):
        """Test negative numeric values are preserved."""
        spell = Spell(
            stable_key="spell:debuff",
            spell_name="Weaken",
            str_=-10,
            ac=-5,
            movement_speed=-0.2,
        )

        result = generator._build_spell_details_context(spell, prefix="proc")

        assert result["proc_str"] == "-10"
        assert result["proc_ac"] == "-5"
        assert result["proc_movement_speed"] == "-0.2"

    def test_float_precision_preserved(self, generator):
        """Test float values preserve their precision."""
        spell = Spell(
            stable_key="spell:precise",
            spell_name="Precise",
            haste=1.15,
            percent_lifesteal=0.125,
        )

        result = generator._build_spell_details_context(spell, prefix="proc")

        assert result["proc_haste"] == "1.15"
        assert result["proc_percent_lifesteal"] == "0.125"

    def test_large_numeric_values(self, generator):
        """Test large numeric values are handled correctly."""
        spell = Spell(
            stable_key="spell:massive",
            spell_name="Massive Hit",
            target_damage=999999,
            hp=100000,
        )

        result = generator._build_spell_details_context(spell, prefix="proc")

        assert result["proc_target_damage"] == "999999"
        assert result["proc_hp"] == "100000"
