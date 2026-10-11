"""Vendors sell only what their copies in the game sell.

Vendor items and dialogs are not part of the character dedup identity, so a
copy that players never meet, such as an unplaced backup prefab, can list stock
or dialogs that the copy in the game lacks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _offers(clean: sqlite3.Connection, vendor: str) -> set[str]:
    return {
        row[0]
        for row in clean.execute("SELECT item_stable_key FROM vendor_offers WHERE vendor_stable_key = ?", (vendor,))
    }


def test_unplaced_copies_add_no_stock(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        tiver = _offers(clean, "character:tiver banes")
        samuel = _offers(clean, "character:shopkeeper samuel")
        placed_samuel = {
            row[0]
            for row in clean.execute(
                "SELECT item_stable_key FROM character_vendor_items WHERE character_stable_key = ?",
                ("character:shopkeeper samuel",),
            )
        }

    # Only the unplaced backup copies list these two.
    assert not tiver & {"item:arm - 9 - vinewrapped vambracer", "item:chest - 12 - living chainmail jacket"}
    # The Treven prefab shares Samuel's name, but players meet it only as Treven Pines.
    assert samuel == placed_samuel


def test_dialogs_of_unplaced_copies_add_nothing(main_clean_db: Path) -> None:
    """The wiki merges dialogs across a dedup group, so this must stay empty."""
    with sqlite3.connect(main_clean_db) as clean:
        rows = clean.execute(
            """
            WITH effects AS (
                SELECT character_stable_key AS copy, 'give' AS kind, give_item_stable_key AS target
                FROM character_dialogs
                UNION ALL
                SELECT character_stable_key, 'assign', assign_quest_stable_key FROM character_dialogs
                UNION ALL
                SELECT character_stable_key, 'complete', complete_quest_stable_key FROM character_dialogs
            )
            SELECT d.group_key, e.kind, e.target
            FROM effects e
            JOIN character_deduplications d ON d.member_stable_key = e.copy
            WHERE e.target IS NOT NULL
              AND d.group_key IN (
                SELECT d2.group_key FROM character_deduplications d2
                JOIN characters_in_game g ON g.stable_key = d2.member_stable_key
              )
            GROUP BY d.group_key, e.kind, e.target
            HAVING MAX(e.copy IN (SELECT stable_key FROM characters_in_game)) = 0
            ORDER BY d.group_key, e.kind, e.target
            """
        ).fetchall()

    assert rows == []
