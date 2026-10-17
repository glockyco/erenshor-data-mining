from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_lua.quests import quest_module_text, write_quests_module
from erenshor.application.wiki_lua.views import ViewDataError


def _rows() -> dict[str, list[dict[str, object]]]:
    return {
        "quest:offering": [
            {
                "type": "variant",
                "variant": "native-a",
                "experience": 10,
                "gold": 0,
                "repeatable": False,
                "oncePerSpawn": False,
                "partialAssigns": False,
                "killsHolder": False,
                "dropsInvulnerability": False,
            },
            {
                "type": "required",
                "variant": "native-a",
                "item": "item:token",
                "quantity": 3,
                "requiredSlot": 2,
            },
            {
                "type": "completion",
                "variant": "native-a",
                "method": "item_turnin",
                "source": "character:vendor",
                "sourceKind": "character",
                "item": "item:reward",
                "quantity": 1,
                "mechanic": "trade:slot:7",
                "acquisitionKey": "reward:slot:7",
            },
        ],
    }


_KEYS = {"quest:offering", "item:token", "item:reward", "character:vendor"}
_CATALOG = {key: {"name": key, "page": key} for key in _KEYS}


def test_quest_serializer_preserves_resource_slot_and_canonical_reward_identity(tmp_path: Path) -> None:
    rows = _rows()
    content = quest_module_text(rows, _KEYS, native_catalog=_CATALOG)
    assert '["requiredSlot"] = 2' in content
    assert '["mechanic"] = "trade:slot:7"' in content
    assert '["acquisitionKey"] = "reward:slot:7"' in content

    class Quests:
        def get_quest_panel_rows(self) -> dict[str, list[dict[str, object]]]:
            return rows

    assert (
        write_quests_module(Quests(), _KEYS, tmp_path, native_catalog=_CATALOG).read_text(encoding="utf-8") == content
    )


@pytest.mark.parametrize(("field", "value"), [("requiredSlot", "2"), ("mechanic", 7), ("acquisitionKey", 7)])
def test_canonical_identity_fields_retain_declared_types(field: str, value: object) -> None:
    rows = _rows()
    rows["quest:offering"][1 if field == "requiredSlot" else 2][field] = value
    with pytest.raises(ViewDataError, match=field):
        quest_module_text(rows, _KEYS, native_catalog=_CATALOG)


@pytest.mark.parametrize(
    ("field", "kind"),
    [
        ("source", "quest"),
        ("prerequisite", "quest"),
        ("notOwnedItem", "item"),
        ("blockedByQuest", "quest"),
        ("furniture", "item"),
        ("item", "item"),
        ("nextQuest", "quest"),
        ("unlocksItem", "item"),
        ("faction", "faction"),
        ("quest", "quest"),
    ],
)
def test_each_identity_field_retains_a_valid_pageless_native_reference(field: str, kind: str) -> None:
    rows = _rows()
    key = f"{kind}:native-pageless"
    rows["quest:offering"][0][field] = key
    if field == "source":
        rows["quest:offering"][0]["sourceKind"] = kind
    elif field == "furniture":
        rows["quest:offering"][0]["room"] = "L1"
    elif field == "item":
        rows["quest:offering"][0]["quantity"] = 1
    catalog = _CATALOG | {key: {"name": "Native label"}}
    content = quest_module_text(rows, _KEYS, native_catalog=catalog)
    assert f'["key"] = "{key}"' in content
    assert '["name"] = "Native label"' in content
    assert content.count('["page"]') == quest_module_text(_rows(), _KEYS, native_catalog=_CATALOG).count('["page"]')


def test_quest_references_reject_unknown_keys_and_wrong_native_kinds() -> None:
    rows = _rows()
    rows["quest:offering"][0]["nextQuest"] = "quest:unknown"
    with pytest.raises(ViewDataError, match="unknown native quest"):
        quest_module_text(rows, _KEYS, native_catalog=_CATALOG)
    rows["quest:offering"][0]["nextQuest"] = "item:token"
    with pytest.raises(ViewDataError, match="wrong kind"):
        quest_module_text(rows, _KEYS, native_catalog=_CATALOG)
