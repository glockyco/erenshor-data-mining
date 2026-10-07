"""The manifest of character models to capture: one entry for each character image title.

A character's image title follows its model, so characters that share a model
share one title and one capture (design D5 of the change
restore-missing-wiki-images). The manifest lists every title of the clean
database once, whether or not the wiki has a picture for it, because the picture
catalog holds a render of every character. Each entry names the pages of its
characters, the generated ones and those that ``content-lifecycle.json`` marks
as unused, and one game object to capture: a prefab that ``Resources.Load`` can
load, a character placed in a scene, or a prefab that a scene references
(design D3 of that change).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erenshor.domain.value_objects.wiki_filename import image_file_title

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# The camera, light, and framing that a capture uses. A change to the capture
# mode's preset needs a new name, so that captures of different presets are
# never mixed in one review.
CAMERA_PRESET = "portrait-3"


@dataclass(frozen=True, slots=True)
class CharacterSource:
    """A character of the clean database with the facts that locate its game object."""

    stable_key: str
    image_title: str
    wiki_page: str | None
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
    kind: str  # character or summon
    stable_key: str
    source: CaptureSource
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnsourcedModel:
    """A model whose characters no capture can locate, with the pages that show it."""

    file: str
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelImageManifest:
    game_build: str
    camera_preset: str
    entries: tuple[ManifestEntry, ...]
    unsourced: tuple[UnsourcedModel, ...]

    def to_json(self) -> dict[str, object]:
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
            "unsourced": [{"file": model.file, "pages": list(model.pages)} for model in self.unsourced],
        }


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
    """Prefer a character of a generated page, then a prefab that loads
    without a scene, then a placed character that is on at load."""
    if character.resources_path:
        source = 0
    elif not character.is_prefab and character.scene:
        source = 1 if character.is_enabled else 2
    else:
        source = 3
    return not character.is_wiki_generated, source, character.stable_key


def _sorted_pages(pages: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(pages), key=lambda page: (page.casefold(), page)))


def build_manifest(
    characters: Sequence[CharacterSource],
    unused_pages: Mapping[str, str],
    game_build: str,
) -> ModelImageManifest:
    """The manifest of every character model of the clean database.

    ``unused_pages`` maps each page with the unused notice to the stable key of
    its character, which the bot does not generate a page for.
    """
    known = {character.stable_key for character in characters}
    unused_by_key: dict[str, list[str]] = defaultdict(list)
    for page, stable_key in unused_pages.items():
        if stable_key not in known:
            raise ValueError(f"{page}: the unused page's character {stable_key} is not in the clean database")
        unused_by_key[stable_key].append(page)

    by_title: dict[str, list[CharacterSource]] = defaultdict(list)
    for character in characters:
        by_title[character.image_title].append(character)

    entries: list[ManifestEntry] = []
    unsourced: list[UnsourcedModel] = []
    for file in sorted(by_title):
        models = by_title[file]
        pages = _sorted_pages(
            [character.wiki_page for character in models if character.wiki_page]
            + [page for character in models for page in unused_by_key.get(character.stable_key, ())]
        )
        located = sorted(
            ((character, source) for character in models if (source := capture_source(character)) is not None),
            key=lambda pair: _capture_rank(pair[0]),
        )
        if not located:
            unsourced.append(UnsourcedModel(file=file, pages=pages))
            continue
        chosen, source = located[0]
        kind = "summon" if any(character.is_summon for character in models) else "character"
        entries.append(ManifestEntry(file=file, kind=kind, stable_key=chosen.stable_key, source=source, pages=pages))
    return ModelImageManifest(
        game_build=game_build,
        camera_preset=CAMERA_PRESET,
        entries=tuple(entries),
        unsourced=tuple(unsourced),
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
        SELECT c.stable_key, c.image_name, c.display_name, c.wiki_page_name, c.object_name, c.npc_name,
               c.scene, c.x, c.y, c.z, c.is_prefab, c.is_enabled, c.is_wiki_generated, c.resources_path,
               EXISTS (SELECT 1 FROM spells s WHERE s.pet_to_summon_stable_key = c.stable_key)
        FROM characters c
        ORDER BY c.stable_key
        """
    )
    return [
        CharacterSource(
            stable_key=stable_key,
            image_title=image_file_title(image_name, display_name),
            wiki_page=wiki_page,
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
            display_name,
            wiki_page,
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
