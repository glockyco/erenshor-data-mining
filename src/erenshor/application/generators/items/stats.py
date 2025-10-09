"""Stat formatting utilities for items.

Handles weapon/armor stats, procs, and tier validation.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from erenshor.domain.entities import DbItem, DbItemStats
from erenshor.domain.entities.spell import DbSpell
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import REQUIRED_TIER_COUNT

__all__ = ["ProcExtractor", "validate_and_normalize_tiers", "weapon_type_display"]


logger = logging.getLogger(__name__)


def weapon_type_display(required_slot: str, this_weapon_type: str) -> str:
    """Convert weapon slot and type to display format for Fancy templates.

    Args:
        required_slot: Item required slot
        this_weapon_type: Weapon type string

    Returns:
        Display string for weapon type
    """
    slot = (required_slot or "").strip()
    if slot == "PrimaryOrSecondary":
        slot = "Primary or Secondary"

    two_handed = (this_weapon_type or "").strip() in (
        "TwoHandMelee",
        "TwoHandStaff",
    )
    if two_handed:
        slot += " - 2-Handed"

    return slot


def validate_and_normalize_tiers(
    stats: list[DbItemStats], item_id: str, item_name: str, item_type: str
) -> list[DbItemStats]:
    """Validate tier count is exactly 3.

    Fancy weapon/armor tables require exactly 3 tiers (Normal/0, Blessed/1, Godly/2).
    All weapons/armor MUST have exactly 3 tiers in the database. If tier count ≠ 3,
    this indicates a data error that must be fixed in the database.

    Args:
        stats: List of ItemStats records from database
        item_id: Item ID for error reporting
        item_name: Item name for error reporting
        item_type: "weapon" or "armor" for error reporting

    Returns:
        List with exactly 3 elements (Normal, Blessed, Godly)

    Raises:
        ValueError: If tier count is not exactly 3 (data error)
    """
    tier_count = len(stats)

    if tier_count != REQUIRED_TIER_COUNT:
        existing_qualities = [s.Quality for s in stats]
        error_msg = (
            f"DATA ERROR: {item_type.capitalize()} '{item_name}' (ID: {item_id}) "
            f"has {tier_count} tier(s), expected exactly {REQUIRED_TIER_COUNT}. "
            f"Tiers found: {existing_qualities}. "
            f"This item will be skipped. Please fix the database to include "
            f"exactly {REQUIRED_TIER_COUNT} tiers (Normal, Blessed, Godly)."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    return stats


class ProcExtractor:
    """Extract proc information from items."""

    def __init__(self) -> None:
        """Initialize proc extractor."""
        self._spell_cache: dict[str, DbSpell] = {}

    def _get_cached_spell(self, engine: Engine, spell_id: str) -> DbSpell | None:
        """Get spell from cache or database.

        Args:
            engine: Database engine
            spell_id: Spell ID

        Returns:
            Spell object or None
        """
        from erenshor.infrastructure.database.repositories import get_spell_by_id

        if spell_id in self._spell_cache:
            return self._spell_cache[spell_id]
        spell = get_spell_by_id(engine, spell_id)
        if spell is not None:
            self._spell_cache[spell_id] = spell
        return spell

    def clear_cache(self) -> None:
        """Clear the spell cache for deterministic behavior."""
        self._spell_cache.clear()

    def extract_weapon_proc(
        self, engine: Engine, item: DbItem, link_resolver: RegistryLinkResolver
    ) -> tuple[str, str, str, str]:
        """Extract weapon proc information.

        Args:
            engine: Database engine
            item: Item to extract from
            link_resolver: Link resolver

        Returns:
            Tuple of (proc_name, proc_desc, proc_chance, proc_style)
        """
        from erenshor.shared.text import parse_name_and_id

        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""

        if item.WeaponProcOnHit and (item.WeaponProcChance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.WeaponProcOnHit)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_chance = str(item.WeaponProcChance)
                proc_style = "Bash" if item.Shield else "Attack"
        elif item.WandEffect and (item.WandProcChance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.WandEffect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_chance = str(item.WandProcChance)
                proc_style = "Attack"
        elif item.BowEffect and (item.BowProcChance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.BowEffect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_chance = str(item.BowProcChance)
                proc_style = "Attack"
        elif item.ItemEffectOnClick:
            parsed_tuple = parse_name_and_id(item.ItemEffectOnClick)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style

    def extract_armor_proc(
        self, engine: Engine, item: DbItem, link_resolver: RegistryLinkResolver
    ) -> tuple[str, str, str, str]:
        """Extract armor proc information.

        Args:
            engine: Database engine
            item: Item to extract from
            link_resolver: Link resolver

        Returns:
            Tuple of (proc_name, proc_desc, proc_chance, proc_style)
        """
        from erenshor.shared.text import parse_name_and_id

        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""

        if item.WeaponProcOnHit and (item.WeaponProcChance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.WeaponProcOnHit)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_chance = str(item.WeaponProcChance)
                proc_style = "Cast"
        elif item.WornEffect:
            parsed_tuple = parse_name_and_id(item.WornEffect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_style = "Worn"
        elif item.ItemEffectOnClick:
            parsed_tuple = parse_name_and_id(item.ItemEffectOnClick)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(engine, spell_id)
                if spell:
                    proc_name = link_resolver.ability_link(
                        spell.ResourceName, spell.SpellName
                    )
                    if spell.SpellDesc:
                        proc_desc = spell.SpellDesc
                proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style
