"""Publish reviewed non-item lifecycle facts as an immutable narrow supplement."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.infrastructure.content_lifecycle import ContentLifecycle

_ENTITY_PREFIXES = ("stance:", "spell:", "skill:")


def build_entity_lifecycle_data(lifecycle: ContentLifecycle) -> dict[str, object]:
    """Serialize exact keyed facts, excluding item dispositions and unkeyed pages."""
    entities: dict[str, dict[str, str]] = {}
    for title, fact in sorted(lifecycle.pages.items()):
        key = fact.stable_key
        if key is None or not key.startswith(_ENTITY_PREFIXES):
            continue
        record = {"state": fact.state, "thing": fact.thing}
        for field, value in (("update", fact.update), ("date", fact.date), ("url", fact.patch_notes_url)):
            if value is not None:
                record[field] = value
        previous = entities.get(key)
        if previous is not None and previous != record:
            raise ValueError(f"{title}: contradictory lifecycle facts for {key}")
        entities[key] = record
    return {"entities": dict(sorted(entities.items()))}


def generate_entity_lifecycle_module(lifecycle: ContentLifecycle) -> str:
    """Generate Module:Erenshor/Data/EntityLifecycle from validated facts."""
    return module_text(build_entity_lifecycle_data(lifecycle))


def write_entity_lifecycle_module(lifecycle: ContentLifecycle, output_root: Path) -> Path:
    """Write the supplement through the native generated-data publication path."""
    path = output_root / "Erenshor" / "Data" / "EntityLifecycle.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_entity_lifecycle_module(lifecycle), encoding="utf-8")
    return path
