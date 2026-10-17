"""Generate default-rate special-roll selections before unique-item replacement."""

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
        "Independent special-roll selections from eligible loot tables, one row per item and roll, most likely first. "
        "Missing hosts and enemies destroyed on death or configured not to leave a corpse make no rolls. "
        "Chances are before owned unique items are replaced with common world items. "
        "An already-owned unique mask is not awarded again. "
        "Rolls can succeed together, so their chances must not be added to find the chance of any drop. "
        "Server loot-rate, top-guild and blessing bonuses affect other rolls, but not masks."
    ),
    entity="item",
    fields=(
        ViewField(
            "chance",
            "number",
            "Selection chance per eligible kill in percent, at the default loot rate without bonuses, "
            "before owned unique-item replacement.",
        ),
        ViewField(
            "minLevel",
            "integer",
            "The lowest eligible enemy level for the roll. 1 means no additional level gate.",
        ),
    ),
)


class WorldDropRepository(Protocol):
    """Repository method needed for the world drops view."""

    def get_all_special_world_drops(self) -> list[tuple[str, WorldDropInfo]]: ...


def build_world_drop_rows(drops: Iterable[tuple[str, WorldDropInfo]]) -> dict[str, list[dict[str, object]]]:
    """Return each item's rolls, most likely first.

    A roll selects its item from an eligible enemy strictly above its level
    gate. Ownership replacement happens later and is not represented here.
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
