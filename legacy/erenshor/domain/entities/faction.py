"""Faction domain entities."""

from __future__ import annotations

from pydantic import BaseModel


class DbFaction(BaseModel):
    REFNAME: str
    FactionName: str
    FactionDesc: str


__all__ = ["DbFaction"]
