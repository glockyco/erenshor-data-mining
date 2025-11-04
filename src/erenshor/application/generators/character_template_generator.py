"""Character template generator for wiki content.

This module generates MediaWiki {{Character}} template wikitext for individual
characters including NPCs, enemies, vendors, and other in-game entities.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.

Template structure:
- {{Character}} template + category tags
"""

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.entities.character import Character

if TYPE_CHECKING:
    from erenshor.application.services.character_enricher import EnrichedCharacterData


class CharacterTemplateGenerator(TemplateGeneratorBase):
    """Generator for character wiki templates.

    Generates {{Character}} template wikitext for a SINGLE character entity
    with appropriate category tags.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> generator = CharacterTemplateGenerator()
        >>> enriched_data = enricher.enrich(character)  # Done by service
        >>> wikitext = generator.generate_template(enriched_data, character, page_title="Goblin Scout")
    """

    def __init__(self) -> None:
        """Initialize generator."""
        super().__init__()

    def generate_template(self, enriched: "EnrichedCharacterData") -> str:
        """Generate template wikitext for a single character.

        Args:
            enriched: Pre-enriched character data (from CharacterEnricher service)

        Returns:
            Template wikitext for single character (infobox + categories)

        Example:
            >>> character = Character(id=1, object_name="Goblin", npc_name="Goblin Scout")
            >>> enriched = enricher.enrich(character, "Goblin Scout")
            >>> wikitext = generator.generate_template(enriched)
        """
        logger.debug(f"Generating template for character: {enriched.character.npc_name}")

        # Build template context from enriched data
        context = self._build_character_template_context(enriched)

        # Render template
        template_wikitext = self.render_template("character.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports characters

        return self.normalize_wikitext(template_wikitext)

    def _build_character_template_context(self, enriched: "EnrichedCharacterData") -> dict[str, str]:
        """Build context for {{Character}} template.

        Converts enriched character data to template context dict with ALL fields
        so that field preservation can work properly.

        Args:
            enriched: Enriched character data with formatted wiki fields

        Returns:
            Template context dict with all Character template fields
        """
        character = enriched.character

        # Calculate XP range with boss multiplier
        xp_range = ""
        if character.base_xp_min and character.base_xp_max:
            # Apply BossXpMultiplier (default to 1.0 if None or 0)
            multiplier = character.boss_xp_multiplier if character.boss_xp_multiplier else 1.0
            if multiplier == 0.0:
                multiplier = 1.0

            xp_min = int(character.base_xp_min * multiplier)
            xp_max = int(character.base_xp_max * multiplier)

            if xp_min == xp_max:
                xp_range = str(xp_min)
            else:
                xp_range = f"{xp_min}-{xp_max}"

        # Calculate resistance values based on game logic
        # Characters with HandSetResistances=1 use base values
        # Characters with HandSetResistances=0 use calculated ranges (level * 0.5 to level * 1.2)
        def _format_resistance(base_val: int | None, min_val: int | None, max_val: int | None, hand_set: int | None) -> str:
            if hand_set:
                return safe_str(base_val)
            # Use effective range for dynamic resistances
            min_r = min_val or 0
            max_r = max_val or 0
            return f"{min_r}-{max_r}" if min_r != max_r else str(min_r)

        context: dict[str, str] = {
            # Basic info
            "name": enriched.display_name,
            "image": f"{enriched.image_name}.png",
            "imagecaption": "",  # Manual edit field
            "type": enriched.enemy_type,
            "faction": enriched.faction,
            "faction_change": enriched.faction_change,
            "zones": enriched.zones,
            "coordinates": enriched.coordinates,
            "spawn_chance": enriched.spawn_chance,
            "respawn": enriched.respawn,
            "guaranteed_drops": enriched.guaranteed_drops,
            "drop_rates": enriched.drop_rates,
            # Stats from database
            "level": safe_str(character.level),
            "experience": xp_range,
            "health": safe_str(character.base_hp or character.effective_hp),
            "mana": safe_str(character.base_mana),
            "ac": safe_str(character.base_ac or character.effective_ac),
            "strength": safe_str(character.base_str),
            "endurance": safe_str(character.base_end),
            "dexterity": safe_str(character.base_dex),
            "agility": safe_str(character.base_agi),
            "intelligence": safe_str(character.base_int),
            "wisdom": safe_str(character.base_wis),
            "charisma": safe_str(character.base_cha),
            "magic": _format_resistance(character.base_mr, character.effective_min_mr, character.effective_max_mr, character.hand_set_resistances),
            "poison": _format_resistance(character.base_pr, character.effective_min_pr, character.effective_max_pr, character.hand_set_resistances),
            "elemental": _format_resistance(character.base_er, character.effective_min_er, character.effective_max_er, character.hand_set_resistances),
            "void": _format_resistance(character.base_vr, character.effective_min_vr, character.effective_max_vr, character.hand_set_resistances),
        }

        return context
