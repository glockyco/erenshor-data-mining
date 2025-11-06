"""Skill template generator for wiki content.

This module generates MediaWiki {{Ability}} template wikitext for skill entities.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.
"""

from __future__ import annotations

from loguru import logger

from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.enriched_data.skill import EnrichedSkillData
from erenshor.registry.resolver import RegistryResolver

# Game constants for cooldown calculation
GAME_TICKS_PER_SECOND = 60  # Game runs at 60 ticks per second


class SkillTemplateGenerator(TemplateGeneratorBase):
    """Generator for skill wiki templates.

    Generates {{Ability}} template wikitext for a SINGLE skill entity.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> resolver = RegistryResolver(...)
        >>> generator = SkillTemplateGenerator(resolver)
        >>> skill = Skill(...)  # From repository
        >>> wikitext = generator.generate_template(skill, page_title="Shield Bash")
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize skill template generator.

        Args:
            resolver: Registry resolver for links and display names
        """
        super().__init__()
        self._resolver = resolver

    def generate_template(self, enriched: EnrichedSkillData, page_title: str) -> str:
        """Generate {{Ability}} template wikitext for a single skill.

        Args:
            enriched: Enriched skill data with items and teaching items
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single skill (infobox + categories)

        Example:
            >>> enriched = EnrichedSkillData(skill=skill, entity=entity, items_with_effect=[], teaching_items=[])
            >>> wikitext = generator.generate_template(enriched, "Shield Bash")
        """
        skill = enriched.skill
        logger.debug(f"Generating template for skill: {skill.skill_name}")

        # Build template context
        context = self._build_skill_template_context(enriched, page_title)

        # Render template
        template_wikitext = self.render_template("ability.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports skills

        return self.normalize_wikitext(template_wikitext)

    def _build_skill_template_context(
        self,
        enriched: EnrichedSkillData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Ability}} template from Skill entity.

        Converts Skill entity to template context dict. Skills have simpler
        data than spells (no mana cost, cast time, most buffs/debuffs, etc.).

        Args:
            enriched: Enriched skill data
            page_title: Wiki page title
            resolver: Registry resolver for image name overrides

        Returns:
            Template context dict with all {{Ability}} template fields
        """
        skill = enriched.skill

        def bool_str(value: int | None) -> str:
            """Convert int boolean to 'True' or empty string."""
            return "True" if value else ""

        # Format class restrictions with levels: [[ClassName]] (level)
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

        # Sort alphabetically and format with wiki links and levels
        class_level_pairs.sort(key=lambda x: x[0])
        classes_list = [f"[[{class_name}]] ({level})" for class_name, level in class_level_pairs]
        classes = ", ".join(classes_list)

        # Determine minimum level requirement across all classes
        min_level = min([level for _, level in class_level_pairs]) if class_level_pairs else None

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

        # Resolve image name from registry (with overrides)
        image_name = self._resolver.resolve_image_name(skill.stable_key)
        image = f"{image_name}.png"

        # Resolve references to links
        pet_to_summon = ""
        if skill.spawn_on_use_stable_key:
            pet_to_summon = self._resolver.character_link(skill.spawn_on_use_stable_key)

        status_effect = ""
        if skill.effect_to_apply_stable_key:
            status_effect = self._resolver.ability_link(skill.effect_to_apply_stable_key)

        cast_on_target = ""
        if skill.cast_on_target_stable_key:
            cast_on_target = self._resolver.ability_link(skill.cast_on_target_stable_key)

        # Combine effects (both status_effect and cast_on_target)
        effects_parts = []
        seen_effects: set[str] = set()
        if status_effect and status_effect not in seen_effects:
            effects_parts.append(status_effect)
            seen_effects.add(status_effect)
        if cast_on_target and cast_on_target not in seen_effects:
            effects_parts.append(cast_on_target)
            seen_effects.add(cast_on_target)
        effects = "<br>".join(effects_parts)

        # Determine cast time: non-innate skills are instant
        skill_type = skill.type_of_skill or "Passive"
        cast_time = ""
        if skill.type_of_skill and skill.type_of_skill != "Innate":
            cast_time = "Instant"

        # Format cooldown: convert ticks to seconds, format as duration
        cooldown = self._format_cooldown(skill.cooldown)

        # Damage type only shown for Attack skills
        damage_type = safe_str(skill.damage_type) if skill_type == "Attack" else ""

        # Format source from teaching items
        source = self._format_item_links(enriched.teaching_items)

        context: dict[str, str] = {
            "title": page_title,
            "image": image,
            "imagecaption": "",
            "description": safe_str(skill.skill_desc),
            "type": skill_type,
            "line": "",  # Skills don't have spell lines
            "classes": classes,
            "required_level": "",  # Redundant with classes field
            "manacost": "",  # Skills don't use mana
            "aggro": "",  # Not tracked for skills
            "is_taunt": "",  # Not tracked for skills
            "casttime": cast_time,
            "cooldown": cooldown,
            "duration": "",  # Not tracked for skills
            "duration_in_ticks": "",  # Not tracked for skills
            "has_unstable_duration": "",  # Not tracked for skills
            "is_instant_effect": "",  # Not tracked for skills
            "is_reap_and_renew": "",  # Not tracked for skills
            "is_sim_usable": bool_str(skill.sim_players_autolearn),
            "range": safe_str(skill.skill_range, zero_as_blank=True),
            "max_level_target": "",  # Not tracked for skills
            "is_self_only": bool_str(skill.affect_player and not skill.affect_target),
            "is_group_effect": bool_str(skill.ae_skill),
            "is_applied_to_caster": bool_str(skill.affect_player),
            "effects": effects,
            "damage_type": damage_type,
            "resist_modifier": "",  # Not tracked for skills
            "target_damage": safe_str(skill.skill_power, zero_as_blank=True),
            "target_healing": "",  # Not tracked separately for skills
            "caster_healing": "",  # Not tracked for skills
            "shield_amount": "",  # Not tracked for skills
            "pet_to_summon": pet_to_summon,
            "status_effect": "",  # Combined into effects field
            "add_proc": "",  # Not tracked for skills
            "add_proc_chance": "",  # Not tracked for skills
            "has_lifetap": "",  # Not tracked for skills
            "lifesteal": "",  # Not tracked for skills
            "damage_shield": "",  # Not tracked for skills
            "percent_mana_restoration": "",  # Not tracked for skills
            "bleed_damage_percent": "",  # Not tracked for skills
            "special_descriptor": equipment_desc,  # Show equipment requirements
            # Stat modifiers (skills don't provide stat buffs)
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
            # Crowd control
            "is_root": "",  # Not tracked separately for skills
            "is_stun": "",  # Not tracked separately for skills
            "is_charm": "",  # Not tracked separately for skills
            "is_broken_on_damage": "",  # Not tracked for skills
            # Sources
            "itemswitheffect": "",  # TODO: Get from junction table
            "source": source,
        }

        return context

    def _format_cooldown(self, cooldown: float | None) -> str:
        """Format skill cooldown from ticks to human-readable duration string.

        Args:
            cooldown: Cooldown in game ticks (60 ticks/second)

        Returns:
            Formatted duration string (e.g., "9 seconds", "1 minute 30 seconds")
            or empty string if no cooldown

        Examples:
            >>> self._format_cooldown(None)
            ''
            >>> self._format_cooldown(0)
            ''
            >>> self._format_cooldown(540)  # 540 ticks = 9 seconds
            '9 seconds'
        """
        if cooldown is None or cooldown == 0:
            return ""

        # Convert ticks to seconds
        seconds = cooldown / GAME_TICKS_PER_SECOND

        # Format as duration
        return self._seconds_to_duration(int(seconds))

    def _seconds_to_duration(self, seconds: int) -> str:
        """Convert seconds to human-readable duration string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "9 seconds", "1 minute 30 seconds")
            or empty string if zero

        Examples:
            >>> self._seconds_to_duration(0)
            ''
            >>> self._seconds_to_duration(9)
            '9 seconds'
            >>> self._seconds_to_duration(90)
            '1 minute 30 seconds'
        """
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

    def _format_item_links(
        self,
        items: list[str],
    ) -> str:
        """Format list of items as {{ItemLink}} templates separated by <br>.

        Args:
            items: List of item stable keys

        Returns:
            Formatted string like "{{ItemLink|Item1}}<br>{{ItemLink|Item2}}"
            sorted alphabetically by resolved page title, or empty string if no items

        Examples:
            >>> items = ["item:water"]
            >>> self._format_item_links(items)
            '{{ItemLink|Water}}'
        """
        if not items:
            return ""

        # Resolve page titles and build (title, link) tuples
        item_data = []
        for stable_key in items:
            page_title = self._resolver.resolve_page_title(stable_key)
            if page_title is None:
                # Skip excluded items
                continue
            link = self._resolver.item_link(stable_key)
            item_data.append((page_title, link))

        # Sort by page title (case-insensitive)
        item_data.sort(key=lambda x: x[0].lower())

        # Extract just the links
        item_links = [link for _, link in item_data]

        return "<br>".join(item_links)
