"""Test-side decoding of the schema 11 guide wire contract."""

from __future__ import annotations

import json
import struct
from typing import Any

SPAWN_FIELDS = (
    "activations",
    "condition",
    "entries",
    "is_directly_placed",
    "night_spawn",
    "scene",
    "source_script",
    "stable_key",
    "x",
    "y",
    "z",
)
PLACE_FIELDS = (
    "conditions",
    "entry_zone_line_keys",
    "marker_stable_key",
    "place_key",
    "player_level_max",
    "player_level_min",
    "relation",
    "scene",
    "source_copy_stable_key",
    "x",
    "y",
    "z",
    "zone",
    "zone_stable_key",
)


def decode_mod_guide(serialized: str) -> dict[str, Any]:
    """Expand pooled strings, native references and the two masked row types."""

    def unique_object(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        assert len(entries) == len({key for key, _ in entries}), "duplicate JSON property"
        return dict(entries)

    wire = json.loads(serialized, object_pairs_hook=unique_object)
    strings = wire.pop("_strings", [])
    assert all(isinstance(value, str) for value in strings)

    def string(value: str) -> str:
        if not value.startswith("~"):
            return value
        assert value[1:].isdecimal(), value
        return strings[int(value[1:])]

    def expand(value: Any) -> Any:
        if isinstance(value, str):
            return string(value)
        if isinstance(value, list):
            return [expand(child) for child in value]
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                expanded_key = string(key)
                assert expanded_key not in result, "duplicate expanded JSON property"
                result[expanded_key] = child if expanded_key in {"$id", "$ref"} else expand(child)
            return result
        return value

    references: dict[str, Any] = {}

    def resolve(value: Any) -> Any:
        if isinstance(value, list):
            return [resolve(child) for child in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            assert set(value) == {"$ref"}
            return references[value["$ref"]]
        result: Any = [] if "$values" in value else {}
        if "$id" in value:
            assert value["$id"] not in references
            references[value["$id"]] = result
        if "$values" in value:
            assert set(value) <= {"$id", "$values"}
            result.extend(resolve(child) for child in value["$values"])
        else:
            result.update((key, resolve(child)) for key, child in value.items() if key != "$id")
        return result

    def row(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        mask, *values = value
        assert isinstance(mask, int) and not isinstance(mask, bool)
        assert 0 <= mask < 1 << len(fields)
        names = [field for index, field in enumerate(fields) if mask & (1 << index)]
        assert len(names) == len(values)
        return dict(zip(names, values, strict=True))

    guide = resolve(expand(wire))
    if "_spawn_points" in guide:
        guide["_spawn_points"] = [row(value, SPAWN_FIELDS) for value in guide["_spawn_points"]]
    for places in guide.get("_place_sets", {}).values():
        places[:] = [row(value, PLACE_FIELDS) for value in places]
    return guide


def character_spawns(guide: dict[str, Any], character: str) -> list[dict[str, Any]]:
    """Read inline semantic spawns or indexed wire spawns with false defaults omitted."""
    rows = guide["_character_spawns"][character]
    return [
        {
            key: value
            for key, value in (guide["_spawn_points"][row] if isinstance(row, int) else row).items()
            if not (key in {"night_spawn", "is_directly_placed"} and value is False)
        }
        for row in rows
    ]


def assert_wire_roundtrip(serialized: str, semantic: dict[str, Any]) -> None:
    """Require exact facts and the same game-consumed float32 coordinate bits."""

    def defaults(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: defaults(child)
                for key, child in value.items()
                if child is not None
                and not (key in {"conditions", "entry_zone_line_keys"} and child == [])
                and not (
                    key
                    in {
                        "night_spawn",
                        "is_directly_placed",
                        "repeatable",
                        "disabled",
                        "kill_turn_in_holder",
                        "destroy_turn_in_holder",
                        "drop_invuln_on_holder",
                        "once_per_spawn_instance",
                        "random",
                    }
                    and child is False
                )
                and not (key in {"xp", "gold"} and child == 0)
            }
        if isinstance(value, list):
            return [defaults(child) for child in value]
        return value

    decoded = decode_mod_guide(serialized)
    expected = defaults(semantic)
    decoded["_character_spawns"] = {key: character_spawns(decoded, key) for key in decoded["_character_spawns"]}
    expected["_character_spawns"] = {key: character_spawns(expected, key) for key in expected["_character_spawns"]}
    decoded.pop("_spawn_points", None)
    expected.pop("_spawn_points", None)
    row_sets = [(decoded["_character_spawns"][key], rows) for key, rows in expected["_character_spawns"].items()]
    row_sets.extend((decoded["_place_sets"][key], rows) for key, rows in expected["_place_sets"].items())
    for actual_rows, expected_rows in row_sets:
        assert len(actual_rows) == len(expected_rows)
        for actual, wanted in zip(actual_rows, expected_rows, strict=True):
            for field in ("x", "y", "z"):
                if field in wanted:
                    assert struct.pack("f", actual[field]) == struct.pack("f", wanted[field])
                    actual[field] = wanted[field]
    assert decoded == expected
