"""Item repository for specialized item queries."""

from loguru import logger

from erenshor.domain.entities.item import Item
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

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
                ItemDBIndex,
                Id,
                ItemName,
                ResourceName,
                Lore,
                RequiredSlot,
                ThisWeaponType,
                Classes,
                ItemLevel,
                WeaponDly,
                Shield,
                WeaponProcChance,
                WeaponProcOnHit,
                IsWand,
                WandRange,
                WandProcChance,
                WandEffect,
                WandBoltColorR,
                WandBoltColorG,
                WandBoltColorB,
                WandBoltColorA,
                WandBoltSpeed,
                WandAttackSoundName,
                IsBow,
                BowEffect,
                BowProcChance,
                BowRange,
                BowArrowSpeed,
                BowAttackSoundName,
                ItemEffectOnClick,
                ItemSkillUse,
                TeachSpell,
                TeachSkill,
                Aura,
                WornEffect,
                SpellCastTime,
                AssignQuestOnRead,
                CompleteOnRead,
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

    def get_item_by_resource_name(self, resource_name: str) -> Item | None:
        """Get single item by resource name.

        Used by: Individual page updates, cross-references

        Args:
            resource_name: ResourceName field value (stable identifier)

        Returns:
            Item entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                ItemDBIndex,
                Id,
                ItemName,
                ResourceName,
                Lore,
                RequiredSlot,
                ThisWeaponType,
                Classes,
                ItemLevel,
                WeaponDly,
                Shield,
                WeaponProcChance,
                WeaponProcOnHit,
                IsWand,
                WandRange,
                WandProcChance,
                WandEffect,
                WandBoltColorR,
                WandBoltColorG,
                WandBoltColorB,
                WandBoltColorA,
                WandBoltSpeed,
                WandAttackSoundName,
                IsBow,
                BowEffect,
                BowProcChance,
                BowRange,
                BowArrowSpeed,
                BowAttackSoundName,
                ItemEffectOnClick,
                ItemSkillUse,
                TeachSpell,
                TeachSkill,
                Aura,
                WornEffect,
                SpellCastTime,
                AssignQuestOnRead,
                CompleteOnRead,
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
            WHERE ResourceName = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (resource_name,))
            if not rows:
                return None
            return self._row_to_item(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve item by resource_name={resource_name}: {e}") from e

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
