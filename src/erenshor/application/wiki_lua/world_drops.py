"""Generate the world-drop view from canonical acquisition facts."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import TYPE_CHECKING, cast

from erenshor.application.wiki_lua.views import DataView, ViewField, view_module_text
from erenshor.domain.value_objects.item_provenance import PROVENANCE_SCHEMA_VERSION, fact_to_dict

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from pathlib import Path

    from erenshor.domain.value_objects.item_provenance import ItemAcquisition
    from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository

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


def _world_drop_row(fact: ItemAcquisition) -> dict[str, object] | None:
    if fact.kind != "special_world_drop":
        return None
    if fact.player_access_state != "verified_player" or fact.probability_stage != "final_acquisition":
        return None
    if any(condition.predicate == "never" for condition in fact.conditions):
        return None
    if fact.probability_max is not None and fact.probability_max <= 0:
        return None
    if fact.probability_kind != "exact" or fact.probability_min is None:
        raise ValueError(f"World-drop view needs an exact final chance: {fact.acquisition_key}")
    minimum = 1
    for condition in fact.conditions:
        if condition.predicate == "actor_level" and condition.actor == "enemy" and condition.minimum is not None:
            lower = math.ceil(condition.minimum) if condition.minimum_inclusive else math.floor(condition.minimum) + 1
            minimum = max(minimum, lower)
    return {"chance": fact.probability_min, "minLevel": minimum}


def build_world_drop_rows(drops: Iterable[ItemAcquisition]) -> dict[str, list[dict[str, object]]]:
    """Project each canonical final roll without merging distinct pool identities."""
    rolls: defaultdict[str, list[tuple[str, dict[str, object]]]] = defaultdict(list)
    for fact in drops:
        if (row := _world_drop_row(fact)) is not None:
            rolls[fact.item_stable_key].append((fact.acquisition_key, row))
    return {
        item_key: [
            row
            for _key, row in sorted(
                item_rolls,
                key=lambda roll: (-cast("float", roll[1]["chance"]), cast("int", roll[1]["minLevel"]), roll[0]),
            )
        ]
        for item_key, item_rolls in sorted(rolls.items())
    }


def world_drop_manifest(drops: Iterable[ItemAcquisition], known_keys: Collection[str]) -> dict[str, object]:
    """Retain exact pool facts offline, including facts the concise view cannot show."""
    records = []
    for fact in sorted(drops, key=lambda candidate: candidate.acquisition_key):
        if fact.kind != "special_world_drop":
            continue
        row = _world_drop_row(fact)
        reason = None
        if fact.item_stable_key not in known_keys:
            reason = "Item has no wiki link target."
        elif row is None:
            reason = "Only positive verified final-acquisition rolls appear in the public table."
        records.append(
            {
                "fact": fact_to_dict(fact),
                "row": row if reason is None else None,
                "not_presented_reason": reason,
                "concise_dimensions": (
                    "The public table shows chance and minimum enemy level. Full typed facts remain here."
                ),
            }
        )
    return {"schema_version": PROVENANCE_SCHEMA_VERSION, "acquisitions": records}


def validate_world_drop_manifest(
    drops: Iterable[ItemAcquisition],
    known_keys: Collection[str],
    manifest: dict[str, object],
) -> None:
    """Reject loss of pool identity, typed dimensions or presentation disposition offline."""
    expected = world_drop_manifest(drops, known_keys)
    if json.dumps(manifest, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("World-drop provenance coverage differs")


def write_world_drops_module(
    repo: ItemProvenanceRepository,
    known_keys: Collection[str],
    output_root: Path,
) -> Path:
    """Write the public view and its offline, lossless provenance manifest."""
    drops = tuple(repo.iter_acquisitions())
    rows = {key: rows for key, rows in build_world_drop_rows(drops).items() if key in known_keys}
    output_path = output_root / "Erenshor" / "Data" / "WorldDrops.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    module = view_module_text(WORLD_DROPS, rows, known_keys)
    manifest_data = world_drop_manifest(drops, known_keys)
    validate_world_drop_manifest(drops, known_keys, manifest_data)
    output_path.write_text(module, encoding="utf-8")
    manifest = output_root / "world-drops-provenance.json"
    manifest.write_text(json.dumps(manifest_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
