"""What an NPC's stats become when it spawns.

``NPC.Start`` rolls the level variance, applies ``DamageBalanceFactor`` to the
base attack, and scales HP. ``Stats.Start`` rolls the resists and raises the
base attack to the level. Both scripts have the default execution order, so
Unity calls their ``Start`` in the order of the components on the GameObject,
which differs between prefabs (exported as ``stats_starts_before_npc``). That
order decides which level the resists and the attack floor see, and whether
the balance factor applies before or after the floor.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

# code-fact: npc.ac_per_level
AC_PER_LEVEL = 15

# code-fact: npc.base_resists
RESIST_ROLL_MIN = 0.5
RESIST_ROLL_MAX = 1.2

# The Class asset that Stats.Start gives a character without one
# (EffectDB.DefaultClass in LoadScene).
DEFAULT_CLASS_RESOURCE_NAME = "DefaultNPC"

_HEALTH_CONSTANT_KEYS = ("ServerHPMod", "HPScale", "Under35HPScale", "Under8HPScale")


def f32(value: float) -> float:
    """Round a value to single precision, as Unity computes with floats."""
    result: float = struct.unpack("f", struct.pack("f", value))[0]
    return result


def round_to_int(value: float) -> int:
    """``Mathf.RoundToInt``: round half to even."""
    return round(value)


def scale(value: int, factor: float) -> int:
    """``Mathf.RoundToInt((float)value * factor)`` in single precision."""
    return round_to_int(f32(f32(float(value)) * f32(factor)))


@dataclass(frozen=True, slots=True)
class SpawnConstants:
    """The exported multipliers that NPC.Start applies."""

    server_hp_mod: float
    hp_scale: float
    under35_hp_scale: float
    under8_hp_scale: float
    damage_balance_factor: float


def load_spawn_constants(conn: sqlite3.Connection) -> SpawnConstants:
    """Read the spawn multipliers from the clean ``game_constants`` table."""
    keys = (*_HEALTH_CONSTANT_KEYS, "DamageBalanceFactor")
    placeholders = ",".join("?" for _ in keys)
    values = {
        str(key): float(value)
        for key, value in conn.execute(f"SELECT key, value FROM game_constants WHERE key IN ({placeholders})", keys)
    }
    missing = [key for key in keys if key not in values]
    if missing:
        raise ValueError(f"the clean game_constants table lacks {', '.join(missing)}")
    return SpawnConstants(
        server_hp_mod=values["ServerHPMod"],
        hp_scale=values["HPScale"],
        under35_hp_scale=values["Under35HPScale"],
        under8_hp_scale=values["Under8HPScale"],
        damage_balance_factor=values["DamageBalanceFactor"],
    )


def balanced_hp(base_hp: int, level: int, constants: SpawnConstants) -> int:
    """Max HP after ``NPC.ApplyBalanceAdjustments`` for an NPC of this level."""
    # code-fact: npc.balance_hp
    hp = scale(base_hp, constants.server_hp_mod)
    hp = scale(hp, constants.hp_scale)
    if 7 < level <= 36:
        hp = scale(hp, constants.under35_hp_scale)
    elif level <= 7:
        hp = scale(hp, constants.under8_hp_scale)
    return max(hp, 1)


def spawn_attack(
    base_attack: int,
    level_before: int,
    level_after: int,
    *,
    stats_starts_first: bool,
    floors_at_level: bool,
    damage_balance_factor: float,
) -> int:
    """Base attack damage of a spawned NPC.

    ``level_before`` is the level before the variance of ``NPC.Start``, and
    ``level_after`` the level after it. ``floors_at_level`` is false for NPCs
    with hand-set resistances, which ``Stats.Start`` leaves alone.
    """
    attack = base_attack
    if stats_starts_first:
        # code-fact: npc.start_attack_floor
        if floors_at_level and attack < level_before:
            attack = level_before
        # code-fact: npc.start_damage_balance
        return max(1, scale(attack, damage_balance_factor))
    attack = max(1, scale(attack, damage_balance_factor))
    if floors_at_level and attack < level_after:
        attack = level_after
    return attack


def resist_level(level_before: int, level_after: int, *, stats_starts_first: bool) -> int:
    """The level that ``Stats.Start`` rolls the resists from."""
    return level_before if stats_starts_first else level_after


def resist_range(level: int) -> tuple[int, int]:
    """The lowest and highest resist that ``Stats.ReturnBaseResitances`` rolls for this level."""
    return (
        round_to_int(f32(f32(float(level)) * f32(RESIST_ROLL_MIN))),
        round_to_int(f32(f32(float(level)) * f32(RESIST_ROLL_MAX))),
    )


def armor_class(level: int, hard_set_ac: int, mitigation_bonus: float) -> int:
    """NPC AC from ``Stats.CalcStats`` without status effects."""
    base = hard_set_ac if hard_set_ac != 0 else level * AC_PER_LEVEL
    # code-fact: npc.ac_class_mitigation
    return scale(base, mitigation_bonus)


def class_mitigation(conn: sqlite3.Connection, class_resource_name: str | None) -> float:
    """MitigationBonus of a character's class, or of the default class when it has none."""
    name = class_resource_name or DEFAULT_CLASS_RESOURCE_NAME
    row = conn.execute("SELECT mitigation_bonus FROM classes WHERE resource_name = ?", (name,)).fetchone()
    if row is None:
        raise ValueError(f"the clean classes table has no class {name!r}")
    return float(row[0])
