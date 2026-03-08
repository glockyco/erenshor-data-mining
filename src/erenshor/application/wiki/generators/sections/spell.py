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
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.domain.enriched_data.spell import EnrichedSpellData

# Game constants for cast time calculation
GAME_TICKS_PER_SECOND = 60  # Game runs at 60 ticks per second


class SpellSectionGenerator(SectionGeneratorBase):
    """Generator for spell wiki sections.

    Generates {{Ability}} template wikitext for a single spell entity.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self, class_display: ClassDisplayNameService) -> None:
        """Initialize spell template generator.

        Args:
            class_display: Service for mapping class names to display names
        """
        super().__init__()
        self._class_display = class_display

    def generate_template(
        self,
        enriched: EnrichedSpellData,
        page_title: str,
    ) -> str:
        """Generate {{Ability}} template wikitext for a single spell."""
        spell = enriched.spell
        logger.debug(f"Generating template for spell: {spell.spell_name}")

        context = self._build_spell_template_context(enriched, page_title)
        template_wikitext = self.render_template("ability.jinja2", context)
        return self.normalize_wikitext(template_wikitext)

    def _build_spell_template_context(
        self,
        enriched: EnrichedSpellData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Ability}} template from Spell entity."""
        spell = enriched.spell

        def bool_str(value: int | None) -> str:
            return "True" if value else ""

        # Calculate duration from ticks (if available)
        duration = ""
        has_duration = bool(spell.spell_duration_in_ticks)
        if spell.spell_duration_in_ticks:
            duration = self._format_duration(spell.spell_duration_in_ticks)

        # Format class restrictions with level: [[DisplayName]] (level)
        classes_list = []
        if enriched.classes and spell.required_level and spell.required_level > 0:
            display_names = self._class_display.map_class_list(enriched.classes)
            for display_name in display_names:
                classes_list.append(f"[[{display_name}]] ({spell.required_level})")
        classes = "<br>".join(classes_list)

        cast_time_str = self._format_cast_time(spell.spell_charge_time)

        image = f"{spell.image_name}.png" if spell.image_name else ""

        # Pre-built links on the Spell entity and enriched DTO
        pet_to_summon = str(enriched.pet_to_summon) if enriched.pet_to_summon else ""
        status_effect = str(spell.status_effect_link) if spell.status_effect_link else ""
        add_proc = str(spell.add_proc_link) if spell.add_proc_link else ""

        imagecaption = ""
        if spell.status_effect_message_on_player:
            imagecaption = f"You {spell.status_effect_message_on_player}"

        display_name = spell.display_name or spell.spell_name or page_title

        # Items with effect and teaching items are already ItemLink objects
        itemswitheffect = self._format_wiki_links(enriched.items_with_effect)
        source = self._format_wiki_links(enriched.teaching_items)
        used_by = self._format_wiki_links(enriched.used_by_characters)

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
            "itemswitheffect": itemswitheffect,
            "source": source,
            "used_by": used_by,
        }

        return context

    def _format_cast_time(self, spell_charge_time: float | None) -> str:
        """Format spell cast time in ticks to human-readable string."""
        if spell_charge_time is None or spell_charge_time == 0:
            return "Instant"

        seconds = spell_charge_time / GAME_TICKS_PER_SECOND

        if seconds < 0.05:
            return "Instant"

        return f"{seconds:.1f} seconds"

    def _format_duration(self, duration_in_ticks: int) -> str:
        """Format spell duration from ticks to human-readable string."""
        seconds = duration_in_ticks * 3
        return f"{seconds} seconds"

    def _format_cooldown(self, cooldown: float | None) -> str:
        """Format spell cooldown to human-readable string."""
        if cooldown is None or cooldown == 0:
            return ""

        return f"{int(cooldown)} seconds"

    def _format_wiki_links(self, links: list) -> str:  # type: ignore[type-arg]
        """Format a list of WikiLink objects as wikitext separated by <br>.

        Filters out links with no page_title (excluded entities), sorts by display
        name, and joins with <br>.
        """
        if not links:
            return ""

        visible = [link for link in links if link.page_title is not None]
        visible.sort()
        return "<br>".join(str(link) for link in visible)
