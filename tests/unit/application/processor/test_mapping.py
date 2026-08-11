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
