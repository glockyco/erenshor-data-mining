"""Character repository for specialized character queries."""

from loguru import logger

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.wiki_link import CharacterLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    All queries target the clean snake_case database written by ``extract build``.
    """

    def get_characters_for_wiki_generation(self) -> list[Character]:
        """Get all characters for wiki page generation.

        The clean DB already excludes SimPlayers and blank-named entries.
        Faction display/wiki fields and faction modifiers are populated via JOINs
        so section generators never need a resolver.

        Returns:
            List of Character entities ordered by display_name.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                c.stable_key,
                c.object_name,
                c.npc_name,
                c.display_name,
                c.wiki_page_name,
                c.image_name,
                c.scene,
                c.x,
                c.y,
                c.z,
                c.my_world_faction_stable_key,
                f.display_name  AS my_world_faction_display_name,
                f.wiki_page_name AS my_world_faction_wiki_page_name,
                c.my_faction,
                c.aggro_range,
                c.attack_range,
                c.aggressive_towards,
                c.allies,
                c.is_prefab,
                c.is_common,
                c.is_rare,
                c.is_unique,
                c.is_friendly,
                c.is_npc,
                c.is_vendor,
                c.is_mining_node,
                c.has_stats,
                c.has_dialog,
                c.has_modify_faction,
                c.is_enabled,
                c.invulnerable,
                c.shout_on_death,
                c.quest_complete_on_death,
                c.destroy_on_death,
                c.level,
                c.base_xp_min,
                c.base_xp_max,
                c.boss_xp_multiplier,
                c.base_hp,
                c.base_ac,
                c.base_mana,
                c.base_str,
                c.base_end,
                c.base_dex,
                c.base_agi,
                c.base_int,
                c.base_wis,
                c.base_cha,
                c.base_res,
                c.base_mr,
                c.base_er,
                c.base_pr,
                c.base_vr,
                c.run_speed,
                c.base_life_steal,
                c.base_mh_atk_delay,
                c.base_oh_atk_delay,
                c.effective_hp,
                c.effective_ac,
                c.effective_base_atk_dmg,
                c.effective_attack_ability,
                c.effective_min_mr,
                c.effective_max_mr,
                c.effective_min_er,
                c.effective_max_er,
                c.effective_min_pr,
                c.effective_max_pr,
                c.effective_min_vr,
                c.effective_max_vr,
                c.pet_spell_stable_key,
                c.proc_on_hit_stable_key,
                c.proc_on_hit_chance,
                c.hand_set_resistances,
                c.hard_set_ac,
                c.base_atk_dmg,
                c.oh_atk_dmg,
                c.min_atk_dmg,
                c.damage_range_min,
                c.damage_range_max,
                c.damage_mult,
                c.armor_pen_mult,
                c.power_attack_base_dmg,
                c.power_attack_freq,
                c.heal_tolerance,
                c.leash_range,
                c.aggro_regardless_of_level,
                c.mobile,
                c.group_encounter,
                c.treasure_chest,
                c.do_not_leave_corpse,
                c.set_achievement_on_defeat,
                c.set_achievement_on_spawn,
                c.aggro_msg,
                c.aggro_emote,
                c.spawn_emote,
                c.guild_name,
                c.vendor_desc
            FROM characters c
            LEFT JOIN factions f ON f.stable_key = c.my_world_faction_stable_key
            ORDER BY c.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            characters = [Character.model_validate(dict(row)) for row in rows]

            # Populate faction modifiers from junction table
            stable_keys = [char.stable_key for char in characters if char.stable_key]
            if stable_keys:
                faction_modifiers_map = self._get_faction_modifiers_for_characters(stable_keys)
                for char in characters:
                    if char.stable_key:
                        char.faction_modifiers = faction_modifiers_map.get(char.stable_key, [])

            logger.debug(f"Retrieved {len(characters)} characters for wiki generation")
            return characters
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve characters for wiki: {e}") from e

    def _get_faction_modifiers_for_characters(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]:
        """Get faction modifiers for multiple characters.

        JOINs the factions table to populate display_name and wiki_page_name
        on each FactionModifier so section generators can build FactionLinks
        without a resolver.

        Args:
            stable_keys: List of character stable keys to query

        Returns:
            Dict mapping character stable key to list of FactionModifiers

        Raises:
            RepositoryError: If query execution fails
        """
        if not stable_keys:
            return {}

        placeholders = ",".join("?" * len(stable_keys))
        query = f"""
            SELECT
                cfm.character_stable_key,
                cfm.faction_stable_key,
                cfm.modifier_value,
                f.display_name   AS faction_display_name,
                f.wiki_page_name AS faction_wiki_page_name
            FROM character_faction_modifiers cfm
            LEFT JOIN factions f ON f.stable_key = cfm.faction_stable_key
            WHERE cfm.character_stable_key IN ({placeholders})
            ORDER BY cfm.character_stable_key, f.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, tuple(stable_keys))

            result: dict[str, list[FactionModifier]] = {}
            for row in rows:
                char_key = str(row["character_stable_key"])
                display = (
                    str(row["faction_display_name"]) if row["faction_display_name"] else str(row["faction_stable_key"])
                )
                wiki = str(row["faction_wiki_page_name"]) if row["faction_wiki_page_name"] else None
                modifier = FactionModifier(
                    faction_stable_key=str(row["faction_stable_key"]),
                    modifier_value=int(row["modifier_value"]),
                    faction_display_name=display,
                    faction_wiki_page_name=wiki,
                )
                if char_key not in result:
                    result[char_key] = []
                result[char_key].append(modifier)

            logger.debug(f"Retrieved faction modifiers for {len(result)} characters")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction modifiers: {e}") from e

    def get_character_link(self, stable_key: str) -> CharacterLink | None:
        """Get a pre-built CharacterLink for a single character by stable key.

        Used for cross-entity links (e.g., pet_to_summon on spells) where the
        section generator needs a ready-to-render link object.

        Args:
            stable_key: Character stable key

        Returns:
            CharacterLink if found, None if character doesn't exist or is excluded.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT display_name, wiki_page_name
            FROM characters
            WHERE stable_key = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                return None
            row = rows[0]
            return CharacterLink(
                page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                display_name=str(row["display_name"]),
            )
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve character link for '{stable_key}': {e}") from e

    def get_vendors_selling_item(self, item_stable_key: str) -> list[CharacterLink]:
        """Get characters (vendors) that sell the given item.

        Returns pre-built CharacterLink objects — section generators call str(link)
        directly without resolver lookup.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of CharacterLink objects sorted by display name.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT
                c.display_name,
                c.wiki_page_name
            FROM characters c
            JOIN character_vendor_items cvi ON c.stable_key = cvi.character_stable_key
            WHERE cvi.item_stable_key = ?
            ORDER BY c.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            links = [
                CharacterLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} vendors selling '{item_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve vendors for item '{item_stable_key}': {e}") from e

    def get_characters_dropping_item(self, item_stable_key: str) -> list[tuple[CharacterLink, float]]:
        """Get characters that drop the given item.

        Returns pre-built CharacterLink objects with drop probabilities — section
        generators call str(link) directly without resolver lookup.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of (CharacterLink, drop_probability) tuples sorted by display name.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT
                c.display_name,
                c.wiki_page_name,
                ld.drop_probability
            FROM characters c
            JOIN loot_drops ld ON c.stable_key = ld.character_stable_key
            WHERE ld.item_stable_key = ?
                AND ld.drop_probability > 0.0
            ORDER BY c.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            results = [
                (
                    CharacterLink(
                        page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                        display_name=str(row["display_name"]),
                    ),
                    float(row["drop_probability"]) if row["drop_probability"] is not None else 0.0,
                )
                for row in rows
            ]
            logger.debug(f"Found {len(results)} characters dropping '{item_stable_key}'")
            return results
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve droppers for item '{item_stable_key}': {e}") from e

    def get_characters_using_spell(self, spell_stable_key: str) -> list[CharacterLink]:
        """Get characters that use the given spell.

        Returns pre-built CharacterLink objects sorted by display name.

        Args:
            spell_stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            List of CharacterLink objects (sorted alphabetically, deduplicated).

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT c.display_name, c.wiki_page_name
            FROM characters c
            WHERE c.stable_key IN (
                SELECT character_stable_key FROM character_attack_spells WHERE spell_stable_key = ?
                UNION
                SELECT character_stable_key FROM character_buff_spells WHERE spell_stable_key = ?
                UNION
                SELECT character_stable_key FROM character_heal_spells WHERE spell_stable_key = ?
                UNION
                SELECT character_stable_key FROM character_group_heal_spells WHERE spell_stable_key = ?
                UNION
                SELECT character_stable_key FROM character_cc_spells WHERE spell_stable_key = ?
                UNION
                SELECT character_stable_key FROM character_taunt_spells WHERE spell_stable_key = ?
            )
            ORDER BY c.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,) * 6)
            links = [
                CharacterLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} characters using spell '{spell_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve characters using spell '{spell_stable_key}': {e}") from e
