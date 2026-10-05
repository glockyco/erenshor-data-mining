"""Treasure hunting: the zones a map can point to, the chests, and their guardians.

Reading a treasure map picks a zone from a pool that grows with the reading
level. Digging at the marked site spawns one of four chests, chosen by the
level at the time of digging. Striking that chest spawns waves of guardians
whose level, health, attack, AC, and resists follow from the striking
player's level. ``TreasureChestEvent.SetGuardianStats`` sets them right after
the guardian is instantiated, before ``NPC.Start`` and ``Stats.Start`` run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from .npc_spawn import (
    SpawnConstants,
    armor_class,
    balanced_hp,
    class_mitigation,
    f32,
    load_class_mitigations,
    load_spawn_constants,
    resist_level,
    resist_range,
    round_to_int,
    spawn_attack,
)

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterator

    from .writer import Writer

# code-fact: player.level_cap
PLAYER_LEVEL_CAP = 35

# code-fact: treasure.zone_pool_by_level
# A map read above level 20 adds the zones flagged IsPickableGreater20, and a
# map read above level 30 adds those flagged IsPickableGreater30.
_POOL_LEVEL_ALWAYS = 1
_POOL_LEVEL_GREATER_20 = 21
_POOL_LEVEL_GREATER_30 = 31

# code-fact: treasure.chest_tier_by_level
# Each chest with the dig levels [low, high) that spawn it.
CHEST_DIG_LEVELS = (
    ("character:treasurechest 0-10 1", 0, 10),
    ("character:treasurechest 10-20 1", 10, 20),
    ("character:treasurechest 20-30 1", 20, 30),
    ("character:treasurechest 30-35", 30, 999),
)

# code-fact: treasure.guardian_stats
_GUARDIAN_LEVEL_OFFSETS = range(-3, 2)
_GUARDIAN_MIN_LEVEL = 3
# Base HP per level below each bound, in the game's order, and above the last.
_GUARDIAN_HP_BRACKETS = ((11, 200), (15, 300), (20, 450), (25, 550), (30, 700), (34, 1000))
_GUARDIAN_HP_TOP = 2000
# Below this level the attack is the level minus 0 to 2, from it the level x 1.5.
_GUARDIAN_ATTACK_SCALED_FROM = 30
_GUARDIAN_ATTACK_DROPS = range(3)
_GUARDIAN_ATTACK_SCALE = 1.5
_GUARDIAN_ATTACK_DELAY_BASE = 150
_GUARDIAN_HAND_SET_RESIST_PER_LEVEL = 5

# code-fact: npc.level_variance
_LEVEL_VARIANCE_BELOW = 35

# A strike on the chest rolls Random.Range(0, 10) and breaks the chest open
# when the roll exceeds the durability. The durability starts at 15 and
# drops by 3 with each wave that spawns.
# code-fact: treasure.chest_break_roll
_BREAK_ROLLS = range(10)
# code-fact: treasure.chest_durability_start
_CHEST_DURABILITY_START = 15
# code-fact: treasure.chest_durability_per_wave
_CHEST_DURABILITY_PER_WAVE = 3
# code-fact: treasure.wave_size
_WAVE_GUARDIANS = range(3, 5)
# The ground rumbles for 300 ticks, counted down at 60 per second, before a
# wave appears.
# code-fact: treasure.wave_delay_start
_WAVE_DELAY_TICKS = 300.0
# code-fact: treasure.wave_delay_rate
_WAVE_DELAY_TICKS_PER_SECOND = 60.0

_TREASURE_EVENT_SCRIPT = "TreasureChestEvent"


@dataclass(frozen=True, slots=True)
class GuardianProfile:
    """The prefab values of a guardian that its spawned stats depend on."""

    stable_key: str
    stats_starts_first: bool
    hand_set_resistances: bool
    level_varies: bool
    hard_set_ac: int
    mitigation_bonus: float


@dataclass(frozen=True, slots=True)
class GuardianOutcome:
    """One way a spawned guardian can turn out."""

    level: int
    health: int
    armor_class: int
    attack: int
    resist_min: int
    resist_max: int
    attack_delay: int


def guardian_base_hp(level: int) -> int:
    """Base HP that ``SetGuardianStats`` gives a guardian of this level."""
    # code-fact: treasure.guardian_stats
    for bound, per_level in _GUARDIAN_HP_BRACKETS:
        if level < bound:
            return level * per_level
    return level * _GUARDIAN_HP_TOP


def guardian_base_attacks(level: int) -> tuple[int, ...]:
    """The base attacks that ``SetGuardianStats`` can give a guardian of this level."""
    # code-fact: treasure.guardian_stats
    if level < _GUARDIAN_ATTACK_SCALED_FROM:
        return tuple(level - drop for drop in _GUARDIAN_ATTACK_DROPS)
    return (round_to_int(f32(f32(float(level)) * f32(_GUARDIAN_ATTACK_SCALE))),)


def guardian_outcomes(
    player_level: int, guardian: GuardianProfile, constants: SpawnConstants
) -> Iterator[GuardianOutcome]:
    """Every outcome of the rolls when a player of this level strikes a chest."""
    for offset in _GUARDIAN_LEVEL_OFFSETS:
        set_level = max(_GUARDIAN_MIN_LEVEL, player_level + offset)
        varies = guardian.level_varies and set_level < _LEVEL_VARIANCE_BELOW
        for variance in (-1, 0, 1) if varies else (0,):
            final_level = max(1, set_level + variance)
            health = balanced_hp(guardian_base_hp(set_level), final_level, constants)
            if guardian.hand_set_resistances:
                resist_low = resist_high = set_level * _GUARDIAN_HAND_SET_RESIST_PER_LEVEL
            else:
                resist_low, resist_high = resist_range(
                    resist_level(set_level, final_level, stats_starts_first=guardian.stats_starts_first)
                )
            for base_attack in guardian_base_attacks(set_level):
                yield GuardianOutcome(
                    level=final_level,
                    health=health,
                    armor_class=armor_class(final_level, guardian.hard_set_ac, guardian.mitigation_bonus),
                    attack=spawn_attack(
                        base_attack,
                        set_level,
                        final_level,
                        stats_starts_first=guardian.stats_starts_first,
                        floors_at_level=not guardian.hand_set_resistances,
                        damage_balance_factor=constants.damage_balance_factor,
                    ),
                    resist_min=resist_low,
                    resist_max=resist_high,
                    attack_delay=_GUARDIAN_ATTACK_DELAY_BASE - set_level,
                )


def guardian_scaling_row(player_level: int, guardian: GuardianProfile, constants: SpawnConstants) -> dict[str, object]:
    """The range of each stat over every outcome for a player of this level."""
    outcomes = list(guardian_outcomes(player_level, guardian, constants))
    return {
        "guardian_character_stable_key": guardian.stable_key,
        "player_level": player_level,
        "level_min": min(o.level for o in outcomes),
        "level_max": max(o.level for o in outcomes),
        "health_min": min(o.health for o in outcomes),
        "health_max": max(o.health for o in outcomes),
        "attack_min": min(o.attack for o in outcomes),
        "attack_max": max(o.attack for o in outcomes),
        "attack_delay_min": min(o.attack_delay for o in outcomes),
        "attack_delay_max": max(o.attack_delay for o in outcomes),
        "ac_min": min(o.armor_class for o in outcomes),
        "ac_max": max(o.armor_class for o in outcomes),
        "resist_min": min(o.resist_min for o in outcomes),
        "resist_max": max(o.resist_max for o in outcomes),
    }


def min_reading_level(always: bool, greater_20: bool, greater_30: bool) -> int | None:
    """The lowest player level whose treasure map can point to a zone with these flags."""
    if always:
        return _POOL_LEVEL_ALWAYS
    if greater_20:
        return _POOL_LEVEL_GREATER_20
    if greater_30:
        return _POOL_LEVEL_GREATER_30
    return None


def chest_can_be_dug_in(zone_min_reading_level: int | None, dig_level_high: int) -> bool:
    """Whether a chest dug below ``dig_level_high`` can lie in a zone with this lowest reading level.

    The player reads the map first and digs later, at the same or a higher
    level, so some reading level below ``dig_level_high`` must reach the zone.
    """
    return zone_min_reading_level is not None and zone_min_reading_level < dig_level_high


def strike_break_chance(waves_spawned: int) -> float:
    """The chance that a strike breaks the chest open after this many waves."""
    durability = _CHEST_DURABILITY_START - _CHEST_DURABILITY_PER_WAVE * waves_spawned
    return sum(1 for roll in _BREAK_ROLLS if roll > durability) / len(_BREAK_ROLLS)


def chest_wave_rows() -> list[dict[str, object]]:
    """One row for each number of waves a chest can have spawned.

    Every strike rolls for the break first, also while guardians are alive.
    A strike that does not break the chest starts the next wave only when no
    guardian is alive, and the last row is the first one at which a strike
    always breaks the chest, so no wave follows it.
    """
    rows: list[dict[str, object]] = []
    waves_spawned = 0
    while True:
        chance = strike_break_chance(waves_spawned)
        last = chance >= 1
        rows.append(
            {
                "waves_spawned": waves_spawned,
                "strike_break_chance": chance,
                "next_wave_guardians_min": None if last else _WAVE_GUARDIANS.start,
                "next_wave_guardians_max": None if last else _WAVE_GUARDIANS.stop - 1,
                "next_wave_delay_seconds": None if last else _WAVE_DELAY_TICKS / _WAVE_DELAY_TICKS_PER_SECOND,
            }
        )
        if last:
            return rows
        waves_spawned += 1


def load_guardians(conn: sqlite3.Connection) -> list[GuardianProfile]:
    """The guardians that the treasure chests spawn, from the clean database.

    Each guardian of a wave is a random entry of the chest's guardian list.
    """
    # code-fact: treasure.guardian_pick
    rows = conn.execute(
        """
        SELECT DISTINCT c.stable_key, c.stats_starts_before_npc, c.hand_set_resistances,
               c.group_encounter, c.hard_set_ac, c.class_resource_name
        FROM character_chained_spawns ccs
        JOIN characters c ON c.stable_key = ccs.child_stable_key
        WHERE ccs.source_script = ?
        ORDER BY c.stable_key
        """,
        (_TREASURE_EVENT_SCRIPT,),
    ).fetchall()
    if not rows:
        raise ValueError("no treasure chest links to a guardian in character_chained_spawns")
    mitigations = load_class_mitigations(conn)
    return [
        GuardianProfile(
            stable_key=row["stable_key"],
            stats_starts_first=bool(row["stats_starts_before_npc"]),
            hand_set_resistances=bool(row["hand_set_resistances"]),
            level_varies=not row["group_encounter"],
            hard_set_ac=int(row["hard_set_ac"] or 0),
            mitigation_bonus=class_mitigation(mitigations, row["class_resource_name"]),
        )
        for row in rows
    ]


def process_treasure(raw: sqlite3.Connection, writer: Writer) -> None:
    """Write the treasure zones, the possible chest sites, the chest waves, and the guardian scaling."""
    hunting: list[dict[str, object]] = [
        {
            "zone_name": row["ZoneName"],
            "zone_display_name": row["ZoneDisplayName"],
            "is_pickable_always": row["IsPickableAlways"],
            "is_pickable_greater_20": row["IsPickableGreater20"],
            "is_pickable_greater_30": row["IsPickableGreater30"],
            "min_reading_level": min_reading_level(
                bool(row["IsPickableAlways"]), bool(row["IsPickableGreater20"]), bool(row["IsPickableGreater30"])
            ),
        }
        for row in raw.execute("SELECT * FROM TreasureHunting ORDER BY ZoneName")
    ]
    writer.insert_treasure_hunting(hunting)

    sites: list[dict[str, object]] = []
    locations = writer.conn.execute(
        """
        SELECT tl.stable_key, tl.scene, tl.x, tl.y, tl.z, th.min_reading_level
        FROM treasure_locations tl
        JOIN treasure_hunting th ON th.zone_name = tl.scene
        ORDER BY tl.stable_key
        """
    ).fetchall()
    for chest_key, dig_low, dig_high in CHEST_DIG_LEVELS:
        for row in locations:
            if not chest_can_be_dug_in(row["min_reading_level"], dig_high):
                continue
            sites.append(
                {
                    "chest_character_stable_key": chest_key,
                    "treasure_location_stable_key": row["stable_key"],
                    "level_min": dig_low,
                    "level_max": dig_high,
                    "scene": row["scene"],
                    "x": row["x"],
                    "y": row["y"],
                    "z": row["z"],
                }
            )
    writer.insert_treasure_chest_possible_spawns(sites)
    waves = chest_wave_rows()
    writer.insert_treasure_chest_waves(waves)

    constants = load_spawn_constants(writer.conn)
    guardians = load_guardians(writer.conn)
    scaling = [
        guardian_scaling_row(level, guardian, constants)
        for guardian in guardians
        for level in range(1, PLAYER_LEVEL_CAP + 1)
    ]
    writer.insert_treasure_guardian_scaling(scaling)
    logger.info(
        f"Treasure: {len(hunting)} zones, {len(sites)} possible chest sites, up to {len(waves) - 1} waves, "
        f"{len(guardians)} guardians scaled for player levels 1-{PLAYER_LEVEL_CAP}"
    )
