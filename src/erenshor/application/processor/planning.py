"""Characters that the Reliquary's planning table places with furniture.

The player puts one item into each room slot of the planning table. Building
the table turns on the room's child whose name is the item's
EquipmentToActivate when the item is a furniture set, and turns off the other
children. Every room has the same children, so a furnishing character can stand
at its spot in any of the eight rooms (design D18 of adopt-data-backed-wiki).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

# The slots that ExecuteBuild builds from the children that CaptureRoomLayouts
# collects. The export also records the statue slots, which hold no character.
# code-fact: planning.builds
_ROOM_SLOTS = frozenset({"L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"})


def furniture_items_by_character(raw: sqlite3.Connection) -> dict[str, str]:
    """The furniture set that places each character of a planning table room, by character stable key.

    A room keeps its furnishings when the player puts in an item other than a
    furniture set or an empty slot, and a furniture set turns on the child that
    its EquipmentToActivate names.
    """
    # code-fact: planning.build_gate
    # code-fact: planning.build_furnishing
    furniture: dict[str, str] = {}
    for item_key, furnishing in raw.execute(
        "SELECT StableKey, EquipmentToActivate FROM Items WHERE FurnitureSet = 1 ORDER BY StableKey"
    ):
        if furnishing in furniture:
            raise ValueError(f"furniture sets {furniture[furnishing]} and {item_key} both build {furnishing!r}")
        furniture[str(furnishing)] = str(item_key)
    placed: dict[str, str] = {}
    for character_key, slot, furnishing in raw.execute(
        "SELECT CharacterStableKey, Slot, Furnishing FROM PlanningTableCharacters ORDER BY CharacterStableKey"
    ):
        if slot not in _ROOM_SLOTS:
            raise ValueError(f"{character_key}: the planning table slot {slot} places it, and only rooms are described")
        item_key = furniture.get(str(furnishing))
        if item_key is None:
            raise ValueError(f"{character_key}: no furniture set builds the furnishing {furnishing!r}")
        placed[str(character_key)] = item_key
    return placed
