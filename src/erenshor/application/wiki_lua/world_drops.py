"""Generate the world drops view: what any kill of a character with a loot table can roll."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.views import DataView, ViewField, view_module_text

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from pathlib import Path

    from erenshor.domain.value_objects.source_info import WorldDropInfo

WORLD_DROPS = DataView(
    module="WorldDrops",
    description=(
        "The items that a special world drop roll yields, which every kill of a character with a loot table "
        "makes, one row for each roll, most likely first."
    ),
    entity="item",
    fields=(
        ViewField("chance", "number", "The chance per kill in percent, at the default loot rate."),
        ViewField(
            "minLevel",
            "integer",
            "The lowest level of an enemy whose kill makes the roll. 1 when every enemy makes it.",
        ),
    ),
)


class WorldDropRepository(Protocol):
    """Repository method needed for the world drops view."""

    def get_all_special_world_drops(self) -> list[tuple[str, WorldDropInfo]]: ...


def build_world_drop_rows(drops: Iterable[tuple[str, WorldDropInfo]]) -> dict[str, list[dict[str, object]]]:
    """Return each item's rolls, most likely first.

    A roll yields its item from an enemy above its level gate, so the lowest
    enemy level is one above the gate.
    """
    rolls: defaultdict[str, list[tuple[float, int]]] = defaultdict(list)
    for item_key, drop in drops:
        rolls[item_key].append((drop.probability, drop.min_level_exclusive + 1))
    return {
        item_key: [
            {"chance": chance, "minLevel": min_level}
            for chance, min_level in sorted(item_rolls, key=lambda roll: (-roll[0], roll[1]))
        ]
        for item_key, item_rolls in rolls.items()
    }


def write_world_drops_module(repo: WorldDropRepository, known_keys: Collection[str], output_root: Path) -> Path:
    """Write ``Data/WorldDrops.lua`` below an output root."""
    rows = build_world_drop_rows(repo.get_all_special_world_drops())
    output_path = output_root / "Erenshor" / "Data" / "WorldDrops.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(view_module_text(WORLD_DROPS, rows, known_keys), encoding="utf-8")
    return output_path
