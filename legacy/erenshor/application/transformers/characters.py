"""Character page transformer.

Applies generated character content to existing wiki pages using parser-driven
transformations.
"""

from __future__ import annotations

import logging

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.transformers.base import PageTransformer
from erenshor.shared.wiki_parser import (
    find_templates as mw_find_templates,
)
from erenshor.shared.wiki_parser import (
    parse as mw_parse,
)
from erenshor.shared.wiki_parser import (
    replace_template_with_text as mw_replace_template,
)
from erenshor.shared.wiki_parser import (
    template_params as mw_template_params,
)

__all__ = ["CharacterTransformer"]


logger = logging.getLogger(__name__)


class CharacterTransformer(PageTransformer):
    """Transform character pages with generated content.

    Responsibilities:
    1. Parse existing page to locate Enemy/Character/Pet/Enemy Stats templates
    2. Merge manual imagecaption field when generated value is blank
    3. Replace existing Enemy template in place
    4. Insert new template after {{spoiler}} if present, else prepend
    5. Remove extra and legacy templates (Enemy Stats, Character, Pet)

    Per CLAUDE.md:
    - All characters use Enemy template regardless of friendly/hostile
    - Remove legacy Enemy Stats templates
    - Replace in place if exists, otherwise insert after {{spoiler}} or prepend
    - Preserve manual imagecaption when generated is blank
    """

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Transform character page with generated content.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from CharacterGenerator

        Returns:
            Updated wiki page text

        Raises:
            ValueError: If page structure is invalid
        """
        if not generated.rendered_blocks:
            raise ValueError("No rendered blocks in generated content")

        rendered_infobox = generated.rendered_blocks[0].text

        try:
            code = mw_parse(original)
        except Exception as exc:
            raise ValueError(f"Failed to parse character page: {exc}")

        # Find all relevant templates
        enemy_templates = mw_find_templates(code, ["Enemy"])
        character_templates = mw_find_templates(code, ["Character"])
        pet_templates = mw_find_templates(code, ["Pet"])
        enemy_stats_templates = mw_find_templates(code, ["Enemy Stats"])

        # Preserve existing Boss type classification and imagecaption
        existing_caption = ""
        existing_type = ""
        if enemy_templates:
            try:
                existing = mw_template_params(enemy_templates[0])
                existing_caption = (existing.get("imagecaption") or "").strip()
                existing_type = (existing.get("type") or "").strip()
            except Exception as e:
                logger.warning(
                    f"Failed to extract params from existing Enemy template: {e}"
                )

        # Merge existing values when appropriate
        if existing_caption or (existing_type == "[[Enemies|Boss]]"):
            try:
                new_code = mw_parse(rendered_infobox)
                new_tpls = list(new_code.filter_templates())
                if new_tpls:
                    nt = new_tpls[0]

                    # Preserve imagecaption when blank in generated
                    if existing_caption:
                        cur_cap = ""
                        try:
                            if nt.has("imagecaption"):
                                cur_cap = str(nt.get("imagecaption").value).strip()
                        except Exception as e:
                            logger.warning(
                                f"Failed to extract imagecaption from template: {e}"
                            )
                            cur_cap = ""
                        if not cur_cap:
                            nt.add("imagecaption", existing_caption, showkey=True)

                    # Preserve Boss type if it was manually set
                    if existing_type == "[[Enemies|Boss]]":
                        try:
                            if nt.has("type"):
                                nt.add("type", "[[Enemies|Boss]]", showkey=True)
                        except Exception as e:
                            logger.warning(f"Failed to preserve Boss type: {e}")

                    rendered_infobox = str(nt)
            except Exception as e:
                logger.warning(f"Failed to merge cached fields for character page: {e}")

        # Remove templates that predate current Enemy-only standard
        for t in enemy_stats_templates:
            code.replace(t, "")
        for t in character_templates:
            code.replace(t, "")
        for t in pet_templates:
            code.replace(t, "")

        # Replace or insert Enemy template
        if enemy_templates:
            # Replace first template in place
            first = enemy_templates[0]
            text = mw_replace_template(code, first, rendered_infobox.rstrip("\n"))
            try:
                code2 = mw_parse(text)
                # Remove any extra Enemy templates
                extras = mw_find_templates(code2, ["Enemy"])[1:]
                for extra_tpl in extras:
                    code2.replace(extra_tpl, "")
                return str(code2)
            except Exception as exc:
                logger.warning(
                    f"Failed to remove extra Enemy templates: {exc}. Returning text without cleanup."
                )
                return text
        else:
            # No Enemy template - insert after {{spoiler}} if present, else prepend
            spoiler_templates = mw_find_templates(code, ["spoiler"])
            if spoiler_templates:
                # Insert after first {{spoiler}}
                spoiler = spoiler_templates[0]
                # Find position after spoiler
                text = str(code)
                spoiler_str = str(spoiler)
                pos = text.find(spoiler_str)
                if pos >= 0:
                    end_pos = pos + len(spoiler_str)
                    return (
                        text[:end_pos]
                        + "\n\n"
                        + rendered_infobox.strip()
                        + "\n\n"
                        + text[end_pos:].lstrip("\n")
                    )
            # No spoiler - prepend
            return rendered_infobox.strip() + "\n\n" + str(code).lstrip("\n")
