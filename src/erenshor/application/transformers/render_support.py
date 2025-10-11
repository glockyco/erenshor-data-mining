from __future__ import annotations

from typing import Dict, List, Tuple

from erenshor.shared.text import normalize_wikitext

__all__ = ["extract_canonical_item_snippets"]


def extract_canonical_item_snippets(blocks: List[Tuple[str, str]]) -> Dict[str, str]:
    """From a list of (template_key, text) pairs, return canonical bodies without markers.

    Keys returned:
      - infobox: one of Infobox_item_weapon/armor/aura/ability_book/consumable/mold/item
      - table: Fancy_<weapon|armor>_table
      - tiers: Fancy_<weapon|armor>_tier_0/1/2
      - charm: Fancy_charm template
    """
    out: Dict[str, str] = {}
    for key, text in blocks:
        body = normalize_wikitext(text)
        if key.startswith("Infobox_item_") or key == "Infobox_item":
            out["infobox"] = body
        elif key == "Fancy_weapon_table":
            out["table_weapon"] = body
        elif key == "Fancy_armor_table":
            out["table_armor"] = body
        elif key.startswith("Fancy_weapon_template_tier_"):
            tier = key.rsplit("_", 1)[-1]
            out[f"tier_weapon_{tier}"] = body
        elif key.startswith("Fancy_armor_template_tier_"):
            tier = key.rsplit("_", 1)[-1]
            out[f"tier_armor_{tier}"] = body
        elif key == "Fancy_charm":
            out["charm"] = body
    return out
