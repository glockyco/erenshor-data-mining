from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeItemProvenanceRepository

from erenshor.application.wiki_lua.class_abilities import build_class_ability_rows, write_class_abilities_module
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemDisposition


def _acquisition(item: str, identity: str) -> ItemAcquisition:
    return ItemAcquisition(
        identity,
        item,
        "vendor",
        "character:vendor",
        probability_stage="final_acquisition",
    )


def test_alternative_teaching_items_fold_by_class_ability_and_required_level(tmp_path: Path) -> None:
    teachers = [
        {"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:a"},
        {"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:b"},
        {"class": "class:knight", "ability": "spell:ice", "level": 4, "item": "item:a"},
    ]
    provenance = FakeItemProvenanceRepository(
        ["item:a", "item:b"],
        acquisitions=[_acquisition("item:a", "offer:a"), _acquisition("item:b", "offer:b")],
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


@pytest.mark.parametrize("defect", ["removed", "unconfirmed", "internal", "native_pool", "zero", "missing"])
def test_only_current_verified_final_acquisitions_advertise_teaching_items(defect: str) -> None:
    acquisition = _acquisition("item:a", "offer:a")
    dispositions = [ItemDisposition("item:a", "removed" if defect == "removed" else "current")]
    if defect == "unconfirmed":
        acquisition = replace(acquisition, player_access_state="unconfirmed_player")
    elif defect == "internal":
        acquisition = replace(acquisition, player_access_state="internal_only")
    elif defect == "native_pool":
        acquisition = replace(acquisition, probability_stage="native_pool")
    elif defect == "zero":
        acquisition = replace(acquisition, probability_kind="exact", probability_min=0, probability_max=0)
    provenance = FakeItemProvenanceRepository(
        ["item:a"],
        acquisitions=[] if defect == "missing" else [acquisition],
        dispositions=dispositions,
    )
    teachers = [{"class": "class:knight", "ability": "spell:fire", "level": 10, "item": "item:a"}]
    assert build_class_ability_rows(teachers, provenance) == {}
