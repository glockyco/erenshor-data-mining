"""Item page transformer.

Applies generated item content to existing wiki pages using parser-driven
transformations.
"""

from __future__ import annotations

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.transformers.base import PageTransformer
from erenshor.application.transformers.merger import FieldMerger
from erenshor.application.transformers.parser import WikiParser
from erenshor.application.transformers.render_support import (
    extract_canonical_item_snippets,
)

__all__ = ["ItemTransformer"]


class ItemTransformer(PageTransformer):
    """Transform item pages with generated content.

    Responsibilities:
    1. Extract snippets from GeneratedContent
    2. Classify item kind (weapon, armor, etc.)
    3. Replace infobox with field merging
    4. Handle Fancy tables for weapons/armor
    5. Remove Fancy tables for non-weapons/armor

    Logic extracted from update/item_updater.py.
    """

    def __init__(self, parser: WikiParser, merger: FieldMerger) -> None:
        """Initialize item transformer.

        Args:
            parser: Wiki parser for template manipulation
            merger: Field merger for preserving manual edits
        """
        self._parser = parser
        self._merger = merger

    def transform(
        self,
        original: str,
        generated: GeneratedContent,
    ) -> str:
        """Transform item page with generated content.

        Args:
            original: Original wiki page text (from cache)
            generated: Generated content from ItemGenerator

        Returns:
            Updated wiki page text

        Raises:
            ValueError: If page structure is invalid
        """
        snippet_blocks = [(b.template_key, b.text) for b in generated.rendered_blocks]
        snippets = extract_canonical_item_snippets(snippet_blocks)

        kind_str = self._infer_kind_from_snippets(snippets)
        # Cast to ItemKind for type safety
        from typing import cast

        from erenshor.domain.services.item_classifier import ItemKind

        kind: ItemKind = cast(ItemKind, kind_str)

        infobox_body = snippets.get("infobox", "").strip()
        page_text = original

        if infobox_body:
            infobox_body = self._retarget_template_name(infobox_body, kind_str)
            infobox_body = self._merger.merge_manual_fields(
                original, infobox_body, kind
            )
            page_text = self._parser.replace_infobox(page_text, infobox_body)

        if kind_str in ("weapon", "armor"):
            table_key = "table_weapon" if kind_str == "weapon" else "table_armor"
            table_body = snippets.get(table_key, "").strip()
            if table_body:
                tier_bodies = {
                    f"tier_{kind_str}_{i}": snippets.get(f"tier_{kind_str}_{i}", "")
                    for i in range(3)
                }
                page_text = self._parser.ensure_fancy_table(
                    page_text, kind_str, tier_bodies, table_body
                )
        else:
            page_text = self._parser.remove_fancy_tables(page_text)

        return page_text

    def _infer_kind_from_snippets(self, snippets: dict[str, str]) -> str:
        """Infer item kind from which templates were rendered.

        Args:
            snippets: Extracted snippet dictionary

        Returns:
            Item kind string (weapon, armor, aura, ability_book, mold, consumable, general)
        """
        if "table_weapon" in snippets or any("tier_weapon_" in k for k in snippets):
            return "weapon"
        if "table_armor" in snippets or any("tier_armor_" in k for k in snippets):
            return "armor"

        # Check infobox to determine other types
        infobox = snippets.get("infobox", "")
        if "Infobox_item_ability_book" in snippets or (
            infobox and "Learn Skill:" in infobox or "Learn Spell:" in infobox
        ):
            return "ability_book"
        if "Infobox_item_mold" in snippets:
            return "mold"
        if "Infobox_item_consumable" in snippets:
            return "consumable"
        if "Infobox_item_aura" in snippets:
            return "aura"

        return "general"

    def _retarget_template_name(self, body: str, kind: str) -> str:
        """Retarget template name based on item kind.

        Args:
            body: Template body text
            kind: Item kind from classification

        Returns:
            Template body with correct template name
        """
        import re

        target_name = (
            "Item"
            if kind in ("weapon", "armor", "aura", "general", "consumable")
            else "Ability Books"
            if kind == "ability_book"
            else "Mold"
            if kind == "mold"
            else "Item"
        )

        # Replace any existing item infobox template name with target template name
        # Matches: {{Weapon, {{Armor, {{Item, etc. at start of body
        pattern = re.compile(
            r"^\{\{\s*(Weapon|Armor|Auras|Ability Books|Ability_Books|Consumable|Mold|Item)"
        )
        return pattern.sub("{{" + target_name, body, count=1)
