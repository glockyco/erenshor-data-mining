"""Character page generator for wiki content.

This module generates complete MediaWiki pages for characters including NPCs,
enemies, vendors, and other in-game entities.

Page structure:
- {{Character}} template + category tags
"""

from loguru import logger

from erenshor.application.generators.page_generator_base import PageGeneratorBase
from erenshor.domain.entities.character import Character


class CharacterPageGenerator(PageGeneratorBase):
    """Generator for character wiki pages.

    Creates complete wikitext pages for characters with {{Character}} template
    and appropriate category tags.

    Example:
        >>> generator = CharacterPageGenerator()
        >>> character = Character(...)  # From repository
        >>> wikitext = generator.generate_page(character, page_title="Goblin Scout")
    """

    def generate_page(self, character: Character, page_title: str) -> str:
        """Generate complete wiki page for a character.

        Args:
            character: Character entity from repository
            page_title: Wiki page title (from registry)

        Returns:
            Complete wikitext page with template and category tags

        Example:
            >>> character = Character(id=1, object_name="Goblin", npc_name="Goblin Scout")
            >>> wikitext = generator.generate_page(character, "Goblin Scout")
        """
        logger.debug(f"Generating page for character: {character.npc_name}")

        # Build template context
        context = self._build_character_template_context(character, page_title)

        # Render template
        template_wikitext = self.render_template("character.jinja2", context)

        # TODO: Add category tags when CategoryGenerator supports characters

        return self.normalize_wikitext(template_wikitext)

    def _build_character_template_context(self, character: Character, page_title: str) -> dict[str, str]:
        """Build context for {{Character}} template.

        Converts Character entity to template context dict.

        Args:
            character: Character entity
            page_title: Wiki page title

        Returns:
            Template context dict
        """

        def safe_str(value: object) -> str:
            """Convert value to string, handling None."""
            if value is None:
                return ""
            if isinstance(value, bool):
                return "True" if value else ""
            return str(value)

        # Calculate XP range if available
        xp_range = ""
        if character.base_xp_min and character.base_xp_max:
            if character.base_xp_min == character.base_xp_max:
                xp_range = str(int(character.base_xp_min))
            else:
                xp_range = f"{int(character.base_xp_min)}-{int(character.base_xp_max)}"

        context: dict[str, str] = {
            "name": page_title,
            "image": f"{character.object_name or 'Unknown'}.png",  # TODO: Use registry for image name
            "type": "",  # TODO: Determine type (Enemy, Vendor, NPC, etc.)
            "faction": safe_str(character.my_faction),
            "zones": "",  # TODO: Get zones from spawn points
            "level": safe_str(character.level),
            "experience": xp_range,
        }

        return context
