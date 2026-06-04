"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- All items: {{Item}} template + {{ItemTooltip|stablekey=...}}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import safe_str
from erenshor.application.wiki.generators.item_type_display import build_item_types
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind
from erenshor.domain.value_objects.wiki_link import AbilityLink

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item


class ItemSectionGenerator(SectionGeneratorBase):
    """Generator for item wiki sections.

    Generates template wikitext for a SINGLE item entity. All name/page resolution
    uses direct entity attribute access and pre-built WikiLink objects from
    SourceInfo — no resolver.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self) -> None:
        super().__init__()

    def generate_template(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate template wikitext for a single item."""
        item = enriched.item
        logger.debug(f"Generating template for item: {item.item_name} (kind: {self._classify(item)})")

        kind = self._classify(item)
        if kind == ItemKind.WEAPON and not enriched.stats:
            raise ValueError(
                f"Weapon '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )
        if kind == ItemKind.ARMOR and not enriched.stats:
            raise ValueError(
                f"Armor '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )

        template_wikitext = self._generate_tooltip_page(enriched)
        return self.normalize_wikitext(template_wikitext)

    def _classify(self, item: Item) -> ItemKind:
        return classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable),
        )

    def _generate_tooltip_page(self, enriched: EnrichedItemData) -> str:
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)
        return f"{item_template}\n\n{{{{ItemTooltip|stablekey={enriched.item.stable_key}}}}}"

    def _build_item_infobox_context(self, enriched: EnrichedItemData) -> dict[str, str]:
        """Build context for {{Item}} infobox template."""
        item = enriched.item
        kind = self._classify(item)

        quest_requirement_links = enriched.sources.quest_requirements if enriched.sources else []
        component_for_links = enriched.sources.component_for if enriched.sources else []

        # build_item_types needs string lists; pass display names
        quest_req_strs = [link.display_name for link in quest_requirement_links]
        component_for_strs = [link.display_name for link in component_for_links]

        item_type = build_item_types(
            item=item,
            item_kind=kind,
            quest_requirements=quest_req_strs,
            component_for=component_for_strs,
        )

        display_name = item.display_name or item.item_name or ""

        vendor_sources = self._format_vendor_sources(enriched)
        drop_sources = self._format_drop_sources(enriched)
        quest_rewards_str, quest_requirements_str = self._format_quest_sources(enriched)
        craft_sources, component_for_str = self._format_crafting_sources(enriched)

        # Taught spell link — use AbilityLink-style wikitext directly
        taughtspell = ""
        if item.teach_spell_stable_key and enriched.taught_spell:
            sp = enriched.taught_spell
            taughtspell = str(
                AbilityLink(
                    page_title=sp.wiki_page_name,
                    display_name=sp.display_name or sp.spell_name or "",
                    image_name=sp.image_name,
                )
            )

        # Taught skill link
        taughtskill = ""
        if item.teach_skill_stable_key and enriched.taught_skill:
            sk = enriched.taught_skill
            taughtskill = str(
                AbilityLink(
                    page_title=sk.wiki_page_name,
                    display_name=sk.display_name or sk.skill_name or "",
                    image_name=sk.image_name,
                )
            )

        guaranteed_drops = self._format_guaranteed_drops(enriched)
        drop_rates = self._format_drop_rates(enriched)

        return {
            "title": display_name,
            "type": item_type,
            "vendorsource": vendor_sources,
            "source": drop_sources,
            "othersource": "",
            "questsource": quest_rewards_str,
            "relatedquest": quest_requirements_str,
            "craftsource": craft_sources,
            "componentfor": component_for_str,
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "taughtspell": taughtspell,
            "taughtskill": taughtskill,
            "guaranteeddrops": guaranteed_drops,
            "droprates": drop_rates,
        }

    def _format_vendor_sources(self, enriched: EnrichedItemData) -> str:
        """Format vendor sources from pre-built CharacterLink objects."""
        if not enriched.sources or not enriched.sources.vendors:
            return ""
        visible = [link for link in enriched.sources.vendors if link.page_title is not None]
        visible.sort()
        seen: set[str] = set()
        result = []
        for link in visible:
            s = str(link)
            if s not in seen:
                seen.add(s)
                result.append(s)
        return "<br>".join(result)

    def _format_drop_sources(self, enriched: EnrichedItemData) -> str:
        """Format drop sources from pre-built WikiLink objects with probabilities."""
        if not enriched.sources or not enriched.sources.drops:
            return ""
        drop_data = [(link, prob) for link, prob in enriched.sources.drops if link.page_title is not None]
        drop_data.sort(key=lambda x: (-x[1], x[0]))
        seen: set[tuple[str, float]] = set()
        result = []
        for link, probability in drop_data:
            key = (str(link), probability)
            if key not in seen:
                seen.add(key)
                result.append(f"{link!s} ({probability:.1f}%)")
        return "<br>".join(result)

    def _format_quest_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format quest reward and requirement sources from pre-built QuestLink objects."""
        if not enriched.sources:
            return ("", "")

        reward_links = [link for link in enriched.sources.quest_rewards if link.page_title is not None]
        reward_links.sort()
        seen_r: set[str] = set()
        rewards_result = []
        for link in reward_links:
            s = str(link)
            if s not in seen_r:
                seen_r.add(s)
                rewards_result.append(s)

        req_links = [link for link in enriched.sources.quest_requirements if link.page_title is not None]
        req_links.sort()
        seen_q: set[str] = set()
        reqs_result = []
        for link in req_links:
            s = str(link)
            if s not in seen_q:
                seen_q.add(s)
                reqs_result.append(s)

        return ("<br>".join(rewards_result), "<br>".join(reqs_result))

    def _format_crafting_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format crafting sources from pre-built ItemLink tuples."""
        if not enriched.sources:
            return ("", "")
        craft_links = [f"{qty}x {link!s}" for link, qty in enriched.sources.craft_recipe]
        component_links = [str(link) for link in enriched.sources.component_for]
        return ("<br>".join(craft_links), "<br>".join(component_links))

    def _format_guaranteed_drops(self, enriched: EnrichedItemData) -> str:
        """Format guaranteed drop pool from pre-built ItemLink objects."""
        if not enriched.sources or not enriched.sources.item_drops:
            return ""
        items_with_names = [
            (link.display_name.lower(), str(link))
            for link, _ in enriched.sources.item_drops
            if link.page_title is not None
        ]
        items_with_names.sort(key=lambda x: x[0])
        return "<br>".join(link for _, link in items_with_names)

    def _format_drop_rates(self, enriched: EnrichedItemData) -> str:
        """Format drop rates from pre-built ItemLink objects with probabilities."""
        if not enriched.sources or not enriched.sources.item_drops:
            return ""
        links = [
            f"{link!s} ({probability:.0f}%)"
            for link, probability in enriched.sources.item_drops
            if link.page_title is not None
        ]
        return "<br>".join(links)
