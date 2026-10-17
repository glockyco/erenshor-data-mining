"""Zone-wide candidates and potential scenes, without fictional personal placements.

The player must equip the exported lens in a cosmetic slot. Runtime equipment,
registered SpawnPoints, and the five most recent successful-spawn scenes are
unknown to an offline export. A potential scene is not an unconditional spawn.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import sqlite3

    from .writer import Writer

SPECTRE_RULE = "sivakayan_spectres"
# code-fact: spectres.entry_attempt
_EXCLUDED_SCENES = frozenset(
    {"Azure", "Stowaway", "Tutorial", "SummerEvent", "ShiveringStep", "ShiveringTomb", "ShiveringTomb2"}
)
_REQUIRED_FACTS = (
    "spectres.entry_delay_start",
    "spectres.entry_attempt",
    "spectres.single_entry_call",
    "spectres.roll",
    "spectres.spawn_selection",
    "spectres.recent_zones",
    "spectres.cosmetic_slots",
    "spectres.spawn_point_registration",
)


def process_zone_wide_spawns(raw: sqlite3.Connection, writer: Writer) -> None:
    """Keep serialized slot weights and derive the scenes that can qualify.

    This deliberately adds nothing to character_spawns. Disabled authored spawn
    points are retained as potential registrations, not assumed active. The game
    registers a point in Start before checking its own NPC's quest prerequisite.
    """
    facts = {str(row[0]) for row in raw.execute("SELECT fact_id FROM code_facts WHERE key = 'ok' AND value = 'true'")}
    missing = set(_REQUIRED_FACTS) - facts
    if missing:
        raise ValueError(f"Zone-wide spawn facts missing: {sorted(missing)}. Run 'erenshor extract code-facts'.")

    slots = list(
        raw.execute("SELECT RuleId, Slot, CharacterStableKey FROM ZoneWideSpawnCandidates ORDER BY RuleId, Slot")
    )
    if not slots or any(rule != SPECTRE_RULE for rule, _, _ in slots):
        raise ValueError("Expected the exported Sivakayan spectre candidate pool")
    if [slot for _, slot, _ in slots] != list(range(len(slots))):
        raise ValueError("Zone-wide spawn candidate slots must be unique and contiguous from zero")
    weights = Counter(str(key) for _, _, key in slots)
    characters = {str(row[0]) for row in writer.conn.execute("SELECT stable_key FROM characters")}
    if unknown := set(weights) - characters:
        raise ValueError(f"Unknown zone-wide spawn characters: {sorted(unknown)}")

    lenses = list(raw.execute("SELECT ItemStableKey FROM CosmeticItems WHERE Field = 'WatchersLens'"))
    if len(lenses) != 1:
        raise ValueError("Expected the player's one exported WatchersLens cosmetic item")
    lens = str(lenses[0][0])
    if not writer.conn.execute("SELECT 1 FROM items WHERE stable_key = ?", (lens,)).fetchone():
        raise ValueError(f"WatchersLens references an unknown item: {lens}")

    # code-fact: spectres.entry_delay_start
    # code-fact: spectres.entry_attempt
    # code-fact: spectres.roll
    # code-fact: spectres.recent_zones
    # code-fact: spectres.cosmetic_slots
    rule = {
        "rule_id": SPECTRE_RULE,
        "source_script": "ZoneAnnounce",
        "candidate_script": "Misc",
        "candidate_field": "SivakayanSpectres",
        "required_cosmetic_item_stable_key": lens,
        "attempt_probability": 0.1,
        "entry_delay_ticks": 10.0,
        "entry_delay_ticks_per_second": 60.0,
        "attempt_trigger": "entry_timer_crosses_below_zero",
        # code-fact: spectres.single_entry_call
        "max_attempts_per_entry": 1,
        "recent_successful_zone_limit": 5,
        "requires_registered_spawn_point": 1,
    }
    # code-fact: spectres.spawn_selection
    candidates = [
        {"rule_id": SPECTRE_RULE, "character_stable_key": key, "weight": weight, "total_weight": len(slots)}
        for key, weight in sorted(weights.items())
    ]

    # code-fact: spectres.spawn_point_registration
    points = {
        str(scene): (int(count), int(enabled))
        for scene, count, enabled in raw.execute(
            "SELECT Scene, COUNT(*), SUM(CASE WHEN IsEnabled THEN 1 ELSE 0 END) FROM SpawnPoints GROUP BY Scene"
        )
    }
    zones = [
        {
            "rule_id": SPECTRE_RULE,
            "zone_stable_key": str(key),
            "authored_spawn_point_count": points[str(scene)][0],
            "enabled_spawn_point_count": points[str(scene)][1],
        }
        for key, scene in writer.conn.execute("SELECT stable_key, scene_name FROM zones ORDER BY stable_key")
        if scene not in _EXCLUDED_SCENES and str(scene) in points
    ]
    writer.insert_zone_wide_spawn_rules([rule])
    writer.insert_zone_wide_spawn_candidates(candidates)
    writer.insert_zone_wide_spawn_zones(zones)
    logger.info(
        f"Zone-wide spawns: {len(slots)} candidate slots, {len(candidates)} characters, {len(zones)} potential zones"
    )
