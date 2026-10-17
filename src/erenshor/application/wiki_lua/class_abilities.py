"""Generate abilities learned from items, using the player's item-learning gates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.views import DataView, ViewField, view_module_text
from erenshor.domain.value_objects.item_provenance import is_actionable_acquisition

if TYPE_CHECKING:
    from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository

CLASS_ABILITIES = DataView(
    module="ClassAbilities",
    description="Abilities taught by obtainable wiki-visible items, sorted by required level and ability key.",
    entity="class",
    fields=(
        ViewField("ability", "key", "The spell or skill learned."),
        ViewField(
            "level",
            "integer",
            "The spell's required level or the skill's class-specific level. "
            "Non-positive spell levels mean no minimum.",
        ),
        ViewField("items", "keys", "Obtainable teaching items usable by this class, including alternatives."),
    ),
)


class ClassAbilityRepository(Protocol):
    def get_class_ability_teachers(self) -> list[dict[str, object]]: ...


def build_class_ability_rows(
    teachers: list[dict[str, object]], provenance_repo: ItemProvenanceRepository
) -> dict[str, list[dict[str, object]]]:
    """Fold alternate books and scrolls without using spell class flags as learning gates."""
    items: defaultdict[tuple[str, str, int], set[str]] = defaultdict(set)
    for teacher in teachers:
        if provenance_repo.get_player_access(str(teacher["item"])) != "verified_player":
            continue
        acquisitions = provenance_repo.get_acquisitions(str(teacher["item"]))
        if not any(is_actionable_acquisition(fact) for fact in acquisitions):
            continue
        items[str(teacher["class"]), str(teacher["ability"]), int(str(teacher["level"]))].add(str(teacher["item"]))
    rows: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for (class_key, ability, level), teaching_items in sorted(
        items.items(), key=lambda entry: (entry[0][2], entry[0][1])
    ):
        rows[class_key].append({"ability": ability, "level": level, "items": sorted(teaching_items)})
    return dict(rows)


def write_class_abilities_module(
    repo: ClassAbilityRepository,
    provenance_repo: ItemProvenanceRepository,
    known_keys: Collection[str],
    output_root: Path,
) -> Path:
    """Write the checked class ability view below an output root."""
    rows = build_class_ability_rows(repo.get_class_ability_teachers(), provenance_repo)
    path = output_root / "Erenshor" / "Data" / "ClassAbilities.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(view_module_text(CLASS_ABILITIES, rows, known_keys), encoding="utf-8")
    return path
