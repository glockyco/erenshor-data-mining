"""Spell repository for specialized spell queries."""

from loguru import logger

from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake


class SpellRepository(BaseRepository[Spell]):
    """Repository for spell-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_spells_for_wiki_generation(self) -> list[Spell]:
        """Get all spells for wiki page generation.

        Returns all spells with basic fields populated.

        Filters out spells with blank/missing names (data quality issue).

        Used by: Spell page generators (damage spells, buffs, debuffs, etc.)

        Returns:
            List of Spell entities with basic fields populated.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                SpellDBIndex,
                Id,
                ResourceName,
                SpellName,
                SpellDesc,
                SpecialDescriptor,
                Type,
                Line,
                RequiredLevel,
                ManaCost,
                SimUsable,
                Aggro,
                SpellChargeTime,
                Cooldown,
                SpellDurationInTicks,
                UnstableDuration,
                InstantEffect,
                SpellRange,
                SelfOnly,
                MaxLevelTarget,
                GroupEffect,
                CanHitPlayers,
                ApplyToCaster,
                TargetDamage,
                TargetHealing,
                CasterHealing,
                ShieldingAmt,
                Lifetap,
                DamageType,
                ResistModifier,
                AddProcStableKey,
                AddProcChance,
                HP,
                AC,
                Mana,
                PercentManaRestoration,
                MovementSpeed,
                Str,
                Dex,
                "End",
                Agi,
                Wis,
                Int,
                Cha,
                MR,
                ER,
                PR,
                VR,
                DamageShield,
                Haste,
                PercentLifesteal,
                AtkRollModifier,
                BleedDamagePercent,
                RootTarget,
                StunTarget,
                CharmTarget,
                CrowdControlSpell,
                BreakOnDamage,
                BreakOnAnyAction,
                TauntSpell,
                PetToSummonStableKey,
                StatusEffectToApplyStableKey,
                ReapAndRenew,
                ResonateChance,
                XPBonus,
                AutomateAttack,
                WornEffect,
                SpellChargeFXIndex,
                SpellResolveFXIndex,
                SpellIconName,
                ShakeDur,
                ShakeAmp,
                ColorR,
                ColorG,
                ColorB,
                ColorA,
                StatusEffectMessageOnPlayer,
                StatusEffectMessageOnNPC
            FROM Spells
            WHERE COALESCE(SpellName, '') != ''
              AND COALESCE(ResourceName, '') != ''
            ORDER BY SpellName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            spells = [self._row_to_spell(row) for row in rows]
            logger.debug(f"Retrieved {len(spells)} spells for wiki generation")
            return spells
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spells for wiki: {e}") from e

    def get_spell_by_stable_key(self, stable_key: str) -> Spell | None:
        """Get single spell by stable key.

        Used by: Item enrichment (items reference spells via stable keys)

        Args:
            stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            Spell entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                SpellDBIndex,
                SpellName,
                SpellDesc
            FROM Spells
            WHERE StableKey = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                return None
            return self._row_to_spell(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spell by stable_key={stable_key}: {e}") from e

    def get_spell_classes(self, stable_key: str) -> list[str]:
        """Get class restrictions for a spell from SpellClasses junction table.

        Args:
            stable_key: Spell stable key (format: 'spell:resource_name')

        Returns:
            List of class names that can use this spell (e.g., ["Arcanist", "Duelist"]).
            Empty list means no class restrictions (item effects, enemy abilities, etc.).

        Raises:
            RepositoryError: If query execution fails
        """
        query = """
            SELECT ClassName
            FROM SpellClasses
            WHERE SpellStableKey = ?
            ORDER BY ClassName
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            classes = [row["ClassName"] for row in rows]
            logger.debug(f"Retrieved {len(classes)} class restrictions for spell {stable_key}")
            return classes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve spell classes for {stable_key}: {e}") from e

    def _row_to_spell(self, row: dict[str, object]) -> Spell:
        """Convert database row to Spell entity.

        Args:
            row: sqlite3.Row object with Spell columns.

        Returns:
            Spell domain entity.
        """
        # Convert row to dict and transform PascalCase keys to snake_case
        data = {pascal_to_snake(key): value for key, value in dict(row).items()}

        # Pydantic will handle validation and type conversion
        return Spell.model_validate(data)
