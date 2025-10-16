"""Relationship repository - cross-entity queries (items, characters, quests, factions)."""

from __future__ import annotations

from typing import Any, List

from sqlalchemy import text
from sqlalchemy.engine import Engine

from erenshor.domain.entities import DbFaction

__all__ = [
    "get_faction_desc_by_ref",
    "get_factions",
    "get_factions_map",
    "get_quest_by_dbname",
    "get_quests_requiring_item",
    "get_quests_rewarding_item",
]


def get_factions_map(engine: Engine) -> dict[str, str]:
    """Map faction name to faction description."""
    sql = text("SELECT FactionName, FactionDesc FROM Factions")
    with engine.connect() as conn:
        rows = conn.execute(sql).all()
    m: dict[str, str] = {}
    for name, desc in rows:
        if name:
            d = (desc or "").strip()
            if d:
                # Capitalize first letter if needed
                d = d[0].upper() + d[1:]
            m[str(name).strip()] = d
    return m


def get_faction_desc_by_ref(engine: Engine) -> dict[str, str]:
    """Map Factions.REFNAME -> Factions.FactionDesc (display name)."""
    sql = text("SELECT COALESCE(REFNAME,''), COALESCE(FactionDesc,'') FROM Factions")
    with engine.connect() as conn:
        rows = conn.execute(sql).all()
    out: dict[str, str] = {}
    for ref, desc in rows:
        if ref:
            out[str(ref).strip()] = str(desc or "").strip()
    return out


def get_factions(engine: Engine) -> List[DbFaction]:
    """Fetch all factions from the database."""
    sql = text(
        """
        SELECT REFNAME, FactionName, FactionDesc
        FROM Factions
        WHERE COALESCE(FactionDesc, '') <> ''
        ORDER BY FactionName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [DbFaction.model_validate(dict(r)) for r in rows]


def get_quests_rewarding_item(engine: Engine, item_id: str) -> list[dict[str, Any]]:
    """Fetch quests that reward a given item.

    Items are stored in the format 'ItemName (ItemId)' in comma-separated lists.
    We search for the pattern '(ItemId)' to match exact IDs.
    """
    # Build the search pattern with parentheses to match exact IDs
    pattern = f"%({item_id})%"
    sql = text(
        """
        SELECT QuestDBIndex AS Id, COALESCE(DBName,'') AS DBName, QuestName, ItemOnCompleteId
        FROM Quests
        WHERE COALESCE(ItemOnCompleteId,'') LIKE :pattern
        ORDER BY QuestName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"pattern": pattern}).mappings().all()
    return [dict(r) for r in rows]


def get_quests_requiring_item(engine: Engine, item_id: str) -> list[dict[str, Any]]:
    """Fetch quests that require a given item.

    Items are stored in the format 'ItemName (ItemId)' in comma-separated lists.
    We search for the pattern '(ItemId)' to match exact IDs.
    """
    # Build the search pattern with parentheses to match exact IDs
    pattern = f"%({item_id})%"
    sql = text(
        """
        SELECT QuestDBIndex AS Id, COALESCE(DBName,'') AS DBName, QuestName, RequiredItemIds
        FROM Quests
        WHERE COALESCE(RequiredItemIds,'') LIKE :pattern
        ORDER BY QuestName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"pattern": pattern}).mappings().all()
    return [dict(r) for r in rows]


def get_quest_by_dbname(engine: Engine, db_name: str) -> dict[str, Any] | None:
    """Return quest record by Quests.DBName (minimal columns)."""
    sql = text(
        """
        SELECT QuestDBIndex AS Id, COALESCE(DBName,'') AS DBName, COALESCE(QuestName,'') AS QuestName
        FROM Quests
        WHERE COALESCE(DBName,'') = :dbname
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"dbname": db_name}).mappings().first()
    return dict(row) if row else None
