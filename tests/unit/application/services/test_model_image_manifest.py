from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from erenshor.application.services.model_image_manifest import (
    CharacterSource,
    build_manifest,
    page_image_uses,
    unused_page_image_uses,
)


def _character(
    stable_key: str,
    image_name: str,
    *,
    resources_path: str | None = None,
    scene: str | None = None,
    is_enabled: bool = True,
    is_wiki_generated: bool = True,
    spawn_points: tuple[tuple[str, float, float, float], ...] = (),
    is_summon: bool = False,
) -> CharacterSource:
    placed = resources_path is None and scene is not None
    return CharacterSource(
        stable_key=stable_key,
        image_name=image_name,
        object_name=image_name,
        npc_name=image_name,
        scene=scene if placed else None,
        position=(1.0, 2.0, 3.0) if placed else None,
        is_prefab=not placed,
        is_enabled=is_enabled,
        is_wiki_generated=is_wiki_generated,
        resources_path=resources_path,
        spawn_points=spawn_points,
        is_summon=is_summon,
    )


def _uploaded(*files: str) -> Callable[[Sequence[str]], frozenset[str]]:
    """A stand-in for MediaWikiClient.get_uploaded_files that knows the given files."""

    def lookup(titles: Sequence[str]) -> frozenset[str]:
        return frozenset(title for title in titles if title.removeprefix("File:") in files)

    return lookup


def _infobox(name: str, *, stable_key: str = "", image: str = "", imagefile: str = "", extra: str = "") -> str:
    return (
        f"{{{{Character\n|name={name}\n|stablekey={stable_key}\n|image={image}\n|imagefile={imagefile}\n{extra}}}}}\n"
    )


def test_a_missing_file_appears_once_with_every_page_and_one_object() -> None:
    # Three Vithean chests share one image: the chest page and two boss pages
    # whose editors added the chest box.
    pages = {
        "Vithean Chest": _infobox(
            "Vithean Chest (Round 1)", stable_key="character:arenachest 1", imagefile="Vithean Chest.png"
        )
        + _infobox("Vithean Chest (Round 2)", stable_key="character:arenachest 2", imagefile="Vithean Chest.png"),
        "Honsus": _infobox("Honsus", stable_key="character:honsus", imagefile="Honsus.png")
        + _infobox("Vithean Chest (Round 7)", imagefile="Vithean Chest.png", extra="|imagekind=chest\n"),
        "Tojokom": _infobox("Vithean Chest (Round 2)", imagefile="Vithean Chest.png", extra="|imagekind=chest\n"),
    }
    characters = [
        _character("character:arenachest 2", "Vithean Chest", resources_path="npcs/plane of vitheo/ArenaChest 2"),
        _character("character:arenachest 1", "Vithean Chest", resources_path="npcs/plane of vitheo/ArenaChest 1"),
        _character("character:arenachest 9", "Vithean Chest", scene="PlaneOfVitheo"),
        _character("character:honsus", "Honsus", resources_path="npcs/Honsus"),
    ]

    manifest = build_manifest(page_image_uses(pages), characters, _uploaded("Honsus.png"), "24405256")

    assert [(entry.file, entry.kind, entry.stable_key, entry.pages) for entry in manifest.entries] == [
        ("Vithean Chest.png", "chest", "character:arenachest 1", ("Honsus", "Tojokom", "Vithean Chest"))
    ]
    assert manifest.entries[0].source.resources_path == "npcs/plane of vitheo/ArenaChest 1"


def test_a_placed_character_or_a_scene_prefab_is_the_source_without_a_resources_prefab() -> None:
    pages = {
        "Faith": _infobox("Faith", stable_key="character:faith", imagefile="Faith.png"),
        "Training Dummy": _infobox(
            "Training Dummy (1000 AC)",
            stable_key="character:dummy:reliquary:1",
            imagefile="Training Dummy (1000 AC).png",
        ),
    }
    characters = [
        # Faith's prefab is outside Resources, and a FaithEvent of the scene references it.
        _character(
            "character:faith",
            "Faith",
            spawn_points=(("PlaneOfSoluna", 361.9, 327.1, 1346.7), ("PlaneOfSoluna", 275.6, 327.1, 1346.7)),
        ),
        _character("character:dummy:reliquary:1", "Training Dummy (1000 AC)", scene="Reliquary", is_enabled=False),
    ]

    manifest = build_manifest(page_image_uses(pages), characters, _uploaded(), "24405256")

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


def test_a_file_without_a_game_object_is_listed_apart() -> None:
    pages = {"Old Friend": _infobox("Old Friend", image="[[File:Old Friend.png|thumb]]")}

    manifest = build_manifest(page_image_uses(pages), [], _uploaded(), "24405256")

    assert manifest.entries == ()
    assert [(file.file, file.pages) for file in manifest.unsourced] == [("Old Friend.png", ("Old Friend",))]


def test_colon_and_magic_word_titles_resolve_to_the_shown_file() -> None:
    pages = {
        "Summoned: Treant": _infobox(
            "Summoned: Treant",
            stable_key="character:summoned treant",
            imagefile="Summoned: Treant.png",
            extra="|imagekind=summon\n",
        ),
        "Prielian Cascade": "{{Zone\n|title=Prielian Cascade\n|image=[[File:{{PAGENAME}}.png|thumb]]\n}}\n",
        "Port Azure": "{{Zone\n|title=Port Azure\n|image=[[File:{{PAGENAMEE}}.png|thumb]]\n}}\n",
    }
    characters = [
        _character("character:summoned treant", "Summoned: Treant", resources_path="npcs/Treant", is_summon=True)
    ]

    manifest = build_manifest(page_image_uses(pages), characters, _uploaded("Port Azure.png"), "24405256")

    assert [(entry.file, entry.kind) for entry in manifest.entries] == [("Summoned: Treant.png", "summon")]
    assert [(file.file, file.pages) for file in manifest.editor_files] == [
        ("Prielian Cascade.png", ("Prielian Cascade",))
    ]


def test_a_summon_spell_icon_is_not_a_creature_image() -> None:
    pages = {"Summon Treant": "{{Ability\n|title=Summon Treant\n|image=[[File:Summon Treant.png|thumb]]\n}}\n"}
    characters = [_character("character:summoned treant", "Summon Treant", resources_path="npcs/Treant")]

    manifest = build_manifest(page_image_uses(pages), characters, _uploaded(), "24405256")

    assert (manifest.entries, manifest.unsourced) == ((), ())


def test_an_unused_page_shows_the_image_of_its_character_in_the_clean_database() -> None:
    # The six unused rune receptacles show the shared receptacle model. Every
    # receptacle is off at load, and the one of the generated page is captured.
    characters = [
        _character(
            "character:receptacle-sand",
            "Portal Receptacle",
            scene="Reliquary",
            is_enabled=False,
            is_wiki_generated=False,
        ),
        _character("character:receptacle:reliquary:2", "Portal Receptacle", scene="Reliquary", is_enabled=False),
    ]
    pages = {
        "Portal Receptacle": _infobox(
            "Portal Receptacle", stable_key="character:receptacle:reliquary:2", imagefile="Portal Receptacle.png"
        )
    }
    uses = [
        *page_image_uses(pages),
        *unused_page_image_uses({"Braxonian Receptacle": "character:receptacle-sand"}, characters),
    ]

    manifest = build_manifest(uses, characters, _uploaded(), "24405256")

    assert [(entry.file, entry.pages) for entry in manifest.entries] == [
        ("Portal Receptacle.png", ("Braxonian Receptacle", "Portal Receptacle"))
    ]
    assert manifest.entries[0].stable_key == "character:receptacle:reliquary:2"


def test_an_unused_page_needs_its_character() -> None:
    with pytest.raises(ValueError, match="not in the clean database"):
        unused_page_image_uses({"Holy Corpse": "character:holy corpse"}, [])


def test_a_present_file_is_not_captured() -> None:
    pages = {"Faith": _infobox("Faith", stable_key="character:faith", imagefile="Faith.png")}
    characters = [_character("character:faith", "Faith", resources_path="npcs/Faith")]

    manifest = build_manifest(page_image_uses(pages), characters, _uploaded("Faith.png"), "24405256")

    assert (manifest.entries, manifest.unsourced, manifest.editor_files) == ((), (), ())
