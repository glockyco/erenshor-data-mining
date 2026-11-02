"""Schema 11 wire encoding for the embedded guide.

Rows omit property names for the two large placement tables. Json.NET reference
metadata shares identical paths, and the streaming reader expands pooled strings
without constructing a second JSON tree.
"""

from __future__ import annotations

import json
import struct
from collections import Counter
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


def _coordinate(value: float) -> int | float:
    """Use the shortest significant precision that preserves the DTO's float32."""
    bits = struct.pack("f", value)
    single = struct.unpack("f", bits)[0]
    for precision in range(1, 10):
        candidate = float(format(single, f".{precision}g"))
        if struct.pack("f", candidate) == bits:
            return int(candidate) if candidate.is_integer() and (candidate != 0 or bits == bytes(4)) else candidate
    raise ValueError(f"Coordinate cannot roundtrip float32: {value}")


def encode_guide(guide: dict[str, Any]) -> dict[str, Any]:
    """Encode DTO defaults, shared rows, paths and strings deterministically."""

    def defaults(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: defaults(member)
                for key, member in value.items()
                if member is not None
                and not (key in {"conditions", "entry_zone_line_keys"} and member == [])
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
                    and member is False
                )
                and not (key in {"xp", "gold"} and member == 0)
            }
        if isinstance(value, list):
            return [defaults(member) for member in value]
        return value

    result = defaults(guide)
    rows: set[int] = set()

    def row(value: dict[str, Any], fields: tuple[str, ...]) -> list[Any]:
        unknown = value.keys() - set(fields)
        if unknown:
            raise ValueError(f"Unknown guide row fields: {sorted(unknown)}")
        encoded: list[Any] = [sum(1 << index for index, key in enumerate(fields) if key in value)]
        # Placement DTOs consume float32, not the exporter's doubles.
        encoded.extend(
            _coordinate(value[key]) if key in {"x", "y", "z"} else value[key] for key in fields if key in value
        )
        rows.add(id(encoded))
        return encoded

    spawn_points: list[Any] = []
    spawn_indexes: dict[str, int] = {}
    for key, spawns in result["_character_spawns"].items():
        indexes = []
        for spawn in spawns:
            spawn_identity = json.dumps(spawn, separators=(",", ":"), sort_keys=True)
            if spawn_identity not in spawn_indexes:
                spawn_indexes[spawn_identity] = len(spawn_points)
                spawn_points.append(row(spawn, SPAWN_FIELDS))
            indexes.append(spawn_indexes[spawn_identity])
        result["_character_spawns"][key] = indexes
    result["_spawn_points"] = spawn_points
    result["_place_sets"] = {
        key: [row(place, PLACE_FIELDS) for place in places] for key, places in result["_place_sets"].items()
    }

    counts: Counter[str] = Counter()

    def identity(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)

    def shareable(value: Any) -> bool:
        # Reference metadata must never join structurally equal DTOs of different
        # types. Only these homogeneous guide paths and conditions are shared.
        if isinstance(value, dict):
            return (
                "acquisition_key" in value
                or ("type" in value and "name" in value and "kind" not in value)
                or "predicate" in value
                or "repeatable" in value
            )
        if isinstance(value, list) and value and id(value) not in rows:
            return all(isinstance(member, dict) and shareable(member) for member in value)
        return False

    def census(value: Any) -> None:
        if isinstance(value, (dict, list)):
            if shareable(value):
                counts[identity(value)] += 1
            for member in value.values() if isinstance(value, dict) else value:
                census(member)

    census(result)
    references: dict[str, str] = {}

    def share(value: Any) -> Any:
        if not isinstance(value, (dict, list)):
            return value
        key = identity(value)
        reference = None
        if shareable(value) and counts[key] > 1:
            if key in references:
                return {"$ref": references[key]}
            reference = str(len(references))
            references[key] = reference
        if isinstance(value, list):
            members = [share(member) for member in value]
            return {"$id": reference, "$values": members} if reference is not None else members
        mapping = {key: share(member) for key, member in value.items()}
        return {"$id": reference, **mapping} if reference is not None else mapping

    shared = share(result)
    strings: Counter[str] = Counter()

    def count_strings(value: Any) -> None:
        if isinstance(value, str):
            strings[value] += 1
        elif isinstance(value, dict):
            for key, member in value.items():
                if not key.startswith("$"):
                    strings[key] += 1
                    count_strings(member)
                elif key == "$values":
                    count_strings(member)
        elif isinstance(value, list):
            for member in value:
                count_strings(member)

    count_strings(shared)
    pool = sorted(
        value for value, count in strings.items() if (len(value) - 5) * (count - 1) > 8 or value.startswith("~")
    )
    pooled = {value: f"~{index}" for index, value in enumerate(pool)}

    def intern(value: Any, *, top: bool = False) -> Any:
        if isinstance(value, str):
            return pooled.get(value, value)
        if isinstance(value, dict):
            return {
                key if top or key.startswith("$") else pooled.get(key, key): (
                    member if key in {"$id", "$ref"} else intern(member)
                )
                for key, member in value.items()
            }
        if isinstance(value, list):
            return [intern(member) for member in value]
        return value

    return {"_strings": pool, **intern(shared, top=True)}
