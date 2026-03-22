"""Schema-driven JSON serialization for quest guides.

Converts dataclass instances to dicts with clean omission rules:
- None values: omitted (optional field not present)
- Empty lists/dicts: omitted (no data, not "zero items")
- Present values including 0, False, "": always serialized
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import QuestGuide


def guides_to_json(guides: list[QuestGuide]) -> list[dict]:
    """Convert QuestGuide list to JSON-serializable dicts."""
    return [_clean(asdict(g)) for g in guides]


def _clean(obj: object) -> object:
    """Recursively clean a value for JSON serialization.

    Dicts: recurse values, omit keys whose cleaned value is None or empty collection.
    Lists: recurse elements, omit the list itself if empty.
    Primitives: pass through unchanged.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            cleaned = _clean(v)
            # Omit None (absent optional) and empty collections (no data)
            if cleaned is None:
                continue
            if isinstance(cleaned, (list, dict)) and not cleaned:
                continue
            result[k] = cleaned
        return result
    if isinstance(obj, list):
        return [_clean(item) for item in obj]
    return obj
