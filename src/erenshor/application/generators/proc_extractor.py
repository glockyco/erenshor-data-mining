"""Proc extraction utilities for items.

This module extracts weapon and armor proc information including spell effects,
chances, and style labels (Attack, Bash, Cast, Worn, Activatable).

Proc fields store Spell ResourceNames, which are looked up to get spell names
and descriptions for display.
"""

from sqlalchemy import Connection, text

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.spell import Spell


class ProcExtractor:
    """Extract proc information from items.

    Handles WeaponProcOnHit, WandEffect, BowEffect, WornEffect, and ItemEffectOnClick
    with appropriate style labels based on proc type.
    """

    def __init__(self) -> None:
        """Initialize proc extractor with spell cache."""
        self._spell_cache: dict[str, Spell] = {}

    def _get_cached_spell(self, conn: Connection, resource_name: str) -> Spell | None:
        """Get spell from cache or database by ResourceName.

        Args:
            conn: Database connection
            resource_name: Spell ResourceName (primary key)

        Returns:
            Spell object or None if not found
        """
        if not resource_name:
            return None

        if resource_name in self._spell_cache:
            return self._spell_cache[resource_name]

        # Query by ResourceName (primary key)
        query = text("SELECT SpellName, SpellDesc FROM Spells WHERE ResourceName = :resource_name")
        result = conn.execute(query, {"resource_name": resource_name}).fetchone()

        if result is None:
            return None

        # Create minimal Spell object with just name and description
        spell = Spell(
            spell_db_index=0,  # Not needed for proc display
            spell_name=result[0],
            spell_desc=result[1],
        )
        self._spell_cache[resource_name] = spell
        return spell

    def clear_cache(self) -> None:
        """Clear the spell cache for deterministic behavior."""
        self._spell_cache.clear()

    def extract_weapon_proc(self, conn: Connection, item: Item) -> tuple[str, str, str, str]:
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
        if item.weapon_proc_on_hit_stable_key and (item.weapon_proc_chance or 0) > 0:
            spell = self._get_cached_spell(conn, item.weapon_proc_on_hit_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_chance = str(item.weapon_proc_chance)
            proc_style = "Bash" if item.shield else "Attack"

        # Priority 2: WandEffect
        elif item.wand_effect_stable_key and (item.wand_proc_chance or 0) > 0:
            spell = self._get_cached_spell(conn, item.wand_effect_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_chance = str(item.wand_proc_chance)
            proc_style = "Attack"

        # Priority 3: BowEffect
        elif item.bow_effect_stable_key and (item.bow_proc_chance or 0) > 0:
            spell = self._get_cached_spell(conn, item.bow_effect_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_chance = str(item.bow_proc_chance)
            proc_style = "Attack"

        # Priority 4: ItemEffectOnClick
        elif item.item_effect_on_click_stable_key:
            spell = self._get_cached_spell(conn, item.item_effect_on_click_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style

    def extract_armor_proc(self, conn: Connection, item: Item) -> tuple[str, str, str, str]:
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
        if item.weapon_proc_on_hit_stable_key and (item.weapon_proc_chance or 0) > 0:
            spell = self._get_cached_spell(conn, item.weapon_proc_on_hit_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_chance = str(item.weapon_proc_chance)
            proc_style = "Cast"

        # Priority 2: WornEffect
        elif item.worn_effect_stable_key:
            spell = self._get_cached_spell(conn, item.worn_effect_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_style = "Worn"

        # Priority 3: ItemEffectOnClick
        elif item.item_effect_on_click_stable_key:
            spell = self._get_cached_spell(conn, item.item_effect_on_click_stable_key)
            if spell and spell.spell_name:
                proc_name = spell.spell_name
                if spell.spell_desc:
                    proc_desc = spell.spell_desc
            proc_style = "Activatable"

        return proc_name, proc_desc, proc_chance, proc_style
