"""Spell and skill domain entities."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DbSpell(BaseModel):
    """Spell database entity.

    Attributes contain game data for spells including effects, costs, and requirements.

    Junction-enriched fields:
        - Classes: Populated from SpellClasses junction table

    Note: Repository functions return fully enriched instances.
          Direct construction will have junction fields as None.
    """

    SpellDBIndex: int  # Integer primary key
    Id: str
    SpellName: str
    SpellDesc: str = ""
    Type: str = ""
    Line: str = ""
    RequiredLevel: int = 0
    Classes: Optional[list[str]] = Field(
        default=None,
        description="Class names that can use this spell",
    )
    Aggro: int = 0
    ManaCost: int = 0
    SelfOnly: bool = False
    GroupEffect: bool = False
    TargetDamage: int = 0
    TargetHealing: int = 0
    CasterHealing: int = 0
    InstantEffect: bool = False
    SpellChargeTime: float = 0.0
    Cooldown: float = 0.0
    SpellDurationInTicks: int = 0
    UnstableDuration: bool = False
    StatusEffectMessageOnPlayer: str = ""
    StatusEffectMessageOnNPC: str = ""
    DamageType: str = ""
    ResistModifier: float = 0.0
    ShieldingAmt: int = 0
    Lifetap: bool = False
    HP: int = 0
    AC: int = 0
    Mana: int = 0
    Str: int = 0
    Dex: int = 0
    End: int = 0
    Agi: int = 0
    Wis: int = 0
    Int: int = 0
    Cha: int = 0
    MR: int = 0
    ER: int = 0
    PR: int = 0
    VR: int = 0
    DamageShield: int = 0
    Haste: float = 0.0
    PercentLifesteal: float = 0.0
    AtkRollModifier: int = 0
    XPBonus: float = 0.0
    ReapAndRenew: bool = False
    RootTarget: bool = False
    StunTarget: bool = False
    CharmTarget: bool = False
    BreakOnDamage: bool = False
    TauntSpell: bool = False
    MovementSpeed: float = 0.0
    ApplyToCaster: bool = False
    MaxLevelTarget: int = 0
    SpellRange: float = 0.0
    SimUsable: bool = True
    AddProc: str = ""
    AddProcChance: int = 0
    StatusEffectToApply: str = ""
    ResonateChance: int = 0
    PetToSummonResourceName: str = ""
    PercentManaRestoration: int = 0
    BleedDamagePercent: int = 0
    SpecialDescriptor: str = ""
    ResourceName: str


class Spell(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str = ""
    line: str = ""
    required_level: int = 0
    classes: List[str] = Field(default_factory=list)
    resource_name: str


class DbSkill(BaseModel):
    Id: str
    SkillName: str
    SkillDesc: str = ""
    TypeOfSkill: str = ""
    Cooldown: float = 0.0
    DuelistRequiredLevel: int = 0
    PaladinRequiredLevel: int = 0
    ArcanistRequiredLevel: int = 0
    DruidRequiredLevel: int = 0
    StormcallerRequiredLevel: int = 0
    EffectToApplyId: str = ""
    CastOnTargetId: str = ""
    RequireBow: bool = False
    RequireShield: bool = False
    DamageType: str = ""
    ResourceName: str


def db_spell_to_domain(db: DbSpell) -> Spell:
    return Spell(
        id=db.Id,
        name=db.SpellName,
        description=db.SpellDesc or "",
        type=db.Type or "",
        line=db.Line or "",
        required_level=db.RequiredLevel or 0,
        classes=[],  # to be filled from items that teach, if needed later
        resource_name=db.ResourceName,
    )


__all__ = ["DbSpell", "Spell", "DbSkill", "db_spell_to_domain"]
