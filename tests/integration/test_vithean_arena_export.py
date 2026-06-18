from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

PLAYTEST_DB = Path(__file__).resolve().parents[2] / "variants" / "playtest" / "erenshor-playtest.sqlite"


def _playtest_connection() -> sqlite3.Connection:
    if not PLAYTEST_DB.exists():
        pytest.skip("playtest clean DB missing; run 'uv run erenshor -V playtest extract build'")
    conn = sqlite3.connect(PLAYTEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def test_vithean_arena_rounds_join_fights_to_reward_chests() -> None:
    with closing(_playtest_connection()) as db:
        rows = db.execute(
            """
            SELECT
                ar.round_index,
                ar.award_chest_character_stable_key,
                chest.object_name AS chest_object_name,
                enemy.npc_name AS enemy_name,
                are.sequence_index
            FROM arena_rounds ar
            JOIN arena_round_enemies are ON are.arena_round_stable_key = ar.stable_key
            JOIN characters chest ON chest.stable_key = ar.award_chest_character_stable_key
            JOIN characters enemy ON enemy.stable_key = are.enemy_character_stable_key
            ORDER BY ar.round_index, are.sequence_index
            """
        ).fetchall()

    assert len({row["round_index"] for row in rows}) == 8
    assert [row["enemy_name"] for row in rows if row["round_index"] == 1] == [
        "Wandering Gladiator",
        "Wandering Gladiator",
    ]
    assert [row["enemy_name"] for row in rows if row["round_index"] == 6] == [
        "Expert Gladiator",
        "Expert Gladiator",
        "Expert Gladiator",
    ]
    assert [row["enemy_name"] for row in rows if row["round_index"] == 8] == ["Vitheo the Tactician"]
    assert {row["chest_object_name"] for row in rows if row["round_index"] == 8} == {"ArenaChest 8"}


def test_vithean_arena_rounds_join_reward_chests_to_loot() -> None:
    with closing(_playtest_connection()) as db:
        rows = db.execute(
            """
            SELECT items.display_name, ROUND(loot_drops.drop_probability, 2) AS drop_probability
            FROM arena_rounds ar
            JOIN loot_drops ON loot_drops.character_stable_key = ar.award_chest_character_stable_key
            JOIN items ON items.stable_key = loot_drops.item_stable_key
            WHERE ar.round_index = 8
            ORDER BY items.display_name
            """
        ).fetchall()

    rates = {row["display_name"]: row["drop_probability"] for row in rows}
    assert rates["Wakeweaver"] == 36.4
    assert rates["Ripcurrent"] == 36.4
    assert rates["Vithean Arena Fee (1)"] == 100.0
    assert "Skyseared Tunic" not in rates
