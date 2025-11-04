"""Proc extraction utilities for items.

This module extracts weapon and armor proc information including spell effects,
chances, and style labels (Attack, Bash, Cast, Worn, Activatable).
"""

from sqlalchemy import Connection

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repositories.spells import get_spell_by_id
from erenshor.shared.text import parse_name_and_id


class ProcExtractor:
    """Extract proc information from items.

    Handles WeaponProcOnHit, WandEffect, BowEffect, WornEffect, and ItemEffectOnClick
    with appropriate style labels based on proc type.
    """

    def __init__(self) -> None:
        """Initialize proc extractor with spell cache."""
        self._spell_cache: dict[str, Spell] = {}

    def _get_cached_spell(self, conn: Connection, spell_id: str) -> Spell | None:
        """Get spell from cache or database.

        Args:
            conn: Database connection
            spell_id: Spell ID

        Returns:
            Spell object or None if not found
        """
        if spell_id in self._spell_cache:
            return self._spell_cache[spell_id]
        spell = get_spell_by_id(conn, spell_id)
        if spell is not None:
            self._spell_cache[spell_id] = spell
        return spell

    def clear_cache(self) -> None:
        """Clear the spell cache for deterministic behavior."""
        self._spell_cache.clear()

    def extract_weapon_proc(
        self, conn: Connection, item: Item
    ) -> tuple[str, str, str, str]:
        """Extract weapon proc information.

        Priority order:
        1. WeaponProcOnHit (with WeaponProcChance) - style: "Bash" if shield, else "Attack"
        2. WandEffect (with WandProcChance) - style: "Attack"
        3. BowEffect (with BowProcChance) - style: "Attack"
        4. ItemEffectOnClick - style: "Activatable"

        Args:
            conn: Database connection
            item: Item to extract from

        Returns:
            Tuple of (proc_name, proc_desc, proc_chance, proc_style)
            where proc_name is the spell name/link, proc_desc is the spell description,
            proc_chance is the percentage string, and proc_style is one of:
            "Attack", "Bash", "Activatable"
        """
        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""

        # Priority 1: WeaponProcOnHit
        if item.weapon_proc_on_hit and (item.weapon_proc_chance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.weapon_proc_on_hit)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_chance = str(item.weapon_proc_chance)
            proc_style = "Bash" if item.shield else "Attack"

        # Priority 2: WandEffect
        elif item.wand_effect and (item.wand_proc_chance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.wand_effect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_chance = str(item.wand_proc_chance)
            proc_style = "Attack"

        # Priority 3: BowEffect
        elif item.bow_effect and (item.bow_proc_chance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.bow_effect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_chance = str(item.bow_proc_chance)
            proc_style = "Attack"

        # Priority 4: ItemEffectOnClick
        elif item.item_effect_on_click:
            parsed_tuple = parse_name_and_id(item.item_effect_on_click)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style

    def extract_armor_proc(
        self, conn: Connection, item: Item
    ) -> tuple[str, str, str, str]:
        """Extract armor proc information.

        Priority order:
        1. WeaponProcOnHit (with WeaponProcChance) - style: "Cast"
        2. WornEffect - style: "Worn"
        3. ItemEffectOnClick - style: "Activatable"

        Args:
            conn: Database connection
            item: Item to extract from

        Returns:
            Tuple of (proc_name, proc_desc, proc_chance, proc_style)
            where proc_name is the spell name/link, proc_desc is the spell description,
            proc_chance is the percentage string, and proc_style is one of:
            "Cast", "Worn", "Activatable"
        """
        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""

        # Priority 1: WeaponProcOnHit (for armor, this is a "Cast" proc)
        if item.weapon_proc_on_hit and (item.weapon_proc_chance or 0) > 0:
            parsed_tuple = parse_name_and_id(item.weapon_proc_on_hit)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_chance = str(item.weapon_proc_chance)
            proc_style = "Cast"

        # Priority 2: WornEffect
        elif item.worn_effect:
            parsed_tuple = parse_name_and_id(item.worn_effect)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_style = "Worn"

        # Priority 3: ItemEffectOnClick
        elif item.item_effect_on_click:
            parsed_tuple = parse_name_and_id(item.item_effect_on_click)
            if parsed_tuple:
                _proc_name, spell_id = parsed_tuple
                spell = self._get_cached_spell(conn, spell_id)
                if spell and spell.spell_name:
                    proc_name = spell.spell_name
                    if spell.spell_desc:
                        proc_desc = spell.spell_desc
            proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style
