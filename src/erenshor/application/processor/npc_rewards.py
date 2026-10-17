"""Character XP initialization and reward inputs from shipped Start methods."""

from __future__ import annotations

from dataclasses import dataclass

from erenshor.application.processor.npc_spawn import PLAYER_LEVEL_CAP, training_dummy_level


@dataclass(frozen=True, slots=True)
class InitializedReward:
    """XP initialized by Character.Start and BossXp after NPC.Start."""

    base_experience: int | None
    multiplier: float


def initialized_reward(
    order: tuple[str, ...],
    prefab_level: int,
    designer_multiplier: float,
    *,
    player_level: int | None = None,
    npc_level: int | None = None,
) -> InitializedReward:
    """Replay only level writers and reward initialization in native start order.

    ``npc_level`` is an actual supported NPC variance outcome. Leaving it absent
    retains the clean pipeline's nominal-level stat convention. Missing Character
    order evidence leaves base experience unknown instead of guessing its order.
    """
    level = prefab_level
    multiplier = designer_multiplier
    experience = None
    for component in order:
        if component == "TestDummy":
            dummy_level = training_dummy_level(prefab_level)
            if dummy_level is None:
                if player_level is None:
                    raise ValueError("a player-level training dummy requires the player's level")
                dummy_level = player_level
            level = dummy_level
        elif component == "NPC":
            if npc_level is not None:
                level = npc_level
            # code-fact: npc.start_xp_multiplier
            if level >= 40 and multiplier < 2:
                multiplier = 2.0
        elif component == "Character":
            # code-fact: character.base_xp_per_level
            experience = level * 6
    # code-fact: character.xp_zero_multiplier
    return InitializedReward(experience, 1.0 if multiplier == 0 else multiplier)


def reward_columns(
    order: tuple[str, ...], prefab_level: int | None, designer_multiplier: float | None
) -> dict[str, object]:
    """Project fixed XP fields and exact player-level scaling without false zeros."""
    empty: dict[str, object] = {
        "initialized_xp": None,
        "xp_per_player_level": None,
        "effective_xp_multiplier": None,
    }
    if prefab_level is None or designer_multiplier is None:
        return empty
    follows_player = "TestDummy" in order and training_dummy_level(prefab_level) is None
    levels = range(1, PLAYER_LEVEL_CAP + 1) if follows_player else (None,)
    rewards = [initialized_reward(order, prefab_level, designer_multiplier, player_level=level) for level in levels]
    experiences = [reward.base_experience for reward in rewards]
    multipliers = [reward.multiplier for reward in rewards]
    fixed_xp = experiences[0] if len(set(experiences)) == 1 else None
    per_level = None
    if follows_player and all(xp == level * 6 for level, xp in enumerate(experiences, 1)):
        per_level = 6
    return {
        "initialized_xp": fixed_xp,
        "xp_per_player_level": per_level,
        "effective_xp_multiplier": multipliers[0] if len(set(multipliers)) == 1 else None,
    }


def player_level_bonus(character_level: int, player_level: int) -> int:
    """The death branch bonus before server and reward multipliers."""
    # code-fact: character.xp_player_level_bonus
    if character_level < player_level:
        return 0
    difference = character_level - player_level + int(player_level > 10)
    return min(difference, 5) * character_level
