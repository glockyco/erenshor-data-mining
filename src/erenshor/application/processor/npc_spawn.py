"""What an NPC's stats become when it spawns.

``NPC.Start`` rolls the level variance, applies ``DamageBalanceFactor`` to the
base attack, and scales HP. ``Stats.Start`` rolls the resists and raises the
base attack to the level. Both scripts have the default execution order, so
the order in which Unity creates a character's components decides which
``Start`` runs first (``start_order``). That order decides which level the
resists and the attack floor see, and whether the balance factor applies
before or after the floor.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Mapping

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


def start_order(listed: str | None, by_file_id: str | None, active_at_load: bool | None) -> tuple[str, ...]:
    """The order in which Unity runs ``Start`` on a character's NPC, Stats, and TestDummy.

    An instantiated prefab starts its components in component list order. A
    scene character starts them in local file ID order when it is active at
    load, and in the reverse order when a script activates it later. In-game
    checks of design D16 of the change adopt-data-backed-wiki established
    these three cases, which are engine behavior rather than game code.
    """
    if by_file_id is None:
        return tuple(listed.split(",")) if listed else ()
    order = tuple(by_file_id.split(","))
    return order if active_at_load else order[::-1]


def starts_before(order: tuple[str, ...], first: str, second: str) -> bool:
    """Whether ``first`` starts before ``second`` in a start order."""
    return first in order and second in order and order.index(first) < order.index(second)


def resist_level(level_before: int, level_after: int, *, stats_starts_first: bool) -> int:
    """The level that ``Stats.Start`` rolls the resists from."""
    return level_before if stats_starts_first else level_after


def resist_range(level: int) -> tuple[int, int]:
    """The lowest and highest resist that ``Stats.ReturnBaseResitances`` rolls for this level."""
    return (
        round_to_int(f32(f32(float(level)) * f32(RESIST_ROLL_MIN))),
        round_to_int(f32(f32(float(level)) * f32(RESIST_ROLL_MAX))),
    )


def armor_class(
    level: int, hard_set_ac: int, mitigation_bonus: float, test_dummy_hand_set_ac: int | None = None
) -> int:
    """NPC AC from ``Stats.CalcStats`` without status effects.

    A training dummy with a hand-set AC overwrites the computed AC with it,
    after the class mitigation.
    """
    # code-fact: npc.test_dummy_ac
    if test_dummy_hand_set_ac:
        return test_dummy_hand_set_ac
    base = hard_set_ac if hard_set_ac != 0 else level * AC_PER_LEVEL
    # code-fact: npc.ac_class_mitigation
    return scale(base, mitigation_bonus)


def attack_ability(level: int, armor_pen_mult: float) -> float:
    """NPC AttackAbility from ``Stats.CalcStats``, in the game's single precision."""
    # code-fact: npc.attack_ability
    ability = f32(float(100 + (level - 1) * 40))
    if level >= 20:
        progress = min(max(f32(f32(float(level) - 20.0) / 20.0), 0.0), 1.0)
        cubic = f32(f32(f32(2.0 * progress) * progress) * progress)
        smooth = f32(f32(f32(3.0 * progress) * progress) - cubic)
        ability = f32(ability + f32(ability * f32(f32(0.33) * smooth)))
    return f32(ability * f32(armor_pen_mult))


def load_class_mitigations(conn: sqlite3.Connection) -> dict[str, float]:
    """The MitigationBonus of each class, by its asset name."""
    return {
        str(name): float(bonus) for name, bonus in conn.execute("SELECT resource_name, mitigation_bonus FROM classes")
    }


def class_mitigation(mitigations: Mapping[str, float], class_resource_name: str | None) -> float:
    """MitigationBonus of a character's class, or of the default class when it has none."""
    name = class_resource_name or DEFAULT_CLASS_RESOURCE_NAME
    if name not in mitigations:
        raise ValueError(f"the clean classes table has no class {name!r}")
    return mitigations[name]
