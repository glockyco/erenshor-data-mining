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


class StanceSectionGenerator(SectionGeneratorBase):
    """Generator for stance wiki sections.

    Generates {{Stance}} template wikitext for a single stance entity.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self) -> None:
        super().__init__()

    def generate_template(
        self,
        enriched: EnrichedStanceData,
        page_title: str,
    ) -> str:
        """Generate {{Stance}} template wikitext for a single stance."""
        stance = enriched.stance
        logger.debug(f"Generating template for stance: {stance.display_name}")

        context = self._build_stance_template_context(enriched, page_title)
        template_wikitext = self.render_template("stance.jinja2", context)
        return self.normalize_wikitext(template_wikitext)

    def _build_stance_template_context(
        self,
        enriched: EnrichedStanceData,
        page_title: str,
    ) -> dict[str, str]:
        """Build context for {{Stance}} template from Stance entity."""
        stance = enriched.stance

        image = f"{stance.image_name}.png" if stance.image_name else ""
        display_name = stance.display_name or page_title

        # activated_by_skills are pre-built AbilityLink objects
        activated_by = self._format_wiki_links(enriched.activated_by_skills)

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
            # Skill links - pre-built WikiLink objects
            "activated_by": activated_by,
        }

        return context

    def _format_wiki_links(self, links: list) -> str:  # type: ignore[type-arg]
        """Format a list of WikiLink objects as wikitext separated by <br>."""
        if not links:
            return ""

        visible = [link for link in links if link.page_title is not None]
        visible.sort()
        return "<br>".join(str(link) for link in visible)
