"""Charm item generator.

Handles charm items (RequiredSlot == 'Charm') with Fancy-charm template.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from erenshor.application.generators.items.base import ItemGeneratorBase
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities import DbItem
from erenshor.infrastructure.templates.contexts import FancyCharmContext
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.text import normalize_wikitext

__all__ = ["CharmGenerator"]


logger = logging.getLogger(__name__)


class CharmGenerator(ItemGeneratorBase):
    """Generator for charm items."""

    def generate_charm_blocks(
        self,
        engine: Engine,
        item: DbItem,
        page_title: str,
        linker: RegistryLinkResolver,
        vendor_sources: list[str],
        drop_sources: list[str],
        quest_sources: list[str],
        related_quests: list[str],
        craft_sources: list[str],
        component_for: list[str],
    ) -> list[RenderedBlock]:
        """Generate charm item blocks with Item infobox and Fancy-charm template.

        Args:
            engine: Database engine
            item: Database item
            page_title: Wiki page title
            linker: Link resolver
            vendor_sources: Vendor source links
            drop_sources: Drop source links
            quest_sources: Quest source links
            related_quests: Related quest links
            craft_sources: Crafting source links
            component_for: Component usage links

        Returns:
            List of rendered blocks for charm item
        """
        from erenshor.infrastructure.templates.contexts import ItemInfoboxContext
        from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR

        blocks: list[RenderedBlock] = []
        buy_value = str(item.ItemValue or "") if vendor_sources else ""
        sell_value = str(item.SellValue or "")

        # Item infobox (source fields only)
        inf_ctx = ItemInfoboxContext(
            block_id=item.ResourceName,
            title=page_title,
            image="",
            imagecaption="",
            type="",
            vendorsource=WIKITEXT_LINE_SEPARATOR.join(vendor_sources)
            if vendor_sources
            else "",
            source=WIKITEXT_LINE_SEPARATOR.join(drop_sources) if drop_sources else "",
            othersource="",
            questsource=WIKITEXT_LINE_SEPARATOR.join(quest_sources)
            if quest_sources
            else "",
            relatedquest=WIKITEXT_LINE_SEPARATOR.join(related_quests)
            if related_quests
            else "",
            craftsource=WIKITEXT_LINE_SEPARATOR.join(craft_sources)
            if craft_sources
            else "",
            componentfor=WIKITEXT_LINE_SEPARATOR.join(component_for) if component_for else "",
            relic="",
            classes="",
            effects="",
            damage="",
            delay="",
            dps="",
            casttime="",
            duration="",
            cooldown="",
            description="",
            buy=buy_value,
            sell=sell_value,
            itemid=item.Id if item.Id is not None else "",
        )

        inf_rendered = normalize_wikitext(
            render_template("items/item.j2", inf_ctx)
        )
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Infobox_item_item",
                text=inf_rendered,
            )
        )
        from erenshor.infrastructure.database.repositories import get_item_stats

        # Get stats for scaling values (charms have tiers but should have same scaling)
        stats = get_item_stats(engine, item.Id)

        # Use first stat row for scaling values (all tiers should have same scaling)
        scaling_stat = stats[0] if stats else None

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        # Get class restrictions
        classes = item.Classes or []

        def has(name: str) -> bool:
            return name in classes

        # Format scaling values (always round to integer)
        def format_scaling(value: float | None) -> str:
            if value is None or value == 0:
                return ""
            return str(round(value))

        charm_ctx = FancyCharmContext(
            block_id=item.ResourceName,
            image=f"[[File:{image_name}.png|80px]]",
            name=page_title,
            description=item.Lore or "",
            strscaling=format_scaling(scaling_stat.StrScaling if scaling_stat else None),
            endscaling=format_scaling(scaling_stat.EndScaling if scaling_stat else None),
            dexscaling=format_scaling(scaling_stat.DexScaling if scaling_stat else None),
            agiscaling=format_scaling(scaling_stat.AgiScaling if scaling_stat else None),
            intscaling=format_scaling(scaling_stat.IntScaling if scaling_stat else None),
            wisscaling=format_scaling(scaling_stat.WisScaling if scaling_stat else None),
            chascaling=format_scaling(scaling_stat.ChaScaling if scaling_stat else None),
            arcanist=("True" if has("Arcanist") else ""),
            duelist=("True" if has("Duelist") else ""),
            druid=("True" if has("Druid") else ""),
            paladin=("True" if has("Paladin") else ""),
            stormcaller=("True" if has("Stormcaller") else ""),
        )

        charm_rendered = normalize_wikitext(
            render_template("items/fancy_charm.j2", charm_ctx)
        )
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Fancy_charm",
                text=charm_rendered,
            )
        )

        return blocks
