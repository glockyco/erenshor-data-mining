"""Item repository for specialized item queries."""

from loguru import logger

from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.value_objects.crafting_recipe import CraftingMaterial, CraftingRecipe, CraftingReward
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError
from erenshor.infrastructure.database.row_types import ItemStatsRow

from ._case_utils import pascal_to_snake


class ItemRepository(BaseRepository[Item]):
    """Repository for item-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_items_for_wiki_generation(self) -> list[Item]:
        """Get all items for wiki page generation.

        Returns all items with basic fields populated. Does NOT include:
        - Quality stats (use get_item_stats separately)
        - Class restrictions (use junction table query)
        - Crafting recipes (use junction table query)

        These relationships should be enriched separately after retrieval.

        Filters out items with blank/missing names (data quality issue).

        Used by: Item page generators (weapons, armor, consumables, etc.)

        Returns:
            List of Item entities with basic fields populated.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                ItemDBIndex,
                Id,
                ItemName,
                ResourceName,
                Lore,
                RequiredSlot,
                ThisWeaponType,
                ItemLevel,
                WeaponDly,
                Shield,
                WeaponProcChance,
                WeaponProcOnHitStableKey,
                IsWand,
                WandRange,
                WandProcChance,
                WandEffectStableKey,
                WandBoltColorR,
                WandBoltColorG,
                WandBoltColorB,
                WandBoltColorA,
                WandBoltSpeed,
                WandAttackSoundName,
                IsBow,
                BowEffectStableKey,
                BowProcChance,
                BowRange,
                BowArrowSpeed,
                BowAttackSoundName,
                ItemEffectOnClickStableKey,
                ItemSkillUseStableKey,
                TeachSpellStableKey,
                TeachSkillStableKey,
                AuraStableKey,
                WornEffectStableKey,
                SpellCastTime,
                AssignQuestOnReadStableKey,
                CompleteOnReadStableKey,
                Template,
                TemplateIngredientIds,
                TemplateRewardIds,
                ItemValue,
                SellValue,
                Stackable,
                Disposable,
                "Unique",
                Relic,
                NoTradeNoDestroy,
                BookTitle,
                Mining,
                FuelSource,
                FuelLevel,
                SimPlayersCantGet,
                AttackSoundName,
                ItemIconName,
                EquipmentToActivate,
                HideHairWhenEquipped,
                HideHeadWhenEquipped
            FROM Items
            WHERE COALESCE(ItemName, '') != ''
              AND COALESCE(ResourceName, '') != ''
            ORDER BY ItemName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            items = [self._row_to_item(row) for row in rows]
            logger.debug(f"Retrieved {len(items)} items for wiki generation")
            return items
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items for wiki: {e}") from e

    def get_item_classes(self, stable_key: str) -> list[str]:
        """Get class restrictions for an item from ItemClasses junction table.

        Args:
            stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of class names that can equip this item (e.g., ["Paladin", "Duelist"]).
            Empty list means NO classes can equip (likely a data error).

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT ClassName
            FROM ItemClasses
            WHERE ItemStableKey = ?
            ORDER BY ClassName
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            classes = [row["ClassName"] for row in rows]
            logger.debug(f"Retrieved {len(classes)} class restrictions for item {stable_key}")
            return classes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item classes for {stable_key}: {e}") from e

    def get_item_stats(self, stable_key: str) -> list[ItemStats]:
        """Get all quality variants for an item.

        Returns stats for Normal, Blessed, and Godly quality levels (if they exist).
        Most equipment has 3 variants, but some items (consumables, quest items, etc.)
        have no stats at all.

        Args:
            stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of ItemStats entities ordered by quality (Normal, Blessed, Godly).
            Empty list if item has no stats.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT
                ItemStableKey,
                Quality,
                WeaponDmg,
                HP,
                AC,
                Mana,
                Str,
                "End",
                Dex,
                Agi,
                "Int",
                Wis,
                Cha,
                Res,
                MR,
                ER,
                PR,
                VR,
                StrScaling,
                EndScaling,
                DexScaling,
                AgiScaling,
                IntScaling,
                WisScaling,
                ChaScaling,
                ResistScaling,
                MitigationScaling
            FROM ItemStats
            WHERE ItemStableKey = ?
            ORDER BY
                CASE Quality
                    WHEN 'Normal' THEN 1
                    WHEN 'Blessed' THEN 2
                    WHEN 'Godly' THEN 3
                    ELSE 4
                END
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            stats = [self._row_to_item_stats(row) for row in rows]
            logger.debug(f"Retrieved {len(stats)} stat variants for item '{stable_key}'")
            return stats
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve stats for item '{stable_key}': {e}") from e

    def get_items_producing_item(self, item_stable_key: str) -> list[str]:
        """Get items (molds) that produce the given item via crafting.

        Uses CraftingRewards table to find molds that produce this item.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of item stable keys

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT i.StableKey
            FROM Items i
            JOIN CraftingRewards cr ON i.StableKey = cr.RecipeItemStableKey
            WHERE cr.RewardItemStableKey = ?
            ORDER BY i.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} items producing '{item_stable_key}'")
            return [str(row["StableKey"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items producing '{item_stable_key}': {e}") from e

    def get_items_requiring_item(self, item_stable_key: str) -> list[str]:
        """Get items (molds) that require the given item as a crafting component.

        Uses CraftingRecipes table to find molds requiring this item.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of item stable keys

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT i.StableKey
            FROM Items i
            JOIN CraftingRecipes cr ON i.StableKey = cr.RecipeItemStableKey
            WHERE cr.MaterialItemStableKey = ?
            ORDER BY i.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} items requiring '{item_stable_key}'")
            return [str(row["StableKey"]) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve items requiring '{item_stable_key}': {e}") from e

    def get_crafting_recipe(self, item_stable_key: str) -> CraftingRecipe | None:
        """Get complete crafting recipe for a mold item.

        Retrieves materials and rewards for the given crafting recipe.

        Used by: Item source enrichment (for mold items)

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            Dict with 'materials' and 'rewards' lists, or None if no recipe exists.
            Materials: List of dicts with MaterialItemStableKey, MaterialQuantity, MaterialSlot
            Rewards: List of dicts with RewardItemStableKey, RewardQuantity, RewardSlot

        Raises:
            RepositoryError: If query execution fails
        """
        materials_query = """
            SELECT
                MaterialItemStableKey,
                MaterialQuantity,
                MaterialSlot
            FROM CraftingRecipes
            WHERE RecipeItemStableKey = ?
            ORDER BY MaterialSlot
        """

        rewards_query = """
            SELECT
                RewardItemStableKey,
                RewardQuantity,
                RewardSlot
            FROM CraftingRewards
            WHERE RecipeItemStableKey = ?
            ORDER BY RewardSlot
        """

        try:
            materials_rows = self._execute_raw(materials_query, (item_stable_key,))
            rewards_rows = self._execute_raw(rewards_query, (item_stable_key,))

            if not materials_rows and not rewards_rows:
                return None

            materials: list[CraftingMaterial] = [
                {
                    "MaterialItemStableKey": str(row["MaterialItemStableKey"]),
                    "MaterialQuantity": int(row["MaterialQuantity"]),
                    "MaterialSlot": int(row["MaterialSlot"]),
                }
                for row in materials_rows
            ]

            rewards: list[CraftingReward] = [
                {
                    "RewardItemStableKey": str(row["RewardItemStableKey"]),
                    "RewardQuantity": int(row["RewardQuantity"]),
                    "RewardSlot": int(row["RewardSlot"]),
                }
                for row in rewards_rows
            ]

            logger.debug(
                f"Retrieved recipe for '{item_stable_key}': {len(materials)} materials, {len(rewards)} rewards"
            )
            return {"materials": materials, "rewards": rewards}
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve recipe for '{item_stable_key}': {e}") from e

    def get_items_that_teach_spell(self, spell_stable_key: str) -> list[str]:
        """Get items (spell scrolls, skill books) that teach the given spell.

        Args:
            spell_stable_key: Spell stable key

        Returns:
            List of item stable keys.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT StableKey
            FROM Items
            WHERE TeachSpellStableKey = ?
        """

        try:
            rows = self._execute_raw(query, (spell_stable_key,))
            result = [row["StableKey"] for row in rows]
            logger.debug(f"Found {len(result)} items that teach spell '{spell_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get teaching items for spell '{spell_stable_key}': {e}") from e

    def get_items_with_spell_effect(self, spell_stable_key: str) -> list[str]:
        """Get items that grant the given spell/skill as an effect.

        Searches across all ability effect columns:
        - WeaponProcOnHitStableKey: Weapon procs
        - WandEffectStableKey: Wand effects
        - BowEffectStableKey: Bow procs
        - ItemEffectOnClickStableKey: Click effects (clickable items)
        - ItemSkillUseStableKey: Skill use effects
        - AuraStableKey: Passive auras
        - WornEffectStableKey: Worn effects (armor, jewelry)

        Note: TeachSpellStableKey/TeachSkillStableKey are handled separately by get_items_that_teach_spell.

        Args:
            spell_stable_key: Spell stable key

        Returns:
            List of item stable keys.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT StableKey
            FROM Items
            WHERE
                WeaponProcOnHitStableKey = ? OR
                WandEffectStableKey = ? OR
                BowEffectStableKey = ? OR
                ItemEffectOnClickStableKey = ? OR
                ItemSkillUseStableKey = ? OR
                AuraStableKey = ? OR
                WornEffectStableKey = ?
        """

        try:
            # Pass the stable key 7 times (one for each column)
            params = (spell_stable_key,) * 7
            rows = self._execute_raw(query, params)
            result = [str(row["StableKey"]) for row in rows]
            logger.debug(f"Found {len(result)} items with ability effect '{spell_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get items with ability effect '{spell_stable_key}': {e}") from e

    def get_items_that_teach_skill(self, skill_stable_key: str) -> list[str]:
        """Get items (skill books) that teach the given skill.

        Searches Items.TeachSkillStableKey column for exact match.

        Used by: Skill source enrichment

        Args:
            skill_stable_key: Skill stable key

        Returns:
            List of item stable keys.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT StableKey
            FROM Items
            WHERE TeachSkillStableKey = ?
        """

        try:
            rows = self._execute_raw(query, (skill_stable_key,))
            result = [row["StableKey"] for row in rows]
            logger.debug(f"Found {len(result)} items that teach skill '{skill_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get teaching items for skill '{skill_stable_key}': {e}") from e

    def get_items_with_skill_effect(self, skill_stable_key: str) -> list[str]:
        """Get items that grant the given skill as an effect.

        Searches the ItemSkillUseStableKey column for skills granted as item effects.
        This is different from TeachSkillStableKey (which permanently teaches the skill).

        Used by: Skill source enrichment

        Args:
            skill_stable_key: Skill stable key

        Returns:
            List of item stable keys.

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT StableKey
            FROM Items
            WHERE ItemSkillUseStableKey = ?
        """

        try:
            rows = self._execute_raw(query, (skill_stable_key,))
            result = [str(row["StableKey"]) for row in rows]
            logger.debug(f"Found {len(result)} items with skill effect '{skill_stable_key}'")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to get items with skill effect '{skill_stable_key}': {e}") from e

    def is_item_obtainable(self, item_stable_key: str) -> bool:
        """Check if an item is obtainable in the game through any means.

        An item is considered obtainable if it can be acquired via:
        - Drops from characters (LootDrops.ItemStableKey)
        - Purchase from vendors (CharacterVendorItems.ItemStableKey)
        - Quest rewards (QuestRewards.ItemStableKey)
        - Quest dialog rewards (CharacterDialogs.GiveItemStableKey)
        - Fishing (WaterFishables.ItemStableKey)
        - Mining (MiningNodeItems.ItemStableKey)
        - Crafting recipes (CraftingRewards.ItemStableKey)
        - World item bags (ItemBags.ItemStableKey)

        Used by: Spell classes obtainability check (only show classes if spell is obtainable)

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            True if item can be obtained through any acquisition method

        Raises:
            RepositoryError: If critical query failure occurs
        """
        # Check all acquisition methods in a single query using EXISTS
        obtainability_query = """
            SELECT 1 WHERE EXISTS (
                -- Drops from characters (with positive drop rate)
                SELECT 1 FROM LootDrops
                WHERE ItemStableKey = ? AND COALESCE(DropProbability, 0.0) > 0.0
            ) OR EXISTS (
                -- Purchase from vendors
                SELECT 1 FROM CharacterVendorItems WHERE ItemStableKey = ?
            ) OR EXISTS (
                -- Quest rewards
                SELECT 1 FROM QuestRewards WHERE RewardType = 'Item' AND RewardValue = ?
            ) OR EXISTS (
                -- Quest dialog rewards
                SELECT 1 FROM CharacterDialogs WHERE GiveItemStableKey = ?
            ) OR EXISTS (
                -- Fishing
                SELECT 1 FROM WaterFishables WHERE ItemStableKey = ?
            ) OR EXISTS (
                -- Mining
                SELECT 1 FROM MiningNodeItems WHERE ItemStableKey = ?
            ) OR EXISTS (
                -- Crafting
                SELECT 1 FROM CraftingRewards WHERE RewardItemStableKey = ?
            ) OR EXISTS (
                -- World item bags
                SELECT 1 FROM ItemBags WHERE ItemStableKey = ?
            )
        """
        return bool(self._execute_raw(obtainability_query, (item_stable_key,) * 8))

    def _row_to_item_stats(self, row: ItemStatsRow) -> ItemStats:
        """Convert database row to ItemStats entity.

        Args:
            row: Database row with ItemStats columns

        Returns:
            ItemStats entity
        """
        # Use model_validate with data dict (Pydantic handles aliases)
        return ItemStats.model_validate(
            {
                "item_stable_key": row["ItemStableKey"],
                "quality": row["Quality"],
                "weapon_dmg": row["WeaponDmg"],
                "hp": row["HP"],
                "ac": row["AC"],
                "mana": row["Mana"],
                "str": row["Str"],  # Pydantic alias handles this
                "end": row["End"],  # Pydantic alias handles this
                "dex": row["Dex"],
                "agi": row["Agi"],
                "int": row["Int"],  # Pydantic alias handles this
                "wis": row["Wis"],
                "cha": row["Cha"],
                "res": row["Res"],
                "mr": row["MR"],
                "er": row["ER"],
                "pr": row["PR"],
                "vr": row["VR"],
                "str_scaling": row["StrScaling"],
                "end_scaling": row["EndScaling"],
                "dex_scaling": row["DexScaling"],
                "agi_scaling": row["AgiScaling"],
                "int_scaling": row["IntScaling"],
                "wis_scaling": row["WisScaling"],
                "cha_scaling": row["ChaScaling"],
                "resist_scaling": row["ResistScaling"],
                "mitigation_scaling": row["MitigationScaling"],
            }
        )

    def _row_to_item(self, row: dict[str, object]) -> Item:
        """Convert database row to Item entity.

        Args:
            row: sqlite3.Row object with Item columns.

        Returns:
            Item domain entity.
        """
        # Convert row to dict and transform PascalCase keys to snake_case
        data = {pascal_to_snake(key): value for key, value in dict(row).items()}

        # Pydantic will handle validation and type conversion
        return Item.model_validate(data)
