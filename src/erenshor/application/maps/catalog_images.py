"""Catalog-backed WebP sets for the map's item icons and character portraits.

Items keep their 20 px search icons and 48 px popup icons. Character popups and
spawn cards show a centred 96 px portrait above their text, leaving the narrow
popup's full width for names and details; 192 px supplies the same view at 2x.
Pixel-hash filenames let unchanged and shared pictures reuse their files.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from erenshor.application.processor.pictures import CATALOG_DIRECTORY

__all__ = [
    "ICON_SIZES",
    "PORTRAIT_SIZES",
    "CatalogImagesResult",
    "build_character_portraits",
    "build_item_icons",
    "selected_source_paths",
]

ICON_SIZES = (20, 48)
PORTRAIT_SIZES = (96, 192)
_WEBP_QUALITY = 90


@dataclass(frozen=True, slots=True)
class CatalogImagesResult:
    written: int
    kept: int
    removed: int


def _item_hashes(database_path: Path) -> list[str]:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as conn:
        return sorted(
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT image_hash FROM items WHERE is_map_visible = 1 AND image_hash IS NOT NULL"
            )
        )


def _character_hashes(database_path: Path) -> list[str]:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as conn:
        return sorted(
            str(row[0])
            for row in conn.execute(
                """SELECT DISTINCT c.image_hash
                   FROM characters c
                   JOIN character_deduplications d ON d.member_stable_key = c.stable_key
                   WHERE d.is_map_visible = 1 AND c.image_hash IS NOT NULL"""
            )
        )


def selected_source_paths(database_path: Path, images_dir: Path) -> list[Path]:
    """Return only catalog pixels selected by the map's native visibility queries."""
    hashes = set(_item_hashes(database_path)) | set(_character_hashes(database_path))
    return [images_dir / CATALOG_DIRECTORY / f"{image_hash}.png" for image_hash in sorted(hashes)]


def build_item_icons(database_path: Path, images_dir: Path, output_dir: Path) -> CatalogImagesResult:
    """Build every map-visible item's icons in ``static/items``."""
    return _build_images(_item_hashes(database_path), images_dir, output_dir, ICON_SIZES, "item")


def build_character_portraits(database_path: Path, images_dir: Path, output_dir: Path) -> CatalogImagesResult:
    """Build approved portraits of map-visible characters in ``static/characters``.

    Visibility comes from the same deduplication members that the map queries.
    Missing portraits are omitted. A referenced portrait missing its catalog file
    fails the build rather than falling back to a wiki picture.
    """
    return _build_images(_character_hashes(database_path), images_dir, output_dir, PORTRAIT_SIZES, "character")


def _build_images(
    hashes: list[str], images_dir: Path, output_dir: Path, sizes: tuple[int, ...], subject: str
) -> CatalogImagesResult:
    catalog_dir = images_dir / CATALOG_DIRECTORY
    output_dir.mkdir(parents=True, exist_ok=True)

    wanted: set[str] = set()
    written = kept = 0
    for image_hash in hashes:
        targets = {size: output_dir / f"{image_hash}.w{size}.webp" for size in sizes}
        wanted.update(path.name for path in targets.values())
        if all(path.is_file() for path in targets.values()):
            kept += 1
            continue
        source = catalog_dir / f"{image_hash}.png"
        if not source.is_file():
            raise FileNotFoundError(f"The picture {image_hash} of a map-visible {subject} has no catalog file {source}")
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
    return CatalogImagesResult(written=written, kept=kept, removed=removed)


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
    """Write through a temporary file, so a stopped build leaves no partial image."""
    temporary = path.with_name(f".{path.name}.tmp")
    picture.save(temporary, "WEBP", quality=_WEBP_QUALITY, method=6)
    temporary.replace(path)
