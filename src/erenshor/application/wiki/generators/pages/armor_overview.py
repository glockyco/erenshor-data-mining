"""Armor overview page generator.

Generates a large sortable table of all armor with their stats.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.base import GeneratedPage, PageMetadata
from erenshor.application.wiki.generators.pages.overview_base import (
    OverviewPageGeneratorBase,
)
from erenshor.registry.item_classifier import classify_item_kind

if TYPE_CHECKING:
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats


class ArmorOverviewPageGenerator(OverviewPageGeneratorBase):
    """Generator for Armor overview page.

    Creates a large sortable table of all armor with their stats.
    """

    PAGE_TITLE = "Armor"

    def get_pages_to_fetch(self) -> list[str]:
        """Return page titles to fetch from wiki.

        Returns:
            List with single entry: ["Armor"]
        """
        return [self.PAGE_TITLE]

    def generate_pages(self) -> Iterator[GeneratedPage]:
        """Generate Armor overview page.

        Yields:
            Single GeneratedPage for Armor overview
        """
        logger.info("Generating Armor overview page")

        # Query all items
        all_items = self.context.item_repo.get_items_for_wiki_generation()

        # Filter to armor only
        armor_items = [
            item
            for item in all_items
            if classify_item_kind(
                required_slot=item.required_slot,
                teach_spell=item.teach_spell_stable_key,
                teach_skill=item.teach_skill_stable_key,
                template_flag=item.template,
                click_effect=item.item_effect_on_click_stable_key,
                disposable=bool(item.disposable),
            )
            == "armor"
        ]

        logger.debug(f"Found {len(armor_items)} armor items")

        # Generate table
        wikitext = self._generate_armor_table(armor_items)

        # Create GeneratedPage
        yield GeneratedPage(
            title=self.PAGE_TITLE,
            content=wikitext,
            metadata=PageMetadata(
                summary="Update armor overview table with latest game data",
                minor=False,
            ),
            stable_keys=[],  # Overview pages don't track specific entities
        )

    def _generate_armor_table(self, armor_items: list[Item]) -> str:
        """Generate wikitable for armor.

        Args:
            armor_items: List of armor items

        Returns:
            Complete wikitable wikitext
        """
        # Pre-fetch stats for all armor
        armor_stats: dict[str, ItemStats | None] = {}
        for armor in armor_items:
            stats_list = self.context.item_repo.get_item_stats(armor.stable_key)
            # Get Normal quality stats
            base_stats = next(
                (s for s in stats_list if s.quality in ("Normal", "0")),
                None,
            )
            armor_stats[armor.stable_key] = base_stats

        # Pre-fetch class restrictions for all armor
        armor_classes: dict[str, list[str]] = {}
        for armor in armor_items:
            classes = self.context.item_repo.get_item_classes(armor.stable_key)
            armor_classes[armor.stable_key] = classes

        # Sort armor (by slot, then name)
        armor_sorted = sorted(
            armor_items,
            key=lambda a: (
                (a.required_slot or "").casefold(),
                (self.context.resolver.resolve_page_title(a.stable_key) or "").casefold(),
            ),
        )

        # Build table rows
        rows = []

        # Header
        rows.append('{| class="wikitable datatable compact hover" style="font-size: 14px; text-align: center;"')
        rows.extend(
            [
                "!Armor",
                "!Slot",
                '!class="numeric"|Level',
                '!class="numeric"|HP',
                '!class="numeric"|Mana',
                '!class="numeric"|AC',
                '!class="numeric"|Str',
                '!class="numeric"|End',
                '!class="numeric"|Dex',
                '!class="numeric"|Agi',
                '!class="numeric"|Int',
                '!class="numeric"|Wis',
                '!class="numeric"|Cha',
                '!class="numeric"|Res',
                '!class="numeric"|MR',
                '!class="numeric"|PR',
                '!class="numeric"|ER',
                '!class="numeric"|VR',
                "!Notes",
                "![[Classes]]",
            ]
        )

        # Data rows
        for armor in armor_sorted:
            stats = armor_stats.get(armor.stable_key)
            classes = armor_classes.get(armor.stable_key, [])
            self._add_armor_row(rows, armor, stats, classes)

        rows.append("|}")

        return "\n".join(rows) + "\n"

    def _add_armor_row(
        self,
        rows: list[str],
        armor: Item,
        stats: ItemStats | None,
        class_names: list[str],
    ) -> None:
        """Add armor data row to table.

        Args:
            rows: List of table rows (modified in-place)
            armor: Armor item
            stats: Base (Normal quality) stats for armor
            class_names: List of class names that can equip this armor
        """
        # Item link
        name = str(self.context.resolver.item_link(armor.stable_key))

        # Slot
        slot = armor.required_slot or ""

        # Level
        level = self._format_stat(armor.item_level)

        # Stats (all from ItemStats)
        def stat(attr: str) -> str:
            return self._format_stat(getattr(stats, attr) if stats else None)

        # Notes column (worn effects, click effects, bracer procs)
        notes = self._build_armor_notes(armor)

        # Classes column - map to display names (already sorted by map_class_list)
        display_class_names = self.context.class_display.map_class_list(class_names)
        classes = ", ".join(f"[[{cls}]]" for cls in display_class_names) if display_class_names else ""

        # Add row
        rows.extend(
            [
                "|-",
                f'|style="text-align: left;"|{name}',
                f"|{slot}",
                f"|{level}",
                f"|{stat('hp')}",
                f"|{stat('mana')}",
                f"|{stat('ac')}",
                f"|{stat('str_')}",
                f"|{stat('end_')}",
                f"|{stat('dex')}",
                f"|{stat('agi')}",
                f"|{stat('int_')}",
                f"|{stat('wis')}",
                f"|{stat('cha')}",
                f"|{stat('res')}",
                f"|{stat('mr')}",
                f"|{stat('pr')}",
                f"|{stat('er')}",
                f"|{stat('vr')}",
                f"|{notes}",
                f"|{classes}",
            ]
        )

    def _build_armor_notes(self, armor: Item) -> str:
        """Build notes column content for armor.

        Includes:
        - Worn effects
        - Click effects
        - Bracer procs (on cast)

        Args:
            armor: Armor item

        Returns:
            Notes content with <br> separators
        """
        notes_parts = []

        # Worn effect
        if armor.worn_effect_stable_key:
            spell_link = str(self.context.resolver.ability_link(armor.worn_effect_stable_key))
            notes_parts.append(f"Worn: {spell_link}")

        # Click effect
        if armor.item_effect_on_click_stable_key:
            spell_link = str(self.context.resolver.ability_link(armor.item_effect_on_click_stable_key))
            notes_parts.append(f"On click: {spell_link}")

        # Bracer proc
        if armor.required_slot == "Bracer" and armor.weapon_proc_on_hit_stable_key and armor.weapon_proc_chance:
            spell_link = str(self.context.resolver.ability_link(armor.weapon_proc_on_hit_stable_key))
            notes_parts.append(f"{spell_link}, {int(armor.weapon_proc_chance)}% on cast")

        return "<br>".join(notes_parts)
