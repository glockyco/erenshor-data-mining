"""NPC level bounds from the initialization rule in NPC.Start."""


def npc_level_bounds(level: int, group_encounter: bool) -> tuple[int, int]:
    """Apply the below-35 variance and the level-one floor after spawn modifiers."""
    # code-fact: npc.level_variance
    variance = 1 if not group_encounter and level < 35 else 0
    # code-fact: npc.level_floor
    return max(1, level - variance), max(1, level + variance)
