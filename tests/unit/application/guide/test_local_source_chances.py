"""Local final-acquisition odds survive the real canonical producer boundary."""

from __future__ import annotations

import json

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.mod_writer import serialize_mod_guide
from erenshor.application.guide.schema import Node, NodeType
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceLocation,
)

from .fixtures import build_graph, character_node, item_node, load_canonical_sources, quest_node


def _fixture():
    return build_graph(
        quest_node("quest:chances", "CHANCES"),
        item_node("item:catch"),
        character_node("character:test", "Dropper"),
        Node("water:test", NodeType.WATER, "Fishing Water"),
        Node("mining:test", NodeType.MINING_NODE, "Mining Node"),
    )


def _payload(graph):
    return json.loads(serialize_mod_guide(graph, compile_graph(graph)))


def _required():
    return ItemUse(
        "required",
        "item:catch",
        "quest:chances",
        "quest_requirement",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )


@pytest.mark.parametrize(
    "day,night",
    [
        (5.9375, 19.0),
        (None, 13.5714283),
        (31.66666603088379, None),
        (0.0, 13.5714283),
        (31.66666603088379, 0.0),
        (5.588235378265381, 5.588235378265381),
        (1.000001, 1.000002),
    ],
)
def test_final_local_fishing_phases_are_not_replaced_or_maximized_again(tmp_path, day, night):
    graph = _fixture()
    facts = [
        ItemAcquisition(
            period,
            "item:catch",
            "fishing",
            "water:test",
            probability_kind="exact",
            probability_min=chance,
            probability_max=chance,
            probability_basis="per_successful_catch",
            conditions=(ProvenanceCondition("time", 0, 0, "time_of_day", value=period, phase="operation_input"),),
            locations=(ProvenanceLocation("actual-water", "fixed", scene="FishingScene", x=1, y=2, z=3),),
        )
        for period, chance in (("day", day), ("night", night))
        if chance is not None
    ]
    load_canonical_sources(tmp_path, graph, facts, [_required()])
    payload = _payload(graph)
    sources = payload["quests"][0]["required_items"][0]["sources"]
    assert {row["time_restriction"]: row["chance"] for row in sources} == {
        period: chance for period, chance in (("day", day), ("night", night)) if chance is not None and chance > 0
    }
    for row in sources:
        period = row["time_restriction"]
        assert row[f"{period}_chance"] == row["chance"]
        assert row["night_chance" if period == "day" else "day_chance"] == 0
        assert row["location_key"] == "actual-water"
        assert payload["_source_facts"][row["acquisition_key"]]["probability_stage"] == "final_acquisition"


@pytest.mark.parametrize("kind,source", [("character_drop", "character:test"), ("mining", "mining:test")])
@pytest.mark.parametrize("chance", [36.7123456789, 0.000000000001, None])
def test_unknown_and_tiny_positive_local_odds_survive(tmp_path, kind, source, chance):
    graph = _fixture()
    fact = ItemAcquisition(
        "actual",
        "item:catch",
        kind,
        source,
        probability_kind="unknown" if chance is None else "exact",
        probability_min=chance,
        probability_max=chance,
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    payload = _payload(graph)
    [row] = payload["quests"][0]["required_items"][0]["sources"]
    if chance is None:
        assert "chance" not in row
    else:
        assert row["chance"] == chance
    assert payload["_source_facts"]["actual"]["probability_min"] == chance


def test_known_zero_is_excluded_by_the_shared_selector(tmp_path):
    graph = _fixture()
    fact = ItemAcquisition(
        "zero",
        "item:catch",
        "character_drop",
        "character:test",
        probability_kind="exact",
        probability_min=0,
        probability_max=0,
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    assert "sources" not in _payload(graph)["quests"][0]["required_items"][0]
    assert graph.source_exclusions["zero"] == "not_actionable_canonical_acquisition"


@pytest.mark.parametrize("keywords", ["papers,leave", None])
def test_selected_native_dialog_copy_and_index_preserve_keyword(tmp_path, keywords):
    graph = _fixture()
    fact = ItemAcquisition(
        "dialog", "item:catch", "dialog", "character:test", source_copy_stable_key="character:test", variant_key="2"
    )
    metadata = (
        "INSERT INTO characters(stable_key,object_name,npc_name,display_name,image_name,"
        "encounter_tier,level_scales_with_player,can_be_damaged)"
        " VALUES ('character:test','Test','Test','Test','','npc',0,1);"
        "INSERT INTO character_dialogs(character_stable_key,dialog_index,keywords)"
        f" VALUES ('character:test',2,{repr(keywords) if keywords is not None else 'NULL'});"
        "INSERT INTO character_dialogs(character_stable_key,dialog_index,keywords) VALUES ('character:test',1,'WRONG');"
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()], metadata)
    [row] = _payload(graph)["quests"][0]["required_items"][0]["sources"]
    assert row.get("keyword") == ("papers" if keywords else None)
