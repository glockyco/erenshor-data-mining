"""Scripted spawns come only from placed copies of their event scripts.

A script on a prefab asset has no scene. The export reads the copies that the
scenes place, so a row without a scene would come from a prefab that is never
placed, such as the Fernalla event spawner, and has no place in the world.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_NIGHTMARIANS = (
    "character:nightmarian arcanist",
    "character:nightmarian hound",
    "character:nightmarian knight",
)


def test_every_dynamic_spawn_has_a_scene(main_raw_db: Path) -> None:
    with sqlite3.connect(main_raw_db) as raw:
        rows = raw.execute(
            "SELECT Key, SourceScript FROM DynamicCharacterSpawns WHERE COALESCE(Scene, '') = '' ORDER BY Key"
        ).fetchall()

    assert rows == []


def test_every_wiki_visible_spawn_has_a_zone(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        rows = clean.execute(
            "SELECT character_stable_key, source_script FROM wiki_character_spawns WHERE zone_stable_key IS NULL"
        ).fetchall()

    assert rows == []


def test_nightmarians_keep_their_fernalla_portal_spawns(main_clean_db: Path) -> None:
    with sqlite3.connect(main_clean_db) as clean:
        counts = dict(
            clean.execute(
                f"""
                SELECT character_stable_key, COUNT(*)
                FROM wiki_character_spawns
                WHERE scene = 'FernallaPortal' AND source_script = 'FernallaPortalEvent'
                  AND character_stable_key IN ({",".join("?" * len(_NIGHTMARIANS))})
                GROUP BY character_stable_key
                """,
                _NIGHTMARIANS,
            ).fetchall()
        )

    assert counts == dict.fromkeys(_NIGHTMARIANS, 4)


def test_chessboard_spawns_retain_complete_native_interaction_sites(main_raw_db: Path, main_clean_db: Path) -> None:
    fields = (
        "EventX",
        "EventY",
        "EventZ",
        "TriggerItemStableKey",
        "TriggerMode",
        "EventDisplayName",
        "TriggerBoundsCenterX",
        "TriggerBoundsCenterY",
        "TriggerBoundsCenterZ",
        "TriggerBoundsExtentsX",
        "TriggerBoundsExtentsY",
        "TriggerBoundsExtentsZ",
    )
    with sqlite3.connect(main_raw_db) as raw, sqlite3.connect(main_clean_db) as clean:
        raw.row_factory = sqlite3.Row
        rows = raw.execute(
            f"SELECT Key, {', '.join(fields)} FROM DynamicCharacterSpawns "
            "WHERE SourceScript = 'Chessboard' ORDER BY Key"
        ).fetchall()
        assert rows
        for row in rows:
            assert all(row[field] is not None for field in fields), dict(row)
            assert row["TriggerMode"] == "proximity_auto_consume"
            assert all(row[f"TriggerBoundsExtents{axis}"] > 0 for axis in "XYZ")
            projected = clean.execute(
                """SELECT event_x, event_y, event_z, trigger_item_stable_key, trigger_mode,
                          event_display_name, trigger_bounds_center_x, trigger_bounds_center_y,
                          trigger_bounds_center_z, trigger_bounds_extents_x,
                          trigger_bounds_extents_y, trigger_bounds_extents_z
                   FROM character_spawns WHERE spawn_point_stable_key = ?""",
                (row["Key"],),
            ).fetchall()
            assert projected == [tuple(row[field] for field in fields)], row["Key"]
