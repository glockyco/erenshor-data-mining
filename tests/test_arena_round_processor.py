from __future__ import annotations

import sqlite3
from pathlib import Path

from erenshor.application.processor import characters
from erenshor.application.processor.writer import Writer


def _clean_writer(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    return writer


def test_process_arena_rounds_keeps_valid_rounds_and_duplicate_enemies(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.row_factory = sqlite3.Row
    raw.execute(
        """
        CREATE TABLE ArenaRounds (
            StableKey TEXT PRIMARY KEY,
            Scene TEXT,
            ArenaObjectName TEXT,
            RoundIndex INTEGER,
            CoinItemStableKey TEXT,
            AwardChestCharacterStableKey TEXT
        )
        """
    )
    raw.execute(
        """
        CREATE TABLE ArenaRoundEnemies (
            ArenaRoundStableKey TEXT,
            SequenceIndex INTEGER,
            EnemyCharacterStableKey TEXT,
            PRIMARY KEY (ArenaRoundStableKey, SequenceIndex)
        )
        """
    )
    raw.executemany(
        "INSERT INTO ArenaRounds VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("arenaround:plane:vith arena:1", "PlaneOfVitheo", "Vith Arena", 1, "item:coin 1", "character:chest 1"),
            ("arenaround:plane:vith arena:2", "PlaneOfVitheo", "Vith Arena", 2, "item:missing", "character:chest 2"),
            ("arenaround:plane:vith arena:3", "PlaneOfVitheo", "Vith Arena", 3, "item:coin 3", "character:missing"),
        ],
    )
    raw.executemany(
        "INSERT INTO ArenaRoundEnemies VALUES (?, ?, ?)",
        [
            ("arenaround:plane:vith arena:1", 0, "character:gladiator"),
            ("arenaround:plane:vith arena:1", 1, "character:gladiator"),
            ("arenaround:plane:vith arena:1", 2, "character:missing"),
            ("arenaround:plane:vith arena:2", 0, "character:gladiator"),
        ],
    )
    raw.commit()

    writer = _clean_writer(tmp_path)
    characters.process_arena_rounds(
        raw,
        writer,
        valid_character_keys={"character:chest 1", "character:chest 2", "character:gladiator"},
        valid_item_keys={"item:coin 1", "item:coin 3"},
    )
    raw.close()
    writer.finalize()

    clean = sqlite3.connect(tmp_path / "clean.sqlite")
    rounds = clean.execute(
        """
        SELECT stable_key, scene, arena_object_name, round_index, coin_item_stable_key, award_chest_character_stable_key
        FROM arena_rounds
        ORDER BY stable_key
        """
    ).fetchall()
    try:
        enemies = clean.execute(
            """
            SELECT arena_round_stable_key, sequence_index, enemy_character_stable_key
            FROM arena_round_enemies
            ORDER BY arena_round_stable_key, sequence_index
            """
        ).fetchall()
    finally:
        clean.close()

    assert rounds == [
        (
            "arenaround:plane:vith arena:1",
            "PlaneOfVitheo",
            "Vith Arena",
            1,
            "item:coin 1",
            "character:chest 1",
        )
    ]
    assert enemies == [
        ("arenaround:plane:vith arena:1", 0, "character:gladiator"),
        ("arenaround:plane:vith arena:1", 1, "character:gladiator"),
    ]


def test_process_arena_rounds_treats_missing_raw_tables_as_empty(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.row_factory = sqlite3.Row

    writer = _clean_writer(tmp_path)
    characters.process_arena_rounds(
        raw,
        writer,
        valid_character_keys={"character:chest 1"},
        valid_item_keys={"item:coin 1"},
    )
    raw.close()
    writer.finalize()

    clean = sqlite3.connect(tmp_path / "clean.sqlite")
    try:
        assert clean.execute("SELECT COUNT(*) FROM arena_rounds").fetchone() == (0,)
        assert clean.execute("SELECT COUNT(*) FROM arena_round_enemies").fetchone() == (0,)
    finally:
        clean.close()
