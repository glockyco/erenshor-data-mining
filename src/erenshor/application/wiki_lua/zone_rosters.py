"""Generate deduplicated zone rosters without implying fixed positions for scripted encounters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Protocol, cast

from erenshor.application.wiki_lua.views import DataView, ViewField, native_reference, view_module_text
from erenshor.domain.value_objects.npc_level import npc_level_bounds

ZONE_ROSTERS = DataView(
    module="ZoneRosters",
    description="Characters placed in each zone. "
    "Separate rows preserve alternative spawn conditions, not spawn counts.",
    entity="zone",
    fields=(
        ViewField(
            "character",
            "key",
            "The canonical character key for this wiki page and encounter tier. "
            "Copies sharing a page contribute their ranges and conditions.",
        ),
        ViewField("tier", "text", "The encounter tier: enemy, elite, boss, npc, or chest."),
        ViewField(
            "levelMin", "integer", "Lowest possible level, including spawn modifiers and NPC initialization variance."
        ),
        ViewField(
            "levelMax", "integer", "Highest possible level, including spawn modifiers and NPC initialization variance."
        ),
        ViewField("scales", "boolean", "Whether the character's level scales with the player."),
        ViewField("night", "boolean", "Whether these placements spawn only at night."),
        ViewField("rare", "boolean", "Whether these placements include the rare spawn pool."),
        ViewField(
            "chanceMin",
            "number",
            "Lowest percentage chance per eligible spawn roll, from 0 to 100. Not a zone-wide encounter chance.",
            optional=True,
        ),
        ViewField(
            "chanceMax", "number", "Highest percentage chance per eligible spawn roll, from 0 to 100.", optional=True
        ),
        ViewField(
            "script",
            "text",
            "The source script, when it controls spawning. No fixed position is implied.",
            optional=True,
        ),
        ViewField("furniture", "key", "The furniture set that must be placed in the Reliquary.", optional=True),
        ViewField("quest", "reference", "The quest whose completion enables this spawn.", optional=True),
        ViewField("stopQuests", "references", "Quests whose completion stops this spawn.", optional=True),
        ViewField("triggerItem", "key", "The item that triggers the encounter.", optional=True),
        ViewField("protector", "key", "The protector associated with this spawn.", optional=True),
    ),
)


class ZoneRosterRepository(Protocol):
    def get_zone_roster_spawns(self) -> list[dict[str, object]]: ...


def build_zone_roster_rows(spawns: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Fold copies with the same conditions, keeping different conditions as alternative rows."""
    groups: dict[tuple[object, ...], dict[str, object]] = {}
    condition_fields = ("script", "furniture", "quest", "triggerItem", "protector")
    for spawn in spawns:
        conditions = {name: spawn[name] for name in condition_fields if spawn.get(name) is not None}
        stop_quests = sorted(set(cast("list[str]", spawn.get("stopQuests", []))))
        if stop_quests:
            conditions["stopQuests"] = stop_quests
        key = (
            spawn["zone"],
            spawn["character"],
            spawn["tier"],
            bool(spawn["night"]),
            bool(spawn["rare"]),
            bool(spawn["scales"]),
            *(spawn.get(name) for name in condition_fields),
            tuple(stop_quests),
        )
        level = int(str(spawn["level"])) + int(str(spawn.get("levelMod", 0)))
        low, high = npc_level_bounds(level, bool(spawn["group"]))
        row = groups.get(key)
        if row is None:
            row = {
                "character": spawn["character"],
                "tier": spawn["tier"],
                "levelMin": low,
                "levelMax": high,
                "scales": bool(spawn["scales"]),
                "night": bool(spawn["night"]),
                "rare": bool(spawn["rare"]),
                **conditions,
            }
            groups[key] = row
        else:
            row["levelMin"] = min(int(str(row["levelMin"])), low)
            row["levelMax"] = max(int(str(row["levelMax"])), high)
        chance = spawn.get("chance")
        if chance is not None:
            value = float(str(chance))
            row["chanceMin"] = min(float(str(row.get("chanceMin", value))), value)
            row["chanceMax"] = max(float(str(row.get("chanceMax", value))), value)
    rows: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for key, row in sorted(groups.items(), key=lambda entry: str(entry[0])):
        rows[str(key[0])].append(row)
    return dict(rows)


def write_zone_rosters_module(
    repo: ZoneRosterRepository,
    known_keys: Collection[str],
    output_root: Path,
    *,
    quest_catalog: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write the checked zone roster view below an output root."""
    rows = build_zone_roster_rows(repo.get_zone_roster_spawns())
    native_quests = {key: value for key, value in quest_catalog.items() if key.startswith("quest:")}

    for roster in rows.values():
        for row in roster:
            if row.get("quest") is not None:
                row["quest"] = native_reference(cast("str", row["quest"]), native_quests, kind="quest")
            if row.get("stopQuests") is not None:
                row["stopQuests"] = [
                    native_reference(key, native_quests, kind="quest") for key in cast("list[str]", row["stopQuests"])
                ]
    path = output_root / "Erenshor" / "Data" / "ZoneRosters.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        view_module_text(ZONE_ROSTERS, rows, known_keys, reference_catalog=native_quests),
        encoding="utf-8",
    )
    return path
