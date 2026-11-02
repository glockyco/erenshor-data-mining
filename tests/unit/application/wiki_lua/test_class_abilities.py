from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.unit.application.wiki_lua.fakes import FakeItemPublicViewRepository, public_source

from erenshor.application.wiki_lua.class_abilities import build_class_ability_rows, write_class_abilities_module

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_public_view import PublicSource


def _source(item: str, identity: str) -> PublicSource:
    return public_source(identity, item, "vendor", "character:vendor")


def test_alternative_teaching_items_fold_by_class_ability_and_required_level(tmp_path: Path) -> None:
    teachers = [
        {"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:a"},
        {"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:b"},
        {"class": "class:knight", "ability": "spell:ice", "level": 4, "item": "item:a"},
    ]
    provenance = FakeItemPublicViewRepository(
        ["item:a", "item:b"],
        sources=[_source("item:a", "offer:a"), _source("item:b", "offer:b")],
    )
    assert build_class_ability_rows(teachers, provenance) == {
        "class:knight": [
            {"ability": "spell:ice", "level": 4, "items": ["item:a"]},
            {"ability": "spell:fire", "level": 10, "items": ["item:a", "item:b"]},
        ]
    }

    class Teachers:
        def get_class_ability_teachers(self) -> list[dict[str, object]]:
            return teachers

    path = write_class_abilities_module(
        Teachers(),
        provenance,
        {"class:knight", "spell:fire", "spell:ice", "item:a", "item:b"},
        tmp_path,
    )
    assert '"item:b"' in path.read_text(encoding="utf-8")


def test_an_item_without_a_public_source_is_not_advertised_as_a_teaching_item() -> None:
    provenance = FakeItemPublicViewRepository(["item:a"])
    teachers = [{"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:a"}]
    assert build_class_ability_rows(teachers, provenance) == {}
