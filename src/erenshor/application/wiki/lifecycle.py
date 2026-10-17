"""Reviewed lifecycle facts for historical, renamed, and split wiki pages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

import mwparserfromhell

if TYPE_CHECKING:
    from erenshor.application.wiki.chat_knowledge import ChatKnowledge
    from erenshor.infrastructure import content_lifecycle


def with_chat_knowledge(
    lifecycle: content_lifecycle.ContentLifecycle, knowledge: ChatKnowledge
) -> content_lifecycle.ContentLifecycle:
    """Set the chat flag of each unused page whose character chat names without being asked."""
    pages = {
        title: replace(
            page,
            chat=page.state == "unused"
            and page.stable_key is not None
            and any(entry.named_unprompted for entry in knowledge.entries_for_character(page.stable_key)),
        )
        for title, page in lifecycle.pages.items()
    }
    return replace(lifecycle, pages=MappingProxyType(pages))


def render_split_disambiguation(split: content_lifecycle.LifecycleSplit) -> str:
    """Render a former title with links to every current variant."""
    variants = "\n".join(f"* [[{title}]]" for title in split.current_titles)
    return f"{split.old_title} may refer to:\n\n{variants}\n\n__DISAMBIG__\n"


def apply_lifecycle_fields(
    title: str, stable_keys: Sequence[str], content: str, lifecycle: content_lifecycle.ContentLifecycle
) -> str:
    """Add reviewed fields to matching generated article roots, not their prose."""
    fact = lifecycle.pages.get(title)
    former_names = [
        rename.old_title
        for rename in lifecycle.renames.values()
        if rename.current_title == title and rename.stable_key.startswith("item:") and rename.stable_key in stable_keys
    ]
    if fact is None and not former_names:
        return content
    if fact is not None and (fact.stable_key is None or fact.stable_key not in stable_keys):
        raise ValueError(f"{title}: recorded lifecycle identity conflicts with generated page")

    code = mwparserfromhell.parse(content)
    matched_fact = False
    matched_renames: set[str] = set()
    for template in code.filter_templates(recursive=False):
        name = str(template.name).strip()
        if name not in {"Item", "Ability"} or not template.has("stablekey"):
            continue
        key = str(template.get("stablekey").value).strip()
        if fact is not None and key == fact.stable_key:
            matched_fact = True
            template.add("historical_state", fact.state)
            if name == "Ability":
                template.add("historical_thing", fact.thing)
            if fact.update is not None:
                template.add("historical_update", fact.update)
            if fact.date is not None:
                release_date = date.fromisoformat(fact.date)
                template.add(
                    "historical_date",
                    f"{release_date.strftime('%B')} {release_date.day}, {release_date.year}",
                )
            if fact.patch_notes_url is not None:
                template.add("historical_url", fact.patch_notes_url)
        if name == "Item":
            for rename in lifecycle.renames.values():
                if rename.current_title == title and rename.stable_key == key:
                    matched_renames.add(rename.old_title)
                    template.add("aka", rename.old_title)

    if fact is not None and not matched_fact:
        raise ValueError(f"{title}: no generated Item or Ability root matches {fact.stable_key}")
    if set(former_names) != matched_renames:
        raise ValueError(f"{title}: no generated Item root matches recorded rename")
    return str(code)
