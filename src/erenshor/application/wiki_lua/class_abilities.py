"""Generate abilities learned from items, using the player's item-learning gates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.views import DataView, ViewField, view_module_text

if TYPE_CHECKING:
    from erenshor.infrastructure.database.repositories.item_public_view import ItemPublicViewRepository

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
    teachers: list[dict[str, object]], public_view: ItemPublicViewRepository
) -> dict[str, list[dict[str, object]]]:
    """Fold alternate books and scrolls without using spell class flags as learning gates."""
    items: defaultdict[tuple[str, str, int], set[str]] = defaultdict(set)
    for teacher in teachers:
        key = str(teacher["item"])
        status = public_view.status(key)
        if status is None or status.disposition != "current" or not public_view.sources_for_item(key):
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
    public_view: ItemPublicViewRepository,
    known_keys: Collection[str],
    output_root: Path,
) -> Path:
    """Write the checked class ability view below an output root."""
    rows = build_class_ability_rows(repo.get_class_ability_teachers(), public_view)
    path = output_root / "Erenshor" / "Data" / "ClassAbilities.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(view_module_text(CLASS_ABILITIES, rows, known_keys), encoding="utf-8")
    return path
