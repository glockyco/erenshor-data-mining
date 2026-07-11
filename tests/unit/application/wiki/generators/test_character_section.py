from __future__ import annotations

from tests.unit.application.wiki_lua.fakes import make_character

from erenshor.application.wiki.generators.sections.character import CharacterSectionGenerator
from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import ZoneLink


def _spawn(
    *,
    chance: float | None,
    x: float,
    source_script: str | None = None,
) -> CharacterSpawnInfo:
    return CharacterSpawnInfo(
        zone_link=ZoneLink(page_title="Plane of Fernalla", display_name="Plane of Fernalla"),
        base_respawn=None,
        x=x,
        y=24.6,
        z=1151.0,
        spawn_chance=chance,
        is_rare=False,
        is_unique=True,
        source_script=source_script,
    )


def _render(spawn_infos: list[CharacterSpawnInfo]) -> str:
    character = make_character(
        display_name="Faerie Trickster",
        npc_name="Faerie Trickster",
        wiki_page_name="Faerie Trickster",
        is_unique=1,
        is_common=0,
    )
    return CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=spawn_infos, spells=[]),
        page_title="Faerie Trickster",
    )


def test_dynamic_only_spawn_has_no_fabricated_chance() -> None:
    content = _render([_spawn(chance=None, x=1124.2, source_script="SprinklesEvent")])

    assert "|spawnchance=" in content
    assert "|spawnchance=1%" not in content
    assert "|spawntype=Dynamic event spawn" in content
    assert "|coordinates=1124.2 x 24.6 x 1151.0" in content
    assert "SprinklesEvent" not in content


def test_dynamic_only_multiple_spawns_keep_all_coordinates() -> None:
    content = _render(
        [
            _spawn(chance=None, x=1124.2, source_script="SprinklesEvent"),
            _spawn(chance=None, x=1180.5, source_script="SprinklesEvent"),
        ]
    )

    assert "|coordinates=1124.2 x 24.6 x 1151.0<br>1180.5 x 24.6 x 1151.0" in content


def test_mixed_dynamic_and_ordinary_spawns_keep_ordinary_chance_and_coords() -> None:
    content = _render(
        [
            _spawn(chance=25.0, x=700.0),
            _spawn(chance=None, x=1124.2, source_script="SprinklesEvent"),
        ]
    )

    assert "|spawnchance=25%" in content
    assert "|coordinates=700.0 x 24.6 x 1151.0" in content
    assert "|spawntype=" in content
    assert "|spawntype=World and dynamic event spawns" not in content
    assert "1%" not in content
