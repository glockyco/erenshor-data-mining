"""Generate zone summaries and conditional exits without estimating encounter frequency."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.views import DataView, ViewDataError, ViewField, native_reference, view_module_text
from erenshor.domain.value_objects.npc_level import npc_level_bounds

if TYPE_CHECKING:
    from erenshor.domain.entities.zone import Zone

ZONES = DataView(
    module="Zones",
    description="Zone overview. One summary row and zero or more connection rows per zone. "
    "Hostiles are damageable, nonfriendly enemies, elites and bosses in wiki-visible placements. "
    "Each deduplicated character contributes one possible level interval across its placements. "
    "Minimum and maximum are the outer bounds. Median bounds are the medians of the lower and upper endpoints, "
    "with the two middle endpoints averaged for an even population. "
    "They bound the median, not a likely encounter level. "
    "Spawn counts and chances do not weight the population. "
    "Player-scaling characters have no fixed level contribution. "
    "Connections describe physical exits, not currently satisfied player gates. "
    "Stored returns have no fixed destination.",
    entity="zone",
    fields=(
        ViewField("type", "text", "summary or connection."),
        ViewField("zoneType", "text", "Public zone classification from the clean database.", optional=True),
        ViewField(
            "hostileCount",
            "integer",
            "Distinct deduplicated hostile characters, including scaling characters.",
            optional=True,
        ),
        ViewField(
            "scalingCount",
            "integer",
            "Hostile characters with player-dependent levels, excluded from level statistics.",
            optional=True,
        ),
        ViewField("levelMin", "integer", "Lowest possible fixed hostile level.", optional=True),
        ViewField("levelMedianMin", "number", "Lower bound of the median fixed hostile level.", optional=True),
        ViewField("levelMedianMax", "number", "Upper bound of the median fixed hostile level.", optional=True),
        ViewField("levelMax", "integer", "Highest possible fixed hostile level.", optional=True),
        ViewField("line", "text", "Native zone-line identity.", optional=True),
        ViewField("kind", "text", "fixed or stored_return.", optional=True),
        ViewField("destination", "reference", "Native destination zone. Absent for stored returns.", optional=True),
        ViewField(
            "conditional",
            "boolean",
            "Exit has a gate or starts inactive. Does not evaluate player state.",
            optional=True,
        ),
    ),
)


class ZoneOverviewRepository(Protocol):
    def get_all_zones(self) -> Sequence[Zone]: ...

    def get_zone_overview_spawns(self) -> list[dict[str, object]]: ...

    def get_zone_overview_connections(self) -> list[dict[str, object]]: ...


def build_zone_overview_rows(
    zone_types: Mapping[str, str],
    spawns: Sequence[Mapping[str, object]],
    connections: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Bound a character-weighted median without inventing spawn probabilities or realized rolls."""
    populations: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    scaling: dict[str, set[str]] = defaultdict(set)
    for spawn in spawns:
        zone = str(spawn["zone"])
        if zone not in zone_types:
            continue
        if spawn["tier"] not in {"enemy", "elite", "boss"} or not spawn["damageable"] or spawn["friendly"]:
            continue
        character = str(spawn["character"])
        if spawn["scales"]:
            scaling[zone].add(character)
            continue
        level = int(str(spawn["level"])) + int(str(spawn["levelMod"]))
        low, high = npc_level_bounds(level, bool(spawn["group"]))
        previous = populations[zone].get(character, (low, high))
        populations[zone][character] = min(low, previous[0]), max(high, previous[1])
    rows: dict[str, list[dict[str, object]]] = {}
    for zone, zone_type in sorted(zone_types.items()):
        # A group that includes a scaling copy cannot have a bounded fixed interval.
        fixed = {key: bounds for key, bounds in populations[zone].items() if key not in scaling[zone]}
        summary: dict[str, object] = {
            "type": "summary",
            "zoneType": zone_type,
            "hostileCount": len(fixed) + len(scaling[zone]),
            "scalingCount": len(scaling[zone]),
        }
        if fixed:
            lows, highs = zip(*fixed.values(), strict=True)
            summary.update(
                levelMin=min(lows),
                levelMedianMin=median(lows),
                levelMedianMax=median(highs),
                levelMax=max(highs),
            )
        rows[zone] = [summary]
    for connection in sorted(connections, key=lambda row: (str(row["zone"]), str(row["line"]))):
        zone = str(connection["zone"])
        if zone not in rows:
            continue
        kind = connection["kind"]
        if kind not in {"fixed", "stored_return"}:
            raise ViewDataError(f"{ZONES.title}: unknown connection kind {kind!r} for {connection['line']}")
        row = {
            "type": "connection",
            "line": connection["line"],
            "kind": kind,
            "conditional": bool(connection["conditional"]),
        }
        if kind == "fixed":
            if not connection.get("destination"):
                raise ViewDataError(f"{ZONES.title}: fixed connection {connection['line']} has no destination")
            row["destination"] = connection["destination"]
        rows[zone].append(row)
    return rows


def write_zones_module(
    repo: ZoneOverviewRepository,
    known_keys: Collection[str],
    output_root: Path,
    *,
    native_catalog: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write the checked overview using exported public zone types and native zone identities."""
    zone_types = {zone.stable_key: zone.zone_type for zone in repo.get_all_zones() if zone.wiki_page_name is not None}
    rows = build_zone_overview_rows(zone_types, repo.get_zone_overview_spawns(), repo.get_zone_overview_connections())
    for zone_rows in rows.values():
        for row in zone_rows:
            if "destination" in row:
                row["destination"] = native_reference(str(row["destination"]), native_catalog, kind="zone")
    content = view_module_text(ZONES, rows, known_keys, reference_catalog=native_catalog)
    path = output_root / "Erenshor" / "Data" / "Zones.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
