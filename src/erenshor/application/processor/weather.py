"""Derive scene weather and its producers from serialized limits and shipped rules."""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict


def _fact(conn: sqlite3.Connection, fact: str, key: str) -> str:
    rows = conn.execute("SELECT value FROM code_facts WHERE fact_id=? AND key=?", (fact, key)).fetchall()
    if len(rows) != 1:
        raise ValueError(f"Weather fact {fact}.{key}: expected one value")
    return str(rows[0][0])


def _number(conn: sqlite3.Connection, fact: str, key: str) -> float:
    value = float(_fact(conn, fact, key))
    if not math.isfinite(value):
        raise ValueError(f"Weather fact {fact}.{key}: nonfinite value")
    return value


def process_weather(raw: sqlite3.Connection, conn: sqlite3.Connection) -> None:
    """Keep every trend and derive rain only for scenes with exported sun evidence."""
    # code-fact: weather.trend_start
    # code-fact: weather.trend_pull
    # code-fact: weather.weight_follows_goal
    # code-fact: weather.rain_stop
    # code-fact: weather.scene_sun
    # code-fact: weather.zone_line_sun
    for fact in (
        "weather.trend_start",
        "weather.trend_pull",
        "weather.weight_follows_goal",
        "weather.rain_stop",
        "weather.scene_sun",
        "weather.zone_line_sun",
    ):
        if _fact(conn, fact, "ok") != "true":
            raise ValueError(f"Weather rule {fact}: missing assertion")
    # code-fact: weather.rain_start
    threshold = _number(conn, "weather.rain_start", "threshold")
    trends: dict[str, list[float]] = defaultdict(list)
    for key, scene, enabled, cloudy, rainy in raw.execute(
        "SELECT StableKey, Scene, IsEnabled, MaxNaturalCloudy, MaxNaturalRainy FROM WeatherTrends"
    ):
        if not all(math.isfinite(value) for value in (cloudy, rainy)):
            raise ValueError(f"Weather trend {key}: nonfinite limit")
        conn.execute("INSERT INTO weather_trends VALUES (?,?,?,?,?)", (key, scene, enabled, cloudy, rainy))
        if enabled and rainy > 0:
            trends[scene].append(rainy)
    # code-fact: weather.invoke_storm
    # code-fact: weather.dissipate_storm
    rain_spells = []
    for fact in ("weather.invoke_storm", "weather.dissipate_storm"):
        name = _fact(conn, fact, "spell_name")
        spells = conn.execute("SELECT stable_key FROM spells WHERE spell_name=?", (name,)).fetchall()
        if len(spells) != 1:
            raise ValueError(f"Weather spell {name!r}: expected one exported spell")
        spell = spells[0][0]
        weight = _number(conn, fact, "weight_goal")
        since = _number(conn, fact, "since_rain") if fact == "weather.invoke_storm" else None
        cloud = _number(conn, fact, "cloud_amount")
        conn.execute("INSERT INTO weather_spell_effects VALUES (?,?,?,?)", (spell, weight, since, cloud))
        if weight > threshold and since is not None and since <= 0:
            rain_spells.append(spell)
    sun: dict[str, set[int]] = defaultdict(set)
    for zone, uses_sun in conn.execute(
        "SELECT destination_zone_stable_key, use_sun_in_new_zone FROM zone_lines"
        " WHERE destination_zone_stable_key IS NOT NULL"
    ):
        if uses_sun not in (0, 1):
            raise ValueError(f"Weather scene {zone}: zone line lacks its sun flag")
        sun[zone].add(uses_sun)
    for zone, scene in conn.execute("SELECT stable_key, scene_name FROM zones"):
        flags = sun.get(zone)
        if not flags:
            continue
        if len(flags) != 1:
            raise ValueError(f"Weather scene {zone}: conflicting incoming sun flags")
        uses_sun = next(iter(flags))
        natural = bool(uses_sun and all(cap >= threshold for cap in trends.get(scene, ())))
        state = f"world_state:weather:raining:{zone}"
        conn.execute("INSERT INTO world_states VALUES (?,?,?,?,?)", (state, "raining", zone, uses_sun, int(natural)))
        if natural:
            conn.execute("INSERT INTO world_state_producers VALUES (?, 'natural_weather', NULL)", (state,))
        if uses_sun:
            conn.executemany(
                "INSERT INTO world_state_producers VALUES (?, 'spell', ?)",
                [(state, spell) for spell in rain_spells],
            )
