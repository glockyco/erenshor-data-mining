"""What an item in a cosmetic slot of the inventory does.

An item in one of the inventory's cosmetic slots takes effect only if the game
knows it. ``Inventory.SetHalloweenMask`` shows the mask object whose name is the
item's ``EquipmentToActivate``, and ``Inventory.Update`` lights the belt lamp for
the items of ``BeltLampItem``, ``ShiveringBeltLamp``, and ``KeepersLamp`` and
shows the lens for the item of ``WatchersLens``. The export records the mask
objects with the body parts and the four items as ``CosmeticItems``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterable, Mapping

_EFFECTS = {"BeltLamp": "belt lamp", "FernallanLensObj": "lens"}
MASK = "mask"


def cosmetic_effects(
    items: Iterable[tuple[str, str | None]],
    mask_objects: Iterable[str],
    inventory_items: Mapping[str, str],
) -> dict[str, str]:
    """Map each cosmetic item's stable key to its effect: mask, belt lamp, or lens.

    ``items`` pairs each item's stable key with its ``EquipmentToActivate``,
    ``mask_objects`` holds the names of the mask objects, and ``inventory_items``
    maps each item that the inventory names to the field of the object it turns
    on. An item that the inventory names must exist, and its object must be known.
    """
    masks = frozenset(mask_objects)
    if not masks:
        raise ValueError("The export holds no mask objects")
    effects: dict[str, str] = {}
    keys: set[str] = set()
    for stable_key, equipment in items:
        keys.add(stable_key)
        # code-fact: cosmetics.mask_by_equipment_name
        if equipment and equipment in masks:
            effects[stable_key] = MASK
    for stable_key, field in inventory_items.items():
        if stable_key not in keys:
            raise ValueError(f"The inventory names {stable_key}, which is no item")
        if field not in _EFFECTS:
            raise ValueError(f"The inventory turns on {field} for {stable_key}, which no effect describes")
        if stable_key in effects:
            raise ValueError(f"{stable_key} is both a mask and the inventory's {field} item")
        effects[stable_key] = _EFFECTS[field]
    return effects


def load_cosmetic_effects(raw: sqlite3.Connection, items: Iterable[tuple[str, str | None]]) -> dict[str, str]:
    """The cosmetic effects of ``items``, which pairs each item's stable key with its ``EquipmentToActivate``."""
    return cosmetic_effects(
        items,
        (
            str(part)
            for (part,) in raw.execute("SELECT DISTINCT Part FROM ItemModelParts WHERE Slot = 'HalloweenMasks'")
        ),
        {str(key): str(effect) for key, effect in raw.execute("SELECT ItemStableKey, Effect FROM CosmeticItems")},
    )
