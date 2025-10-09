"""Ability page transformer.

Applies generated ability content to existing wiki pages using parser-driven
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

__all__ = ["AbilityTransformer"]


logger = logging.getLogger(__name__)


class AbilityTransformer(PageTransformer):
    """Transform ability pages with generated content.

    Responsibilities:
    1. Parse existing page to locate Ability template
    2. Merge manual imagecaption field when generated value is blank
    3. Replace existing Ability template in place (preserves surrounding content)
    4. Insert new template at top if none exists
    5. Remove extra Ability templates (ensure exactly one)

    Content preservation:
    - Content before first {{Ability}} template is preserved
    - Content after last {{Ability}} template is preserved
    - Content between multiple {{Ability}} templates is preserved (multi-entity pages)
    - Only {{Ability}} templates themselves are replaced

    Idempotency:
    - Repeated transforms produce identical output
    - imagecaption is only merged once (won't duplicate)
    - Template removal is deterministic
    """

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Transform ability page with generated content.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from AbilityGenerator

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
            raise ValueError(f"Failed to parse ability page: {exc}")

        tpls = mw_find_templates(code, ["Ability"])

        # Merge existing imagecaption when blank in generated
        try:
            if tpls:
                existing = mw_template_params(tpls[0])
                old_cap = (existing.get("imagecaption") or "").strip()
                if old_cap:
                    new_code = mw_parse(rendered_infobox)
                    new_tpls = list(new_code.filter_templates())
                    if new_tpls:
                        nt = new_tpls[0]
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
                            nt.add("imagecaption", old_cap, showkey=True)
                            rendered_infobox = str(nt)
        except Exception as e:
            logger.warning(f"Failed to merge imagecaption for ability page: {e}")

        if tpls:
            # Replace first template in place
            first = tpls[0]
            # Strip trailing newline to prevent accumulating blank lines
            text = mw_replace_template(code, first, rendered_infobox.rstrip("\n"))
            try:
                code2 = mw_parse(text)
                # Remove any extra Ability templates
                extras = mw_find_templates(code2, ["Ability"])[1:]
                for extra_tpl in extras:
                    code2.replace(extra_tpl, "")
                return str(code2)
            except Exception as exc:
                logger.warning(
                    f"Failed to remove extra Ability templates: {exc}. Returning text without cleanup."
                )
                return text

        # No infobox present - insert at top
        return rendered_infobox.strip() + "\n\n" + original.lstrip("\n")
