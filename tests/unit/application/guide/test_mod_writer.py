"""Behavioral tests for the AdventureGuide compatibility wrapper."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.mod_writer import build_mod_guide, serialize_mod_guide
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType, WorkflowCycle, WorkflowTarget

from .fixtures import build_graph, character_node, item_node, quest_node


def _fixture() -> tuple[EntityGraph, dict[str, object]]:
    """Build one small graph exercising every legacy wrapper section."""
    main = quest_node(
        "quest:main",
        "MAIN",
        display_name="Main Quest",
        description="Recover the relic.",
        xp_reward=321,
        gold_reward=45,
        reward_item_key="item:reward",
        repeatable=True,
        disabled=True,
        disabled_text="Unavailable",
        implicit=False,
        kill_turn_in_holder=True,
        destroy_turn_in_holder=True,
        drop_invuln_on_holder=True,
        once_per_spawn_instance=True,
        zone="Ashen Vale",
        zone_key="zone:ashen",
    )
    previous = quest_node("quest:previous", "PREVIOUS", display_name="Previous Quest")
    alternate = quest_node("quest:alternate", "ALTERNATE", display_name="Alternate Quest")
    second = quest_node("quest:second", "SECOND", display_name="Second Quest")
    also = quest_node("quest:also", "ALSO", display_name="Also Quest")

    giver = character_node(
        "char:giver",
        "Quest Giver",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        x=1,
        y=2,
        z=3,
    )
    completer = character_node(
        "char:completer",
        "Quest Completer",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        x=4,
        y=5,
        z=6,
    )
    mob = character_node(
        "char:mob",
        "Relic Guardian",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        level=12,
        x=7,
        y=8,
        z=9,
    )
    unlockable = character_node(
        "char:unlockable",
        "Unlocked Guide",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
    )
    spawn = Node(
        key="spawn:mob:one",
        type=NodeType.SPAWN_POINT,
        display_name="Relic Guardian Spawn",
        scene="AshenScene",
        zone_key="zone:ashen",
        x=10,
        y=11,
        z=12,
        night_spawn=True,
    )
    unlock_spawn = Node(
        key="spawn:unlockable",
        type=NodeType.SPAWN_POINT,
        display_name="Unlocked Guide Spawn",
        scene="AshenScene",
        zone_key="zone:ashen",
        x=13,
        y=14,
        z=15,
        is_directly_placed=True,
        source_script="VithArenaFight",
    )

    item_a = item_node("item:alpha", "Alpha Relic")
    item_b = item_node("item:beta", "Beta Relic")
    reward = item_node("item:reward", "Reward Relic")
    read_item = item_node("item:read", "Ancient Tablet")
    travel_zone = Node(
        key="zone:travel",
        type=NodeType.ZONE,
        display_name="Hidden Vale",
        scene="HiddenScene",
        zone_key="zone:travel",
        level_min=8,
        level_max=16,
    )
    ashen_zone = Node(
        key="zone:ashen",
        type=NodeType.ZONE,
        display_name="Ashen Vale",
        scene="AshenScene",
        zone_key="zone:ashen",
        level_min=5,
        level_max=20,
    )
    zone_line = Node(
        key="zone-line:ashen-hidden",
        type=NodeType.ZONE_LINE,
        display_name="Ashen Gate",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        x=20,
        y=21,
        z=22,
        destination_zone_key="zone:travel",
        destination_display="Hidden Vale",
        landing_x=30,
        landing_y=31,
        landing_z=32,
    )

    edges = [
        Edge(source="quest:main", target="quest:previous", type=EdgeType.REQUIRES_QUEST),
        Edge(source="quest:main", target="item:alpha", type=EdgeType.REQUIRES_ITEM, quantity=2, group="path-a"),
        Edge(source="quest:main", target="item:beta", type=EdgeType.REQUIRES_ITEM, quantity=1, group="path-b"),
        Edge(source="quest:main", target="char:giver", type=EdgeType.ASSIGNED_BY, keyword="BEGIN"),
        Edge(
            source="quest:main", target="char:completer", type=EdgeType.COMPLETED_BY, keyword="DONE", note="item_turnin"
        ),
        Edge(source="quest:main", target="item:reward", type=EdgeType.REWARDS_ITEM),
        Edge(source="quest:main", target="quest:also", type=EdgeType.ALSO_COMPLETES),
        Edge(source="quest:main", target="quest:second", type=EdgeType.CHAINS_TO),
        Edge(source="quest:main", target="char:unlockable", type=EdgeType.UNLOCKS_CHARACTER, group="route-2"),
        Edge(source="quest:main", target="zone-line:ashen-hidden", type=EdgeType.UNLOCKS_ZONE_LINE, group="route-2"),
        Edge(source="quest:main", target="char:mob", type=EdgeType.STEP_KILL, ordinal=20, group="combat-path"),
        Edge(source="quest:main", target="item:read", type=EdgeType.STEP_READ, ordinal=30, group="read-path"),
        Edge(source="quest:main", target="zone:travel", type=EdgeType.STEP_TRAVEL, ordinal=40),
        Edge(source="quest:main", target="char:completer", type=EdgeType.STEP_TALK, ordinal=10, keyword="SPEAK"),
        Edge(source="quest:main", target="char:mob", type=EdgeType.STEP_SHOUT, ordinal=50, keyword="ROAR"),
        Edge(source="char:mob", target="item:alpha", type=EdgeType.DROPS_ITEM, chance=0.25),
        Edge(source="char:mob", target="spawn:mob:one", type=EdgeType.HAS_SPAWN),
        Edge(source="char:unlockable", target="spawn:unlockable", type=EdgeType.HAS_SPAWN),
        Edge(source="spawn:unlockable", target="quest:main", type=EdgeType.GATED_BY_QUEST),
        # Two quests in one AND group, and one independent OR group.
        Edge(source="quest:previous", target="char:unlockable", type=EdgeType.UNLOCKS_CHARACTER, group="route-1"),
        Edge(source="quest:second", target="char:unlockable", type=EdgeType.UNLOCKS_CHARACTER, group="route-1"),
        Edge(source="quest:alternate", target="char:unlockable", type=EdgeType.UNLOCKS_CHARACTER, group="route-3"),
        Edge(
            source="quest:previous", target="zone-line:ashen-hidden", type=EdgeType.UNLOCKS_ZONE_LINE, group="route-1"
        ),
        Edge(source="quest:second", target="zone-line:ashen-hidden", type=EdgeType.UNLOCKS_ZONE_LINE, group="route-1"),
        Edge(
            source="quest:alternate", target="zone-line:ashen-hidden", type=EdgeType.UNLOCKS_ZONE_LINE, group="route-3"
        ),
        Edge(source="quest:previous", target="quest:main", type=EdgeType.CHAINS_TO),
    ]
    graph = build_graph(
        main,
        previous,
        alternate,
        second,
        also,
        giver,
        completer,
        mob,
        unlockable,
        spawn,
        unlock_spawn,
        item_a,
        item_b,
        reward,
        read_item,
        travel_zone,
        ashen_zone,
        zone_line,
        edges=edges,
    )
    return graph, {"main": main, "unlockable": unlockable}


def _main_entry(data: dict[str, object], stable_key: str = "quest:main") -> dict[str, object]:
    entries = data["quests"]
    assert isinstance(entries, list)
    return next(entry for entry in entries if entry["stable_key"] == stable_key)


def test_build_mod_guide_preserves_wrapper_shape_and_quest_identity() -> None:
    graph, _ = _fixture()
    data = build_mod_guide(graph, compile_graph(graph))

    assert list(data) == [
        "_version",
        "_zone_lookup",
        "_character_spawns",
        "_zone_lines",
        "_chain_groups",
        "_character_quest_unlocks",
        "quests",
    ]
    assert data["_version"] == 6
    main = _main_entry(data)
    assert main["db_name"] == "MAIN"
    assert main["stable_key"] == "quest:main"
    assert main["display_name"] == "Main Quest"
    assert main["description"] == "Recover the relic."
    assert main["acceptance"] == "explicit"
    assert data["_chain_groups"] == [{"name": "Previous Quest", "quests": ["PREVIOUS", "MAIN", "SECOND"]}]


def test_build_mod_guide_emits_acquisition_completion_and_ordered_steps() -> None:
    graph, _ = _fixture()
    main = _main_entry(build_mod_guide(graph, compile_graph(graph)))

    assert main["acquisition"] == [
        {
            "method": "dialog",
            "source_name": "Quest Giver",
            "source_type": "character",
            "source_stable_key": "char:giver",
            "zone_name": "Ashen Vale",
            "keyword": "BEGIN",
        }
    ]
    assert main["completion"] == [
        {
            "method": "item_turnin",
            "source_name": "Quest Completer",
            "source_type": "character",
            "source_stable_key": "char:completer",
            "zone_name": "Ashen Vale",
            "keyword": "SPEAK",
            "note": "item_turnin",
        }
    ]
    steps = main["steps"]
    assert [(step["order"], step["action"], step["target_key"]) for step in steps] == [
        (1, "talk", "char:giver"),
        (2, "collect", "item:alpha"),
        (3, "collect", "item:beta"),
        (4, "collect", "item:read"),
        (5, "talk", "char:completer"),
        (6, "kill", "char:mob"),
        (7, "read", "item:read"),
        (8, "travel", "zone:travel"),
        (9, "shout", "char:mob"),
        (10, "turn_in", "char:completer"),
    ]
    assert (
        next(step for step in steps if step["target_key"] == "char:mob" and step["action"] == "kill")["or_group"]
        == "combat-path"
    )
    assert next(step for step in steps if step["target_key"] == "item:alpha")["or_group"] == "path-a"


def test_build_mod_guide_groups_required_items_and_inlines_sources() -> None:
    graph, _ = _fixture()
    main = _main_entry(build_mod_guide(graph, compile_graph(graph)))
    required = main["required_items"]

    assert [(item["item_stable_key"], item["quantity"], item["or_group"]) for item in required] == [
        ("item:alpha", 2, "path-a"),
        ("item:beta", 1, "path-b"),
        ("item:read", 1, "read-path"),
    ]
    source = next(item for item in required if item["item_stable_key"] == "item:alpha")["sources"][0]
    assert source["type"] == "drop"
    assert source["name"] == "Relic Guardian"
    assert source["source_key"] == "char:mob"
    assert source["scene"] == "AshenScene"
    assert source["spawn_count"] == 1


def test_build_mod_guide_emits_rewards_chain_and_flags() -> None:
    graph, _ = _fixture()
    main = _main_entry(build_mod_guide(graph, compile_graph(graph)))

    assert main["rewards"]["xp"] == 321
    assert main["rewards"]["gold"] == 45
    assert main["rewards"]["item_name"] == "Reward Relic"
    assert main["rewards"]["item_stable_key"] == "item:reward"
    assert "ALSO" in main["rewards"]["also_completes"]
    assert main["chain"] == [
        {"quest_name": "Second Quest", "quest_stable_key": "quest:second", "relationship": "next"},
        {"quest_name": "Previous Quest", "quest_stable_key": "quest:previous", "relationship": "previous"},
    ]
    assert main["rewards"]["unlocked_zone_lines"] == [
        {
            "from_zone": "Ashen Vale",
            "to_zone": "Hidden Vale",
        }
    ]
    assert main["rewards"]["unlocked_characters"] == [{"name": "Unlocked Guide", "zone": "Ashen Vale"}]
    assert main["flags"] == {
        "guide_only": False,
        "repeatable": True,
        "disabled": True,
        "disabled_text": "Unavailable",
        "kill_turn_in_holder": True,
        "destroy_turn_in_holder": True,
        "drop_invuln_on_holder": True,
        "once_per_spawn_instance": True,
    }


def test_build_mod_guide_emits_zone_character_and_unlock_lookups() -> None:
    graph, _ = _fixture()
    data = build_mod_guide(graph, compile_graph(graph))

    assert data["_zone_lookup"]["AshenScene"] == {
        "display_name": "Ashen Vale",
        "stable_key": "zone:ashen",
        "level_min": 5,
        "level_max": 20,
    }
    assert data["_character_spawns"]["char:mob"] == [
        {
            "scene": "AshenScene",
            "x": 10,
            "y": 11,
            "z": 12,
            "night_spawn": True,
            "is_directly_placed": False,
        }
    ]
    assert data["_character_spawns"]["char:unlockable"] == [
        {
            "scene": "AshenScene",
            "x": 13,
            "y": 14,
            "z": 15,
            "night_spawn": False,
            "is_directly_placed": True,
            "source_script": "VithArenaFight",
            "spawn_upon_quest_complete_stable_key": "quest:main",
        }
    ]
    assert data["_zone_lines"] == [
        {
            "scene": "AshenScene",
            "x": 20,
            "y": 21,
            "z": 22,
            "is_enabled": True,
            "destination_zone_key": "zone:travel",
            "destination_display": "Hidden Vale",
            "landing_x": 30,
            "landing_y": 31,
            "landing_z": 32,
            "required_quest_groups": [["PREVIOUS", "SECOND"], ["MAIN"], ["ALTERNATE"]],
        }
    ]
    assert data["_character_quest_unlocks"]["char:unlockable"] == [
        ["PREVIOUS", "SECOND"],
        ["MAIN"],
        ["ALTERNATE"],
    ]


def _resource_graph(source_type: NodeType) -> EntityGraph:
    quest = quest_node("quest:resource", "RESOURCE", display_name="RESOURCE")
    item = item_node("item:resource", "Resource Item")
    source = Node(
        key=f"{source_type.value}:source",
        type=source_type,
        display_name=f"{source_type.value.title()} Source",
        scene="ResourceScene",
        zone="Resource Zone",
        zone_key="zone:resource",
        level=9,
    )
    return build_graph(
        quest,
        item,
        source,
        Node(
            key="zone:resource",
            type=NodeType.ZONE,
            display_name="Resource Zone",
            scene="ResourceScene",
            level_min=9,
            level_max=9,
        ),
        edges=[
            Edge(source=quest.key, target=item.key, type=EdgeType.REQUIRES_ITEM),
            Edge(source=source.key, target=item.key, type=EdgeType.YIELDS_ITEM),
        ],
    )


@pytest.mark.parametrize(
    ("source_type", "expected_type"),
    [
        (NodeType.WATER, "fishing"),
        (NodeType.MINING_NODE, "mining"),
        (NodeType.ITEM_BAG, "pickup"),
    ],
)
def test_build_mod_guide_maps_resource_yields_by_source_node_type(source_type: NodeType, expected_type: str) -> None:
    graph = _resource_graph(source_type)
    required = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:resource")["required_items"]

    assert required[0]["sources"][0]["type"] == expected_type


def test_build_mod_guide_rejects_unsupported_resource_yield_source() -> None:
    graph = _resource_graph(NodeType.FORGE)

    with pytest.raises(ValueError):
        build_mod_guide(graph, compile_graph(graph))


def _coordinate_graph(node_type: NodeType, field: str, value: float | None) -> EntityGraph:
    if node_type == NodeType.SPAWN_POINT:
        character = character_node("char:coordinate", "Coordinate Character")
        spawn = Node(
            key="spawn:coordinate",
            type=node_type,
            display_name="Coordinate Spawn",
            scene="CoordinateScene",
            x=1,
            y=2,
            z=3,
        )
        spawn = replace(spawn, **{field: value})
        return build_graph(
            character, spawn, edges=[Edge(source=character.key, target=spawn.key, type=EdgeType.HAS_SPAWN)]
        )
    line = Node(
        key="zone-line:coordinate",
        type=node_type,
        display_name="Coordinate Zone Line",
        scene="CoordinateScene",
        x=1,
        y=2,
        z=3,
        destination_zone_key="zone:destination",
        destination_display="Destination Zone",
    )
    return build_graph(replace(line, **{field: value}))


@pytest.mark.parametrize(
    ("node_type", "field", "value"),
    [
        (node_type, field, value)
        for node_type in (NodeType.SPAWN_POINT, NodeType.ZONE_LINE)
        for field in ("x", "y", "z")
        for value in (None, math.nan, math.inf)
    ],
)
def test_build_mod_guide_rejects_invalid_required_coordinates(
    node_type: NodeType, field: str, value: float | None
) -> None:
    graph = _coordinate_graph(node_type, field, value)
    key = "spawn:coordinate" if node_type == NodeType.SPAWN_POINT else "zone-line:coordinate"

    with pytest.raises(ValueError) as error:
        build_mod_guide(graph, compile_graph(graph))

    assert key in str(error.value)


def _vendor_unlock_graph(multiple: bool = False) -> EntityGraph:
    quest = quest_node("quest:vendor", "VENDOR", display_name="VENDOR")
    item = item_node("item:vendor", "Vendor Unlock Item")
    vendor = character_node("char:vendor", "Unlock Vendor", is_vendor=True)
    edges = [Edge(source=quest.key, target=item.key, type=EdgeType.UNLOCKS_VENDOR_ITEM, note=vendor.key)]
    nodes = [quest, item, vendor]
    if multiple:
        second_item = item_node("item:vendor-second", "Second Vendor Item")
        nodes.append(second_item)
        edges.append(Edge(source=quest.key, target=second_item.key, type=EdgeType.UNLOCKS_VENDOR_ITEM, note=vendor.key))
    return build_graph(*nodes, edges=edges)


def test_build_mod_guide_emits_single_vendor_unlock_names() -> None:
    graph = _vendor_unlock_graph()
    rewards = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:vendor")["rewards"]

    assert rewards["vendor_unlock"] == {
        "item_name": "Vendor Unlock Item",
        "vendor_name": "Unlock Vendor",
    }


def test_build_mod_guide_rejects_multiple_vendor_unlocks() -> None:
    graph = _vendor_unlock_graph(multiple=True)

    with pytest.raises(ValueError):
        build_mod_guide(graph, compile_graph(graph))


def _item_step_graph() -> EntityGraph:
    quest = quest_node("quest:item-step", "ITEM_STEP", display_name="ITEM_STEP")
    item = item_node("item:item-step", "Read Me")
    source = character_node("char:item-source", "Item Source", level=11)
    return build_graph(
        quest,
        item,
        source,
        edges=[
            Edge(source=quest.key, target=item.key, type=EdgeType.STEP_READ, group="read-path", ordinal=1),
            Edge(source=quest.key, target=item.key, type=EdgeType.COMPLETED_BY, group="read-path"),
            Edge(source=source.key, target=item.key, type=EdgeType.DROPS_ITEM),
        ],
    )


def test_build_mod_guide_synthesizes_deduped_item_requirements_from_item_steps() -> None:
    graph = _item_step_graph()
    main = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:item-step")

    assert main["required_items"] == [
        {
            "item_name": "Read Me",
            "item_stable_key": "item:item-step",
            "quantity": 1,
            "or_group": "read-path",
            "sources": [
                {
                    "type": "drop",
                    "name": "Item Source",
                    "level": 11,
                    "source_key": "char:item-source",
                    "spawn_count": 0,
                }
            ],
        }
    ]
    assert [(step["action"], step["target_key"]) for step in main["steps"]] == [
        ("collect", "item:item-step"),
        ("read", "item:item-step"),
    ]


def _level_step_graph() -> EntityGraph:
    quest = quest_node("quest:levels", "LEVELS", display_name="LEVELS")
    zone = Node(
        key="zone:levels",
        type=NodeType.ZONE,
        display_name="Level Zone",
        zone="Level Zone",
        level=16,
        level_min=16,
        level_max=16,
    )
    character = character_node("char:levels", "Level Character", zone="Level Zone", level=12)
    source = character_node("char:dropper", "Level Dropper", zone="Level Zone", level=18)
    second_source = character_node("char:dropper2", "Another Dropper", zone="Level Zone", level=14)
    item = item_node("item:levels", "Level Item")
    return build_graph(
        quest,
        zone,
        character,
        source,
        second_source,
        item,
        edges=[
            Edge(source=quest.key, target=character.key, type=EdgeType.STEP_TALK, ordinal=1),
            Edge(source=quest.key, target=zone.key, type=EdgeType.STEP_TRAVEL, ordinal=2),
            Edge(source=quest.key, target=item.key, type=EdgeType.REQUIRES_ITEM),
            Edge(source=source.key, target=item.key, type=EdgeType.DROPS_ITEM),
            Edge(source=second_source.key, target=item.key, type=EdgeType.DROPS_ITEM),
        ],
    )


def test_build_mod_guide_emits_per_step_level_estimates_and_factors() -> None:
    graph = _level_step_graph()
    steps = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:levels")["steps"]
    by_target = {step["target_key"]: step for step in steps}

    assert by_target["char:levels"]["level_estimate"] == {
        "recommended": 12,
        "factors": [{"source": "zone", "name": "Level Zone", "level": 12}],
    }
    assert by_target["zone:levels"]["level_estimate"] == {
        "recommended": 16,
        "factors": [{"source": "zone", "name": "Level Zone", "level": 16}],
    }
    assert by_target["item:levels"]["level_estimate"] == {
        "recommended": 14,
        "factors": [
            {"source": "drop", "name": "Another Dropper", "level": 14},
            {"source": "drop", "name": "Level Dropper", "level": 18},
        ],
    }


def _acquisition_item_graph(*, mixed_source: bool = False, required: bool = False) -> EntityGraph:
    prior = quest_node("quest:prior", "PRIOR", display_name="Prior Quest")
    current = quest_node("quest:current", "CURRENT", display_name="Duskenlight Quest")
    item = item_node("item:duskenlight", "Duskenlight")
    nodes: list[Node] = [prior, current, item]
    edges = [
        Edge(source=prior.key, target=item.key, type=EdgeType.REWARDS_ITEM),
        Edge(source=current.key, target=item.key, type=EdgeType.ASSIGNED_BY),
    ]
    if required:
        edges.extend(
            [
                Edge(source=current.key, target=prior.key, type=EdgeType.REQUIRES_QUEST),
                Edge(source=current.key, target=item.key, type=EdgeType.REQUIRES_ITEM),
            ]
        )
    if mixed_source:
        source = character_node("char:duskenlight-source", "Duskenlight Source")
        nodes.append(source)
        edges.append(Edge(source=source.key, target=item.key, type=EdgeType.DROPS_ITEM))
    return build_graph(*nodes, edges=edges)


def test_build_mod_guide_emits_item_bearing_prerequisite_for_quest_rewarded_acquisitionitem_node() -> None:
    graph = _acquisition_item_graph()

    current = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:current")

    assert current["prerequisites"] == [
        {
            "type": "quest",
            "quest_key": "quest:prior",
            "quest_name": "Prior Quest",
            "item": "Duskenlight",
        }
    ]


def test_build_mod_guide_does_not_hide_prerequisite_for_mixed_source_acquisitionitem_node() -> None:
    graph = _acquisition_item_graph(mixed_source=True)

    current = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:current")

    assert current.get("prerequisites", []) == []


def test_build_mod_guide_dedupes_direct_and_item_reward_prerequisites() -> None:
    graph = _acquisition_item_graph(required=True)

    current = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:current")

    assert current["prerequisites"] == [
        {
            "type": "quest",
            "quest_key": "quest:prior",
            "quest_name": "Prior Quest",
            "item": "Duskenlight",
        }
    ]


def test_character_spawns_dedupes_identical_quest_gates() -> None:
    graph, _ = _fixture()
    graph.add_edge(Edge(source="spawn:unlockable", target="quest:main", type=EdgeType.GATED_BY_QUEST))
    graph.build_indexes()

    entry = build_mod_guide(graph, compile_graph(graph))["_character_spawns"]["char:unlockable"][0]

    assert entry["spawn_upon_quest_complete_stable_key"] == "quest:main"


def test_character_spawns_rejects_distinct_quest_gates() -> None:
    graph, _ = _fixture()
    graph.add_edge(Edge(source="spawn:unlockable", target="quest:previous", type=EdgeType.GATED_BY_QUEST))
    graph.build_indexes()

    with pytest.raises(ValueError, match="multiple quest gates"):
        build_mod_guide(graph, compile_graph(graph))


def test_serialize_mod_guide_is_compact_deterministic_and_json() -> None:
    graph, _ = _fixture()
    compiled = compile_graph(graph)
    first = serialize_mod_guide(graph, compiled)
    second = serialize_mod_guide(graph, compiled)

    reversed_graph = EntityGraph()
    for node in reversed(list(graph.all_nodes())):
        reversed_graph.add_node(node)
    for edge in reversed(list(graph.all_edges())):
        reversed_graph.add_edge(edge)
    reversed_graph.build_indexes()

    assert first == second
    assert first == serialize_mod_guide(reversed_graph, compile_graph(reversed_graph))
    assert "\n" not in first
    assert " : " not in first
    parsed = json.loads(first)
    assert list(parsed) == [
        "_version",
        "_zone_lookup",
        "_character_spawns",
        "_zone_lines",
        "_chain_groups",
        "_character_quest_unlocks",
        "quests",
    ]
    assert parsed["_character_spawns"]["char:unlockable"][0] == {
        "scene": "AshenScene",
        "x": 13,
        "y": 14,
        "z": 15,
        "night_spawn": False,
        "is_directly_placed": True,
        "source_script": "VithArenaFight",
        "spawn_upon_quest_complete_stable_key": "quest:main",
    }
    assert all(math.isfinite(value) for value in _finite_floats(parsed))


def _finite_floats(value: object) -> list[float]:
    if isinstance(value, float):
        return [value]
    if isinstance(value, dict):
        return [number for child in value.values() for number in _finite_floats(child)]
    if isinstance(value, list):
        return [number for child in value for number in _finite_floats(child)]
    return []


def _arena_step_graph() -> EntityGraph:
    quest = quest_node("quest:arena", "ARENA", display_name="ARENA")
    token = item_node("item:vith-token", "Vith Token")
    fee = item_node("item:vith-coin", "Vith Coin")
    completer = character_node("char:arena-master", "Arena Master")
    enemy = character_node("char:arena-enemy", "Arena Wave Enemy")
    chest = character_node("char:arena-chest", "Arena Reward Chest")
    return build_graph(
        quest,
        token,
        fee,
        completer,
        enemy,
        chest,
        edges=[
            Edge(source=quest.key, target=token.key, type=EdgeType.REQUIRES_ITEM, quantity=1),
            Edge(source=quest.key, target=completer.key, type=EdgeType.COMPLETED_BY, note="item_turnin"),
            Edge(source=quest.key, target=completer.key, type=EdgeType.STEP_TURN_IN, ordinal=20),
            Edge(source=quest.key, target=fee.key, type=EdgeType.STEP_BUY, ordinal=25, quantity=1),
            Edge(source=quest.key, target=enemy.key, type=EdgeType.STEP_KILL, ordinal=30, quantity=3),
            Edge(source=quest.key, target=chest.key, type=EdgeType.STEP_LOOT, ordinal=40),
        ],
    )


def test_build_mod_guide_emits_arena_steps_in_ordinal_order_and_dedupes_turn_in() -> None:
    graph = _arena_step_graph()
    main = _main_entry(build_mod_guide(graph, compile_graph(graph)), "quest:arena")

    assert main["completion"] == [
        {
            "method": "item_turnin",
            "source_name": "Arena Master",
            "source_type": "character",
            "source_stable_key": "char:arena-master",
            "note": "item_turnin",
        }
    ]
    steps = main["steps"]
    assert [(step["action"], step["target_key"]) for step in steps] == [
        ("collect", "item:vith-token"),
        ("turn_in", "char:arena-master"),
        ("buy", "item:vith-coin"),
        ("kill", "char:arena-enemy"),
        ("loot", "char:arena-chest"),
    ]
    turn_in = steps[1]
    assert "quantity" not in turn_in
    buy = steps[2]
    assert buy["quantity"] == 1
    assert buy["description"] == "Buy Vith Coin."
    kill = steps[3]
    assert kill["quantity"] == 3
    assert kill["description"] == "Defeat 3x Arena Wave Enemy."
    loot = steps[4]
    assert "quantity" not in loot
    assert loot["description"] == "Loot Arena Reward Chest."
    assert sum(step["action"] == "turn_in" for step in steps) == 1


def _workflow_projection_graph() -> EntityGraph:
    trigger_item = item_node("item:arena-fee", "Arena Fee")
    location = Node(
        key="guide-location:arena:one",
        type=NodeType.LOCATION,
        display_name="Arena entrance",
        scene="ArenaScene",
        zone="Arena Zone",
        x=10.0,
        y=20.0,
        z=30.0,
        trigger_bounds_center_x=11.0,
        trigger_bounds_center_y=21.0,
        trigger_bounds_center_z=31.0,
        trigger_bounds_extents_x=4.0,
        trigger_bounds_extents_y=5.0,
        trigger_bounds_extents_z=6.0,
        guide_only=True,
    )
    target = character_node("character:arena-target", "Arena Target", level=40)
    reward = character_node("character:arena-reward", "Arena Reward")
    drop_source = character_node("character:previous-chest", "Previous Chest")
    vendor_a = character_node("character:vendor-a", "Vendor A", scene="ArenaScene", zone="Arena Zone")
    vendor_b = character_node("character:vendor-b", "Vendor B", scene="ArenaScene", zone="Arena Zone")
    unlock_a = quest_node("quest:unlock-a", "UNLOCK_A", display_name="Unlock Vendor A")
    unlock_b = quest_node("quest:unlock-b", "UNLOCK_B", display_name="Unlock Vendor B")
    workflow = quest_node(
        "guide-quest:arena:one",
        "guide.arena.one",
        display_name="Arena Round One",
        implicit=True,
        repeatable=True,
        guide_only=True,
        workflow_cycle=WorkflowCycle(
            trigger_item_stable_key=trigger_item.key,
            trigger_item_quantity=1,
            trigger_mode="proximity_auto_consume",
            location_stable_key=location.key,
            targets=[WorkflowTarget(stable_key=target.key, quantity=2)],
            reward_container_stable_key=reward.key,
            reset_evidence="reward_container_consumed",
        ),
    )
    return build_graph(
        workflow,
        unlock_a,
        unlock_b,
        trigger_item,
        location,
        target,
        reward,
        drop_source,
        vendor_a,
        vendor_b,
        edges=[
            Edge(source=workflow.key, target=trigger_item.key, type=EdgeType.REQUIRES_ITEM, quantity=1),
            Edge(source=workflow.key, target=location.key, type=EdgeType.STEP_GO_TO, ordinal=0),
            Edge(source=workflow.key, target=target.key, type=EdgeType.STEP_KILL, ordinal=1, quantity=2),
            Edge(source=workflow.key, target=reward.key, type=EdgeType.STEP_LOOT, ordinal=2),
            Edge(source=drop_source.key, target=trigger_item.key, type=EdgeType.DROPS_ITEM),
            Edge(source=vendor_a.key, target=trigger_item.key, type=EdgeType.SELLS_ITEM),
            Edge(source=vendor_b.key, target=trigger_item.key, type=EdgeType.SELLS_ITEM),
            Edge(
                source=unlock_a.key,
                target=trigger_item.key,
                type=EdgeType.UNLOCKS_VENDOR_ITEM,
                note=vendor_a.key,
            ),
            Edge(
                source=unlock_b.key,
                target=trigger_item.key,
                type=EdgeType.UNLOCKS_VENDOR_ITEM,
                note=vendor_b.key,
            ),
        ],
    )


def test_build_mod_guide_projects_workflow_inside_unified_quest_contract() -> None:
    graph = _workflow_projection_graph()
    compiled = compile_graph(graph)
    first = serialize_mod_guide(graph, compiled)
    assert first == serialize_mod_guide(graph, compiled)

    data = json.loads(first)
    assert "encounters" not in data
    workflow = _main_entry(data, "guide-quest:arena:one")
    assert workflow["flags"]["guide_only"] is True
    assert workflow["acceptance"] == "implicit"
    assert workflow["zone_context"] == "Arena Zone"
    assert [step["action"] for step in workflow["steps"]] == ["obtain", "go_to", "kill", "loot"]

    obtain = workflow["steps"][0]
    vendors = {source["name"]: source for source in obtain["sources"] if source["type"] == "vendor"}
    assert set(vendors) == {"Vendor A", "Vendor B"}
    assert vendors["Vendor A"]["instruction"] == "Buy Arena Fee."
    assert vendors["Vendor A"]["required_quest_db_names"] == ["UNLOCK_A"]
    assert vendors["Vendor B"]["instruction"] == "Buy Arena Fee."
    assert vendors["Vendor B"]["required_quest_db_names"] == ["UNLOCK_B"]
    assert any(source["type"] == "drop" and source["name"] == "Previous Chest" for source in obtain["sources"])

    go_to = workflow["steps"][1]
    assert go_to["description"] == "Go to Arena entrance."
    assert go_to["location"] == {
        "stable_key": "guide-location:arena:one",
        "display_name": "Arena entrance",
        "scene": "ArenaScene",
        "x": 10.0,
        "y": 20.0,
        "z": 30.0,
    }
    assert workflow["workflow_cycle"] == {
        "trigger": {
            "item_stable_key": "item:arena-fee",
            "item_name": "Arena Fee",
            "quantity": 1,
            "mode": "proximity_auto_consume",
            "consumes_item_automatically": True,
            "location": {
                **go_to["location"],
                "bounds": {
                    "center": {"x": 11.0, "y": 21.0, "z": 31.0},
                    "extents": {"x": 4.0, "y": 5.0, "z": 6.0},
                },
            },
        },
        "targets": [{"stable_key": "character:arena-target", "display_name": "Arena Target", "quantity": 2}],
        "reset_evidence": "reward_container_consumed",
        "reward_container": {"stable_key": "character:arena-reward", "display_name": "Arena Reward"},
    }


def test_build_mod_guide_rejects_invalid_workflow_projection_metadata() -> None:
    graph = _workflow_projection_graph()
    compiled = compile_graph(graph)
    location_id = compiled.node_key_to_id["guide-location:arena:one"]
    compiled.nodes[location_id].x = math.nan

    with pytest.raises(ValueError, match="invalid x coordinate"):
        build_mod_guide(graph, compiled)

    compiled = compile_graph(graph)
    workflow_spec = next(spec for spec in compiled.quest_specs if spec.is_guide_only)
    assert workflow_spec.workflow_cycle is not None
    workflow_spec.workflow_cycle.reset_evidence = ""

    with pytest.raises(ValueError, match="invalid reset evidence"):
        build_mod_guide(graph, compiled)


def test_build_mod_guide_rejects_real_and_synthetic_db_name_collision() -> None:
    real = quest_node("quest:real", "REAL")
    synthetic = quest_node("guide-quest:one", "guide.one", implicit=True)
    graph = build_graph(real, synthetic)
    compiled = compile_graph(graph)
    synthetic.db_name = "REAL"

    with pytest.raises(ValueError, match="duplicate quest db_name"):
        build_mod_guide(graph, compiled)
