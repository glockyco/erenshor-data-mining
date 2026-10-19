"""Player wording shared by progression readers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.value_objects.progression import ProgressionNode

WORDING = {
    "event:": "Scripted event",
    "release:health_phase_timer:": "Becomes vulnerable after a health phase timer",
    "release:spawn_health_phase_timer:": "Becomes vulnerable after a spawn health phase timer",
    "release:combat_empty_wards:": "Becomes vulnerable in combat when no wards remain",
    "mechanic:new_character_start": "New character start",
    "mechanic:alternate_start": "Alternate start",
    "mechanic:common_world_item": "Common world items",
    "mechanic:special_world_drop": "World drops",
    "ui:planningtableui": "Planning table",
    "ui:replenishtmoghide": "Cosmetic slot",
    "barrier": "{name}",
    "account_state:reliquary_claimed:false": "Reliquary not claimed by this account",
    "account_state:reliquary_claimed:true": "Reliquary claimed by this account",
    "world_state:weather:raining:": "Rain in {name}",
    "weather:natural_rain": "Wait for natural rain",
    "faction_standing:positive": "Positive standing with {name}",
    "faction_standing:non_negative": "Standing of zero or more with {name}",
}


class ProgressionWordingError(ValueError):
    """A typed progression key has no player wording."""


def condition_text(key: str) -> str:
    """Word a supported condition family and reject unknown keys."""
    if key == "weather:natural_rain":
        return WORDING[key]
    for prefix in (
        "event:",
        "release:health_phase_timer:",
        "release:spawn_health_phase_timer:",
        "release:combat_empty_wards:",
    ):
        if key.startswith(prefix) and key.removeprefix(prefix):
            return WORDING[prefix]
    raise ProgressionWordingError(f"Cannot word progression condition: {key!r}")


def standing_text(key: str, names: Mapping[str, str]) -> str:
    """Word a faction standing by the name of its faction."""
    faction, _, required = key.removeprefix("faction_standing:").rpartition(":")
    template = WORDING.get("faction_standing:" + required)
    name = names.get("faction:" + faction)
    if template is None or not name:
        raise ProgressionWordingError(f"Cannot word progression faction standing: {key!r}")
    return template.format(name=name)


def node_text(node: ProgressionNode, names: Mapping[str, str]) -> str:
    """Word a noncatalog node without substituting a raw stable key."""
    key = node.stable_key
    if key in WORDING:
        return WORDING[key]
    if node.kind == "barrier" and node.name != key:
        return WORDING["barrier"].format(name=node.name)
    if node.kind == "world_state" and key.startswith("world_state:weather:raining:"):
        zone = key.removeprefix("world_state:weather:raining:")
        if zone in names:
            return WORDING["world_state:weather:raining:"].format(name=names[zone])
    if node.kind == "faction_standing":
        return standing_text(key, names)
    if node.kind == "mechanism" and key.startswith("ui:"):
        parts = key.rsplit(":", 2)
        wording_key = "ui:" + parts[-2] if len(parts) == 3 else key
        if wording_key in WORDING:
            return WORDING[wording_key]
    raise ProgressionWordingError(f"Cannot word progression {node.kind}: {key!r}")
