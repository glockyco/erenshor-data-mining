"""TypedDict definitions for database row types.

These types represent the structure of rows returned from SQLite queries,
providing type safety for repository methods.
"""

from typing import TypedDict


class ItemStatsRow(TypedDict, total=False):
    """Row structure for ItemStats query results."""

    ItemStableKey: str
    Quality: str
    WeaponDmg: int | None
    HP: int | None
    AC: int | None
    Mana: int | None
    Str: int | None
    End: int | None
    Dex: int | None
    Agi: int | None
    Int: int | None
    Wis: int | None
    Cha: int | None
    Res: int | None
    MR: int | None
    ER: int | None
    PR: int | None
    VR: int | None
    StrScaling: float | None
    EndScaling: float | None
    DexScaling: float | None
    AgiScaling: float | None
    IntScaling: float | None
    WisScaling: float | None
    ChaScaling: float | None
    ResistScaling: float | None
    MitigationScaling: float | None


class CharacterDropRow(TypedDict, total=False):
    """Row structure for character drop query results."""

    StableKey: str
    DropProbability: float | None
