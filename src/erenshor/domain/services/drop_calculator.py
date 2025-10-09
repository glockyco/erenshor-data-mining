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
        except Exception:
            return ""
        return (
            f"{prob_float * 100:.1f}%"
            if 0.0 <= prob_float <= 1.0
            else f"{prob_float:.1f}%"
        )

    def _sort_key(drop_data: dict[str, Any]) -> tuple[float, str]:
        # Descending probability, then ascending item name as tiebreaker
        try:
            probability = float(drop_data.get("DropProbability") or 0.0)
        except Exception:
            probability = 0.0
        item_name = (drop_data.get("ItemName") or "").lower()
        return (-probability, item_name)

    # Prepare entries with sort keys
    guaranteed_entries: list[tuple[tuple[float, str], str]] = []
    regular_entries: list[tuple[tuple[float, str], str]] = []

    for drop_data in loot_rows:
        title = link_resolver.resolve_item_title(
            drop_data.get("ResourceName", "") or "",
            drop_data.get("ItemName", "") or "",
            drop_data.get("ItemId"),
        )
        if not title:
            continue

        drop_probability = float(drop_data.get("DropProbability") or 0.0)
        if drop_probability <= 0:
            continue

        probability_text = _format_probability(drop_probability)
        entry = f"{{{{ItemLink|{title}}}}}"
        if probability_text:
            entry += f" ({probability_text})"
        # Non-exclusive refs; suppress for IsActual
        if not drop_data.get("IsActual"):
            references: list[str] = []
            if append_visible_ref and drop_data.get("IsVisible") and character_name:
                references.append(
                    f"<ref>If {character_name} has {{{{ItemLink|{title}}}}} equipped, it is guaranteed to drop.</ref>"
                )
            if drop_data.get("IsUnique"):
                references.append(
                    f"<ref>If the player is already holding {{{{ItemLink|{title}}}}} in their inventory, another will not drop.</ref>"
                )
            if references:
                entry += "".join(references)

        sort_key = _sort_key(drop_data)
        if drop_data.get("IsGuaranteed"):
            guaranteed_entries.append((sort_key, entry))
        else:
            regular_entries.append((sort_key, entry))

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

    return _join_entries(guaranteed_entries), _join_entries(regular_entries)
