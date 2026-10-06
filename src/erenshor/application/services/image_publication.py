"""The plan that publishes the picture catalog of the clean build to the wiki.

The planner reads the wiki's files and file pages once and gives every file
title that a page names one verdict (design D4 of the change
rebuild-game-image-pipeline):

- ``create``: the picture's file is missing, so it is uploaded
- ``update``: the picture's file holds other pixels and the project uploaded
  its latest version, so a new version is uploaded
- ``unchanged``: the title shows the picture already
- ``redirect``: the title should redirect to the picture's file and does not
- ``retire``: the title holds a copy that the project uploaded, which moves
  aside so the title can redirect to the picture's file
- ``conflict``: someone else uploaded the file at the title, or the title holds
  a page that is not a redirect, so the bot leaves it alone

Each picture has one file (design D5), and every other title of the picture
redirects to it. A file is the project's when one of its accounts uploaded the
latest version (design D3). Pixels are compared without downloads where the
listing settles it: equal bytes, a different size, or the picture's hash in the
upload comment of the project's own version. Only the remaining files are
downloaded, once, into a cache keyed by their SHA-1.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from PIL import Image, ImageDraw, UnidentifiedImageError

from erenshor.application.pictures import identify
from erenshor.application.processor.pictures import CATALOG_DIRECTORY
from erenshor.application.services.model_image_manifest import load_game_build
from erenshor.domain.value_objects.wiki_filename import upload_file_title

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping, Sequence

    from erenshor.infrastructure.wiki import MediaWikiFile

__all__ = [
    "RETIRED_PREFIX",
    "Catalog",
    "LivePictureCache",
    "LiveWiki",
    "Orphan",
    "Picture",
    "PlannedTitle",
    "PublishPlan",
    "Verdict",
    "load_catalog",
    "plan_publication",
    "write_contact_sheets",
]

Verdict = Literal["create", "update", "unchanged", "redirect", "retire", "conflict"]
VERDICTS: tuple[Verdict, ...] = ("create", "update", "unchanged", "redirect", "retire", "conflict")
RETIRED_PREFIX = "File:Retired "

# The order in which the entities of a shared picture give the picture's file its title.
_ENTITY_ORDER = ("item", "spell", "skill", "stance", "character")


@dataclass(frozen=True, slots=True)
class Picture:
    """A picture of the catalog with the facts that publishing needs.

    ``source`` is the first source of the picture, a texture of the export or an
    approved capture. A portrait carries its capture preset and the game build
    of its approval.
    """

    image_hash: str
    kind: str
    width: int
    height: int
    sha1: str
    source: str
    path: Path
    capture_preset: str | None = None
    approved_build: str | None = None


@dataclass(frozen=True, slots=True)
class Catalog:
    """The pictures of a clean build and the file titles that pages name for them.

    ``titles`` maps each ``File:`` title to its picture's hash and
    ``entities`` to the stable key of the first entity that names it, or None
    for the hotbar frame.
    """

    game_build: str
    pictures: Mapping[str, Picture]
    titles: Mapping[str, str]
    entities: Mapping[str, str | None]


def load_catalog(clean_db: Path, images_dir: Path) -> Catalog:
    """Read the pictures and titles of a clean database and locate the catalog files."""
    catalog_dir = images_dir / CATALOG_DIRECTORY
    with sqlite3.connect(f"file:{clean_db}?mode=ro", uri=True) as conn:
        game_build = load_game_build(conn)
        sources: dict[str, str] = {}
        for image_hash, source in conn.execute("SELECT image_hash, source FROM image_sources ORDER BY source"):
            sources.setdefault(str(image_hash), str(source))
        pictures = {
            str(image_hash): Picture(
                image_hash=str(image_hash),
                kind=str(kind),
                width=int(width),
                height=int(height),
                sha1=str(sha1),
                source=sources[str(image_hash)],
                path=catalog_dir / f"{image_hash}.png",
                capture_preset=preset,
                approved_build=approved_build,
            )
            for image_hash, kind, width, height, sha1, preset, approved_build in conn.execute(
                "SELECT image_hash, kind, width, height, file_sha1, capture_preset, approved_build FROM images"
            )
        }
        rows = conn.execute("SELECT title, image_hash, stable_key FROM image_titles").fetchall()
    for picture in pictures.values():
        if not picture.path.is_file():
            raise FileNotFoundError(f"The catalog lacks the file of picture {picture.image_hash}: {picture.path}")
    return Catalog(
        game_build=game_build,
        pictures=pictures,
        titles={f"File:{title}": str(image_hash) for title, image_hash, _ in rows},
        entities={f"File:{title}": stable_key for title, _, stable_key in rows},
    )


@dataclass(frozen=True, slots=True)
class LiveWiki:
    """One listing of the wiki's files and File pages.

    ``files`` holds the current version of every uploaded file by title.
    ``redirects`` maps every File redirect to the page it names: a title shows
    a picture through a redirect only when that page holds the file, because
    MediaWiki follows one file redirect. ``pages`` holds every other File page,
    with or without a file.
    """

    files: Mapping[str, MediaWikiFile]
    redirects: Mapping[str, str]
    pages: frozenset[str]

    def has_page(self, title: str) -> bool:
        return title in self.files or title in self.redirects or title in self.pages


class LivePictureCache:
    """The bytes and pixel hashes of live files, downloaded once and kept by SHA-1."""

    _INDEX = "pixel-hashes.json"

    def __init__(self, download: Callable[[str], bytes], directory: Path) -> None:
        self._download = download
        self._directory = directory
        index = directory / self._INDEX
        self._hashes: dict[str, str] = json.loads(index.read_text(encoding="utf-8")) if index.is_file() else {}
        self.downloads = 0

    def content(self, file: MediaWikiFile) -> bytes:
        """The bytes of a file's current version, downloaded unless the cache holds them."""
        path = self._directory / f"{file.sha1}.bin"
        if path.is_file():
            return path.read_bytes()
        data = self._download(file.url)
        if hashlib.sha1(data, usedforsecurity=False).hexdigest() != file.sha1:
            raise ValueError(f"The download of {file.title} does not have the SHA-1 that the listing gives")
        self.downloads += 1
        self._directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
        return data

    def pixel_hash(self, file: MediaWikiFile) -> str:
        """The pixel hash of a file's current version, or a marker for bytes that are not a picture."""
        known = self._hashes.get(file.sha1)
        if known is None:
            try:
                known = identify(self.content(file)).pixel_hash
            except (UnidentifiedImageError, OSError):
                known = f"unreadable {file.sha1}"
            self._hashes[file.sha1] = known
        return known

    def save(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        (self._directory / self._INDEX).write_text(json.dumps(self._hashes, indent=0, sort_keys=True) + "\n")


@dataclass(frozen=True, slots=True)
class PlannedTitle:
    """The verdict of one title.

    ``file`` is the title of the picture's file, which every other title of the
    picture redirects to, or None when no title of the picture can hold it.
    ``live_sha1`` and ``live_user`` describe the file at the title when the plan
    was made, and ``redirect_target`` the target of its redirect. ``warnings``
    are the upload warnings that the verdict expects.
    """

    title: str
    verdict: Verdict
    image_hash: str
    file: str | None
    reason: str
    live_sha1: str | None = None
    live_user: str | None = None
    redirect_target: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def retired_title(self) -> str:
        return RETIRED_PREFIX + self.title.removeprefix("File:")


@dataclass(frozen=True, slots=True)
class Orphan:
    """A file of the project that no title produces and no page shows."""

    title: str
    user: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class PublishPlan:
    """The verdict of every title, the orphans, and the retired files that await deletion.

    ``untagged`` names the retired files whose description page lacks the
    deletion notice.
    """

    titles: tuple[PlannedTitle, ...]
    orphans: tuple[Orphan, ...]
    retired: tuple[str, ...]
    untagged: tuple[str, ...]

    def counts(self) -> dict[str, int]:
        return {verdict: sum(item.verdict == verdict for item in self.titles) for verdict in VERDICTS}

    def to_json(self) -> dict[str, Any]:
        return {
            "counts": self.counts(),
            "titles": [asdict(item) for item in self.titles],
            "orphans": [asdict(orphan) for orphan in self.orphans],
            "retired": list(self.retired),
            "untagged": list(self.untagged),
        }


def plan_publication(
    catalog: Catalog,
    live: LiveWiki,
    owners: Collection[str],
    pictures: LivePictureCache,
    is_used: Callable[[str], bool],
    delete_tagged: Callable[[Sequence[str]], Collection[str]],
) -> PublishPlan:
    """Give every title one verdict against one listing of the wiki.

    Args:
        catalog: The pictures and titles of the clean build.
        live: The listing of the wiki.
        owners: The accounts whose uploads are the project's.
        pictures: The bytes and pixel hashes of live files.
        is_used: Whether a page shows a file, directly or through a redirect.
        delete_tagged: Which of the given retired files carry the deletion notice.
    """
    planner = _Planner(catalog, live, frozenset(owners), pictures)
    titles = planner.titles()
    files = {image_hash: planner.choose_file(image_hash, members) for image_hash, members in _by_picture(titles)}
    # A picture's file may take a title that no page names, such as the upload
    # title of a title with a colon, so the plan creates or keeps it too.
    for image_hash, file_title in files.items():
        if file_title is not None:
            titles.setdefault(file_title, image_hash)
    planned = tuple(planner.verdict(title, titles[title], files[titles[title]]) for title in sorted(titles))

    retiring = {item.retired_title for item in planned if item.verdict == "retire"}
    retired_before = sorted(
        title
        for title, file in live.files.items()
        if title.startswith(RETIRED_PREFIX) and file.user in planner.owners and title not in titles
    )
    tagged = set(delete_tagged(retired_before))
    orphans = tuple(
        Orphan(title, file.user or "", file.timestamp)
        for title, file in live.files.items()
        if title not in titles
        and not title.startswith(RETIRED_PREFIX)
        and file.user in planner.owners
        and not is_used(title)
    )
    return PublishPlan(
        titles=planned,
        orphans=orphans,
        retired=tuple(sorted(retiring | set(retired_before))),
        untagged=tuple(title for title in retired_before if title not in tagged),
    )


def _by_picture(titles: Mapping[str, str]) -> Iterable[tuple[str, list[str]]]:
    members: dict[str, list[str]] = defaultdict(list)
    for title, image_hash in titles.items():
        members[image_hash].append(title)
    return members.items()


def _entity_rank(stable_key: str | None) -> int:
    kind = (stable_key or "").partition(":")[0]
    return _ENTITY_ORDER.index(kind) if kind in _ENTITY_ORDER else len(_ENTITY_ORDER)


class _Planner:
    def __init__(self, catalog: Catalog, live: LiveWiki, owners: frozenset[str], pictures: LivePictureCache) -> None:
        self.catalog = catalog
        self.live = live
        self.owners = owners
        self.pictures = pictures
        self.entities: dict[str, str | None] = dict(catalog.entities)
        self.picture_of: dict[str, str] = {}
        self._by_sha1: dict[str, list[str]] = defaultdict(list)
        for title, file in live.files.items():
            self._by_sha1[file.sha1].append(title)

    def titles(self) -> dict[str, str]:
        """The catalog's titles, plus the upload title of each title with a colon that the wiki has.

        A title with a colon cannot hold a file, so the old pipeline uploaded
        to the title without it and redirected. Such an upload title joins the
        plan, so that its copy is retired or becomes the picture's file.
        """
        titles = dict(self.catalog.titles)
        for title, image_hash in self.catalog.titles.items():
            upload = _upload(title)
            if upload == title:
                continue
            known = titles.get(upload)
            if known is not None and known != image_hash:
                raise ValueError(f"{title} and {upload} name different pictures")
            if known is None and self.live.has_page(upload):
                titles[upload] = image_hash
                self.entities[upload] = self.entities[title]
        self.picture_of = titles
        return titles

    def owned(self, file: MediaWikiFile) -> bool:
        return file.user in self.owners

    def holds(self, picture: Picture, file: MediaWikiFile) -> bool:
        """Whether a live file has the picture's pixels."""
        if file.sha1 == picture.sha1:
            return True
        if (file.width, file.height) != (picture.width, picture.height):
            return False
        if self.owned(file) and picture.image_hash in (file.comment or ""):
            return True
        return self.pictures.pixel_hash(file) == picture.image_hash

    def choose_file(self, image_hash: str, members: Sequence[str]) -> str | None:
        """The title of a picture's file (design D5).

        A file that holds the picture already comes first, at one of the
        picture's titles or at the target of one's redirect. Then come a title
        whose file the project may update and a missing title. Within each
        group the order is item, spell, skill, stance, character, then title.
        A title held by someone else's other picture or by a page without a
        file cannot take the upload.
        """
        picture = self.catalog.pictures[image_hash]
        ranks: dict[str, int] = {}
        for title in members:
            rank = _entity_rank(self.entities.get(title))
            candidates = [_upload(title)]
            target = self.live.redirects.get(title)
            if (
                target is not None
                and target in self.live.files
                and self.picture_of.get(target, image_hash) == image_hash
            ):
                candidates.append(target)
            for candidate in candidates:
                ranks[candidate] = min(ranks.get(candidate, len(_ENTITY_ORDER)), rank)

        def preference(candidate: str) -> tuple[int, int, str] | None:
            file = self.live.files.get(candidate)
            if file is not None and self.holds(picture, file):
                group = 0
            elif file is not None and self.owned(file) and candidate in members:
                group = 1
            elif not self.live.has_page(candidate):
                group = 2
            else:
                return None
            return (group, ranks[candidate], candidate)

        preferences = [key for key in map(preference, ranks) if key is not None]
        return min(preferences)[2] if preferences else None

    def verdict(self, title: str, image_hash: str, file_title: str | None) -> PlannedTitle:  # noqa: PLR0911
        picture = self.catalog.pictures[image_hash]
        live = self.live.files.get(title)
        target = self.live.redirects.get(title)
        facts = {
            "live_sha1": live.sha1 if live else None,
            "live_user": live.user if live else None,
            "redirect_target": target,
        }

        def planned(verdict: Verdict, reason: str, warnings: tuple[str, ...] = ()) -> PlannedTitle:
            return PlannedTitle(title, verdict, image_hash, file_title, reason, warnings=warnings, **facts)

        if file_title is None:
            if live is not None and not self.owned(live):
                return planned("conflict", f"{live.user} uploaded the file")
            shown = self.live.files.get(target or "")
            if shown is not None and not self.owned(shown):
                return planned("conflict", f"the title redirects to {target}, which {shown.user} uploaded")
            return planned("conflict", "no title of the picture can hold its file")
        duplicate = ("duplicate",) if any(other != title for other in self._by_sha1.get(picture.sha1, ())) else ()
        if title == file_title:
            if live is None:
                return planned("create", "the file is missing", duplicate)
            if self.holds(picture, live):
                return planned("unchanged", "the file has the picture")
            if self.owned(live):
                # An earlier version of the file may hold the picture's bytes already.
                return planned("update", "the file has other pixels", ("exists", "duplicateversions", *duplicate))
            return planned("conflict", f"{live.user} uploaded the file")
        if live is not None:
            if self.owned(live):
                if self.live.has_page(RETIRED_PREFIX + title.removeprefix("File:")):
                    return planned("conflict", "the title of its retired copy is taken")
                return planned("retire", f"a copy of the picture belongs at {file_title}")
            return planned("conflict", f"{live.user} uploaded a file here")
        if target is not None:
            if target == file_title:
                return planned("unchanged", "the title redirects to the picture's file")
            shown = self.live.files.get(target)
            if shown is None or self.owned(shown) or self.holds(picture, shown):
                return planned("redirect", f"the title redirects to {target}")
            return planned("conflict", f"the title redirects to {target}, which {shown.user} uploaded")
        if title in self.live.pages:
            return planned("conflict", "a page without a file holds the title")
        return planned("redirect", "the title is missing")


def _upload(title: str) -> str:
    return "File:" + upload_file_title(title.removeprefix("File:"))


_CELL = 64
_ROW_HEIGHT = _CELL + 16
_LABEL_WIDTH = 420
_LIVE_COLUMNS = 3
_ROWS_PER_SHEET = 40


def write_contact_sheets(
    plan: PublishPlan, catalog: Catalog, live: LiveWiki, pictures: LivePictureCache, directory: Path
) -> list[Path]:
    """Draw every picture that the plan changes beside what its titles show live.

    Each row shows one picture: its title and change counts, the new picture,
    and up to three distinct live pictures that its titles show now.
    """
    changing: dict[str, list[PlannedTitle]] = defaultdict(list)
    for item in plan.titles:
        if item.verdict in ("create", "update", "redirect", "retire"):
            changing[item.image_hash].append(item)
    rows = []
    for image_hash, items in sorted(changing.items(), key=lambda entry: entry[1][0].file or ""):
        shown: dict[str, MediaWikiFile] = {}
        for item in plan.titles:
            if item.image_hash != image_hash:
                continue
            current = live.files.get(item.title) or live.files.get(item.redirect_target or "")
            if current is not None:
                shown.setdefault(current.sha1, current)
        verdicts: dict[str, int] = defaultdict(int)
        for item in items:
            verdicts[item.verdict] += 1
        label = f"{(items[0].file or '').removeprefix('File:')}\n" + ", ".join(
            f"{count} {verdict}" for verdict, count in sorted(verdicts.items())
        )
        rows.append((label, catalog.pictures[image_hash].path, list(shown.values())[:_LIVE_COLUMNS]))

    directory.mkdir(parents=True, exist_ok=True)
    sheets = []
    for start in range(0, len(rows), _ROWS_PER_SHEET):
        page = rows[start : start + _ROWS_PER_SHEET]
        width = _LABEL_WIDTH + (_LIVE_COLUMNS + 2) * (_CELL + 8)
        sheet = Image.new("RGB", (width, len(page) * _ROW_HEIGHT + 24), (40, 40, 40))
        draw = ImageDraw.Draw(sheet)
        draw.text((_LABEL_WIDTH, 4), "new", fill=(240, 220, 140))
        draw.text((_LABEL_WIDTH + 2 * (_CELL + 8), 4), "live now", fill=(240, 220, 140))
        for index, (label, new_path, shown_files) in enumerate(page):
            top = 24 + index * _ROW_HEIGHT
            draw.text((8, top + 8), label, fill=(230, 230, 230))
            with Image.open(new_path) as new:
                _paste(sheet, new, _LABEL_WIDTH, top)
            for column, file in enumerate(shown_files):
                try:
                    with Image.open(io.BytesIO(pictures.content(file))) as old:
                        _paste(sheet, old, _LABEL_WIDTH + (column + 2) * (_CELL + 8), top)
                except (UnidentifiedImageError, OSError):
                    draw.text((_LABEL_WIDTH + (column + 2) * (_CELL + 8), top + 24), "?", fill=(255, 80, 80))
        path = directory / f"contact-sheet-{start // _ROWS_PER_SHEET + 1:03d}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets


def _paste(sheet: Image.Image, picture: Image.Image, left: int, top: int) -> None:
    thumbnail = picture.convert("RGBA")
    thumbnail.thumbnail((_CELL, _CELL), Image.Resampling.LANCZOS)
    backdrop = Image.new("RGBA", (_CELL, _CELL), (90, 90, 90, 255))
    backdrop.alpha_composite(thumbnail, ((_CELL - thumbnail.width) // 2, (_CELL - thumbnail.height) // 2))
    sheet.paste(backdrop.convert("RGB"), (left, top))
