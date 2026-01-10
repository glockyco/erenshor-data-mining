"""Unit tests for SectionGeneratorBase.

Tests the base class functionality including template rendering, category
formatting, and wikitext normalization.
"""

import pytest

from erenshor.application.wiki.generators.sections.base import (
    SectionGeneratorBase,
    TemplateNotFoundError,
)


class ConcreteSectionGenerator(SectionGeneratorBase):
    """Concrete implementation for testing abstract base."""

    def generate_template(self, *args, **kwargs) -> str:
        """Minimal implementation for testing."""
        return "test template"


class TestTemplateGeneratorBase:
    """Test suite for TemplateGeneratorBase."""

    def test_init_creates_jinja_environment(self):
        """Test that initialization creates Jinja2 environment."""
        generator = ConcreteSectionGenerator()
        assert generator._jinja_env is not None
        assert generator._template_dir.exists()

    def test_render_template_with_simple_context(self):
        """Test rendering a template with simple context."""
        generator = ConcreteSectionGenerator()

        # Item template exists in templates/
        context = {
            "title": "Test Item",
            "image": "[[File:Test.png]]",
            "imagecaption": "",
            "type": "Weapon",
            "vendorsource": "",
            "source": "Drop from enemies",
            "othersource": "",
            "questsource": "",
            "relatedquest": "",
            "craftsource": "",
            "componentfor": "",
            "relic": "",
            "classes": "Arcanist, Duelist",
            "effects": "",
            "damage": "10",
            "delay": "2.0",
            "dps": "5",
            "casttime": "",
            "duration": "",
            "cooldown": "",
            "description": "A test item",
            "buy": "100",
            "sell": "25",
            "itemid": "1",
            "crafting": "",
            "recipe": "",
        }

        result = generator.render_template("item.jinja2", context)

        assert "{{Item" in result
        assert "|title=Test Item" in result
        assert "|type=Weapon" in result
        assert "|source=Drop from enemies" in result
        assert "}}" in result

    def test_render_template_not_found(self):
        """Test that rendering non-existent template raises error."""
        generator = ConcreteSectionGenerator()

        with pytest.raises(TemplateNotFoundError):
            generator.render_template("nonexistent.jinja2", {})

    def test_normalize_wikitext_removes_trailing_whitespace(self):
        """Test that normalization removes trailing whitespace from lines."""
        generator = ConcreteSectionGenerator()

        text = "Line 1   \nLine 2\t\nLine 3"
        result = generator.normalize_wikitext(text)

        assert "Line 1   " not in result
        assert "Line 1\n" in result
        assert "Line 2\t" not in result
        assert "Line 2\n" in result

    def test_normalize_wikitext_reduces_excessive_blank_lines(self):
        """Test that normalization reduces 3+ consecutive blank lines to 2."""
        generator = ConcreteSectionGenerator()

        text = "Line 1\n\n\n\n\nLine 2"
        result = generator.normalize_wikitext(text)

        # Should reduce to max 2 consecutive blank lines
        assert "\n\n\n\n" not in result
        assert "Line 1\n\nLine 2" in result or "Line 1\n\n\nLine 2" in result

    def test_normalize_wikitext_ensures_trailing_newline(self):
        """Test that normalization ensures single trailing newline."""
        generator = ConcreteSectionGenerator()

        text_without_newline = "Line 1\nLine 2"
        result = generator.normalize_wikitext(text_without_newline)
        assert result.endswith("\n")
        assert not result.endswith("\n\n")

    def test_normalize_wikitext_empty_string(self):
        """Test normalizing empty string."""
        generator = ConcreteSectionGenerator()

        result = generator.normalize_wikitext("")

        assert result == ""

    def test_render_weapon_template(self):
        """Test rendering weapon template."""
        generator = ConcreteSectionGenerator()

        context = {
            "image": "[[File:Sword.png|150px]]",
            "name": "Sword of Testing",
            "type": "One-Hand",
            "relic": "",
            "str": "5",
            "end": "0",
            "dex": "3",
            "agi": "0",
            "int": "0",
            "wis": "0",
            "cha": "0",
            "res": "0",
            "damage": "10",
            "delay": "2.0",
            "health": "0",
            "mana": "0",
            "armor": "0",
            "magic": "0",
            "poison": "0",
            "elemental": "0",
            "void": "0",
            "description": "A sharp blade",
            "arcanist": "",
            "duelist": "True",
            "druid": "",
            "paladin": "",
            "stormcaller": "",
            "proc_name": "",
            "proc_desc": "",
            "proc_chance": "",
            "proc_style": "",
            "tier": "Normal",
        }

        result = generator.render_template("weapon.jinja2", context)

        assert "{{Item/Weapon" in result
        assert "|name=Sword of Testing" in result
        assert "|damage=10" in result
        assert "|tier=Normal" in result

    def test_render_armor_template(self):
        """Test rendering armor template."""
        generator = ConcreteSectionGenerator()

        context = {
            "image": "[[File:Helmet.png|150px]]",
            "name": "Test Helmet",
            "type": "",
            "slot": "Head",
            "relic": "",
            "str": "0",
            "end": "5",
            "dex": "0",
            "agi": "0",
            "int": "0",
            "wis": "0",
            "cha": "0",
            "res": "0",
            "health": "50",
            "mana": "0",
            "armor": "10",
            "magic": "5",
            "poison": "0",
            "elemental": "0",
            "void": "0",
            "description": "Protective headgear",
            "arcanist": "True",
            "duelist": "",
            "druid": "",
            "paladin": "",
            "stormcaller": "",
            "proc_name": "",
            "proc_desc": "",
            "proc_chance": "",
            "proc_style": "",
            "tier": "Normal",
        }

        result = generator.render_template("armor.jinja2", context)

        assert "{{Item/Armor" in result
        assert "|slot=Head" in result
        assert "|armor=10" in result

    def test_render_charm_template(self):
        """Test rendering charm template."""
        generator = ConcreteSectionGenerator()

        context = {
            "image": "[[File:Charm.png|150px]]",
            "name": "Test Charm",
            "description": "Magical charm",
            "strscaling": "1.0",
            "endscaling": "0.5",
            "dexscaling": "0",
            "agiscaling": "0",
            "intscaling": "0",
            "wisscaling": "0",
            "chascaling": "0",
            "arcanist": "True",
            "duelist": "",
            "druid": "",
            "paladin": "",
            "stormcaller": "",
        }

        result = generator.render_template("charm.jinja2", context)

        assert "{{Item/Charm" in result
        assert "|strscaling=1.0" in result

    def test_render_character_template(self):
        """Test rendering character template."""
        generator = ConcreteSectionGenerator()

        context = {
            "name": "Test Goblin",
            "image": "Goblin.png",
            "type": "Enemy",
            "faction": "Evil",
            "zones": "Forest, Cave",
            "level": "5",
            "level_mod_min": "0",
            "level_mod_max": "0",
            "variance_min": "-1",
            "variance_max": "1",
            "xp_multiplier": "1.0",
        }

        result = generator.render_template("character.jinja2", context)

        assert "{{Enemy" in result
        assert "|name=Test Goblin" in result
        assert "|level=5" in result
        assert "|levelmodmin=0" in result
        assert "|xpmultiplier=1.0" in result

    def test_render_spell_template(self):
        """Test rendering spell template (partial check due to size)."""
        generator = ConcreteSectionGenerator()

        context = {
            "id": "spell_001",
            "title": "Test Spell",
            "image": "Spell.png",
            "imagecaption": "",
            "description": "A test spell",
            "type": "Damage",
            "line": "Fire",
            "classes": "Arcanist",
            "required_level": "10",
            "manacost": "50",
            "aggro": "100",
            "is_taunt": "",
            "casttime": "2.0",
            "cooldown": "10",
            "duration": "20 ticks",
            "duration_in_ticks": "20",
            "has_unstable_duration": "",
            "is_instant_effect": "",
            "is_reap_and_renew": "",
            "is_sim_usable": "True",
            "range": "30",
            "max_level_target": "",
            "is_self_only": "",
            "is_group_effect": "",
            "is_applied_to_caster": "",
            "effects": "",
            "damage_type": "Magic",
            "resist_modifier": "1.0",
            "target_damage": "100",
            "target_healing": "",
            "caster_healing": "",
            "shield_amount": "",
            "pet_to_summon": "",
            "status_effect": "",
            "add_proc": "",
            "add_proc_chance": "",
            "has_lifetap": "",
            "lifesteal": "",
            "damage_shield": "",
            "percent_mana_restoration": "",
            "bleed_damage_percent": "",
            "special_descriptor": "",
            "hp": "",
            "ac": "",
            "mana": "",
            "str": "",
            "dex": "",
            "end": "",
            "agi": "",
            "wis": "",
            "int": "",
            "cha": "",
            "mr": "",
            "er": "",
            "vr": "",
            "pr": "",
            "haste": "",
            "resonance": "",
            "movement_speed": "",
            "atk_roll_modifier": "",
            "xp_bonus": "",
            "is_root": "",
            "is_stun": "",
            "is_charm": "",
            "is_broken_on_damage": "",
            "itemswitheffect": "",
            "source": "",
        }

        result = generator.render_template("ability.jinja2", context)

        assert "{{Ability" in result
        assert "|title=Test Spell" in result
        assert "|type=Damage" in result
        assert "|target_damage=100" in result
