from __future__ import annotations

from dataclasses import asdict, replace

import pytest
from tests.unit.application.wiki_lua.fakes import public_source

from erenshor.application.wiki_lua.world_drops import (
    build_world_drop_rows,
    validate_world_drop_manifest,
    world_drop_manifest,
)
from erenshor.domain.value_objects.item_public_view import PublicCondition, PublicSource


def _drop(key: str, item: str, chance: float, level: int = 0) -> PublicSource:
    return public_source(
        key,
        item,
        "special_world_drop",
        None,
        variant_key=key,
        probability_kind="exact",
        probability_min=chance,
        probability_max=chance,
        probability_basis="per_kill",
        conditions=(
            PublicCondition(
                0, 0, 0, "enemy_level", "actor_level", actor="enemy", minimum=level, minimum_inclusive=False
            ),
        ),
    )


def test_each_roll_shows_its_final_chance_and_lowest_enemy_level() -> None:
    rows = build_world_drop_rows(
        [
            _drop("roll:sivakrux", "item:sivakrux", 1.0, 10),
            _drop("roll:map", "item:map", 0.625),
            _drop("roll:stone1", "item:stone", 0.05, 30),
            _drop("roll:stone2", "item:stone", 0.1, 15),
        ]
    )
    assert rows == {
        "item:sivakrux": [{"chance": 1.0, "minLevel": 11}],
        "item:map": [{"chance": 0.625, "minLevel": 1}],
        "item:stone": [{"chance": 0.1, "minLevel": 16}, {"chance": 0.05, "minLevel": 31}],
    }


def test_distinct_equal_chance_pools_keep_independent_rows_and_offline_identities() -> None:
    drops = [_drop("roll:first", "item:stone", 0.05), _drop("roll:second", "item:stone", 0.05)]
    assert len(build_world_drop_rows(drops)["item:stone"]) == 2
    manifest = world_drop_manifest(drops, {"item:stone"})
    assert [row["fact"] for row in manifest["acquisitions"]] == [asdict(fact) for fact in drops]


def test_unlinked_public_source_remains_in_manifest() -> None:
    drops = [_drop("roll:unlinked", "item:hidden", 1)]
    manifest = world_drop_manifest(drops, {"item:stone"})
    assert manifest["acquisitions"][0]["not_presented_reason"]
    assert manifest["acquisitions"][0]["fact"] == asdict(drops[0])


def test_unknown_final_probability_fails_instead_of_inventing_a_chance() -> None:
    fact = replace(_drop("roll:unknown", "item:stone", 1), probability_kind="unknown", probability_min=None)
    with pytest.raises(ValueError, match="exact final chance"):
        build_world_drop_rows([fact])


@pytest.mark.parametrize("dimension", ["conditions", "variant_key", "probability_min"])
def test_world_drop_manifest_rejects_lost_dimensions(dimension: str) -> None:
    fact = _drop("roll:map", "item:map", 0.625)
    manifest = world_drop_manifest([fact], {"item:map"})
    del manifest["acquisitions"][0]["fact"][dimension]
    with pytest.raises(ValueError, match="coverage differs"):
        validate_world_drop_manifest([fact], {"item:map"}, manifest)
