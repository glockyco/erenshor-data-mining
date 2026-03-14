"""Unit tests for field preservation system."""

import pytest

from erenshor.application.wiki.generators.field_preservation import (
    DEFAULT_PRESERVATION_RULES,
    FieldPreservationConfig,
    FieldPreservationHandler,
    HandlerNotFoundError,
    merge_handler,
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

    def test_merge_handler_combines_values(self) -> None:
        """merge_handler should combine old and new values."""
        # <br>-separated lists - combine with <br>
        result = merge_handler("Quest1<br>Quest2", "Quest3<br>Quest4", {})
        assert result == "Quest1<br>Quest2<br>Quest3<br>Quest4"

        # <br>-separated lists - deduplicates
        result = merge_handler("Quest1<br>Quest2", "Quest2<br>Quest3", {})
        assert result == "Quest1<br>Quest2<br>Quest3"

        # Neither has separator - use <br> to combine (old first, then new)
        result = merge_handler("{{QuestLink|Whispers of Wyland}}", "{{QuestLink|A Retired Locksmith}}", {})
        assert result == "{{QuestLink|Whispers of Wyland}}<br>{{QuestLink|A Retired Locksmith}}"

        # Mixed separators - old has no separator, new has <br> - should use <br> for result
        result = merge_handler("Quest1", "Quest2<br>Quest3", {})
        assert result == "Quest1<br>Quest2<br>Quest3"

        # Comma-separated lists (like type field) - both have commas, use comma
        result = merge_handler("[[Quest Items|Quest Item]], Other", "[[Consumables|Consumable]], Another", {})
        assert result == "[[Quest Items|Quest Item]], Other, [[Consumables|Consumable]], Another"

        # Comma-separated lists - deduplicates
        result = merge_handler("Type1, Type2", "Type2, Type3", {})
        assert result == "Type1, Type2, Type3"

        # Old empty -> use new
        result = merge_handler("", "new", {})
        assert result == "new"

        # New empty -> use old
        result = merge_handler("old", "", {})
        assert result == "old"

        # Non-list fields (no comma or <br>) - combine with <br>
        result = merge_handler("Value1", "Value2", {})
        assert result == "Value1<br>Value2"

        # QuestLink with comma in display name - should use <br> separator (not split on internal comma)
        result = merge_handler(
            "{{QuestLink|link=The Mathers' Demise{{!}}The Mather's Demise, Part 3}}",
            "{{QuestLink|link=The Mathers' Demise{{!}}The Mather's Demise}}",
            {},
        )
        expected = (
            "{{QuestLink|link=The Mathers' Demise{{!}}The Mather's Demise, Part 3}}"
            "<br>{{QuestLink|link=The Mathers' Demise{{!}}The Mather's Demise}}"
        )
        assert result == expected
        # Ensure it didn't break the QuestLink template by splitting on the comma
        assert "}}, {{" not in result  # Should not have broken the template


class TestFieldPreservationConfig:
    """Tests for FieldPreservationConfig."""

    def test_init_with_default_rules(self) -> None:
        """Config should initialize with default rules."""
        config = FieldPreservationConfig()

        # Check Item template has expected rules
        item_rules = config.get_template_rules("Item")
        assert item_rules["image"] == "prefer_manual"
        assert item_rules["othersource"] == "preserve"
        assert item_rules["type"] == "merge"
        assert item_rules["questsource"] == "merge"
        assert item_rules["relatedquest"] == "merge"

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

        assert config.get_rule("Item", "image") == "prefer_manual"
        assert config.get_rule("Item", "othersource") == "preserve"
        assert config.get_rule("Item", "type") == "merge"

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
            "image": "Custom.png",
            "imagecaption": "Old caption",
            "othersource": "Manual source",
            "type": "[[Quest Items|Quest Item]]",
            "questsource": "{{QuestLink|Old Quest}}",
            "damage": "10",
        }
        new_fields = {
            "image": "",
            "imagecaption": "",
            "othersource": "",
            "type": "[[Consumables|Consumable]]",
            "questsource": "{{QuestLink|New Quest}}",
            "damage": "15",
        }

        result = handler.apply_preservation("Item", old_fields, new_fields)

        # Image uses prefer_manual -> keeps old if non-empty
        assert result["image"] == "Custom.png"
        assert result["imagecaption"] == "Old caption"

        # Othersource uses preserve -> always keeps old
        assert result["othersource"] == "Manual source"

        # Type and questsource use merge -> combines old and new
        assert "Quest Item" in result["type"]
        assert "Consumable" in result["type"]
        assert "Old Quest" in result["questsource"]
        assert "New Quest" in result["questsource"]

        # Damage has no rule -> uses override (default)
        assert result["damage"] == "15"

    def test_merge_templates_with_single_template(self) -> None:
        """merge_templates should merge a single template's fields."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|image=Custom.png|othersource=Manual|damage=10}}"
        new_wikitext = "{{Item|image=|othersource=|damage=15|level=5}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Parse result to check fields
        from erenshor.infrastructure.wiki.template_parser import TemplateParser

        parser = TemplateParser()
        code = parser.parse(result)
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)

        # Image preserved (prefer_manual rule - old is non-empty)
        assert params["image"] == "Custom.png"
        # Othersource preserved (preserve rule)
        assert params["othersource"] == "Manual"
        # Damage updated (override rule)
        assert params["damage"] == "15"
        # Level added (new field)
        assert params["level"] == "5"

    def test_merge_templates_with_no_old_templates(self) -> None:
        """merge_templates should append new template when no old template found."""
        handler = FieldPreservationHandler()

        old_wikitext = "Some manual text without templates"
        new_wikitext = "{{Item|name=Sword|damage=10}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should append new template to old wikitext (preserving manual text)
        assert "Some manual text without templates" in result
        assert "{{Item" in result
        assert "name=Sword" in result or "name = Sword" in result

    def test_merge_templates_with_no_new_templates(self) -> None:
        """merge_templates should return old wikitext when no new templates found."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|name=Sword|damage=10}}\nManual content"
        new_wikitext = "Some text without templates"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should return old wikitext unchanged (preserving everything)
        assert result == old_wikitext

    def test_merge_templates_preserves_non_template_content(self) -> None:
        """merge_templates should preserve non-template content from old page."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|othersource=Old}}\n\nSome manual wiki text\n\n[[Category:Items]]"
        new_wikitext = "{{Item|othersource=New}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Should preserve manual content from old page
        assert "Some manual wiki text" in result
        assert "[[Category:Items]]" in result
        # But old othersource preserved (preserve rule)
        assert "othersource=Old" in result or "othersource = Old" in result

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

    def test_item_template_has_manual_content_rules(self) -> None:
        """Item template should have prefer_manual for images."""
        item_rules = DEFAULT_PRESERVATION_RULES["Item"]
        assert item_rules["image"] == "prefer_manual"
        assert item_rules["imagecaption"] == "prefer_manual"

    def test_item_template_has_merge_rules(self) -> None:
        """Item template should merge quest-related fields."""
        item_rules = DEFAULT_PRESERVATION_RULES["Item"]
        assert item_rules["type"] == "merge"
        assert item_rules["questsource"] == "merge"
        assert item_rules["relatedquest"] == "merge"

    def test_item_template_preserves_othersource(self) -> None:
        """Item template should preserve othersource field."""
        assert DEFAULT_PRESERVATION_RULES["Item"]["othersource"] == "preserve"

    def test_fancy_weapon_has_no_preservation_rules(self) -> None:
        """Fancy-weapon template should have no preservation rules (all override)."""
        assert DEFAULT_PRESERVATION_RULES["Fancy-weapon"] == {}

    def test_fancy_armor_has_no_preservation_rules(self) -> None:
        """Fancy-armor template should have no preservation rules (all override)."""
        assert DEFAULT_PRESERVATION_RULES["Fancy-armor"] == {}

    def test_fancy_charm_has_no_preservation_rules(self) -> None:
        """Fancy-charm template should have no preservation rules (all override)."""
        assert DEFAULT_PRESERVATION_RULES["Fancy-charm"] == {}

    def test_all_templates_have_valid_handler_names(self) -> None:
        """All rules should reference valid handler names."""
        valid_handlers = {"override", "preserve", "prefer_manual", "prefer_database", "merge"}

        for template_name, field_rules in DEFAULT_PRESERVATION_RULES.items():
            for field_name, handler_name in field_rules.items():
                assert handler_name in valid_handlers, (
                    f"Invalid handler '{handler_name}' for {template_name}.{field_name}"
                )


class TestIntegrationScenarios:
    """Integration tests for realistic use cases."""

    def test_item_page_regeneration_preserves_manual_content(self) -> None:
        """Full scenario: Regenerating item page preserves manual edits."""
        handler = FieldPreservationHandler()

        # Original wiki page with manual content
        old_wikitext = """{{Item
|image=[[File:Sword.png]]
|imagecaption=Custom image caption
|othersource=Found in treasure chest
|type=[[Quest Items|Quest Item]]
|questsource={{QuestLink|Manual Quest}}
|damage=10
|level=5
}}

[[Category:Items]]
[[Category:Weapons]]"""

        # Fresh page generated from database
        new_wikitext = """{{Item
|image=
|imagecaption=
|othersource=
|type=[[Consumables|Consumable]]
|questsource={{QuestLink|Database Quest}}
|damage=15
|level=5
}}

[[Category:Items]]
[[Category:Weapons]]"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"])

        # Manual content should be preserved (prefer_manual)
        assert "[[File:Sword.png]]" in result
        assert "Custom image caption" in result

        # Othersource should be preserved
        assert "Found in treasure chest" in result

        # Type and questsource should be merged
        assert "Quest Item" in result
        assert "Consumable" in result
        assert "Manual Quest" in result
        assert "Database Quest" in result

        # Database updates should apply (override)
        assert "damage=15" in result or "damage = 15" in result

        # Categories should remain (not in template)
        assert "[[Category:Items]]" in result

    def test_weapon_with_fancy_template_preservation(self) -> None:
        """Full scenario: Weapon page with Fancy-weapon template."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Item
|image=[[File:OldWeapon.png]]
|othersource=Manual source
|damage=10
}}

{{Fancy-weapon
|name=Legendary Sword
|description=Deals holy damage
|damage=10
|tier=0
}}"""

        new_wikitext = """{{Item
|image=
|othersource=
|damage=15
}}

{{Fancy-weapon
|name=
|description=Generic weapon
|damage=15
|tier=0
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item", "Fancy-weapon"])

        # Item image preserved (prefer_manual)
        assert "[[File:OldWeapon.png]]" in result
        # Item othersource preserved
        assert "Manual source" in result
        # Fancy-weapon description OVERRIDDEN (no preservation)
        assert "Generic weapon" in result
        assert "Deals holy damage" not in result
        # Fancy-weapon name OVERRIDDEN (no preservation)
        assert "Legendary Sword" not in result
        # Damage updated to 15 in both templates
        assert result.count("15") == 2


class TestTemplateFormatting:
    """Tests for template formatting preservation (multiline, field order)."""

    def test_merge_templates_preserves_multiline_formatting(self) -> None:
        """merge_templates should preserve multiline template formatting."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Enemy
|name=Test NPC
|type=NPC
|level=5
|health=100
}}"""

        new_wikitext = """{{Enemy
|name=Test NPC
|image=[[File:Test.png|thumb]]
|imagecaption=
|type=
|faction=Villager
|factionChange=
|zones=
|coordinates=
|spawnchance=
|respawn=
|guaranteeddrops=
|droprates=
|level=10
|experience=50-100
|health=200
|mana=50
|ac=5
|strength=10
|endurance=8
|dexterity=9
|agility=7
|intelligence=6
|wisdom=5
|charisma=4
|magic=0
|poison=0
|elemental=0
|void=0
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Enemy"])

        # Should have newlines between fields (not compacted to single line)
        assert "\n|name=" in result
        assert "\n|level=" in result
        assert "\n|health=" in result
        assert "\n|type=" in result

        # Should not be single-line format
        assert "|name=Test NPC|image=" not in result
        assert "|level=10|experience=" not in result

    def test_merge_templates_preserves_field_order(self) -> None:
        """merge_templates should preserve field order from new template."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Enemy
|name=Test
|type=NPC
|zones=Forest
|level=5
}}"""

        new_wikitext = """{{Enemy
|name=Test
|image=[[File:Test.png|thumb]]
|imagecaption=
|type=
|faction=Villager
|factionChange=
|zones=
|coordinates=
|level=10
|health=200
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Enemy"])

        # Extract field order from result
        lines = [line for line in result.split("\n") if line.startswith("|")]
        field_names = [line.split("=")[0].strip("|") for line in lines]

        # Field order should match new template, not old template
        expected_order = [
            "name",
            "image",
            "imagecaption",
            "type",
            "faction",
            "factionChange",
            "zones",
            "coordinates",
            "level",
            "health",
        ]
        assert field_names == expected_order

    def test_merge_templates_with_character_template_preserves_manual_fields(self) -> None:
        """merge_templates should preserve Character template manual edit fields only."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Character
|name=Goblin Scout
|type=[[:Category:Characters|Enemy]]
|imagecaption=A fearsome goblin
|zones=[[Rottenfoot]]
|coordinates=100.0 x 20.0 x 200.0
|droprates=Manual loot table
|level=5
|health=100
}}"""

        new_wikitext = """{{Character
|name=Goblin Scout
|image=[[File:Goblin Scout.png|thumb]]
|imagecaption=
|type=
|faction=Bandit
|factionChange=+5 [[Bandits]]
|zones=[[Darkwood Forest]]
|coordinates=150.0 x 30.0 x 250.0
|spawnchance=75%
|respawn=10m
|guaranteeddrops={{ItemLink|Goblin Tooth}}
|droprates={{ItemLink|Rusty Dagger}} (50%)
|level=10
|experience=50-100
|health=200
|mana=50
|ac=5
|strength=10
|endurance=8
|dexterity=9
|agility=7
|intelligence=6
|wisdom=5
|charisma=4
|magic=0
|poison=0
|elemental=0
|void=0
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Character"])

        # Manual edit fields should be preserved
        assert "A fearsome goblin" in result  # imagecaption (preserve)
        assert "[[:Category:Characters|Enemy]]" in result  # type (prefer_manual - had value)

        # Database-generated fields should be UPDATED from new wikitext
        assert "[[Darkwood Forest]]" in result  # zones (from DB, not old manual value)
        assert "150.0 x 30.0 x 250.0" in result  # coordinates (from DB)
        assert "{{ItemLink|Rusty Dagger}} (50%)" in result  # droprates (from DB)
        assert "+5 [[Bandits]]" in result  # factionChange (from DB)
        assert "75%" in result  # spawnchance (from DB)
        assert "10m" in result  # respawn (from DB)
        assert "{{ItemLink|Goblin Tooth}}" in result  # guaranteeddrops (from DB)

        # Should NOT have old manual values
        assert "[[Rottenfoot]]" not in result  # old zones
        assert "100.0 x 20.0 x 200.0" not in result  # old coordinates
        assert "Manual loot table" not in result  # old droprates

        # Stats should be updated
        assert "level=10" in result or "|level=10\n" in result
        assert "health=200" in result or "|health=200\n" in result
        assert "experience=50-100" in result or "|experience=50-100\n" in result
        assert "faction=Bandit" in result or "|faction=Bandit\n" in result
