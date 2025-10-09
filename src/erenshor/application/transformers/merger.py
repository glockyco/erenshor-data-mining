"""Field merging logic for preserving manual wiki edits.

Implements selective field preservation based on content type and CLAUDE.md rules.
"""

from __future__ import annotations

import logging
from typing import Any

from erenshor.domain.services.item_classifier import ItemKind
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.wiki_parser import parse as mw_parse

__all__ = ["FieldMerger"]


logger = logging.getLogger(__name__)


class FieldMerger:
    """Merge manual wiki fields with generated content.

    Preserves select manual fields based on content type rules:
    - Standard items: preserve imagecaption, othersource, type when our values blank
    - Weapon/armor: do NOT preserve imagecaption or type (handled by Fancy tables)
    """

    def merge_manual_fields(
        self,
        original: str,
        generated_infobox: str,
        item_kind: ItemKind,
    ) -> str:
        """Merge manual fields from original page into generated infobox.

        Args:
            original: Original wiki page text
            generated_infobox: Newly generated infobox template
            item_kind: Classification of item (weapon, armor, etc.)

        Returns:
            Generated infobox with manual fields merged in
        """
        try:
            code, existing_tpl = self._find_item_infobox(original)
            if not existing_tpl:
                return generated_infobox

            existing_params = self._extract_params(existing_tpl)

            merge: dict[str, str] = {}
            preserve_fields = ["othersource", "type", "imagecaption", "relatedquest"]

            for field in preserve_fields:
                if field in ("type", "imagecaption") and item_kind in (
                    "weapon",
                    "armor",
                ):
                    continue
                val = (existing_params.get(field) or "").strip()
                if val:
                    merge[field] = val

            try:
                code_new = mw_parse(generated_infobox)
                new_tpls = list(code_new.filter_templates())
            except Exception as e:
                logger.warning(
                    f"Failed to parse generated infobox during field merge: {e}"
                )
                new_tpls = []

            if new_tpls:
                nt = new_tpls[0]

                def _param(nt_: Any, name_: str) -> str:
                    try:
                        return (
                            str(nt_.get(name_).value).strip() if nt_.has(name_) else ""
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract parameter '{name_}' from template: {e}"
                        )
                        return ""

                gen_others = _param(nt, "othersource")
                old_others = (existing_params.get("othersource") or "").strip()
                if gen_others and old_others:

                    def split_vals(s: str) -> list[str]:
                        return [
                            p.strip()
                            for p in s.split(WIKITEXT_LINE_SEPARATOR)
                            if p.strip()
                        ]

                    old_lower = old_others.lower()
                    gen_parts = split_vals(gen_others)
                    filtered_gen: list[str] = []
                    for p in gen_parts:
                        if p == "[[Fishing]]" and "fishing" in old_lower:
                            continue
                        if p == "[[Mining]]" and "mining" in old_lower:
                            continue
                        filtered_gen.append(p)
                    parts: list[str] = []
                    for p in filtered_gen + split_vals(old_others):
                        if p not in parts:
                            parts.append(p)
                    nt.add(
                        "othersource", WIKITEXT_LINE_SEPARATOR.join(parts), showkey=True
                    )
                    generated_infobox = str(nt)

            generated_infobox = self._merge_missing_params_text(
                generated_infobox, merge
            )

        except Exception as e:
            logger.error(
                f"Unexpected error merging manual fields: {e}",
                exc_info=True,
            )

        return generated_infobox

    def _find_item_infobox(self, page_text: str) -> tuple[Any, Any | None]:
        """Find first item infobox template in page."""
        names = [
            "Weapon",
            "Armor",
            "Auras",
            "Ability Books",
            "Ability_Books",
            "Consumable",
            "Mold",
            "Item",
        ]
        code = mw_parse(page_text)
        from erenshor.shared.wiki_parser import find_templates

        templates = find_templates(code, names)
        return code, templates[0] if templates else None

    def _extract_params(self, template: Any) -> dict[str, str]:
        """Extract template parameters as dict."""
        from erenshor.shared.wiki_parser import template_params

        return template_params(template)

    def _merge_missing_params_text(self, body: str, merge: dict[str, str]) -> str:
        """Replace empty fields with manual values in-place."""
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("|") and "=" in ln:
                parts = ln[1:].split("=", 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                if not value and key in merge and merge[key]:
                    lines[i] = f"|{key}={merge[key]}"

        return "\n".join(lines)
