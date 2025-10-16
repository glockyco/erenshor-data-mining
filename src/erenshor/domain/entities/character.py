"""Character domain entities."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from erenshor.domain.value_objects.faction import FactionModifier


class DbCharacter(BaseModel):
    """Character database entity.

    Entity ID semantics:
        - Id: Database row identity (auto-increment). Used for instance-specific
              relationships like dialogs, spells, and coordinates.
        - Guid: Unity prefab identity (hash). Used for prefab-specific relationships
                like spawns, loot tables, and vendor inventories. Multiple character
                instances (e.g., wolves at different spawn points) share the same Guid.

    Note: Both Id and Guid serve distinct purposes and should not be standardized.
    """

    Id: int
    Guid: Optional[str] = None
    ObjectName: Optional[str] = None
    NPCName: str
    MyWorldFaction: Optional[str] = None
    MyFaction: Optional[str] = None
    AggroRange: Optional[float] = 0.0
    AttackRange: Optional[float] = 0.0
    IsPrefab: bool = False
    IsNPC: bool = False
    IsSimPlayer: bool = False
    IsFriendly: bool = False
    IsUnique: bool = False
    IsRare: bool = False
    IsVendor: bool = False
    IsMiningNode: bool = False
    HasStats: bool = False
    HasModifyFaction: bool = False
    Invulnerable: bool = False
    ShoutOnDeath: Optional[str] = None
    QuestCompleteOnDeath: Optional[str] = None
    DestroyOnDeath: bool = False
    Scene: Optional[str] = None
    ZoneName: Optional[str] = None
    X: Optional[float] = None
    Y: Optional[float] = None
    Z: Optional[float] = None
    Level: Optional[int] = 0
    BaseXpMin: Optional[int] = 0
    BaseXpMax: Optional[int] = 0
    BossXpMultiplier: Optional[float] = 1.0
    BaseHP: Optional[int] = 0
    BaseAC: Optional[int] = 0
    BaseMana: Optional[int] = 0
    BaseStr: Optional[int] = 0
    BaseEnd: Optional[int] = 0
    BaseDex: Optional[int] = 0
    BaseAgi: Optional[int] = 0
    BaseInt: Optional[int] = 0
    BaseWis: Optional[int] = 0
    BaseCha: Optional[int] = 0
    BaseRes: Optional[int] = 0
    EffectiveMinMR: Optional[int] = 0
    EffectiveMaxMR: Optional[int] = 0
    EffectiveMinER: Optional[int] = 0
    EffectiveMaxER: Optional[int] = 0
    EffectiveMinPR: Optional[int] = 0
    EffectiveMaxPR: Optional[int] = 0
    EffectiveMinVR: Optional[int] = 0
    EffectiveMaxVR: Optional[int] = 0
    RunSpeed: Optional[float] = 0.0
    BaseLifeSteal: Optional[float] = 0.0
    BaseMHAtkDelay: Optional[float] = 0.0
    BaseOHAtkDelay: Optional[float] = 0.0
    PetSpell: Optional[str] = None
    ProcOnHit: Optional[str] = None
    ProcOnHitChance: Optional[float] = 0.0
    VendorDesc: Optional[str] = None

    # Junction table fields - populated by JunctionEnricher
    AggressiveFactions: Optional[list[str]] = Field(
        default=None,
        description="Faction names from CharacterAggressiveFactions junction table",
    )
    AlliedFactions: Optional[list[str]] = Field(
        default=None,
        description="Faction names from CharacterAlliedFactions junction table",
    )
    AttackSkills: Optional[list[str]] = Field(
        default=None,
        description="Skill IDs from CharacterAttackSkills junction table",
    )
    AttackSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterAttackSpells junction table",
    )
    BuffSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterBuffSpells junction table",
    )
    CCSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterCCSpells junction table",
    )
    FactionModifiers: Optional[list[FactionModifier]] = Field(
        default=None,
        description="Faction modifiers from CharacterFactionModifiers junction table",
    )
    GroupHealSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterGroupHealSpells junction table",
    )
    HealSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterHealSpells junction table",
    )
    TauntSpells: Optional[list[str]] = Field(
        default=None,
        description="Spell IDs from CharacterTauntSpells junction table",
    )
    VendorItems: Optional[list[str]] = Field(
        default=None,
        description="Item names from CharacterVendorItems junction table",
    )


__all__ = ["DbCharacter"]
