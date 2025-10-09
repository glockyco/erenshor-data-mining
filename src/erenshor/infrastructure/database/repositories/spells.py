"""Spell repository - database queries for spells and skills."""

from __future__ import annotations

from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Engine

from erenshor.domain.entities import DbItem, DbSkill, DbSpell
from erenshor.infrastructure.database.junction_enricher import JunctionEnricher

__all__ = [
    "get_items_that_teach_spell",
    "get_items_with_effects_for_spell",
    "get_skill_by_id",
    "get_skills",
    "get_spell_by_id",
    "get_spells",
]


def get_spells(engine: Engine, *, obtainable_only: bool = True) -> List[DbSpell]:
    """Fetch all spells from the database with classes pre-populated from junction table.

    The Classes field is populated from the SpellClasses junction table using the
    generic JunctionEnricher.

    Note: SpellClasses.SpellId references Spells.SpellDBIndex (integer PK),
    not Spells.Id (varchar).
    """
    sql = text(
        """
        SELECT
            SpellDBIndex,
            Id,
            SpellName,
            COALESCE(SpellDesc, '') AS SpellDesc,
            COALESCE(Type, '') AS Type,
            COALESCE(Line, '') AS Line,
            COALESCE(RequiredLevel, 0) AS RequiredLevel,
            COALESCE(Aggro, 0) AS Aggro,
            COALESCE(ManaCost, 0) AS ManaCost,
            COALESCE(SelfOnly, 0) AS SelfOnly,
            COALESCE(GroupEffect, 0) AS GroupEffect,
            COALESCE(TargetDamage, 0) AS TargetDamage,
            COALESCE(TargetHealing, 0) AS TargetHealing,
            COALESCE(CasterHealing, 0) AS CasterHealing,
            COALESCE(InstantEffect, 0) AS InstantEffect,
            COALESCE(SpellChargeTime, 0.0) AS SpellChargeTime,
            COALESCE(Cooldown, 0.0) AS Cooldown,
            COALESCE(SpellDurationInTicks, 0) AS SpellDurationInTicks,
            COALESCE(UnstableDuration, 0) AS UnstableDuration,
            COALESCE(StatusEffectMessageOnPlayer, '') AS StatusEffectMessageOnPlayer,
            COALESCE(StatusEffectMessageOnNPC, '') AS StatusEffectMessageOnNPC,
            COALESCE(DamageType, '') AS DamageType,
            COALESCE(ResistModifier, 0.0) AS ResistModifier,
            COALESCE(ShieldingAmt, 0) AS ShieldingAmt,
            COALESCE(Lifetap, 0) AS Lifetap,
            COALESCE(HP, 0) AS HP,
            COALESCE(AC, 0) AS AC,
            COALESCE(Mana, 0) AS Mana,
            COALESCE(Str, 0) AS Str,
            COALESCE(Dex, 0) AS Dex,
            COALESCE(End, 0) AS End,
            COALESCE(Agi, 0) AS Agi,
            COALESCE(Wis, 0) AS Wis,
            COALESCE(Int, 0) AS Int,
            COALESCE(Cha, 0) AS Cha,
            COALESCE(MR, 0) AS MR,
            COALESCE(ER, 0) AS ER,
            COALESCE(PR, 0) AS PR,
            COALESCE(VR, 0) AS VR,
            COALESCE(DamageShield, 0) AS DamageShield,
            COALESCE(Haste, 0.0) AS Haste,
            COALESCE(PercentLifesteal, 0.0) AS PercentLifesteal,
            COALESCE(AtkRollModifier, 0) AS AtkRollModifier,
            COALESCE(XPBonus, 0.0) AS XPBonus,
            COALESCE(ReapAndRenew, 0) AS ReapAndRenew,
            COALESCE(RootTarget, 0) AS RootTarget,
            COALESCE(StunTarget, 0) AS StunTarget,
            COALESCE(CharmTarget, 0) AS CharmTarget,
            COALESCE(BreakOnDamage, 0) AS BreakOnDamage,
            COALESCE(TauntSpell, 0) AS TauntSpell,
            COALESCE(MovementSpeed, 0.0) AS MovementSpeed,
            COALESCE(ApplyToCaster, 0) AS ApplyToCaster,
            COALESCE(MaxLevelTarget, 0) AS MaxLevelTarget,
            COALESCE(SpellRange, 0.0) AS SpellRange,
            COALESCE(SimUsable, 1) AS SimUsable,
            COALESCE(AddProc, '') AS AddProc,
            COALESCE(AddProcChance, 0) AS AddProcChance,
            COALESCE(StatusEffectToApply, '') AS StatusEffectToApply,
            COALESCE(ResonateChance, 0) AS ResonateChance,
            COALESCE(PetToSummonResourceName, '') AS PetToSummonResourceName,
            COALESCE(PercentManaRestoration, 0) AS PercentManaRestoration,
            COALESCE(BleedDamagePercent, 0) AS BleedDamagePercent,
            COALESCE(SpecialDescriptor, '') AS SpecialDescriptor,
            ResourceName
        FROM Spells
        ORDER BY SpellName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
        spells = [DbSpell.model_validate(dict(r)) for r in rows]

    # Enrich with junction table data using generic enricher
    # Populates DbSpell.Classes field from SpellClasses junction table
    enricher = JunctionEnricher(engine)
    enricher.enrich(spells, ["SpellClasses"])

    return spells


def get_spell_by_id(engine: Engine, spell_id: str) -> DbSpell | None:
    """Fetch a spell by ID.

    Note: This function does NOT enrich with junction table data.
    If you need Classes populated, use get_spells() instead.
    """
    sql = text(
        """
        SELECT SpellDBIndex, Id, SpellName,
               COALESCE(SpellDesc, '') AS SpellDesc,
               COALESCE(Type, '') AS Type,
               COALESCE(Line, '') AS Line,
               COALESCE(RequiredLevel, 0) AS RequiredLevel,
               COALESCE(Aggro, 0) AS Aggro,
               COALESCE(ManaCost, 0) AS ManaCost,
               COALESCE(SelfOnly, 0) AS SelfOnly,
               COALESCE(GroupEffect, 0) AS GroupEffect,
               COALESCE(TargetDamage, 0) AS TargetDamage,
               COALESCE(TargetHealing, 0) AS TargetHealing,
               COALESCE(CasterHealing, 0) AS CasterHealing,
               COALESCE(InstantEffect, 0) AS InstantEffect,
               COALESCE(SpellChargeTime, 0.0) AS SpellChargeTime,
               COALESCE(Cooldown, 0.0) AS Cooldown,
               COALESCE(SpellDurationInTicks, 0) AS SpellDurationInTicks,
               COALESCE(UnstableDuration, 0) AS UnstableDuration,
               COALESCE(StatusEffectMessageOnPlayer, '') AS StatusEffectMessageOnPlayer,
               COALESCE(StatusEffectMessageOnNPC, '') AS StatusEffectMessageOnNPC,
               COALESCE(DamageType, '') AS DamageType,
               COALESCE(ResistModifier, 0.0) AS ResistModifier,
               COALESCE(ShieldingAmt, 0) AS ShieldingAmt,
               COALESCE(Lifetap, 0) AS Lifetap,
               COALESCE(HP, 0) AS HP,
               COALESCE(AC, 0) AS AC,
               COALESCE(Mana, 0) AS Mana,
               COALESCE(Str, 0) AS Str,
               COALESCE(Dex, 0) AS Dex,
               COALESCE(End, 0) AS End,
               COALESCE(Agi, 0) AS Agi,
               COALESCE(Wis, 0) AS Wis,
               COALESCE(Int, 0) AS Int,
               COALESCE(Cha, 0) AS Cha,
               COALESCE(MR, 0) AS MR,
               COALESCE(ER, 0) AS ER,
               COALESCE(PR, 0) AS PR,
               COALESCE(VR, 0) AS VR,
               COALESCE(DamageShield, 0) AS DamageShield,
               COALESCE(Haste, 0.0) AS Haste,
               COALESCE(PercentLifesteal, 0.0) AS PercentLifesteal,
               COALESCE(AtkRollModifier, 0) AS AtkRollModifier,
               COALESCE(XPBonus, 0.0) AS XPBonus,
               COALESCE(ReapAndRenew, 0) AS ReapAndRenew,
               COALESCE(RootTarget, 0) AS RootTarget,
               COALESCE(StunTarget, 0) AS StunTarget,
               COALESCE(CharmTarget, 0) AS CharmTarget,
               COALESCE(BreakOnDamage, 0) AS BreakOnDamage,
               COALESCE(TauntSpell, 0) AS TauntSpell,
               COALESCE(MovementSpeed, 0.0) AS MovementSpeed,
               COALESCE(ApplyToCaster, 0) AS ApplyToCaster,
               COALESCE(MaxLevelTarget, 0) AS MaxLevelTarget,
               COALESCE(SpellRange, 0.0) AS SpellRange,
               COALESCE(SimUsable, 1) AS SimUsable,
               COALESCE(AddProc, '') AS AddProc,
               COALESCE(AddProcChance, 0) AS AddProcChance,
               COALESCE(StatusEffectToApply, '') AS StatusEffectToApply,
               COALESCE(ResonateChance, 0) AS ResonateChance,
               COALESCE(PetToSummonResourceName, '') AS PetToSummonResourceName,
               COALESCE(PercentManaRestoration, 0) AS PercentManaRestoration,
               COALESCE(BleedDamagePercent, 0) AS BleedDamagePercent,
               COALESCE(SpecialDescriptor, '') AS SpecialDescriptor,
               ResourceName
        FROM Spells WHERE Id = :sid
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"sid": spell_id}).mappings().first()
    return DbSpell.model_validate(dict(row)) if row else None


def get_skills(engine: Engine) -> List[DbSkill]:
    """Fetch all skills from the database."""
    sql = text(
        """
        SELECT
            Id,
            COALESCE(SkillName, '') AS SkillName,
            COALESCE(SkillDesc, '') AS SkillDesc,
            COALESCE(TypeOfSkill, '') AS TypeOfSkill,
            COALESCE(Cooldown, 0.0) AS Cooldown,
            COALESCE(DuelistRequiredLevel, 0) AS DuelistRequiredLevel,
            COALESCE(PaladinRequiredLevel, 0) AS PaladinRequiredLevel,
            COALESCE(ArcanistRequiredLevel, 0) AS ArcanistRequiredLevel,
            COALESCE(DruidRequiredLevel, 0) AS DruidRequiredLevel,
            COALESCE(StormcallerRequiredLevel, 0) AS StormcallerRequiredLevel,
            COALESCE(EffectToApplyId, '') AS EffectToApplyId,
            COALESCE(CastOnTargetId, '') AS CastOnTargetId,
            COALESCE(RequireBow, 0) AS RequireBow,
            COALESCE(RequireShield, 0) AS RequireShield,
            COALESCE(DamageType, '') AS DamageType,
            ResourceName
        FROM Skills
        WHERE COALESCE(SkillName, '') <> '' AND COALESCE(ResourceName, '') <> ''
        ORDER BY SkillName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [DbSkill.model_validate(dict(r)) for r in rows]


def get_skill_by_id(engine: Engine, skill_id: str) -> DbSkill | None:
    """Fetch a single skill by ID.

    Args:
        engine: Database engine
        skill_id: Skill ID to fetch

    Returns:
        DbSkill object or None if not found
    """
    sql = text(
        """
        SELECT
            Id,
            COALESCE(SkillName, '') AS SkillName,
            COALESCE(SkillDesc, '') AS SkillDesc,
            COALESCE(TypeOfSkill, '') AS TypeOfSkill,
            COALESCE(Cooldown, 0.0) AS Cooldown,
            COALESCE(DuelistRequiredLevel, 0) AS DuelistRequiredLevel,
            COALESCE(PaladinRequiredLevel, 0) AS PaladinRequiredLevel,
            COALESCE(ArcanistRequiredLevel, 0) AS ArcanistRequiredLevel,
            COALESCE(DruidRequiredLevel, 0) AS DruidRequiredLevel,
            COALESCE(StormcallerRequiredLevel, 0) AS StormcallerRequiredLevel,
            COALESCE(EffectToApplyId, '') AS EffectToApplyId,
            COALESCE(CastOnTargetId, '') AS CastOnTargetId,
            COALESCE(RequireBow, 0) AS RequireBow,
            COALESCE(RequireShield, 0) AS RequireShield,
            COALESCE(DamageType, '') AS DamageType,
            ResourceName
        FROM Skills
        WHERE Id = :sid
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"sid": skill_id}).mappings().first()
    return DbSkill.model_validate(dict(row)) if row else None


def get_items_with_effects_for_spell(
    engine: Engine, spell_id: str, *, obtainable_only: bool = False
) -> list[DbItem]:
    """Fetch items that have effects related to a spell."""
    sql = text(
        """
        SELECT Id, ItemName, ResourceName, COALESCE(ItemIconName,'') AS ItemIconName
        FROM Items
        WHERE (
            COALESCE(WeaponProcOnHit,'') LIKE '%' || :sid || '%' OR
            COALESCE(WandEffect,'') LIKE '%' || :sid || '%' OR
            COALESCE(ItemEffectOnClick,'') LIKE '%' || :sid || '%' OR
            COALESCE(ItemSkillUse,'') LIKE '%' || :sid || '%' OR
            COALESCE(Aura,'') LIKE '%' || :sid || '%' OR
            COALESCE(WornEffect,'') LIKE '%' || :sid || '%'
        )
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"sid": spell_id}).mappings().all()
    return [DbItem.model_validate(dict(r)) for r in rows]


def get_items_that_teach_spell(
    engine: Engine, spell_id: str, *, obtainable_only: bool = False
) -> list[DbItem]:
    """Fetch items that teach a spell."""
    sql = text(
        """
        SELECT Id, ItemName, ResourceName, COALESCE(ItemIconName,'') AS ItemIconName
        FROM Items
        WHERE (
            COALESCE(TeachSpell,'') LIKE '%' || :sid || '%' OR
            COALESCE(TeachSkill,'') LIKE '%' || :sid || '%'
        )
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"sid": spell_id}).mappings().all()
    return [DbItem.model_validate(dict(r)) for r in rows]
