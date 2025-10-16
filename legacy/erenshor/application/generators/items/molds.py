"""Mold item generator.

Handles mold items (Template == 1) which are crafting recipe items.
"""

from __future__ import annotations

import logging

from erenshor.application.generators.items.base import ItemGeneratorBase
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities import DbItem
from erenshor.infrastructure.templates.contexts import ItemInfoboxContext
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.text import normalize_wikitext

__all__ = ["MoldGenerator"]


logger = logging.getLogger(__name__)


class MoldGenerator(ItemGeneratorBase):
    """Generator for mold items."""

    def generate_mold_block(
        self,
        item: DbItem,
        page_title: str,
        linker: RegistryLinkResolver,
        vendor_sources: list[str],
        drop_sources: list[str],
        quest_sources: list[str],
        related_quests: list[str],
        craft_sources: list[str],
        comp_for: list[str],
        crafting_results: list[str],
        recipe_ings: list[str],
        display_type: str,
        others: list[str],
    ) -> RenderedBlock:
        """Generate mold item block.

        Args:
            item: Database item
            page_title: Wiki page title
            linker: Link resolver
            vendor_sources: Vendor source links
            drop_sources: Drop source links
            quest_sources: Quest source links
            related_quests: Related quest links
            craft_sources: Crafting source links
            comp_for: Component usage links
            crafting_results: Crafting result links
            recipe_ings: Recipe ingredient links
            display_type: Type display string
            others: Auto-enriched sources

        Returns:
            Rendered block for mold item
        """
        buy_value = str(item.ItemValue or "") if vendor_sources else ""
        sell_value = str(item.SellValue or "")

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        mold_ctx = ItemInfoboxContext(
            block_id=item.ResourceName,
            title=page_title,
            image=f"[[File:{image_name}.png]]",
            imagecaption="",
            type=display_type,
            vendorsource=WIKITEXT_LINE_SEPARATOR.join(vendor_sources)
            if vendor_sources
            else "",
            source=WIKITEXT_LINE_SEPARATOR.join(drop_sources) if drop_sources else "",
            othersource=WIKITEXT_LINE_SEPARATOR.join(others) if others else "",
            questsource=WIKITEXT_LINE_SEPARATOR.join(quest_sources)
            if quest_sources
            else "",
            relatedquest=WIKITEXT_LINE_SEPARATOR.join(related_quests)
            if related_quests
            else "",
            craftsource=WIKITEXT_LINE_SEPARATOR.join(craft_sources)
            if craft_sources
            else "",
            componentfor=WIKITEXT_LINE_SEPARATOR.join(comp_for) if comp_for else "",
            relic="True" if item.Relic else "",
            classes=", ".join(item.Classes) if item.Classes else "",
            effects="",
            damage="",
            delay="",
            dps="",
            casttime="",
            duration="",
            cooldown="",
            description=item.Lore or "",
            buy=buy_value,
            sell=sell_value,
            itemid=item.Id if item.Id is not None else "",
            crafting=WIKITEXT_LINE_SEPARATOR.join(crafting_results)
            if crafting_results
            else "",
            recipe=WIKITEXT_LINE_SEPARATOR.join(recipe_ings) if recipe_ings else "",
        )

        mold_rendered = normalize_wikitext(render_template("items/mold.j2", mold_ctx))
        return RenderedBlock(
            page_title=page_title,
            block_id=item.ResourceName,
            template_key="Infobox_item_mold",
            text=mold_rendered,
        )
