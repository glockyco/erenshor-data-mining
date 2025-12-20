"""Tests for fancy table/template replacement in WikiGenerateService.

Tests that legacy Fancy-* tables and templates are replaced with new Item/*
templates while preserving the original formatting (no spaces added around
equals signs).
"""

from erenshor.application.wiki.services.generate_service import WikiGenerateService


class TestFancyTableReplacement:
    """Test fancy table replacement preserves formatting."""

    def test_replace_weapon_table_preserves_no_space_formatting(self):
        """Test weapon table replacement preserves |param=value format (no spaces)."""
        # Old wikitext has legacy Fancy-weapon templates
        old_wikitext = """{{Item
|title=Test Weapon
}}

{|{
|-
||{{Fancy-weapon
| image = [[File:Test.png|80px]]
| name = Old Format
| tier = 0
}}
|}
"""

        # New wikitext has modern Item/Weapon templates
        new_wikitext = """{{Item
|title=Test Weapon
}}

{|{
|-
||{{Item/Weapon
|image=[[File:Test.png|80px]]
|name=New Format
|tier=0
}}
|}
"""

        # Create minimal service instance (we only need the helper method)
        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Result should have no spaces around equals and use new template name
        assert "{{Item/Weapon" in result
        assert "|image=[[File:Test.png|80px]]" in result
        assert "|name=New Format" in result
        assert "| image =" not in result
        assert "| name =" not in result
        # Legacy template should be replaced
        assert "{{Fancy-weapon" not in result

    def test_replace_armor_table_preserves_no_space_formatting(self):
        """Test armor table replacement preserves |param=value format (no spaces)."""
        # Old wikitext has legacy Fancy-armor templates
        old_wikitext = """{{Item
|title=Test Armor
}}

{|{
|-
||{{Fancy-armor
| image = [[File:Test.png|80px]]
| name = Old Format
| tier = 0
}}
|}
"""

        # New wikitext has modern Item/Armor templates
        new_wikitext = """{{Item
|title=Test Armor
}}

{|{
|-
||{{Item/Armor
|image=[[File:Test.png|80px]]
|name=New Format
|tier=0
}}
|}
"""

        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Result should have no spaces around equals and use new template name
        assert "{{Item/Armor" in result
        assert "|image=[[File:Test.png|80px]]" in result
        assert "|name=New Format" in result
        assert "| image =" not in result
        assert "| name =" not in result
        # Legacy template should be replaced
        assert "{{Fancy-armor" not in result

    def test_replace_charm_template_preserves_no_space_formatting(self):
        """Test charm template replacement preserves |param=value format (no spaces)."""
        # Old wikitext has legacy Fancy-charm template
        old_wikitext = """{{Item
|title=Test Charm
}}

{{Fancy-charm
| image = [[File:Test.png|80px]]
| name = Old Format
| description = Old description
}}
"""

        # New wikitext has modern Item/Charm template
        new_wikitext = """{{Item
|title=Test Charm
}}

{{Item/Charm
|image=[[File:Test.png|80px]]
|name=New Format
|description=New description
}}
"""

        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Result should have no spaces around equals and use new template name
        assert "{{Item/Charm" in result
        assert "|image=[[File:Test.png|80px]]" in result
        assert "|name=New Format" in result
        assert "|description=New description" in result
        assert "| image =" not in result
        assert "| name =" not in result
        # Legacy template should be replaced
        assert "{{Fancy-charm" not in result

    def test_replace_charm_with_nested_templates(self):
        """Test charm replacement handles nested templates like {{AbilityLink}}."""
        # Old wikitext has legacy Fancy-charm template
        old_wikitext = """{{Item
|title=Test Charm
}}

{{Fancy-charm
| image = [[File:Test.png|80px]]
| name = Old Format
| proc_name = Old Proc
}}
"""

        # New wikitext has modern Item/Charm with nested template
        new_wikitext = """{{Item
|title=Test Charm
}}

{{Item/Charm
|image=[[File:Test.png|80px]]
|name=New Format
|proc_name={{AbilityLink|Tangle}}
}}
"""

        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Result should preserve nested template and use new template name
        assert "{{Item/Charm" in result
        assert "{{AbilityLink|Tangle}}" in result
        assert "|proc_name={{AbilityLink|Tangle}}" in result
        # No spaces around equals
        assert "| proc_name =" not in result
        # Legacy template should be replaced
        assert "{{Fancy-charm" not in result

    def test_replace_weapon_table_with_nested_templates(self):
        """Test weapon table replacement handles nested templates."""
        # Old wikitext has legacy Fancy-weapon template
        old_wikitext = """{{Item
|title=Test Weapon
}}

{|{
|-
||{{Fancy-weapon
| image = [[File:Test.png|80px]]
| proc_name = Old Proc
| tier = 0
}}
|}
"""

        # New wikitext has modern Item/Weapon with nested template
        new_wikitext = """{{Item
|title=Test Weapon
}}

{|{
|-
||{{Item/Weapon
|image=[[File:Test.png|80px]]
|proc_name={{AbilityLink|Stun}}
|tier=0
}}
|}
"""

        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Result should preserve nested template and use new template name
        assert "{{Item/Weapon" in result
        assert "{{AbilityLink|Stun}}" in result
        assert "|proc_name={{AbilityLink|Stun}}" in result
        # Legacy template should be replaced
        assert "{{Fancy-weapon" not in result

    def test_no_replacement_when_no_fancy_templates(self):
        """Test no replacement occurs when new content has no fancy templates."""
        old_wikitext = """{{Item
|title=Test Item
}}

Some content
"""

        new_wikitext = """{{Item
|title=Test Item
}}

Different content
"""

        service = WikiGenerateService(
            storage=None,  # type: ignore
            item_repo=None,  # type: ignore
            character_repo=None,  # type: ignore
            spell_repo=None,  # type: ignore
            skill_repo=None,  # type: ignore
            faction_repo=None,  # type: ignore
            spawn_repo=None,  # type: ignore
            loot_repo=None,  # type: ignore
            quest_repo=None,  # type: ignore
            registry_resolver=None,  # type: ignore
        )

        result = service._replace_fancy_tables(old_wikitext, new_wikitext)

        # Should return old content unchanged
        assert result == old_wikitext
