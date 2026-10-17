"""Board placement identities must not promote unrelated Reaver loot or hide spawned copies."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from erenshor.application.wiki_lua.game_board import build_game_board_rows
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemDisposition
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository


def test_reaver_board_copy_and_alternative_copy_keep_their_own_loot(tmp_path: Path) -> None:
    path = tmp_path / "board.sqlite"
    board = "character:reaver of sivakaya bkp"
    other = "character:reaver of sivakaya"
    alternative = "character:alternative-board-copy"
    piece = "item:quest - game piece the faceless sivakayan"
    second_piece = "item:another-piece"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE characters (
                stable_key TEXT PRIMARY KEY, level INTEGER, group_encounter INTEGER,
                level_scales_with_player INTEGER
            );
            CREATE TABLE character_deduplications (
                group_key TEXT, member_stable_key TEXT, is_wiki_generated INTEGER
            );
            CREATE TABLE character_spawns (
                character_stable_key TEXT, spawn_point_stable_key TEXT, trigger_item_stable_key TEXT,
                level_mod INTEGER, source_script TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO characters VALUES (?, ?, 0, 0)", [(board, 38), (other, 38), (alternative, 34)]
        )
        connection.executemany(
            "INSERT INTO character_deduplications VALUES (?, ?, ?)",
            [(board, board, 1), (other, other, 0), (board, alternative, 0)],
        )
        connection.executemany(
            "INSERT INTO character_spawns VALUES (?, ?, ?, ?, ?)",
            [
                (board, "board", piece, None, "Chessboard"),
                (other, "elsewhere", piece, None, "AnotherScript"),
                (alternative, "alternative-board", second_piece, 1, "Chessboard"),
            ],
        )
    db = DatabaseConnection(path, read_only=True)
    try:
        spawns = CharacterRepository(db).get_game_board_spawns()
    finally:
        db.close()
    assert {row["copy"] for row in spawns} == {board, alternative}
    assert {row["character"] for row in spawns} == {board}

    def drop(copy: str, item: str, chance: float) -> ItemAcquisition:
        return ItemAcquisition(
            copy + ":" + item,
            item,
            "character_drop",
            board if copy != other else other,
            source_copy_stable_key=copy,
            probability_kind="exact",
            probability_min=chance,
            probability_max=chance,
            probability_basis="per_kill",
        )

    facts = [
        drop(board, "item:void-slice", 100),
        drop(other, "item:ring-of-the-deceiver", 25),
        drop(other, "item:resonating-brace", 25),
        drop(alternative, "item:alternative-drop", 50),
    ]
    catalog = {
        key: {"name": key, "page": key} for key in (piece, second_piece, *(fact.item_stable_key for fact in facts))
    }
    dispositions = {fact.item_stable_key: ItemDisposition(fact.item_stable_key, "current") for fact in facts}
    rows = build_game_board_rows(spawns, facts, dispositions, catalog)[board]
    assert len(rows) == 2
    assert {
        (row["copy"], row["piece"]["key"], row["drop"]["key"], row["levelMin"], row["levelMax"]) for row in rows
    } == {
        (board, piece, "item:void-slice", 38, 38),
        (alternative, second_piece, "item:alternative-drop", 35, 35),
    }
