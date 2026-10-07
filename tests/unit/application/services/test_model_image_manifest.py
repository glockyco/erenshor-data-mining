from __future__ import annotations

import pytest

from erenshor.application.services.model_image_manifest import CharacterSource, build_manifest


def _character(
    stable_key: str,
    image_title: str,
    *,
    wiki_page: str | None = None,
    resources_path: str | None = None,
    scene: str | None = None,
    object_name: str | None = "",
    is_enabled: bool = True,
    is_wiki_generated: bool = True,
    spawn_points: tuple[tuple[str, float, float, float], ...] = (),
    is_summon: bool = False,
) -> CharacterSource:
    placed = resources_path is None and scene is not None
    name = image_title.removesuffix(".png") if object_name == "" else object_name
    return CharacterSource(
        stable_key=stable_key,
        image_title=image_title,
        wiki_page=wiki_page,
        object_name=name,
        npc_name=name,
        scene=scene if placed else None,
        position=(1.0, 2.0, 3.0) if placed else None,
        is_prefab=not placed,
        is_enabled=is_enabled,
        is_wiki_generated=is_wiki_generated,
        resources_path=resources_path,
        spawn_points=spawn_points,
        is_summon=is_summon,
    )


def test_characters_that_share_a_model_share_one_capture_with_the_pages_of_all() -> None:
    # The Vithean chests of the arena rounds share one model. Round 9 is placed
    # in the scene and has no page of its own.
    characters = [
        _character(
            "character:arenachest 2",
            "Vithean Chest.png",
            wiki_page="Vithean Chest",
            resources_path="npcs/plane of vitheo/ArenaChest 2",
        ),
        _character(
            "character:arenachest 1",
            "Vithean Chest.png",
            wiki_page="Vithean Chest",
            resources_path="npcs/plane of vitheo/ArenaChest 1",
        ),
        _character("character:arenachest 9", "Vithean Chest.png", scene="PlaneOfVitheo", is_wiki_generated=False),
        _character("character:honsus", "Honsus.png", wiki_page="Honsus", resources_path="npcs/Honsus"),
    ]

    manifest = build_manifest(characters, {}, "24405256")

    assert [(entry.file, entry.stable_key, entry.pages) for entry in manifest.entries] == [
        ("Honsus.png", "character:honsus", ("Honsus",)),
        ("Vithean Chest.png", "character:arenachest 1", ("Vithean Chest",)),
    ]
    assert manifest.entries[1].source.resources_path == "npcs/plane of vitheo/ArenaChest 1"


def test_every_model_is_captured_whether_or_not_a_page_shows_it() -> None:
    characters = [
        _character("character:watchman", "Watchman.png", resources_path="npcs/Watchman", is_wiki_generated=False),
        _character(
            "character:summoned treant",
            "Summoned: Treant.png",
            wiki_page="Summoned: Treant",
            resources_path="npcs/Treant",
            is_summon=True,
        ),
    ]

    manifest = build_manifest(characters, {}, "24405256")

    assert [(entry.file, entry.kind, entry.pages) for entry in manifest.entries] == [
        ("Summoned: Treant.png", "summon", ("Summoned: Treant",)),
        ("Watchman.png", "character", ()),
    ]


def test_a_placed_character_or_a_scene_prefab_is_the_source_without_a_resources_prefab() -> None:
    characters = [
        # Faith's prefab is outside Resources, and a FaithEvent of the scene references it.
        _character(
            "character:faith",
            "Faith.png",
            wiki_page="Faith",
            spawn_points=(("PlaneOfSoluna", 361.9, 327.1, 1346.7), ("PlaneOfSoluna", 275.6, 327.1, 1346.7)),
        ),
        _character(
            "character:dummy:reliquary:1",
            "Training Dummy (1000 AC).png",
            wiki_page="Training Dummy",
            scene="Reliquary",
            is_enabled=False,
        ),
    ]

    manifest = build_manifest(characters, {}, "24405256")

    sources = {entry.file: entry.source for entry in manifest.entries}
    # The player lands at Faith's first spawn point while the scene loads.
    faith = sources["Faith.png"]
    assert (faith.scene, faith.object_name, faith.position, faith.landing) == (
        "PlaneOfSoluna",
        "Faith",
        None,
        (361.9, 327.1, 1346.7),
    )
    dummy = sources["Training Dummy (1000 AC).png"]
    assert (dummy.scene, dummy.position, dummy.landing) == ("Reliquary", (1.0, 2.0, 3.0), (1.0, 2.0, 3.0))


def test_a_model_without_a_game_object_is_listed_apart() -> None:
    characters = [_character("character:old friend", "Old Friend.png", wiki_page="Old Friend", object_name=None)]

    manifest = build_manifest(characters, {}, "24405256")

    assert manifest.entries == ()
    assert [(model.file, model.pages) for model in manifest.unsourced] == [("Old Friend.png", ("Old Friend",))]


def test_an_unused_page_names_the_model_of_its_character() -> None:
    # The unused rune receptacles show the shared receptacle model. Every
    # receptacle is off at load, and the one of the generated page is captured.
    characters = [
        _character(
            "character:receptacle-sand",
            "Portal Receptacle.png",
            scene="Reliquary",
            is_enabled=False,
            is_wiki_generated=False,
        ),
        _character(
            "character:receptacle:reliquary:2",
            "Portal Receptacle.png",
            wiki_page="Portal Receptacle",
            scene="Reliquary",
            is_enabled=False,
        ),
    ]

    manifest = build_manifest(characters, {"Braxonian Receptacle": "character:receptacle-sand"}, "24405256")

    assert [(entry.file, entry.stable_key, entry.pages) for entry in manifest.entries] == [
        ("Portal Receptacle.png", "character:receptacle:reliquary:2", ("Braxonian Receptacle", "Portal Receptacle"))
    ]


def test_an_unused_page_needs_its_character() -> None:
    with pytest.raises(ValueError, match="not in the clean database"):
        build_manifest([], {"Holy Corpse": "character:holy corpse"}, "24405256")
