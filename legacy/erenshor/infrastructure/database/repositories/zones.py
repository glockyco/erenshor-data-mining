"""Zone repository - zone and location queries (fishing, mining, etc)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

__all__ = ["get_water_fishables", "get_waters"]


def get_waters(engine: Engine) -> list[dict[str, Any]]:
    """Fetch all fishing waters with zone information."""
    sql = text(
        """
        SELECT w.Id AS WaterId,
               c.Scene AS Scene,
               COALESCE(za.ZoneName, '') AS ZoneName
        FROM Waters w
        JOIN Coordinates c ON w.CoordinateId = c.Id
        LEFT JOIN ZoneAnnounces za ON za.SceneName = c.Scene
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_water_fishables(engine: Engine, water_id: str) -> list[dict[str, Any]]:
    """Fetch fishable items for a given water ID."""
    sql = text(
        """
        SELECT ItemName, Type, ROUND(DropChance, 2) AS DropChance
        FROM WaterFishables
        WHERE WaterId = :wid
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"wid": water_id}).mappings().all()
    return [dict(r) for r in rows]
