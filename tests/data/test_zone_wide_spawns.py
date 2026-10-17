"""Raw slot weights and clean potential zones agree without invented markers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_EXCLUDED = {"Azure", "Stowaway", "Tutorial", "SummerEvent", "ShiveringStep", "ShiveringTomb", "ShiveringTomb2"}
_RULE = "sivakayan_spectres"


def test_spectre_raw_pool_keeps_all_nine_slots(main_raw_db: Path) -> None:
    with sqlite3.connect(main_raw_db) as raw:
        slots = raw.execute(
            "SELECT Slot FROM ZoneWideSpawnCandidates WHERE RuleId = ? ORDER BY Slot", (_RULE,)
        ).fetchall()
        weights = raw.execute(
            "SELECT COUNT(*) FROM ZoneWideSpawnCandidates WHERE RuleId = ? GROUP BY CharacterStableKey", (_RULE,)
        ).fetchall()
        orphans = raw.execute("""
            SELECT COUNT(*) FROM ZoneWideSpawnCandidates z
            LEFT JOIN Characters c ON c.StableKey = z.CharacterStableKey WHERE c.StableKey IS NULL
        """).fetchone()[0]
    assert slots == [(slot,) for slot in range(9)]
    assert sorted(row[0] for row in weights) == [1, 2, 2, 2, 2]
    assert orphans == 0


def test_clean_spectre_relations_match_raw(main_raw_db: Path, main_clean_db: Path) -> None:
    with sqlite3.connect(main_raw_db) as raw, sqlite3.connect(main_clean_db) as clean:
        raw_weights = dict(
            raw.execute(
                "SELECT CharacterStableKey, COUNT(*) FROM ZoneWideSpawnCandidates "
                "WHERE RuleId = ? GROUP BY CharacterStableKey",
                (_RULE,),
            )
        )
        clean_weights = dict(
            clean.execute(
                "SELECT character_stable_key, weight FROM zone_wide_spawn_candidates WHERE rule_id = ?", (_RULE,)
            )
        )
        assert len(raw_weights) == 5
        assert clean_weights == raw_weights
        assert (
            clean.execute("SELECT COUNT(*) FROM zone_wide_spawn_candidates WHERE total_weight != 9").fetchone()[0] == 0
        )
        counts = dict(raw.execute("SELECT Scene, COUNT(*) FROM SpawnPoints GROUP BY Scene"))
        assert counts["Azure"] > 0
        expected = {
            key: counts[scene]
            for key, scene in raw.execute("SELECT StableKey, SceneName FROM Zones")
            if scene not in _EXCLUDED and scene in counts
        }
        assert expected
        assert (
            dict(
                clean.execute(
                    "SELECT zone_stable_key, authored_spawn_point_count FROM zone_wide_spawn_zones WHERE rule_id = ?",
                    (_RULE,),
                )
            )
            == expected
        )
        lens = raw.execute("SELECT ItemStableKey FROM CosmeticItems WHERE Field = 'WatchersLens'").fetchone()[0]
        assert clean.execute(
            "SELECT required_cosmetic_item_stable_key, attempt_probability, max_attempts_per_entry, "
            "recent_successful_zone_limit FROM zone_wide_spawn_rules WHERE rule_id = ?",
            (_RULE,),
        ).fetchone() == (lens, 0.1, 1, 5)
        assert (
            clean.execute("SELECT COUNT(*) FROM character_spawns WHERE source_script = 'ZoneAnnounce'").fetchone()[0]
            == 0
        )
        assert clean.execute("PRAGMA foreign_key_check").fetchall() == []
