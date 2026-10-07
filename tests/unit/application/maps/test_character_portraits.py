"""Map portraits use approved catalog pictures, not wiki images."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image

from erenshor.application.maps.catalog_images import build_character_portraits


def _database(path: Path, characters: list[tuple[str, str | None, int]]) -> Path:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE characters (stable_key TEXT PRIMARY KEY, image_hash TEXT)")
        conn.execute("CREATE TABLE character_deduplications (member_stable_key TEXT, is_map_visible INTEGER)")
        conn.executemany(
            "INSERT INTO characters VALUES (?, ?)", [(key, image_hash) for key, image_hash, _ in characters]
        )
        conn.executemany(
            "INSERT INTO character_deduplications VALUES (?, ?)", [(key, visible) for key, _, visible in characters]
        )
        conn.commit()
    return path


def _picture(images: Path, image_hash: str) -> None:
    catalog = images / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 512), (40, 200, 40, 255)).save(catalog / f"{image_hash}.png")


def test_shared_portraits_keep_transparency_and_unchanged_files(tmp_path: Path) -> None:
    images, portraits = tmp_path / "images", tmp_path / "characters"
    _picture(images, "shared")
    database = _database(tmp_path / "clean.sqlite", [("character:a", "shared", 1), ("character:b", "shared", 1)])

    result = build_character_portraits(database, images, portraits)

    assert (result.written, result.kept, result.removed) == (1, 0, 0)
    assert sorted(path.name for path in portraits.iterdir()) == ["shared.w192.webp", "shared.w96.webp"]
    for size in (96, 192):
        with Image.open(portraits / f"shared.w{size}.webp") as portrait:
            assert portrait.size == (size, size)
            assert portrait.getchannel("A").getbbox() == (size // 4, 0, 3 * size // 4, size)
    (portraits / "shared.w96.webp").write_bytes(b"kept")

    result = build_character_portraits(database, images, portraits)

    assert (result.written, result.kept, result.removed) == (0, 1, 0)
    assert (portraits / "shared.w96.webp").read_bytes() == b"kept"


def test_hidden_and_missing_portraits_get_no_files_and_stale_files_go(tmp_path: Path) -> None:
    images, portraits = tmp_path / "images", tmp_path / "characters"
    _picture(images, "old")
    before = _database(tmp_path / "before.sqlite", [("character:a", "old", 1)])
    build_character_portraits(before, images, portraits)
    after = _database(
        tmp_path / "after.sqlite", [("character:aetherfiend", None, 1), ("character:hidden", "hidden", 0)]
    )

    result = build_character_portraits(after, images, portraits)

    assert (result.written, result.kept, result.removed) == (0, 0, 2)
    assert list(portraits.iterdir()) == []


def test_referenced_portrait_missing_from_catalog_fails_and_names_it(tmp_path: Path) -> None:
    database = _database(tmp_path / "clean.sqlite", [("character:a", "missing", 1)])

    with pytest.raises(FileNotFoundError, match="picture missing of a map-visible character"):
        build_character_portraits(database, tmp_path / "images", tmp_path / "characters")
