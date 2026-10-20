from __future__ import annotations

import json
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeProgressionRepository

from erenshor.application.wiki_lua.progression import (
    build_progression_data,
    compact_progression_data,
    write_progression_module,
)
from erenshor.application.wiki_lua.views import ViewDataError
from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode, ProgressionWay


@pytest.fixture
def graph() -> FakeProgressionRepository:
    return FakeProgressionRepository(
        (
            ProgressionNode("quest:goal", "quest", "Goal", True, 2, "complete"),
            ProgressionNode("quest_start:quest:goal", "quest_start", "Start", False, 1, "start"),
            ProgressionNode("item:key", "item", "Key", False, None, None),
            ProgressionNode("mechanic:new_character_start", "mechanism", "Start", False, 0, "initial"),
        ),
        {
            "quest:goal": (
                ProgressionWay(
                    "complete",
                    (
                        ProgressionNeed("required item", "item:key", 2.5, "L1", "hello", None, True, True),
                        ProgressionNeed(
                            "condition", None, None, None, None, "release:combat_empty_wards:copy", False, False
                        ),
                    ),
                ),
                ProgressionWay("alternative", ()),
            ),
            "quest_start:quest:goal": (ProgressionWay("start", ()),),
            "mechanic:new_character_start": (ProgressionWay("initial", ()),),
        },
    )


@pytest.fixture
def catalog() -> dict[str, dict[str, object]]:
    return {"quest:goal": {"name": "Goal", "page": "Goal"}, "item:key": {"name": "Key"}}


def test_rows_preserve_nodes_alternative_empty_ways_and_all_need_fields(graph, catalog):
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert (data.node_count, data.way_count, data.need_count) == (4, 4, 2)
    assert list(data.rows) == sorted(node.stable_key for node in graph.nodes)
    node, alternative, way, required, condition = data.rows["quest:goal"]
    assert node == {
        "type": "node",
        "kind": "quest",
        "tier": 2,
        "milestone": True,
        "label": {"key": "quest:goal", **catalog["quest:goal"]},
    }
    assert alternative == {"type": "way", "way": "alternative", "first": False}
    assert way == {"type": "way", "way": "complete", "first": True}
    assert required == {
        "type": "need",
        "way": "complete",
        "relation": "required item",
        "need": "item:key",
        "quantity": 2.5,
        "slot": "L1",
        "keywords": "hello",
        "advisory": True,
        "unconfirmed": True,
    }
    assert condition.keys() == {"type", "way", "relation", "text"}
    assert isinstance(condition["text"], str) and condition["text"]
    assert "tier" not in data.rows["item:key"][0]
    assert data.rows["quest_start:quest:goal"][0]["label"] == node["label"]
    assert data.rows["mechanic:new_character_start"][1] == {"type": "way", "way": "initial", "first": True}


def test_unknown_condition_names_module_node_way_and_fact(graph, catalog):
    need = ProgressionNeed("condition", None, None, None, None, "new:unworded", False, False)
    graph.ways["quest:goal"] = (ProgressionWay("complete", (need,)),)
    with pytest.raises(ViewDataError) as error:
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert all(
        value in str(error.value)
        for value in ("Module:Erenshor/Data/Progression", "quest:goal", "complete", "new:unworded")
    )


@pytest.mark.parametrize("failure", ["node", "need", "mechanism"])
def test_unknown_identities_fail_closed(graph, catalog, failure):
    if failure == "node":
        del catalog["item:key"]
    elif failure == "need":
        original = graph.ways["quest:goal"][0].needs[0]
        graph.ways["quest:goal"] = (ProgressionWay("complete", (replace(original, need_stable_key="item:missing"),)),)
    else:
        graph.nodes += (ProgressionNode("mechanic:unknown", "mechanism", "Unknown", False, None, None),)
        graph.ways["mechanic:unknown"] = (ProgressionWay("available", ()),)
    with pytest.raises(ViewDataError):
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)


def test_a_way_that_needs_its_own_node_is_left_out(graph, catalog):
    held = ProgressionNeed("held", "quest:goal", None, None, None, None, False, False)
    graph.ways["quest:goal"] += (ProgressionWay("circular", (held,)),)
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert [row["way"] for row in data.rows["quest:goal"] if row["type"] == "way"] == ["alternative", "complete"]
    assert data.circular_ways == 1
    graph.ways["quest:goal"] = (ProgressionWay("complete", (held,)),)
    with pytest.raises(ViewDataError, match="missing first way complete"):
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)


@pytest.mark.parametrize("field", ["slot", "keywords", "label"])
def test_markup_is_rejected_in_all_player_text(graph, catalog, field):
    if field == "label":
        catalog["quest:goal"]["name"] = "[[Unsafe]]"
    else:
        original = graph.ways["quest:goal"][0].needs[0]
        graph.ways["quest:goal"] = (ProgressionWay("complete", (replace(original, **{field: "[[Unsafe]]"}),)),)
    with pytest.raises(ViewDataError, match="wiki markup"):
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)


def test_writer_checks_budget_before_touching_existing_output(graph, catalog, tmp_path: Path):
    path = tmp_path / "Erenshor" / "Data" / "Progression.lua"
    path.parent.mkdir(parents=True)
    path.write_text("previous")
    with pytest.raises(ViewDataError, match="Page budget"):
        write_progression_module(graph, {"quest:goal"}, tmp_path, native_catalog=catalog, max_page_bytes=1)
    assert path.read_text() == "previous"
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert (
        write_progression_module(
            graph, {"quest:goal"}, tmp_path, native_catalog=catalog, max_page_bytes=data.module_bytes
        )
        == path
    )
    assert path.read_text() == data.content


def test_input_order_does_not_change_module_bytes(graph, catalog):
    first = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    graph.nodes = tuple(reversed(graph.nodes))
    graph.ways = {key: tuple(reversed(ways)) for key, ways in reversed(graph.ways.items())}
    second = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert first.content == second.content
    assert first.json_bytes == second.json_bytes


@pytest.mark.parametrize(
    ("key", "kind", "name"),
    [
        ("door:zone:1:2:3", "barrier", "Door in Bay"),
        ("account_state:reliquary_claimed:true", "account_state", "unused"),
        ("account_state:reliquary_claimed:false", "account_state", "unused"),
        ("world_state:weather:raining:zone:bay", "world_state", "unused"),
        ("ui:scene:path:planningtableui:0", "mechanism", "unused"),
    ],
)
def test_noncatalog_nodes_have_native_labels_without_fabricated_pages(graph, catalog, key, kind, name):
    graph.nodes += (ProgressionNode(key, kind, name, False, None, None),)
    graph.ways[key] = (ProgressionWay("available", ()),)
    catalog["zone:bay"] = {"name": "Bay"}
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    label = data.rows[key][0]["label"]
    assert isinstance(label, dict)
    assert label["key"] == key
    assert isinstance(label["name"], str) and label["name"]
    assert "page" not in label


def test_native_identity_outside_links_keeps_its_label_but_not_an_article(graph, catalog):
    catalog["item:key"]["page"] = "Excluded article"
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert data.rows["item:key"][0]["label"] == {"key": "item:key", "name": "Key"}


def test_empty_native_label_fails_instead_of_displaying_a_stable_key(graph, catalog):
    catalog["item:key"]["name"] = ""
    with pytest.raises(ViewDataError, match=r"item:key.*no label"):
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)


def test_isolated_nodes_are_omitted_but_referenced_nodes_without_ways_remain(graph, catalog):
    graph.nodes += (
        ProgressionNode("item:unused", "item", "", False, None, None),
        ProgressionNode("quest:unused", "quest", "", True, None, None),
    )
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    assert "item:unused" not in data.rows
    assert "quest:unused" not in data.rows
    assert "item:unused" not in compact
    assert "quest:unused" not in compact
    assert compact["item:key"]["ways"] == []
    assert data.omitted_counts == {"item": 1, "quest": 1}


def test_compact_node_preserves_first_index_alternatives_and_all_need_fields(graph, catalog):
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    node = compact["quest:goal"]
    assert node == {
        "kind": "quest",
        "tier": 2,
        "milestone": True,
        "name": "Goal",
        "first": 2,
        "ways": [
            "[]",
            json.dumps(
                [
                    ["required item", "item:key", 2.5, "L1", "hello", None, True, True],
                    ["condition", None, None, None, None, data.rows["quest:goal"][-1]["text"]],
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ],
    }
    assert compact["quest_start:quest:goal"]["name"] == "Goal"
    assert compact["item:key"] == {
        "kind": "item",
        "milestone": False,
        "name": "Key",
        "page": False,
        "ways": [],
    }
    assert compact["_meta"] == {"defaults": [], "maxDepth": 6, "unmet": ["quest not done"]}


@pytest.mark.parametrize("page", [None, "Goal", "Different article"])
def test_compact_page_contract_distinguishes_pageless_and_same_name_pages(graph, catalog, page):
    if page is None:
        del catalog["quest:goal"]["page"]
    else:
        catalog["quest:goal"]["page"] = page
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    for key in ("quest:goal", "quest_start:quest:goal"):
        node = compact[key]
        actual = node.get("page", node["name"])
        assert actual == (False if page is None else page)


def test_packed_needs_round_trip_escaped_unicode_and_empty_text(graph, catalog):
    original = graph.ways["quest:goal"][0].needs[0]
    need = replace(original, slot="", keywords='say "café" \\ | ; ~')
    graph.ways["quest:goal"] = (ProgressionWay("complete", (need,)),)
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    node = compact_progression_data(data.rows)["quest:goal"]
    assert json.loads(node["ways"][0]) == [
        ["required item", "item:key", 2.5, "", 'say "café" \\ | ; ~', None, True, True]
    ]
    assert "-- Each way is a JSON string of need arrays." in data.content
    assert data.module_bytes == len(data.content.encode("utf-8"))


def test_compact_keeps_all_sources_and_dependencies_without_depth_projection(graph, catalog):
    keys = [f"item:chain:{index}" for index in range(9)]
    for index, key in enumerate(keys):
        graph.nodes += (ProgressionNode(key, "item", key, False, None, None),)
        catalog[key] = {"name": key}
        if index + 1 < len(keys):
            need = ProgressionNeed("source", keys[index + 1], None, None, None, None, False, False)
            graph.ways[key] = (ProgressionWay("source", (need,)),)
        else:
            graph.ways[key] = ()
    ways = tuple(
        ProgressionWay(
            f"source:{index}",
            (ProgressionNeed("source", key, None, None, None, None, False, False),),
        )
        for index, key in enumerate(keys)
    )
    graph.ways["quest:goal"] += ways
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    assert set(compact) == set(data.rows) | {"_meta"}
    assert len(compact["quest:goal"]["ways"]) == len(graph.ways["quest:goal"])
    for left, right in pairwise(keys):
        assert json.loads(compact[left]["ways"][0]) == [["source", right]]


def test_default_raid_routes_use_dedicated_planning_slot_needs_not_names(graph, catalog):
    dedicated = [f"zone:dedicated:{index}" for index in range(4)]
    for key in [*dedicated, "zone:rune", "zone:ordinary"]:
        graph.nodes += (ProgressionNode(key, "zone", "Unrelated name", True, None, None),)
        catalog[key] = {"name": "Unrelated name"}
        slot = "rune slot" if key == "zone:rune" else "native slot"
        relation = "zone line" if key == "zone:ordinary" else "planning slot"
        graph.ways[key] = (
            ProgressionWay(
                "planning",
                (ProgressionNeed(relation, "item:key", None, slot, None, None, False, False),),
            ),
        )
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    assert compact["_meta"] == {"defaults": dedicated, "maxDepth": 6, "unmet": ["quest not done"]}
    assert all("first" not in compact[key] and "tier" not in compact[key] for key in dedicated)


def test_compact_preserves_required_character_level_on_its_need(graph, catalog):
    original = graph.ways["quest:goal"][0].needs[0]
    need = replace(original, required_level=8)
    graph.ways["quest:goal"] = (ProgressionWay("complete", (need,)),)
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert data.rows["quest:goal"][-1]["required_level"] == 8
    packed = compact_progression_data(data.rows)["quest:goal"]["ways"][0]
    assert json.loads(packed) == [["required item", "item:key", 2.5, "L1", "hello", None, True, True, 8]]
