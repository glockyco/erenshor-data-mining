"""A dedup group shows the facts of its copies in the game.

Spells, dialogs, and vendor status are not part of the character dedup
identity, so a copy that players never meet can cast or give what the copy in
the game does not. A group that the export places nowhere keeps the facts of
the copies that the mapping generates, because a script can still spawn it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _group_buffs(clean: sqlite3.Connection, group: str) -> set[str]:
    return {
        row[0]
        for row in clean.execute(
            """
            SELECT b.spell_stable_key
            FROM character_fact_sources s
            JOIN character_buff_spells b ON b.character_stable_key = s.member_stable_key
            WHERE s.group_key = ?
            """,
            (group,),
        )
    }


def test_an_unplaced_copy_adds_no_spells(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        buffs = _group_buffs(clean, "character:sean figarello")

    # Only the unplaced Sean Figarello prefab casts these; the copy in Stowaway does not.
    assert not buffs & {
        "spell:pal - soluna's invigoration",
        "spell:pal - soluna's blessing",
        "spell:dru duel - minor regen",
    }


def test_a_group_that_only_a_script_spawns_keeps_its_facts(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        drops = clean.execute(
            """
            SELECT COUNT(*)
            FROM character_fact_sources s
            JOIN loot_drops ld ON ld.character_stable_key = s.member_stable_key
            WHERE s.group_key = 'character:24 - sivakayan spectre'
            """
        ).fetchone()[0]

    # ZoneAnnounce spawns the spectres for a player who wears the Watcher's Lens.
    assert drops > 0


def test_an_unused_prefab_placed_nowhere_sells_nothing(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        sellers = clean.execute(
            "SELECT copy_stable_key FROM vendor_offers WHERE item_stable_key = 'item:spell scroll - minor protection'"
        ).fetchall()

    # Only unused prefabs list it: Shopkeeper Treven, Lucian Revald, and TestDummy.
    assert sellers == []
