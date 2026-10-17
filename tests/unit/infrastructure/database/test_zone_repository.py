"""Zone entities retain the clean build's public area classification."""

from pathlib import Path

import pytest

from erenshor.application.processor.writer import Writer
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.zones import ZoneRepository


@pytest.mark.parametrize("zone_type", ["Outdoor", "Dungeon", "Raid", "Event"])
def test_zone_classification_is_selected_not_inferred_from_native_dungeon_flag(tmp_path: Path, zone_type: str) -> None:
    path = tmp_path / "clean.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.insert_zones(
        [
            {
                "stable_key": "zone:fixture",
                "scene_name": "Fixture",
                "zone_name": "Fixture",
                "display_name": "Fixture",
                "wiki_page_name": "Fixture",
                "image_name": "",
                "is_dungeon": 0,
                "zone_type": zone_type,
                "raid_capable": 0,
                "use_zone_as_temp_bind": "",
                "achievement": "",
                "north_bearing": 0.0,
            }
        ]
    )
    database = DatabaseConnection(path, read_only=True)
    try:
        zones = ZoneRepository(database).get_all_zones()
        assert len(zones) == 1
        assert zones[0].zone_type == zone_type
        assert zones[0].is_dungeon == 0
    finally:
        database.close()
        writer.conn.close()


def test_legacy_zone_connections_exclude_stored_returns_and_nonfunctional_lines(tmp_path: Path) -> None:
    path = tmp_path / "clean.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.insert_zones(
        [
            {
                "stable_key": f"zone:{name}",
                "scene_name": name,
                "zone_name": name,
                "display_name": name,
                "wiki_page_name": name,
                "image_name": "",
                "zone_type": "Outdoor",
            }
            for name in ("A", "B", "Hidden")
        ]
    )
    writer.insert_zone_lines(
        [
            {
                "stable_key": key,
                "scene": "A",
                "destination_zone_stable_key": destination,
                "is_enabled": 0,
                "object_is_active": 0,
                "component_is_enabled": component_enabled,
                "collider_is_trigger": 1,
                "has_enabled_trigger": 1,
            }
            for key, destination, component_enabled in (
                ("line:fixed", "zone:B", 1),
                ("line:return", "zone:Hidden", 1),
                ("line:nonfunctional", "zone:Hidden", 0),
            )
        ]
    )
    writer.insert_zone_line_destination_contexts(
        [
            {
                "zone_line_stable_key": "line:return",
                "kind": "stored_return",
                "destination_state_key": "portal.return_zone",
                "landing_state_key": "portal.return_position",
                "source_key": "controller:return",
            }
        ]
    )
    database = DatabaseConnection(path, read_only=True)
    try:
        assert ZoneRepository(database).get_zone_connections("A") == ["B"]
    finally:
        database.close()
        writer.conn.close()
