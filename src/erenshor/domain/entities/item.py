"""Item domain entities."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from erenshor.domain.value_objects.crafting import CraftingMaterial, CraftingReward


class DbItem(BaseModel):
    """Item database entity.

    Attributes contain game data for items including stats, effects, and metadata.

    Junction-enriched fields:
        - Classes: Populated from ItemClasses junction table

    Note: Repository functions return fully enriched instances.
          Direct construction will have junction fields as None.
    """

    Id: str
    ItemName: str
    ResourceName: str
    ItemIconName: Optional[str] = None
    ItemLevel: Optional[int] = 0
    ItemValue: Optional[int] = 0  # Buy price
    SellValue: Optional[int] = 0
    Template: Optional[int] = 0
    ThisWeaponType: Optional[str] = None
    WeaponDly: Optional[float] = None
    WeaponProcChance: Optional[int] = None
    WeaponProcOnHit: Optional[str] = None
    IsWand: Optional[bool] = None
    WandRange: Optional[float] = None
    WandProcChance: Optional[int] = None
    WandEffect: Optional[str] = None
    IsBow: Optional[bool] = None
    BowEffect: Optional[str] = None
    BowProcChance: Optional[int] = None
    TeachSpell: Optional[str] = None
    TeachSkill: Optional[str] = None
    ItemEffectOnClick: Optional[str] = None
    Classes: Optional[list[str]] = Field(
        default=None,
        description="Class names that can use this item",
    )
    Lore: Optional[str] = None
    RequiredSlot: Optional[str] = None
    Relic: Optional[bool] = None
    Shield: Optional[bool] = None
    WornEffect: Optional[str] = None
    Disposable: Optional[bool] = None
    CompleteOnRead: Optional[str] = None
    Aura: Optional[str] = None
    CraftingMaterials: Optional[list[CraftingMaterial]] = Field(
        default=None,
        description="Required materials from CraftingRecipes junction table",
    )
    CraftingRewards: Optional[list[CraftingReward]] = Field(
        default=None,
        description="Crafting rewards from CraftingRewards junction table",
    )


class DbItemStats(BaseModel):
    ItemId: str
    Quality: str
    WeaponDmg: Optional[int] = 0
    HP: Optional[int] = 0
    AC: Optional[int] = 0
    Mana: Optional[int] = 0
    Str: Optional[int] = 0
    End: Optional[int] = 0
    Dex: Optional[int] = 0
    Agi: Optional[int] = 0
    Int: Optional[int] = 0
    Wis: Optional[int] = 0
    Cha: Optional[int] = 0
    Res: Optional[int] = 0
    MR: Optional[int] = 0
    ER: Optional[int] = 0
    PR: Optional[int] = 0
    VR: Optional[int] = 0


__all__ = ["DbItem", "DbItemStats"]
