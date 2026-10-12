from __future__ import annotations

from erenshor.application.wiki_lua.world_drops import build_world_drop_rows
from erenshor.domain.value_objects.source_info import WorldDropInfo


def test_each_roll_shows_its_chance_and_the_lowest_enemy_level_that_makes_it() -> None:
    rows = build_world_drop_rows(
        [
            ("item:sivakrux", WorldDropInfo(probability=1.0, min_level_exclusive=10)),
            ("item:map", WorldDropInfo(probability=0.625, min_level_exclusive=0)),
            # An item that two rolls yield lists the likelier roll first.
            ("item:stone", WorldDropInfo(probability=0.05, min_level_exclusive=30)),
            ("item:stone", WorldDropInfo(probability=0.1, min_level_exclusive=15)),
        ]
    )

    assert rows == {
        "item:sivakrux": [{"chance": 1.0, "minLevel": 11}],
        "item:map": [{"chance": 0.625, "minLevel": 1}],
        "item:stone": [{"chance": 0.1, "minLevel": 16}, {"chance": 0.05, "minLevel": 31}],
    }
