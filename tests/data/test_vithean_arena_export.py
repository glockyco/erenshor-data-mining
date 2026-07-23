from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


def _main_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def test_vithean_arena_rounds_join_fights_to_reward_chests(main_clean_db: Path) -> None:
    with closing(_main_connection(main_clean_db)) as db:
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


def test_vithean_arena_rounds_join_reward_chests_to_loot(main_clean_db: Path) -> None:
    with closing(_main_connection(main_clean_db)) as db:
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
