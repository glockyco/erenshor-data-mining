"""The clean build catalogues each game picture once, by its pixels."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from erenshor.application.pictures import identify
from erenshor.application.processor.pictures import process_pictures, prune_catalog
from erenshor.application.processor.writer import Writer


def _png(color: tuple[int, int, int, int], size: tuple[int, int] = (8, 8), compress_level: int = 6) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, "PNG", compress_level=compress_level)
    return buffer.getvalue()


class _Build:
    """A raw export, its textures, and a clean database with entity rows."""

    def __init__(self, tmp_path: Path) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.export = tmp_path / "ExportedProject"
        self.images = tmp_path / "images"
        self.raw = sqlite3.connect(tmp_path / "raw.sqlite")
        self.raw.execute("CREATE TABLE Items (StableKey TEXT, ItemIconTexture TEXT)")
        self.raw.execute("CREATE TABLE Spells (StableKey TEXT, SpellIconTexture TEXT)")
        self.raw.execute("CREATE TABLE Skills (StableKey TEXT, SkillIconTexture TEXT)")
        self.writer = Writer(tmp_path / "clean.sqlite")
        self.writer.create_schema()

    def texture(self, path: str, data: bytes) -> str:
        target = self.export / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return path

    def item(self, key: str, name: str, texture: str | None, page: str | None = None) -> None:
        self.raw.execute("INSERT INTO Items VALUES (?, ?)", (key, texture))
        self.writer.insert_items(
            [{"stable_key": key, "display_name": name, "image_name": name, "wiki_page_name": page or name}]
        )

    def skill(self, key: str, name: str, texture: str, stance: str | None = None) -> None:
        self.raw.execute("INSERT INTO Skills VALUES (?, ?)", (key, texture))
        self.writer.insert_skills(
            [
                {
                    "stable_key": key,
                    "display_name": name,
                    "image_name": name,
                    "wiki_page_name": name,
                    "stance_to_use_stable_key": stance,
                }
            ]
        )

    def run(self) -> None:
        process_pictures(self.raw, self.writer, self.export, self.images)

    def rows(self, sql: str) -> list[tuple[object, ...]]:
        return [tuple(row) for row in self.writer.conn.execute(sql)]


def test_an_icon_is_its_texture_unchanged_and_shared_textures_give_one_picture(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    scroll = build.texture("Assets/Texture2D/8_5.png", _png((40, 200, 40, 128), size=(10, 6)))
    for index in range(3):
        build.item(f"item:scroll {index}", f"Spell Scroll {index}", scroll)

    build.run()

    (image_hash,) = {row[0] for row in build.rows("SELECT image_hash FROM items")}
    assert (build.images / "catalog" / f"{image_hash}.png").read_bytes() == (build.export / scroll).read_bytes()
    assert build.rows(f"SELECT kind, width, height FROM images WHERE image_hash = '{image_hash}'") == [("icon", 10, 6)]
    assert build.rows("SELECT title FROM image_titles WHERE title LIKE 'Spell Scroll%' ORDER BY title") == [
        ("Spell Scroll 0 icon.png",),
        ("Spell Scroll 1 icon.png",),
        ("Spell Scroll 2 icon.png",),
    ]


def test_textures_with_equal_pixels_share_one_picture_that_names_both_sources(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.item(
        "item:bracers a", "Bracers A", build.texture("Assets/Texture2D/11_Leather_bracers.png", _png((1, 2, 3, 255)))
    )
    build.item(
        "item:bracers b",
        "Bracers B",
        build.texture("Assets/Texture2D/Leather11_bracers.png", _png((1, 2, 3, 255), compress_level=9)),
    )

    build.run()

    assert len({row[0] for row in build.rows("SELECT image_hash FROM items")}) == 1
    sources = [row[0] for row in build.rows("SELECT source FROM image_sources WHERE source LIKE '%bracers%'")]
    assert sorted(sources) == ["Assets/Texture2D/11_Leather_bracers.png", "Assets/Texture2D/Leather11_bracers.png"]


def test_an_encoder_change_keeps_the_identity_of_a_picture() -> None:
    assert identify(_png((9, 9, 9, 9), compress_level=1)) == identify(_png((9, 9, 9, 9), compress_level=9))


def test_a_missing_texture_fails_and_names_the_entity_and_the_texture(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.item("item:thorned branch", "Thorned Branch", "Assets/Texture2D/4_8.png")

    with pytest.raises(FileNotFoundError, match=r"item:thorned branch: icon texture Assets/Texture2D/4_8\.png"):
        build.run()


def test_two_builds_of_one_export_write_identical_files_and_rows(tmp_path: Path) -> None:
    results = []
    for run in ("a", "b"):
        build = _Build(tmp_path / run)
        build.item("item:branch", "Thorned Branch", build.texture("Assets/Texture2D/4_8.png", _png((200, 60, 20, 255))))
        build.run()
        files = {path.name: path.read_bytes() for path in (build.images / "catalog").iterdir()}
        tables = [build.rows(f"SELECT * FROM {table} ORDER BY 1, 2") for table in ("images", "image_sources")]
        results.append((files, tables))

    assert results[0] == results[1]


def test_a_stance_shows_the_icon_of_its_skill_under_its_own_title(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.skill(
        "skill:stance - aggressive",
        "Stance: Aggressive",
        build.texture("Assets/Texture2D/24_1.png", _png((250, 0, 0, 255))),
        stance="stance:aggressive",
    )
    build.writer.insert_stances(
        [
            {
                "stable_key": "stance:aggressive",
                "display_name": "Aggressive",
                "image_name": "Stance: Aggressive",
                "wiki_page_name": "Aggressive",
            }
        ]
    )

    build.run()

    skill_hash = build.rows("SELECT image_hash FROM skills")[0][0]
    assert build.rows("SELECT image_hash FROM stances") == [(skill_hash,)]
    assert ("Stance Aggressive icon.png", skill_hash) in build.rows("SELECT title, image_hash FROM image_titles")


def test_one_title_for_two_pictures_fails_and_names_both_entities(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.item(
        "item:artifact (fern)", "A Strange Artifact", build.texture("Assets/Texture2D/a.png", _png((1, 0, 0, 255)))
    )
    build.item(
        "item:artifact (vith)", "A Strange Artifact", build.texture("Assets/Texture2D/b.png", _png((0, 1, 0, 255)))
    )

    with pytest.raises(ValueError, match=r"A Strange Artifact icon\.png names two pictures"):
        build.run()


def _approve(
    build: _Build, subject: str, data: bytes, game_build: str = "24405256", pages: tuple[str, ...] = ("Faith",)
) -> None:
    captures = build.images / "model-captures"
    (captures / "approved").mkdir(parents=True, exist_ok=True)
    png = f"{subject}.png"
    (captures / "approved" / png).write_bytes(data)
    image = {
        "subject": subject,
        "png": png,
        "sha256": hashlib.sha256(data).hexdigest(),
        "stable_key": "character:faith",
        "kind": "character",
        "pages": list(pages),
        "game_build": game_build,
        "preset": "portrait-3",
    }
    (captures / "approved.json").write_text(json.dumps({"images": [image]}))


def _character(build: _Build, key: str, name: str, page: str | None) -> None:
    build.writer.conn.execute(
        "INSERT INTO characters (stable_key, display_name, image_name, wiki_page_name, encounter_tier, "
        "level_scales_with_player) VALUES (?, ?, ?, ?, 'npc', 0)",
        (key, name, name, page),
    )


def test_an_approved_portrait_gives_its_character_a_picture_and_a_title(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    _character(build, "character:faith", "Faith", "Faith")
    _character(build, "character:queen evadne", "Queen Evadne", None)
    _approve(build, "Faith", _png((255, 200, 255, 90), size=(12, 20)))

    build.run()

    faith = build.rows("SELECT image_hash FROM characters WHERE stable_key = 'character:faith'")[0][0]
    assert build.rows(f"SELECT kind, capture_preset, approved_build FROM images WHERE image_hash = '{faith}'") == [
        ("portrait", "portrait-3", "24405256")
    ]
    assert ("Faith render.png", faith) in build.rows("SELECT title, image_hash FROM image_titles")
    assert build.rows("SELECT image_hash FROM characters WHERE stable_key = 'character:queen evadne'") == [(None,)]


def test_an_item_and_a_character_of_one_name_get_a_title_each(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.item("item:faith", "Faith", build.texture("Assets/Texture2D/f.png", _png((1, 2, 3, 255))))
    _character(build, "character:faith", "Faith", "Faith")
    _approve(build, "Faith", _png((255, 200, 255, 90)))

    build.run()

    titles = dict(build.rows("SELECT title, stable_key FROM image_titles WHERE title LIKE 'Faith%'"))
    assert titles == {"Faith icon.png": "item:faith", "Faith render.png": "character:faith"}


def test_a_portrait_of_a_page_without_generation_still_gets_its_title(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    _character(build, "character:queen evadne", "Queen Evadne", None)
    _approve(build, "Queen Evadne", _png((10, 10, 10, 255)), pages=("Queen Evadne",))

    build.run()

    assert [row[0] for row in build.rows("SELECT title FROM image_titles WHERE title LIKE 'Queen%'")] == [
        "Queen Evadne render.png"
    ]


def test_a_portrait_that_no_page_shows_is_catalogued_without_a_title(tmp_path: Path) -> None:
    # The map shows every character, so the catalog keeps the portrait, but no page names its file.
    build = _Build(tmp_path)
    _character(build, "character:watchman", "Watchman", None)
    _approve(build, "Watchman", _png((90, 90, 120, 255)), pages=())

    build.run()

    watchman = build.rows("SELECT image_hash FROM characters WHERE stable_key = 'character:watchman'")[0][0]
    assert build.rows(f"SELECT kind FROM images WHERE image_hash = '{watchman}'") == [("portrait",)]
    assert build.rows("SELECT title FROM image_titles WHERE title LIKE 'Watchman%'") == []


def test_an_approved_copy_that_changed_fails_the_build_and_names_the_subject(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    _character(build, "character:faith", "Faith", "Faith")
    _approve(build, "Faith", _png((255, 255, 255, 255)))
    (build.images / "model-captures" / "approved" / "Faith.png").write_bytes(_png((0, 0, 0, 255)))

    with pytest.raises(ValueError, match=r"approved capture of Faith changed after its approval"):
        build.run()


def test_a_repeat_capture_with_the_same_pixels_keeps_the_picture(tmp_path: Path) -> None:
    hashes = []
    for game_build, level in (("24405256", 1), ("25000000", 9)):
        build = _Build(tmp_path / game_build)
        _character(build, "character:faith", "Faith", "Faith")
        _approve(build, "Faith", _png((200, 100, 50, 255), compress_level=level), game_build)
        build.run()
        hashes.append(build.rows("SELECT image_hash FROM characters")[0][0])

    assert hashes[0] == hashes[1]


def test_pruning_removes_only_the_files_that_the_database_does_not_reference(tmp_path: Path) -> None:
    build = _Build(tmp_path)
    build.item("item:branch", "Thorned Branch", build.texture("Assets/Texture2D/4_8.png", _png((200, 60, 20, 255))))
    build.run()
    build.writer.conn.commit()
    catalog = build.images / "catalog"
    (catalog / f"{'0' * 64}.png").write_bytes(b"left over")
    kept = sorted(path.name for path in catalog.iterdir() if not path.name.startswith("0"))

    assert prune_catalog(catalog, tmp_path / "clean.sqlite") == 1
    assert sorted(path.name for path in catalog.iterdir()) == kept
