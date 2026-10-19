from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from erenshor.application.processor.weather import process_weather
from erenshor.application.processor.writer import _DDL


@pytest.fixture
def weather() -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE WeatherTrends (StableKey, Scene, IsEnabled, MaxNaturalCloudy, MaxNaturalRainy)")
    conn = sqlite3.connect(":memory:")
    conn.executescript(_DDL)
    for scene in ("Desert", "Forest", "Cave"):
        conn.execute(
            "INSERT INTO zones (stable_key, scene_name, zone_name, display_name, image_name, zone_type)"
            " VALUES (?,?,?,?,?,?)",
            ("zone:" + scene.lower(), scene, scene, scene, scene, "Outdoor"),
        )
        conn.execute(
            "INSERT INTO zone_lines (stable_key, destination_zone_stable_key, use_sun_in_new_zone, is_usable)"
            " VALUES (?,?,?,1)",
            ("line:" + scene, "zone:" + scene.lower(), int(scene != "Cave")),
        )
    for name, key in (("Invoke Storm", "spell:invoke"), ("Dissipate Storm", "spell:dissipate")):
        conn.execute(
            "INSERT INTO spells (stable_key, spell_name, display_name, image_name) VALUES (?,?,?,?)",
            (key, name, name, name),
        )
    assertions = (
        "weather.trend_start",
        "weather.trend_pull",
        "weather.weight_follows_goal",
        "weather.rain_stop",
        "weather.scene_sun",
        "weather.zone_line_sun",
    )
    facts = [(fact, "ok", "true", "bool") for fact in assertions]
    facts += [("weather.rain_start", "threshold", "0.55", "float")]
    for fact, name, weight, cloud in (
        ("weather.invoke_storm", "Invoke Storm", "0.9", "0.4"),
        ("weather.dissipate_storm", "Dissipate Storm", "0", "0.1"),
    ):
        facts += [
            (fact, "spell_name", name, "text"),
            (fact, "weight_goal", weight, "float"),
            (fact, "cloud_amount", cloud, "float"),
        ]
    facts.append(("weather.invoke_storm", "since_rain", "-1", "float"))
    conn.executemany("INSERT INTO code_facts VALUES (?,?,?,?)", facts)
    yield raw, conn
    raw.close()
    conn.close()


@pytest.mark.parametrize("cap", [0.15, 0.3, 0.35, 0.5])
def test_capped_scenes_need_invoke_storm(weather, cap):
    raw, conn = weather
    raw.execute("INSERT INTO WeatherTrends VALUES ('trend', 'Desert', 1, 0.5, ?)", (cap,))
    process_weather(raw, conn)
    assert conn.execute("SELECT max_natural_rainy FROM weather_trends").fetchall() == [(cap,)]
    assert conn.execute(
        "SELECT natural_rain_can_start FROM world_states WHERE zone_stable_key='zone:desert'"
    ).fetchall() == [(0,)]
    assert conn.execute(
        "SELECT mechanism,spell_stable_key FROM world_state_producers"
        " WHERE state_stable_key='world_state:weather:raining:zone:desert'"
    ).fetchall() == [("spell", "spell:invoke")]


@pytest.mark.parametrize("cap,enabled", [(0, 1), (0.55, 1), (0.6, 1), (0.15, 0)])
def test_nonlimiting_scenes_keep_natural_weather(weather, cap, enabled):
    raw, conn = weather
    raw.execute("INSERT INTO WeatherTrends VALUES ('trend', 'Forest', ?, 0.01, ?)", (enabled, cap))
    process_weather(raw, conn)
    assert conn.execute(
        "SELECT natural_rain_can_start FROM world_states WHERE zone_stable_key='zone:forest'"
    ).fetchall() == [(1,)]
    assert conn.execute(
        "SELECT mechanism FROM world_state_producers WHERE state_stable_key='world_state:weather:raining:zone:forest'"
        " ORDER BY mechanism"
    ).fetchall() == [("natural_weather",), ("spell",)]


def test_without_sun_neither_spells_nor_natural_weather_start_rain(weather):
    raw, conn = weather
    process_weather(raw, conn)
    assert conn.execute(
        "SELECT uses_sun,natural_rain_can_start FROM world_states WHERE zone_stable_key='zone:cave'"
    ).fetchall() == [(0, 0)]
    assert conn.execute(
        "SELECT count(*) FROM world_state_producers WHERE state_stable_key='world_state:weather:raining:zone:cave'"
    ).fetchone() == (0,)
    assert conn.execute(
        "SELECT weight_goal,since_rain FROM weather_spell_effects ORDER BY spell_stable_key"
    ).fetchall() == [(0.0, None), (0.9, -1.0)]


def test_conflicting_sun_evidence_fails_closed(weather):
    raw, conn = weather
    conn.execute(
        "INSERT INTO zone_lines (stable_key,destination_zone_stable_key,use_sun_in_new_zone,is_usable)"
        " VALUES ('conflict','zone:forest',0,1)"
    )
    with pytest.raises(ValueError, match="conflicting incoming sun flags"):
        process_weather(raw, conn)


def test_a_line_that_players_cannot_use_gives_no_sun_evidence(weather):
    raw, conn = weather
    conn.execute(
        "INSERT INTO zone_lines (stable_key,destination_zone_stable_key,use_sun_in_new_zone,is_usable,unusable_reason)"
        " VALUES ('sealed','zone:forest',0,0,'Reviewed fixture obstruction.')"
    )
    process_weather(raw, conn)
    assert conn.execute("SELECT uses_sun FROM world_states WHERE zone_stable_key = 'zone:forest'").fetchone() == (1,)


def test_missing_rule_fails_closed(weather):
    raw, conn = weather
    conn.execute("DELETE FROM code_facts WHERE fact_id='weather.rain_start'")
    with pytest.raises(ValueError, match=r"weather\.rain_start\.threshold"):
        process_weather(raw, conn)
