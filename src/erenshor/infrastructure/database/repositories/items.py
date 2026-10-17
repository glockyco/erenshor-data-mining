"""Item repository for specialized item queries."""

from collections.abc import Iterable, Mapping

from loguru import logger

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemUse, is_actionable_acquisition
from erenshor.domain.value_objects.wiki_link import ItemLink
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


def _item_link_from_row(row: Mapping[str, object], prefix: str = "") -> ItemLink:
    """Build an ItemLink from a row, with optional column prefix."""
    d: dict[str, object] = dict(row)
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

    def __init__(self, db: DatabaseConnection) -> None:
        super().__init__(db)
        self._provenance_repository: ItemProvenanceRepository | None = None

    def _provenance(self) -> ItemProvenanceRepository:
        try:
            if self._provenance_repository is None:
                self._provenance_repository = ItemProvenanceRepository(self.db)
            return self._provenance_repository
        except Exception as e:
            raise RepositoryError(f"Failed to read canonical item provenance: {e}") from e

    def _acquisitions(self, item_key: str, kinds: set[str]) -> list[ItemAcquisition]:
        try:
            return [fact for fact in self._provenance().get_acquisitions(item_key) if fact.kind in kinds]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve canonical acquisitions for '{item_key}': {e}") from e

    def _uses(self, item_key: str, kinds: set[str]) -> list[ItemUse]:
        try:
            return [fact for fact in self._provenance().get_uses(item_key) if fact.kind in kinds]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve canonical uses for '{item_key}': {e}") from e

    def _uses_targeting(self, target_key: str, kinds: set[str]) -> list[ItemUse]:
        try:
            return [fact for fact in self._provenance().get_uses_targeting(target_key) if fact.kind in kinds]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve canonical uses targeting '{target_key}': {e}") from e

    def _item_links(self, keys: Iterable[str | None]) -> dict[str, ItemLink]:
        item_keys = tuple(sorted({key for key in keys if key is not None}))
        if not item_keys:
            return {}
        placeholders = ",".join("?" for _ in item_keys)
        rows = self._execute_raw(
            "SELECT stable_key, display_name, wiki_page_name, image_name FROM items "
            f"WHERE stable_key IN ({placeholders}) ORDER BY display_name COLLATE NOCASE, stable_key",
            item_keys,
        )
        return {str(row["stable_key"]): _item_link_from_row(row) for row in rows}

    @staticmethod
    def _quantity(fact: ItemAcquisition | ItemUse) -> int | None:
        value = fact.quantity_min
        if fact.quantity_kind != "exact" or value is None or value != fact.quantity_max:
            return None
        if int(value) != value:
            raise RepositoryError(f"Non-integral item quantity in canonical fact: {fact}")
        return int(value)

    def _get_items(self, *, include_blank_pages: bool) -> list[Item]:
        page_filter = "wiki_page_name IS NOT NULL" if include_blank_pages else "COALESCE(wiki_page_name, '') != ''"
        purpose = "link catalog generation" if include_blank_pages else "wiki generation"
        query = f"""
            SELECT
                stable_key,
                item_db_index,
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
                must_be_equipped_to_click,
                rare_item,
                is_auctionable,
                cosmetic_effect,
                book_title,
                mining,
                fuel_source,
                fuel_level,
                sim_players_cant_get,
                furniture_set,
                attack_sound_name,
                item_icon_name,
                equipment_to_activate,
                hide_hair_when_equipped,
                hide_head_when_equipped
            FROM items
            WHERE {page_filter}
            ORDER BY item_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            items = [Item.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(items)} items for {purpose}")
            return items
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items for {purpose}: {e}") from e

    def get_items_for_wiki_generation(self) -> list[Item]:
        """Get all items with nonblank wiki pages for article generation."""
        return self._get_items(include_blank_pages=False)

    def get_items_for_link_catalog(self) -> list[Item]:
        """Get all items with non-null wiki pages for semantic identity validation."""
        return self._get_items(include_blank_pages=True)

    def get_item_renders(self, stable_key: str) -> dict[str | None, str]:
        """Get the titles of an item's approved renders, keyed by the body that each shows.

        The key is None for a render of no one body.

        Raises:
            RepositoryError: If query execution fails
        """
        query = "SELECT body, title FROM item_renders WHERE stable_key = ? ORDER BY title"
        try:
            rows = self._execute_raw(query, (stable_key,))
            return {row["body"]: str(row["title"]) for row in rows}
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item renders for {stable_key}: {e}") from e

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

    def get_classes_that_can_learn_spell(self, spell_stable_key: str) -> list[str]:
        """Get the classes able to learn a spell from a scroll.

        Reading a scroll is gated on the *scroll's* class restrictions
        (``Item.Classes``) plus ``Spell.RequiredLevel``. ``Spell.UsedBy`` only
        drives SimPlayer spell selection and is incomplete for some spells, so
        it must not be used to describe player access.

        Args:
            spell_stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            Union of class names across every scroll teaching this spell.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT ic.class_name
            FROM items i
            JOIN item_classes ic ON ic.item_stable_key = i.stable_key
            WHERE i.teach_spell_stable_key = ?
            ORDER BY ic.class_name
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,))
            classes = [str(row["class_name"]) for row in rows]
            logger.debug(f"Retrieved {len(classes)} learnable classes for spell {spell_stable_key}")
            return classes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve learnable classes for '{spell_stable_key}': {e}") from e

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        """Get all quality variants for an item.

        Args:
            stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of ItemStats entities ordered by quality (Standard, Improved +1 through
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
                    WHEN 'Standard' THEN 1
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

    def get_crafting_recipe(self, item_stable_key: str) -> CraftingRecipe | None:
        """Present native material slots and actionable reward slots without collapsing duplicates."""
        materials = sorted(
            self._uses_targeting(item_stable_key, {"crafting_material"}),
            key=lambda fact: (fact.material_slot if fact.material_slot is not None else -1, fact.use_key),
        )
        rewards = self._uses(item_stable_key, {"crafting_recipe"})
        try:
            rewards.sort(key=lambda fact: (int(fact.variant_key or ""), fact.use_key))
        except ValueError as e:
            raise RepositoryError(f"Missing native crafting reward slot for '{item_stable_key}'") from e
        if not materials and not rewards:
            return None
        links = self._item_links(
            [fact.item_stable_key for fact in materials] + [fact.target_stable_key for fact in rewards]
        )
        outcomes = {
            outcome.acquisition_key: outcome
            for target in sorted({fact.target_stable_key for fact in rewards if fact.target_stable_key is not None})
            for outcome in self._acquisitions(target, {"crafting"})
        }
        material_rows = []
        result_rows = []
        try:
            for fact in materials:
                quantity = self._quantity(fact)
                if quantity is None:
                    raise RepositoryError(f"Missing exact crafting material quantity: {fact.use_key}")
                material_rows.append((links[fact.item_stable_key], quantity))
            for fact in rewards:
                outcome = outcomes.get(fact.outcome_key or "")
                if outcome is None:
                    raise RepositoryError(f"Missing canonical crafting outcome: {fact.use_key}")
                if not is_actionable_acquisition(outcome):
                    continue
                quantity = self._quantity(outcome)
                if quantity is None:
                    raise RepositoryError(f"Missing exact crafting reward quantity: {fact.use_key}")
                result_rows.append((links[fact.target_stable_key or ""], quantity))
        except KeyError as e:
            raise RepositoryError(f"Missing item metadata in recipe '{item_stable_key}': {e}") from e
        return CraftingRecipe(materials=material_rows, results=result_rows)

    def get_obtainable_items_that_teach_spell(self, spell_stable_key: str) -> list[ItemLink]:
        """Return spell-teaching items with a verified current acquisition."""
        return [
            link
            for link in self.get_items_that_teach_spell(spell_stable_key)
            if link.stable_key is not None and self.is_item_obtainable(link.stable_key)
        ]

    def get_obtainable_items_that_teach_skill(self, skill_stable_key: str) -> list[ItemLink]:
        """Return skill-teaching items with a verified current acquisition."""
        return [
            link
            for link in self.get_items_that_teach_skill(skill_stable_key)
            if link.stable_key is not None and self.is_item_obtainable(link.stable_key)
        ]

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

    def is_item_obtainable(self, item_stable_key: str) -> bool:
        """Require a reviewed current item and a satisfiable verified final acquisition."""
        try:
            return self._provenance().get_player_access(item_stable_key) == "verified_player"
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve player access for '{item_stable_key}': {e}") from e
