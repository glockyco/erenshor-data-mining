"""Behavioral tests for the AdventureGuide compatibility wrapper."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.mod_writer import build_mod_guide, serialize_mod_guide
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


def _graph(*nodes: Node, edges: list[Edge] | None = None) -> EntityGraph:
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    graph.build_indexes()
    return graph


def _quest(key: str, db_name: str, **kwargs: object) -> Node:
    return Node(
        key=key,
        type=NodeType.QUEST,
        display_name=kwargs.pop("display_name", db_name),
        db_name=db_name,
        **kwargs,
    )


def _item(key: str, name: str | None = None) -> Node:
    return Node(key=key, type=NodeType.ITEM, display_name=name or key)


def _character(key: str, name: str | None = None, **kwargs: object) -> Node:
    return Node(key=key, type=NodeType.CHARACTER, display_name=name or key, **kwargs)


def _fixture() -> tuple[EntityGraph, dict[str, object]]:
    """Build one small graph exercising every legacy wrapper section."""
    main = _quest(
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
    previous = _quest("quest:previous", "PREVIOUS", display_name="Previous Quest")
    alternate = _quest("quest:alternate", "ALTERNATE", display_name="Alternate Quest")
    second = _quest("quest:second", "SECOND", display_name="Second Quest")
    also = _quest("quest:also", "ALSO", display_name="Also Quest")

    giver = _character(
        "char:giver",
        "Quest Giver",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        x=1,
        y=2,
        z=3,
    )
    completer = _character(
        "char:completer",
        "Quest Completer",
        scene="AshenScene",
        zone="Ashen Vale",
        zone_key="zone:ashen",
        x=4,
        y=5,
        z=6,
    )
    mob = _character(
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
    unlockable = _character(
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

    item_a = _item("item:alpha", "Alpha Relic")
    item_b = _item("item:beta", "Beta Relic")
    reward = _item("item:reward", "Reward Relic")
    read_item = _item("item:read", "Ancient Tablet")
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
    graph = _graph(
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
    assert data["_version"] == 5
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
    quest = _quest("quest:resource", "RESOURCE")
    item = _item("item:resource", "Resource Item")
    source = Node(
        key=f"{source_type.value}:source",
        type=source_type,
        display_name=f"{source_type.value.title()} Source",
        scene="ResourceScene",
        zone="Resource Zone",
        zone_key="zone:resource",
        level=9,
    )
    return _graph(
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
        character = _character("char:coordinate", "Coordinate Character")
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
        return _graph(character, spawn, edges=[Edge(source=character.key, target=spawn.key, type=EdgeType.HAS_SPAWN)])
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
    return _graph(replace(line, **{field: value}))


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
    quest = _quest("quest:vendor", "VENDOR")
    item = _item("item:vendor", "Vendor Unlock Item")
    vendor = _character("char:vendor", "Unlock Vendor", is_vendor=True)
    edges = [Edge(source=quest.key, target=item.key, type=EdgeType.UNLOCKS_VENDOR_ITEM, note=vendor.key)]
    nodes = [quest, item, vendor]
    if multiple:
        second_item = _item("item:vendor-second", "Second Vendor Item")
        nodes.append(second_item)
        edges.append(Edge(source=quest.key, target=second_item.key, type=EdgeType.UNLOCKS_VENDOR_ITEM, note=vendor.key))
    return _graph(*nodes, edges=edges)


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
    quest = _quest("quest:item-step", "ITEM_STEP")
    item = _item("item:item-step", "Read Me")
    source = _character("char:item-source", "Item Source", level=11)
    return _graph(
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
    quest = _quest("quest:levels", "LEVELS")
    zone = Node(
        key="zone:levels",
        type=NodeType.ZONE,
        display_name="Level Zone",
        zone="Level Zone",
        level=16,
        level_min=16,
        level_max=16,
    )
    character = _character("char:levels", "Level Character", zone="Level Zone", level=12)
    source = _character("char:dropper", "Level Dropper", zone="Level Zone", level=18)
    second_source = _character("char:dropper2", "Another Dropper", zone="Level Zone", level=14)
    item = _item("item:levels", "Level Item")
    return _graph(
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
    prior = _quest("quest:prior", "PRIOR", display_name="Prior Quest")
    current = _quest("quest:current", "CURRENT", display_name="Duskenlight Quest")
    item = _item("item:duskenlight", "Duskenlight")
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
        source = _character("char:duskenlight-source", "Duskenlight Source")
        nodes.append(source)
        edges.append(Edge(source=source.key, target=item.key, type=EdgeType.DROPS_ITEM))
    return _graph(*nodes, edges=edges)


def test_build_mod_guide_emits_item_bearing_prerequisite_for_quest_rewarded_acquisition_item() -> None:
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


def test_build_mod_guide_does_not_hide_prerequisite_for_mixed_source_acquisition_item() -> None:
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
