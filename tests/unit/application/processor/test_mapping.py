from __future__ import annotations

import json
from pathlib import Path

import pytest

from erenshor.application.processor.mapping import (
    MappingOverride,
    load_mapping,
    validate_character_name_overrides,
)


def _override(*, display_name: str, expected_npc_name: str | None) -> MappingOverride:
    return MappingOverride(
        display_name=display_name,
        wiki_page_name=display_name,
        image_name=display_name,
        expected_npc_name=expected_npc_name,
        is_wiki_generated=1,
        is_map_visible=1,
        encounter_tier=None,
        loot_unreachable=False,
    )


def test_load_mapping_preserves_expected_npc_name(tmp_path: Path) -> None:
    path = tmp_path / "mapping.json"
    path.write_text(
        json.dumps(
            {
                "rules": {
                    "character:guard": {
                        "display_name": "Fire Guard",
                        "wiki_page_name": "Fire Guard",
                        "image_name": "Fire Guard",
                        "expected_npc_name": "Guard",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    mapping, _ = load_mapping(path)

    assert mapping["character:guard"]["expected_npc_name"] == "Guard"


def test_matching_game_name_needs_no_pin() -> None:
    mapping = {"character:guard": _override(display_name="Guard", expected_npc_name=None)}

    validate_character_name_overrides(mapping, {"character:guard": "Guard"})


def test_pinned_intentional_rename_is_valid() -> None:
    mapping = {"character:guard": _override(display_name="Fire Guard", expected_npc_name="Guard")}

    validate_character_name_overrides(mapping, {"character:guard": "Guard"})


def test_unpinned_display_name_override_is_rejected() -> None:
    mapping = {"character:guard": _override(display_name="Fire Guard", expected_npc_name=None)}

    with pytest.raises(ValueError, match="without 'expected_npc_name'"):
        validate_character_name_overrides(mapping, {"character:guard": "Guard"})


def test_changed_pinned_game_name_is_rejected() -> None:
    mapping = {"character:guard": _override(display_name="Fire Guard", expected_npc_name="Guard")}

    with pytest.raises(ValueError, match="expected NPCName 'Guard', found 'Arcanist'"):
        validate_character_name_overrides(mapping, {"character:guard": "Arcanist"})


def _write_rule(tmp_path: Path, **fields: object) -> Path:
    path = tmp_path / "mapping.json"
    rule = {"display_name": "Catnip", "wiki_page_name": "Catnip", "image_name": "Catnip", **fields}
    path.write_text(json.dumps({"rules": {"character:catnip": rule}}))
    return path


def test_encounter_tier_override_is_loaded(tmp_path: Path) -> None:
    characters, _ = load_mapping(_write_rule(tmp_path, encounter_tier="enemy", reason="Killed for a quest item."))

    assert characters["character:catnip"]["encounter_tier"] == "enemy"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"encounter_tier": "rare", "reason": "x"}, "must be one of"),
        ({"encounter_tier": "enemy"}, "requires a 'reason'"),
    ],
)
def test_invalid_encounter_tier_override_is_rejected(tmp_path: Path, fields: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_mapping(_write_rule(tmp_path, **fields))


def test_unreachable_loot_requires_a_reason(tmp_path: Path) -> None:
    characters, _ = load_mapping(_write_rule(tmp_path, loot_unreachable=True, reason="Destroyed by its fight."))
    assert characters["character:catnip"]["loot_unreachable"] is True

    with pytest.raises(ValueError, match="'loot_unreachable' requires a 'reason'"):
        load_mapping(_write_rule(tmp_path, loot_unreachable=True))


def test_a_stance_rule_cannot_set_the_image(tmp_path: Path) -> None:
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"rules": {"stance:normal": {"display_name": "Normal", "wiki_page_name": "Normal"}}}))
    rules, _ = load_mapping(path)
    assert rules["stance:normal"]["image_name"] is None

    path.write_text(json.dumps({"rules": {"stance:normal": {"display_name": "Normal", "image_name": "Normal"}}}))
    with pytest.raises(ValueError, match="must not set 'image_name'"):
        load_mapping(path)
