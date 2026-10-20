from __future__ import annotations

import json
import re
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeProgressionRepository

from erenshor.application.progression_wording import ACTIONS, LEADS
from erenshor.application.wiki_lua.progression import (
    build_progression_data,
    compact_progression_data,
    write_progression_module,
)
from erenshor.application.wiki_lua.views import ViewDataError
from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode, ProgressionWay

REQUIRED = ProgressionNeed("required item", "item:key", 2.5, "L1", "hello", None, True, True)
RELEASE = ProgressionNeed("release", None, None, None, None, "release:combat_empty_wards:copy", False, False)
TURN_IN = ProgressionNeed("turn in to", "character:giver", None, None, None, None, False, False)
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def complete(*needs: ProgressionNeed) -> tuple[ProgressionWay, ...]:
    """The goal's only way: the given needs and the turn-in that finishes it."""
    return (ProgressionWay("complete", (*needs, TURN_IN)),)


@pytest.fixture
def graph() -> FakeProgressionRepository:
    return FakeProgressionRepository(
        (
            ProgressionNode("quest:goal", "quest", "Goal", True, 2, "complete"),
            ProgressionNode("quest_start:quest:goal", "quest_start", "Start", False, 1, "start"),
            ProgressionNode("item:key", "item", "Key", False, None, None),
            ProgressionNode("character:giver", "character", "Giver", False, 0, None),
            ProgressionNode("mechanic:new_character_start", "mechanism", "Start", False, 0, "initial"),
        ),
        {
            "quest:goal": (ProgressionWay("complete", (REQUIRED, RELEASE, TURN_IN)), ProgressionWay("alternative", ())),
            "quest_start:quest:goal": (ProgressionWay("start", ()),),
            "mechanic:new_character_start": (ProgressionWay("initial", ()),),
        },
    )


@pytest.fixture
def catalog() -> dict[str, dict[str, object]]:
    return {
        "quest:goal": {"name": "Goal", "page": "Goal"},
        "item:key": {"name": "Key"},
        "character:giver": {"name": "Giver"},
    }


def without_sentence(row: dict[str, object]) -> dict[str, object]:
    return {field: value for field, value in row.items() if field != "sentence"}


def test_rows_preserve_nodes_alternative_empty_ways_and_all_need_fields(graph, catalog):
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert (data.node_count, data.way_count, data.need_count) == (5, 4, 3)
    assert list(data.rows) == sorted(node.stable_key for node in graph.nodes)
    node, alternative, way, required, condition, receiver = data.rows["quest:goal"]
    assert node == {
        "type": "node",
        "kind": "quest",
        "tier": 2,
        "milestone": True,
        "label": {"key": "quest:goal", **catalog["quest:goal"]},
    }
    assert without_sentence(alternative) == {"type": "way", "way": "alternative", "first": False}
    assert without_sentence(way) == {"type": "way", "way": "complete", "first": True}
    # Every way carries its sentence, which names the nodes of its needs and the node itself.
    assert set(PLACEHOLDER.findall(str(way["sentence"]))) == {"item:key", "character:giver", "quest:goal"}
    assert isinstance(alternative["sentence"], str) and alternative["sentence"]
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
    assert receiver["need"] == "character:giver"
    assert "tier" not in data.rows["item:key"][0]
    assert data.rows["quest_start:quest:goal"][0]["label"] == node["label"]
    assert without_sentence(data.rows["mechanic:new_character_start"][1]) == {
        "type": "way",
        "way": "initial",
        "first": True,
    }


def test_unknown_condition_names_module_node_way_and_fact(graph, catalog):
    need = ProgressionNeed("release", None, None, None, None, "new:unworded", False, False)
    graph.ways["quest:goal"] = complete(need)
    with pytest.raises(ViewDataError) as error:
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert all(
        value in str(error.value)
        for value in ("Module:Erenshor/Data/Progression", "quest:goal", "complete", "new:unworded")
    )


def test_a_relation_without_wording_names_module_node_and_way(graph, catalog):
    need = ProgressionNeed("bargain", "item:key", None, None, None, None, False, False)
    graph.ways["quest:goal"] = complete(need)
    with pytest.raises(ViewDataError) as error:
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert all(value in str(error.value) for value in ("Module:Erenshor/Data/Progression", "quest:goal", "complete"))
    assert "bargain" in str(error.value)


def test_a_sentence_that_names_a_node_outside_the_module_fails(graph, catalog):
    # A start whose quest has no node of its own would name the quest in its sentence.
    graph.nodes += (ProgressionNode("quest_start:quest:orphan", "quest_start", "Start", False, 1, "start"),)
    talk = ProgressionNeed("talk to", "character:giver", None, None, None, None, False, False)
    graph.ways["quest_start:quest:orphan"] = (ProgressionWay("start", (talk,)),)
    catalog["quest:orphan"] = {"name": "Orphan"}
    with pytest.raises(
        ViewDataError, match=r"quest_start:quest:orphan way start: names unknown nodes \['quest:orphan'\]"
    ):
        build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)


def test_a_quest_without_a_way_stays_when_its_start_names_it(graph, catalog):
    graph.nodes += (
        ProgressionNode("quest:open", "quest", "Open", True, None, None),
        ProgressionNode("quest_start:quest:open", "quest_start", "Start", False, 1, "start"),
    )
    talk = ProgressionNeed("talk to", "character:giver", None, None, None, None, False, False)
    graph.ways["quest_start:quest:open"] = (ProgressionWay("start", (talk,)),)
    catalog["quest:open"] = {"name": "Open"}
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert data.rows["quest:open"] == [
        {"type": "node", "kind": "quest", "milestone": True, "label": {"key": "quest:open", "name": "Open"}}
    ]
    assert "quest:open" in PLACEHOLDER.findall(str(data.rows["quest_start:quest:open"][1]["sentence"]))


@pytest.mark.parametrize("failure", ["node", "need", "mechanism"])
def test_unknown_identities_fail_closed(graph, catalog, failure):
    if failure == "node":
        del catalog["item:key"]
    elif failure == "need":
        graph.ways["quest:goal"] = complete(replace(REQUIRED, need_stable_key="item:missing"))
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


def test_an_item_that_only_a_quest_rewards_names_that_quest(graph, catalog):
    reward = ProgressionNeed("reward", "quest:goal", None, None, None, None, False, False)
    undone = ProgressionNeed("quest not done", "quest:goal", None, None, None, None, False, False)
    held = ProgressionNeed("held", "item:key", None, None, None, None, False, False)
    other = ProgressionNeed("held", "character:giver", None, None, None, None, False, False)
    for key, needs in (("item:prize", (reward, undone, held)), ("item:other", (reward, other))):
        graph.nodes += (ProgressionNode(key, "item", key, True, 3, "reward"),)
        graph.ways[key] = (ProgressionWay("reward", needs),)
        catalog[key] = {"name": key}
    compact = compact_progression_data(build_progression_data(graph, {"quest:goal"}, native_catalog=catalog).rows)
    # The turn-in item and the undone quest come with the reward, so only the reward remains.
    assert compact["item:prize"]["reward"] == "quest:goal"
    assert "reward" not in compact["item:other"]


@pytest.mark.parametrize("field", ["slot", "keywords", "label"])
def test_markup_is_rejected_in_all_player_text(graph, catalog, field):
    if field == "label":
        catalog["quest:goal"]["name"] = "[[Unsafe]]"
    else:
        graph.ways["quest:goal"] = complete(replace(REQUIRED, **{field: "[[Unsafe]]"}))
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


def test_compact_node_packs_each_sentence_before_its_needs(graph, catalog):
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    alternative, way = (row for row in data.rows["quest:goal"] if row["type"] == "way")

    def packed(*values: object) -> str:
        return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))

    assert compact["quest:goal"] == {
        "kind": "quest",
        "tier": 2,
        "milestone": True,
        "name": "Goal",
        "first": 2,
        "ways": [
            packed(alternative["sentence"]),
            packed(
                way["sentence"],
                ["required item", "item:key", 2.5, "L1", "hello", None, True, True],
                ["release", None, None, None, None, data.rows["quest:goal"][4]["text"]],
                ["turn in to", "character:giver"],
            ),
        ],
    }
    assert compact["quest_start:quest:goal"]["name"] == "Goal"
    assert compact["item:key"] == {"kind": "item", "milestone": False, "name": "Key", "page": False, "ways": []}
    assert compact["_meta"] == {
        "defaults": [],
        "unmet": ["quest not done"],
        "actions": dict(sorted(ACTIONS.items())),
        "leads": dict(sorted(LEADS.items())),
    }


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
    graph.ways["quest:goal"] = complete(replace(REQUIRED, slot="", keywords='say "café" \\ | ; ~'))
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    node = compact_progression_data(data.rows)["quest:goal"]
    assert json.loads(node["ways"][0])[1:] == [
        ["required item", "item:key", 2.5, "", 'say "café" \\ | ; ~', None, True, True],
        ["turn in to", "character:giver"],
    ]
    assert data.module_bytes == len(data.content.encode("utf-8"))


def test_compact_keeps_all_sources_and_dependencies_without_depth_projection(graph, catalog):
    keys = [f"item:chain:{index}" for index in range(9)]
    for index, key in enumerate(keys):
        graph.nodes += (ProgressionNode(key, "item", key, False, None, None),)
        catalog[key] = {"name": key}
        if index + 1 < len(keys):
            need = ProgressionNeed("contained in", keys[index + 1], None, None, None, None, False, False)
            graph.ways[key] = (ProgressionWay("source", (need,)),)
        else:
            graph.ways[key] = ()
    ways = tuple(
        ProgressionWay(
            f"source:{index}",
            (ProgressionNeed("read", key, None, None, None, None, False, False),),
        )
        for index, key in enumerate(keys)
    )
    graph.ways["quest:goal"] += ways
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    compact = compact_progression_data(data.rows)
    assert set(compact) == set(data.rows) | {"_meta"}
    assert len(compact["quest:goal"]["ways"]) == len(graph.ways["quest:goal"])
    for left, right in pairwise(keys):
        assert json.loads(compact[left]["ways"][0])[1:] == [["contained in", right]]


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
    assert compact["_meta"]["defaults"] == dedicated
    assert all("first" not in compact[key] and "tier" not in compact[key] for key in dedicated)


def test_compact_preserves_required_character_level_on_its_need(graph, catalog):
    graph.ways["quest:goal"] = complete(replace(REQUIRED, required_level=8))
    data = build_progression_data(graph, {"quest:goal"}, native_catalog=catalog)
    assert data.rows["quest:goal"][2]["required_level"] == 8
    packed = compact_progression_data(data.rows)["quest:goal"]["ways"][0]
    assert json.loads(packed)[1] == ["required item", "item:key", 2.5, "L1", "hello", None, True, True, 8]
