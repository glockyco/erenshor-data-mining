from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeProgressionRepository

from erenshor.application.wiki_lua.progression import build_progression_data, write_progression_module
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
    assert "item:unused" not in data.rows
    assert "quest:unused" not in data.rows
    assert "item:key" in data.rows
    assert data.omitted_counts == {"item": 1, "quest": 1}
