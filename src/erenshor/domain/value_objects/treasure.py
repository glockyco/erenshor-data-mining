"""Value objects for treasure hunting: the chest waves and the guardians."""

from dataclasses import dataclass

__all__ = ["ChestWave", "GuardianScaling", "TreasureGuardian"]


@dataclass(frozen=True)
class TreasureGuardian:
    """A character that striking a dug-up treasure chest can spawn."""

    stable_key: str
    name: str
    page: str


@dataclass(frozen=True)
class GuardianScaling:
    """The stats of a guardian when a player of ``player_level`` strikes the chest.

    Every stat is a range because the game rolls it. ``attack`` is the base
    damage per hit and ``attack_delay`` the base swing delay in 1/60 s.
    """

    guardian_stable_key: str
    player_level: int
    level_min: int
    level_max: int
    health_min: int
    health_max: int
    attack_min: int
    attack_max: int
    attack_delay_min: int
    attack_delay_max: int
    ac_min: int
    ac_max: int
    resist_min: int
    resist_max: int


@dataclass(frozen=True)
class ChestWave:
    """A dug-up chest after ``waves_spawned`` waves.

    ``strike_break_chance`` is the chance that a strike then breaks the chest
    open. The next wave fields are None when every strike breaks it.
    """

    waves_spawned: int
    strike_break_chance: float
    next_wave_guardians_min: int | None
    next_wave_guardians_max: int | None
    next_wave_delay_seconds: float | None
