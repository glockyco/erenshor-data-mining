"""Fishing template contexts."""

from __future__ import annotations

import builtins as _b

from pydantic import BaseModel


class FishingRow(BaseModel):
    """Single row in a fishing table."""

    name: _b.str
    day_rate: _b.str
    night_rate: _b.str


class FishingTableContext(BaseModel):
    """Context for fishing zone tables."""

    zone_key: _b.str
    rows: list[FishingRow]


__all__ = ["FishingRow", "FishingTableContext"]
