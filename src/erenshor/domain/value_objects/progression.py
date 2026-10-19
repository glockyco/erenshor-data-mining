"""Persisted progression graph records shared by producers and readers."""

from __future__ import annotations

from dataclasses import dataclass

PROGRESSION_SCHEMA_VERSION = 4


@dataclass(frozen=True)
class ProgressionNode:
    stable_key: str
    kind: str
    name: str
    is_milestone: bool
    tier: int | None
    first_way_key: str | None


@dataclass(frozen=True)
class ProgressionNeed:
    relation: str
    need_stable_key: str | None
    quantity: float | None
    slot: str | None
    keywords: str | None
    condition_key: str | None
    advisory: bool
    unconfirmed: bool
    required_level: int | None = None


@dataclass(frozen=True)
class ProgressionWay:
    way_key: str
    needs: tuple[ProgressionNeed, ...]
