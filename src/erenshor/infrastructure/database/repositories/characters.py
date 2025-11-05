"""Character repository for specialized character queries."""

from loguru import logger

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

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
                c.Id,
                c.CoordinateId,
                c.Guid,
                c.ObjectName,
                c.NPCName,
                c.MyWorldFaction,
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
                c.PetSpell,
                c.ProcOnHit,
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
            character_ids = [char.id for char in characters]
            if character_ids:
                faction_modifiers_map = self._get_faction_modifiers_for_characters(character_ids)
                for char in characters:
                    char.faction_modifiers = faction_modifiers_map.get(char.id, [])

            logger.debug(f"Retrieved {len(characters)} characters for wiki generation")
            return characters
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve characters for wiki: {e}") from e

    def get_character_by_object_name(self, object_name: str) -> Character | None:
        """Get single character by object name.

        Used by: Individual page updates, cross-references

        Args:
            object_name: ObjectName field value (stable identifier)

        Returns:
            Character entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                Id,
                CoordinateId,
                Guid,
                ObjectName,
                NPCName,
                MyWorldFaction,
                MyFaction,
                AggroRange,
                AttackRange,
                AggressiveTowards,
                Allies,
                IsPrefab,
                IsCommon,
                IsRare,
                IsUnique,
                IsFriendly,
                IsNPC,
                IsSimPlayer,
                IsVendor,
                IsMiningNode,
                HasStats,
                HasDialog,
                HasModifyFaction,
                IsEnabled,
                Invulnerable,
                ShoutOnDeath,
                QuestCompleteOnDeath,
                DestroyOnDeath,
                Level,
                BaseXpMin,
                BaseXpMax,
                BossXpMultiplier,
                BaseHP,
                BaseAC,
                BaseMana,
                BaseStr,
                BaseEnd,
                BaseDex,
                BaseAgi,
                BaseInt,
                BaseWis,
                BaseCha,
                BaseRes,
                BaseMR,
                BaseER,
                BasePR,
                BaseVR,
                RunSpeed,
                BaseLifeSteal,
                BaseMHAtkDelay,
                BaseOHAtkDelay,
                EffectiveHP,
                EffectiveAC,
                EffectiveBaseAtkDmg,
                EffectiveAttackAbility,
                EffectiveMinMR,
                EffectiveMaxMR,
                EffectiveMinER,
                EffectiveMaxER,
                EffectiveMinPR,
                EffectiveMaxPR,
                EffectiveMinVR,
                EffectiveMaxVR,
                AttackSkills,
                AttackSpells,
                BuffSpells,
                HealSpells,
                GroupHealSpells,
                CCSpells,
                TauntSpells,
                PetSpell,
                ProcOnHit,
                ProcOnHitChance,
                HandSetResistances,
                HardSetAC,
                BaseAtkDmg,
                OHAtkDmg,
                MinAtkDmg,
                DamageRangeMin,
                DamageRangeMax,
                DamageMult,
                ArmorPenMult,
                PowerAttackBaseDmg,
                PowerAttackFreq,
                HealTolerance,
                LeashRange,
                AggroRegardlessOfLevel,
                Mobile,
                GroupEncounter,
                TreasureChest,
                DoNotLeaveCorpse,
                SetAchievementOnDefeat,
                SetAchievementOnSpawn,
                AggroMsg,
                AggroEmote,
                SpawnEmote,
                GuildName,
                VendorDesc,
                ItemsForSale
            FROM Characters
            WHERE ObjectName = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (object_name,))
            if not rows:
                return None
            character = self._row_to_character(rows[0])

            # Enrich with faction modifiers
            faction_modifiers_map = self._get_faction_modifiers_for_characters([character.id])
            character.faction_modifiers = faction_modifiers_map.get(character.id, [])

            return character
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve character by object_name={object_name}: {e}") from e

    def _get_faction_modifiers_for_characters(self, character_ids: list[int]) -> dict[int, list[FactionModifier]]:
        """Get faction modifiers for multiple characters.

        Args:
            character_ids: List of character IDs to query

        Returns:
            Dict mapping character ID to list of FactionModifiers

        Raises:
            RepositoryError: If query execution fails
        """
        if not character_ids:
            return {}

        # Build query with placeholders for IN clause
        placeholders = ",".join("?" * len(character_ids))
        query = f"""
            SELECT
                CharacterId,
                FactionREFNAME,
                ModifierValue
            FROM CharacterFactionModifiers
            WHERE CharacterId IN ({placeholders})
            ORDER BY CharacterId, FactionREFNAME
        """

        try:
            rows = self._execute_raw(query, tuple(character_ids))

            # Group by character ID
            result: dict[int, list[FactionModifier]] = {}
            for row in rows:
                char_id = row["CharacterId"]
                modifier = FactionModifier(
                    faction_refname=row["FactionREFNAME"],
                    modifier_value=row["ModifierValue"],
                )
                if char_id not in result:
                    result[char_id] = []
                result[char_id].append(modifier)

            logger.debug(f"Retrieved faction modifiers for {len(result)} characters")
            return result
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve faction modifiers: {e}") from e

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
