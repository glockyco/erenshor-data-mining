"""Overview content generator.

Generates wiki content for overview pages (Weapons and Armor) from the database,
yielding one overview page at a time.
"""

from __future__ import annotations

from typing import Any, Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import GeneratedContent
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.services.item_classifier import classify_item_kind
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.database.repositories import (
    get_item_stats,
    get_items,
    get_spell_by_id,
)
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.text import parse_name_and_id

__all__ = ["OverviewGenerator"]


def _num(v: int | float | None) -> str:
    """Format numeric value for wiki tables."""
    try:
        if v is None:
            return ""
        if isinstance(v, float):
            if abs(v - int(v)) < 1e-9:
                s = str(int(v))
            else:
                s = f"{v:g}"
        else:
            s = str(v)
        if s == "0":
            return ""
        if s.startswith("-"):
            s = "&minus;" + s[1:]
        return s
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"Cannot format stat value: {v!r} (type: {type(v).__name__})"
        ) from e


def _classes_text(classes: list[str] | None) -> str:
    """Format classes as wiki links."""
    if not classes:
        return ""
    parts = sorted(set(classes), key=str.casefold)
    class_links = [f"[[{part}]]" for part in parts]
    return ", ".join(class_links)


class OverviewGenerator:
    """Generate overview page content from database.

    Extracts all items from database, classifies them as weapons/armor,
    builds overview tables with stats, and yields GeneratedContent for
    Weapons and Armor pages.

    The generator is responsible for:
    1. Querying database for all items
    2. Classifying items as weapons or armor
    3. Building overview table rows with stats
    4. Rendering overview table templates
    5. Resolving page titles via registry
    6. Yielding GeneratedContent for each overview page
    """

    def __init__(self) -> None:
        """Initialize overview generator."""
        pass

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate overview page content.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Not used for overviews (fixed page set)

        Yields:
            GeneratedContent for Weapons page and Armor page
        """
        linker = RegistryLinkResolver(registry)
        items = get_items(engine, obtainable_only=False)

        # Separate weapons and armor
        weapons = []
        armor = []

        for it in items:
            kind = classify_item_kind(
                required_slot=it.RequiredSlot,
                teach_spell=it.TeachSpell,
                teach_skill=it.TeachSkill,
                template_flag=it.Template,
                click_effect=it.ItemEffectOnClick,
                disposable=bool(it.Disposable),
            )
            if kind == "weapon":
                weapons.append(it)
            elif kind == "armor":
                armor.append(it)

        # Generate Weapons page
        yield from self._generate_weapons_page(engine, registry, linker, weapons)

        # Generate Armor page
        yield from self._generate_armor_page(engine, registry, linker, armor)

    def _generate_weapons_page(
        self,
        engine: Engine,
        registry: WikiRegistry,
        linker: RegistryLinkResolver,
        weapons: list[Any],
    ) -> Iterator[GeneratedContent]:
        """Generate Weapons overview page."""
        # Pre-fetch stats for shield classification
        weapon_stats = {}
        for weapon in weapons:
            stats = get_item_stats(engine, weapon.Id)
            base = next(
                (s for s in stats if (s.Quality or "").strip() in ("Normal", "0")), None
            )
            weapon_stats[weapon.Id] = base

        def slot_label(it: Any) -> str:
            slot = (it.RequiredSlot or "").strip()
            if slot == "PrimaryOrSecondary":
                slot = "Primary or Secondary"
            two_handed = (it.ThisWeaponType or "").strip() in (
                "TwoHandMelee",
                "TwoHandStaff",
            )
            if two_handed:
                slot += " - 2-Handed"
            return slot

        def type_label(it: Any, stats_dict: dict[int, Any]) -> str:
            if bool(getattr(it, "Shield", False)):
                base_stats = stats_dict.get(it.Id)
                weapon_dmg = getattr(base_stats, "WeaponDmg", 0) if base_stats else 0
                if weapon_dmg == 0:
                    return "Shield"

            if bool(getattr(it, "IsWand", False)):
                return "Wand"
            if bool(getattr(it, "IsBow", False)):
                return "Bow"
            t = (it.ThisWeaponType or "").strip()
            if t == "TwoHandBow":
                return "Bow"
            if t == "OneHandDagger":
                return "1H Dagger"
            if t == "OneHandMelee":
                return "1H Melee"
            if t == "TwoHandMelee":
                return "2H Melee"
            if t == "TwoHandStaff":
                return "2H Staff"
            return ""

        weapons_sorted = sorted(
            weapons,
            key=lambda it: (
                slot_label(it).casefold(),
                type_label(it, weapon_stats).casefold(),
                (
                    linker.resolve_item_title(it.ResourceName, it.ItemName, it.Id) or ""
                ).casefold(),
            ),
        )

        rows: list[str] = []
        header = [
            '{| class="wikitable datatable compact hover" style="font-size: 14px; text-align: center;"',
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
        rows.extend(header)

        for it in weapons_sorted:
            base = weapon_stats.get(it.Id)
            name = linker.item_link(it.ResourceName, it.ItemName, it.Id)
            slot_raw = (it.RequiredSlot or "").strip()
            slot_disp = (
                "Primary or Secondary" if slot_raw == "PrimaryOrSecondary" else slot_raw
            )
            two_handed = (it.ThisWeaponType or "").strip() in (
                "TwoHandMelee",
                "TwoHandStaff",
            )
            if two_handed:
                slot_disp += " - 2-Handed"

            level = _num(it.ItemLevel)
            dmg = _num(getattr(base, "WeaponDmg") if base else None)
            dly = _num(it.WeaponDly)

            def sget(attr: str) -> str:
                return _num(getattr(base, attr)) if base else ""

            # Notes: include procs, worn effects, on-click effects
            pieces: list[str] = []
            if it.WeaponProcOnHit and (it.WeaponProcChance or 0) > 0:
                tup = parse_name_and_id(it.WeaponProcOnHit)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        trigger = (
                            "on bash"
                            if bool(getattr(it, "Shield", False))
                            else "on attack"
                        )
                        pieces.append(f"{link}, {int(it.WeaponProcChance)}% {trigger}")

            if it.WandEffect and (it.WandProcChance or 0) > 0:
                tup = parse_name_and_id(it.WandEffect)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"{link}, {int(it.WandProcChance)}% on cast")

            if it.BowEffect and (it.BowProcChance or 0) > 0:
                tup = parse_name_and_id(it.BowEffect)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"{link}, {int(it.BowProcChance)}% on attack")

            if it.WornEffect:
                tup = parse_name_and_id(it.WornEffect)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"Worn: {link}")

            if it.ItemEffectOnClick:
                tup = parse_name_and_id(it.ItemEffectOnClick)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"On click: {link}")

            notes = WIKITEXT_LINE_SEPARATOR.join(pieces)
            classes = _classes_text(it.Classes)

            rows.extend(
                [
                    "|-",
                    f'|style="text-align: left;"|{name}',
                    f"|{slot_disp}",
                    f"|{type_label(it, weapon_stats)}",
                    f"|{level}",
                    f"|{dmg}",
                    f"|{dly}",
                    f"|{sget('HP')}",
                    f"|{sget('Mana')}",
                    f"|{sget('AC')}",
                    f"|{sget('Str')}",
                    f"|{sget('End')}",
                    f"|{sget('Dex')}",
                    f"|{sget('Agi')}",
                    f"|{sget('Int')}",
                    f"|{sget('Wis')}",
                    f"|{sget('Cha')}",
                    f"|{sget('Res')}",
                    f"|{sget('MR')}",
                    f"|{sget('PR')}",
                    f"|{sget('ER')}",
                    f"|{sget('VR')}",
                    f"|{notes}",
                    f"|{classes}",
                ]
            )

        rows.append("|}")
        rendered = "\n".join(rows) + "\n"

        title = "Weapons"
        entity_ref = EntityRef(
            entity_type=EntityType.OVERVIEW,
            db_id=None,
            db_name="Weapons",
            resource_name="weapons_overview",
        )

        page = registry.resolve_entity(entity_ref)
        if not page:
            page = registry.register_entity(entity_ref, title)

        blocks = [
            RenderedBlock(
                page_title=title,
                block_id="weapons_overview",
                template_key="Weapons_overview",
                text=rendered,
            )
        ]

        yield GeneratedContent(
            entity_ref=entity_ref,
            page_title=title,
            rendered_blocks=blocks,
        )

    def _generate_armor_page(
        self,
        engine: Engine,
        registry: WikiRegistry,
        linker: RegistryLinkResolver,
        armor: list[Any],
    ) -> Iterator[GeneratedContent]:
        """Generate Armor overview page."""

        def name_key(it: Any) -> str:
            return (
                linker.resolve_item_title(it.ResourceName, it.ItemName, it.Id) or ""
            ).casefold()

        armor_sorted = sorted(
            armor,
            key=lambda it: (((it.RequiredSlot or "").strip().casefold()), name_key(it)),
        )

        rows: list[str] = []
        header = [
            '{| class="wikitable datatable compact hover" style="font-size: 14px; text-align: center;"',
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
        rows.extend(header)

        for it in armor_sorted:
            stats = get_item_stats(engine, it.Id)
            base = next(
                (s for s in stats if (s.Quality or "").strip() in ("Normal", "0")), None
            )
            name = linker.item_link(it.ResourceName, it.ItemName, it.Id)
            slot = (it.RequiredSlot or "").strip()
            level = _num(it.ItemLevel)

            def sget(attr: str) -> str:
                return _num(getattr(base, attr)) if base else ""

            # Notes: include worn effects, on-click effects, bracer procs
            pieces: list[str] = []
            if it.WornEffect:
                tup = parse_name_and_id(it.WornEffect)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"Worn: {link}")

            if it.ItemEffectOnClick:
                tup = parse_name_and_id(it.ItemEffectOnClick)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"On click: {link}")

            if (
                (it.RequiredSlot or "").strip() == "Bracer"
                and it.WeaponProcOnHit
                and (it.WeaponProcChance or 0) > 0
            ):
                tup = parse_name_and_id(it.WeaponProcOnHit)
                if tup:
                    _, sid = tup
                    sp = get_spell_by_id(engine, sid)
                    if sp:
                        from erenshor.domain.entities.page import EntityRef

                        entity = EntityRef.from_spell(sp)
                        link = linker.ability_link(entity)
                        pieces.append(f"{link}, {int(it.WeaponProcChance)}% on cast")

            notes = WIKITEXT_LINE_SEPARATOR.join(pieces)
            classes = _classes_text(it.Classes)

            rows.extend(
                [
                    "|-",
                    f'|style="text-align: left;"|{name}',
                    f"|{slot}",
                    f"|{level}",
                    f"|{sget('HP')}",
                    f"|{sget('Mana')}",
                    f"|{sget('AC')}",
                    f"|{sget('Str')}",
                    f"|{sget('End')}",
                    f"|{sget('Dex')}",
                    f"|{sget('Agi')}",
                    f"|{sget('Int')}",
                    f"|{sget('Wis')}",
                    f"|{sget('Cha')}",
                    f"|{sget('Res')}",
                    f"|{sget('MR')}",
                    f"|{sget('PR')}",
                    f"|{sget('ER')}",
                    f"|{sget('VR')}",
                    f"|{notes}",
                    f"|{classes}",
                ]
            )

        rows.append("|}")
        rendered = "\n".join(rows) + "\n"

        title = "Armor"
        entity_ref = EntityRef(
            entity_type=EntityType.OVERVIEW,
            db_id=None,
            db_name="Armor",
            resource_name="armor_overview",
        )

        page = registry.resolve_entity(entity_ref)
        if not page:
            page = registry.register_entity(entity_ref, title)

        blocks = [
            RenderedBlock(
                page_title=title,
                block_id="armor_overview",
                template_key="Armor_overview",
                text=rendered,
            )
        ]

        yield GeneratedContent(
            entity_ref=entity_ref,
            page_title=title,
            rendered_blocks=blocks,
        )
