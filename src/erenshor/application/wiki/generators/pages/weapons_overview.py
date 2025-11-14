"""Weapons overview page generator.

Generates a large sortable table of all weapons with their stats.
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


class WeaponsOverviewPageGenerator(OverviewPageGeneratorBase):
    """Generator for Weapons overview page.

    Creates a large sortable table of all weapons with their stats.
    """

    PAGE_TITLE = "Weapons"

    def get_pages_to_fetch(self) -> list[str]:
        """Return page titles to fetch from wiki.

        Returns:
            List with single entry: ["Weapons"]
        """
        return [self.PAGE_TITLE]

    def generate_pages(self) -> Iterator[GeneratedPage]:
        """Generate Weapons overview page.

        Yields:
            Single GeneratedPage for Weapons overview
        """
        logger.info("Generating Weapons overview page")

        # Query all items
        all_items = self.context.item_repo.get_items_for_wiki_generation()

        # Filter to weapons only
        weapons = [
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
            == "weapon"
        ]

        logger.debug(f"Found {len(weapons)} weapons")

        # Generate table
        wikitext = self._generate_weapons_table(weapons)

        # Create GeneratedPage
        yield GeneratedPage(
            title=self.PAGE_TITLE,
            content=wikitext,
            metadata=PageMetadata(
                summary="Update weapons overview table with latest game data",
                minor=False,
            ),
            stable_keys=[],  # Overview pages don't track specific entities
        )

    def _generate_weapons_table(self, weapons: list[Item]) -> str:
        """Generate wikitable for weapons.

        Args:
            weapons: List of weapon items

        Returns:
            Complete wikitable wikitext
        """
        # Pre-fetch stats for all weapons
        weapon_stats: dict[str, ItemStats | None] = {}
        for weapon in weapons:
            stats_list = self.context.item_repo.get_item_stats(weapon.stable_key)
            # Get Normal quality stats
            base_stats = next(
                (s for s in stats_list if s.quality in ("Normal", "0")),
                None,
            )
            weapon_stats[weapon.stable_key] = base_stats

        # Pre-fetch class restrictions for all weapons
        weapon_classes: dict[str, list[str]] = {}
        for weapon in weapons:
            classes = self.context.item_repo.get_item_classes(weapon.stable_key)
            weapon_classes[weapon.stable_key] = classes

        # Sort weapons
        weapons_sorted = sorted(
            weapons,
            key=lambda w: (
                self._slot_label(w).casefold(),
                self._type_label(w, weapon_stats).casefold(),
                (self.context.resolver.resolve_page_title(w.stable_key) or "").casefold(),
            ),
        )

        # Build table rows
        rows = []

        # Header
        rows.append('{| class="wikitable datatable compact hover" style="font-size: 14px; text-align: center;"')
        rows.extend(
            [
                "!Weapon",
                "!Slot",
                "!Type",
                '!class="numeric"|Level',
                '!class="numeric"|Damage',
                '!class="numeric"|Delay',
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
        for weapon in weapons_sorted:
            stats = weapon_stats.get(weapon.stable_key)
            classes = weapon_classes.get(weapon.stable_key, [])
            self._add_weapon_row(rows, weapon, stats, classes)

        rows.append("|}")

        return "\n".join(rows) + "\n"

    def _slot_label(self, item: Item) -> str:
        """Get display label for weapon slot.

        Args:
            item: Weapon item

        Returns:
            Slot label like "Primary or Secondary - 2-Handed"
        """
        slot = item.required_slot or ""
        if slot == "PrimaryOrSecondary":
            slot = "Primary or Secondary"

        two_handed = item.this_weapon_type in ("TwoHandMelee", "TwoHandStaff")
        if two_handed:
            slot += " - 2-Handed"

        return slot

    def _type_label(
        self,
        item: Item,
        stats_dict: dict[str, ItemStats | None],
    ) -> str:
        """Get weapon type label.

        Args:
            item: Weapon item
            stats_dict: Dict of item stats by stable_key

        Returns:
            Type label like "1H Melee", "Bow", "Shield", etc.
        """
        # Check if shield (no weapon damage)
        if item.shield:
            stats = stats_dict.get(item.stable_key)
            weapon_dmg = stats.weapon_dmg if stats else 0
            if weapon_dmg == 0:
                return "Shield"

        # Check special weapon types
        if item.is_wand:
            return "Wand"
        if item.is_bow:
            return "Bow"

        # Map ThisWeaponType field to label
        weapon_type = item.this_weapon_type or ""
        type_map = {
            "TwoHandBow": "Bow",
            "OneHandDagger": "1H Dagger",
            "OneHandMelee": "1H Melee",
            "TwoHandMelee": "2H Melee",
            "TwoHandStaff": "2H Staff",
        }

        return type_map.get(weapon_type, "")

    def _add_weapon_row(
        self,
        rows: list[str],
        weapon: Item,
        stats: ItemStats | None,
        class_names: list[str],
    ) -> None:
        """Add weapon data row to table.

        Args:
            rows: List of table rows (modified in-place)
            weapon: Weapon item
            stats: Base (Normal quality) stats for weapon
            class_names: List of class names that can equip this weapon
        """
        # Item link
        name = str(self.context.resolver.item_link(weapon.stable_key))

        # Slot and type
        slot = self._slot_label(weapon)
        weapon_type = self._type_label(weapon, {weapon.stable_key: stats})

        # Level, damage, delay
        level = self._format_stat(weapon.item_level)
        dmg = self._format_stat(stats.weapon_dmg if stats else None)
        dly = self._format_stat(weapon.weapon_dly)

        # Stats (all from ItemStats)
        def stat(attr: str) -> str:
            return self._format_stat(getattr(stats, attr) if stats else None)

        # Notes column (procs, effects)
        notes = self._build_weapon_notes(weapon)

        # Classes column - format as wiki links (sorted alphabetically)
        classes = ", ".join(f"[[{cls}]]" for cls in sorted(class_names)) if class_names else ""

        # Add row
        rows.extend(
            [
                "|-",
                f'|style="text-align: left;"|{name}',
                f"|{slot}",
                f"|{weapon_type}",
                f"|{level}",
                f"|{dmg}",
                f"|{dly}",
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

    def _build_weapon_notes(self, weapon: Item) -> str:
        """Build notes column content for weapon.

        Includes:
        - Weapon procs (on attack/bash)
        - Wand effects (on cast)
        - Bow effects (on attack)
        - Worn effects
        - Click effects

        Args:
            weapon: Weapon item

        Returns:
            Notes content with <br> separators
        """
        notes_parts = []

        # Weapon proc
        if weapon.weapon_proc_on_hit_stable_key and weapon.weapon_proc_chance:
            spell_link = str(self.context.resolver.ability_link(weapon.weapon_proc_on_hit_stable_key))
            trigger = "on bash" if weapon.shield else "on attack"
            notes_parts.append(f"{spell_link}, {int(weapon.weapon_proc_chance)}% {trigger}")

        # Wand effect
        if weapon.wand_effect_stable_key and weapon.wand_proc_chance:
            spell_link = str(self.context.resolver.ability_link(weapon.wand_effect_stable_key))
            notes_parts.append(f"{spell_link}, {int(weapon.wand_proc_chance)}% on cast")

        # Bow effect
        if weapon.bow_effect_stable_key and weapon.bow_proc_chance:
            spell_link = str(self.context.resolver.ability_link(weapon.bow_effect_stable_key))
            notes_parts.append(f"{spell_link}, {int(weapon.bow_proc_chance)}% on attack")

        # Worn effect
        if weapon.worn_effect_stable_key:
            spell_link = str(self.context.resolver.ability_link(weapon.worn_effect_stable_key))
            notes_parts.append(f"Worn: {spell_link}")

        # Click effect
        if weapon.item_effect_on_click_stable_key:
            spell_link = str(self.context.resolver.ability_link(weapon.item_effect_on_click_stable_key))
            notes_parts.append(f"On click: {spell_link}")

        return "<br>".join(notes_parts)
