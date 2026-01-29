"""Stance section generator for wiki content.

This module generates MediaWiki {{Stance}} template wikitext for stance entities.

This section generator produces templates for single stances. Multi-entity page
assembly is handled by PageGenerator classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.stance import EnrichedStanceData
    from erenshor.registry.resolver import RegistryResolver


class StanceSectionGenerator(SectionGeneratorBase):
    """Generator for stance wiki sections.

    Generates {{Stance}} template wikitext for a single stance entity.

    Multi-entity page assembly is handled by PageGenerator classes, not here.

    Example:
        >>> resolver = RegistryResolver(...)
        >>> generator = StanceSectionGenerator(resolver)
        >>> stance = Stance(...)  # From repository
        >>> enriched = enrich(stance)
        >>> wikitext = generator.generate_template(enriched, page_title="Aggressive")
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize stance template generator.

        Args:
            resolver: Registry resolver for links and display names
        """
        super().__init__()
        self._resolver = resolver

    def generate_template(
        self,
        enriched: EnrichedStanceData,
        page_title: str,
    ) -> str:
        """Generate {{Stance}} template wikitext for a single stance.

        Args:
            enriched: Enriched stance data with activating skills
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single stance (infobox + categories)

        Example:
            >>> enriched = EnrichedStanceData(stance=stance, activated_by_skills=["skill:stance - aggressive"])
            >>> wikitext = generator.generate_template(enriched, "Aggressive")
        """
        stance = enriched.stance
        logger.debug(f"Generating template for stance: {stance.display_name}")

        # Build template context
        context = self._build_stance_template_context(enriched, page_title)

        # Render template
        template_wikitext = self.render_template("stance.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports stances

        return self.normalize_wikitext(template_wikitext)

    def _build_stance_template_context(
        self,
        enriched: EnrichedStanceData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Stance}} template from Stance entity.

        Converts Stance entity to template context dict. All fields are passed
        as raw values - formatting is handled by MediaWiki templates, not here.

        Args:
            enriched: Enriched stance data
            page_title: Wiki page title

        Returns:
            Template context dict with all {{Stance}} template fields
        """
        stance = enriched.stance

        # Resolve image name from registry (with overrides)
        image_name = self._resolver.resolve_image_name(stance.stable_key)
        image = f"{image_name}.png"

        # Get display name from resolver (respects mapping.json overrides)
        display_name = self._resolver.resolve_display_name(stance.stable_key)

        # Format activated_by skills as ability links
        activated_by = self._format_skill_links(enriched.activated_by_skills)

        context: dict[str, str] = {
            "title": display_name,
            "image": image,
            "description": format_description(safe_str(stance.stance_desc)) if stance.stance_desc else "",
            "switch_message": safe_str(stance.switch_message),
            # Combat modifiers - RAW VALUES (let wiki format them)
            "max_hp_mod": safe_str(stance.max_hp_mod, zero_as_blank=True),
            "damage_mod": safe_str(stance.damage_mod, zero_as_blank=True),
            "damage_taken_mod": safe_str(stance.damage_taken_mod, zero_as_blank=True),
            "proc_rate_mod": safe_str(stance.proc_rate_mod, zero_as_blank=True),
            "aggro_gen_mod": safe_str(stance.aggro_gen_mod, zero_as_blank=True),
            "spell_damage_mod": safe_str(stance.spell_damage_mod, zero_as_blank=True),
            # Self-damage - RAW VALUES
            "self_damage_per_attack": safe_str(stance.self_damage_per_attack, zero_as_blank=True),
            "self_damage_per_cast": safe_str(stance.self_damage_per_cast, zero_as_blank=True),
            # Lifesteal/resonance - RAW VALUES
            "lifesteal_amount": safe_str(stance.lifesteal_amount, zero_as_blank=True),
            "resonance_amount": safe_str(stance.resonance_amount, zero_as_blank=True),
            # Stop regen - RAW VALUE (0 or 1)
            "stop_regen": safe_str(stance.stop_regen, zero_as_blank=True),
            # Skill links - FORMATTED using resolver
            "activated_by": activated_by,
        }

        return context

    def _format_skill_links(
        self,
        skill_stable_keys: list[str],
    ) -> str:
        """Format list of skill stable keys as {{AbilityLink}} templates separated by <br>.

        Args:
            skill_stable_keys: List of skill stable keys (not names)

        Returns:
            Formatted string like "{{AbilityLink|Skill1}}<br>{{AbilityLink|Skill2}}"
            sorted alphabetically by display name, or empty string if no skills

        Examples:
            >>> keys = ["skill:stance - aggressive", "skill:stance - defensive"]
            >>> self._format_skill_links(keys)
            '{{AbilityLink|Stance: Aggressive}}<br>{{AbilityLink|Stance: Defensive}}'
        """
        if not skill_stable_keys:
            return ""

        # Create link objects and filter out excluded skills (page_title=None)
        links = [self._resolver.ability_link(key) for key in skill_stable_keys]
        links = [link for link in links if link.page_title is not None]

        # Sort by display name (WikiLink.__lt__ handles this)
        links.sort()

        return "<br>".join(str(link) for link in links)
