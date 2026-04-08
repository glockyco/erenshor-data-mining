"""Unit tests for the new guide compiler data model."""

from __future__ import annotations

import math

from erenshor.application.guide.compiler import (
    CompiledData,
    CompiledEdge,
    CompiledNode,
    EdgeFlags,
    ItemRequirement,
    NodeFlags,
    QuestSpec,
    SectionId,
    SourceSite,
    SpawnPosition,
    StepSpec,
    UnlockCondition,
    UnlockPredicate,
)


def test_compiled_data_defaults_are_empty() -> None:
    data = CompiledData()

    assert data.nodes == []
    assert data.edges == []
    assert data.quest_node_ids == []
    assert data.item_node_ids == []
    assert data.topo_order == []
    assert data.infeasible_node_ids == set()
    assert data.node_key_to_id == {}


def test_compiled_node_preserves_nan_positions() -> None:
    node = CompiledNode(
        node_id=7,
        key="quest:a",
        node_type=0,
        display_name="Quest A",
        scene=None,
        x=math.nan,
        y=math.nan,
        z=math.nan,
        flags=NodeFlags.IMPLICIT,
        level=0,
        zone_key=None,
        db_name="QUESTA",
    )

    assert node.node_id == 7
    assert math.isnan(node.x)
    assert math.isnan(node.y)
    assert math.isnan(node.z)
    assert node.flags == NodeFlags.IMPLICIT
    assert node.db_name == "QUESTA"


def test_section_ids_are_stable() -> None:
    assert SectionId.STRING_TABLE == 0
    assert SectionId.NODE_TABLE == 1
    assert SectionId.EDGE_TABLE == 2
    assert SectionId.FEASIBILITY == 13


def test_nested_compiled_types_round_trip() -> None:
    step = StepSpec(step_type=3, target_id=11, ordinal=2)
    req = ItemRequirement(item_id=22, qty=5, group=1)
    pred = UnlockPredicate(
        target_id=33,
        conditions=[UnlockCondition(source_id=44, check_type=0, group=2)],
        group_count=2,
        semantics=1,
    )
    source = SourceSite(
        source_id=55,
        source_type=2,
        edge_type=18,
        direct_item_id=0,
        scene=None,
        positions=[SpawnPosition(spawn_id=66, x=1.0, y=2.0, z=3.0)],
    )
    edge = CompiledEdge(
        source_id=1,
        target_id=2,
        edge_type=3,
        flags=EdgeFlags.HAS_GROUP,
        group="and-a",
        ordinal=0,
        quantity=2,
        keyword=None,
        chance=1000,
    )
    spec = QuestSpec(
        quest_id=77,
        quest_index=4,
        prereq_quest_ids=[9],
        required_items=[req],
        steps=[step],
        giver_node_ids=[12],
        completer_node_ids=[13],
        chains_to_ids=[14],
        is_implicit=True,
        is_infeasible=False,
    )
    data = CompiledData(
        edges=[edge],
        quest_specs=[spec],
        unlock_predicates=[pred],
        item_sources=[[source]],
    )

    assert data.edges[0].group == "and-a"
    assert data.quest_specs[0].required_items[0].qty == 5
    assert data.unlock_predicates[0].conditions[0].source_id == 44
    assert data.item_sources[0][0].positions[0].spawn_id == 66
