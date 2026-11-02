"""Consumer-visible canonical source contracts through the producer and repository."""

from __future__ import annotations

from dataclasses import replace

import pytest

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.mod_writer import build_mod_guide, serialize_mod_guide
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceLocation,
)
from erenshor.domain.value_objects.item_public_view import PublicCondition, PublicUse

from .fixtures import build_graph, character_node, item_node, load_canonical_sources, quest_node, spawn_node
from .wire import assert_wire_roundtrip


def _graph():
    return build_graph(
        quest_node("quest:main", "MAIN"),
        quest_node("quest:reward", "REWARD"),
        item_node("item:result"),
        item_node("item:input"),
        item_node("item:mold"),
        character_node("character:source", "Source"),
        Node("water:source", NodeType.WATER, "Water"),
        Node("mining:source", NodeType.MINING_NODE, "Ore"),
        Node("bag:source", NodeType.ITEM_BAG, "Bag"),
    )


def _required(key="required", variant=None, quality=None):
    conditions = (
        ()
        if quality is None
        else (ProvenanceCondition("quality", 0, 0, "quality", value=quality, phase="operation_input"),)
    )
    return ItemUse(
        key,
        "item:result",
        "quest:main",
        "quest_requirement",
        variant_key=variant,
        material_slot=3,
        quantity_min=2,
        quantity_max=2,
        quantity_kind="exact",
        conditions=conditions,
    )


def _payload(graph):
    return build_mod_guide(graph, compile_graph(graph))


def _sources(payload):
    references = next(quest for quest in payload["quests"] if quest["db_name"] == "MAIN")["required_items"][0][
        "sources"
    ]
    return [_resolved_source(payload, reference) for reference in references]


def _resolved_source(payload, reference):
    source = {**payload["_sources"][reference["acquisition_key"]], **reference}
    if "children" in source:
        source["children"] = [
            {**child, "children": [_resolved_source(payload, nested) for nested in child.get("children", [])]}
            for child in source["children"]
        ]
    return source


@pytest.mark.parametrize("kind", ["quest_reward", "dialog", "vendor"])
def test_noncombat_actor_copy_is_preserved_without_a_combat_node(tmp_path, kind):
    graph = _graph()
    actor = "character:noncombat"
    fact = ItemAcquisition(
        "noncombat",
        "item:result",
        kind,
        "quest:reward" if kind == "quest_reward" else actor,
        source_copy_stable_key=actor,
        variant_key="2",
        location_source_key=actor,
        locations=(ProvenanceLocation("trade-site", "fixed", scene="Town", x=4, y=5, z=6),),
    )
    metadata = (
        "INSERT INTO characters(stable_key,object_name,npc_name,display_name,image_name,"
        "encounter_tier,level_scales_with_player,can_be_damaged,invulnerable,is_map_visible)"
        " VALUES ('character:noncombat','Actor','Actor','Actor','','npc',0,0,1,0);"
        "INSERT INTO character_dialogs(character_stable_key,dialog_index,keywords)"
        " VALUES ('character:noncombat',2,'TRADE');"
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()], metadata)
    payload = _payload(graph)
    [source] = _sources(payload)
    assert source["source_key"] == actor
    [place] = payload["_place_sets"][source["place_set_key"]]
    assert place["place_key"] == "0"
    assert graph.get_node(actor).invulnerable
    if kind == "quest_reward":
        assert source["quest_key"] == "quest:reward"
        reward_quest = next(quest for quest in payload["quests"] if quest["db_name"] == "REWARD")
        assert reward_quest["rewards"]["item_stable_key"] == "item:result"
    assert graph.source_facts["noncombat"].source_key == "noncombat"


@pytest.mark.parametrize(
    "kind,source,expected",
    [
        ("character_drop", "character:source", "drop"),
        ("vendor", "character:source", "vendor"),
        ("quest_reward", "quest:reward", "quest_reward"),
        ("mining", "mining:source", "mining"),
        ("fishing", "water:source", "fishing"),
        ("item_bag", "bag:source", "pickup"),
        ("common_world_item", None, "common_world_item"),
        ("special_world_drop", None, "world_drop"),
        ("fishing_bonus", None, "fishing_bonus"),
        ("starting_class", None, "starting_class"),
        ("ui_grant", None, "ui_grant"),
    ],
)
def test_canonical_families_keep_actual_location_and_normalize_facts_once(tmp_path, kind, source, expected):
    graph = _graph()
    fact = ItemAcquisition(
        "actual",
        "item:result",
        kind,
        source,
        variant_key="native-variant",
        mechanic="native-mechanic",
        probability_kind="bounded",
        probability_min=0.00001,
        probability_max=0.00002,
        quantity_min=2,
        quantity_max=4,
        quantity_kind="bounded",
        expected_quantity=3,
        location_source_key="source:actual",
        locations=(
            ProvenanceLocation(
                "location:actual",
                "fixed",
                scene="ActualScene",
                x=17,
                y=18,
                z=19,
                entry_zone_line_keys=("line:actual",),
            ),
        ),
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    payload = _payload(graph)
    [row] = _sources(payload)
    assert row["type"] == expected
    assert (row["chance"], row["chance_max"]) == (0.00001, 0.00002)
    [place] = payload["_place_sets"][row["place_set_key"]]
    assert (place["place_key"], place["scene"], place["x"], place["y"], place["z"]) == (
        "0",
        "ActualScene",
        17,
        18,
        19,
    )
    assert place["entry_zone_line_keys"] == ["line:actual"]
    assert not {"acquisition_key", "location_key", "scene", "x", "y", "z", "children"}.intersection(
        payload["_sources"]["actual"]
    )
    assert payload["_version"] == 11
    assert "_source_facts" not in payload
    assert payload["_item_uses"]["required"]["material_slot"] == 3


def test_public_auction_house_is_a_guide_source(tmp_path):
    graph = _graph()
    fact = ItemAcquisition("listed", "item:result", "auction_house", "mechanic:auction_house")
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    [source] = _sources(_payload(graph))
    assert source["type"] == "auction_house"
    assert source["source_key"] == "mechanic:auction_house"


def test_repeated_recipe_slots_mold_and_requested_output_quality_are_traversable(tmp_path):
    graph = _graph()
    location = ProvenanceLocation("vendor-location", "fixed", scene="Town", x=4, y=5, z=6)
    facts = [
        ItemAcquisition(
            "crafted",
            "item:result",
            "crafting",
            "item:mold",
            variant_key="native-result",
            conditions=(
                ProvenanceCondition("result-quality", 0, 0, "quality", value="perfect", phase="operation_outcome"),
            ),
        ),
        ItemAcquisition(
            "wrong-quality",
            "item:result",
            "crafting",
            "item:mold",
            variant_key="other-result",
            conditions=(
                ProvenanceCondition("result-quality", 0, 0, "quality", value="normal", phase="operation_outcome"),
            ),
        ),
        ItemAcquisition(
            "material-source",
            "item:input",
            "vendor",
            "character:source",
            location_source_key="character:source",
            locations=(location,),
        ),
        ItemAcquisition(
            "mold-source",
            "item:mold",
            "vendor",
            "character:source",
            location_source_key="character:source",
            locations=(location,),
        ),
    ]
    materials = [
        ItemUse(
            f"material:{slot}",
            "item:input",
            "item:mold",
            "crafting_material",
            material_slot=slot,
            quantity_min=quantity,
            quantity_max=quantity,
            quantity_kind="exact",
        )
        for slot, quantity in ((1, 2), (2, 3))
    ]
    recipe = ItemUse(
        "recipe",
        "item:mold",
        "item:result",
        "crafting_recipe",
        outcome_key="crafted",
        variant_key="native-result",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    wrong_recipe = replace(recipe, use_key="wrong-recipe", outcome_key="wrong-quality", variant_key="other-result")
    load_canonical_sources(tmp_path, graph, facts, [_required(quality="perfect"), *materials, recipe, wrong_recipe])
    payload = _payload(graph)
    [source] = _sources(payload)
    assert source["acquisition_key"] == "crafted"
    assert source["output_quality"] == "perfect"
    assert {row["use_key"]: row["quantity"] for row in source["children"]} == {
        "material:1": 2,
        "material:2": 3,
        "recipe": 1,
    }
    for ingredient in source["children"]:
        assert ingredient["type"] == "ingredient"
        nested = ingredient["children"][0]
        [place] = payload["_place_sets"][nested["place_set_key"]]
        assert place["place_key"] == "0"
    assert {payload["_item_uses"][f"material:{slot}"]["material_slot"] for slot in (1, 2)} == {1, 2}
    assert "wrong-quality" in payload["_sources"]


@pytest.mark.parametrize("kind", ["item_drop", "spell_created", "item_conversion"])
def test_item_operation_inputs_are_real_use_children(tmp_path, kind):
    graph = _graph()
    result = ItemAcquisition("result", "item:result", kind, "item:input", variant_key="operation")
    material = ItemAcquisition(
        "input-source",
        "item:input",
        "item_bag",
        "bag:source",
        location_source_key="bag:source",
        locations=(ProvenanceLocation("bag-location", "fixed", scene="Forest", x=1, y=2, z=3),),
    )
    use = ItemUse(
        "operation-input",
        "item:input",
        "item:result",
        kind,
        variant_key="operation",
        outcome_key="result",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    load_canonical_sources(tmp_path, graph, [result, material], [_required(), use])
    payload = _payload(graph)
    [source] = _sources(payload)
    assert source["type"] == "item_use"
    [child] = source["children"]
    assert child["use_key"] == "operation-input"
    assert child["item_stable_key"] == "item:input"
    assert child["children"][0]["acquisition_key"] == "input-source"


@pytest.mark.parametrize(
    ("slots", "expected"),
    [
        (
            [("octo", "item:result", slot, 1) for slot in range(4)],
            [("octo", "item:result", 4)],
        ),
        (
            [("bundle", "item:result", 0, 1), ("bundle", "item:input", 1, 2)],
            [("bundle", "item:input", 2), ("bundle", "item:result", 1)],
        ),
        (
            [
                ("a", "item:result", 0, 1),
                ("a", "item:result", 1, 2),
                ("a", "item:input", 2, 1),
                ("b", "item:result", 0, 3),
                ("b", "item:result", 1, 4),
                ("b", "item:input", 2, 2),
            ],
            [
                ("a", "item:input", 1),
                ("a", "item:result", 3),
                ("b", "item:input", 2),
                ("b", "item:result", 7),
            ],
        ),
        (
            [("a", "item:result", 0, 2), ("b", "item:result", 0, 3)],
            [("a", "item:result", 2), ("b", "item:result", 3)],
        ),
        (
            [(None, "item:result", 0, 1), (None, "item:result", 1, 2), (None, "item:input", 2, 1)],
            [(None, "item:input", 1), (None, "item:result", 3)],
        ),
    ],
    ids=["octorunners-four-slots", "mixed-item-and", "repeated-items-in-two-bundles", "single-slot-or", "ordinary-and"],
)
def test_native_requirement_bundles_aggregate_without_losing_slots(tmp_path, slots, expected):
    graph = _graph()
    facts = [
        ItemAcquisition(f"vendor:{item}:{alternative}", item, "vendor", "character:source")
        for item in ("item:result", "item:input")
        for alternative in ("first", "second")
    ]
    uses = [
        replace(
            _required(f"slot:{variant}:{slot}", variant),
            item_stable_key=item,
            material_slot=slot,
            quantity_min=quantity,
            quantity_max=quantity,
        )
        for variant, item, slot, quantity in slots
    ]
    load_canonical_sources(tmp_path, graph, facts, uses)
    payload = _payload(graph)
    quest = next(row for row in payload["quests"] if row["db_name"] == "MAIN")
    assert [
        (row.get("variant_key"), row["item_stable_key"], row["quantity"]) for row in quest["required_items"]
    ] == expected
    assert [
        (step.get("requirement_variant"), step["target_key"], step["quantity"])
        for step in quest["steps"]
        if step["action"] == "collect"
    ] == expected
    assert all("or_group" not in row and "use_key" not in row for row in quest["required_items"])
    assert all("or_group" not in step for step in quest["steps"] if step["action"] == "collect")
    for row in quest["required_items"]:
        assert row["use_keys"] == sorted(
            use.use_key
            for use in uses
            if use.variant_key == row.get("variant_key") and use.item_stable_key == row["item_stable_key"]
        )
        assert {source["acquisition_key"] for source in row["sources"]} == {
            f"vendor:{row['item_stable_key']}:{alternative}" for alternative in ("first", "second")
        }
    for use in uses:
        serialized = payload["_item_uses"][use.use_key]
        assert serialized.get("material_slot", 0) == use.material_slot
        assert serialized["quantity_min"] == serialized["quantity_max"] == use.quantity_min
        assert serialized.get("variant_key") == use.variant_key
        assert "mechanic" not in serialized


def test_native_requirement_aggregation_keeps_requested_quality_separate(tmp_path):
    graph = _graph()
    uses = [
        replace(_required(f"{quality}:{slot}", "bundle", quality), material_slot=slot)
        for quality in ("normal", "perfect")
        for slot in range(2)
    ]
    facts = [
        ItemAcquisition(
            f"vendor:{quality}",
            "item:result",
            "vendor",
            "character:source",
            conditions=(ProvenanceCondition("quality", 0, 0, "quality", value=quality, phase="operation_outcome"),),
        )
        for quality in ("normal", "perfect")
    ]
    load_canonical_sources(tmp_path, graph, facts, uses)
    payload = _payload(graph)
    quest = next(row for row in payload["quests"] if row["db_name"] == "MAIN")
    assert [(row["output_quality"], row["quantity"]) for row in quest["required_items"]] == [
        ("normal", 4),
        ("perfect", 4),
    ]
    for row in quest["required_items"]:
        assert row["use_keys"] == [f"{row['output_quality']}:{slot}" for slot in range(2)]
        assert [source["acquisition_key"] for source in row["sources"]] == [f"vendor:{row['output_quality']}"]
    assert set(payload["_item_uses"]) == {use.use_key for use in uses}
    assert [
        (step["requirement_variant"], step["output_quality"], step["quantity"])
        for step in quest["steps"]
        if step["action"] == "collect"
    ] == [("bundle", "normal", 4), ("bundle", "perfect", 4)]


@pytest.mark.parametrize("quantity", [None, -1, 0.5, float("inf"), float("nan"), True])
def test_native_requirement_aggregation_rejects_nonintegral_slot_quantities(quantity):
    graph = _graph()
    graph.quest_uses[("quest:main", "item:result")] = [
        PublicUse(
            "required",
            "item:result",
            "quest:main",
            "quest_requirement",
            None,
            3,
            "exact",
            quantity,
            quantity,
            None,
            None,
            None,
        )
    ]
    with pytest.raises(ValueError, match="Quest requirement has no integer quantity: required"):
        _payload(graph)


@pytest.mark.parametrize("maximum,kind", [(2, "bounded"), (1, "unknown"), (None, "unknown")])
def test_native_requirement_aggregation_rejects_uncertain_slot_quantities(maximum, kind):
    graph = _graph()
    graph.quest_uses[("quest:main", "item:result")] = [
        PublicUse(
            "required",
            "item:result",
            "quest:main",
            "quest_requirement",
            None,
            3,
            kind,
            1,
            maximum,
            None,
            None,
            None,
        )
    ]
    with pytest.raises(ValueError, match="integer quantity"):
        _payload(graph)


def test_public_conditions_preserve_indices_actors_bounds_and_phases(tmp_path):
    graph = _graph()
    conditions = (
        ProvenanceCondition("level", 0, 0, "actor_level", actor="player", minimum=20),
        ProvenanceCondition("quality", 0, 0, "quality", value="perfect", phase="operation_outcome"),
    )
    fact = ItemAcquisition("actual", "item:result", "vendor", "character:source", conditions=conditions)
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    payload = _payload(graph)
    actual = payload["_sources"]["actual"]["conditions"]
    assert {row["predicate"] for row in actual} == {"actor_level", "quality"}
    assert [
        (row.get("gate_index", 0), row.get("alternative_index", 0), row.get("atom_index", 0)) for row in actual
    ] == [(0, 0, 0), (1, 0, 0)]
    assert all("phase" in row for row in actual)
    assert all(
        value != 0
        for row in actual
        for key, value in row.items()
        if key in {"gate_index", "alternative_index", "atom_index"}
    )
    assert all(not {"minimum_inclusive", "maximum_inclusive"} & row.keys() for row in actual)
    assert all(not {"scope", "group_index"}.intersection(row) for row in actual)
    level = next(row for row in actual if row["predicate"] == "actor_level")
    assert (level["actor"], level["minimum"]) == ("player", 20)
    quality = next(row for row in actual if row["predicate"] == "quality")
    assert (quality["value"], quality["phase"]) == ("perfect", "operation_outcome")
    assert "_source_facts" not in payload


def test_no_location_native_actions_do_not_borrow_graph_coordinates(tmp_path):
    graph = _graph()
    fact = ItemAcquisition("ui", "item:result", "ui_grant", None)
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    [source] = _sources(_payload(graph))
    assert not {"location_key", "scene", "x", "y", "z"}.intersection(source)


def test_smithing_byproduct_keeps_equipment_and_fuel_as_alternatives(tmp_path):
    graph = _graph()
    fact = ItemAcquisition(
        "smithing-output",
        "item:result",
        "crafting",
        "item:mold",
        mechanic="remove_blessing",
        conditions=(ProvenanceCondition("equipment", 0, 0, "quality", minimum=2, maximum=3, phase="operation_input"),),
    )
    uses = [
        ItemUse(
            f"smithing:{index}",
            item,
            "item:mold",
            "smithing",
            outcome_key=fact.acquisition_key,
            mechanic=role,
            quantity_min=1,
            quantity_max=1,
            quantity_kind="exact",
        )
        for index, (item, role) in enumerate(
            (
                ("item:mold", "blessing_removal_material"),
                ("item:input", "remove_blessing"),
                ("item:result", "remove_blessing"),
                ("item:input", "blessing_removal_fuel"),
                ("item:result", "blessing_removal_fuel"),
            )
        )
    ]
    load_canonical_sources(tmp_path, graph, [fact], [_required(), *uses])
    payload = _payload(graph)
    [source] = _sources(payload)
    assert source["type"] == "item_use"
    assert "recipe_key" not in source
    assert "operation_use_keys" not in source
    assert source["operation_context"] > 0
    assert [child["use_key"] for child in source["children"]] == ["smithing:0"]
    assert {key for key in payload["_item_uses"] if key.startswith("smithing:")} == {"smithing:0"}
    assert payload["_sources"][fact.acquisition_key]["conditions"][0]["phase"] == "operation_input"


@pytest.mark.parametrize("quantity,kind", [(None, "unknown"), (1.5, "exact")])
def test_quest_counts_cannot_silently_default_or_truncate(tmp_path, quantity, kind):
    graph = _graph()
    required = replace(_required(), quantity_min=quantity, quantity_max=quantity, quantity_kind=kind)
    load_canonical_sources(tmp_path, graph, [], [required])
    with pytest.raises(ValueError, match="integer quantity"):
        _payload(graph)


def test_each_source_carries_the_lowest_rank_of_its_acquisitions_ways_to_its_item(tmp_path):
    graph = _graph()
    ranked = ItemAcquisition("ranked", "item:result", "ui_grant", None)
    unranked = ItemAcquisition("unranked", "item:result", "ui_grant", None)
    ways = [
        ("item:result", "slow", 5, 9, "ranked"),
        ("item:result", "early", 4, 12, "ranked"),
        ("item:result", "blocked", None, None, "unranked"),
        ("item:other", "elsewhere", 0, 0, "unranked"),
    ]
    sql = "".join(
        f"INSERT OR IGNORE INTO progression_nodes VALUES ('{node}','item',0,NULL,NULL);"
        f"INSERT INTO progression_ways VALUES ('{node}','{way}',{tier if tier is not None else 'NULL'},"
        f"{depth if depth is not None else 'NULL'});"
        f"INSERT INTO progression_way_facts VALUES ('{node}','{way}','{fact}');"
        for node, way, tier, depth, fact in ways
    )
    load_canonical_sources(tmp_path, graph, [ranked, unranked], [_required()], raw_outcomes_sql=sql)

    payload = _payload(graph)
    assert "_source_ranks" not in payload
    assert payload["_sources"]["ranked"]["rank"] == {"tier": 4, "depth": 12}
    assert "rank" not in payload["_sources"]["unranked"]


def test_wire_roundtrip_preserves_all_sources_for_referenced_items_only(tmp_path):
    graph = _graph()
    graph.add_node(item_node("item:unrelated"))
    facts = [
        ItemAcquisition(
            "chosen",
            "item:result",
            "item_conversion",
            "item:input",
            variant_key="chosen",
            conditions=(ProvenanceCondition("quality", 0, 0, "quality", value="perfect", phase="operation_outcome"),),
        ),
        ItemAcquisition(
            "excluded-variant",
            "item:result",
            "ui_grant",
            None,
            conditions=(ProvenanceCondition("quality", 0, 0, "quality", value="normal", phase="operation_outcome"),),
        ),
        ItemAcquisition(
            "recursive-source",
            "item:input",
            "vendor",
            "character:source",
            location_source_key="character:source",
            locations=(
                ProvenanceLocation("first-place", "fixed", scene="Town", x=1, y=2, z=3),
                ProvenanceLocation("second-place", "fixed", scene="Forest", x=4, y=5, z=6),
            ),
        ),
        ItemAcquisition("recursive-alternative", "item:input", "ui_grant", None),
        ItemAcquisition("unrelated", "item:unrelated", "ui_grant", None),
    ]
    use = ItemUse(
        "conversion-input",
        "item:input",
        "item:result",
        "item_conversion",
        variant_key="chosen",
        outcome_key="chosen",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    load_canonical_sources(tmp_path, graph, facts, [_required(quality="perfect"), use])
    compiled = compile_graph(graph)
    semantic = build_mod_guide(graph, compiled)
    serialized = serialize_mod_guide(graph, compiled)
    assert serialized == serialize_mod_guide(graph, compiled)
    assert_wire_roundtrip(serialized, semantic)
    assert set(semantic["_sources"]) == {
        "chosen",
        "excluded-variant",
        "recursive-source",
        "recursive-alternative",
    }
    [source] = _sources(semantic)
    assert source["acquisition_key"] == "chosen"
    assert {nested["acquisition_key"] for nested in source["children"][0]["children"]} == {
        "recursive-source",
        "recursive-alternative",
    }
    places = semantic["_place_sets"][semantic["_sources"]["recursive-source"]["place_set_key"]]
    assert [place["place_key"] for place in places] == ["0", "1"]
    public_places = graph.source_places[semantic["_sources"]["recursive-source"]["place_set_key"]]
    assert [place["scene"] for place in places] == [place.scene for place in public_places]
    assert set(semantic["_item_uses"]) == {"required", "conversion-input"}


def test_marker_backed_places_omit_only_recoverable_fields_and_keep_public_conditions(tmp_path):
    graph = _graph()
    graph.add_node(spawn_node("spawn:source", scene="Town", x=1, y=2, z=3))
    graph.add_node(Node("zone:town", NodeType.ZONE, "Town", scene="Town"))
    graph.add_edge(Edge("character:source", "spawn:source", EdgeType.HAS_SPAWN))
    graph.build_indexes()
    fact = ItemAcquisition(
        "located",
        "item:result",
        "vendor",
        "character:source",
        location_source_key="character:source",
        locations=(
            ProvenanceLocation("first", "fixed", scene="Town", x=1, y=2, z=3),
            ProvenanceLocation("second", "fixed", scene="Town", x=4, y=5, z=6),
        ),
    )
    load_canonical_sources(tmp_path, graph, [fact], [_required()])
    public = graph.source_facts["located"]
    assert public.place_set_key is not None
    condition = PublicCondition(
        1,
        2,
        3,
        "bounded",
        "actor_level",
        actor="player",
        minimum=4,
        maximum=9,
        minimum_inclusive=False,
        maximum_inclusive=False,
    )
    places = graph.source_places[public.place_set_key]
    graph.source_places[public.place_set_key] = (
        replace(
            places[0],
            marker_stable_key="spawn:source",
            zone_stable_key="zone:town",
            conditions=(condition,),
        ),
        replace(
            places[1],
            marker_stable_key="spawn:not-exported",
            zone_stable_key="zone:town",
            conditions=(condition,),
        ),
    )
    compiled = compile_graph(graph)
    semantic = build_mod_guide(graph, compiled)
    first, second = semantic["_place_sets"][public.place_set_key]
    assert [first["place_key"], second["place_key"]] == ["0", "1"]
    assert not {"scene", "x", "y", "z", "zone", "zone_stable_key"} & first.keys()
    assert second["scene"] == "Town"
    assert second["zone"] == "Town"
    assert second["zone_stable_key"] == "zone:town"
    for place in (first, second):
        [atom] = place["conditions"]
        assert PublicCondition(**atom) == condition
        assert atom["minimum_inclusive"] is atom["maximum_inclusive"] is False
        assert (atom["gate_index"], atom["alternative_index"], atom["atom_index"]) == (1, 2, 3)
        assert all(value is not None for value in atom.values())
        assert place.get("entry_zone_line_keys", []) == []
    assert_wire_roundtrip(serialize_mod_guide(graph, compiled), semantic)
