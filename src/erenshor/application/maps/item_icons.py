"""The item icons of the map, built from the picture catalog of the clean build.

The map shows each map-visible item's icon at two sizes: 20 px in search
results and 48 px in the item popup. Each icon file is named by the pixel hash
of its picture, so a changed picture gets a new URL, an unchanged one keeps its
file, and items that share a picture share its files.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from erenshor.application.processor.pictures import CATALOG_DIRECTORY

__all__ = ["ICON_SIZES", "ItemIconsResult", "build_item_icons"]

ICON_SIZES = (20, 48)
_WEBP_QUALITY = 90


@dataclass(frozen=True, slots=True)
class ItemIconsResult:
    written: int
    kept: int
    removed: int


def build_item_icons(database_path: Path, images_dir: Path, output_dir: Path) -> ItemIconsResult:
    """Write the icon files of every map-visible item's picture and remove the others.

    Args:
        database_path: The clean database, whose items name their pictures.
        images_dir: The variant's images directory, which holds the catalog.
        output_dir: The map's directory of item icons, ``static/items``.

    Raises:
        FileNotFoundError: If the catalog lacks the file of a picture that an item names.
    """
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as conn:
        hashes = sorted(
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT image_hash FROM items WHERE is_map_visible = 1 AND image_hash IS NOT NULL"
            )
        )
    catalog_dir = images_dir / CATALOG_DIRECTORY
    output_dir.mkdir(parents=True, exist_ok=True)

    wanted: set[str] = set()
    written = kept = 0
    for image_hash in hashes:
        targets = {size: output_dir / _icon_name(image_hash, size) for size in ICON_SIZES}
        wanted.update(path.name for path in targets.values())
        if all(path.is_file() for path in targets.values()):
            kept += 1
            continue
        source = catalog_dir / f"{image_hash}.png"
        if not source.is_file():
            raise FileNotFoundError(f"The picture {image_hash} of a map-visible item has no catalog file {source}")
        with Image.open(source) as opened:
            picture = opened.convert("RGBA")
        for size, path in targets.items():
            _write_webp(_fit(picture, size), path)
        written += 1

    removed = 0
    for path in output_dir.iterdir():
        if path.is_file() and path.name not in wanted:
            path.unlink()
            removed += 1
    return ItemIconsResult(written=written, kept=kept, removed=removed)


def _icon_name(image_hash: str, size: int) -> str:
    return f"{image_hash}.w{size}.webp"


def _fit(picture: Image.Image, size: int) -> Image.Image:
    """Scale a picture to fit within a square of ``size`` pixels at its own proportions, centred."""
    scale = size / max(picture.width, picture.height)
    width = max(1, round(picture.width * scale))
    height = max(1, round(picture.height * scale))
    scaled = picture.resize((width, height), Image.Resampling.LANCZOS)
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(scaled, ((size - width) // 2, (size - height) // 2))
    return square


def _write_webp(picture: Image.Image, path: Path) -> None:
    """Write a WebP file through a temporary file, so a stopped build leaves no partial icon."""
    temporary = path.with_name(f".{path.name}.tmp")
    picture.save(temporary, "WEBP", quality=_WEBP_QUALITY, method=6)
    temporary.replace(path)
