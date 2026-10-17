"""Character repository for specialized character queries."""

import json

from loguru import logger

from erenshor.application.processor.npc_spawn import SpawnConstants, load_spawn_constants
from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.loot import LootDropDisplayInfo
from erenshor.domain.value_objects.vendor_stock import VendorStockEntry
from erenshor.domain.value_objects.wiki_link import CharacterLink, ItemLink
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    All queries target the clean snake_case database written by ``extract build``.
    """

    def get_character_data_catalog(self) -> dict[str, dict[str, object]]:
        """Read canonical labels, including identities without a public article."""
        tables = ("characters", "items", "spells", "skills", "quests", "factions", "zones")
        query = (
            " UNION ALL ".join(
                f"SELECT stable_key, display_name AS name, wiki_page_name AS page FROM {table}" for table in tables
            )
            + " ORDER BY stable_key"
        )
        return {
            str(row["stable_key"]): {"name": row["name"], "page": row["page"]} for row in self._execute_raw(query, ())
        }

    def get_character_data_classes(self) -> list[dict[str, object]]:
        """Read resource identity and class metadata without fabricating article targets."""
        return [
            dict(row)
            for row in self._execute_raw(
                "SELECT resource_name, class_name, display_name, mitigation_bonus FROM classes ORDER BY resource_name",
                (),
            )
        ]

    def get_character_data_spawn_constants(self) -> SpawnConstants:
        """Read the constants through the existing initialization owner."""
        with self.db.connect() as connection:
            return load_spawn_constants(connection)

    def get_character_data_summoners(self) -> list[dict[str, object]]:
        """Read every actual summon edge, including abilities without wiki pages."""
        return [
            dict(row)
            for row in self._execute_raw(
                """
                SELECT pet_to_summon_stable_key AS character_stable_key,
                       stable_key AS ability_key, display_name AS name, wiki_page_name AS page
                FROM spells
                WHERE pet_to_summon_stable_key IS NOT NULL
                ORDER BY pet_to_summon_stable_key, stable_key
                """,
                (),
            )
        ]

    def get_character_data_members(self, stable_key: str) -> list[Character]:
        """Read every eligible fact source without promoting representative facts."""
        rows = self._execute_raw(
            """
            SELECT c.*, f.display_name AS my_world_faction_display_name,
                   f.wiki_page_name AS my_world_faction_wiki_page_name
            FROM character_fact_sources s
            JOIN characters c ON c.stable_key = s.member_stable_key
            LEFT JOIN factions f ON f.stable_key = c.my_world_faction_stable_key
            WHERE s.group_key = (
                SELECT group_key FROM character_deduplications
                WHERE member_stable_key = ?
            )
            ORDER BY c.stable_key
            """,
            (stable_key,),
        )
        members = [Character.model_validate(dict(row)) for row in rows]
        modifiers = self._get_faction_modifiers_for_characters([member.stable_key for member in members])
        for member in members:
            member.faction_modifiers = modifiers.get(member.stable_key, [])
        return members

    def get_character_data_abilities(self, stable_key: str) -> list[dict[str, object]]:
        """Return actual ability usages with the copy that supplies each relation."""
        rows = self._execute_raw(
            """
            WITH members AS (
                SELECT member_stable_key FROM character_fact_sources
                WHERE group_key = (
                    SELECT group_key FROM character_deduplications WHERE member_stable_key = ?
                )
            ), usages AS (
                SELECT character_stable_key, skill_stable_key AS ability_key,
                       'attack_skill' AS usage FROM character_attack_skills
                UNION ALL SELECT character_stable_key, spell_stable_key, 'attack' FROM character_attack_spells
                UNION ALL SELECT character_stable_key, spell_stable_key, 'buff' FROM character_buff_spells
                UNION ALL SELECT character_stable_key, spell_stable_key, 'heal' FROM character_heal_spells
                UNION ALL SELECT character_stable_key, spell_stable_key, 'group_heal' FROM character_group_heal_spells
                UNION ALL SELECT character_stable_key, spell_stable_key, 'cc' FROM character_cc_spells
                UNION ALL SELECT character_stable_key, spell_stable_key, 'taunt' FROM character_taunt_spells
                UNION ALL SELECT stable_key, pet_spell_stable_key, 'pet' FROM characters
                UNION ALL SELECT stable_key, spawn_with_status_stable_key, 'spawn_status' FROM characters
                UNION ALL SELECT stable_key, group_hot_spell_stable_key, 'group_hot' FROM characters
                UNION ALL SELECT stable_key, emit_vitae_spell_stable_key, 'emit_vitae' FROM characters
                UNION ALL SELECT stable_key, hot_spell_stable_key, 'hot' FROM characters
                UNION ALL SELECT stable_key, ae_taunt_spell_stable_key, 'ae_taunt' FROM characters
                UNION ALL SELECT stable_key, proc_on_hit_stable_key, 'proc_on_hit' FROM characters
            )
            SELECT DISTINCT u.character_stable_key, u.ability_key, u.usage,
                   COALESCE(s.display_name, k.display_name) AS name,
                   COALESCE(s.wiki_page_name, k.wiki_page_name) AS page,
                   CASE WHEN u.usage = 'proc_on_hit' THEN owner.proc_on_hit_chance END AS chance
            FROM usages u
            JOIN members m ON m.member_stable_key = u.character_stable_key
            JOIN characters owner ON owner.stable_key = u.character_stable_key
            LEFT JOIN spells s ON s.stable_key = u.ability_key
            LEFT JOIN skills k ON k.stable_key = u.ability_key
            WHERE u.ability_key IS NOT NULL AND u.ability_key != ''
            ORDER BY u.ability_key, u.usage, u.character_stable_key
            """,
            (stable_key,),
        )
        return [dict(row) for row in rows]

    def get_character_placements(self) -> list[dict[str, object]]:
        """Read the shared full copy-keyed placement boundary without combat filtering."""
        rows = self._execute_raw(
            """
            WITH reps AS (
                SELECT group_key, MIN(member_stable_key) AS stable_key
                FROM character_deduplications
                WHERE is_wiki_generated = 1 GROUP BY group_key
            ), page_reps AS (
                SELECT c.wiki_page_name, c.encounter_tier, MIN(r.stable_key) AS stable_key
                FROM reps r JOIN characters c ON c.stable_key = r.stable_key
                GROUP BY c.wiki_page_name, c.encounter_tier
            )
            SELECT cs.*, d.group_key,
                   c.stable_key AS source_member_stable_key,
                   r.stable_key AS representative_stable_key,
                   p.stable_key AS page_character_stable_key,
                   d.is_wiki_generated AS member_is_wiki_generated,
                   d.is_map_visible AS member_is_map_visible,
                   c.display_name AS character_display_name,
                   c.wiki_page_name AS character_wiki_page_name,
                   c.encounter_tier, c.level, c.group_encounter,
                   c.level_scales_with_player, c.can_be_damaged, c.dps_dummy,
                   c.invulnerable AS initial_invulnerable,
                   z.display_name AS zone_display_name,
                   z.wiki_page_name AS zone_wiki_page_name,
                   z.is_map_visible AS zone_is_map_visible,
                   pr.stable_key AS protector_representative_stable_key,
                   (SELECT json_group_array(sq.quest_stable_key)
                    FROM spawn_point_stop_quests sq
                    WHERE sq.spawn_point_stable_key = cs.spawn_point_stable_key) AS stop_quests,
                   (SELECT json_group_array(json_object(
                        'mechanism', dr.mechanism,
                        'source_stable_key', dr.source_stable_key,
                        'condition_kind', dr.condition_kind,
                        'condition_stable_key', dr.condition_stable_key,
                        'quest_stable_key', CASE WHEN dr.condition_kind = 'quest_variant' THEN
                            (SELECT qv.quest_stable_key FROM quest_variants qv
                             WHERE qv.resource_name = dr.condition_stable_key) END,
                        'can_release', dr.can_release,
                        'controller_enabled', dr.controller_enabled))
                    FROM character_damage_releases dr
                    WHERE dr.character_stable_key = c.stable_key) AS damage_releases,
                   (SELECT json_group_array(json_object(
                        'subject_kind', gc.subject_kind,
                        'subject_stable_key', gc.subject_stable_key,
                        'gate', gc.gate, 'group_index', gc.group_index,
                        'atom_kind', gc.atom_kind, 'atom_stable_key', gc.atom_stable_key,
                        'atom_slot', gc.atom_slot))
                    FROM gate_conditions gc
                    WHERE (gc.subject_kind = 'character' AND gc.subject_stable_key = c.stable_key)
                       OR (gc.subject_kind = 'spawn_point' AND gc.subject_stable_key = cs.spawn_point_stable_key)
                   ) AS gates,
                   (SELECT json_group_array(te.zone_line_stable_key)
                    FROM target_entries te
                    WHERE (te.target_kind = 'character' AND te.target_stable_key = c.stable_key)
                       OR (te.target_kind = 'spawn_point' AND te.target_stable_key = cs.spawn_point_stable_key)
                   ) AS entry_zone_line_keys,
                   (SELECT json_group_array(json_object(
                        'key', zl.stable_key, 'source_zone_key', ez.stable_key,
                        'source_zone_name', ez.display_name, 'source_zone_page', ez.wiki_page_name,
                        'x', zl.x, 'y', zl.y, 'z', zl.z,
                        'destination_zone_key', zl.destination_zone_stable_key))
                    FROM target_entries te
                    JOIN zone_lines zl ON zl.stable_key = te.zone_line_stable_key
                    LEFT JOIN zones ez ON ez.scene_name = zl.scene
                    WHERE (te.target_kind = 'character' AND te.target_stable_key = c.stable_key)
                       OR (te.target_kind = 'spawn_point' AND te.target_stable_key = cs.spawn_point_stable_key)
                   ) AS entries
            FROM character_fact_sources fs
            JOIN character_deduplications d ON d.group_key = fs.group_key
                                           AND d.member_stable_key = fs.member_stable_key
            JOIN reps r ON r.group_key = d.group_key
            JOIN characters c ON c.stable_key = fs.member_stable_key
            LEFT JOIN wiki_character_spawns cs ON cs.character_stable_key = c.stable_key
            LEFT JOIN page_reps p ON p.wiki_page_name = c.wiki_page_name
                           AND p.encounter_tier = c.encounter_tier
            LEFT JOIN zones z ON z.stable_key = cs.zone_stable_key
            LEFT JOIN character_deduplications pd ON pd.member_stable_key = cs.protector_stable_key
            LEFT JOIN reps pr ON pr.group_key = pd.group_key
            ORDER BY r.stable_key, cs.character_stable_key,
                     cs.spawn_point_stable_key, cs.is_directly_placed
            """,
            (),
        )
        result = [dict(row) for row in rows]
        for row in result:
            for field in ("stop_quests", "damage_releases", "gates", "entry_zone_line_keys", "entries"):
                row[field] = sorted(json.loads(str(row[field])), key=lambda value: json.dumps(value, sort_keys=True))
            row["placement_kind"] = "placement" if row["character_stable_key"] is not None else "unplaced"
            row["character_stable_key"] = row.pop("source_member_stable_key")
        treasure_rows = self._execute_raw(
            """
            WITH reps AS (
                SELECT group_key, MIN(member_stable_key) AS stable_key
                FROM character_deduplications WHERE is_wiki_generated = 1 GROUP BY group_key
            ), subjects AS (
                SELECT DISTINCT ts.chest_character_stable_key AS character_stable_key,
                       ts.chest_character_stable_key, 'chest' AS treasure_role
                FROM treasure_chest_possible_spawns ts
                UNION
                SELECT chain.child_stable_key, chain.parent_stable_key, 'guardian'
                FROM character_chained_spawns chain
                WHERE chain.source_script = 'TreasureChestEvent'
            )
            SELECT ts.*, subject.character_stable_key, subject.treasure_role,
                   d.group_key, r.stable_key AS representative_stable_key,
                   d.is_wiki_generated AS member_is_wiki_generated,
                   d.is_map_visible AS member_is_map_visible,
                   c.display_name AS character_display_name,
                   c.wiki_page_name AS character_wiki_page_name,
                   c.encounter_tier, c.level, c.group_encounter, c.level_scales_with_player,
                   c.can_be_damaged, c.dps_dummy, c.invulnerable AS initial_invulnerable,
                   z.stable_key AS zone_stable_key, z.display_name AS zone_display_name,
                   z.wiki_page_name AS zone_wiki_page_name,
                   z.is_map_visible AS zone_is_map_visible
            FROM subjects subject
            JOIN treasure_chest_possible_spawns ts
              ON ts.chest_character_stable_key = subject.chest_character_stable_key
            JOIN character_deduplications d ON d.member_stable_key = subject.character_stable_key
            JOIN character_fact_sources fs ON fs.group_key = d.group_key
                                         AND fs.member_stable_key = subject.character_stable_key
            JOIN reps r ON r.group_key = d.group_key
            JOIN characters c ON c.stable_key = subject.character_stable_key
            LEFT JOIN zones z ON z.scene_name = ts.scene
            ORDER BY r.stable_key, subject.character_stable_key, ts.treasure_location_stable_key
            """,
            (),
        )
        for source in treasure_rows:
            row = dict(source)
            row.update(
                placement_kind="possible_treasure",
                is_directly_placed=0,
                is_map_visible=0,
                level_mod=0,
                spawn_point_stable_key=None,
                stop_quests=[],
                damage_releases=[],
                gates=[],
                entry_zone_line_keys=[],
                entries=[],
            )
            result.append(row)
        return result

    def get_zone_roster_spawns(self) -> list[dict[str, object]]:
        """Return wiki-visible spawn copies with their conditions and canonical character keys."""
        query = """
            WITH reps AS (
                SELECT group_key, MIN(member_stable_key) AS stable_key
                FROM character_deduplications WHERE is_wiki_generated = 1 GROUP BY group_key
            ), page_reps AS (
                SELECT c.wiki_page_name, c.encounter_tier, MIN(r.stable_key) AS stable_key
                FROM reps r JOIN characters c ON c.stable_key = r.stable_key
                GROUP BY c.wiki_page_name, c.encounter_tier
            )
            SELECT cs.zone_stable_key AS zone, page_rep.stable_key AS character, c.encounter_tier AS tier,
                   c.level, COALESCE(cs.level_mod, 0) AS levelMod,
                   COALESCE(c.group_encounter, 0) AS "group",
                   COALESCE(c.level_scales_with_player, 0) AS scales,
                   COALESCE(cs.night_spawn, 0) AS night, COALESCE(cs.is_rare, 0) AS rare,
                   cs.spawn_chance AS chance, cs.source_script AS script,
                   cs.furniture_item_stable_key AS furniture,
                   cs.spawn_upon_quest_complete_stable_key AS quest,
                   cs.trigger_item_stable_key AS triggerItem, pr.stable_key AS protector,
                   (SELECT json_group_array(sq.quest_stable_key) FROM spawn_point_stop_quests sq
                    WHERE sq.spawn_point_stable_key = cs.spawn_point_stable_key) AS stopQuests
            FROM wiki_character_spawns cs
            JOIN character_deduplications d ON d.member_stable_key = cs.character_stable_key
                                         AND d.is_wiki_generated = 1
            JOIN reps r ON r.group_key = d.group_key
            JOIN characters c ON c.stable_key = cs.character_stable_key
            JOIN page_reps page_rep ON page_rep.wiki_page_name = c.wiki_page_name
                                  AND page_rep.encounter_tier = c.encounter_tier
            JOIN zones z ON z.stable_key = cs.zone_stable_key AND z.wiki_page_name IS NOT NULL
            LEFT JOIN character_deduplications pd ON pd.member_stable_key = cs.protector_stable_key
            LEFT JOIN reps pr ON pr.group_key = pd.group_key
            WHERE (cs.spawn_chance > 0 OR cs.source_script IS NOT NULL OR cs.is_directly_placed = 1)
              AND c.wiki_page_name IS NOT NULL
            ORDER BY zone, character, cs.spawn_point_stable_key
        """
        try:
            rows = [dict(row) for row in self._execute_raw(query, ())]
            for row in rows:
                row["stopQuests"] = json.loads(str(row["stopQuests"]))
            return rows
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve zone roster spawns: {e}") from e

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
            WITH vendor_status AS (
                -- Vendor status is not part of the dedup identity, so a group
                -- is a vendor when one of its encountered copies is.
                SELECT s.group_key, MAX(m.is_vendor) AS group_is_vendor
                FROM character_fact_sources s
                JOIN characters m ON m.stable_key = s.member_stable_key
                GROUP BY s.group_key
            ),
            reps AS (
                -- A page shows one representative per deduplication group.
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key, v.group_is_vendor
                FROM character_deduplications d
                JOIN vendor_status v ON v.group_key = d.group_key
                WHERE d.is_wiki_generated = 1
                GROUP BY d.group_key
            )
            SELECT
                c.stable_key,
                c.object_name,
                c.guid,
                c.resources_path,
                c.class_resource_name,
                c.start_components_listed,
                c.start_components_by_file_id,
                c.is_active_at_load,
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
                c.encounter_tier,
                c.is_friendly,
                c.is_npc,
                r.group_is_vendor AS is_vendor,
                c.is_mining_node,
                c.has_stats,
                c.has_dialog,
                c.has_modify_faction,
                c.is_enabled,
                c.invulnerable,
                c.can_be_damaged,
                c.can_never_see_invis,
                c.dps_dummy,
                c.is_wyrm,
                c.no_run,
                c.never_aggro,
                c.no_dmg_cap,
                c.can_phantom_strike,
                c.no_self_heal,
                c.aggro_regardless_of_los,
                c.ignore_los_for_aggro,
                c.sim_players_ignore_until_ordered,
                c.enrage,
                c.shout_on_death,
                c.quest_complete_on_death,
                c.destroy_on_death,
                c.level,
                c.level_scales_with_player,
                c.ac_per_player_level,
                c.base_xp_min,
                c.base_xp_max,
                c.boss_xp_multiplier,
                c.initialized_xp,
                c.xp_per_player_level,
                c.effective_xp_multiplier,
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
                c.base_armor_pen_percentage,
                c.base_attack_roll_modifier,
                c.cannot_be_snared,
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
                c.spawn_with_status_stable_key,
                c.proc_on_hit_stable_key,
                c.proc_on_hit_chance,
                c.hand_set_resistances,
                c.hard_set_ac,
                c.test_dummy_hand_set_ac,
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
                EXISTS (
                    SELECT 1 FROM spells s WHERE s.pet_to_summon_stable_key = c.stable_key
                ) AS is_summon,
                c.guaranteed_drop_rolls,
                c.do_not_leave_corpse,
                c.set_achievement_on_defeat,
                c.set_achievement_on_spawn,
                c.aggro_msg,
                c.aggro_emote,
                c.spawn_emote,
                c.guild_name,
                c.vendor_desc
            FROM reps r
            JOIN characters c ON c.stable_key = r.rep_stable_key
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
            WITH target_group AS (
                SELECT group_key
                FROM character_deduplications
                WHERE member_stable_key = ?
                LIMIT 1
            ),
            rep AS (
                SELECT MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.group_key = (SELECT group_key FROM target_group)
                  AND d.is_wiki_generated = 1
            )
            SELECT c.stable_key, c.display_name, c.wiki_page_name
            FROM characters c
            WHERE c.stable_key = (SELECT rep_stable_key FROM rep)
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
                stable_key=str(row["stable_key"]),
            )
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve character link for '{stable_key}': {e}") from e

    def get_character_loot_drops(self, character_stable_key: str) -> list[LootDropDisplayInfo]:
        """Project one copy's canonical drops with equipped-item display metadata."""
        query = """
            SELECT i.stable_key, i.display_name, i.wiki_page_name, i.image_name,
                a.probability_min AS drop_probability,
                a.guarantee_scope = 'pool' AS is_guaranteed,
                COALESCE(ld.is_visible, 0) AS is_visible,
                COALESCE(i.is_unique, 0) AS item_unique
            FROM item_acquisitions a
            JOIN items i ON i.stable_key = a.item_stable_key
            LEFT JOIN loot_drops ld
              ON ld.character_stable_key = a.source_copy_stable_key
             AND ld.item_stable_key = a.item_stable_key
            WHERE a.kind = 'character_drop' AND a.source_copy_stable_key = ?
              AND i.display_name IS NOT NULL AND a.probability_min IS NOT NULL
            ORDER BY a.probability_min DESC, i.display_name COLLATE NOCASE, a.acquisition_key
        """
        try:
            ItemProvenanceRepository(self.db)
            return [
                LootDropDisplayInfo(
                    item_link=ItemLink(
                        page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                        display_name=str(row["display_name"]),
                        image_name=str(row["image_name"]) if row["image_name"] else None,
                        stable_key=str(row["stable_key"]),
                    ),
                    drop_probability=float(row["drop_probability"]),
                    is_guaranteed=bool(row["is_guaranteed"]),
                    is_visible=bool(row["is_visible"]),
                    item_unique=bool(row["item_unique"]),
                )
                for row in self._execute_raw(query, (character_stable_key,))
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve loot for character {character_stable_key}: {e}") from e

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
            WITH spell_groups AS (
                SELECT DISTINCT d.group_key
                FROM character_fact_sources d
                JOIN (
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
                ) s ON s.character_stable_key = d.member_stable_key
            ),
            reps AS (
                SELECT sg.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM spell_groups sg
                JOIN character_deduplications d ON d.group_key = sg.group_key
                WHERE d.is_wiki_generated = 1
                GROUP BY sg.group_key
            )
            SELECT c.stable_key, c.display_name, c.wiki_page_name
            FROM reps r
            JOIN characters c ON c.stable_key = r.rep_stable_key
            ORDER BY c.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,) * 6)
            links = [
                CharacterLink(
                    page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                    display_name=str(row["display_name"]),
                    stable_key=str(row["stable_key"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(links)} characters using spell '{spell_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve characters using spell '{spell_stable_key}': {e}") from e

    def get_vendor_stock(self) -> list[VendorStockEntry]:
        """Project canonical offers with copy-local furniture and stock-unlock gates."""
        query = """
            WITH location_furniture AS (
                SELECT l.owner_key, l.location_key,
                    CASE WHEN COUNT(DISTINCT json_extract(atom.value, '$.reference_stable_key')) = 1
                    THEN MIN(json_extract(atom.value, '$.reference_stable_key')) END AS furniture_key
                FROM item_acquisition_locations l
                JOIN item_acquisitions a ON a.acquisition_key = l.owner_key AND a.kind = 'vendor'
                LEFT JOIN json_each(l.conditions) atom
                  ON json_extract(atom.value, '$.predicate') = 'room_furnished'
                GROUP BY l.owner_key, l.location_key
            ),
            furniture AS (
                SELECT owner_key,
                    CASE WHEN COUNT(*) = COUNT(furniture_key) AND COUNT(DISTINCT furniture_key) = 1
                    THEN MIN(furniture_key) END AS furniture_key
                FROM location_furniture
                GROUP BY owner_key
            )
            SELECT a.acquisition_key, a.source_group_key, a.source_copy_stable_key,
                a.item_stable_key, f.furniture_key, q.reference_stable_key AS quest_key
            FROM item_acquisitions a
            LEFT JOIN furniture f ON f.owner_key = a.acquisition_key
            LEFT JOIN item_acquisition_conditions q ON q.owner_key = a.acquisition_key
              AND q.gate_key = 'stock_unlock' AND q.predicate = 'quest_done'
            WHERE a.kind = 'vendor'
            ORDER BY a.source_group_key, a.source_copy_stable_key, a.item_stable_key, quest_key
        """
        try:
            ItemProvenanceRepository(self.db)
            stock = []
            for row in self._execute_raw(query):
                if not row["source_group_key"] or not row["source_copy_stable_key"]:
                    raise RepositoryError(f"Canonical vendor offer has no copy identity: {row['acquisition_key']}")
                stock.append(
                    VendorStockEntry(
                        vendor_key=str(row["source_group_key"]),
                        copy_key=str(row["source_copy_stable_key"]),
                        furniture_key=str(row["furniture_key"]) if row["furniture_key"] else None,
                        item_key=str(row["item_stable_key"]),
                        quest_key=str(row["quest_key"]) if row["quest_key"] else None,
                    )
                )
            return stock
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve vendor stock: {e}") from e
