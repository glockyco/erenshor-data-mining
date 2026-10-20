"""Persisted progression graph records shared by producers and readers."""

from __future__ import annotations

from dataclasses import dataclass

PROGRESSION_SCHEMA_VERSION = 4
# A need with one of these relations holds while its target is not done. The
# target is no prerequisite, so it adds no tier and no step to a first-way route.
UNMET_RELATIONS = frozenset({"quest not done"})


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
