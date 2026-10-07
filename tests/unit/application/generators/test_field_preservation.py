"""Unit tests for field preservation system."""

import pytest

from erenshor.application.wiki.generators.field_preservation import (
    DEFAULT_PRESERVATION_RULES,
    AmbiguousRootsError,
    FieldPreservationConfig,
    FieldPreservationHandler,
    HandlerNotFoundError,
    LinkListMerge,
    override_handler,
    prefer_manual_handler,
    preserve_handler,
)
from erenshor.application.wiki_deploy.link_audit import LinkTargets
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry


def _quest(key: str, name: str, page: str) -> LinkCatalogEntry:
    return LinkCatalogEntry(key=key, kind="quest", subtype=None, name=name, page=page, image=None)


@pytest.mark.parametrize(
    ("template_name", "picture_fields"),
    [
        ("Item", {"icon": "Subject icon.png"}),
        ("Ability", {"icon": "Subject icon.png"}),
        ("Stance", {"icon": "Subject icon.png"}),
        ("Character", {"render": "Subject render.png", "screenshot": "Subject screenshot.png"}),
    ],
)
def test_regeneration_drops_retired_picture_parameters(template_name: str, picture_fields: dict[str, str]) -> None:
    old = (
        f"{{{{{template_name}|stablekey=entity:subject"
        "|image=[[File:Editors old picture.png|thumb]]|imagefile=Editors old picture.png"
        "|imagecaption=Editor caption}}"
    )
    new_params = "|".join(f"{field}={value}" for field, value in picture_fields.items())
    new = f"{{{{{template_name}|stablekey=entity:subject|{new_params}|imagecaption=}}}}"

    text = FieldPreservationHandler().merge_templates(old, new, [template_name]).text

    assert "|image=" not in text
    assert "|imagefile=" not in text
    for field, value in picture_fields.items():
        assert f"|{field}={value}\n" in text
    if template_name in {"Character", "Stance"}:
        assert "|imagecaption=Editor caption\n" in text
    assert not ({"image", "imagefile"} & DEFAULT_PRESERVATION_RULES[template_name].keys())


QUESTS = (
    _quest("quest:faerie dust for nylith valarro", "Faerie Dust for Nylith Valorro", "Faerie Dust for Nylith Valorro"),
    _quest("quest:therevivalritual", "The Revival Plains Ritual", "The Revival Plains Ritual"),
    _quest("quest:ripperquestline1", "Ripper's Questline (1)", "Ripper's Questline"),
    _quest("quest:ripperquestline2", "Ripper's Questline (2)", "Ripper's Questline"),
)
DUST = "{{QuestLink|stablekey=quest:faerie dust for nylith valarro}}"
RITUAL = "{{QuestLink|stablekey=quest:therevivalritual}}"


def _merge(field: str, old: str, new: str) -> str:
    return LinkListMerge(LinkTargets(QUESTS))(old, new, {"field_name": field})


def _linked_handler() -> FieldPreservationHandler:
    return FieldPreservationHandler(FieldPreservationConfig(link_targets=LinkTargets(QUESTS)))


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


class TestLinkListMerge:
    """A merged list field links each page once."""

    def test_editor_and_generated_links_to_one_quest_keep_the_generated_form(self) -> None:
        old = "{{QuestLink|Faerie Dust for Nylith Valorro}}<br>{{QuestLink|The Revival Plains Ritual}}"
        new = f"{DUST}<br>{RITUAL}"

        assert _merge("relatedquest", old, new) == new

    def test_editor_links_and_text_without_a_generated_page_stay_in_live_order(self) -> None:
        old = "Mentioned in a book<br>{{QuestLink|Editor Quest}}<br>{{QuestLink|The Revival Plains Ritual}}"

        assert _merge("relatedquest", old, f"{RITUAL}<br>{DUST}") == (
            f"Mentioned in a book<br>{{{{QuestLink|Editor Quest}}}}<br>{RITUAL}<br>{DUST}"
        )

    def test_link_parameter_and_wikilink_forms_match_their_page(self) -> None:
        old = (
            "{{QuestLink|link=The Revival Plains Ritual{{!}}Revival ritual}}<br>[[Faerie Dust for Nylith Valorro|Dust]]"
        )

        assert _merge("questsource", old, f"{DUST}<br>{RITUAL}") == f"{RITUAL}<br>{DUST}"

    def test_deprecated_questlink_parameter_matches_its_page(self) -> None:
        old = "{{QuestLink |questlink=The Revival Plains Ritual}}"

        assert _merge("relatedquest", old, RITUAL) == RITUAL

    def test_link_to_a_page_of_several_quests_takes_the_generated_quest(self) -> None:
        new = "{{QuestLink|stablekey=quest:ripperquestline2}}"

        assert _merge("relatedquest", "{{QuestLink|Ripper's Questline}}", new) == new

    def test_comma_inside_a_link_label_does_not_split_the_entry(self) -> None:
        old = "{{QuestLink|link=The Mathers' Demise{{!}}The Mather's Demise, Part 3}}"

        assert _merge("relatedquest", old, RITUAL) == f"{old}<br>{RITUAL}"

    def test_type_entries_merge_across_separators_into_one_comma_list(self) -> None:
        old = "[[Quest Items|Quest Item]]<br>[[Crafting]]<br>[[Quest Items|Quest Item]], [[Crafting]]"

        assert _merge("type", old, "[[Crafting]]") == "[[Quest Items|Quest Item]], [[Crafting]]"

    def test_a_section_link_is_a_different_page(self) -> None:
        old = "[[Consumables#Food|Food]], [[Consumables|Consumable]]"

        assert _merge("type", old, "[[Consumables|Consumable]]") == old

    def test_merge_rule_requires_link_targets(self) -> None:
        with pytest.raises(HandlerNotFoundError, match="link targets"):
            FieldPreservationHandler().apply_preservation("Item", {"type": "A"}, {"type": "B"})


class TestFieldPreservationConfig:
    """Tests for FieldPreservationConfig."""

    def test_init_with_default_rules(self) -> None:
        """Config should initialize with default rules."""
        config = FieldPreservationConfig()

        # Check Item template has expected rules
        item_rules = config.get_template_rules("Item")
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
        handler = _linked_handler()

        old_fields = {
            "othersource": "Manual source",
            "type": "[[Quest Items|Quest Item]]",
            "questsource": "{{QuestLink|Old Quest}}",
            "damage": "10",
        }
        new_fields = {
            "othersource": "",
            "type": "[[Consumables|Consumable]]",
            "questsource": "{{QuestLink|New Quest}}",
            "damage": "15",
        }

        result = handler.apply_preservation("Item", old_fields, new_fields)

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

        old_wikitext = "{{Item|othersource=Manual|damage=10}}"
        new_wikitext = "{{Item|othersource=|damage=15|level=5}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"]).text

        # Parse result to check fields
        from erenshor.infrastructure.wiki.template_parser import TemplateParser

        parser = TemplateParser()
        code = parser.parse(result)
        template = parser.find_template(code, ["Item"])
        params = parser.get_params(template)

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

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"]).text

        # Should append new template to old wikitext (preserving manual text)
        assert "Some manual text without templates" in result
        assert "{{Item" in result
        assert "name=Sword" in result or "name = Sword" in result

    def test_merge_templates_with_no_new_templates(self) -> None:
        """merge_templates should return old wikitext when no new templates found."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|name=Sword|damage=10}}\nManual content"
        new_wikitext = "Some text without templates"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"]).text

        # Should return old wikitext unchanged (preserving everything)
        assert result == old_wikitext

    def test_merge_templates_preserves_non_template_content(self) -> None:
        """merge_templates should preserve non-template content from old page."""
        handler = FieldPreservationHandler()

        old_wikitext = "{{Item|othersource=Old}}\n\nSome manual wiki text\n\n[[Category:Items]]"
        new_wikitext = "{{Item|othersource=New}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"]).text

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
                "Character": {"level": "preserve"},
            }
        )
        handler = FieldPreservationHandler(config)

        old_wikitext = "{{Item|description=Old item}}\n{{Character|level=10}}"
        new_wikitext = "{{Item|description=New item}}\n{{Character|level=15}}"

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item", "Character"]).text

        # Both templates should have preserved fields
        assert "description=Old item" in result or "description = Old item" in result
        assert "level=10" in result or "level = 10" in result

    def test_get_config_returns_config_instance(self) -> None:
        """get_config should return the config instance."""
        config = FieldPreservationConfig()
        handler = FieldPreservationHandler(config)

        assert handler.get_config() is config


class TestDefaultRules:
    """Tests for DEFAULT_PRESERVATION_RULES."""

    def test_item_template_has_merge_rules(self) -> None:
        """Item template should merge quest-related fields."""
        item_rules = DEFAULT_PRESERVATION_RULES["Item"]
        assert item_rules["type"] == "merge"
        assert item_rules["questsource"] == "merge"
        assert item_rules["relatedquest"] == "merge"

    def test_item_template_preserves_othersource(self) -> None:
        """Item template should preserve othersource field."""
        assert DEFAULT_PRESERVATION_RULES["Item"]["othersource"] == "preserve"

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
        handler = _linked_handler()

        # Original wiki page with manual content
        old_wikitext = """{{Item
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
|othersource=
|type=[[Consumables|Consumable]]
|questsource={{QuestLink|Database Quest}}
|damage=15
|level=5
}}

[[Category:Items]]
[[Category:Weapons]]"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Item"]).text

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


class TestTemplateFormatting:
    """Tests for template formatting preservation (multiline, field order)."""

    def test_merge_templates_preserves_multiline_formatting(self) -> None:
        """merge_templates should preserve multiline template formatting."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Character
|name=Test NPC
|type=NPC
|level=5
|health=100
}}"""

        new_wikitext = """{{Character
|name=Test NPC
|render=Test render.png
|screenshot=Test screenshot.png
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

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Character"]).text

        # Should have newlines between fields (not compacted to single line)
        assert "\n|name=" in result
        assert "\n|level=" in result
        assert "\n|health=" in result
        assert "\n|type=" in result

        # Should not be single-line format
        assert "|name=Test NPC|render=" not in result
        assert "|level=10|experience=" not in result

    def test_merge_templates_preserves_field_order(self) -> None:
        """merge_templates should preserve field order from new template."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Character
|name=Test
|type=NPC
|zones=Forest
|level=5
}}"""

        new_wikitext = """{{Character
|name=Test
|render=Test render.png
|screenshot=Test screenshot.png
|imagecaption=
|type=
|faction=Villager
|factionChange=
|zones=
|coordinates=
|level=10
|health=200
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Character"]).text

        # Extract field order from result
        lines = [line for line in result.split("\n") if line.startswith("|")]
        field_names = [line.split("=")[0].strip("|") for line in lines]

        # Field order should match new template, not old template
        expected_order = [
            "name",
            "render",
            "screenshot",
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
|render=Goblin Scout render.png
|screenshot=Goblin Scout screenshot.png
|imagecaption=
|type=Elite
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

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Character"]).text

        # Manual edit fields should be preserved
        assert "A fearsome goblin" in result  # imagecaption (preserve)
        assert "|type=Elite\n" in result  # generated classification replaces stale type

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
        assert "[[:Category:Characters|Enemy]]" not in result
        assert "100.0 x 20.0 x 200.0" not in result  # old coordinates
        assert "Manual loot table" not in result  # old droprates

        # Stats should be updated
        assert "level=10" in result or "|level=10\n" in result
        assert "health=200" in result or "|health=200\n" in result
        assert "experience=50-100" in result or "|experience=50-100\n" in result
        assert "faction=Bandit" in result or "|faction=Bandit\n" in result

    def test_merge_templates_keeps_editor_location_against_empty_generated_value(self) -> None:
        """The export never sources location, so the editor's description must survive."""
        handler = FieldPreservationHandler()

        old_wikitext = """{{Character
|name=Hadden Passican
|coordinates=367.4 x 41.1 x 537.6
|location=A small campfire area west of the Goodsoil refugee tents
|level=22
}}"""

        new_wikitext = """{{Character
|name=Hadden Passican
|coordinates=367.4 x 41.1 x 537.6
|location=
|level=22
}}"""

        result = handler.merge_templates(old_wikitext, new_wikitext, ["Character"]).text

        assert "|location=A small campfire area west of the Goodsoil refugee tents\n" in result


def _character(name: str, key: str | None = None, **fields: str) -> str:
    parts = [f"|name={name}"]
    if key is not None:
        parts.append(f"|stablekey={key}")
    parts.extend(f"|{field}={value}" for field, value in fields.items())
    return "{{Character\n" + "\n".join(parts) + "\n}}"


class TestRootIdentity:
    """Preserved fields follow the entity, not the position of its root."""

    def test_reordered_entities_keep_their_preserved_fields(self) -> None:
        old = (
            _character("Wolf", "character:wolf", imagecaption="Grey")
            + "\n\n"
            + _character("Bear", "character:bear", imagecaption="Brown")
        )
        new = (
            _character("Bear", "character:bear", imagecaption="", level="9")
            + "\n\n"
            + _character("Wolf", "character:wolf", imagecaption="", level="4")
        )

        merge = FieldPreservationHandler().merge_templates(old, new, ["Character"])

        assert merge.text == (
            _character("Wolf", "character:wolf", imagecaption="Grey", level="4")
            + "\n\n"
            + _character("Bear", "character:bear", imagecaption="Brown", level="9")
        )
        assert merge.kept_roots == ()

    def test_unkeyed_live_roots_match_by_name_and_take_the_key(self) -> None:
        old = _character("Bear", imagecaption="Brown") + "\n\n" + _character("Wolf", imagecaption="Grey")
        new = (
            _character("Wolf", "character:wolf", imagecaption="")
            + "\n\n"
            + _character("Bear", "character:bear", imagecaption="")
        )

        text = FieldPreservationHandler().merge_templates(old, new, ["Character"]).text

        assert text == (
            _character("Bear", "character:bear", imagecaption="Brown")
            + "\n\n"
            + _character("Wolf", "character:wolf", imagecaption="Grey")
        )

    def test_added_entity_follows_the_last_root_and_its_companion(self) -> None:
        old = (
            "{{Item\n|title=Charm A\n|stablekey=item:a\n}}\nText about A.\n{{Item/Charm|name=A}}\n\n[[Category:Charms]]"
        )
        new = (
            "{{Item\n|title=Charm A\n|stablekey=item:a\n}}\n{{Item/Charm|name=A}}\n\n"
            "{{Item\n|title=Charm B\n|stablekey=item:b\n}}\n{{Item/Charm|name=B}}"
        )

        text = FieldPreservationHandler().merge_templates(old, new, ["Item"]).text

        assert text == (
            "{{Item\n|title=Charm A\n|stablekey=item:a\n}}\nText about A.\n{{Item/Charm|name=A}}\n\n"
            "{{Item\n|title=Charm B\n|stablekey=item:b\n}}\n{{Item/Charm|name=B}}\n\n[[Category:Charms]]"
        )

    def test_live_root_without_generated_entity_stays_and_is_listed(self) -> None:
        chest = _character("Braxonian Chest", imagecaption="Opened with a key")
        old = "{{Item\n|title=Frost\n}}\n{{Item/General|name=Frost}}\n\n" + chest + "\n\nEditor notes."
        new = "{{Item\n|title=Frost\n|stablekey=item:frost\n}}\n{{Item/General|name=Frost}}"

        merge = FieldPreservationHandler().merge_templates(old, new, ["Item", "Character"])

        assert chest in merge.text
        assert "Editor notes." in merge.text
        assert "|stablekey=item:frost" in merge.text
        assert merge.kept_roots == ("Character: Braxonian Chest",)

    def test_same_name_roots_with_different_preserved_values_fail_the_page(self) -> None:
        old = _character("A Raider", imagecaption="Camp guard") + "\n\n" + _character("A Raider", imagecaption="")
        new = (
            _character("A Raider", "character:raider 1", imagecaption="")
            + "\n\n"
            + _character("A Raider", "character:raider 2", imagecaption="")
        )

        with pytest.raises(AmbiguousRootsError, match="character:raider 1, character:raider 2"):
            FieldPreservationHandler().merge_templates(old, new, ["Character"])

    def test_same_name_roots_with_equal_preserved_values_pair_by_position(self) -> None:
        old = (
            _character("A Raider", imagecaption="Camp guard")
            + "\n\n"
            + _character("A Raider", imagecaption="Camp guard")
        )
        new = (
            _character("A Raider", "character:raider 1", imagecaption="")
            + "\n\n"
            + _character("A Raider", "character:raider 2", imagecaption="")
        )

        text = FieldPreservationHandler().merge_templates(old, new, ["Character"]).text

        assert text == (
            _character("A Raider", "character:raider 1", imagecaption="Camp guard")
            + "\n\n"
            + _character("A Raider", "character:raider 2", imagecaption="Camp guard")
        )

    def test_same_name_roots_without_preserved_values_pair_by_position(self) -> None:
        old = _character("A Raider", level="3") + "\n\n" + _character("A Raider", level="4")
        new = (
            _character("A Raider", "character:raider 1", level="5")
            + "\n\n"
            + _character("A Raider", "character:raider 2", level="6")
        )

        assert FieldPreservationHandler().merge_templates(old, new, ["Character"]).text == new

    def test_same_name_roots_pair_with_the_entity_whose_data_they_hold(self) -> None:
        old = (
            _character("A Raider", imagecaption="North camp", coordinates="1 x 1 x 1")
            + "\n\n"
            + _character("A Raider", imagecaption="South camp", coordinates="2 x 2 x 2")
        )
        new = (
            _character("A Raider", "character:raider south", imagecaption="", coordinates="2 x 2 x 2")
            + "\n\n"
            + _character("A Raider", "character:raider north", imagecaption="", coordinates="1 x 1 x 1")
        )

        text = FieldPreservationHandler().merge_templates(old, new, ["Character"]).text

        assert text == (
            _character("A Raider", "character:raider north", imagecaption="North camp", coordinates="1 x 1 x 1")
            + "\n\n"
            + _character("A Raider", "character:raider south", imagecaption="South camp", coordinates="2 x 2 x 2")
        )

    def test_a_live_root_keeps_its_value_away_from_a_variant_it_does_not_describe(self) -> None:
        old = _character("A Dream", coordinates="3 x 3 x 3")
        new = (
            _character("A Dream", "character:dream 1", coordinates="")
            + "\n\n"
            + _character("A Dream", "character:dream 3", coordinates="3 x 3 x 3")
        )

        text = FieldPreservationHandler().merge_templates(old, new, ["Character"]).text

        assert text == (
            _character("A Dream", "character:dream 3", coordinates="3 x 3 x 3")
            + "\n\n"
            + _character("A Dream", "character:dream 1", coordinates="")
        )


class TestRootCompanions:
    """A merged root takes the companions of its generated root."""

    @pytest.mark.parametrize(
        ("root", "companion", "key"),
        [
            ("Ability", "SpellTooltip", "spell:flame bolt"),
            ("Ability", "SkillTooltip", "skill:kick"),
            ("Stance", "StanceTooltip", "stance:aggressive"),
        ],
    )
    def test_companion_follows_its_root_and_the_merge_is_idempotent(self, root: str, companion: str, key: str) -> None:
        old = f"{{{{{root}\n|title=Name\n}}}}\n\nEditor prose.\n\n{{{{{companion}|stablekey=stale}}}}"
        new = f"{{{{{root}\n|title=Name\n|stablekey={key}\n}}}}\n{{{{{companion}|stablekey={key}}}}}"
        handler = _linked_handler()

        first = handler.merge_templates(old, new, [root]).text
        second = handler.merge_templates(first, new, [root]).text

        assert first == (
            f"{{{{{root}\n|title=Name\n|stablekey={key}\n}}}}\n\nEditor prose.\n\n{{{{{companion}|stablekey={key}}}}}"
        )
        assert second == first

    def test_missing_companion_is_inserted_after_its_root_and_extra_companions_go(self) -> None:
        old = (
            "{{Ability\n|title=A\n}}\n\nProse A.\n\n"
            "{{Ability\n|title=B\n}}\n{{SpellTooltip|stablekey=spell:b}}\n{{SpellTooltip|stablekey=spell:b}}"
        )
        new = (
            "{{Ability\n|title=A\n|stablekey=spell:a\n}}\n{{SpellTooltip|stablekey=spell:a}}\n\n"
            "{{Ability\n|title=B\n|stablekey=spell:b\n}}\n{{SpellTooltip|stablekey=spell:b}}"
        )

        text = _linked_handler().merge_templates(old, new, ["Ability"]).text

        assert text.count("{{SpellTooltip|stablekey=spell:b}}") == 1
        assert text.startswith(
            "{{Ability\n|title=A\n|stablekey=spell:a\n}}\n{{SpellTooltip|stablekey=spell:a}}\n\nProse A."
        )

    def test_companion_inside_editor_markup_is_replaced_in_place(self) -> None:
        layout = '{| style="width:50%;"\n| style="vertical-align:top;" |\n'
        old = "{{Item\n|title=Charm\n}}\n\n" + layout + "{{Item/Charm|name=Old}}\n|}\n\nNotes."
        new = "{{Item\n|title=Charm\n|stablekey=item:charm\n}}\n{{Item/Charm|name=New}}"

        text = _linked_handler().merge_templates(old, new, ["Item"]).text

        assert (
            text
            == "{{Item\n|title=Charm\n|stablekey=item:charm\n}}\n\n" + layout + "{{Item/Charm|name=New}}\n|}\n\nNotes."
        )
