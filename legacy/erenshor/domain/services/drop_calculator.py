from __future__ import annotations

from typing import Any, Iterable

from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR

__all__ = ["format_drops"]


def _extract_item_title(entry: str) -> str:
    import re

    m = re.search(r"\{\{\s*ItemLink\s*\|\s*([^\}|]+)", entry)
    return m.group(1).strip() if m else ""


def _extract_ref(entry: str) -> str:
    import re

    m = re.search(r"(<ref[\s\S]*?</ref>)\s*$", entry.strip())
    return m.group(1) if m else ""


def format_drops(
    loot_rows: Iterable[dict[str, Any]],
    link_resolver: RegistryLinkResolver,
    *,
    append_visible_ref: bool = True,
    character_name: str = "",
) -> tuple[str, str]:
    def _format_probability(probability: float) -> str:
        try:
            prob_float = float(probability)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid drop probability for character '{character_name}': {probability!r}"
            ) from e
        # Database stores probabilities as percentages (e.g., 11.48 = 11.48%)
        # Do NOT multiply by 100
        return f"{prob_float:.1f}%"

    def _sort_key(drop_data: dict[str, Any]) -> tuple[float, str]:
        # Descending probability, then ascending item name as tiebreaker
        try:
            probability = float(drop_data.get("DropProbability") or 0.0)
        except (TypeError, ValueError) as e:
            item_name = drop_data.get("ItemName", "<unknown>")
            raise ValueError(
                f"Invalid drop probability for item '{item_name}' (character '{character_name}'): "
                f"{drop_data.get('DropProbability')!r}"
            ) from e
        item_name = (drop_data.get("ItemName") or "").lower()
        return (-probability, item_name)

    # Prepare entries with sort keys
    guaranteed_entries_no_pct: list[tuple[tuple[float, str], str]] = []  # For guaranteeddrops field
    all_entries_with_pct: list[tuple[tuple[float, str], str]] = []  # For droprates field

    for drop_data in loot_rows:
        resource_name = drop_data.get("ResourceName", "") or ""
        item_name = drop_data.get("ItemName", "") or ""
        item_id = drop_data.get("ItemId")

        # Skip if no valid item data
        if not item_name:
            continue

        drop_probability = float(drop_data.get("DropProbability") or 0.0)
        if drop_probability <= 0:
            continue

        probability_text = _format_probability(drop_probability)
        is_guaranteed = drop_data.get("IsGuaranteed")

        # Use link resolver to create ItemLink template
        item_link = link_resolver.item_link(resource_name, item_name, item_id)

        # Build entry with percentage (for droprates field)
        entry_with_pct = item_link
        if probability_text:
            entry_with_pct += f" ({probability_text})"

        # Add refs for special cases
        references: list[str] = []

        # IsVisible ref: if character has item equipped, it drops
        if append_visible_ref and drop_data.get("IsVisible") and character_name:
            references.append(
                f"<ref>If {character_name} has {item_link} equipped, it is guaranteed to drop.</ref>"
            )

        # ItemUnique ref: if item is unique, only one can be held at a time
        if drop_data.get("ItemUnique"):
            references.append(
                f"<ref>If the player is already holding {item_link} in their inventory, another will not drop.</ref>"
            )

        if references:
            entry_with_pct += "".join(references)

        sort_key = _sort_key(drop_data)

        # All items go to droprates with percentage
        all_entries_with_pct.append((sort_key, entry_with_pct))

        # Guaranteed items also go to guaranteeddrops WITHOUT percentage
        if is_guaranteed:
            guaranteed_entries_no_pct.append((sort_key, item_link))

    # Sort by key and deduplicate while preserving order
    def _join_entries(entries: list[tuple[tuple[float, str], str]]) -> str:
        if not entries:
            return ""
        entries.sort(key=lambda entry_tuple: entry_tuple[0])
        seen: set[str] = set()
        output: list[str] = []
        for _, entry_text in entries:
            if entry_text not in seen:
                seen.add(entry_text)
                output.append(entry_text)
        return WIKITEXT_LINE_SEPARATOR.join(output)

    # Only show guaranteeddrops if there are 2+ guaranteed items
    # (single guaranteed drop is obvious from 100% in droprates)
    guaranteed_str = ""
    if len(guaranteed_entries_no_pct) >= 2:
        guaranteed_str = _join_entries(guaranteed_entries_no_pct)

    return guaranteed_str, _join_entries(all_entries_with_pct)
