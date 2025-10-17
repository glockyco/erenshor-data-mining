"""Character repository for specialized character queries.

Add query methods here ONLY when actually needed for specific features.

GOOD examples (when to add queries):
- get_vendors() -> for wiki vendor lists
- get_quest_givers() -> for wiki quest giver tables
- get_spawn_data(character_id) -> for wiki spawn location sections
- get_character_abilities(character_id) -> for wiki ability tables

BAD examples (do not add):
- get_by_id() -> use raw SQL when needed
- get_all() -> too broad, query specific subset
- create()/update() -> we're read-only
"""

from loguru import logger

from erenshor.domain.entities.character import Character
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

        Filters out characters with blank/missing object names (data quality issue).

        Used by: Character/Enemy page generators

        Returns:
            List of Character entities with basic fields populated.

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
                ModifyFactions,
                VendorDesc,
                ItemsForSale
            FROM Characters
            WHERE COALESCE(ObjectName, '') != ''
            ORDER BY NPCName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            characters = [self._row_to_character(row) for row in rows]
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
                ModifyFactions,
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
            return self._row_to_character(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve character by object_name={object_name}: {e}") from e

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
