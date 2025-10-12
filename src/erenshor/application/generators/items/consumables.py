"""Consumable item generator.

Handles consumable items (disposable items with click effects).
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
from erenshor.shared.text import normalize_wikitext, parse_name_and_id

__all__ = ["ConsumableGenerator"]


logger = logging.getLogger(__name__)


class ConsumableGenerator(ItemGeneratorBase):
    """Generator for consumable items."""

    def generate_consumable_block(
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
        display_type: str,
        others: list[str],
    ) -> RenderedBlock:
        """Generate consumable item block.

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
            display_type: Type display string
            others: Auto-enriched sources

        Returns:
            Rendered block for consumable item
        """
        buy_value = str(item.ItemValue or "") if vendor_sources else ""
        sell_value = str(item.SellValue or "")

        item_effect = ""
        if item.ItemEffectOnClick and item.ItemEffectOnClick.strip():
            parsed = parse_name_and_id(item.ItemEffectOnClick)
            if parsed and len(parsed) == 2:
                effect_name, effect_id = parsed
                if effect_name:
                    from erenshor.domain.entities.page import EntityRef
                    from erenshor.domain.value_objects.entity_type import EntityType

                    entity = EntityRef(
                        entity_type=EntityType.SPELL,
                        db_id=effect_id,
                        db_name=effect_name,
                        resource_name=effect_name,
                    )
                    item_effect = linker.ability_link(entity)

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        consumable_ctx = ItemInfoboxContext(
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
            effects=item_effect,
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
        )

        consumable_rendered = normalize_wikitext(
            render_template("items/item.j2", consumable_ctx)
        )
        return RenderedBlock(
            page_title=page_title,
            block_id=item.ResourceName,
            template_key="Infobox_item_item",
            text=consumable_rendered,
        )
