from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.wiki_lua.game_board import build_game_board_rows, write_game_board_module
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ProvenanceCondition,
)


def _spawn(**values: object) -> dict[str, object]:
    return {
        "copy": "character:board-copy",
        "character": "character:boss",
        "piece": "item:piece",
        "level": 34,
        "levelMod": 0,
        "group": False,
        "scales": False,
        **values,
    }


def _drop(**values: object) -> ItemAcquisition:
    return replace(
        ItemAcquisition(
            "drop:board",
            "item:reward",
            "character_drop",
            "character:boss",
            source_group_key="character:boss",
            source_copy_stable_key="character:board-copy",
            probability_kind="exact",
            probability_min=12.5,
            probability_max=12.5,
            probability_basis="per_kill",
        ),
        **values,
    )


CATALOG: dict[str, dict[str, object]] = {
    "item:piece": {"name": "Piece", "page": "Piece"},
    "item:other-piece": {"name": "Other piece", "page": "Other piece"},
    "item:reward": {"name": "Reward", "page": "Reward"},
}
DISPOSITIONS = {"item:reward": ItemDisposition("item:reward", "current")}


def test_only_exact_spawned_copy_supplies_drops_not_its_group_or_page() -> None:
    rows = build_game_board_rows(
        [_spawn()],
        [
            _drop(source_copy_stable_key="character:unplaced-backup", probability_min=99, probability_max=99),
            _drop(source_group_key="character:other-group", probability_min=12.5, probability_max=12.5),
            _drop(kind="common_world_item", probability_min=50, probability_max=50),
            _drop(kind="special_world_drop", probability_min=75, probability_max=75),
        ],
        DISPOSITIONS,
        CATALOG,
    )["character:boss"]
    assert len(rows) == 1
    assert rows[0]["copy"] == "character:board-copy"
    assert rows[0]["chance"] == 12.5


@pytest.mark.parametrize(
    "fact",
    [
        _drop(player_access_state="non_acquirable"),
        _drop(player_access_state="internal_only"),
        _drop(player_access_state="unconfirmed_player"),
        _drop(probability_stage="native_pool"),
        _drop(probability_min=0, probability_max=0),
        _drop(conditions=(ProvenanceCondition("impossible", 0, 0, "never"),)),
    ],
)
def test_unavailable_canonical_facts_do_not_become_obtainable_board_drops(fact: ItemAcquisition) -> None:
    rows = build_game_board_rows([_spawn()], [fact], DISPOSITIONS, CATALOG)["character:boss"]
    assert len(rows) == 1
    assert "drop" not in rows[0] and "chance" not in rows[0]


@pytest.mark.parametrize("state", ["removed", "unobtainable", "unused"])
def test_noncurrent_item_dispositions_are_not_presented_as_drops(state: str) -> None:
    rows = build_game_board_rows(
        [_spawn()], [_drop()], {"item:reward": ItemDisposition("item:reward", state)}, CATALOG
    )["character:boss"]
    assert "drop" not in rows[0]


def test_copy_piece_and_effective_level_boundaries_remain_alternative_rows() -> None:
    rows = build_game_board_rows(
        [
            _spawn(),
            _spawn(),
            _spawn(piece="item:other-piece", levelMod=1),
            _spawn(copy="character:second-board-copy", level=40),
        ],
        [
            _drop(),
            _drop(
                acquisition_key="drop:second",
                source_copy_stable_key="character:second-board-copy",
                probability_min=75,
                probability_max=75,
            ),
        ],
        DISPOSITIONS,
        CATALOG,
    )["character:boss"]
    assert len(rows) == 3
    assert {(row["copy"], row["piece"]["key"], row["levelMin"], row["levelMax"], row["chance"]) for row in rows} == {
        ("character:board-copy", "item:piece", 33, 35, 12.5),
        ("character:board-copy", "item:other-piece", 35, 35, 12.5),
        ("character:second-board-copy", "item:piece", 40, 40, 75),
    }


@pytest.mark.parametrize("piece", [None, "item:unknown"])
def test_missing_or_unknown_piece_fails_instead_of_inventing_an_identity(piece: object) -> None:
    with pytest.raises(ValueError, match=r"summoning piece|unknown native item"):
        build_game_board_rows([_spawn(piece=piece)], [], {}, CATALOG)


def test_conflicting_same_copy_chances_are_not_summed_or_selected() -> None:
    with pytest.raises(ValueError, match="conflicting drop chances"):
        build_game_board_rows(
            [_spawn()],
            [_drop(), _drop(acquisition_key="drop:other", probability_min=50, probability_max=50)],
            DISPOSITIONS,
            CATALOG,
        )


def test_new_boss_enters_from_bindings_without_a_class_or_name_override() -> None:
    rows = build_game_board_rows([_spawn(character="character:new-class-boss")], [_drop()], DISPOSITIONS, CATALOG)
    assert list(rows) == ["character:new-class-boss"]
    assert rows["character:new-class-boss"][0]["chance"] == 12.5


def test_pageless_native_items_keep_labels_without_invented_links() -> None:
    catalog = dict(CATALOG, **{"item:reward": {"name": "Native reward"}})
    rows = build_game_board_rows([_spawn()], [_drop()], DISPOSITIONS, catalog)
    assert rows["character:boss"][0]["drop"] == {"key": "item:reward", "name": "Native reward"}


def test_writer_rejects_a_page_backed_item_missing_from_links_before_writing(tmp_path: Path) -> None:
    class Repository:
        def get_game_board_spawns(self) -> list[dict[str, object]]:
            return [_spawn()]

    class Provenance:
        def get_character_drop_acquisitions(self, character_copy_keys: Iterable[str]) -> list[ItemAcquisition]:
            return [_drop()]

        def get_disposition(self, item_key: str) -> ItemDisposition | None:
            return DISPOSITIONS.get(item_key)

    with pytest.raises(ValueError, match="link catalog"):
        write_game_board_module(
            Repository(), Provenance(), {"character:boss", "item:piece"}, tmp_path, reference_catalog=CATALOG
        )
    assert not list(tmp_path.rglob("*.lua"))
