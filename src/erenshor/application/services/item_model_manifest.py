"""The manifest of item models to capture: one entry for each item render.

An item's model is the game object that equipping or building the item turns
on by its ``EquipmentToActivate``: a part of the player's body, a weapon or
shield in a hand, a mask, or the furnishing of a Reliquary furniture set
(design D2 of the change show-item-pictures-by-role). A lamp or the Watcher's
Lens in a cosmetic slot turns on the player's belt lamp or lens, which the
capture names by the item's cosmetic effect; the three lamps share one model. A render shows that
model by itself. The male and the female body hold separate meshes for most
armour parts, so a worn item whose parts draw different meshes on the two
bodies gets one render for each, ``<subject> render (male).png`` and
``<subject> render (female).png``. Every other item gets one
``<subject> render.png``. Items that share a subject share their renders.

Each entry's ``subject`` is the name under which the capture, the review, and
the approval record the picture: the item's picture subject, followed by the
body in parentheses for a render of one body.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from erenshor.application.services.model_image_manifest import load_scene_landings
from erenshor.domain.value_objects.wiki_filename import (
    Body,
    body_render_title,
    picture_file_title,
    picture_subject,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# The camera, light, and framing of an item capture. A change of the preset
# needs a new name, so that captures of different presets are never mixed.
ITEM_PRESET = "item-1"

# The ModularParts slot transforms that UpdatePlayerVisuals fills for each
# slot of a worn item or a weapon. A bow in the primary slot goes to the left hand.
_SLOT_FIELDS: Mapping[str, tuple[str, ...]] = {
    "Head": ("HeadCover", "FullHeadHelm", "HatWithHair"),
    "Chest": ("Chest",),
    "Leg": ("Pants",),
    "Arm": ("ArmL", "ArmR"),
    "Foot": ("BootsL", "BootsR"),
    "Hand": ("GloveL", "GloveR"),
    "Bracer": ("BracerL", "BracerR"),
    "Back": ("Cloak",),
    "Primary": ("WeaponR",),
    "Secondary": ("WeaponL",),
    "PrimaryOrSecondary": ("WeaponR",),
}
_WEAPON_SLOTS = frozenset({"Primary", "Secondary", "PrimaryOrSecondary"})
_BOW_FIELDS = ("WeaponL",)
# The slot of the mask objects, which the cosmetic effect of an item names instead.
_MASK_SLOT = "HalloweenMasks"
# The cosmetic effects that turn on an object of the player, as the capture names it.
_COSMETIC_OBJECTS = frozenset({"belt lamp", "lens"})
_BODIES: tuple[Body, ...] = ("male", "female")
_EMPTY_PARTS = frozenset({"", "DEFAULT", "0"})


@dataclass(frozen=True, slots=True)
class ItemSource:
    """An item of the clean database with the facts that locate its model."""

    stable_key: str
    item_id: str
    subject: str
    wiki_page: str
    required_slot: str
    part: str
    is_bow: bool
    is_furniture_set: bool
    cosmetic_effect: str | None


@dataclass(frozen=True, slots=True)
class ModelParts:
    """The exported game objects that items turn on.

    ``body_meshes`` maps (body, slot field, part) to the meshes that the part
    draws, and ``furnishings`` maps the name of each planning table furnishing
    to its scene and a place in that scene where the player can land while the
    capture loads it.
    """

    body_meshes: Mapping[tuple[str, str, str], frozenset[str]]
    furnishings: Mapping[str, tuple[str, tuple[float, float, float]]]


@dataclass(frozen=True, slots=True)
class ItemManifestEntry:
    subject: str
    title: str
    kind: str  # weapon, worn, mask, furnishing, or cosmetic
    body: Body | None
    stable_key: str
    item_id: str
    slot: str
    part: str
    pages: tuple[str, ...]
    # The scene to load and the player's landing in it, for a furnishing.
    scene: str | None = None
    landing: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class UnsourcedItem:
    """An item whose model no exported game object holds."""

    subject: str
    part: str
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemModelManifest:
    game_build: str
    camera_preset: str
    entries: tuple[ItemManifestEntry, ...]
    unsourced: tuple[UnsourcedItem, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "game_build": self.game_build,
            "camera_preset": self.camera_preset,
            "entries": [
                {
                    "subject": entry.subject,
                    "title": entry.title,
                    "kind": entry.kind,
                    "body": entry.body,
                    "stable_key": entry.stable_key,
                    "item_id": entry.item_id,
                    "slot": entry.slot,
                    "part": entry.part,
                    "pages": list(entry.pages),
                    "scene": entry.scene,
                    "landing": list(entry.landing) if entry.landing else None,
                }
                for entry in self.entries
            ],
            "unsourced": [
                {"subject": item.subject, "part": item.part, "pages": list(item.pages)} for item in self.unsourced
            ],
        }


def _fields(item: ItemSource) -> tuple[str, ...]:
    if item.required_slot == "Primary" and item.is_bow:
        return _BOW_FIELDS
    return _SLOT_FIELDS[item.required_slot]


def _body_meshes(item: ItemSource, parts: ModelParts, body: Body) -> frozenset[str] | None:
    """The meshes that the body's parts of the item's name draw, or None when the body holds none."""
    found = [
        parts.body_meshes[key] for field in _fields(item) if (key := (body, field, item.part)) in parts.body_meshes
    ]
    return frozenset().union(*found) if found else None


def _entry(
    item: ItemSource,
    pages: tuple[str, ...],
    kind: str,
    body: Body | None,
    *,
    per_body: bool,
    place: tuple[str, tuple[float, float, float]] | None = None,
    part: str | None = None,
) -> ItemManifestEntry:
    """An entry that captures the item on ``body``, titled for that body when ``per_body``."""
    if per_body and body is not None:
        subject, title = f"{item.subject} ({body})", body_render_title(body, item.subject)
    else:
        subject, title = item.subject, picture_file_title("render", item.subject)
    return ItemManifestEntry(
        subject=subject,
        title=title,
        kind=kind,
        body=body,
        stable_key=item.stable_key,
        item_id=item.item_id,
        slot=item.required_slot,
        part=item.part if part is None else part,
        pages=pages,
        scene=place[0] if place else None,
        landing=place[1] if place else None,
    )


def _sorted_pages(pages: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(pages), key=lambda page: (page.casefold(), page)))


def build_item_manifest(items: Sequence[ItemSource], parts: ModelParts, game_build: str) -> ItemModelManifest:
    """The manifest of every item model that a wiki page shows.

    Items without a model, such as rings and potions, and blueprints, which
    name their set's furnishing, get no entry.
    """
    by_subject: dict[str, list[ItemSource]] = defaultdict(list)
    for item in items:
        by_subject[item.subject].append(item)

    entries: list[ItemManifestEntry] = []
    unsourced: list[UnsourcedItem] = []
    for subject in sorted(by_subject):
        group = sorted(by_subject[subject], key=lambda item: item.stable_key)
        if len({(item.required_slot, item.part, item.is_bow, item.cosmetic_effect) for item in group}) > 1:
            names = ", ".join(item.stable_key for item in group)
            raise ValueError(f"{subject}: the items {names} share a subject but not a model")
        item = group[0]
        pages = _sorted_pages(member.wiki_page for member in group)
        if item.required_slot in _SLOT_FIELDS:
            meshes = {body: _body_meshes(item, parts, body) for body in _BODIES}
            held = [body for body in _BODIES if meshes[body] is not None]
            kind = "weapon" if item.required_slot in _WEAPON_SLOTS else "worn"
            if not held:
                unsourced.append(UnsourcedItem(subject=subject, part=item.part, pages=pages))
            elif kind == "worn" and len(held) == 2 and meshes["male"] != meshes["female"]:
                entries.extend(_entry(item, pages, kind, body, per_body=True) for body in _BODIES)
            else:
                entries.append(_entry(item, pages, kind, held[0], per_body=False))
        elif item.is_furniture_set:
            if item.part in parts.furnishings:
                place = parts.furnishings[item.part]
                entries.append(_entry(item, pages, "furnishing", None, per_body=False, place=place))
            else:
                unsourced.append(UnsourcedItem(subject=subject, part=item.part, pages=pages))
        elif item.cosmetic_effect == "mask":
            entries.append(_entry(item, pages, "mask", None, per_body=False))
        elif item.cosmetic_effect in _COSMETIC_OBJECTS:
            entries.append(_entry(item, pages, "cosmetic", None, per_body=False, part=item.cosmetic_effect))
    return ItemModelManifest(
        game_build=game_build,
        camera_preset=ITEM_PRESET,
        entries=tuple(entries),
        unsourced=tuple(unsourced),
    )


def load_item_sources(clean: sqlite3.Connection) -> list[ItemSource]:
    """Read every item that has a page and names a part or has a cosmetic effect."""
    rows = clean.execute(
        """
        SELECT stable_key, id, image_name, display_name, item_name, wiki_page_name, required_slot,
               equipment_to_activate, is_bow, furniture_set, cosmetic_effect
        FROM items
        WHERE COALESCE(wiki_page_name, '') != ''
        ORDER BY stable_key
        """
    ).fetchall()
    return [
        ItemSource(
            stable_key=str(stable_key),
            item_id=str(item_id),
            subject=picture_subject(image_name, display_name, item_name),
            wiki_page=str(page),
            required_slot=str(slot or ""),
            part=str(part).strip(),
            is_bow=bool(is_bow),
            is_furniture_set=bool(furniture_set),
            cosmetic_effect=cosmetic,
        )
        for (
            stable_key,
            item_id,
            image_name,
            display_name,
            item_name,
            page,
            slot,
            part,
            is_bow,
            furniture_set,
            cosmetic,
        ) in rows
        if str(part or "").strip() not in _EMPTY_PARTS or cosmetic is not None
    ]


def load_model_parts(clean: sqlite3.Connection) -> ModelParts:
    """Read the exported body parts and furnishings."""
    body_meshes: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for body, slot, part, meshes in clean.execute(
        "SELECT body, slot, part, meshes FROM item_model_parts WHERE slot != ?", (_MASK_SLOT,)
    ):
        body_meshes[(str(body), str(slot), str(part))].update(filter(None, str(meshes).split("|")))
    landings = load_scene_landings(clean)
    furnishings: dict[str, tuple[str, tuple[float, float, float]]] = {}
    for furnishing, scene in clean.execute(
        "SELECT DISTINCT furnishing, scene FROM planning_table_furnishings ORDER BY scene, furnishing"
    ):
        if scene not in landings:
            raise ValueError(f"No zone line leads into {scene}, the scene of the furnishing {furnishing}")
        furnishings.setdefault(str(furnishing), (str(scene), landings[str(scene)]))
    return ModelParts(
        body_meshes={key: frozenset(value) for key, value in body_meshes.items()},
        furnishings=furnishings,
    )
