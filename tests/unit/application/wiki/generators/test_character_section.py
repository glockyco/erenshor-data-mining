from __future__ import annotations

from dataclasses import replace

from tests.unit.application.wiki_lua.fakes import make_character

from erenshor.application.wiki.generators.sections.categories import CategoryGenerator
from erenshor.application.wiki.generators.sections.character import CharacterSectionGenerator
from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.value_objects.loot import LootDropDisplayInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import ItemLink, ZoneLink


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
        source_script=source_script,
    )


def _render(spawn_infos: list[CharacterSpawnInfo]) -> str:
    character = make_character(
        display_name="Faerie Trickster",
        npc_name="Faerie Trickster",
        wiki_page_name="Faerie Trickster",
        encounter_tier="boss",
    )
    return CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=spawn_infos, spells=[]),
        page_title="Faerie Trickster",
    )


def test_elite_type_and_rare_placement_chance_are_independent() -> None:
    character = make_character(encounter_tier="elite")
    spawn = _spawn(chance=25.0, x=700.0)
    content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=[spawn], spells=[]),
        page_title="Faerie Trickster",
    )

    assert "|type=Elite" in content
    assert "|spawnchance=25%" in content


def test_ordinary_enemy_shows_rare_placement_chance() -> None:
    character = make_character(encounter_tier="enemy")
    spawn = _spawn(chance=10.0, x=700.0)

    content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=[replace(spawn, is_rare=True)], spells=[]),
        page_title="Faerie Trickster",
    )

    assert "|type=Enemy" in content
    assert "|spawnchance=10%" in content


def test_character_categories_follow_encounter_tier() -> None:
    generator = CategoryGenerator()
    for tier, expected in (
        ("npc", ["Characters"]),
        ("boss", ["Enemies", "Bosses"]),
        ("elite", ["Enemies", "Elites"]),
        ("enemy", ["Enemies"]),
        ("chest", ["Chests"]),
    ):
        enriched = EnrichedCharacterData(character=make_character(encounter_tier=tier), spawn_infos=[], spells=[])
        assert generator.generate_character_categories(enriched) == expected


def test_dynamic_only_spawn_has_no_fabricated_chance() -> None:
    content = _render([_spawn(chance=None, x=1124.2, source_script="SprinklesEvent")])

    assert "|spawnchance=" in content
    assert "|spawnchance=1%" not in content
    assert "|spawntype=Event spawn" in content
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


def test_character_loot_drop_fields_render_rates_refs_and_guaranteed_pool() -> None:
    character = make_character(
        display_name="Faerie Trickster",
        npc_name="Faerie Trickster",
        wiki_page_name="Faerie Trickster",
        encounter_tier="boss",
    )
    drops = [
        LootDropDisplayInfo(
            item_link=ItemLink(page_title="Beta Blade", display_name="Beta Blade"),
            drop_probability=15.0,
            is_guaranteed=True,
            is_visible=True,
            item_unique=False,
        ),
        LootDropDisplayInfo(
            item_link=ItemLink(page_title="Alpha Armor", display_name="Alpha Armor"),
            drop_probability=30.0,
            is_guaranteed=False,
            is_visible=False,
            item_unique=True,
        ),
        LootDropDisplayInfo(
            item_link=ItemLink(page_title="Common Coin", display_name="Common Coin"),
            drop_probability=5.0,
            is_guaranteed=False,
            is_visible=False,
            item_unique=False,
        ),
    ]

    content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=[], spells=[], loot_drops=drops),
        page_title="Faerie Trickster",
    )

    rates = content.split("|droprates=", 1)[1].split("\n", 1)[0]
    assert rates.index("Alpha Armor") < rates.index("Beta Blade") < rates.index("Common Coin")
    assert "If Faerie Trickster has {{ItemLink|Beta Blade}} equipped, it is guaranteed to drop." in content
    assert (
        "If the player is already holding {{ItemLink|Alpha Armor}} in their inventory, another will not drop."
        in content
    )
    assert "|guaranteeddrops=\n" in content

    two_guaranteed = [
        drops[0],
        LootDropDisplayInfo(
            item_link=drops[1].item_link,
            drop_probability=drops[1].drop_probability,
            is_guaranteed=True,
            is_visible=drops[1].is_visible,
            item_unique=drops[1].item_unique,
        ),
        drops[2],
    ]
    guaranteed_content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=character, spawn_infos=[], spells=[], loot_drops=two_guaranteed),
        page_title="Faerie Trickster",
    )
    guaranteed = guaranteed_content.split("|guaranteeddrops=", 1)[1].split("\n", 1)[0]
    assert guaranteed == "{{ItemLink|Alpha Armor}}<br>{{ItemLink|Beta Blade}}"
    assert "|guaranteedrolls=" not in guaranteed_content

    two_rolls = character.model_copy(update={"guaranteed_drop_rolls": 2})
    rolled_content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=two_rolls, spawn_infos=[], spells=[], loot_drops=two_guaranteed),
        page_title="Faerie Trickster",
    )
    assert "|guaranteeddrops={{ItemLink|Alpha Armor}}<br>{{ItemLink|Beta Blade}}\n|guaranteedrolls=Two\n" in (
        rolled_content
    )

    # Without a shown pool there is nothing for the label to describe.
    no_pool_content = CharacterSectionGenerator().generate_template(
        EnrichedCharacterData(character=two_rolls, spawn_infos=[], spells=[], loot_drops=drops),
        page_title="Faerie Trickster",
    )
    assert "|guaranteedrolls=" not in no_pool_content
    assert "|guaranteeddrops=\n|droprates=" in no_pool_content
