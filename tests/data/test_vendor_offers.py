"""Vendors sell only what their copies in the game sell.

Vendor items are not part of the character dedup identity, so a copy that
players never meet, such as an unplaced backup prefab, can list stock that the
copy in the game lacks.
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
