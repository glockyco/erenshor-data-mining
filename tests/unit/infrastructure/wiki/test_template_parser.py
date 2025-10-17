"""Unit tests for MediaWiki template parser.

These tests verify template parsing, manipulation, and generation functionality
using the mwparserfromhell library wrapper.
"""

import pytest

from erenshor.infrastructure.wiki import (
    TemplateNotFoundError,
    TemplateParser,
)


class TestTemplateParserParsing:
    """Test template parsing functionality."""

    def test_parse_simple_template(self) -> None:
        """Test parsing a simple template."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        assert code is not None
        assert "Item" in str(code)

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        parser = TemplateParser()
        code = parser.parse("")
        assert code is not None
        assert str(code) == ""

    def test_parse_complex_wikitext(self) -> None:
        """Test parsing wikitext with multiple elements."""
        parser = TemplateParser()
        wikitext = """
        = Header =
        Some text here.
        {{Item|name=Sword|damage=10}}
        More text.
        {{Weapon|type=melee}}
        """
        code = parser.parse(wikitext)
        assert code is not None
        assert "Header" in str(code)
        assert "Item" in str(code)
        assert "Weapon" in str(code)

    def test_parse_preserves_structure(self) -> None:
        """Test that parsing preserves wiki structure."""
        parser = TemplateParser()
        wikitext = "{{Item|name=Sword}} <!-- comment --> more text"
        code = parser.parse(wikitext)
        rendered = parser.render(code)
        assert "<!-- comment -->" in rendered
        assert "more text" in rendered


class TestTemplateParserFinding:
    """Test finding templates in wikitext."""

    def test_find_templates_single_match(self) -> None:
        """Test finding a single template."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        templates = parser.find_templates(code, ["Item"])
        assert len(templates) == 1

    def test_find_templates_multiple_matches(self) -> None:
        """Test finding multiple templates of same type."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} {{Item|name=Shield}}")
        templates = parser.find_templates(code, ["Item"])
        assert len(templates) == 2

    def test_find_templates_multiple_names(self) -> None:
        """Test finding templates with multiple possible names."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} {{Weapon|damage=10}}")
        templates = parser.find_templates(code, ["Item", "Weapon"])
        assert len(templates) == 2

    def test_find_templates_case_insensitive(self) -> None:
        """Test that template finding is case-insensitive."""
        parser = TemplateParser()
        code = parser.parse("{{item|name=Sword}}")
        templates = parser.find_templates(code, ["Item"])
        assert len(templates) == 1

        templates = parser.find_templates(code, ["ITEM"])
        assert len(templates) == 1

    def test_find_templates_no_match(self) -> None:
        """Test finding templates when none match."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        templates = parser.find_templates(code, ["Weapon"])
        assert len(templates) == 0

    def test_find_templates_empty_wikitext(self) -> None:
        """Test finding templates in empty wikitext."""
        parser = TemplateParser()
        code = parser.parse("")
        templates = parser.find_templates(code, ["Item"])
        assert len(templates) == 0

    def test_find_template_success(self) -> None:
        """Test find_template returns first match."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} {{Item|name=Shield}}")
        template = parser.find_template(code, ["Item"])
        assert template is not None
        params = parser.get_params(template)
        assert params["name"] == "Sword"

    def test_find_template_not_found(self) -> None:
        """Test find_template raises error when not found."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        with pytest.raises(TemplateNotFoundError, match="No template found matching"):
            parser.find_template(code, ["Weapon"])


class TestTemplateParserParameters:
    """Test getting and setting template parameters."""

    def test_get_params_single_param(self) -> None:
        """Test getting single parameter."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)
        assert params == {"name": "Sword"}

    def test_get_params_multiple_params(self) -> None:
        """Test getting multiple parameters."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10|level=5}}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)
        assert params == {"name": "Sword", "damage": "10", "level": "5"}

    def test_get_params_no_params(self) -> None:
        """Test getting parameters from template with none."""
        parser = TemplateParser()
        code = parser.parse("{{Item}}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)
        assert params == {}

    def test_get_params_strips_whitespace(self) -> None:
        """Test that parameter names and values are stripped."""
        parser = TemplateParser()
        code = parser.parse("{{Item| name = Sword | damage = 10 }}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)
        assert params == {"name": "Sword", "damage": "10"}

    def test_get_param_exists(self) -> None:
        """Test getting single parameter that exists."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10}}")
        template = parser.find_template(code, ["Item"])
        assert parser.get_param(template, "name") == "Sword"
        assert parser.get_param(template, "damage") == "10"

    def test_get_param_not_exists(self) -> None:
        """Test getting parameter that doesn't exist."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        template = parser.find_template(code, ["Item"])
        assert parser.get_param(template, "damage") is None

    def test_get_param_with_default(self) -> None:
        """Test getting parameter with default value."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        template = parser.find_template(code, ["Item"])
        assert parser.get_param(template, "damage", "0") == "0"
        assert parser.get_param(template, "name", "Unknown") == "Sword"

    def test_set_param_update_existing(self) -> None:
        """Test updating existing parameter."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10}}")
        template = parser.find_template(code, ["Item"])
        parser.set_param(template, "damage", "15")
        assert parser.get_param(template, "damage") == "15"

    def test_set_param_add_new(self) -> None:
        """Test adding new parameter."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        template = parser.find_template(code, ["Item"])
        parser.set_param(template, "damage", "10")
        assert parser.get_param(template, "damage") == "10"

    def test_set_param_preserves_other_params(self) -> None:
        """Test that setting parameter preserves others."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10|level=5}}")
        template = parser.find_template(code, ["Item"])
        parser.set_param(template, "damage", "15")
        params = parser.get_params(template)
        assert params["name"] == "Sword"
        assert params["damage"] == "15"
        assert params["level"] == "5"

    def test_remove_param_exists(self) -> None:
        """Test removing parameter that exists."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10|level=5}}")
        template = parser.find_template(code, ["Item"])
        parser.remove_param(template, "damage")
        params = parser.get_params(template)
        assert "damage" not in params
        assert params["name"] == "Sword"
        assert params["level"] == "5"

    def test_remove_param_not_exists(self) -> None:
        """Test removing parameter that doesn't exist (idempotent)."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        template = parser.find_template(code, ["Item"])
        # Should not raise error
        parser.remove_param(template, "damage")
        params = parser.get_params(template)
        assert params == {"name": "Sword"}


class TestTemplateParserReplacement:
    """Test replacing and removing templates."""

    def test_replace_template_with_new_template(self) -> None:
        """Test replacing template with different template."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} is a weapon")
        template = parser.find_template(code, ["Item"])
        result = parser.replace_template(code, template, "{{Weapon|damage=10}}")
        assert "{{Weapon|damage=10}}" in result
        assert "{{Item" not in result
        assert "is a weapon" in result

    def test_replace_template_with_text(self) -> None:
        """Test replacing template with plain text."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} is a weapon")
        template = parser.find_template(code, ["Item"])
        result = parser.replace_template(code, template, "The sword")
        assert "The sword" in result
        assert "{{Item" not in result

    def test_replace_template_with_empty(self) -> None:
        """Test replacing template with empty string."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} is a weapon")
        template = parser.find_template(code, ["Item"])
        result = parser.replace_template(code, template, "")
        assert "{{Item" not in result
        assert "is a weapon" in result

    def test_remove_template(self) -> None:
        """Test removing template from wikitext."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} is a weapon")
        template = parser.find_template(code, ["Item"])
        result = parser.remove_template(code, template)
        assert "{{Item" not in result
        assert "is a weapon" in result

    def test_replace_multiple_templates(self) -> None:
        """Test replacing multiple templates."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}} and {{Item|name=Shield}}")
        templates = parser.find_templates(code, ["Item"])

        # Replace first template
        result = parser.replace_template(code, templates[0], "{{Weapon|name=Sword}}")
        assert "{{Weapon|name=Sword}}" in result

        # Parse again and replace second template
        code = parser.parse(result)
        templates = parser.find_templates(code, ["Item"])
        result = parser.replace_template(code, templates[0], "{{Armor|name=Shield}}")
        assert "{{Weapon|name=Sword}}" in result
        assert "{{Armor|name=Shield}}" in result


class TestTemplateParserGeneration:
    """Test generating template strings."""

    def test_generate_template_multiline(self) -> None:
        """Test generating multi-line template."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"name": "Sword", "damage": "10"})
        assert template.startswith("{{Item")
        assert "|name=Sword" in template
        assert "|damage=10" in template
        assert template.endswith("}}")

    def test_generate_template_inline(self) -> None:
        """Test generating inline template."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"name": "Sword", "damage": "10"}, inline=True)
        valid_templates = {"{{Item|name=Sword|damage=10}}", "{{Item|damage=10|name=Sword}}"}
        assert template in valid_templates
        assert "\n" not in template

    def test_generate_template_no_params(self) -> None:
        """Test generating template with no parameters."""
        parser = TemplateParser()
        template_multi = parser.generate_template("Item", {})
        assert template_multi == "{{Item\n}}"

        template_inline = parser.generate_template("Item", {}, inline=True)
        assert template_inline == "{{Item}}"

    def test_generate_template_single_param(self) -> None:
        """Test generating template with single parameter."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"name": "Sword"}, inline=True)
        assert template == "{{Item|name=Sword}}"

    def test_generate_template_int_value(self) -> None:
        """Test generating template with integer value."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"damage": 10}, inline=True)
        assert template == "{{Item|damage=10}}"

    def test_generate_template_float_value(self) -> None:
        """Test generating template with float value."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"damage": 10.5}, inline=True)
        assert template == "{{Item|damage=10.5}}"

    def test_generate_template_bool_value(self) -> None:
        """Test generating template with boolean value."""
        parser = TemplateParser()
        template_true = parser.generate_template("Item", {"enabled": True}, inline=True)
        assert template_true == "{{Item|enabled=yes}}"

        template_false = parser.generate_template("Item", {"enabled": False}, inline=True)
        assert template_false == "{{Item|enabled=no}}"

    def test_generate_template_none_value(self) -> None:
        """Test generating template with None value."""
        parser = TemplateParser()
        template = parser.generate_template("Item", {"optional": None}, inline=True)
        assert template == "{{Item|optional=}}"

    def test_generate_template_mixed_types(self) -> None:
        """Test generating template with mixed value types."""
        parser = TemplateParser()
        template = parser.generate_template(
            "Item",
            {"name": "Sword", "damage": 10, "level": 5.5, "rare": True, "note": None},
            inline=True,
        )
        # Check all parameters present (order may vary)
        assert "name=Sword" in template
        assert "damage=10" in template
        assert "level=5.5" in template
        assert "rare=yes" in template
        assert "note=" in template

    def test_generate_and_parse_roundtrip(self) -> None:
        """Test that generated template can be parsed."""
        parser = TemplateParser()
        original_params = {"name": "Sword", "damage": "10", "level": "5"}
        generated = parser.generate_template("Item", original_params, inline=True)

        # Parse the generated template
        code = parser.parse(generated)
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)

        assert params == original_params


class TestTemplateParserRendering:
    """Test rendering wikicode to string."""

    def test_render_simple(self) -> None:
        """Test rendering simple wikicode."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        rendered = parser.render(code)
        assert "{{Item|name=Sword}}" in rendered

    def test_render_complex(self) -> None:
        """Test rendering complex wikicode."""
        parser = TemplateParser()
        original = "= Header =\n{{Item|name=Sword}}\nSome text"
        code = parser.parse(original)
        rendered = parser.render(code)
        assert "Header" in rendered
        assert "{{Item" in rendered
        assert "Some text" in rendered

    def test_render_after_modification(self) -> None:
        """Test rendering after modifying templates."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword|damage=10}}")
        template = parser.find_template(code, ["Item"])
        parser.set_param(template, "damage", "15")
        rendered = parser.render(code)
        assert "damage=15" in rendered


class TestTemplateParserIntegration:
    """Integration tests for complete workflows."""

    def test_workflow_parse_find_modify_render(self) -> None:
        """Test complete workflow: parse -> find -> modify -> render."""
        parser = TemplateParser()

        # Parse wikitext
        wikitext = "{{Item|name=Sword|damage=10}} is a weapon."
        code = parser.parse(wikitext)

        # Find template
        template = parser.find_template(code, ["Item"])

        # Modify parameters
        parser.set_param(template, "damage", "15")
        parser.set_param(template, "level", "5")

        # Render back to string
        result = parser.render(code)

        # Verify changes
        assert "damage=15" in result
        assert "level=5" in result
        assert "is a weapon" in result

    def test_workflow_extract_and_regenerate(self) -> None:
        """Test extracting params and regenerating template."""
        parser = TemplateParser()

        # Parse existing template
        code = parser.parse("{{Item|name=Sword|damage=10}}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)

        # Modify params
        params["damage"] = "15"
        params["level"] = "5"

        # Generate new template
        new_template = parser.generate_template("Item", params, inline=True)

        # Verify new template
        assert "name=Sword" in new_template
        assert "damage=15" in new_template
        assert "level=5" in new_template

    def test_workflow_replace_infobox(self) -> None:
        """Test replacing infobox template (common wiki operation)."""
        parser = TemplateParser()

        # Original page with old infobox
        page_text = """{{Item|name=Old Sword|damage=5}}

        Some page content here.

        == Description ==
        A rusty old sword.
        """

        # Parse and find old infobox
        code = parser.parse(page_text)
        old_template = parser.find_template(code, ["Item"])

        # Generate new infobox
        new_infobox = parser.generate_template("Item", {"name": "New Sword", "damage": "15", "level": "10"})

        # Replace old with new
        result = parser.replace_template(code, old_template, new_infobox)

        # Verify replacement
        assert "New Sword" in result
        assert "damage=15" in result
        assert "level=10" in result
        assert "Old Sword" not in result
        assert "Some page content here" in result
        assert "Description" in result

    def test_workflow_preserve_manual_edits(self) -> None:
        """Test preserving manual content while updating template."""
        parser = TemplateParser()

        # Page with template and manual content
        page_text = """{{Item|name=Sword|damage=10}}

        This is manually written content about the sword.
        <!-- Manual comment -->

        == Acquisition ==
        Drops from goblins.
        """

        # Parse and update only the template
        code = parser.parse(page_text)
        template = parser.find_template(code, ["Item"])
        parser.set_param(template, "damage", "15")
        result = parser.render(code)

        # Verify manual content preserved
        assert "damage=15" in result
        assert "manually written content" in result
        assert "<!-- Manual comment -->" in result
        assert "Acquisition" in result
        assert "Drops from goblins" in result

    def test_workflow_multiple_templates(self) -> None:
        """Test handling page with multiple templates."""
        parser = TemplateParser()

        page_text = """{{Item|name=Sword|damage=10}}

        The sword deals {{Damage|type=physical|amount=10}} damage.

        {{Category|Weapons}}
        """

        code = parser.parse(page_text)

        # Find and update Item template
        item_template = parser.find_template(code, ["Item"])
        parser.set_param(item_template, "damage", "15")

        # Find and update Damage template
        damage_template = parser.find_template(code, ["Damage"])
        parser.set_param(damage_template, "amount", "15")

        result = parser.render(code)

        # Verify both templates updated
        assert "{{Item" in result
        assert "damage=15" in result
        assert "{{Damage" in result
        assert "amount=15" in result
        assert "{{Category|Weapons}}" in result


class TestTemplateParserErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_wikitext_handling(self) -> None:
        """Test handling of invalid wikitext (should not raise for most cases)."""
        parser = TemplateParser()
        # mwparserfromhell is very forgiving, but test it anyway
        code = parser.parse("{{Item|name=Sword")  # Missing closing braces
        assert code is not None

    def test_empty_template_name(self) -> None:
        """Test finding template with empty name."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword}}")
        templates = parser.find_templates(code, [""])
        assert len(templates) == 0

    def test_special_characters_in_params(self) -> None:
        """Test parameters with special characters."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name=Sword of the [[Dragon]]|damage=10}}")
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)
        assert "Sword of the [[Dragon]]" in params["name"]

    def test_nested_templates(self) -> None:
        """Test handling nested templates."""
        parser = TemplateParser()
        code = parser.parse("{{Item|name={{LocalizedString|Sword}}|damage=10}}")
        item_templates = parser.find_templates(code, ["Item"])
        assert len(item_templates) == 1

        # Can also find nested template
        all_templates = parser.find_templates(code, ["Item", "LocalizedString"])
        assert len(all_templates) == 2
