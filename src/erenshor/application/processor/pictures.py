"""Catalogue every game picture that the wiki or the map shows.

Each picture enters once, identified by the hash of its pixels:

- the icon of each item, spell, and skill, from the texture that its sprite
  draws, which the export records
- each rendered portrait that a capture review approved

The build copies each picture's file to the catalog directory under its hash,
links every entity to its picture, and lists the wiki file title of each
entity's picture: ``<subject> icon.png`` for an item, spell, skill, or stance,
and ``<subject> render.png`` for a character. A stance shows the icon of the
skill that switches to it.
Textures with equal pixels share one picture. The build only adds catalog
files; ``prune_catalog`` removes the files that a published database no longer
references.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.pictures import identify
from erenshor.domain.value_objects.capture_approval import APPROVAL_FILE, Approval
from erenshor.domain.value_objects.wiki_filename import PictureRole, picture_file_title, picture_subject

if TYPE_CHECKING:
    from .writer import Writer

__all__ = [
    "CATALOG_DIRECTORY",
    "process_pictures",
    "prune_catalog",
]

CATALOG_DIRECTORY = "catalog"
CAPTURES_DIRECTORY = "model-captures"

# The clean table, raw table, and raw texture column of each kind of icon.
_ICON_TABLES = (
    ("items", "Items", "ItemIconTexture"),
    ("spells", "Spells", "SpellIconTexture"),
    ("skills", "Skills", "SkillIconTexture"),
)


@dataclass
class _Picture:
    kind: str
    width: int
    height: int
    sources: dict[str, Path] = field(default_factory=dict)
    capture_preset: str | None = None
    approved_build: str | None = None


class _Catalog:
    """The pictures of one build, keyed by pixel hash."""

    def __init__(self) -> None:
        self.pictures: dict[str, _Picture] = {}
        self._by_source: dict[str, str] = {}

    def add(
        self,
        source: str,
        path: Path,
        kind: str,
        *,
        capture_preset: str | None = None,
        approved_build: str | None = None,
    ) -> str:
        """Add the picture of a source file and return its pixel hash."""
        known = self._by_source.get(source)
        if known is not None:
            return known
        identity = identify(path.read_bytes())
        picture = self.pictures.get(identity.pixel_hash)
        if picture is None:
            picture = _Picture(kind, identity.width, identity.height, {}, capture_preset, approved_build)
            self.pictures[identity.pixel_hash] = picture
        elif picture.kind != kind:
            raise ValueError(f"{source} has the pixels of a {picture.kind} but is a {kind}")
        picture.sources[source] = path
        self._by_source[source] = identity.pixel_hash
        return identity.pixel_hash


def process_pictures(raw: sqlite3.Connection, writer: Writer, export_dir: Path, images_dir: Path) -> None:
    """Catalogue the pictures of the clean database's entities and write their files.

    Args:
        raw: The raw export database, for the texture of each icon.
        writer: The clean database, whose entity tables are already written.
        export_dir: The ripped Unity project, which holds the textures.
        images_dir: The variant's image directory, which holds the approved
            captures and receives the catalog.

    Raises:
        FileNotFoundError: A texture or an approved capture is missing.
        ValueError: An approved capture changed after its approval, or one
            wiki file title would name two pictures.
    """
    catalog = _Catalog()
    conn = writer.conn

    icon_links: dict[str, list[tuple[str, str]]] = {}
    for table, raw_table, column in _ICON_TABLES:
        keys = {str(row[0]) for row in conn.execute(f"SELECT stable_key FROM {table}")}
        links = icon_links.setdefault(table, [])
        for stable_key, texture in raw.execute(
            f"SELECT StableKey, {column} FROM {raw_table} WHERE {column} IS NOT NULL"
        ):
            if stable_key not in keys:
                continue
            path = export_dir / texture
            if not path.is_file():
                raise FileNotFoundError(f"{stable_key}: icon texture {texture} is missing from the export")
            links.append((catalog.add(texture, path, "icon"), stable_key))

    portraits, paged_portraits = _add_portraits(catalog, images_dir / CAPTURES_DIRECTORY)

    # The entity tables reference the pictures, so the pictures go in first.
    writer.insert_images(_write_files(catalog, images_dir / CATALOG_DIRECTORY))
    writer.insert_image_sources(
        [
            {"image_hash": image_hash, "source": source}
            for image_hash, picture in sorted(catalog.pictures.items())
            for source in sorted(picture.sources)
        ]
    )
    for table, links in icon_links.items():
        conn.executemany(f"UPDATE {table} SET image_hash = ? WHERE stable_key = ?", links)
    _link_stances(conn)
    _link_characters(conn, portraits)

    titles = _titles(conn, paged_portraits)
    writer.insert_image_titles(
        [
            {"title": title, "image_hash": image_hash, "stable_key": stable_key}
            for title, (image_hash, stable_key) in sorted(titles.items())
        ]
    )
    kinds = {kind: sum(picture.kind == kind for picture in catalog.pictures.values()) for kind in ("icon", "portrait")}
    logger.info(f"Pictures: {kinds['icon']} icons, {kinds['portrait']} portraits, {len(titles)} wiki file titles")


def _link_stances(conn: sqlite3.Connection) -> None:
    """Give each stance the icon of the skills that switch to it, which must agree."""
    rows = conn.execute(
        """
        SELECT st.stable_key, COUNT(DISTINCT sk.image_hash), MIN(sk.image_hash)
        FROM stances st JOIN skills sk ON sk.stance_to_use_stable_key = st.stable_key
        WHERE sk.image_hash IS NOT NULL
        GROUP BY st.stable_key
        """
    ).fetchall()
    for stable_key, count, _ in rows:
        if count > 1:
            raise ValueError(f"{stable_key}: the skills that switch to this stance draw different icons")
    conn.executemany(
        "UPDATE stances SET image_hash = ? WHERE stable_key = ?", [(image_hash, key) for key, _, image_hash in rows]
    )


def _add_portraits(catalog: _Catalog, captures_dir: Path) -> tuple[dict[str, str], frozenset[str]]:
    """Add every approved capture.

    Returns the pixel hash of each approved subject, and the subjects whose
    approval names a page that shows them.
    """
    approval_path = captures_dir / APPROVAL_FILE
    if not approval_path.exists():
        return {}, frozenset()
    approval = Approval.from_json(json.loads(approval_path.read_text(encoding="utf-8")))
    portraits: dict[str, str] = {}
    for image in approval.images:
        path = captures_dir / "approved" / image.png
        if hashlib.sha256(path.read_bytes()).hexdigest() != image.sha256:
            raise ValueError(f"The approved capture of {image.subject} changed after its approval: {path}")
        portraits[image.subject] = catalog.add(
            f"{CAPTURES_DIRECTORY}/approved/{image.png}",
            path,
            "portrait",
            capture_preset=image.preset,
            approved_build=image.game_build,
        )
    return portraits, frozenset(image.subject for image in approval.images if image.pages)


def _link_characters(conn: sqlite3.Connection, portraits: dict[str, str]) -> None:
    """Give each character the approved portrait of its subject.

    An approval whose subject no character has any more stays out of the
    wiki's titles and is reported, so that a review can drop it.
    """
    links: list[tuple[str, str]] = []
    named: set[str] = set()
    for stable_key, image_name, display_name in conn.execute(
        "SELECT stable_key, image_name, display_name FROM characters"
    ):
        subject = picture_subject(image_name, display_name)
        if subject in portraits:
            links.append((portraits[subject], stable_key))
            named.add(subject)
    conn.executemany("UPDATE characters SET image_hash = ? WHERE stable_key = ?", links)
    stale = sorted(set(portraits) - named)
    if stale:
        logger.warning(f"Approved captures that no character has: {', '.join(stale)}")


def _titles(conn: sqlite3.Connection, paged_portraits: frozenset[str]) -> dict[str, tuple[str, str]]:
    """Map each wiki file title that a page names to its picture and the first entity that names it.

    An icon's title counts when its entity has a generated page. The catalog
    holds a portrait of every character, also of those that no page shows, so
    a character's title counts when the character has a generated page or the
    approval of its portrait names a page, such as one with the unused notice.
    """
    queries: tuple[tuple[str, int, PictureRole], ...] = (
        ("SELECT stable_key, image_hash, image_name, display_name, item_name, wiki_page_name FROM items", 3, "icon"),
        ("SELECT stable_key, image_hash, image_name, wiki_page_name FROM spells", 1, "icon"),
        ("SELECT stable_key, image_hash, image_name, wiki_page_name FROM skills", 1, "icon"),
        ("SELECT stable_key, image_hash, image_name, wiki_page_name FROM stances", 1, "icon"),
        ("SELECT stable_key, image_hash, image_name, display_name, wiki_page_name FROM characters", 2, "render"),
    )
    titles: dict[str, tuple[str, str]] = {}
    for sql, name_count, role in queries:
        for row in conn.execute(f"{sql} WHERE image_hash IS NOT NULL"):
            stable_key, image_hash = str(row[0]), str(row[1])
            names = row[2 : 2 + name_count]
            has_page = row[2 + name_count] is not None or (
                role == "render" and picture_subject(*names) in paged_portraits
            )
            title = picture_file_title(role, *names)
            if not title or not has_page:
                continue
            claimed = titles.setdefault(title, (image_hash, stable_key))
            if claimed[0] != image_hash:
                raise ValueError(f"{title} names two pictures: the one of {claimed[1]} and the one of {stable_key}")
    return titles


def _write_files(catalog: _Catalog, catalog_dir: Path) -> list[dict[str, object]]:
    """Write each picture's file under its hash and return the rows of the ``images`` table.

    A picture's file holds the bytes of its first source in path order. A file
    is written only when it is missing or holds other bytes, through a
    temporary file, so a stopped build leaves no partial file.
    """
    catalog_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for image_hash, picture in sorted(catalog.pictures.items()):
        data = picture.sources[min(picture.sources)].read_bytes()
        target = catalog_dir / f"{image_hash}.png"
        if not target.is_file() or target.read_bytes() != data:
            staged = target.with_suffix(".png.tmp")
            staged.write_bytes(data)
            staged.replace(target)
        rows.append(
            {
                "image_hash": image_hash,
                "kind": picture.kind,
                "width": picture.width,
                "height": picture.height,
                "file_sha1": hashlib.sha1(data, usedforsecurity=False).hexdigest(),
                "file_bytes": len(data),
                "capture_preset": picture.capture_preset,
                "approved_build": picture.approved_build,
            }
        )
    return rows


def prune_catalog(catalog_dir: Path, clean_db_path: Path) -> int:
    """Remove the catalog files that the clean database does not reference and return their count."""
    if not catalog_dir.is_dir():
        return 0
    with sqlite3.connect(f"file:{clean_db_path}?mode=ro", uri=True) as conn:
        referenced = {str(row[0]) for row in conn.execute("SELECT image_hash FROM images")}
    removed = 0
    for path in catalog_dir.iterdir():
        if path.is_file() and path.name.removesuffix(".png") not in referenced:
            path.unlink()
            removed += 1
    return removed
