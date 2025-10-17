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
                SpawnOnUseResourceName,
                EffectToApplyId,
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
                CastOnTargetId,
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

    def get_skill_by_skill_name(self, skill_name: str) -> Skill | None:
        """Get single skill by skill name.

        Used by: Individual page updates, cross-references

        Args:
            skill_name: SkillName field value (display name)

        Returns:
            Skill entity if found, None otherwise.

        Raises:
            RepositoryError: If query execution fails.
        """
        query = """
            SELECT
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
                SpawnOnUseResourceName,
                EffectToApplyId,
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
                CastOnTargetId,
                SkillAnimName,
                SkillIconName,
                PlayerUses,
                NPCUses
            FROM Skills
            WHERE SkillName = ?
            LIMIT 1
        """

        try:
            rows = self._execute_raw(query, (skill_name,))
            if not rows:
                return None
            return self._row_to_skill(rows[0])
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve skill by skill_name={skill_name}: {e}") from e

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
