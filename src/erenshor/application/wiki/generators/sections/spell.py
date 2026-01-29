"""Spell section generator for wiki content.

This module generates MediaWiki {{Ability}} template wikitext for spell entities.

This section generator produces templates for single spells. Multi-entity page
assembly is handled by PageGenerator classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.spell import EnrichedSpellData
    from erenshor.registry.resolver import RegistryResolver

# Game constants for cast time calculation
GAME_TICKS_PER_SECOND = 60  # Game runs at 60 ticks per second


class SpellSectionGenerator(SectionGeneratorBase):
    """Generator for spell wiki sections.

    Generates {{Ability}} template wikitext for a single spell entity.

    Multi-entity page assembly is handled by PageGenerator classes, not here.

    Example:
        >>> resolver = RegistryResolver(...)
        >>> generator = SpellSectionGenerator(resolver)
        >>> spell = Spell(...)  # From repository
        >>> wikitext = generator.generate_template(spell, page_title="Fireball")
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize spell template generator.

        Args:
            resolver: Registry resolver for links and display names
        """
        super().__init__()
        self._resolver = resolver

    def generate_template(
        self,
        enriched: EnrichedSpellData,
        page_title: str,
    ) -> str:
        """Generate {{Ability}} template wikitext for a single spell.

        Args:
            enriched: Enriched spell data with classes
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single spell (infobox + categories)

        Example:
            >>> enriched = EnrichedSpellData(spell=spell, classes=["Arcanist"])
            >>> wikitext = generator.generate_template(enriched, "Fireball")
        """
        spell = enriched.spell
        logger.debug(f"Generating template for spell: {spell.spell_name}")

        # Build template context
        context = self._build_spell_template_context(enriched, page_title)

        # Render template
        template_wikitext = self.render_template("ability.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports spells

        return self.normalize_wikitext(template_wikitext)

    def _build_spell_template_context(
        self,
        enriched: EnrichedSpellData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Ability}} template from Spell entity.

        Converts Spell entity to template context dict. The {{Ability}} template
        has many fields, most of which are optional.

        Args:
            enriched: Enriched spell data
            page_title: Wiki page title
            resolver: Registry resolver for image name overrides

        Returns:
            Template context dict with all {{Ability}} template fields
        """
        spell = enriched.spell

        def bool_str(value: int | None) -> str:
            """Convert int boolean to 'True' or empty string."""
            return "True" if value else ""

        # Calculate duration from ticks (if available)
        duration = ""
        has_duration = bool(spell.spell_duration_in_ticks)
        if spell.spell_duration_in_ticks:
            duration = self._format_duration(spell.spell_duration_in_ticks)

        # Format class restrictions with level: [[ClassName]] (level)
        classes_list = []
        if enriched.classes and spell.required_level and spell.required_level > 0:
            for class_name in sorted(enriched.classes):
                classes_list.append(f"[[{class_name}]] ({spell.required_level})")
        classes = "<br>".join(classes_list)

        # Format cast time: convert ticks to seconds, treat 0 and <0.05s as "Instant"
        cast_time_str = self._format_cast_time(spell.spell_charge_time)

        # Resolve image name from registry (with overrides)
        image_name = self._resolver.resolve_image_name(spell.stable_key)
        image = f"{image_name}.png"

        # Resolve references to links
        pet_to_summon = ""
        if spell.pet_to_summon_stable_key:
            pet_to_summon = str(self._resolver.character_link(spell.pet_to_summon_stable_key))

        status_effect = ""
        if spell.status_effect_to_apply_stable_key:
            status_effect = str(self._resolver.ability_link(spell.status_effect_to_apply_stable_key))

        add_proc = ""
        if spell.add_proc_stable_key:
            add_proc = str(self._resolver.ability_link(spell.add_proc_stable_key))

        # Format imagecaption from status effect message
        imagecaption = ""
        if spell.status_effect_message_on_player:
            imagecaption = f"You {spell.status_effect_message_on_player}"

        # Get display name from resolver (respects mapping.json overrides)
        display_name = self._resolver.resolve_display_name(spell.stable_key)

        context: dict[str, str] = {
            "title": display_name,
            "image": image,
            "imagecaption": imagecaption,
            "description": format_description(safe_str(spell.spell_desc)) if spell.spell_desc else "",
            "type": safe_str(spell.type),
            "line": safe_str(spell.line),
            "classes": classes,
            "required_level": safe_str(spell.required_level, zero_as_blank=True),
            "manacost": safe_str(spell.mana_cost, zero_as_blank=True),
            "aggro": safe_str(spell.aggro, zero_as_blank=True),
            "is_taunt": bool_str(spell.taunt_spell),
            "casttime": cast_time_str,
            "cooldown": self._format_cooldown(spell.cooldown),
            "duration": duration,
            "duration_in_ticks": safe_str(spell.spell_duration_in_ticks, zero_as_blank=True),
            "has_unstable_duration": bool_str(spell.unstable_duration),
            "is_instant_effect": bool_str(spell.instant_effect),
            "is_reap_and_renew": bool_str(spell.reap_and_renew),
            "is_sim_usable": bool_str(spell.sim_usable),
            "range": "" if spell.self_only else (str(int(spell.spell_range)) if spell.spell_range else ""),
            "max_level_target": safe_str(spell.max_level_target, zero_as_blank=True),
            "is_self_only": bool_str(spell.self_only),
            "is_group_effect": bool_str(spell.group_effect),
            "is_applied_to_caster": bool_str(spell.apply_to_caster),
            "effects": "",  # TODO: Build from multiple effect fields
            "damage_type": safe_str(spell.damage_type) if spell.target_damage else "",
            "resist_modifier": str(int(spell.resist_modifier)) if spell.resist_modifier else "",
            "target_damage": safe_str(spell.target_damage, zero_as_blank=True),
            "target_healing": safe_str(spell.target_healing, zero_as_blank=True),
            "caster_healing": safe_str(spell.caster_healing, zero_as_blank=True),
            "shield_amount": safe_str(spell.shielding_amt, zero_as_blank=True),
            "pet_to_summon": pet_to_summon,
            "status_effect": status_effect,
            "add_proc": add_proc,
            "add_proc_chance": safe_str(spell.add_proc_chance, zero_as_blank=True),
            "has_lifetap": bool_str(spell.lifetap),
            "lifesteal": safe_str(spell.percent_lifesteal, zero_as_blank=True),
            "damage_shield": safe_str(spell.damage_shield, zero_as_blank=True),
            "percent_mana_restoration": safe_str(spell.percent_mana_restoration, zero_as_blank=True),
            "bleed_damage_percent": safe_str(spell.bleed_damage_percent, zero_as_blank=True),
            "special_descriptor": safe_str(spell.special_descriptor),
            # Stat modifiers
            "hp": safe_str(spell.hp, zero_as_blank=True),
            "ac": safe_str(spell.ac, zero_as_blank=True),
            "mana": safe_str(spell.mana, zero_as_blank=True),
            "str": safe_str(spell.str_, zero_as_blank=True),
            "dex": safe_str(spell.dex, zero_as_blank=True),
            "end": safe_str(spell.end_, zero_as_blank=True),
            "agi": safe_str(spell.agi, zero_as_blank=True),
            "wis": safe_str(spell.wis, zero_as_blank=True),
            "int": safe_str(spell.int_, zero_as_blank=True),
            "cha": safe_str(spell.cha, zero_as_blank=True),
            "mr": safe_str(spell.mr, zero_as_blank=True),
            "er": safe_str(spell.er, zero_as_blank=True),
            "vr": safe_str(spell.vr, zero_as_blank=True),
            "pr": safe_str(spell.pr, zero_as_blank=True),
            "haste": safe_str(spell.haste, zero_as_blank=True),
            "resonance": safe_str(spell.resonate_chance, zero_as_blank=True),
            "movement_speed": safe_str(spell.movement_speed, zero_as_blank=True),
            "atk_roll_modifier": safe_str(spell.atk_roll_modifier, zero_as_blank=True),
            "xp_bonus": safe_str(spell.xp_bonus, zero_as_blank=True) if has_duration else "",
            # Crowd control
            "is_root": bool_str(spell.root_target),
            "is_stun": bool_str(spell.stun_target),
            "is_charm": bool_str(spell.charm_target),
            "is_broken_on_damage": bool_str(spell.break_on_damage),
            "is_fear": bool_str(spell.fear_target),
            "inflict_on_self": bool_str(spell.inflict_on_self),
            # Sources
            "itemswitheffect": self._format_item_links(enriched.items_with_effect),
            "source": self._format_item_links(enriched.teaching_items),
            "used_by": self._format_character_links(enriched.used_by_characters),
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

        # Treat very small cast times (< 0.05s) as "Instant"
        if seconds < 0.05:
            return "Instant"

        # Format as "X.X seconds"
        return f"{seconds:.1f} seconds"

    def _format_duration(self, duration_in_ticks: int) -> str:
        """Format spell duration from ticks to human-readable string.

        Args:
            duration_in_ticks: Duration in game ticks (3 seconds per tick)

        Returns:
            Formatted duration string in seconds

        Examples:
            >>> self._format_duration(1)
            '3 seconds'
            >>> self._format_duration(2)
            '6 seconds'
            >>> self._format_duration(10)
            '30 seconds'
        """
        # Game uses 3 seconds per duration tick (not the same as cast time ticks)
        seconds = duration_in_ticks * 3
        return f"{seconds} seconds"

    def _format_cooldown(self, cooldown: float | None) -> str:
        """Format spell cooldown to human-readable string.

        Args:
            cooldown: Cooldown in seconds (already in seconds, not ticks)

        Returns:
            Formatted cooldown string:
            - Empty string for None or 0
            - "X seconds" for positive values (as integer)

        Examples:
            >>> self._format_cooldown(None)
            ''
            >>> self._format_cooldown(0)
            ''
            >>> self._format_cooldown(9.0)
            '9 seconds'
            >>> self._format_cooldown(3.0)
            '3 seconds'
        """
        if cooldown is None or cooldown == 0:
            return ""

        # Convert to integer and add " seconds" suffix
        return f"{int(cooldown)} seconds"

    def _format_item_links(
        self,
        items: list[str],
    ) -> str:
        """Format list of items as {{ItemLink}} templates separated by <br>.

        Args:
            items: List of item stable keys

        Returns:
            Formatted string like "{{ItemLink|Item1}}<br>{{ItemLink|Item2}}"
            sorted alphabetically by display name, or empty string if no items

        Examples:
            >>> items = ["item:water"]
            >>> self._format_item_links(items)
            '{{ItemLink|Water}}'
        """
        if not items:
            return ""

        # Create link objects and filter out excluded items (page_title=None)
        links = [self._resolver.item_link(key) for key in items]
        links = [link for link in links if link.page_title is not None]

        # Sort by display name (WikiLink.__lt__ handles this)
        links.sort()

        return "<br>".join(str(link) for link in links)

    def _format_character_links(
        self,
        characters: list[str],
    ) -> str:
        """Format list of characters as [[Character]] links separated by <br>.

        Args:
            characters: List of character stable keys

        Returns:
            Formatted string like "[[Character1]]<br>[[Character2]]"
            sorted alphabetically by display name, or empty string if no characters

        Examples:
            >>> characters = ["character:goblin"]
            >>> self._format_character_links(characters)
            '[[Goblin]]'
        """
        if not characters:
            return ""

        # Create link objects and filter out excluded characters (page_title=None)
        links = [self._resolver.character_link(key) for key in characters]
        links = [link for link in links if link.page_title is not None]

        # Sort by display name (WikiLink.__lt__ handles this)
        links.sort()

        return "<br>".join(str(link) for link in links)
