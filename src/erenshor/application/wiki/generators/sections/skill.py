"""Skill section generator for wiki content.

This module generates MediaWiki {{Ability}} template wikitext for skill entities.

This section generator produces templates for single skills. Multi-entity page
assembly is handled by PageGenerator classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase

if TYPE_CHECKING:
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.domain.enriched_data.skill import EnrichedSkillData

# Game constants for cooldown calculation
GAME_TICKS_PER_SECOND = 60  # Game runs at 60 ticks per second


class SkillSectionGenerator(SectionGeneratorBase):
    """Generator for skill wiki sections.

    Generates {{Ability}} template wikitext for a single skill entity.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self, class_display: ClassDisplayNameService) -> None:
        """Initialize skill template generator.

        Args:
            class_display: Service for mapping class names to display names
        """
        super().__init__()
        self._class_display = class_display

    def generate_template(self, enriched: EnrichedSkillData, page_title: str) -> str:
        """Generate {{Ability}} template wikitext for a single skill."""
        skill = enriched.skill
        logger.debug(f"Generating template for skill: {skill.skill_name}")

        context = self._build_skill_template_context(enriched, page_title)
        template_wikitext = self.render_template("ability.jinja2", context)
        return self.normalize_wikitext(template_wikitext)

    def _build_skill_template_context(
        self,
        enriched: EnrichedSkillData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Ability}} template from Skill entity."""
        skill = enriched.skill

        def bool_str(value: int | None) -> str:
            return "True" if value else ""

        # Format class restrictions with levels: [[DisplayName]] (level)
        class_level_pairs = []
        if skill.duelist_required_level and skill.duelist_required_level > 0:
            class_level_pairs.append(("Duelist", skill.duelist_required_level))
        if skill.paladin_required_level and skill.paladin_required_level > 0:
            class_level_pairs.append(("Paladin", skill.paladin_required_level))
        if skill.arcanist_required_level and skill.arcanist_required_level > 0:
            class_level_pairs.append(("Arcanist", skill.arcanist_required_level))
        if skill.druid_required_level and skill.druid_required_level > 0:
            class_level_pairs.append(("Druid", skill.druid_required_level))
        if skill.stormcaller_required_level and skill.stormcaller_required_level > 0:
            class_level_pairs.append(("Stormcaller", skill.stormcaller_required_level))
        if skill.reaver_required_level and skill.reaver_required_level > 0:
            class_level_pairs.append(("Reaver", skill.reaver_required_level))

        display_pairs = [
            (self._class_display.get_display_name(class_name), level) for class_name, level in class_level_pairs
        ]
        display_pairs.sort(key=lambda x: x[0])
        classes_list = [f"[[{class_name}]] ({level})" for class_name, level in display_pairs]
        classes = "<br>".join(classes_list)

        # Build equipment requirements description
        equipment_reqs = []
        if skill.require_2h:
            equipment_reqs.append("Two-handed weapon")
        if skill.require_dw:
            equipment_reqs.append("Dual wield")
        if skill.require_bow:
            equipment_reqs.append("Bow")
        if skill.require_shield:
            equipment_reqs.append("Shield")
        if skill.require_behind:
            equipment_reqs.append("Behind target")

        equipment_desc = ", ".join(equipment_reqs) if equipment_reqs else ""

        image = f"{skill.image_name}.png" if skill.image_name else ""

        # Pre-built links from enriched DTO
        pet_to_summon = str(enriched.spawn_on_use) if enriched.spawn_on_use else ""
        status_effect = str(enriched.effect_to_apply) if enriched.effect_to_apply else ""
        activated_stance = str(enriched.activated_stance) if enriched.activated_stance else ""
        cast_on_target = str(enriched.cast_on_target) if enriched.cast_on_target else ""

        # Combine effects
        effects_parts = []
        seen_effects: set[str] = set()
        if status_effect and status_effect not in seen_effects:
            effects_parts.append(status_effect)
            seen_effects.add(status_effect)
        if activated_stance and activated_stance not in seen_effects:
            effects_parts.append(activated_stance)
            seen_effects.add(activated_stance)
        if cast_on_target and cast_on_target not in seen_effects:
            effects_parts.append(cast_on_target)
            seen_effects.add(cast_on_target)
        effects = "<br>".join(effects_parts)

        skill_type = skill.type_of_skill or "Passive"
        cast_time = ""
        if skill.type_of_skill and skill.type_of_skill != "Innate":
            cast_time = "Instant"

        cooldown = self._format_cooldown(skill.cooldown)
        damage_type = safe_str(skill.damage_type) if skill_type == "Attack" else ""

        # teaching_items are pre-built ItemLink objects
        source = self._format_wiki_links(enriched.teaching_items)

        display_name = skill.display_name or skill.skill_name or page_title

        context: dict[str, str] = {
            "title": display_name,
            "image": image,
            "imagecaption": "",
            "description": format_description(safe_str(skill.skill_desc)) if skill.skill_desc else "",
            "type": skill_type,
            "line": "",
            "classes": classes,
            "required_level": "",
            "manacost": "",
            "aggro": "",
            "is_taunt": "",
            "casttime": cast_time,
            "cooldown": cooldown,
            "duration": "",
            "duration_in_ticks": "",
            "has_unstable_duration": "",
            "is_instant_effect": "",
            "is_reap_and_renew": "",
            "is_sim_usable": bool_str(skill.sim_players_autolearn),
            "range": safe_str(skill.skill_range, zero_as_blank=True),
            "max_level_target": "",
            "is_self_only": bool_str(skill.affect_player and not skill.affect_target),
            "is_group_effect": bool_str(skill.ae_skill),
            "is_applied_to_caster": bool_str(skill.affect_player),
            "effects": effects,
            "damage_type": damage_type,
            "resist_modifier": "",
            "target_damage": safe_str(skill.skill_power, zero_as_blank=True),
            "target_healing": "",
            "caster_healing": "",
            "shield_amount": "",
            "pet_to_summon": pet_to_summon,
            "status_effect": "",
            "add_proc": "",
            "add_proc_chance": "",
            "has_lifetap": "",
            "lifesteal": "",
            "damage_shield": "",
            "percent_mana_restoration": "",
            "bleed_damage_percent": "",
            "special_descriptor": equipment_desc,
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
            "itemswitheffect": "",  # TODO: populate from enriched.items_with_effect when template supports it
            "source": source,
        }

        return context

    def _format_cooldown(self, cooldown: float | None) -> str:
        """Format skill cooldown from ticks to human-readable duration string."""
        if cooldown is None or cooldown == 0:
            return ""

        seconds = cooldown / GAME_TICKS_PER_SECOND
        return self._seconds_to_duration(int(seconds))

    def _seconds_to_duration(self, seconds: int) -> str:
        """Convert seconds to human-readable duration string."""
        if seconds == 0:
            return ""

        minutes = seconds // 60
        secs = seconds % 60

        if minutes > 0 and secs > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
        if minutes > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        if secs > 0:
            return f"{secs} second{'s' if secs != 1 else ''}"
        return ""

    def _format_wiki_links(self, links: list) -> str:  # type: ignore[type-arg]
        """Format a list of WikiLink objects as wikitext separated by <br>."""
        if not links:
            return ""

        visible = [link for link in links if link.page_title is not None]
        visible.sort()
        return "<br>".join(str(link) for link in visible)
