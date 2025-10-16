"""Weapon and armor item generators with fancy tables.

Handles weapons and armor items that require both item infoboxes
and fancy tables with 3 tiers (Normal, Blessed, Godly).
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from erenshor.application.generators.items.base import ItemGeneratorBase
from erenshor.application.generators.items.stats import (
    ProcExtractor,
    validate_and_normalize_tiers,
    weapon_type_display,
)
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities import DbItem
from erenshor.infrastructure.templates.contexts import (
    FancyArmorColumn,
    FancyArmorTableContext,
    FancyArmorTemplateContext,
    FancyWeaponColumn,
    FancyWeaponTableContext,
    FancyWeaponTemplateContext,
    ItemInfoboxContext,
)
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import (
    INFOBOX_IMAGE_SIZE,
    LONG_NAME_FONT_SIZE,
    LONG_NAME_THRESHOLD,
    REQUIRED_TIER_COUNT,
    TIER_ORDER_MAP,
    TIER_SORT_DEFAULT,
    TIER_STRING_MAP,
    WEAPON_DELAY_PRECISION,
    WIKITEXT_LINE_SEPARATOR,
)
from erenshor.shared.text import normalize_wikitext, to_zero

__all__ = ["WeaponArmorGenerator"]


logger = logging.getLogger(__name__)


class WeaponArmorGenerator(ItemGeneratorBase):
    """Generator for weapons and armor with fancy tables.

    Handles both weapons and armor, producing:
    1. Item infobox (source fields only)
    2. Fancy table with 3 tiers (Normal, Blessed, Godly)
    3. Individual tier templates
    """

    def __init__(self) -> None:
        """Initialize weapon/armor generator."""
        super().__init__()
        self._proc_extractor = ProcExtractor()

    def generate_weapon_blocks(
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
        comp_for: list[str],
        crafting_results: list[str],
        recipe_ings: list[str],
    ) -> list[RenderedBlock]:
        """Generate weapon blocks (infobox + fancy tables).

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
            comp_for: Component usage links
            crafting_results: Crafting result links
            recipe_ings: Recipe ingredient links

        Returns:
            List of rendered blocks
        """
        from erenshor.infrastructure.database.repositories import get_item_stats

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
            componentfor=WIKITEXT_LINE_SEPARATOR.join(comp_for) if comp_for else "",
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
            crafting=WIKITEXT_LINE_SEPARATOR.join(crafting_results)
            if crafting_results
            else "",
            recipe=WIKITEXT_LINE_SEPARATOR.join(recipe_ings) if recipe_ings else "",
        )

        inf_rendered = normalize_wikitext(render_template("items/item.j2", inf_ctx))
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Infobox_item_item",
                text=inf_rendered,
            )
        )

        # Get stats and validate tiers
        stats = get_item_stats(engine, item.Id)
        stats.sort(key=lambda r: TIER_ORDER_MAP.get(r.Quality, TIER_SORT_DEFAULT))
        stats = validate_and_normalize_tiers(stats, item.Id, item.ItemName, "weapon")

        # Extract proc info
        proc_name, proc_desc, proc_chance, proc_style = (
            self._proc_extractor.extract_weapon_proc(engine, item, linker)
        )

        zero_if_empty = to_zero
        classes = item.Classes or []

        def has(name: str) -> bool:
            return name in classes

        delay_str = (
            f"{item.WeaponDly:.{WEAPON_DELAY_PRECISION}f}"
            if (item.WeaponDly and item.WeaponDly > 0)
            else ""
        )

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        cols: list[FancyWeaponColumn] = []

        for stat_row in stats[:REQUIRED_TIER_COUNT]:
            q = stat_row.Quality
            tier_str = TIER_STRING_MAP.get(q, q if isinstance(q, str) else "")

            display_name = (
                f'<span style="font-size:{LONG_NAME_FONT_SIZE}">{page_title}</span>'
                if len(item.ItemName) > LONG_NAME_THRESHOLD
                else page_title
            )
            cols.append(
                FancyWeaponColumn(
                    image=f"[[File:{image_name}.png|{INFOBOX_IMAGE_SIZE}px]]",
                    name=display_name,
                    type=weapon_type_display(
                        item.RequiredSlot or "", item.ThisWeaponType or ""
                    ),
                    str=zero_if_empty(stat_row.Str),
                    end=zero_if_empty(stat_row.End),
                    dex=zero_if_empty(stat_row.Dex),
                    agi=zero_if_empty(stat_row.Agi),
                    int=zero_if_empty(stat_row.Int),
                    wis=zero_if_empty(stat_row.Wis),
                    cha=zero_if_empty(stat_row.Cha),
                    res=zero_if_empty(stat_row.Res),
                    damage=(
                        ""
                        if not stat_row.WeaponDmg
                        else zero_if_empty(stat_row.WeaponDmg)
                    ),
                    delay=("" if not stat_row.WeaponDmg else delay_str),
                    health=zero_if_empty(stat_row.HP),
                    mana=zero_if_empty(stat_row.Mana),
                    armor=zero_if_empty(stat_row.AC),
                    magic=zero_if_empty(stat_row.MR),
                    poison=zero_if_empty(stat_row.PR),
                    elemental=zero_if_empty(stat_row.ER),
                    void=zero_if_empty(stat_row.VR),
                    description=(item.Lore or ""),
                    arcanist=("True" if has("Arcanist") else ""),
                    duelist=("True" if has("Duelist") else ""),
                    druid=("True" if has("Druid") else ""),
                    paladin=("True" if has("Paladin") else ""),
                    stormcaller=("True" if has("Stormcaller") else ""),
                    relic=("True" if item.Relic else ""),
                    proc_name=proc_name,
                    proc_desc=proc_desc,
                    proc_chance=proc_chance,
                    proc_style=proc_style,
                    tier=tier_str,
                )
            )

            fancy_ctx = FancyWeaponTemplateContext(
                block_id=f"{item.ResourceName}:{tier_str}",
                image=f"[[File:{image_name}.png|{INFOBOX_IMAGE_SIZE}px]]",
                name=display_name,
                type=weapon_type_display(
                    item.RequiredSlot or "", item.ThisWeaponType or ""
                ),
                str=zero_if_empty(stat_row.Str),
                end=zero_if_empty(stat_row.End),
                dex=zero_if_empty(stat_row.Dex),
                agi=zero_if_empty(stat_row.Agi),
                int=zero_if_empty(stat_row.Int),
                wis=zero_if_empty(stat_row.Wis),
                cha=zero_if_empty(stat_row.Cha),
                res=zero_if_empty(stat_row.Res),
                damage=(
                    "" if not stat_row.WeaponDmg else zero_if_empty(stat_row.WeaponDmg)
                ),
                delay=("" if not stat_row.WeaponDmg else delay_str),
                health=zero_if_empty(stat_row.HP),
                mana=zero_if_empty(stat_row.Mana),
                armor=zero_if_empty(stat_row.AC),
                magic=zero_if_empty(stat_row.MR),
                poison=zero_if_empty(stat_row.PR),
                elemental=zero_if_empty(stat_row.ER),
                void=zero_if_empty(stat_row.VR),
                description=(item.Lore or ""),
                arcanist=("True" if has("Arcanist") else ""),
                duelist=("True" if has("Duelist") else ""),
                druid=("True" if has("Druid") else ""),
                paladin=("True" if has("Paladin") else ""),
                stormcaller=("True" if has("Stormcaller") else ""),
                relic=("True" if item.Relic else ""),
                proc_name=proc_name,
                proc_desc=proc_desc,
                proc_chance=proc_chance,
                proc_style=proc_style,
                tier=tier_str,
            )

            fancy_rendered = normalize_wikitext(
                render_template("items/fancy_weapon_template.j2", fancy_ctx)
            )
            blocks.append(
                RenderedBlock(
                    page_title=page_title,
                    block_id=f"{item.ResourceName}:{tier_str}",
                    template_key=f"Fancy_weapon_template_tier_{tier_str}",
                    text=fancy_rendered,
                )
            )

        table_ctx = FancyWeaponTableContext(block_id=item.ResourceName, columns=cols)
        table_rendered = normalize_wikitext(
            render_template("items/fancy_weapon_table.j2", table_ctx)
        )
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Fancy_weapon_table",
                text=table_rendered,
            )
        )

        return blocks

    def generate_armor_blocks(
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
        comp_for: list[str],
        crafting_results: list[str],
        recipe_ings: list[str],
    ) -> list[RenderedBlock]:
        """Generate armor blocks (infobox + fancy tables).

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
            comp_for: Component usage links
            crafting_results: Crafting result links
            recipe_ings: Recipe ingredient links

        Returns:
            List of rendered blocks
        """
        from erenshor.infrastructure.database.repositories import get_item_stats

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
            componentfor=WIKITEXT_LINE_SEPARATOR.join(comp_for) if comp_for else "",
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
            crafting=WIKITEXT_LINE_SEPARATOR.join(crafting_results)
            if crafting_results
            else "",
            recipe=WIKITEXT_LINE_SEPARATOR.join(recipe_ings) if recipe_ings else "",
        )

        inf_rendered = normalize_wikitext(render_template("items/item.j2", inf_ctx))
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Infobox_item_item",
                text=inf_rendered,
            )
        )

        # Get stats and validate tiers
        stats = get_item_stats(engine, item.Id)
        stats.sort(key=lambda r: TIER_ORDER_MAP.get(r.Quality, TIER_SORT_DEFAULT))
        stats = validate_and_normalize_tiers(stats, item.Id, item.ItemName, "armor")

        zero_if_empty = to_zero
        classes = item.Classes or []

        def has(name: str) -> bool:
            return name in classes

        # Extract proc info once (same for all tiers)
        proc_name, proc_desc, proc_chance, proc_style = (
            self._proc_extractor.extract_armor_proc(engine, item, linker)
        )

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        cols: list[FancyArmorColumn] = []

        for stat_row in stats[:REQUIRED_TIER_COUNT]:
            q = stat_row.Quality
            tier_str = TIER_STRING_MAP.get(q, q if isinstance(q, str) else "")

            display_name = (
                f'<span style="font-size:{LONG_NAME_FONT_SIZE}">{page_title}</span>'
                if len(item.ItemName) > LONG_NAME_THRESHOLD
                else page_title
            )
            cols.append(
                FancyArmorColumn(
                    image=f"[[File:{image_name}.png|{INFOBOX_IMAGE_SIZE}px]]",
                    name=display_name,
                    type="",
                    slot=(item.RequiredSlot or ""),
                    tier=tier_str,
                    str=zero_if_empty(stat_row.Str),
                    end=zero_if_empty(stat_row.End),
                    dex=zero_if_empty(stat_row.Dex),
                    agi=zero_if_empty(stat_row.Agi),
                    int=zero_if_empty(stat_row.Int),
                    wis=zero_if_empty(stat_row.Wis),
                    cha=zero_if_empty(stat_row.Cha),
                    res=zero_if_empty(stat_row.Res),
                    health=zero_if_empty(stat_row.HP),
                    mana=zero_if_empty(stat_row.Mana),
                    armor=zero_if_empty(stat_row.AC),
                    magic=zero_if_empty(stat_row.MR),
                    poison=zero_if_empty(stat_row.PR),
                    elemental=zero_if_empty(stat_row.ER),
                    void=zero_if_empty(stat_row.VR),
                    description=(item.Lore or ""),
                    arcanist=("True" if has("Arcanist") else ""),
                    duelist=("True" if has("Duelist") else ""),
                    druid=("True" if has("Druid") else ""),
                    paladin=("True" if has("Paladin") else ""),
                    stormcaller=("True" if has("Stormcaller") else ""),
                    relic=("True" if item.Relic else ""),
                    proc_name=proc_name,
                    proc_desc=proc_desc,
                    proc_chance=proc_chance,
                    proc_style=proc_style,
                )
            )

            fancy_ctx = FancyArmorTemplateContext(
                block_id=f"{item.ResourceName}:{tier_str}",
                image=f"[[File:{image_name}.png|{INFOBOX_IMAGE_SIZE}px]]",
                name=display_name,
                type="",
                slot=(item.RequiredSlot or ""),
                str=zero_if_empty(stat_row.Str),
                end=zero_if_empty(stat_row.End),
                dex=zero_if_empty(stat_row.Dex),
                agi=zero_if_empty(stat_row.Agi),
                int=zero_if_empty(stat_row.Int),
                wis=zero_if_empty(stat_row.Wis),
                cha=zero_if_empty(stat_row.Cha),
                res=zero_if_empty(stat_row.Res),
                health=zero_if_empty(stat_row.HP),
                mana=zero_if_empty(stat_row.Mana),
                armor=zero_if_empty(stat_row.AC),
                magic=zero_if_empty(stat_row.MR),
                poison=zero_if_empty(stat_row.PR),
                elemental=zero_if_empty(stat_row.ER),
                void=zero_if_empty(stat_row.VR),
                description=(item.Lore or ""),
                arcanist=("True" if has("Arcanist") else ""),
                duelist=("True" if has("Duelist") else ""),
                druid=("True" if has("Druid") else ""),
                paladin=("True" if has("Paladin") else ""),
                stormcaller=("True" if has("Stormcaller") else ""),
                relic=("True" if item.Relic else ""),
                proc_name=proc_name,
                proc_desc=proc_desc,
                proc_chance=proc_chance,
                proc_style=proc_style,
                tier=tier_str,
            )

            fancy_rendered = normalize_wikitext(
                render_template("items/fancy_armor_template.j2", fancy_ctx)
            )
            blocks.append(
                RenderedBlock(
                    page_title=page_title,
                    block_id=f"{item.ResourceName}:{tier_str}",
                    template_key=f"Fancy_armor_template_tier_{tier_str}",
                    text=fancy_rendered,
                )
            )

        table_ctx = FancyArmorTableContext(block_id=item.ResourceName, columns=cols)
        table_rendered = normalize_wikitext(
            render_template("items/fancy_armor_table.j2", table_ctx)
        )
        blocks.append(
            RenderedBlock(
                page_title=page_title,
                block_id=item.ResourceName,
                template_key="Fancy_armor_table",
                text=table_rendered,
            )
        )

        return blocks
