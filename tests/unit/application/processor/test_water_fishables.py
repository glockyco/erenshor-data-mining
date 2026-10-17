"""Fishing probabilities combine native slots with one global replacement roll."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.item_mechanics import derive_water_fishables, process_water_fishables
from erenshor.application.processor.writer import Writer

_MAPS = [
    "item:gen - torn map top right",
    "item:gen - torn map top left",
    "item:gen - torn map bottom right",
    "item:gen - torn map bottom left",
]


def _chances(rows: list[dict[str, object]], time: str) -> dict[str, object]:
    return {str(row["item_stable_key"]): row["drop_chance"] for row in rows if row["type"] == time}


def test_brake_native_map_and_bonus_are_one_combined_outcome() -> None:
    native_map = _MAPS[0]
    rows = derive_water_fishables(
        {
            "water:brake": {
                "DayFishable": [native_map] + ["item:fish"] * 15,
                "NightFishable": [native_map] + ["item:fish"] * 14,
            }
        },
        _MAPS,
    )
    assert _chances(rows, "DayFishable")[native_map] == pytest.approx(7.1875)
    assert _chances(rows, "NightFishable")[native_map] == pytest.approx(7.5833333333)
    assert {row["item_stable_key"] for row in rows} == {*_MAPS, "item:fish"}
    for time in ("DayFishable", "NightFishable"):
        assert sum(float(value) for value in _chances(rows, time).values()) == pytest.approx(100)


def test_duplicate_and_null_slots_retain_native_and_bonus_mass() -> None:
    rows = derive_water_fishables(
        {"water:test": {"DayFishable": ["item:a", "item:a", None]}},
        ["item:a", "item:a", None, "item:b", "item:ignored"],
    )
    day = _chances(rows, "DayFishable")
    assert day == pytest.approx({"item:a": 95 * 2 / 3 + 2.5, "item:b": 1.25})
    assert _chances(rows, "NightFishable") == day
    assert sum(float(value) for value in day.values()) < 100


@pytest.mark.parametrize("pools", [{}, {"DayFishable": [], "NightFishable": []}])
def test_empty_water_has_no_native_or_bonus_sources(pools) -> None:
    assert derive_water_fishables({"water:empty": pools}, _MAPS) == []


def test_nonempty_night_does_not_make_empty_day_eligible() -> None:
    rows = derive_water_fishables({"water:night": {"NightFishable": ["item:fish"]}}, _MAPS)
    assert _chances(rows, "DayFishable") == {}
    assert _chances(rows, "NightFishable")["item:fish"] == 95


def test_nonempty_null_pool_keeps_bonus_eligibility_without_redistributing_mass() -> None:
    rows = derive_water_fishables({"water:null": {"DayFishable": [None]}}, _MAPS)
    assert _chances(rows, "DayFishable") == dict.fromkeys(_MAPS, 1.25)


def test_raw_slots_build_final_clean_outcomes_and_leave_global_bonus_separate(tmp_path: Path) -> None:
    raw = sqlite3.connect(":memory:")
    raw.executescript(
        "CREATE TABLE WaterFishables (WaterStableKey TEXT, Type TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE SpecialWorldDropItems (Pool TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE code_facts (fact_id TEXT);"
    )
    raw.executemany(
        "INSERT INTO code_facts VALUES (?)",
        [
            (fact,)
            for fact in (
                "water.empty_night_fallback",
                "fishing.source_eligibility",
                "fishing.native_pool_draw",
                "fishing.map_bonus",
            )
        ],
    )
    raw.executemany(
        "INSERT INTO WaterFishables VALUES ('water:test', 'DayFishable', ?, ?)",
        [(2, None), (0, _MAPS[0]), (1, _MAPS[0])],
    )
    raw.executemany("INSERT INTO SpecialWorldDropItems VALUES ('Maps', ?, ?)", enumerate(_MAPS))
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    process_water_fishables(raw, writer)
    rows = [dict(row) for row in writer.conn.execute("SELECT * FROM water_fishables")]
    assert _chances(rows, "DayFishable")[_MAPS[0]] == pytest.approx(95 * 2 / 3 + 1.25)
    assert _chances(rows, "NightFishable") == _chances(rows, "DayFishable")
    assert writer.conn.execute("SELECT count(*) FROM fishing_bonus_catches").fetchone()[0] == 0
    assert raw.execute("SELECT count(*) FROM WaterFishables WHERE ItemStableKey IS NULL").fetchone()[0] == 1
    raw.execute("DELETE FROM code_facts WHERE fact_id = 'water.empty_night_fallback'")
    with pytest.raises(ValueError, match=r"water\.empty_night_fallback"):
        process_water_fishables(raw, writer)
    writer.conn.close()
    raw.close()


def test_old_raw_water_schema_requires_export_before_any_writes(tmp_path: Path) -> None:
    raw = sqlite3.connect(":memory:")
    raw.executescript(
        "CREATE TABLE WaterFishables (WaterStableKey TEXT, Type TEXT, ItemStableKey TEXT, DropChance REAL);"
        "INSERT INTO WaterFishables VALUES ('water:old', 'DayFishable', 'item:fish', 95);"
        "CREATE TABLE code_facts (fact_id TEXT);"
    )
    raw.executemany(
        "INSERT INTO code_facts VALUES (?)",
        [
            (fact,)
            for fact in (
                "water.empty_night_fallback",
                "fishing.source_eligibility",
                "fishing.native_pool_draw",
                "fishing.map_bonus",
            )
        ],
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.insert_water_fishables(
        [
            {
                "water_stable_key": "water:sentinel",
                "type": "DayFishable",
                "item_stable_key": "item:fish",
                "drop_chance": 12,
            }
        ]
    )
    before = (raw.total_changes, writer.conn.total_changes)
    with pytest.raises(ValueError, match="extract export, then extract code-facts"):
        process_water_fishables(raw, writer)
    assert (raw.total_changes, writer.conn.total_changes) == before
    assert raw.execute("SELECT DropChance FROM WaterFishables").fetchone()[0] == 95
    assert writer.conn.execute("SELECT drop_chance FROM water_fishables").fetchone()[0] == 12
    writer.conn.close()
    raw.close()
