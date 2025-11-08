"""Character repository for specialized character queries."""

from loguru import logger

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError
from erenshor.infrastructure.database.row_types import CharacterDropRow

from ._case_utils import pascal_to_snake


class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_characters_for_wiki_generation(self) -> list[Character]:
        """Get all characters (NPCs/enemies) for wiki page generation.

        Returns all characters with basic fields populated. Does NOT include:
        - Abilities (use junction tables: CharacterAttackSpells, etc.)
        - Loot tables (use LootDrops table)
        - Spawn points (use SpawnPointCharacters junction table)
        - Dialogs (use CharacterDialogs table)

        These relationships should be enriched separately after retrieval.

        Filters out:
        - Characters with blank/missing object names (data quality issue)
        - SimPlayer characters (IsSimPlayer = 1)
        - Player character (ObjectName = 'Player')

        Used by: Character/Enemy page generators

        Returns:
            List of Character entities with basic fields populated.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                c.StableKey,
                c.CoordinateId,
                c.Guid,
                c.ObjectName,
                c.NPCName,
                c.MyWorldFactionStableKey,
                c.MyFaction,
                c.AggroRange,
                c.AttackRange,
                c.AggressiveTowards,
                c.Allies,
                c.IsPrefab,
                c.IsCommon,
                c.IsRare,
                c.IsUnique,
                c.IsFriendly,
                c.IsNPC,
                c.IsSimPlayer,
                c.IsVendor,
                c.IsMiningNode,
                c.HasStats,
                c.HasDialog,
                c.HasModifyFaction,
                c.IsEnabled,
                c.Invulnerable,
                c.ShoutOnDeath,
                c.QuestCompleteOnDeath,
                c.DestroyOnDeath,
                c.Level,
                c.BaseXpMin,
                c.BaseXpMax,
                c.BossXpMultiplier,
                c.BaseHP,
                c.BaseAC,
                c.BaseMana,
                c.BaseStr,
                c.BaseEnd,
                c.BaseDex,
                c.BaseAgi,
                c.BaseInt,
                c.BaseWis,
                c.BaseCha,
                c.BaseRes,
                c.BaseMR,
                c.BaseER,
                c.BasePR,
                c.BaseVR,
                c.RunSpeed,
                c.BaseLifeSteal,
                c.BaseMHAtkDelay,
                c.BaseOHAtkDelay,
                c.EffectiveHP,
                c.EffectiveAC,
                c.EffectiveBaseAtkDmg,
                c.EffectiveAttackAbility,
                c.EffectiveMinMR,
                c.EffectiveMaxMR,
                c.EffectiveMinER,
                c.EffectiveMaxER,
                c.EffectiveMinPR,
                c.EffectiveMaxPR,
                c.EffectiveMinVR,
                c.EffectiveMaxVR,
                c.PetSpellStableKey,
                c.ProcOnHitStableKey,
                c.ProcOnHitChance,
                c.HandSetResistances,
                c.HardSetAC,
                c.BaseAtkDmg,
                c.OHAtkDmg,
                c.MinAtkDmg,
                c.DamageRangeMin,
                c.DamageRangeMax,
                c.DamageMult,
                c.ArmorPenMult,
                c.PowerAttackBaseDmg,
                c.PowerAttackFreq,
                c.HealTolerance,
                c.LeashRange,
                c.AggroRegardlessOfLevel,
                c.Mobile,
                c.GroupEncounter,
                c.TreasureChest,
                c.DoNotLeaveCorpse,
                c.SetAchievementOnDefeat,
                c.SetAchievementOnSpawn,
                c.AggroMsg,
                c.AggroEmote,
                c.SpawnEmote,
                c.GuildName,
                c.VendorDesc,
                c.ItemsForSale,
                co.Scene,
                co.X,
                co.Y,
                co.Z
            FROM Characters c
            LEFT JOIN Coordinates co ON co.Id = c.CoordinateId
            WHERE COALESCE(c.ObjectName, '') != ''
                AND COALESCE(c.IsSimPlayer, 0) = 0
                AND c.ObjectName != 'Player'
            ORDER BY c.NPCName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            characters = [self._row_to_character(row) for row in rows]

            # Enrich characters with faction modifiers from junction table
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

        Args:
            stable_keys: List of character stable keys to query

        Returns:
            Dict mapping character stable key to list of FactionModifiers

        Raises:
            RepositoryError: If query execution fails
        """
        if not stable_keys:
            return {}

        # Build query with placeholders for IN clause
        placeholders = ",".join("?" * len(stable_keys))
        query = f"""
            SELECT
                CharacterStableKey,
                FactionStableKey,
                ModifierValue
            FROM CharacterFactionModifiers
            WHERE CharacterStableKey IN ({placeholders})
            ORDER BY CharacterStableKey, FactionStableKey
        """

        try:
            rows = self._execute_raw(query, tuple(stable_keys))

            # Group by character stable key
            result: dict[str, list[FactionModifier]] = {}
            for row in rows:
                char_key = row["CharacterStableKey"]
                modifier = FactionModifier(
                    faction_stable_key=row["FactionStableKey"],
                    modifier_value=row["ModifierValue"],
                )
                if char_key not in result:
                    result[char_key] = []
                result[char_key].append(modifier)

            logger.debug(f"Retrieved faction modifiers for {len(result)} characters")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction modifiers: {e}") from e

    def get_vendors_selling_item(self, item_stable_key: str) -> list[dict[str, object]]:
        """Get characters (vendors) that sell the given item.

        Uses CharacterVendorItems junction table.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of vendor data dicts with fields:
            - StableKey: Character stable key

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT c.StableKey
            FROM Characters c
            JOIN CharacterVendorItems cvi ON c.StableKey = cvi.CharacterStableKey
            WHERE cvi.ItemStableKey = ?
            ORDER BY c.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} vendors selling '{item_stable_key}'")
            return [dict(row) for row in rows]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve vendors for item '{item_stable_key}': {e}") from e

    def get_characters_dropping_item(self, item_stable_key: str) -> list[CharacterDropRow]:
        """Get characters that drop the given item.

        Uses LootDrops table to find characters dropping this item.
        Only includes drops with non-zero probability.

        Used by: Item source enrichment

        Args:
            item_stable_key: Item stable key (format: 'item:resource_name')

        Returns:
            List of dropper data dicts with fields:
            - StableKey: Character stable key
            - DropProbability: Percentage chance to drop

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT DISTINCT
                c.StableKey,
                ld.DropProbability
            FROM Characters c
            JOIN LootDrops ld ON c.StableKey = ld.CharacterStableKey
            WHERE ld.ItemStableKey = ?
                AND COALESCE(ld.DropProbability, 0.0) > 0.0
            ORDER BY c.StableKey
        """

        try:
            rows = self._execute_raw(query, (item_stable_key,))
            logger.debug(f"Found {len(rows)} characters dropping '{item_stable_key}'")
            return [
                {
                    "StableKey": str(row["StableKey"]),
                    "DropProbability": (float(row["DropProbability"]) if row["DropProbability"] is not None else None),
                }
                for row in rows
            ]
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve droppers for item '{item_stable_key}': {e}") from e

    def _row_to_character(self, row: dict[str, object]) -> Character:
        """Convert database row to Character entity.

        Args:
            row: sqlite3.Row object with Character columns.

        Returns:
            Character domain entity.
        """
        # Convert row to dict and transform PascalCase keys to snake_case
        data = {pascal_to_snake(key): value for key, value in dict(row).items()}

        # Pydantic will handle validation and type conversion
        return Character.model_validate(data)
