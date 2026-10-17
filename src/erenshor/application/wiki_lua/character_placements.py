"""Present the shared copy-keyed placement projection without selecting spawns."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import cast
from urllib.parse import quote


def _link(key: str, catalog: Mapping[str, Mapping[str, object]]) -> str:
    if key not in catalog:
        raise ValueError(f"Character placement references missing canonical identity {key!r}")
    row = catalog[key]
    name, page = str(row["name"]), row.get("page")
    return f"[[{page}|{name}]]" if page and page != name else f"[[{page}]]" if page else name


def _gate_text(atom: Mapping[str, object], catalog: Mapping[str, Mapping[str, object]]) -> str:
    kind, key = atom["atom_kind"], str(atom["atom_stable_key"])
    if kind == "quest_done":
        return "complete " + _link(key, catalog)
    if kind == "quest_not_done":
        return "not complete " + _link(key, catalog)
    if kind in ("item_held", "key_held"):
        return "carry " + _link(key, catalog)
    if kind == "room_furnished":
        return "furnish room " + str(atom["atom_slot"]) + " with " + _link(key, catalog)
    if kind == "encounter_won":
        return "defeat " + _link(key, catalog)
    if kind == "never":
        return "unavailable"
    raise ValueError(f"Unsupported shared placement gate {kind!r}")


def _release_text(release: Mapping[str, object], catalog: Mapping[str, Mapping[str, object]]) -> str | None:
    kind, key = release["condition_kind"], str(release["condition_stable_key"])
    if kind in ("controller", "object", "spawn_point", "character"):
        return None
    if kind == "quest_variant":
        quest = release.get("quest_stable_key")
        if not quest:
            raise ValueError(f"Missing canonical quest for native release variant {key!r}")
        return "Vulnerable after turning in " + _link(str(quest), catalog)
    if kind == "character_dead":
        return "Vulnerable after defeating " + _link(key, catalog)
    if kind == "spawn_point_cleared":
        return "Vulnerable after clearing the linked encounter"
    if kind == "state":
        labels = {
            "protector_null": None,
            "raining": "Vulnerable during rain",
            "dry_after_rain": "Vulnerable after rain ends",
            "requires_prior_damage": "Vulnerability changes during combat",
            "aggro_then_ward_death": "Vulnerable after its combat ward is defeated",
            "random_ward_unprotected": "Can appear without a protective ward",
            "aggro_empty_ward_list": "Vulnerable when combat begins",
        }
        if key not in labels:
            raise ValueError(f"Unsupported native damage-release state {key!r}")
        return labels[key]
    raise ValueError(f"Unsupported native damage-release condition {kind!r}")


def build_character_locations(
    placements: Sequence[Mapping[str, object]],
    catalog: Mapping[str, Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Retain every projected placement, its native fields and supported conditions."""
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    for source in placements:
        representative = str(source["representative_stable_key"])
        member = str(source["character_stable_key"])
        possible_treasure = source.get("placement_kind") == "possible_treasure"
        native_key = (
            [member, source["chest_character_stable_key"], source["treasure_location_stable_key"]]
            if possible_treasure
            else [member, source.get("spawn_point_stable_key"), source.get("is_directly_placed")]
        )
        row: dict[str, object] = {
            "id": json.dumps(native_key, separators=(",", ":")),
            "memberKey": member,
            "native": dict(source),
            "levelMod": source["level_mod"] if source.get("level_mod") is not None else 0,
            "group": bool(source.get("group_encounter")),
            "night": bool(source.get("night_spawn")),
            "canBeDamaged": bool(source["can_be_damaged"]),
            "initialInvulnerable": bool(source["initial_invulnerable"]),
            "kind": source.get("placement_kind", "placement"),
        }
        zone = source.get("zone_stable_key")
        if zone:
            zone_key = str(zone)
            if zone_key not in catalog:
                raise ValueError(f"Character placement references missing zone {zone_key!r}")
            row["zone"] = {"key": zone_key, **dict(catalog[zone_key])}
        for source_field, target in (
            ("x", "x"),
            ("y", "y"),
            ("z", "z"),
            ("spawn_chance", "chance"),
            ("spawn_delay_4", "respawnSeconds"),
            ("furniture_item_stable_key", "furniture"),
        ):
            if possible_treasure and source_field in ("x", "y", "z"):
                continue
            if source.get(source_field) is not None:
                row[target] = source[source_field]
        conditions: list[dict[str, object]] = []
        if possible_treasure:
            row["treasureRole"] = source["treasure_role"]
            row["playerLevelMin"] = source["player_level_min"]
            row["playerLevelMax"] = source["player_level_max"]
            conditions.append(
                {
                    "text": (
                        f"Possible treasure hunt for player levels "
                        f"{source['player_level_min']}-{source['player_level_max']}"
                    ),
                }
            )
        if source.get("night_spawn"):
            conditions.append(
                {"text": "At night", "predicate": "time_of_day", "value": "night", "phase": "availability"}
            )
        quest = source.get("spawn_upon_quest_complete_stable_key")
        if quest:
            conditions.append(
                {
                    "text": "After completing " + _link(str(quest), catalog),
                    "predicate": "quest_done",
                    "reference_stable_key": quest,
                    "phase": "availability",
                }
            )
        for stop_quest in cast("Sequence[str]", source["stop_quests"]):
            conditions.append(
                {
                    "text": "Before completing " + _link(str(stop_quest), catalog),
                    "predicate": "quest_not_done",
                    "reference_stable_key": stop_quest,
                    "phase": "availability",
                }
            )
        protector = source.get("protector_representative_stable_key")
        if protector:
            conditions.append(
                {
                    "text": "Protected by " + _link(str(protector), catalog),
                    "native_protector_stable_key": source.get("protector_stable_key"),
                }
            )
        trigger = source.get("trigger_item_stable_key")
        if trigger:
            mode = source.get("trigger_mode")
            if mode != "proximity_auto_consume":
                raise ValueError(f"Unsupported native character trigger mode {mode!r}")
            conditions.append(
                {
                    "text": "Approach with " + _link(str(trigger), catalog) + " (consumed)",
                    "native_trigger_mode": mode,
                    "reference_stable_key": trigger,
                }
            )
        furniture = source.get("furniture_item_stable_key")
        if furniture:
            slot = source.get("furniture_slot")
            if not slot:
                raise ValueError(f"{member}: furnished placement has no native room slot")
            conditions.append(
                {
                    "text": "Room " + str(slot) + " furnished with " + _link(str(furniture), catalog),
                    "predicate": "room_furnished",
                    "reference_stable_key": furniture,
                    "value": slot,
                    "phase": "availability",
                }
            )
        gates: dict[tuple[str, str, str], dict[int, list[Mapping[str, object]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for atom in cast("Sequence[Mapping[str, object]]", source["gates"]):
            identity = (str(atom["subject_kind"]), str(atom["subject_stable_key"]), str(atom["gate"]))
            gates[identity][cast("int", atom["group_index"])].append(atom)
        for identity, alternatives in sorted(gates.items()):
            groups = [
                " and ".join(_gate_text(atom, catalog) for atom in atoms) for _, atoms in sorted(alternatives.items())
            ]
            conditions.append(
                {
                    "text": "Requires " + " or ".join("(" + group + ")" for group in groups),
                    "native_gate": list(identity),
                }
            )
        entries = cast("Sequence[Mapping[str, object]]", source["entries"])
        if entries:
            labels = []
            for entry in entries:
                key = entry["source_zone_key"]
                if not key or any(entry[axis] is None for axis in ("x", "y", "z")):
                    raise ValueError("A restricted character entry lacks actual source-zone coordinates")
                labels.append(_link(str(key), catalog) + f" ({entry['x']}, {entry['y']}, {entry['z']})")
            conditions.append(
                {"text": "Reachable through the entry from " + " or ".join(labels), "native_entries": list(entries)}
            )
        for release in cast("Sequence[Mapping[str, object]]", source["damage_releases"]):
            if not release["can_release"] or not release["controller_enabled"]:
                continue
            text = _release_text(release, catalog)
            if text:
                conditions.append({"text": text, "native_damage_release": dict(release)})
        if source.get("placement_kind") == "unplaced" and not conditions:
            continue
        row["conditions"] = conditions
        mapped = (
            source.get("member_is_map_visible") == 1
            and source.get("is_map_visible") != 0
            and source.get("zone_is_map_visible") == 1
            and source.get("spawn_point_stable_key") is not None
            and all(source.get(axis) is not None for axis in ("x", "y", "z"))
            and ((cast("float | None", source.get("spawn_chance")) or 0) > 0 or source.get("source_script") is not None)
        )
        if mapped:
            row["mapUrl"] = "https://erenshor.compendiums.org/map?sel=" + quote(
                "marker:" + str(source["spawn_point_stable_key"]), safe=""
            )
        result[representative].append(row)
    return dict(result)
