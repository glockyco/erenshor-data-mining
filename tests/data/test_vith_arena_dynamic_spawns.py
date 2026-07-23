"""Integration checks for VithArena dynamic spawn placement.

The arena has its own raw tables (`ArenaRounds`, `ArenaRoundEnemies`) and also
feeds map/wiki placement through `DynamicCharacterSpawns`. The two surfaces must
stay consistent: every arena enemy sequence entry needs one dynamic spawn row,
and every arena reward chest needs one dynamic spawn row.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path


def _counts(rows: list[sqlite3.Row], column: str) -> Counter[str]:
    return Counter(str(row[column]) for row in rows)


def _vith_arena_position_label(enemy_count: int, sequence_index: int) -> str:
    """Mirror VithArena.SpawnPiece's logical spawn-location choice."""
    if enemy_count == 1:
        return "SpawnLoc1"
    if enemy_count == 2:
        return ["SpawnLoc2", "SpawnLoc3"][sequence_index]
    if enemy_count == 3:
        return ["SpawnLoc1", "SpawnLoc2", "SpawnLoc3"][sequence_index]
    raise AssertionError(f"Unexpected VithArena enemy count: {enemy_count}")


def _expected_enemy_location_counts(rows: list[sqlite3.Row]) -> Counter[str]:
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(str(row["ArenaRoundStableKey"]), []).append(row)

    expected_pairs: set[tuple[str, str]] = set()
    for round_rows in grouped.values():
        enemy_count = len(round_rows)
        for row in round_rows:
            expected_pairs.add(
                (
                    str(row["EnemyCharacterStableKey"]),
                    _vith_arena_position_label(enemy_count, int(row["SequenceIndex"])),
                )
            )

    return Counter(character for character, _position in expected_pairs)


def test_vith_arena_dynamic_enemy_spawns_match_arena_round_enemies(main_raw_db: Path) -> None:
    """VithArena fight placement mirrors the game's unique character/location surface."""
    with sqlite3.connect(main_raw_db) as conn:
        conn.row_factory = sqlite3.Row
        expected = conn.execute(
            """
            SELECT ArenaRoundStableKey, SequenceIndex, EnemyCharacterStableKey
            FROM ArenaRoundEnemies
            ORDER BY ArenaRoundStableKey, SequenceIndex
            """
        ).fetchall()
        award_chests = {
            str(row["AwardChestCharacterStableKey"])
            for row in conn.execute("SELECT AwardChestCharacterStableKey FROM ArenaRounds")
        }
        actual = conn.execute(
            """
            SELECT CharacterStableKey, X, Y, Z
            FROM DynamicCharacterSpawns
            WHERE SourceScript = 'VithArena'
              AND CharacterStableKey NOT IN (
                  SELECT AwardChestCharacterStableKey FROM ArenaRounds
              )
            ORDER BY CharacterStableKey, X, Y, Z
            """
        ).fetchall()

    expected_counts = _expected_enemy_location_counts(expected)

    assert award_chests
    assert len(actual) == sum(expected_counts.values())
    assert _counts(actual, "CharacterStableKey") == expected_counts

    # Multi-enemy rounds use SpawnLoc2/SpawnLoc3 (and 3-enemy rounds also use
    # SpawnLoc1). A single fight position means the exporter collapsed list
    # entries onto SpawnLoc1 instead of applying VithArena.SpawnPiece's rules.
    distinct_positions = {(row["X"], row["Y"], row["Z"]) for row in actual}
    assert len(distinct_positions) == 3


def test_vith_arena_dynamic_chest_spawns_match_arena_rounds(main_raw_db: Path) -> None:
    """Each VithArena reward chest gets one dynamic spawn at ChestSpawnPos."""
    with sqlite3.connect(main_raw_db) as conn:
        conn.row_factory = sqlite3.Row
        expected = conn.execute("SELECT AwardChestCharacterStableKey FROM ArenaRounds").fetchall()
        actual = conn.execute(
            """
            SELECT CharacterStableKey
            FROM DynamicCharacterSpawns
            WHERE SourceScript = 'VithArena'
              AND CharacterStableKey IN (
                  SELECT AwardChestCharacterStableKey FROM ArenaRounds
              )
            """
        ).fetchall()

    assert len(actual) == len(expected)
    assert _counts(actual, "CharacterStableKey") == _counts(expected, "AwardChestCharacterStableKey")
