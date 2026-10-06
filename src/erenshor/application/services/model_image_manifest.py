"""The manifest of character images that the wiki lacks, with the game object to capture for each.

The manifest reads the image of every character infobox on the generated pages
and of every page that ``content-lifecycle.json`` marks as unused, asks the
wiki which of those files have no upload, and joins each missing file to the
characters of the clean database by image name. Each missing file appears once,
with every page that shows it and one game object to capture: a prefab that
``Resources.Load`` can load, a character placed in a scene, or a prefab that a
loaded scene references. Zone images belong to editors, so the manifest lists
their missing files apart from the captures (design D3 and D4 of the change
restore-missing-wiki-images).
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote

from erenshor.infrastructure.wiki.template_parser import TemplateParser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

# The camera, light, and framing that a capture uses. A change to the capture
# mode's preset needs a new name, so that captures of different presets are
# never mixed in one review.
CAMERA_PRESET = "portrait-1"

_FILE_LINK = re.compile(r"\[\[\s*(?:File|Image)\s*:\s*([^|\]]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ImageUse:
    """A page that shows an image file, with the character it shows when the infobox names one."""

    file: str
    page: str
    stable_key: str | None
    kind: str  # character, chest, summon, or zone


@dataclass(frozen=True, slots=True)
class CharacterSource:
    """A character of the clean database with the facts that locate its game object."""

    stable_key: str
    image_name: str
    object_name: str | None
    npc_name: str | None
    scene: str | None
    position: tuple[float, float, float] | None
    is_prefab: bool
    is_enabled: bool
    is_wiki_generated: bool
    resources_path: str | None
    spawn_points: tuple[tuple[str, float, float, float], ...]  # (scene, x, y, z)
    is_summon: bool


@dataclass(frozen=True, slots=True)
class CaptureSource:
    """Where the capture finds the game object.

    A ``resources_path`` loads the prefab without a scene. Otherwise the
    capture lands the player at ``landing`` in ``scene`` and takes the
    character of that name: the one nearest ``position`` when the scene places
    it, or else the prefab that the scene references. A placed character
    answers to ``object_name`` until it starts and to ``npc_name`` after,
    because ``NPC.Start`` renames it.
    """

    resources_path: str | None
    scene: str | None
    object_name: str | None
    npc_name: str | None
    position: tuple[float, float, float] | None
    landing: tuple[float, float, float] | None


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    file: str
    kind: str
    stable_key: str
    source: CaptureSource
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UncapturedFile:
    """A missing file that the manifest does not capture, with the pages that show it."""

    file: str
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelImageManifest:
    game_build: str
    camera_preset: str
    entries: tuple[ManifestEntry, ...]
    unsourced: tuple[UncapturedFile, ...]
    editor_files: tuple[UncapturedFile, ...]

    def to_json(self) -> dict[str, object]:
        def uncaptured(files: Iterable[UncapturedFile]) -> list[dict[str, object]]:
            return [{"file": file.file, "pages": list(file.pages)} for file in files]

        return {
            "game_build": self.game_build,
            "camera_preset": self.camera_preset,
            "entries": [
                {
                    "file": entry.file,
                    "kind": entry.kind,
                    "stable_key": entry.stable_key,
                    "source": {
                        "resources_path": entry.source.resources_path,
                        "scene": entry.source.scene,
                        "object_name": entry.source.object_name,
                        "npc_name": entry.source.npc_name,
                        "position": list(entry.source.position) if entry.source.position else None,
                        "landing": list(entry.source.landing) if entry.source.landing else None,
                    },
                    "pages": list(entry.pages),
                }
                for entry in self.entries
            ],
            "unsourced": uncaptured(self.unsourced),
            "editor_files": uncaptured(self.editor_files),
        }


def file_title(name: str) -> str:
    """The canonical title of a file without its namespace, as MediaWiki normalizes it."""
    title = " ".join(unquote(name).replace("_", " ").split())
    return title[:1].upper() + title[1:]


def _expand_page_name(text: str, page: str) -> str:
    return text.replace("{{PAGENAME}}", page).replace("{{PAGENAMEE}}", quote(page.replace(" ", "_"), safe="/:"))


def _shown_file(params: Mapping[str, str], page: str) -> str | None:
    """The file that an infobox shows: its ``imagefile``, or the file that its ``image`` links."""
    explicit = params.get("imagefile", "").strip()
    if explicit:
        return file_title(explicit)
    match = _FILE_LINK.search(_expand_page_name(params.get("image", ""), page))
    return file_title(match.group(1)) if match else None


def page_image_uses(pages: Mapping[str, str]) -> list[ImageUse]:
    """The images of the character and zone infoboxes of pages, by page title."""
    parser = TemplateParser()
    uses: list[ImageUse] = []
    for page, text in pages.items():
        code = parser.parse(text)
        for root in parser.find_templates(code, ["Character"]):
            params = parser.get_params(root)
            file = _shown_file(params, page)
            if file is None:
                continue
            kind = params.get("imagekind", "").strip() or ("chest" if params.get("type", "").strip() == "Chest" else "")
            stable_key = params.get("stablekey", "").strip() or None
            uses.append(ImageUse(file=file, page=page, stable_key=stable_key, kind=kind or "character"))
        for root in parser.find_templates(code, ["Zone"]):
            file = _shown_file(parser.get_params(root), page)
            if file is not None:
                uses.append(ImageUse(file=file, page=page, stable_key=None, kind="zone"))
    return uses


def unused_page_image_uses(unused: Mapping[str, str], characters: Sequence[CharacterSource]) -> list[ImageUse]:
    """The images of the pages of unused characters, by page title and stable key.

    The bot does not generate these pages, so the manifest takes the image of
    each from the clean database rather than from the page.
    """
    by_key = {character.stable_key: character for character in characters}
    uses: list[ImageUse] = []
    for page, stable_key in unused.items():
        character = by_key.get(stable_key)
        if character is None:
            raise ValueError(f"{page}: the unused page's character {stable_key} is not in the clean database")
        kind = "summon" if character.is_summon else "character"
        uses.append(
            ImageUse(file=file_title(f"{character.image_name}.png"), page=page, stable_key=stable_key, kind=kind)
        )
    return uses


def capture_source(character: CharacterSource) -> CaptureSource | None:
    """Where a capture finds the character's game object, or None when nothing locates it."""
    if character.resources_path:
        return CaptureSource(
            resources_path=character.resources_path,
            scene=None,
            object_name=None,
            npc_name=None,
            position=None,
            landing=None,
        )
    if not character.object_name:
        return None
    if not character.is_prefab and character.scene and character.position:
        return CaptureSource(
            resources_path=None,
            scene=character.scene,
            object_name=character.object_name,
            npc_name=character.npc_name,
            position=character.position,
            landing=character.position,
        )
    if character.spawn_points:
        scene, x, y, z = character.spawn_points[0]
        return CaptureSource(
            resources_path=None,
            scene=scene,
            object_name=character.object_name,
            npc_name=character.npc_name,
            position=None,
            landing=(x, y, z),
        )
    return None


def _capture_rank(character: CharacterSource) -> tuple[bool, int, str]:
    """Prefer a character of a generated page to an unused one, then a prefab that loads
    without a scene, then a placed character that is on at load."""
    if character.resources_path:
        source = 0
    elif not character.is_prefab and character.scene:
        source = 1 if character.is_enabled else 2
    else:
        source = 3
    return not character.is_wiki_generated, source, character.stable_key


def build_manifest(
    uses: Sequence[ImageUse],
    characters: Sequence[CharacterSource],
    uploaded_files: Callable[[Sequence[str]], frozenset[str]],
    game_build: str,
) -> ModelImageManifest:
    """The manifest of the files that ``uses`` show and the wiki lacks.

    ``uploaded_files`` takes ``File:`` titles and returns those with an upload.
    """
    uses_by_file: dict[str, list[ImageUse]] = defaultdict(list)
    for use in uses:
        uses_by_file[use.file].append(use)
    uploaded = uploaded_files([f"File:{file}" for file in sorted(uses_by_file)])
    characters_by_file: dict[str, list[CharacterSource]] = defaultdict(list)
    for character in characters:
        characters_by_file[file_title(f"{character.image_name}.png")].append(character)

    entries: list[ManifestEntry] = []
    unsourced: list[UncapturedFile] = []
    editor_files: list[UncapturedFile] = []
    for file in sorted(uses_by_file):
        if f"File:{file}" in uploaded:
            continue
        file_uses = uses_by_file[file]
        pages = tuple(sorted({use.page for use in file_uses}, key=lambda page: (page.casefold(), page)))
        if any(use.kind == "zone" for use in file_uses):
            editor_files.append(UncapturedFile(file=file, pages=pages))
            continue
        candidates = characters_by_file.get(file, [])
        shown_keys = {use.stable_key for use in file_uses}
        shown = [character for character in candidates if character.stable_key in shown_keys] or candidates
        located = sorted(
            ((character, source) for character in shown if (source := capture_source(character)) is not None),
            key=lambda pair: _capture_rank(pair[0]),
        )
        if not located:
            unsourced.append(UncapturedFile(file=file, pages=pages))
            continue
        chosen, source = located[0]
        kinds = {use.kind for use in file_uses}
        kind = next((k for k in ("summon", "chest") if k in kinds), "character")
        entries.append(ManifestEntry(file=file, kind=kind, stable_key=chosen.stable_key, source=source, pages=pages))
    return ModelImageManifest(
        game_build=game_build,
        camera_preset=CAMERA_PRESET,
        entries=tuple(entries),
        unsourced=tuple(unsourced),
        editor_files=tuple(editor_files),
    )


def load_character_sources(clean: sqlite3.Connection) -> list[CharacterSource]:
    """Read every character of the clean database with the facts that locate its game object."""
    spawn_points: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
    for stable_key, scene, x, y, z in clean.execute(
        """
        SELECT character_stable_key, scene, x, y, z FROM character_spawns
        WHERE scene IS NOT NULL AND x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL
        ORDER BY scene, x, y, z
        """
    ):
        spawn_points[stable_key].append((scene, x, y, z))
    rows = clean.execute(
        """
        SELECT c.stable_key, c.image_name, c.object_name, c.npc_name, c.scene, c.x, c.y, c.z,
               c.is_prefab, c.is_enabled, c.is_wiki_generated, c.resources_path,
               EXISTS (SELECT 1 FROM spells s WHERE s.pet_to_summon_stable_key = c.stable_key)
        FROM characters c
        ORDER BY c.stable_key
        """
    )
    return [
        CharacterSource(
            stable_key=stable_key,
            image_name=image_name,
            object_name=object_name,
            npc_name=npc_name,
            scene=scene,
            position=(x, y, z) if x is not None and y is not None and z is not None else None,
            is_prefab=bool(is_prefab),
            is_enabled=bool(is_enabled),
            is_wiki_generated=bool(is_wiki_generated),
            resources_path=resources_path,
            spawn_points=tuple(spawn_points.get(stable_key, ())),
            is_summon=bool(is_summon),
        )
        for (
            stable_key,
            image_name,
            object_name,
            npc_name,
            scene,
            x,
            y,
            z,
            is_prefab,
            is_enabled,
            is_wiki_generated,
            resources_path,
            is_summon,
        ) in rows
    ]


def load_game_build(clean: sqlite3.Connection) -> str:
    """The game build of the clean database."""
    row = clean.execute("SELECT game_build_id FROM code_facts_meta").fetchone()
    if row is None or not row[0]:
        raise ValueError("The clean database records no game build")
    return str(row[0])
