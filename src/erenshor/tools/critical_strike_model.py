"""Deterministic physical-critical mechanics for Erenshor build 24184286.

The archived build evidence is under
``variants/main/backups/build-24184286/scripts/Assembly-CSharp``:

* ``Stats.cs`` ``CalcStats`` (lines 445-485) derives the current DEX and clamps
  the DEX proficiency modifier to 1..40.
* ``Stats.cs`` ``isCriticalAttack`` (lines 2403-2431) performs one or two
  level-vs-DEX-proficiency trials per critical opportunity, then makes a final
  0..99 roll against the accumulated counter.  The class branches correspond
  to ordinary attacks, Windblade/Duelist, and Stormcaller.
* ``PlayerCombat.cs`` ``HandleDamageResult`` (lines 607-625) applies the
  standard 1.5 critical multiplier and the 10% Crippling Blow proc, whose
  critical multiplier is 3.0 after the extra doubling.
* ``UseSkill.cs`` Reckless Strike's branch (lines 197-214) uses a 1.3
  critical multiplier relative to its normal damage.

The final game roll is represented exactly as ``E[min(counter, 100)] / 100``.
The capped distribution below therefore preserves saturation instead of
clamping an expected counter after the fact.
"""

from enum import StrEnum
from functools import cache
from math import floor, fsum, isclose, isfinite
from struct import Struct
from typing import Final, cast

__all__ = [
    "CRIPPLING_BLOW_CRITICAL_MULTIPLIER",
    "CRIPPLING_BLOW_PROC_CHANCE",
    "MAX_DEX_PROFICIENCY",
    "MAX_PLAYER_LEVEL",
    "MIN_DEX_PROFICIENCY",
    "RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER",
    "STANDARD_CRITICAL_MULTIPLIER",
    "CriticalProfile",
    "crippling_blow_expected_critical_multiplier",
    "critical_hit_chance",
    "critical_opportunities",
    "expected_damage_multiplier",
    "verify_critical_model",
]

# code-fact: critical.dex_proficiency_clamp
MAX_PLAYER_LEVEL: Final[int] = 35
MIN_DEX_PROFICIENCY: Final[int] = 1
MAX_DEX_PROFICIENCY: Final[int] = 40


class CriticalProfile(StrEnum):
    """Physical critical-opportunity profile implemented by the game."""

    ORDINARY = "ordinary"
    STORMCALLER = "stormcaller"
    WINDBLADE = "windblade"


STANDARD_CRITICAL_MULTIPLIER: Final[float] = 1.5
CRIPPLING_BLOW_PROC_CHANCE: Final[float] = 0.1
CRIPPLING_BLOW_CRITICAL_MULTIPLIER: Final[float] = 3.0
RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER: Final[float] = 1.3

_FLOAT32 = Struct("f")


def _validate_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _validate_level(level: int) -> int:
    level = _validate_integer("level", level)
    if not 0 <= level <= MAX_PLAYER_LEVEL:
        raise ValueError(f"level must be between 0 and {MAX_PLAYER_LEVEL}")
    return level


def _validate_dexterity(dexterity: int) -> int:
    dexterity = _validate_integer("dexterity", dexterity)
    if dexterity < 0:
        raise ValueError("dexterity must be nonnegative")
    return dexterity


def _validate_proficiency(dex_proficiency: int) -> int:
    dex_proficiency = _validate_integer("dex_proficiency", dex_proficiency)
    if not MIN_DEX_PROFICIENCY <= dex_proficiency <= MAX_DEX_PROFICIENCY:
        raise ValueError(f"dex_proficiency must be between {MIN_DEX_PROFICIENCY} and {MAX_DEX_PROFICIENCY}")
    return dex_proficiency


def _validate_profile(profile: object) -> CriticalProfile:
    if not isinstance(profile, CriticalProfile):
        raise ValueError(f"profile must be a {CriticalProfile.__name__}")
    return profile


def _validate_nonnegative_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def _validate_chance(critical_chance: float) -> float:
    critical_chance = _validate_nonnegative_float("critical_chance", critical_chance)
    if critical_chance > 1:
        raise ValueError("critical_chance must be between 0 and 1")
    return critical_chance


def _float32(value: float) -> float:
    """Round one value to the game's IEEE 754 single-precision representation."""
    return cast("float", _FLOAT32.unpack(_FLOAT32.pack(value))[0])


def critical_opportunities(dexterity: int, dex_proficiency: int) -> int:
    """Return the number of critical trials for the supplied DEX stats."""
    dexterity = _validate_dexterity(dexterity)
    dex_proficiency = _validate_proficiency(dex_proficiency)
    threshold = _float32(float(dexterity) * _float32(dex_proficiency / 100.0))
    return floor(threshold) + 1


def _apply_trials(probabilities: list[float], trials: int, trial_chance: float) -> None:
    """Advance an in-place 101-bin distribution, with bin 100 absorbing."""
    if trials == 0 or trial_chance == 0:
        return
    failure_chance = 1.0 - trial_chance
    for _ in range(trials):
        probabilities[100] += probabilities[99] * trial_chance
        for counter in range(99, 0, -1):
            probabilities[counter] = probabilities[counter] * failure_chance + probabilities[counter - 1] * trial_chance
        probabilities[0] *= failure_chance


def _expected_capped_counter(trial_groups: tuple[tuple[int, float], ...]) -> float:
    probabilities = [0.0] * 101
    probabilities[0] = 1.0
    for trials, trial_chance in trial_groups:
        _apply_trials(probabilities, trials, trial_chance)
    # Reconstruct the absorbing mass from the nonabsorbing bins.  This removes
    # only floating-point mass drift; the expected value still comes from the
    # capped distribution, never from a clamped expected counter.
    nonabsorbing_mass = fsum(probabilities[counter] for counter in range(100))
    probabilities[100] = max(0.0, 1.0 - nonabsorbing_mass)
    return fsum(counter * probability for counter, probability in enumerate(probabilities))


# code-fact: critical.opportunity_trials
# code-fact: critical.final_roll
@cache
def _critical_hit_chance_cached(
    level: int,
    dexterity: int,
    dex_proficiency: int,
    profile: CriticalProfile,
) -> float:
    opportunities = critical_opportunities(dexterity, dex_proficiency)
    primary_chance = level / (100 - dex_proficiency)
    if profile is CriticalProfile.ORDINARY:
        expected_counter = _expected_capped_counter(((opportunities, primary_chance),))
    elif profile is CriticalProfile.WINDBLADE:
        expected_counter = _expected_capped_counter(((2 * opportunities, primary_chance),))
    else:
        expected_counter = _expected_capped_counter(
            (
                (opportunities, primary_chance),
                (opportunities, 0.4 * primary_chance),
            )
        )
    return expected_counter / 100.0


def critical_hit_chance(
    level: int,
    dexterity: int,
    dex_proficiency: int,
    profile: CriticalProfile = CriticalProfile.ORDINARY,
) -> float:
    """Return exact physical critical probability as a 0..1 fraction."""
    level = _validate_level(level)
    dexterity = _validate_dexterity(dexterity)
    dex_proficiency = _validate_proficiency(dex_proficiency)
    profile = _validate_profile(profile)
    return _critical_hit_chance_cached(level, dexterity, dex_proficiency, profile)


def expected_damage_multiplier(critical_chance: float, critical_multiplier: float) -> float:
    """Return expected damage relative to a noncritical hit."""
    critical_chance = _validate_chance(critical_chance)
    critical_multiplier = _validate_nonnegative_float("critical_multiplier", critical_multiplier)
    return 1.0 + critical_chance * (critical_multiplier - 1.0)


def crippling_blow_expected_critical_multiplier() -> float:
    """Return the conditional multiplier for a critical with Crippling Blow."""
    return (1.0 - CRIPPLING_BLOW_PROC_CHANCE) * STANDARD_CRITICAL_MULTIPLIER + (
        CRIPPLING_BLOW_PROC_CHANCE * CRIPPLING_BLOW_CRITICAL_MULTIPLIER
    )


def verify_critical_model() -> None:
    """Assert build-derived anchors and invariants used by the renderers."""
    assert critical_opportunities(0, 12) == 1
    assert critical_opportunities(8, 12) == 1
    assert critical_opportunities(9, 12) == 2
    assert critical_opportunities(100, 12) == 13

    assert isclose(critical_hit_chance(35, 100, 10), 0.0427777777777778)
    assert isclose(critical_hit_chance(35, 100, 40), 0.23916666666666678)
    assert isclose(critical_hit_chance(35, 100, 40, CriticalProfile.WINDBLADE), 0.4783333333333335)
    assert isclose(critical_hit_chance(35, 200, 40, CriticalProfile.WINDBLADE), 0.9385228688600925)

    ordinary_p12 = critical_hit_chance(35, 100, 12, CriticalProfile.ORDINARY)
    stormcaller_p12 = critical_hit_chance(35, 100, 12, CriticalProfile.STORMCALLER)
    windblade_p12 = critical_hit_chance(35, 100, 12, CriticalProfile.WINDBLADE)
    assert ordinary_p12 < 1.0
    assert isclose(stormcaller_p12 / ordinary_p12, 1.4)
    assert isclose(windblade_p12 / ordinary_p12, 2.0)

    assert expected_damage_multiplier(0.0, STANDARD_CRITICAL_MULTIPLIER) == 1.0
    assert expected_damage_multiplier(0.5, STANDARD_CRITICAL_MULTIPLIER) == 1.25
    assert expected_damage_multiplier(0.1, CRIPPLING_BLOW_CRITICAL_MULTIPLIER) == 1.2
    assert expected_damage_multiplier(0.5, RECKLESS_STRIKE_RELATIVE_CRITICAL_MULTIPLIER) == 1.15
    assert isclose(crippling_blow_expected_critical_multiplier(), 1.65)
