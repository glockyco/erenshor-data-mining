"""The game objects that show an item's model: body parts, masks, and furnishings.

Equipping an item turns on the parts of the player's body whose name is the
item's ``EquipmentToActivate`` (``ModularParts.UpdateSlot``), and a furniture
set turns on the Reliquary furnishing of that name. The export records both
bodies' parts with the meshes they draw and the planning table's furnishings,
so the picture capture knows where each item's model is and whether the two
bodies draw it alike.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import sqlite3

    from .writer import Writer


def process_item_models(raw: sqlite3.Connection, writer: Writer) -> None:
    """Copy the exported body parts and furnishings into the clean database."""
    parts = [
        {"body": body.lower(), "slot": slot, "position": position, "part": part, "meshes": meshes}
        for body, slot, position, part, meshes in raw.execute(
            "SELECT Body, Slot, Position, Part, Meshes FROM ItemModelParts ORDER BY Body, Slot, Position"
        )
    ]
    if not parts:
        raise ValueError("The export holds no body parts of the player")
    furnishings = [
        {"scene": scene, "slot": slot, "furnishing": furnishing, "renderer_count": count}
        for scene, slot, furnishing, count in raw.execute(
            "SELECT Scene, Slot, Furnishing, RendererCount FROM PlanningTableFurnishings "
            "ORDER BY Scene, Slot, Furnishing"
        )
    ]
    writer.insert_item_model_parts(parts)
    writer.insert_planning_table_furnishings(furnishings)
    logger.info(f"Item models: {len(parts)} body parts, {len(furnishings)} furnishings")
