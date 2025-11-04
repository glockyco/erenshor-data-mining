"""Skill template generator for wiki content.

This module generates MediaWiki {{Ability}} template wikitext for skill entities.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.
"""

from loguru import logger

from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.entities.skill import Skill


class SkillTemplateGenerator(TemplateGeneratorBase):
    """Generator for skill wiki templates.

    Generates {{Ability}} template wikitext for a SINGLE skill entity.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> generator = SkillTemplateGenerator()
        >>> skill = Skill(...)  # From repository
        >>> wikitext = generator.generate_template(skill, page_title="Shield Bash")
    """

    def generate_template(self, skill: Skill, page_title: str) -> str:
        """Generate {{Ability}} template wikitext for a single skill.

        Args:
            skill: Single Skill entity from repository
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single skill (infobox + categories)

        Example:
            >>> skill = Skill(skill_db_index=35, resource_name="Shield Bash", skill_name="Shield Bash")
            >>> wikitext = generator.generate_template(skill, "Shield Bash")
        """
        logger.debug(f"Generating template for skill: {skill.skill_name}")

        # Build template context
        context = self._build_skill_template_context(skill, page_title)

        # Render template
        template_wikitext = self.render_template("ability.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports skills

        return self.normalize_wikitext(template_wikitext)

    def _build_skill_template_context(self, skill: Skill, page_title: str) -> dict[str, str]:
        """Build context for {{Ability}} template from Skill entity.

        Converts Skill entity to template context dict. Skills have simpler
        data than spells (no mana cost, cast time, most buffs/debuffs, etc.).

        Args:
            skill: Skill entity
            page_title: Wiki page title

        Returns:
            Template context dict with all {{Ability}} template fields
        """

        def bool_str(value: int | None) -> str:
            """Convert int boolean to 'True' or empty string."""
            return "True" if value else ""

        # Format class restrictions from level requirements
        # If any class has a level requirement, list those classes
        class_names = []
        if skill.duelist_required_level:
            class_names.append("Duelist")
        if skill.paladin_required_level:
            class_names.append("Paladin")
        if skill.arcanist_required_level:
            class_names.append("Arcanist")
        if skill.druid_required_level:
            class_names.append("Druid")
        if skill.stormcaller_required_level:
            class_names.append("Stormcaller")

        classes = ", ".join(class_names) if class_names else ""

        # Determine minimum level requirement across all classes
        level_requirements = [
            skill.duelist_required_level,
            skill.paladin_required_level,
            skill.arcanist_required_level,
            skill.druid_required_level,
            skill.stormcaller_required_level,
        ]
        min_level = min([lvl for lvl in level_requirements if lvl]) if any(level_requirements) else None

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

        context: dict[str, str] = {
            "id": safe_str(skill.id),
            "title": page_title,
            "image": f"{skill.resource_name if skill.resource_name is not None else 'Unknown'}.png",  # TODO: Use registry for image name
            "imagecaption": "",
            "description": safe_str(skill.skill_desc),
            "type": safe_str(skill.type_of_skill),
            "line": "",  # Skills don't have spell lines
            "classes": classes,
            "required_level": safe_str(min_level),
            "manacost": "",  # Skills don't use mana
            "aggro": "",  # Not tracked for skills
            "is_taunt": "",  # Not tracked for skills
            "casttime": "",  # Skills don't have cast time
            "cooldown": safe_str(skill.cooldown),
            "duration": "",  # Not tracked for skills
            "duration_in_ticks": "",  # Not tracked for skills
            "has_unstable_duration": "",  # Not tracked for skills
            "is_instant_effect": "",  # Not tracked for skills
            "is_reap_and_renew": "",  # Not tracked for skills
            "is_sim_usable": bool_str(skill.sim_players_autolearn),
            "range": safe_str(skill.skill_range),
            "max_level_target": "",  # Not tracked for skills
            "is_self_only": bool_str(skill.affect_player and not skill.affect_target),
            "is_group_effect": bool_str(skill.ae_skill),
            "is_applied_to_caster": bool_str(skill.affect_player),
            "effects": "",  # TODO: Build from effect_to_apply_id and other fields
            "damage_type": safe_str(skill.damage_type),
            "resist_modifier": "",  # Not tracked for skills
            "target_damage": safe_str(skill.skill_power),  # Use skill_power for damage
            "target_healing": "",  # Not tracked separately for skills
            "caster_healing": "",  # Not tracked for skills
            "shield_amount": "",  # Not tracked for skills
            "pet_to_summon": safe_str(skill.spawn_on_use_resource_name),
            "status_effect": safe_str(skill.effect_to_apply_id),
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
            "source": "",  # TODO: Determine source (trainer, drop, quest, etc.)
        }

        return context
