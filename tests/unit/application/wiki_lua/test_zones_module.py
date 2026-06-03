from __future__ import annotations

from pathlib import Path

from tests.unit.application.wiki_lua.fakes import FakeZoneRepository, make_zone

from erenshor.application.wiki_lua.zones import build_zones_data, generate_zones_module, write_zones_module


def test_builds_zone_data_from_clean_zones() -> None:
    zone = make_zone(
        stable_key="zone:PortAzure",
        scene_name="PortAzure",
        display_name="Port Azure",
        wiki_page_name="Port Azure",
        image_name="Port Azure",
        is_dungeon=0,
        is_map_visible=1,
    )
    repo = FakeZoneRepository([zone], {"PortAzure": ["Fernalla's Revival Plains"]})

    data = build_zones_data(repo.get_all_zones(), repo)

    assert data == {
        "zones": {
            "zone:PortAzure": {
                "name": "Port Azure",
                "page": "Port Azure",
                "image": "Port Azure",
                "type": "Zone",
                "map": "zone:PortAzure",
                "connects": ["Fernalla's Revival Plains"],
            }
        },
    }


def test_marks_dungeon_zones() -> None:
    zone = make_zone(stable_key="zone:ElderstoneMines", scene_name="ElderstoneMines", is_dungeon=1)

    data = build_zones_data([zone], FakeZoneRepository([zone], {}))

    assert data["zones"]["zone:ElderstoneMines"]["type"] == "Dungeon"


def test_generates_zones_module_from_repository() -> None:
    module = generate_zones_module(FakeZoneRepository([make_zone()], {}))

    assert module.startswith("return {\n")
    assert '["zone:PortAzure"]' in module
    assert '["byPage"]' not in module


def test_writes_zones_module_to_data_module_path(tmp_path: Path) -> None:
    output_path = write_zones_module(FakeZoneRepository([make_zone()], {}), tmp_path)

    assert output_path == tmp_path / "Erenshor" / "Data" / "Zones.lua"
    assert output_path.read_text(encoding="utf-8").startswith("return {\n")
