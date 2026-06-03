"""Generate compact Lua data modules for zone wiki pages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.zone import Zone

LuaData = dict[str, object]


class ZoneDataRepository(Protocol):
    """Repository methods needed to build the zone data module."""

    def get_all_zones(self) -> list[Zone]: ...

    def get_zone_connections(self, scene_name: str) -> list[str]: ...


def generate_zones_module(zone_repo: ZoneDataRepository) -> str:
    """Generate `Module:Erenshor/Data/Zones` from clean DB repositories."""
    return module_text(build_zones_data(zone_repo.get_all_zones(), zone_repo))


def write_zones_module(zone_repo: ZoneDataRepository, output_root: Path) -> Path:
    """Write the generated zone data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Zones.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_zones_module(zone_repo), encoding="utf-8")
    return output_path


def build_zones_data(zones: Iterable[Zone], connection_repo: ZoneDataRepository) -> LuaData:
    """Build the serializable zone data table for `mw.loadData()`."""
    zone_rows: dict[str, LuaData] = {}
    by_page: dict[str, str] = {}

    for zone in sorted(zones, key=lambda candidate: candidate.stable_key):
        record = _zone_record(zone, connection_repo.get_zone_connections(zone.scene_name))
        if record is None:
            continue
        zone_rows[zone.stable_key] = record
        page = record.get("page")
        if isinstance(page, str) and page:
            by_page[page] = zone.stable_key

    return {"zones": zone_rows, "byPage": dict(sorted(by_page.items()))}


def _zone_record(zone: Zone, connections: list[str]) -> LuaData | None:
    name = zone.display_name or zone.zone_name or zone.wiki_page_name
    page = zone.wiki_page_name or name
    if name is None or page is None:
        return None

    record: LuaData = {
        "name": name,
        "page": page,
        "type": "Dungeon" if zone.is_dungeon else "Zone",
    }
    _put(record, "image", zone.image_name)
    if zone.is_map_visible:
        record["map"] = f"zone:{zone.scene_name}"
    if connections:
        record["connects"] = connections
    return record


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value
