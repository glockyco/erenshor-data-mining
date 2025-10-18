"""Unit tests for field preservation system."""

import pytest

from erenshor.application.generators.field_preservation import (
    DEFAULT_PRESERVATION_RULES,
    FieldPreservationConfig,
    FieldPreservationHandler,
    HandlerNotFoundError,
    override_handler,
    prefer_manual_handler,
    preserve_handler,
)


class TestBuiltInHandlers:
    """Tests for built-in handler functions."""

    def test_override_handler_always_uses_new_value(self) -> None:
        """override_handler should always return new value."""
        result = override_handler("old", "new", {})
        assert result == "new"

        result = override_handler("", "new", {})
        assert result == "new"

        result = override_handler("old", "", {})
        assert result == ""

    def test_preserve_handler_always_uses_old_value(self) -> None:
        """preserve_handler should always return old value."""
        result = preserve_handler("old", "new", {})
        assert result == "old"

        result = preserve_handler("", "new", {})
        assert result == ""

        result = preserve_handler("old", "", {})
        assert result == "old"

    def test_prefer_manual_handler_prefers_non_empty_old(self) -> None:
        """prefer_manual_handler should return old if non-empty, else new."""
        # Old is non-empty -> use old
        result = prefer_manual_handler("old", "new", {})
        assert result == "old"

        # Old is empty -> use new
        result = prefer_manual_handler("", "new", {})
        assert result == "new"

        # Old is whitespace -> use new
        result = prefer_manual_handler("   ", "new", {})
        assert result == "new"

        # Both empty -> use new
        result = prefer_manual_handler("", "", {})
        assert result == ""


class TestFieldPreservationConfig:
    """Tests for FieldPreservationConfig."""

    def test_init_with_default_rules(self) -> None:
        """Config should initialize with default rules."""
        config = FieldPreservationConfig()

        # Check Item template has expected rules
        item_rules = config.get_template_rules("Item")
        assert item_rules["description"] == "preserve"
        assert item_rules["vendorsource"] == "preserve"

    def test_init_with_custom_rules(self) -> None:
        """Config should accept custom rules."""
        custom_rules = {
            "TestTemplate": {
                "field1": "preserve",
                "field2": "override",
            }
        }
        config = FieldPreservationConfig(rules=custom_rules)

        assert config.get_rule("TestTemplate", "field1") == "preserve"
        assert config.get_rule("TestTemplate", "field2") == "override"

    def test_get_rule_defaults_to_override(self) -> None:
        """get_rule should return 'override' for fields without explicit rules."""
        config = FieldPreservationConfig()

        # Field not in rules
        assert config.get_rule("Item", "nonexistent_field") == "override"

        # Template not in rules
        assert config.get_rule("UnknownTemplate", "field") == "override"

    def test_get_rule_returns_explicit_rule(self) -> None:
        """get_rule should return explicit rule when configured."""
        config = FieldPreservationConfig()

        assert config.get_rule("Item", "description") == "preserve"
        assert config.get_rule("Item", "image") == "prefer_manual"

    def test_get_handler_returns_built_in_handlers(self) -> None:
        """get_handler should return built-in handlers."""
        config = FieldPreservationConfig()

        assert config.get_handler("override") == override_handler
        assert config.get_handler("preserve") == preserve_handler
        assert config.get_handler("prefer_manual") == prefer_manual_handler

    def test_get_handler_raises_on_unknown_handler(self) -> None:
        """get_handler should raise HandlerNotFoundError for unknown handlers."""
        config = FieldPreservationConfig()

        with pytest.raises(HandlerNotFoundError, match="Handler not found: unknown"):
            config.get_handler("unknown")

    def test_register_custom_handler(self) -> None:
        """register_handler should allow custom handlers."""
        config = FieldPreservationConfig()

        def custom_handler(old: str, new: str, ctx: dict) -> str:
            return f"{old}+{new}"

        config.register_handler("concat", custom_handler)

        handler = config.get_handler("concat")
        assert handler("a", "b", {}) == "a+b"

    def test_add_rule_creates_template_entry(self) -> None:
        """add_rule should create template entry if it doesn't exist."""
        config = FieldPreservationConfig(rules={})

        config.add_rule("NewTemplate", "field1", "preserve")

        assert config.get_rule("NewTemplate", "field1") == "preserve"

    def test_add_rule_validates_handler_exists(self) -> None:
        """add_rule should validate that handler is registered."""
        config = FieldPreservationConfig()

        with pytest.raises(HandlerNotFoundError):
            config.add_rule("Template", "field", "nonexistent_handler")

    def test_get_template_rules_returns_copy(self) -> None:
        """get_template_rules should return a copy of rules dict."""
        config = FieldPreservationConfig()

        rules = config.get_template_rules("Item")
        rules["new_field"] = "preserve"

        # Original should be unchanged
        assert "new_field" not in config.get_template_rules("Item")


class TestFieldPreservationHandler:
    """Tests for FieldPreservationHandler."""

    def test_apply_preservation_with_override(self) -> None:
        """apply_preservation should override fields when rule is 'override'."""
        config = FieldPreservationConfig(
            rules={
                "TestTemplate": {
                    "field1": "override",
                }
            }
        )
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "old_value"}
        new_fields = {"field1": "new_value"}

        result = handler.apply_preservation("TestTemplate", old_fields, new_fields)

        assert result["field1"] == "new_value"

    def test_apply_preservation_with_preserve(self) -> None:
        """apply_preservation should preserve fields when rule is 'preserve'."""
        config = FieldPreservationConfig(
            rules={
                "TestTemplate": {
                    "field1": "preserve",
                }
            }
        )
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "old_value"}
        new_fields = {"field1": "new_value"}

        result = handler.apply_preservation("TestTemplate", old_fields, new_fields)

        assert result["field1"] == "old_value"

    def test_apply_preservation_with_prefer_manual(self) -> None:
        """apply_preservation should prefer manual when old is non-empty."""
        config = FieldPreservationConfig(
            rules={
                "TestTemplate": {
                    "field1": "prefer_manual",
                    "field2": "prefer_manual",
                }
            }
        )
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "manual_value", "field2": ""}
        new_fields = {"field1": "db_value", "field2": "db_value"}

        result = handler.apply_preservation("TestTemplate", old_fields, new_fields)

        assert result["field1"] == "manual_value"  # Old was non-empty
        assert result["field2"] == "db_value"  # Old was empty

    def test_apply_preservation_handles_new_fields(self) -> None:
        """apply_preservation should add new fields from database."""
        config = FieldPreservationConfig(rules={"TestTemplate": {}})
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "old"}
        new_fields = {"field1": "new", "field2": "added"}

        result = handler.apply_preservation("TestTemplate", old_fields, new_fields)

        assert result["field1"] == "new"  # Default override
        assert result["field2"] == "added"  # New field added

    def test_apply_preservation_handles_removed_fields(self) -> None:
        """apply_preservation should handle fields that no longer exist in new.

        Fields removed from new template will have empty values (not present means empty).
        Whether they appear in result depends on the preservation rule.
        """
        config = FieldPreservationConfig(
            rules={
                "TestTemplate": {
                    "field1": "preserve",
                    "field2": "preserve",  # Preserve even if new is empty
                }
            }
        )
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "old", "field2": "removed"}
        new_fields = {"field1": "new"}

        result = handler.apply_preservation("TestTemplate", old_fields, new_fields)

        assert result["field1"] == "old"  # Preserved
        # field2 preserved because rule is "preserve" (keeps old even if new is empty)
        assert result["field2"] == "removed"

    def test_apply_preservation_passes_context_to_handlers(self) -> None:
        """apply_preservation should pass context dict to handlers."""
        context_received = {}

        def capturing_handler(old: str, new: str, ctx: dict) -> str:
            context_received.update(ctx)
            return new

        config = FieldPreservationConfig(
            rules={"TestTemplate": {"field1": "custom"}}, handlers={"custom": capturing_handler}
        )
        handler = FieldPreservationHandler(config)

        old_fields = {"field1": "old"}
        new_fields = {"field1": "new"}
        context = {"extra": "data"}

        handler.apply_preservation("TestTemplate", old_fields, new_fields, context)

        assert context_received["template_name"] == "TestTemplate"
        assert context_received["extra"] == "data"

    def test_apply_preservation_with_default_rules(self) -> None:
        """apply_preservation should work with default Item rules."""
        handler = FieldPreservationHandler()  # Uses default rules

        old_fields = {
            "description": "Manual lore text",
            "image": "Custom.png",
            "vendorsource": "[[Blacksmith]]",
            "damage": "10",
        }
        new_fields = {
            "description": "Default description",
            "image": "",
            "vendorsource": "Database vendor",
            "damage": "15",
        }

        result = handler.apply_preservation("Item", old_fields, new_fields)

        # These should be preserved
        assert result["description"] == "Manual lore text"
        assert result["vendorsource"] == "[[Blacksmith]]"

        # Image uses prefer_manual -> keeps old if non-empty
        assert result["image"] == "Custom.png"

        # Damage has no rule -> uses override (default)
        assert result["damage"] == "15"

    def test_merge_templates_with_single_template(self) -> None:
        """merge_templates should merge a single template's fields."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|description=Manual text|damage=10}}"
        new_wikitext = "{{Item|description=Default|damage=15|level=5}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Parse result to check fields
        from erenshor.infrastructure.wiki.template_parser import TemplateParser

        parser = TemplateParser()
        code = parser.parse(result)
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)

        # Description preserved (preserve rule)
        assert params["description"] == "Manual text"
        # Damage updated (override rule)
        assert params["damage"] == "15"
        # Level added (new field)
        assert params["level"] == "5"

    def test_merge_templates_with_no_old_templates(self) -> None:
        """merge_templates should return new wikitext when no old templates found."""
        handler = FieldPreservationHandler()

        old_wikitext = "Some text without templates"
        new_wikitext = "{{Item|name=Sword|damage=10}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should return new wikitext unchanged
        assert result == new_wikitext

    def test_merge_templates_with_no_new_templates(self) -> None:
        """merge_templates should return new wikitext when no new templates found."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|name=Sword|damage=10}}"
        new_wikitext = "Some text without templates"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should return new wikitext unchanged
        assert result == new_wikitext

    def test_merge_templates_preserves_non_template_content(self) -> None:
        """merge_templates should preserve non-template content."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|description=Old}}\nSome wiki text"
        new_wikitext = "{{Item|description=New}}\nNew wiki text"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should have new non-template content
        assert "New wiki text" in result
        # But old description preserved
        assert "description=Old" in result or "description = Old" in result

    def test_merge_templates_with_multiple_template_types(self) -> None:
        """merge_templates should handle multiple template types."""
        config = FieldPreservationConfig(
            rules={
                "Item": {"description": "preserve"},
                "Fancy-weapon": {"damage": "preserve"},
            }
        )
        handler = FieldPreservationHandler(config)

        old_wikitext = "{{Item|description=Old item}}\n{{Fancy-weapon|damage=10}}"
        new_wikitext = "{{Item|description=New item}}\n{{Fancy-weapon|damage=15}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item", "Fancy-weapon"])

        # Both templates should have preserved fields
        assert "description=Old item" in result or "description = Old item" in result
        assert "damage=10" in result or "damage = 10" in result

    def test_get_config_returns_config_instance(self) -> None:
        """get_config should return the config instance."""
        config = FieldPreservationConfig()
        handler = FieldPreservationHandler(config)

        assert handler.get_config() is config


class TestDefaultRules:
    """Tests for DEFAULT_PRESERVATION_RULES."""

    def test_item_template_has_description_preserve(self) -> None:
        """Item template should preserve description field."""
        assert DEFAULT_PRESERVATION_RULES["Item"]["description"] == "preserve"

    def test_item_template_has_source_fields_preserve(self) -> None:
        """Item template should preserve all source fields."""
        item_rules = DEFAULT_PRESERVATION_RULES["Item"]
        assert item_rules["vendorsource"] == "preserve"
        assert item_rules["source"] == "preserve"
        assert item_rules["othersource"] == "preserve"
        assert item_rules["questsource"] == "preserve"
        assert item_rules["relatedquest"] == "preserve"
        assert item_rules["craftsource"] == "preserve"
        assert item_rules["componentfor"] == "preserve"

    def test_fancy_weapon_has_description_preserve(self) -> None:
        """Fancy-weapon template should preserve description field."""
        assert DEFAULT_PRESERVATION_RULES["Fancy-weapon"]["description"] == "preserve"

    def test_fancy_armor_has_description_preserve(self) -> None:
        """Fancy-armor template should preserve description field."""
        assert DEFAULT_PRESERVATION_RULES["Fancy-armor"]["description"] == "preserve"

    def test_all_templates_have_valid_handler_names(self) -> None:
        """All rules should reference valid handler names."""
        valid_handlers = {"override", "preserve", "prefer_manual"}

        for template_name, field_rules in DEFAULT_PRESERVATION_RULES.items():
            for field_name, handler_name in field_rules.items():
                assert (
                    handler_name in valid_handlers
                ), f"Invalid handler '{handler_name}' for {template_name}.{field_name}"


class TestIntegrationScenarios:
    """Integration tests for realistic use cases."""

    def test_item_page_regeneration_preserves_manual_content(self) -> None:
        """Full scenario: Regenerating item page preserves manual edits."""
        handler = FieldPreservationHandler()

        # Original wiki page with manual content
        old_wikitext = """{{Item
|image=[[File:Sword.png]]
|description=This is a legendary sword forged by ancient smiths.
|vendorsource=[[Blacksmith]] in [[Newhaven City]]
|damage=10
|level=5
}}

[[Category:Items]]
[[Category:Weapons]]"""

        # Fresh page generated from database
        new_wikitext = """{{Item
|image=
|description=A basic sword.
|vendorsource=
|damage=15
|level=5
}}

[[Category:Items]]
[[Category:Weapons]]"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Manual content should be preserved
        assert "legendary sword forged by ancient smiths" in result
        assert "[[Blacksmith]] in [[Newhaven City]]" in result

        # Database updates should apply
        assert "damage=15" in result or "damage = 15" in result

        # Categories should remain (not in template)
        assert "[[Category:Items]]" in result

    def test_weapon_with_fancy_template_preservation(self) -> None:
        """Full scenario: Weapon page with Fancy-weapon template."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Item
|description=A fine weapon
|damage=10
}}

{{Fancy-weapon
|name=Legendary Sword
|description=Deals holy damage
|damage=10
|tier=0
}}"""

        new_wikitext = """{{Item
|description=Default weapon
|damage=15
}}

{{Fancy-weapon
|name=
|description=Generic weapon
|damage=15
|tier=0
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item", "Fancy-weapon"])

        # Item description preserved
        assert "A fine weapon" in result
        # Fancy-weapon description preserved
        assert "Deals holy damage" in result
        # Fancy-weapon name preferred (was non-empty)
        assert "Legendary Sword" in result
        # Damage updated to 15 in both templates
        assert result.count("15") == 2
