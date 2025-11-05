"""Tests for legacy template removal system."""

import pytest

from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover


class TestLegacyTemplateRemover:
    """Test suite for LegacyTemplateRemover class."""

    @pytest.fixture
    def remover(self) -> LegacyTemplateRemover:
        """Create LegacyTemplateRemover instance."""
        return LegacyTemplateRemover()

    # -------------------------------------------------------------------------
    # Basic Template Replacement Tests
    # -------------------------------------------------------------------------

    def test_replace_character_with_enemy(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Character}} with {{Enemy}}."""
        wikitext = "{{Character|name=Goblin|level=5}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Enemy" in result
        assert "{{Character" not in result
        assert "|name=Goblin" in result
        assert "|level=5" in result

    def test_replace_pet_with_enemy(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Pet}} with {{Enemy}}."""
        wikitext = "{{Pet|name=Wolf Companion|type=Pet}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Enemy" in result
        assert "{{Pet" not in result
        assert "|name=Wolf Companion" in result
        assert "|type=Pet" in result

    def test_replace_consumable_with_item(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Consumable}} with {{Item}}."""
        wikitext = "{{Consumable|name=Health Potion|type=Food}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Item" in result
        assert "{{Consumable" not in result
        assert "|name=Health Potion" in result
        assert "|type=Food" in result

    def test_replace_weapon_with_item(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Weapon}} with {{Item}}."""
        wikitext = "{{Weapon|name=Iron Sword|damage=10}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Item" in result
        assert "{{Weapon" not in result
        assert "|name=Iron Sword" in result
        assert "|damage=10" in result

    def test_replace_armor_with_item(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Armor}} with {{Item}}."""
        wikitext = "{{Armor|name=Iron Helmet|armor=5}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Item" in result
        assert "{{Armor" not in result
        assert "|name=Iron Helmet" in result
        assert "|armor=5" in result

    def test_replace_auras_with_item(self, remover: LegacyTemplateRemover) -> None:
        """Test replacing {{Auras}} with {{Item}}."""
        wikitext = "{{Auras|name=Blessing of Might|effect=+10 Strength}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Item" in result
        assert "{{Auras" not in result
        assert "|name=Blessing of Might" in result

    # -------------------------------------------------------------------------
    # Template Removal Tests
    # -------------------------------------------------------------------------

    def test_remove_enemy_stats_template(self, remover: LegacyTemplateRemover) -> None:
        """Test removing {{Enemy Stats}} template entirely."""
        wikitext = "{{Enemy Stats|hp=100|damage=50}}"
        result = remover.remove_legacy_templates(wikitext)

        # Template should be completely removed
        assert "{{Enemy Stats" not in result
        assert result.strip() == ""

    def test_remove_enemy_stats_preserves_other_content(self, remover: LegacyTemplateRemover) -> None:
        """Test removing {{Enemy Stats}} preserves surrounding content."""
        wikitext = "Some text before\n\n{{Enemy Stats|hp=100}}\n\nSome text after"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Enemy Stats" not in result
        assert "Some text before" in result
        assert "Some text after" in result

    # -------------------------------------------------------------------------
    # Multiple Templates Tests
    # -------------------------------------------------------------------------

    def test_multiple_legacy_templates_on_same_page(self, remover: LegacyTemplateRemover) -> None:
        """Test handling multiple legacy templates on same page."""
        wikitext = "{{Character|name=Goblin|level=5}}\n{{Consumable|name=Potion}}\n{{Pet|name=Wolf}}"
        result = remover.remove_legacy_templates(wikitext)

        # All legacy templates should be replaced
        assert "{{Character" not in result
        assert "{{Consumable" not in result
        assert "{{Pet" not in result

        # Should have 2 Enemy templates (Character + Pet) and 1 Item (Consumable)
        assert result.count("{{Enemy") == 2
        assert result.count("{{Item") == 1

    def test_multiple_instances_of_same_legacy_template(self, remover: LegacyTemplateRemover) -> None:
        """Test handling multiple instances of the same legacy template."""
        wikitext = "{{Consumable|name=Potion1}}\n{{Consumable|name=Potion2}}\n{{Consumable|name=Potion3}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Consumable" not in result
        assert result.count("{{Item") == 3

    def test_mixed_legacy_and_active_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test page with both legacy and active templates."""
        wikitext = "{{Item|name=Active Item}}\n{{Consumable|name=Legacy Consumable}}\n{{Enemy|name=Active Enemy}}"
        result = remover.remove_legacy_templates(wikitext)

        # Legacy template should be replaced
        assert "{{Consumable" not in result

        # Active templates should remain unchanged
        assert result.count("{{Item") == 2  # Original + replaced Consumable
        assert result.count("{{Enemy") == 1  # Original only

    # -------------------------------------------------------------------------
    # Active Template Preservation Tests
    # -------------------------------------------------------------------------

    def test_preserve_active_item_template(self, remover: LegacyTemplateRemover) -> None:
        """Test that {{Item}} template is not modified."""
        wikitext = "{{Item|name=Sword|damage=10}}"
        result = remover.remove_legacy_templates(wikitext)

        # Should remain exactly the same
        assert result == wikitext

    def test_preserve_active_enemy_template(self, remover: LegacyTemplateRemover) -> None:
        """Test that {{Enemy}} template is not modified."""
        wikitext = "{{Enemy|name=Dragon|level=20}}"
        result = remover.remove_legacy_templates(wikitext)

        # Should remain exactly the same
        assert result == wikitext

    def test_preserve_fancy_weapon_template(self, remover: LegacyTemplateRemover) -> None:
        """Test that {{Fancy-weapon}} template is not modified."""
        wikitext = "{{Fancy-weapon|name=Godly Sword|damage=100|tier=Godly}}"
        result = remover.remove_legacy_templates(wikitext)

        # Should remain exactly the same
        assert result == wikitext

    def test_preserve_fancy_armor_template(self, remover: LegacyTemplateRemover) -> None:
        """Test that {{Fancy-armor}} template is not modified."""
        wikitext = "{{Fancy-armor|name=Blessed Helmet|armor=50|tier=Blessed}}"
        result = remover.remove_legacy_templates(wikitext)

        # Should remain exactly the same
        assert result == wikitext

    # -------------------------------------------------------------------------
    # Parameter Preservation Tests
    # -------------------------------------------------------------------------

    def test_preserve_all_parameters(self, remover: LegacyTemplateRemover) -> None:
        """Test that all template parameters are preserved during replacement."""
        wikitext = "{{Character|name=Goblin|level=5|health=100|mana=50|faction=Enemy|type=Boss}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Enemy" in result
        assert "|name=Goblin" in result
        assert "|level=5" in result
        assert "|health=100" in result
        assert "|mana=50" in result
        assert "|faction=Enemy" in result
        assert "|type=Boss" in result

    def test_preserve_complex_parameter_values(self, remover: LegacyTemplateRemover) -> None:
        """Test preserving complex parameter values (wiki links, lists, etc.)."""
        wikitext = (
            "{{Consumable"
            "|name=[[Health Potion]]"
            "|effects=[[Restore Health]]<br>[[Remove Poison]]"
            "|source=[[Vendor:Alchemist]]|[[Drop:Goblin]]"
            "}}"
        )
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Item" in result
        assert "[[Health Potion]]" in result
        assert "[[Restore Health]]" in result
        assert "[[Remove Poison]]" in result
        assert "[[Vendor:Alchemist]]" in result

    def test_preserve_empty_parameters(self, remover: LegacyTemplateRemover) -> None:
        """Test handling of empty parameter values."""
        wikitext = "{{Character|name=Goblin|description=|faction=}}"
        result = remover.remove_legacy_templates(wikitext)

        assert "{{Enemy" in result
        assert "|name=Goblin" in result
        # Empty params should be preserved
        assert "|description=" in result
        assert "|faction=" in result

    # -------------------------------------------------------------------------
    # Nested Template Tests
    # -------------------------------------------------------------------------

    def test_nested_templates_in_parameters(self, remover: LegacyTemplateRemover) -> None:
        """Test handling nested templates within parameters."""
        wikitext = "{{Consumable|name=Potion|effect={{Spell|name=Heal}}}}"
        result = remover.remove_legacy_templates(wikitext)

        # Outer template should be replaced
        assert "{{Item" in result
        # Inner template should be preserved
        assert "{{Spell" in result
        assert "|name=Heal" in result

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_wikitext(self, remover: LegacyTemplateRemover) -> None:
        """Test handling empty wikitext."""
        result = remover.remove_legacy_templates("")
        assert result == ""

    def test_whitespace_only_wikitext(self, remover: LegacyTemplateRemover) -> None:
        """Test handling whitespace-only wikitext."""
        result = remover.remove_legacy_templates("   \n\t  \n")
        assert result == "   \n\t  \n"

    def test_wikitext_without_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test wikitext that contains no templates at all."""
        wikitext = "This is just plain text with no templates."
        result = remover.remove_legacy_templates(wikitext)
        assert result == wikitext

    def test_wikitext_with_only_active_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test wikitext that only contains active templates."""
        wikitext = "{{Item|name=Sword}} and {{Enemy|name=Goblin}}"
        result = remover.remove_legacy_templates(wikitext)
        assert result == wikitext

    def test_malformed_template_syntax(self, remover: LegacyTemplateRemover) -> None:
        """Test handling of malformed template syntax."""
        # Unclosed template
        wikitext = "{{Character|name=Goblin"
        result = remover.remove_legacy_templates(wikitext)
        # Should not crash, may return original or partially processed
        assert result is not None

    def test_case_insensitive_template_names(self, remover: LegacyTemplateRemover) -> None:
        """Test that template name matching is case-insensitive."""
        # MediaWiki template names are case-insensitive
        wikitext = "{{character|name=Goblin}} {{CHARACTER|name=Orc}} {{ChArAcTeR|name=Troll}}"
        result = remover.remove_legacy_templates(wikitext)

        # All should be replaced regardless of case
        assert "{{character" not in result.lower()
        assert result.count("{{Enemy") == 3

    def test_template_with_whitespace_in_name(self, remover: LegacyTemplateRemover) -> None:
        """Test handling templates with whitespace in names."""
        wikitext = "{{ Character |name=Goblin}}"
        result = remover.remove_legacy_templates(wikitext)

        # Template parser should handle whitespace
        assert "{{Enemy" in result
        assert "Character" not in result

    # -------------------------------------------------------------------------
    # has_legacy_templates() Tests
    # -------------------------------------------------------------------------

    def test_has_legacy_templates_returns_true_for_legacy(self, remover: LegacyTemplateRemover) -> None:
        """Test has_legacy_templates() returns True for legacy templates."""
        wikitext = "{{Character|name=Goblin}}"
        assert remover.has_legacy_templates(wikitext) is True

    def test_has_legacy_templates_returns_false_for_active(self, remover: LegacyTemplateRemover) -> None:
        """Test has_legacy_templates() returns False for active templates."""
        wikitext = "{{Item|name=Sword}} and {{Enemy|name=Goblin}}"
        assert remover.has_legacy_templates(wikitext) is False

    def test_has_legacy_templates_returns_true_for_removal(self, remover: LegacyTemplateRemover) -> None:
        """Test has_legacy_templates() returns True for templates to remove."""
        wikitext = "{{Enemy Stats|hp=100}}"
        assert remover.has_legacy_templates(wikitext) is True

    def test_has_legacy_templates_returns_false_for_empty(self, remover: LegacyTemplateRemover) -> None:
        """Test has_legacy_templates() returns False for empty wikitext."""
        assert remover.has_legacy_templates("") is False
        assert remover.has_legacy_templates("   ") is False

    def test_has_legacy_templates_mixed_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test has_legacy_templates() with mixed legacy and active templates."""
        wikitext = "{{Item|name=Sword}} {{Character|name=Goblin}}"
        assert remover.has_legacy_templates(wikitext) is True

    # -------------------------------------------------------------------------
    # get_legacy_template_summary() Tests
    # -------------------------------------------------------------------------

    def test_get_legacy_template_summary_single_template(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() with single legacy template."""
        wikitext = "{{Character|name=Goblin}}"
        summary = remover.get_legacy_template_summary(wikitext)

        assert summary == {"Character": 1}

    def test_get_legacy_template_summary_multiple_same_template(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() with multiple instances of same template."""
        wikitext = "{{Consumable|name=Potion1}} {{Consumable|name=Potion2}}"
        summary = remover.get_legacy_template_summary(wikitext)

        assert summary == {"Consumable": 2}

    def test_get_legacy_template_summary_multiple_different_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() with multiple different templates."""
        wikitext = "{{Character|name=Goblin}} {{Consumable|name=Potion}} {{Pet|name=Wolf}}"
        summary = remover.get_legacy_template_summary(wikitext)

        assert summary == {"Character": 1, "Consumable": 1, "Pet": 1}

    def test_get_legacy_template_summary_template_to_remove(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() includes templates to remove."""
        wikitext = "{{Enemy Stats|hp=100}}"
        summary = remover.get_legacy_template_summary(wikitext)

        assert summary == {"Enemy Stats": 1}

    def test_get_legacy_template_summary_empty_wikitext(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() with empty wikitext."""
        summary = remover.get_legacy_template_summary("")
        assert summary == {}

    def test_get_legacy_template_summary_no_legacy_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test get_legacy_template_summary() with no legacy templates."""
        wikitext = "{{Item|name=Sword}} {{Enemy|name=Goblin}}"
        summary = remover.get_legacy_template_summary(wikitext)

        assert summary == {}

    # -------------------------------------------------------------------------
    # Integration Tests (Real-World Scenarios)
    # -------------------------------------------------------------------------

    def test_weapon_page_with_multiple_templates(self, remover: LegacyTemplateRemover) -> None:
        """Test realistic weapon page with {{Item}} + {{Fancy-weapon}} templates."""
        wikitext = """
{{Item|name=Iron Sword|source=Vendor}}

{{Fancy-weapon|name=Iron Sword|tier=Normal|damage=10}}
{{Fancy-weapon|name=Iron Sword|tier=Blessed|damage=15}}
{{Fancy-weapon|name=Iron Sword|tier=Godly|damage=20}}
"""
        result = remover.remove_legacy_templates(wikitext)

        # Should preserve all templates unchanged (no legacy templates)
        assert result.count("{{Item") == 1
        assert result.count("{{Fancy-weapon") == 3

    def test_character_page_with_enemy_stats_removal(self, remover: LegacyTemplateRemover) -> None:
        """Test character page replacing {{Character}} and removing {{Enemy Stats}}."""
        wikitext = """
{{Character|name=Goblin Warrior|level=5|faction=Goblin Clan}}

{{Enemy Stats|hp=100|damage=50}}

Some description text here.
"""
        result = remover.remove_legacy_templates(wikitext)

        # {{Character}} should become {{Enemy}}
        assert "{{Enemy" in result
        assert "{{Character" not in result

        # {{Enemy Stats}} should be removed
        assert "{{Enemy Stats" not in result

        # Description should be preserved
        assert "Some description text here." in result

    def test_consumable_page_migration(self, remover: LegacyTemplateRemover) -> None:
        """Test migrating consumable page from {{Consumable}} to {{Item}}."""
        wikitext = """
{{Consumable
|name=Health Potion
|type=[[Consumables|Consumable]]
|effects=[[Restore Health]]
|buy=100
|sell=25
}}

; Description
A red potion that restores health.
"""
        result = remover.remove_legacy_templates(wikitext)

        # Should become {{Item}}
        assert "{{Item" in result
        assert "{{Consumable" not in result

        # All fields should be preserved
        assert "|name=Health Potion" in result
        assert "[[Restore Health]]" in result

        # Description should be preserved
        assert "A red potion that restores health." in result
