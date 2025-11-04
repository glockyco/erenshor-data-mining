"""Spell template generator for wiki content.

This module generates MediaWiki {{Ability}} template wikitext for spell entities.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.
"""

from loguru import logger

from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.entities.spell import Spell

# Game constants for cast time calculation
GAME_TICKS_PER_SECOND = 60  # Game runs at 60 ticks per second


class SpellTemplateGenerator(TemplateGeneratorBase):
    """Generator for spell wiki templates.

    Generates {{Ability}} template wikitext for a SINGLE spell entity.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> generator = SpellTemplateGenerator()
        >>> spell = Spell(...)  # From repository
        >>> wikitext = generator.generate_template(spell, page_title="Fireball")
    """

    def generate_template(self, spell: Spell, page_title: str) -> str:
        """Generate {{Ability}} template wikitext for a single spell.

        Args:
            spell: Single Spell entity from repository
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single spell (infobox + categories)

        Example:
            >>> spell = Spell(spell_db_index=1, resource_name="Fireball", spell_name="Fireball")
            >>> wikitext = generator.generate_template(spell, "Fireball")
        """
        logger.debug(f"Generating template for spell: {spell.spell_name}")

        # Build template context
        context = self._build_spell_template_context(spell, page_title)

        # Render template
        template_wikitext = self.render_template("ability.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports spells

        return self.normalize_wikitext(template_wikitext)

    def _build_spell_template_context(self, spell: Spell, page_title: str) -> dict[str, str]:
        """Build context for {{Ability}} template from Spell entity.

        Converts Spell entity to template context dict. The {{Ability}} template
        has many fields, most of which are optional.

        Args:
            spell: Spell entity
            page_title: Wiki page title

        Returns:
            Template context dict with all {{Ability}} template fields
        """

        def bool_str(value: int | None) -> str:
            """Convert int boolean to 'True' or empty string."""
            return "True" if value else ""

        # Calculate duration from ticks (if available)
        duration = ""
        if spell.spell_duration_in_ticks:
            duration = f"{spell.spell_duration_in_ticks} ticks"

        # Format class restrictions
        classes = safe_str(spell.classes)

        # Format cast time: convert ticks to seconds, treat 0 and <0.05s as "Instant"
        cast_time_str = self._format_cast_time(spell.spell_charge_time)

        context: dict[str, str] = {
            "id": safe_str(spell.id),
            "title": page_title,
            "image": f"{spell.resource_name if spell.resource_name is not None else 'Unknown'}.png",  # TODO: Use registry for image name
            "imagecaption": "",
            "description": safe_str(spell.spell_desc),
            "type": safe_str(spell.type),
            "line": safe_str(spell.line),
            "classes": classes,
            "required_level": safe_str(spell.required_level),
            "manacost": safe_str(spell.mana_cost),
            "aggro": safe_str(spell.aggro),
            "is_taunt": bool_str(spell.taunt_spell),
            "casttime": cast_time_str,
            "cooldown": safe_str(spell.cooldown),
            "duration": duration,
            "duration_in_ticks": safe_str(spell.spell_duration_in_ticks),
            "has_unstable_duration": bool_str(spell.unstable_duration),
            "is_instant_effect": bool_str(spell.instant_effect),
            "is_reap_and_renew": bool_str(spell.reap_and_renew),
            "is_sim_usable": bool_str(spell.sim_usable),
            "range": safe_str(spell.spell_range),
            "max_level_target": safe_str(spell.max_level_target),
            "is_self_only": bool_str(spell.self_only),
            "is_group_effect": bool_str(spell.group_effect),
            "is_applied_to_caster": bool_str(spell.apply_to_caster),
            "effects": "",  # TODO: Build from multiple effect fields
            "damage_type": safe_str(spell.damage_type),
            "resist_modifier": safe_str(spell.resist_modifier),
            "target_damage": safe_str(spell.target_damage),
            "target_healing": safe_str(spell.target_healing),
            "caster_healing": safe_str(spell.caster_healing),
            "shield_amount": safe_str(spell.shielding_amt),
            "pet_to_summon": safe_str(spell.pet_to_summon_resource_name),
            "status_effect": safe_str(spell.status_effect_to_apply),
            "add_proc": safe_str(spell.add_proc),
            "add_proc_chance": safe_str(spell.add_proc_chance),
            "has_lifetap": bool_str(spell.lifetap),
            "lifesteal": safe_str(spell.percent_lifesteal),
            "damage_shield": safe_str(spell.damage_shield),
            "percent_mana_restoration": safe_str(spell.percent_mana_restoration),
            "bleed_damage_percent": safe_str(spell.bleed_damage_percent),
            "special_descriptor": safe_str(spell.special_descriptor),
            # Stat modifiers
            "hp": safe_str(spell.hp),
            "ac": safe_str(spell.ac),
            "mana": safe_str(spell.mana),
            "str": safe_str(spell.strength),
            "dex": safe_str(spell.dexterity),
            "end": safe_str(spell.endurance),
            "agi": safe_str(spell.agility),
            "wis": safe_str(spell.wisdom),
            "int": safe_str(spell.intelligence),
            "cha": safe_str(spell.charisma),
            "mr": safe_str(spell.magic_resist),
            "er": safe_str(spell.elemental_resist),
            "vr": safe_str(spell.void_resist),
            "pr": safe_str(spell.poison_resist),
            "haste": safe_str(spell.haste),
            "resonance": safe_str(spell.resonate_chance),
            "movement_speed": safe_str(spell.movement_speed),
            "atk_roll_modifier": safe_str(spell.atk_roll_modifier),
            "xp_bonus": safe_str(spell.xp_bonus),
            # Crowd control
            "is_root": bool_str(spell.root_target),
            "is_stun": bool_str(spell.stun_target),
            "is_charm": bool_str(spell.charm_target),
            "is_broken_on_damage": bool_str(spell.break_on_damage),
            # Sources
            "itemswitheffect": "",  # TODO: Get from junction table
            "source": "",  # TODO: Determine source (trainer, drop, quest, etc.)
        }

        return context

    def _format_cast_time(self, spell_charge_time: float | None) -> str:
        """Format spell cast time in ticks to human-readable string.

        Args:
            spell_charge_time: Spell charge time in game ticks (60 ticks/second)

        Returns:
            Formatted cast time string:
            - "Instant" for None or 0
            - "X.X seconds" for all other values

        Examples:
            >>> self._format_cast_time(None)
            'Instant'
            >>> self._format_cast_time(0)
            'Instant'
            >>> self._format_cast_time(2)  # 2 ticks = 0.033s
            '0.0 seconds'
            >>> self._format_cast_time(60)  # 60 ticks = 1.0s
            '1.0 seconds'
            >>> self._format_cast_time(180)  # 180 ticks = 3.0s
            '3.0 seconds'
        """
        if spell_charge_time is None or spell_charge_time == 0:
            return "Instant"

        # Convert ticks to seconds
        seconds = spell_charge_time / GAME_TICKS_PER_SECOND

        # Format as "X.X seconds"
        return f"{seconds:.1f} seconds"
