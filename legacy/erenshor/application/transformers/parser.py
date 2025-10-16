"""Wiki parser utilities wrapping mwparserfromhell.

Provides clean, reusable functions for common wikitext operations without
exposing raw mwparserfromhell details to transformers.
"""

from __future__ import annotations

import logging
from typing import Any

from erenshor.shared.wiki_parser import (
    find_templates as mw_find_templates,
)
from erenshor.shared.wiki_parser import (
    parse as mw_parse,
)
from erenshor.shared.wiki_parser import (
    replace_template_with_text as mw_replace_template,
)

__all__ = ["WikiParser"]


logger = logging.getLogger(__name__)


class WikiParser:
    """Wrapper around mwparserfromhell for common wiki operations.

    Provides high-level methods for template manipulation, avoiding
    regex and ensuring deterministic AST-based transformations.
    """

    def replace_infobox(self, page_text: str, new_infobox: str) -> str:
        """Replace all item infoboxes with a single new one at the top.

        Removes all existing item infobox templates (Item, Weapon, Armor, etc.)
        and inserts the new infobox at the top of the page.

        Args:
            page_text: Original wiki page text
            new_infobox: Rendered infobox template to insert

        Returns:
            Updated page text with single infobox at top

        Raises:
            ValueError: If page cannot be parsed
        """
        names = [
            "Weapon",
            "Armor",
            "Auras",
            "Ability Books",
            "Ability_Books",
            "Mold",
            "Item",
            "Consumable",
            "Ability",
        ]
        try:
            code = mw_parse(page_text)
            for t in list(mw_find_templates(code, names)):
                code.replace(t, "")
            for t in list(mw_find_templates(code, ["Fancy-item"])):
                code.replace(t, "")
            cleaned = str(code)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse item page for infobox replacement: {exc}"
            )

        return new_infobox.strip() + "\n\n" + cleaned.lstrip("\n")

    def ensure_fancy_table(
        self,
        page_text: str,
        kind: str,
        tier_bodies: dict[str, str],
        table_body: str,
    ) -> str:
        """Ensure Fancy table present with 3 tiers for weapons/armor.

        If Fancy templates exist, updates them in place. Otherwise, inserts
        the complete table immediately after the infobox.

        Args:
            page_text: Original wiki page text
            kind: Item kind ("weapon" or "armor")
            tier_bodies: Dict mapping tier keys (e.g., "tier_weapon_0") to rendered templates
            table_body: Complete Fancy table to insert if no templates exist

        Returns:
            Updated page text with Fancy table

        Raises:
            ValueError: If page cannot be parsed
        """
        name = "Fancy-weapon" if kind == "weapon" else "Fancy-armor"
        try:
            code = mw_parse(page_text)
        except Exception as exc:
            raise ValueError(f"Failed to parse page for Fancy table placement: {exc}")

        fancy_tiers = mw_find_templates(code, [name])
        if fancy_tiers:
            text = page_text
            for i in range(3):
                body = tier_bodies.get(f"tier_{kind}_{i}")
                if not body:
                    continue
                try:
                    code_i = mw_parse(text)
                    tiers = mw_find_templates(code_i, [name])
                    if len(tiers) > i:
                        text = mw_replace_template(code_i, tiers[i], body.rstrip("\n"))
                except Exception as e:
                    logger.warning(
                        f"Failed to replace {name} tier {i} template: {e}. Skipping tier."
                    )
            return text

        infobox_names = [
            "Weapon",
            "Armor",
            "Auras",
            "Ability Books",
            "Ability_Books",
            "Mold",
            "Item",
            "Consumable",
        ]
        infoboxes = mw_find_templates(code, infobox_names)
        if infoboxes:
            infobox = infoboxes[0]
            combo = str(infobox) + "\n\n" + table_body.strip() + "\n\n"
            return mw_replace_template(code, infobox, combo)

        return table_body.strip() + "\n\n" + page_text.lstrip("\n")

    def remove_fancy_tables(self, page_text: str) -> str:
        """Remove all Fancy tables from page.

        Args:
            page_text: Original wiki page text

        Returns:
            Page text with Fancy tables removed
        """
        s = page_text
        i = 0
        while True:
            start = s.find("{|", i)
            if start == -1:
                break
            end = s.find("|}", start)
            if end == -1:
                break
            seg = s[start : end + 2]
            if "Fancy-weapon" in seg or "Fancy-armor" in seg:
                s = s[:start] + s[end + 2 :]
                i = 0
                continue
            i = end + 2
        return s

    def find_template(
        self, page_text: str, template_names: list[str]
    ) -> tuple[Any, Any | None]:
        """Find first template matching any of the given names.

        Args:
            page_text: Wiki page text to search
            template_names: List of template names to search for

        Returns:
            Tuple of (parsed code, first matching template or None)
        """
        code = mw_parse(page_text)
        templates = mw_find_templates(code, template_names)
        return code, templates[0] if templates else None

    def extract_template_params(self, template: Any) -> dict[str, str]:
        """Extract all parameters from a template as a dict.

        Args:
            template: mwparserfromhell template object

        Returns:
            Dict mapping parameter names to values (as strings)
        """
        from erenshor.shared.wiki_parser import template_params

        return template_params(template)

    def ensure_fancy_charm(self, page_text: str, charm_body: str) -> str:
        """Ensure Fancy-charm template is present.

        If Fancy-charm template exists, replaces it. Otherwise, inserts
        the template immediately after the infobox.

        Args:
            page_text: Original wiki page text
            charm_body: Rendered Fancy-charm template to insert/replace

        Returns:
            Updated page text with Fancy-charm template

        Raises:
            ValueError: If page cannot be parsed
        """
        try:
            code = mw_parse(page_text)
        except Exception as exc:
            raise ValueError(f"Failed to parse page for Fancy-charm placement: {exc}")

        # Check if Fancy-charm template already exists
        fancy_charms = mw_find_templates(code, ["Fancy-charm"])
        if fancy_charms:
            # Replace existing template
            return mw_replace_template(code, fancy_charms[0], charm_body.rstrip("\n"))

        # No existing template, insert after infobox
        infobox_names = [
            "Weapon",
            "Armor",
            "Auras",
            "Ability Books",
            "Ability_Books",
            "Mold",
            "Item",
            "Consumable",
        ]
        infoboxes = mw_find_templates(code, infobox_names)
        if infoboxes:
            infobox = infoboxes[0]
            combo = str(infobox) + "\n\n" + charm_body.strip() + "\n\n"
            return mw_replace_template(code, infobox, combo)

        # No infobox found, insert at top
        return charm_body.strip() + "\n\n" + page_text.lstrip("\n")
