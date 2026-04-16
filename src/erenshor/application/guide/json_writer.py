"""JSON serialization for the compiled guide format."""

from __future__ import annotations

import dataclasses
import json
import math
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from .compiler import CompiledData


@overload
def _sanitize(obj: dict[str, Any]) -> dict[str, Any]: ...


@overload
def _sanitize(obj: list[Any]) -> list[Any]: ...


def _sanitize(obj: Any) -> Any:
    """Recursively replace NaN floats with None and sets with sorted lists."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {key: _sanitize(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(item) for item in obj]
    if isinstance(obj, set):
        return sorted(obj)
    return obj


def to_dict(compiled: CompiledData) -> dict[str, Any]:
    """Convert compiled data to a JSON-safe dictionary.

    NaN floats become ``None``; sets become sorted lists.
    """
    return _sanitize(dataclasses.asdict(compiled))


def serialize(compiled: CompiledData) -> str:
    """Serialize compiled data to a compact JSON string."""
    return json.dumps(to_dict(compiled), separators=(",", ":"))
