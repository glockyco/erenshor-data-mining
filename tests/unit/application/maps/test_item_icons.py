"""The map's item icons follow the pictures of the clean database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image

from erenshor.application.maps.item_icons import build_item_icons


def _database(path: Path, items: list[tuple[str, str | None, int]]) -> Path:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE items (stable_key TEXT PRIMARY KEY, image_hash TEXT, is_map_visible INTEGER)")
        conn.executemany("INSERT INTO items VALUES (?, ?, ?)", items)
        conn.commit()
    return path


def _picture(images: Path, image_hash: str, size: tuple[int, int], color: tuple[int, int, int, int]) -> None:
    catalog = images / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(catalog / f"{image_hash}.png")


def test_an_icon_fits_the_square_at_its_own_proportions(tmp_path: Path) -> None:
    images, icons = tmp_path / "images", tmp_path / "items"
    _picture(images, "branch", (480, 240), (200, 60, 20, 255))
    database = _database(tmp_path / "clean.sqlite", [("item:thorned branch", "branch", 1)])

    build_item_icons(database, images, icons)

    with Image.open(icons / "branch.w48.webp") as icon:
        assert icon.size == (48, 48)
        alpha = icon.getchannel("A")
        # The 2:1 picture fills the width and leaves equal clear bands above and below.
        assert alpha.getbbox() == (0, 12, 48, 36)


def test_an_unchanged_picture_keeps_its_files_and_items_that_share_one_share_them(tmp_path: Path) -> None:
    images, icons = tmp_path / "images", tmp_path / "items"
    _picture(images, "scroll", (64, 64), (40, 200, 40, 255))
    items = [("item:scroll a", "scroll", 1), ("item:scroll b", "scroll", 1)]
    database = _database(tmp_path / "clean.sqlite", items)
    build_item_icons(database, images, icons)
    (icons / "scroll.w20.webp").write_bytes(b"kept")

    result = build_item_icons(database, images, icons)

    assert (result.written, result.kept, result.removed) == (0, 1, 0)
    assert (icons / "scroll.w20.webp").read_bytes() == b"kept"
    assert sorted(path.name for path in icons.iterdir()) == ["scroll.w20.webp", "scroll.w48.webp"]


def test_a_changed_picture_gets_new_files_and_the_old_ones_go(tmp_path: Path) -> None:
    images, icons = tmp_path / "images", tmp_path / "items"
    _picture(images, "old", (64, 64), (1, 1, 1, 255))
    build_item_icons(_database(tmp_path / "before.sqlite", [("item:seed", "old", 1)]), images, icons)
    _picture(images, "new", (64, 64), (2, 2, 2, 255))

    result = build_item_icons(_database(tmp_path / "after.sqlite", [("item:seed", "new", 1)]), images, icons)

    assert (result.written, result.kept, result.removed) == (1, 0, 2)
    assert sorted(path.name for path in icons.iterdir()) == ["new.w20.webp", "new.w48.webp"]


def test_items_the_map_hides_get_no_icon(tmp_path: Path) -> None:
    images, icons = tmp_path / "images", tmp_path / "items"
    _picture(images, "hidden", (64, 64), (3, 3, 3, 255))

    build_item_icons(_database(tmp_path / "clean.sqlite", [("item:hidden", "hidden", 0)]), images, icons)

    assert list(icons.iterdir()) == []


def test_a_picture_missing_from_the_catalog_fails_and_names_it(tmp_path: Path) -> None:
    database = _database(tmp_path / "clean.sqlite", [("item:branch", "branch", 1)])

    with pytest.raises(FileNotFoundError, match="picture branch"):
        build_item_icons(database, tmp_path / "images", tmp_path / "items")
