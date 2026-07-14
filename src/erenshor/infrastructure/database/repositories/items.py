"""Item repository for specialized item queries."""

from typing import cast

from loguru import logger

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, UsedInInfo
from erenshor.domain.value_objects.wiki_link import ItemLink, StandardLink
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

_SMITHING_FACT_ID = "smithing.upgrade_ids"
_SMITHING_FACT_KEY = "strings"
_SMITHING_UPGRADE_IDS = ("31377423", "2298018", "2265228")
_SMITHING_FUEL_ID = "46289586"
_SMITHING_REFERENCED_IDS = (*_SMITHING_UPGRADE_IDS, _SMITHING_FUEL_ID)
_SMITHING_SPECIAL_TARGET_IDS = {
    "46289586": ("31377423", "upgrade_material"),
    "2298018": ("2298018", "blessing_removal_material"),
}


def _item_link_from_row(row: object, prefix: str = "") -> ItemLink:
    """Build an ItemLink from a row, with optional column prefix."""
    d = dict(row)  # type: ignore[call-overload]
    pn = f"{prefix}display_name"
    pw = f"{prefix}wiki_page_name"
    pi = f"{prefix}image_name"
    ps = f"{prefix}stable_key"
    return ItemLink(
        page_title=str(d[pw]) if d.get(pw) else None,
        display_name=str(d[pn]),
        image_name=str(d[pi]) if d.get(pi) else None,
        stable_key=str(d[ps]) if d.get(ps) else None,
    )


class ItemRepository(BaseRepository[Item]):
    """Repository for item-specific database queries.

    All queries target the clean snake_case database written by ``extract build``.
    """

    def get_items_for_wiki_generation(self) -> list[Item]:
        """Get all items for wiki page generation.

        The clean DB already excludes blank-named items.

        Returns:
            List of Item entities ordered by item_name.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                stable_key,
                item_name,
                display_name,
                wiki_page_name,
                image_name,
                lore,
                required_slot,
                this_weapon_type,
                item_level,
                weapon_dly,
                shield,
                weapon_proc_chance,
                weapon_proc_on_hit_stable_key,
                is_wand,
                wand_range,
                wand_proc_chance,
                wand_effect_stable_key,
                wand_bolt_color_r,
                wand_bolt_color_g,
                wand_bolt_color_b,
                wand_bolt_color_a,
                wand_bolt_speed,
                wand_attack_sound_name,
                is_bow,
                bow_effect_stable_key,
                bow_proc_chance,
                bow_range,
                bow_arrow_speed,
                bow_attack_sound_name,
                item_effect_on_click_stable_key,
                item_skill_use_stable_key,
                teach_spell_stable_key,
                teach_skill_stable_key,
                aura_stable_key,
                worn_effect_stable_key,
                spell_cast_time,
                assign_quest_on_read_stable_key,
                complete_on_read_stable_key,
                template,
                template_ingredient_ids,
                template_reward_ids,
                item_value,
                sell_value,
                stackable,
                disposable,
                is_unique,
                relic,
                no_trade_no_destroy,
                player_cannot_sell,
                rare_item,
                is_auctionable,
                book_title,
                mining,
                fuel_source,
                fuel_level,
                sim_players_cant_get,
                attack_sound_name,
                item_icon_name,
                equipment_to_activate,
                hide_hair_when_equipped,
                hide_head_when_equipped
            FROM items
            WHERE COALESCE(wiki_page_name, '') != ''
            ORDER BY item_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            items = [Item.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(items)} items for wiki generation")
            return items
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items for wiki: {e}") from e

    def get_item_classes(self, stable_key: str) -> list[str]:
        """Get class restrictions for an item.

        Args:
            stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of class names that can equip this item.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT class_name
            FROM item_classes
            WHERE item_stable_key = ?
            ORDER BY class_name
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            classes = [str(row["class_name"]) for row in rows]
            logger.debug(f"Retrieved {len(classes)} class restrictions for item {stable_key}")
            return classes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item classes for {stable_key}: {e}") from e

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        """Get all quality variants for an item.

        Args:
            stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of ItemStats entities ordered by quality (Normal, Improved +1 through
            Improved +5, Blessed, Ascended).

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT
                item_stable_key,
                quality,
                weapon_dmg,
                hp,
                ac,
                mana,
                str,
                end,
                dex,
                agi,
                int,
                wis,
                cha,
                res,
                mr,
                er,
                pr,
                vr,
                str_scaling,
                end_scaling,
                dex_scaling,
                agi_scaling,
                int_scaling,
                wis_scaling,
                cha_scaling,
                resist_scaling,
                mitigation_scaling
            FROM item_stats
            WHERE item_stable_key = ?
            ORDER BY
                CASE quality
                    WHEN 'Normal' THEN 1
                    WHEN 'Improved +1' THEN 2
                    WHEN 'Improved +2' THEN 3
                    WHEN 'Improved +3' THEN 4
                    WHEN 'Improved +4' THEN 5
                    WHEN 'Improved +5' THEN 6
                    WHEN 'Blessed' THEN 7
                    WHEN 'Ascended' THEN 8
                    ELSE 9
                END
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            stats = [ItemStats.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(stats)} stat variants for item '{stable_key}'")
            return stats
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stats for item '{stable_key}': {e}") from e

    def get_items_producing_item(self, item_stable_key: str) -> list[ItemLink]:
        """Get items (molds) that produce the given item via crafting.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of ItemLink objects for molds that produce this item.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT i.stable_key, i.display_name, i.wiki_page_name, i.image_name
            FROM items i
            JOIN crafting_rewards cr ON i.stable_key = cr.recipe_item_stable_key
            WHERE cr.reward_item_stable_key = ?
            ORDER BY i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items producing '{item_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items producing '{item_stable_key}': {e}") from e

    def get_items_requiring_item(self, item_stable_key: str) -> list[ItemLink]:
        """Get items (molds) that require the given item as a crafting component.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of ItemLink objects for molds requiring this item.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT i.stable_key, i.display_name, i.wiki_page_name, i.image_name
            FROM items i
            JOIN crafting_recipes cr ON i.stable_key = cr.recipe_item_stable_key
            WHERE cr.material_item_stable_key = ?
            ORDER BY i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items requiring '{item_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items requiring '{item_stable_key}': {e}") from e

    def get_crafting_recipe(self, item_stable_key: str) -> CraftingRecipe | None:
        """Get complete crafting recipe for a mold item.

        Returns a CraftingRecipe with pre-built ItemLink objects for all materials
        and results, ordered by slot number.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            CraftingRecipe with materials and results, or None if no recipe exists.

        Raises:
            RepositoryError: If query execution fails
        """
        materials_query = """
            SELECT
                cr.material_quantity,
                cr.material_slot,
                i.stable_key,
                i.display_name,
                i.wiki_page_name,
                i.image_name
            FROM crafting_recipes cr
            JOIN items i ON i.stable_key = cr.material_item_stable_key
            WHERE cr.recipe_item_stable_key = ?
            ORDER BY cr.material_slot
        """

        rewards_query = """
            SELECT
                cr.reward_quantity,
                cr.reward_slot,
                i.stable_key,
                i.display_name,
                i.wiki_page_name,
                i.image_name
            FROM crafting_rewards cr
            JOIN items i ON i.stable_key = cr.reward_item_stable_key
            WHERE cr.recipe_item_stable_key = ?
            ORDER BY cr.reward_slot
        """

        try:
            materials_rows = self._execute_raw(materials_query, (item_stable_key,))
            rewards_rows = self._execute_raw(rewards_query, (item_stable_key,))

            if not materials_rows and not rewards_rows:
                return None

            materials = [(_item_link_from_row(row), int(row["material_quantity"])) for row in materials_rows]
            results = [(_item_link_from_row(row), int(row["reward_quantity"])) for row in rewards_rows]

            logger.debug(
                f"Retrieved recipe for '{item_stable_key}': {len(materials)} materials, {len(results)} results"
            )
            return CraftingRecipe(materials=materials, results=results)
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve recipe for '{item_stable_key}': {e}") from e

    def get_obtainable_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]:
        """Get items (spell scrolls) that teach the given spell and are obtainable.

        An item is obtainable if it can be acquired through at least one in-game
        method (drop, vendor, quest reward, dialog reward, etc.).

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            spell_stable_key: Spell stable key

        Returns:
            List of ItemLink objects for obtainable items that teach this spell.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT i.stable_key, i.display_name, i.wiki_page_name, i.image_name
            FROM items i
            WHERE i.teach_spell_stable_key = ?
              AND (
                EXISTS (SELECT 1 FROM loot_drops WHERE item_stable_key = i.stable_key AND drop_probability > 0.0)
                OR EXISTS (SELECT 1 FROM character_vendor_items WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM quest_variants WHERE item_on_complete_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM character_dialogs WHERE give_item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM water_fishables WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM mining_node_items WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM crafting_rewards WHERE reward_item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM item_bags WHERE item_stable_key = i.stable_key)
              )
            ORDER BY i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} obtainable items that teach spell '{spell_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get obtainable teaching items for spell '{spell_stable_key}': {e}") from e

    def get_obtainable_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]:
        """Get items (skill books) that teach the given skill and are obtainable.

        An item is obtainable if it can be acquired through at least one in-game
        method (drop, vendor, quest reward, dialog reward, etc.).

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            skill_stable_key: Skill stable key

        Returns:
            List of ItemLink objects for obtainable items that teach this skill.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT i.stable_key, i.display_name, i.wiki_page_name, i.image_name
            FROM items i
            WHERE i.teach_skill_stable_key = ?
              AND (
                EXISTS (SELECT 1 FROM loot_drops WHERE item_stable_key = i.stable_key AND drop_probability > 0.0)
                OR EXISTS (SELECT 1 FROM character_vendor_items WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM quest_variants WHERE item_on_complete_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM character_dialogs WHERE give_item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM water_fishables WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM mining_node_items WHERE item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM crafting_rewards WHERE reward_item_stable_key = i.stable_key)
                OR EXISTS (SELECT 1 FROM item_bags WHERE item_stable_key = i.stable_key)
              )
            ORDER BY i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (skill_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} obtainable items that teach skill '{skill_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get obtainable teaching items for skill '{skill_stable_key}': {e}") from e

    def get_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]:
        """Get items (spell scrolls) that teach the given spell.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            spell_stable_key: Spell stable key

        Returns:
            List of ItemLink objects for items that teach this spell.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT stable_key, display_name, wiki_page_name, image_name
            FROM items
            WHERE teach_spell_stable_key = ?
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items that teach spell '{spell_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get teaching items for spell '{spell_stable_key}': {e}") from e

    def get_items_with_spell_effect(self, spell_stable_key: str) -> list[ItemLink]:
        """Get items that grant the given spell/skill as an effect.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            spell_stable_key: Spell stable key

        Returns:
            List of ItemLink objects for items with this spell as an effect.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT stable_key, display_name, wiki_page_name, image_name
            FROM items
            WHERE
                weapon_proc_on_hit_stable_key = ? OR
                wand_effect_stable_key = ? OR
                bow_effect_stable_key = ? OR
                item_effect_on_click_stable_key = ? OR
                item_skill_use_stable_key = ? OR
                aura_stable_key = ? OR
                worn_effect_stable_key = ?
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,) * 7)
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items with ability effect '{spell_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get items with ability effect '{spell_stable_key}': {e}") from e

    def get_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]:
        """Get items (skill books) that teach the given skill.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            skill_stable_key: Skill stable key

        Returns:
            List of ItemLink objects for items that teach this skill.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT stable_key, display_name, wiki_page_name, image_name
            FROM items
            WHERE teach_skill_stable_key = ?
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (skill_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items that teach skill '{skill_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get teaching items for skill '{skill_stable_key}': {e}") from e

    def get_items_with_skill_effect(self, skill_stable_key: str) -> list[ItemLink]:
        """Get items that grant the given skill as an effect.

        Returns pre-built ItemLink objects sorted by display name.

        Args:
            skill_stable_key: Skill stable key

        Returns:
            List of ItemLink objects for items with this skill as an effect.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT stable_key, display_name, wiki_page_name, image_name
            FROM items
            WHERE item_skill_use_stable_key = ?
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (skill_stable_key,))
            links = [_item_link_from_row(row) for row in rows]
            logger.debug(f"Found {len(links)} items with skill effect '{skill_stable_key}'")
            return links
        except Exception as e:
            raise RepositoryError(f"Failed to get items with skill effect '{skill_stable_key}': {e}") from e

    def get_item_drops(self, source_item_stable_key: str) -> list[tuple[ItemLink, float, bool]]:
        """Get items that can drop from using this item (e.g., fossil).

        Returns pre-built ItemLink objects with drop probability and whether the
        source guarantees one drop from its pool.

        Args:
            source_item_stable_key: Item stable key of the source item

        Returns:
            List of (ItemLink, drop_probability, is_guaranteed) tuples sorted by
            drop probability descending, then name. Only drops whose item exists
            with a display name are returned.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT i.stable_key, i.display_name, i.wiki_page_name, i.image_name,
                   id.drop_probability, id.is_guaranteed
            FROM item_drops id
            JOIN items i ON i.stable_key = id.dropped_item_stable_key
            WHERE id.source_item_stable_key = ?
              AND i.display_name IS NOT NULL
            ORDER BY id.drop_probability DESC, i.display_name COLLATE NOCASE, id.dropped_item_stable_key
        """

        try:
            rows = self._execute_raw(query, (source_item_stable_key,))
            result = [
                (_item_link_from_row(row), float(row["drop_probability"]), bool(row["is_guaranteed"])) for row in rows
            ]
            logger.debug(f"Found {len(result)} item drops for '{source_item_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get item drops for '{source_item_stable_key}': {e}") from e

    def get_item_sources(self, item_stable_key: str) -> list[tuple[StandardLink, float]]:
        """Get items that can drop this item (e.g., fossils that produce this item).

        Returns StandardLink objects (not ItemLink) because these appear in the
        |source= field of the {{Item}} infobox where [[links]] are expected.

        Args:
            item_stable_key: Item stable key of the dropped item

        Returns:
            List of (StandardLink, drop_probability) tuples sorted by probability descending.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT i.display_name, i.wiki_page_name, id.drop_probability
            FROM item_drops id
            JOIN items i ON i.stable_key = id.source_item_stable_key
            WHERE id.dropped_item_stable_key = ?
            ORDER BY id.drop_probability DESC, i.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            result = [
                (
                    StandardLink(
                        page_title=str(row["wiki_page_name"]) if row["wiki_page_name"] else None,
                        display_name=str(row["display_name"]),
                    ),
                    float(row["drop_probability"]),
                )
                for row in rows
            ]
            logger.debug(f"Found {len(result)} item sources for '{item_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get item sources for '{item_stable_key}': {e}") from e

    def is_item_obtainable(self, item_stable_key: str) -> bool:
        """Check if an item is obtainable in the game through any means.

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            True if item can be obtained through any acquisition method

        Raises:
            RepositoryError: If critical query failure occurs
        """
        query = """
            SELECT 1 WHERE EXISTS (
                SELECT 1 FROM loot_drops
                WHERE item_stable_key = ? AND drop_probability > 0.0
            ) OR EXISTS (
                SELECT 1 FROM character_vendor_items WHERE item_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM quest_variants WHERE item_on_complete_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM character_dialogs WHERE give_item_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM water_fishables WHERE item_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM mining_node_items WHERE item_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM crafting_rewards WHERE reward_item_stable_key = ?
            ) OR EXISTS (
                SELECT 1 FROM item_bags WHERE item_stable_key = ?
            )
        """
        return bool(self._execute_raw(query, (item_stable_key,) * 8))

    def get_recipes_rewarding_item(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return crafting recipe items that produce an item."""
        query = """
            SELECT recipe_item_stable_key, MAX(reward_quantity) AS reward_quantity
            FROM crafting_rewards
            WHERE reward_item_stable_key = ?
            GROUP BY recipe_item_stable_key
            ORDER BY recipe_item_stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                ObtainedFromInfo(
                    source_type="craft",
                    source_key=str(row["recipe_item_stable_key"]),
                    quantity=int(row["reward_quantity"]) if row["reward_quantity"] is not None else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve crafting sources for '{item_stable_key}': {e}") from e

    def get_item_use_sources(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return item sources from item drops and spell-created products."""
        query = """
            WITH source_rows AS (
                SELECT source_item_stable_key, drop_probability AS probability, is_guaranteed
                FROM item_drops
                WHERE dropped_item_stable_key = ?
                UNION ALL
                SELECT source_item_stable_key, NULL AS probability, 0 AS is_guaranteed
                FROM spell_created_items
                WHERE created_item_stable_key = ?
            )
            SELECT source_item_stable_key, MAX(probability) AS probability, MAX(is_guaranteed) AS is_guaranteed
            FROM source_rows
            GROUP BY source_item_stable_key
            ORDER BY source_item_stable_key
        """
        try:
            rows = self._execute_raw(query, (item_stable_key, item_stable_key))
            return [
                ObtainedFromInfo(
                    source_type="item_use",
                    source_key=str(row["source_item_stable_key"]),
                    probability=float(row["probability"]) if row["probability"] is not None else None,
                    is_guaranteed=bool(row["is_guaranteed"]),
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item-use sources for '{item_stable_key}': {e}") from e

    def get_classes_starting_with_item(self, item_stable_key: str) -> list[ObtainedFromInfo]:
        """Return playable classes whose starting inventory includes an item."""
        query = """
            SELECT DISTINCT c.class_name
            FROM class_starting_items csi
            JOIN classes c ON c.class_name = csi.class_name
            WHERE csi.item_stable_key = ?
              AND c.class_name != 'Default'
            ORDER BY c.class_name
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [ObtainedFromInfo(source_type="starting", source_key=f"class:{row['class_name']}") for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve starting-item sources for '{item_stable_key}': {e}") from e

    def get_crafting_material_sources(self, item_stable_key: str) -> list[UsedInInfo]:
        """Return recipes that use an item as a crafting material."""
        query = """
            SELECT recipe_item_stable_key, material_quantity, material_slot
            FROM crafting_recipes
            WHERE material_item_stable_key = ?
            ORDER BY recipe_item_stable_key, material_slot
        """
        try:
            rows = self._execute_raw(query, (item_stable_key,))
            return [
                UsedInInfo(
                    use_type="craft_material",
                    target_key=str(row["recipe_item_stable_key"]),
                    quantity=int(row["material_quantity"]) if row["material_quantity"] is not None else None,
                    slot=int(row["material_slot"]) if row["material_slot"] is not None else None,
                )
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve crafting uses for '{item_stable_key}': {e}") from e

    def _smithing_special_item_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        """Validate the smithing fact and map StableKeys to their numeric IDs."""
        cached = getattr(self, "_smithing_special_item_maps_cache", None)
        if cached is not None:
            return cast("tuple[dict[str, str], dict[str, str]]", cached)

        try:
            fact_rows = self._execute_raw(
                "SELECT key, value FROM code_facts WHERE fact_id = ?",
                (_SMITHING_FACT_ID,),
            )
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve code fact '{_SMITHING_FACT_ID}': {e}") from e

        if len(fact_rows) != 1 or str(fact_rows[0]["key"]) != _SMITHING_FACT_KEY:
            raise ValueError(f"Smithing code-fact drift: expected {_SMITHING_FACT_ID}[{_SMITHING_FACT_KEY}]")
        fact_value = fact_rows[0]["value"]
        if not isinstance(fact_value, str):
            raise ValueError(f"Smithing code-fact drift: {_SMITHING_FACT_ID} must be text")
        fact_ids = tuple(token.strip() for token in fact_value.split(","))
        if (
            len(fact_ids) != len(set(fact_ids))
            or any(not token for token in fact_ids)
            or set(fact_ids) != set(_SMITHING_UPGRADE_IDS)
        ):
            raise ValueError(
                f"Smithing code-fact drift: {_SMITHING_FACT_ID} expected "
                f"{','.join(_SMITHING_UPGRADE_IDS)}, got {fact_value!r}"
            )

        placeholders = ",".join("?" for _ in _SMITHING_REFERENCED_IDS)
        try:
            item_rows = self._execute_raw(
                f"SELECT id, stable_key FROM items WHERE id IN ({placeholders})",
                _SMITHING_REFERENCED_IDS,
            )
        except Exception as e:
            raise RepositoryError("Failed to resolve smithing code-fact item IDs") from e
        id_to_stable = {str(row["id"]): str(row["stable_key"]) for row in item_rows}
        if set(id_to_stable) != set(_SMITHING_REFERENCED_IDS):
            missing = sorted(set(_SMITHING_REFERENCED_IDS) - set(id_to_stable))
            raise ValueError(f"Smithing code-fact drift: missing item IDs {', '.join(missing)}")
        stable_to_id = {stable_key: item_id for item_id, stable_key in id_to_stable.items()}
        cache = (stable_to_id, id_to_stable)
        self._smithing_special_item_maps_cache = cache
        return cache

    def get_item_smithing_special_uses(self, item_stable_key: str) -> list[UsedInInfo]:
        """Return code-fact-backed smithing uses for a material item."""
        stable_to_id, id_to_stable = self._smithing_special_item_maps()
        item_id = stable_to_id.get(item_stable_key)
        if item_id not in _SMITHING_SPECIAL_TARGET_IDS:
            return []
        target_id, use_type = _SMITHING_SPECIAL_TARGET_IDS[item_id]
        return [UsedInInfo(use_type=use_type, target_key=id_to_stable[target_id])]
