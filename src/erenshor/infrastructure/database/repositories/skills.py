"""Skill repository for specialized skill queries."""

from loguru import logger

from erenshor.domain.entities.skill import Skill
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError

from ._case_utils import pascal_to_snake


class SkillRepository(BaseRepository[Skill]):
    """Repository for skill-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.

    All queries should use raw SQL via self._execute_raw().
    """

    def get_skills_for_wiki_generation(self) -> list[Skill]:
        """Get all skills for wiki page generation.

        Returns all skills with basic fields populated.

        Filters out skills with blank/missing names (data quality issue).

        Used by: Skill page generators (combat skills, abilities, etc.)

        Returns:
            List of Skill entities with basic fields populated.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                SkillDBIndex,
                Id,
                ResourceName,
                SkillName,
                SkillDesc,
                TypeOfSkill,
                Cooldown,
                DuelistRequiredLevel,
                PaladinRequiredLevel,
                ArcanistRequiredLevel,
                DruidRequiredLevel,
                StormcallerRequiredLevel,
                ReaverRequiredLevel,
                RequireBehind,
                Require2H,
                RequireDW,
                RequireBow,
                RequireShield,
                SimPlayersAutolearn,
                StanceToUseStableKey,
                AESkill,
                Interrupt,
                SpawnOnUseStableKey,
                EffectToApplyStableKey,
                AffectPlayer,
                AffectTarget,
                SkillRange,
                SkillPower,
                PercentDmg,
                DamageType,
                ScaleOffWeapon,
                ProcWeap,
                ProcShield,
                GuaranteeProc,
                AutomateAttack,
                CastOnTargetStableKey,
                SkillAnimName,
                SkillIconName,
                PlayerUses,
                NPCUses
            FROM Skills
            WHERE COALESCE(SkillName, '') != ''
              AND COALESCE(ResourceName, '') != ''
            ORDER BY SkillName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            skills = [self._row_to_skill(row) for row in rows]
            logger.debug(f"Retrieved {len(skills)} skills for wiki generation")
            return skills
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skills for wiki: {e}") from e

    def get_skill_by_stable_key(self, stable_key: str) -> Skill | None:
        """Get a skill by its stable key.

        Args:
            stable_key: Skill stable key (e.g., "skill:Backstab")

        Returns:
            Skill entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                SkillDBIndex,
                Id,
                ResourceName,
                SkillName,
                SkillDesc,
                TypeOfSkill,
                Cooldown,
                DuelistRequiredLevel,
                PaladinRequiredLevel,
                ArcanistRequiredLevel,
                DruidRequiredLevel,
                StormcallerRequiredLevel,
                RequireBehind,
                Require2H,
                RequireDW,
                RequireBow,
                RequireShield,
                SimPlayersAutolearn,
                AESkill,
                Interrupt,
                SpawnOnUseStableKey,
                EffectToApplyStableKey,
                AffectPlayer,
                AffectTarget,
                SkillRange,
                SkillPower,
                PercentDmg,
                DamageType,
                ScaleOffWeapon,
                ProcWeap,
                ProcShield,
                GuaranteeProc,
                AutomateAttack,
                CastOnTargetStableKey,
                SkillAnimName,
                SkillIconName,
                PlayerUses,
                NPCUses
            FROM Skills
            WHERE StableKey = ?
            ORDER BY SkillName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (stable_key,))
            if not rows:
                logger.debug(f"Skill not found: {stable_key}")
                return None
            return self._row_to_skill(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skill {stable_key}: {e}") from e

    def _row_to_skill(self, row: dict[str, object]) -> Skill:
        """Convert database row to Skill entity.

        Args:
            row: sqlite3.Row object with Skill columns.

        Returns:
            Skill domain entity.
        """
        # Convert row to dict and transform PascalCase keys to snake_case
        data = {pascal_to_snake(key): value for key, value in dict(row).items()}

        # Pydantic will handle validation and type conversion
        return Skill.model_validate(data)

    def get_skills_using_stance(self, stance_stable_key: str) -> list[Skill]:
        """Get all skills that activate a specific stance.

        Used for bidirectional linking on stance wiki pages.

        Args:
            stance_stable_key: Stance stable key (e.g., "stance:Aggressive")

        Returns:
            List of Skill entities that activate this stance.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
                StableKey,
                SkillDBIndex,
                Id,
                ResourceName,
                SkillName,
                SkillDesc,
                TypeOfSkill,
                Cooldown,
                DuelistRequiredLevel,
                PaladinRequiredLevel,
                ArcanistRequiredLevel,
                DruidRequiredLevel,
                StormcallerRequiredLevel,
                ReaverRequiredLevel,
                RequireBehind,
                Require2H,
                RequireDW,
                RequireBow,
                RequireShield,
                SimPlayersAutolearn,
                StanceToUseStableKey,
                AESkill,
                Interrupt,
                SpawnOnUseStableKey,
                EffectToApplyStableKey,
                AffectPlayer,
                AffectTarget,
                SkillRange,
                SkillPower,
                PercentDmg,
                DamageType,
                ScaleOffWeapon,
                ProcWeap,
                ProcShield,
                GuaranteeProc,
                AutomateAttack,
                CastOnTargetStableKey,
                SkillAnimName,
                SkillIconName,
                PlayerUses,
                NPCUses
            FROM Skills
            WHERE StanceToUseStableKey = ?
            ORDER BY SkillName COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, (stance_stable_key,))
            skills = [self._row_to_skill(row) for row in rows]
            logger.debug(f"Retrieved {len(skills)} skills using stance {stance_stable_key}")
            return skills
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skills for stance {stance_stable_key}: {e}") from e
