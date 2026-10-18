from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import asdict

import pytest

from erenshor.application.processor.progression import (
    ACQUISITION_RELATIONS,
    Need,
    ProgressionBuilder,
    canonical_way,
    process_progression,
    way_key,
)
from erenshor.application.processor.writer import _DDL
from erenshor.domain.value_objects.item_provenance import ProvenanceCondition


def insert(conn: sqlite3.Connection, table: str, **values: object) -> None:
    columns = ",".join(values)
    placeholders = ",".join("?" for _ in values)
    conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(_DDL)
    for scene in ("Start", "End", "Other"):
        insert(
            connection,
            "zones",
            stable_key="zone:" + scene.lower(),
            scene_name=scene,
            zone_name=scene,
            display_name=scene,
            image_name=scene,
            zone_type="Outdoor",
        )
    for key in ("quest:q", "quest:other", "quest:gate"):
        insert(connection, "quests", stable_key=key, display_name=key, image_name=key)
    for key in ("item:result", "item:input", "item:material", "item:key", "item:rune"):
        insert(connection, "items", stable_key=key, display_name=key, image_name=key)
    for key in ("character:copy", "character:ward", "character:other"):
        insert(
            connection,
            "characters",
            stable_key=key,
            display_name=key,
            image_name=key,
            encounter_tier="npc",
            can_be_damaged=1,
            invulnerable=0,
            level_scales_with_player=0,
        )
        insert(
            connection,
            "character_spawns",
            character_stable_key=key,
            spawn_point_stable_key="spawn:" + key,
            zone_stable_key="zone:start",
            scene="Start",
            is_directly_placed=1,
        )
    insert(connection, "classes", class_name="Fighter")
    for fact, scene in (
        ("progression.new_character_scene", "Start"),
        ("progression.alternate_start_scene", "Other"),
    ):
        insert(connection, "code_facts", fact_id=fact, key="string", value=scene, value_type="text")
    insert(connection, "code_facts", fact_id="progression.start_selection", key="ok", value="true", value_type="bool")
    insert(connection, "code_facts_meta", game_build_id="123")
    insert(connection, "quest_variants", resource_name="Resource", quest_stable_key="quest:q")
    insert(
        connection,
        "quest_required_items",
        quest_variant_resource_name="Resource",
        required_slot=0,
        item_stable_key="item:input",
        quantity=2,
    )
    insert(
        connection,
        "quest_required_items",
        quest_variant_resource_name="Resource",
        required_slot=1,
        item_stable_key="item:material",
        quantity=3,
    )
    yield connection
    connection.close()


def acquisition(conn: sqlite3.Connection, kind: str, source: str | None = None, **changes: object) -> None:
    values: dict[str, object] = {
        "acquisition_key": "a",
        "item_stable_key": "item:result",
        "kind": kind,
        "source_stable_key": source,
        "player_access_state": "verified_player",
        "probability_kind": "unknown",
        "probability_stage": "final_acquisition",
        "quantity_kind": "unknown",
    }
    if kind in {"character_drop", "vendor", "dialog"}:
        values["source_copy_stable_key"] = source or "character:copy"
    insert(conn, "item_acquisitions", **(values | changes))


def condition(conn: sqlite3.Connection, predicate: str, reference: str | None = None, **changes: object) -> None:
    atom = asdict(ProvenanceCondition("test", 0, 0, predicate, reference)) | changes
    insert(conn, "item_acquisition_conditions", owner_key="a", **atom)


def location(
    conn: sqlite3.Connection,
    zone: str | None = "zone:start",
    atoms: tuple[ProvenanceCondition, ...] = (),
    **changes: object,
) -> None:
    insert(
        conn,
        "item_acquisition_locations",
        **(
            {
                "owner_key": "a",
                "location_key": "location",
                "relation": "source",
                "zone_stable_key": zone,
                "conditions": json.dumps([asdict(atom) for atom in atoms]),
                "entry_zone_line_keys": "[]",
            }
            | changes
        ),
    )


def gate(conn: sqlite3.Connection, kind: str = "quest_done", key: str = "quest:gate", **changes: object) -> None:
    insert(
        conn,
        "gate_conditions",
        **(
            {
                "subject_kind": "character",
                "subject_stable_key": "character:copy",
                "gate": "activation",
                "group_index": 0,
                "atom_kind": kind,
                "atom_stable_key": key,
            }
            | changes
        ),
    )


def route(conn: sqlite3.Connection, method: str, kind: str, source: str | None, **changes: object) -> None:
    insert(
        conn,
        "quest_routes",
        **(
            {
                "route_key": "route",
                "quest_stable_key": "quest:q",
                "phase": "completion",
                "method": method,
                "source_kind": kind,
                "source_stable_key": source,
                "variant_resource_name": "Resource",
                "grants_resource_rewards": int(method == "item_turnin"),
            }
            | changes
        ),
    )


def builder(conn: sqlite3.Connection) -> ProgressionBuilder:
    graph = ProgressionBuilder(conn)
    graph.build()
    return graph


def needs(graph: ProgressionBuilder, node: str) -> set[Need]:
    return {need for way in graph.ways.get(node, {}).values() for need in way}


@pytest.mark.parametrize(
    "kind,source",
    [
        ("character_drop", "character:copy"),
        ("vendor", "character:copy"),
        ("dialog", "character:copy"),
        ("quest_reward", "quest:q"),
        ("crafting", "item:input"),
        ("item_drop", "item:input"),
        ("spell_created", "item:input"),
        ("item_conversion", "item:input"),
        ("starting_class", "class:fighter"),
        ("mining", None),
        ("fishing", None),
        ("fishing_bonus", None),
        ("item_bag", None),
        ("common_world_item", None),
        ("special_world_drop", None),
        ("ui_grant", "ui:grant"),
        ("auction_house", "mechanic:auction_house"),
    ],
)
def test_every_player_acquisition_kind(conn, kind, source):
    acquisition(conn, kind, source)
    location(conn, source_copy_stable_key="character:copy" if kind == "auction_house" else None)
    graph = builder(conn)
    assert any(need.relation == ACQUISITION_RELATIONS[kind] for need in needs(graph, "item:result"))
    if kind == "auction_house":
        assert Need("talk to", "character:copy") in needs(graph, source)
    if kind in {"common_world_item", "special_world_drop", "ui_grant"}:
        assert graph.kinds[source or "mechanic:" + kind] == "mechanism"


def test_crafting_preserves_material_quantities(conn):
    acquisition(conn, "crafting", "item:input")
    insert(
        conn,
        "item_uses",
        use_key="material",
        item_stable_key="item:material",
        target_stable_key="item:input",
        kind="crafting_material",
        material_slot=1,
        quantity_min=7,
        quantity_max=7,
        quantity_kind="exact",
    )
    assert Need("material", "item:material", quantity=7, slot="1") in needs(builder(conn), "item:result")


@pytest.mark.parametrize(
    "kind,relation",
    [("spell_created", "created by"), ("item_conversion", "converted from")],
)
def test_item_transformations_name_the_source_operation(conn, kind, relation):
    acquisition(conn, kind, "item:input")
    condition(conn, "zone_use", "zone:other")
    condition(conn, "quest_done", "quest:gate", gate_key="unlock")
    assert needs(builder(conn), "item:result") == {
        Need(relation, "item:input"),
        Need("in zone", "zone:other"),
        Need("quest done", "quest:gate"),
    }


@pytest.mark.parametrize(
    "kind,relation,key",
    [
        ("quest_done", "quest done", "quest:q"),
        ("quest_not_done", "quest not done", "quest:q"),
        ("item_held", "held", "item:input"),
        ("key_held", "key", "item:key"),
        ("room_furnished", "room furnished", "item:input"),
        ("planning_slot_item", "planning slot", "item:rune"),
        ("encounter_won", "defeated", "character:ward"),
    ],
)
def test_gate_atom_relations(conn, kind, relation, key):
    gate(conn, kind, key)
    assert any(
        need.relation == relation and need.need_stable_key == key for need in needs(builder(conn), "character:copy")
    )


@pytest.mark.parametrize(
    "predicate",
    [
        "item_not_owned",
        "actor_level",
        "actor_class",
        "time_of_day",
        "quality",
        "formula_operand",
        "route",
        "source_replenishment",
    ],
)
def test_source_properties_are_not_progression(conn, predicate):
    acquisition(conn, "vendor", "character:copy")
    condition(conn, predicate)
    assert needs(builder(conn), "item:result") == {Need("sells", "character:copy")}


def test_operation_input_is_not_an_availability_gate(conn):
    acquisition(conn, "vendor", "character:copy")
    condition(conn, "item_held", "item:input", phase="operation_input")
    assert Need("held", "item:input") not in needs(builder(conn), "item:result")


def test_character_locations_do_not_repeat_on_items(conn):
    acquisition(conn, "vendor", "character:copy")
    location(conn, atoms=(ProvenanceCondition("local", 0, 0, "quest_done", "quest:gate"),))
    gate(conn)
    graph = builder(conn)
    assert Need("quest done", "quest:gate") in needs(graph, "character:copy")
    assert Need("quest done", "quest:gate") not in needs(graph, "item:result")


def test_location_alternatives_keep_their_own_gates(conn):
    acquisition(conn, "mining")
    location(conn, "zone:start", (ProvenanceCondition("local", 0, 0, "quest_done", "quest:gate"),))
    location(conn, "zone:other", location_key="second")
    graph = builder(conn)
    ways = list(graph.ways["item:result"].values())
    assert len(ways) == 2
    assert any(Need("mined in", "zone:other") in way and len(way) == 1 for way in ways)


def test_independent_gate_groups_multiply(conn):
    gate(conn)
    gate(conn, "item_held", "item:key", group_index=1)
    gate(conn, "item_held", "item:input", gate="removal:test")
    graph = builder(conn)
    ways = list(graph.ways["character:copy"].values())
    assert len(ways) == 2
    assert all(Need("held", "item:input") in way for way in ways)


def test_barrier_is_shared_instead_of_copying_keys(conn):
    insert(conn, "doors", stable_key="door:test")
    gate(conn, "key_held", "item:key", gate="door:test")
    graph = builder(conn)
    assert needs(graph, "door:test") == {Need("key", "item:key")}
    assert Need("barrier", "door:test") in needs(graph, "character:copy")
    assert Need("key", "item:key") not in needs(graph, "character:copy")
    assert "item:key" in graph.milestones


def test_placement_triggers_furniture_quests_and_restricted_entry(conn):
    insert(conn, "zone_lines", stable_key="zoneline:entry", scene="Other", destination_zone_stable_key="zone:start")
    insert(
        conn,
        "target_entries",
        target_kind="character",
        target_stable_key="character:copy",
        zone_line_stable_key="zoneline:entry",
    )
    conn.execute(
        "UPDATE character_spawns SET spawn_upon_quest_complete_stable_key='quest:q', "
        "furniture_item_stable_key='item:input', furniture_slot='L1', "
        "trigger_item_stable_key='item:key' WHERE character_stable_key='character:copy'"
    )
    insert(
        conn, "spawn_point_stop_quests", spawn_point_stable_key="spawn:character:copy", quest_stable_key="quest:other"
    )
    ns = needs(builder(conn), "character:copy")
    assert {
        Need("entered from", "zone:other"),
        Need("quest done", "quest:q"),
        Need("quest not done", "quest:other"),
        Need("room furnished", "item:input", slot="L1"),
        Need("summoned with", "item:key"),
    } <= ns
    assert Need("in zone", "zone:start") not in ns


def zone_line(conn: sqlite3.Connection, key: str = "zoneline:line", **changes: object) -> None:
    insert(
        conn,
        "zone_lines",
        **(
            {
                "stable_key": key,
                "scene": "Start",
                "destination_zone_stable_key": "zone:end",
                "object_is_active": 1,
                "component_is_enabled": 1,
                "collider_is_trigger": 1,
                "has_enabled_trigger": 1,
            }
            | changes
        ),
    )


def test_rune_slots_collapse_before_expansion(conn):
    zone_line(conn)
    for index in range(6):
        slot = f"Rune{index}"
        insert(conn, "planning_portal_slots", zone_line_stable_key="zoneline:line", slot=slot, slot_kind="rune")
        gate(
            conn,
            "planning_slot_item",
            "item:rune",
            subject_kind="zone_line",
            subject_stable_key="zoneline:line",
            atom_slot=slot,
            group_index=index,
        )
    graph = builder(conn)
    assert len(graph.ways["zone:end"]) == 1
    assert Need("planning slot", "item:rune", slot="rune slot") in needs(graph, "zone:end")


@pytest.mark.parametrize("exclusion", ["stored", "inactive", "incapable", "never"])
def test_unusable_zone_lines_are_excluded(conn, exclusion):
    zone_line(conn)
    if exclusion == "stored":
        insert(
            conn,
            "zone_line_destination_contexts",
            zone_line_stable_key="zoneline:line",
            kind="stored_return",
            destination_state_key="saved",
            landing_state_key="saved-position",
            source_key="controller",
        )
    elif exclusion == "inactive":
        conn.execute("UPDATE zone_lines SET object_is_active=0")
    elif exclusion == "incapable":
        conn.execute("UPDATE zone_lines SET component_is_enabled=0")
    else:
        gate(conn, "never", "no", subject_kind="zone_line", subject_stable_key="zoneline:line")
    assert not builder(conn).ways.get("zone:end")


def test_recorded_activation_allows_inactive_line(conn):
    zone_line(conn, object_is_active=0)
    gate(conn, subject_kind="zone_line", subject_stable_key="zoneline:line")
    assert builder(conn).ways["zone:end"]


def test_teleport_needs_its_item(conn):
    insert(conn, "teleports", stable_key="teleport:end", scene="End", teleport_item_stable_key="item:rune")
    assert Need("teleport", "item:rune") in needs(builder(conn), "zone:end")


@pytest.mark.parametrize("state", ["internal_only", "non_acquirable"])
def test_nonplayer_sources_are_excluded(conn, state):
    acquisition(conn, "vendor", "character:copy", player_access_state=state)
    assert not builder(conn).ways.get("item:result")


def test_never_closes_only_its_group(conn):
    acquisition(conn, "vendor", "character:copy")
    condition(conn, "never")
    condition(conn, "quest_done", "quest:q", group_index=1)
    assert Need("quest done", "quest:q") in needs(builder(conn), "item:result")


def test_unconfirmed_marks_all_needs(conn):
    acquisition(conn, "vendor", "character:copy", player_access_state="unconfirmed_player")
    condition(conn, "quest_done", "quest:q")
    assert all(need.unconfirmed for need in needs(builder(conn), "item:result"))


def release(conn: sqlite3.Connection, mechanism: str, condition_kind: str, key: str, **changes: object) -> None:
    conn.execute("UPDATE characters SET invulnerable=1 WHERE stable_key='character:copy'")
    insert(
        conn,
        "character_damage_releases",
        **(
            {
                "character_stable_key": "character:copy",
                "mechanism": mechanism,
                "source_stable_key": "controller",
                "condition_kind": condition_kind,
                "condition_stable_key": key,
                "can_release": 1,
                "controller_enabled": 1,
            }
            | changes
        ),
    )


@pytest.mark.parametrize(
    "mechanism,kind,key,expected",
    [
        ("trade_turn_in", "quest_variant", "Resource", Need("release", "item:input", quantity=2, slot="0")),
        ("shivering_phantom_wards", "character_dead", "character:ward", Need("release", "character:ward")),
        ("combat_ward_cycle", "character", "character:ward", Need("release", "character:ward")),
        ("reliquary_wards", "spawn_point_cleared", "spawn:character:ward", Need("release", "character:ward")),
        ("npc_protector_weather", "state", "raining", Need("release", "world_state:weather:raining:zone:start")),
        (
            "health_phase_timer",
            "state",
            "requires_prior_damage",
            Need("condition", condition_key="release:health_phase_timer:controller"),
        ),
        (
            "spawn_health_phase_timer",
            "state",
            "requires_prior_damage",
            Need("condition", condition_key="release:spawn_health_phase_timer:controller"),
        ),
        (
            "combat_empty_wards",
            "state",
            "aggro_empty_ward_list",
            Need("condition", condition_key="release:combat_empty_wards:controller"),
        ),
    ],
)
def test_release_mechanisms_join_kills_not_meetings(conn, mechanism, kind, key, expected):
    release(conn, mechanism, kind, key)
    acquisition(conn, "character_drop", "character:copy")
    route(conn, "death", "character", "character:copy")
    graph = builder(conn)
    assert expected in needs(graph, "item:result")
    assert expected in needs(graph, "quest:q")
    assert expected not in needs(graph, "character:copy")
    if mechanism == "npc_protector_weather":
        assert not graph.ways.get(expected.need_stable_key)


@pytest.mark.parametrize("mechanism", ["npc_protector_null", "npc_protector_inactive"])
def test_infeasible_release_branches_are_not_kill_ways(conn, mechanism):
    release(conn, mechanism, "state", "runtime_binding_required", can_release=0)
    acquisition(conn, "character_drop", "character:copy")
    assert not builder(conn).ways.get("item:result")


def test_cannot_be_damaged_has_no_drop_or_defeat_way(conn):
    conn.execute("UPDATE characters SET can_be_damaged=0 WHERE stable_key='character:copy'")
    acquisition(conn, "character_drop", "character:copy")
    route(conn, "death", "character", "character:copy")
    graph = builder(conn)
    assert not graph.ways.get("item:result")
    assert not graph.ways.get("quest:q")
    assert graph.ways["character:copy"]


def test_release_branch_atoms_are_joint_and_branches_alternative(conn):
    release(conn, "trade_turn_in", "quest_variant", "Resource")
    release(conn, "combat_ward_cycle", "character", "character:ward", source_stable_key="other-controller")
    acquisition(conn, "character_drop", "character:copy")
    graph = builder(conn)
    assert len(graph.ways["item:result"]) == 2
    assert any(
        {"item:input", "item:material"} <= {need.need_stable_key for need in way}
        for way in graph.ways["item:result"].values()
    )


def test_vulnerability_gate_does_not_block_turnin_target(conn):
    release(conn, "trade_turn_in", "quest_variant", "Resource")
    gate(conn, "encounter_won", "character:ward", gate="damage_release:controller")
    route(conn, "item_turnin", "character", "character:copy")
    graph = builder(conn)
    assert Need("defeated", "character:ward", advisory=True) not in needs(graph, "character:copy")
    assert not any(need.relation == "release" for need in needs(graph, "quest:q"))


@pytest.mark.parametrize(
    "method,kind,source,relation",
    [
        ("item_turnin", "character", "character:copy", "turn in to"),
        ("talk", "character", "character:copy", "talk to"),
        ("read", "item", "item:input", "read"),
        ("death", "character", "character:copy", "defeat"),
        ("zone", "zone", "zone:start", "enter"),
        ("shout", "character", "character:copy", "hear"),
        ("chain", "quest", "quest:other", "after"),
        ("scripted", "scripted", None, "event"),
    ],
)
def test_completion_relation_families(conn, method, kind, source, relation):
    route(conn, method, kind, source, keywords="hello")
    graph = builder(conn)
    assert any(need.relation == relation for need in needs(graph, "quest:q"))
    if method == "item_turnin":
        assert Need("required item", "item:material", quantity=3, slot="1") in needs(graph, "quest:q")
    if method == "scripted":
        assert all(need.need_stable_key is None for need in needs(graph, "quest:q"))


@pytest.mark.parametrize(
    "method,kind,source,relation",
    [
        ("dialog", "character", "character:copy", "talk to"),
        ("quest_chain", "quest", "quest:other", "after"),
        ("item_read", "item", "item:input", "read"),
        ("zone_entry", "zone", "zone:start", "enter"),
        ("partial_turnin", "character", "character:copy", "turn in to"),
        ("scripted", "scripted", None, "event"),
    ],
)
def test_start_routes_and_partial_item_alternatives(conn, method, kind, source, relation):
    route(conn, method, kind, source, phase="start", keywords="hello")
    route(conn, "talk", "character", "character:copy", route_key="finish")
    graph = builder(conn)
    assert Need("started", "quest_start:quest:q") in needs(graph, "quest:q")
    starts = list(graph.ways["quest_start:quest:q"].values())
    assert len(starts) == (2 if method == "partial_turnin" else 1)
    assert all(any(need.relation == relation for need in way) for way in starts)
    if method != "scripted":
        assert all(Need(relation, source, keywords="hello") in way for way in starts)
    if method == "partial_turnin":
        assert all(sum(need.relation == "required item" for need in way) == 1 for way in starts)


def test_complete_other_requires_active_start_and_executable_variant(conn):
    route(conn, "item_turnin", "character", "character:copy")
    route(
        conn,
        "dialog",
        "character",
        "character:copy",
        phase="start",
        quest_stable_key="quest:other",
        route_key="other-start",
    )
    insert(
        conn,
        "quest_complete_other_quests",
        quest_variant_resource_name="Resource",
        completed_quest_stable_key="quest:other",
    )
    graph = builder(conn)
    assert {Need("after", "quest:q"), Need("quest active", "quest_start:quest:other")} == needs(graph, "quest:other")
    conn.execute("DELETE FROM quest_routes WHERE phase='start'")
    assert not builder(conn).ways.get("quest:other")


def test_encounter_account_false_and_host_death_true(conn):
    insert(
        conn,
        "encounter_placements",
        encounter_key="encounter:test",
        root_spawn_stable_key="spawn:character:copy",
        member_spawn_stable_key="spawn:character:copy",
        role="root",
        context_kind="account_claim",
        post_completion_role="player_home",
    )
    insert(
        conn,
        "encounter_conditions",
        encounter_key="encounter:test",
        state_scope="account",
        state_key="account_state:reliquary_claimed",
        required_value="false",
    )
    insert(
        conn,
        "encounter_conditions",
        encounter_key="encounter:test",
        state_scope="character",
        state_key="quest:q",
        required_value="false",
    )
    insert(
        conn,
        "encounter_completions",
        encounter_key="encounter:test",
        event_kind="host_death",
        state_scope="account",
        state_key="account_state:reliquary_claimed",
        result_value="true",
    )
    graph = builder(conn)
    assert graph.tiers["account_state:reliquary_claimed:false"] == 0
    assert Need("state", "account_state:reliquary_claimed:false") in needs(graph, "character:copy")
    assert Need("quest not done", "quest:q") in needs(graph, "character:copy")
    assert Need("defeated", "character:copy", advisory=True) in needs(graph, "account_state:reliquary_claimed:true")


@pytest.mark.parametrize(
    "failure", ["acquisition", "method", "source", "atom", "gate", "release", "missing", "expansion", "start"]
)
def test_unrepresentable_facts_fail_with_subject_way_and_fact(conn, failure):
    if failure == "acquisition":
        acquisition(conn, "future")
    elif failure == "method":
        route(conn, "future", "character", "character:copy")
    elif failure == "source":
        route(conn, "talk", "future", "character:copy")
    elif failure == "atom":
        acquisition(conn, "vendor", "character:copy")
        condition(conn, "future")
    elif failure == "gate":
        gate(conn, gate="future:controller")
    elif failure == "release":
        release(conn, "future", "state", "x")
    elif failure == "missing":
        acquisition(conn, "item_drop", "item:missing")
    elif failure == "start":
        conn.execute("DELETE FROM code_facts")
    else:
        for index in range(6):
            key = f"item:expansion{index}"
            insert(conn, "items", stable_key=key, display_name=key, image_name=key)
            gate(conn, gate=f"activation:{index}")
            gate(conn, "item_held", key, gate=f"activation:{index}", group_index=1)
    with pytest.raises(ValueError, match=r"Progression node .*way .*fact"):
        builder(conn)


def test_milestones_distinguish_common_and_gated_sources(conn):
    acquisition(conn, "character_drop", "character:ward")
    gate(conn, "key_held", "item:key")
    graph = builder(conn)
    assert "item:key" in graph.milestones
    assert "character:copy" in graph.milestones
    assert "item:result" not in graph.milestones
    assert "quest:q" in graph.milestones


def test_tiers_alternatives_joint_needs_cycles_negatives_and_ties(conn):
    graph = ProgressionBuilder(conn)
    for key in ("start", "a", "b", "c", "negative", "cycle1", "cycle2", "gap"):
        graph.node(key, "quest" if key in {"a", "b", "c"} else "class")
    graph.add("start", (), "fixture")
    graph.add("a", [Need("held", "start")], "fixture")
    graph.add("b", [Need("held", "a")], "fixture")
    graph.add("c", [Need("held", "a"), Need("held", "b")], "fixture")
    graph.add("c", [Need("held", "start")], "fixture")
    graph.add("c", [Need("from", "start")], "fixture")
    graph.add("negative", [Need("quest not done", "gap")], "fixture")
    graph.add("cycle1", [Need("held", "cycle2")], "fixture")
    graph.add("cycle2", [Need("held", "cycle1")], "fixture")
    graph.mark_milestones()
    graph.order()
    assert {key: graph.tiers[key] for key in ("start", "a", "b", "c", "negative")} == {
        "start": 0,
        "a": 1,
        "b": 2,
        "c": 1,
        "negative": 0,
    }
    assert not {"gap", "cycle1", "cycle2"} & graph.tiers.keys()
    expected = min(way_key(canonical_way([Need(relation, "start")])) for relation in ("held", "from"))
    assert graph.first["c"] == expected
    graph.check_tiers()
    graph.tiers["a"] = 0
    with pytest.raises(ValueError, match="tier invariant"):
        graph.check_tiers()


def test_build_rows_are_identical_and_keep_unchanged_way_identity(conn):
    zone_line(conn)
    process_progression(conn)
    tables = ("progression_nodes", "progression_ways", "progression_needs", "progression_meta")
    before = {table: conn.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in tables}
    process_progression(conn)
    assert before == {table: conn.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in tables}
    old = conn.execute("SELECT way_key FROM progression_ways WHERE node_stable_key='zone:end'").fetchone()[0]
    insert(conn, "teleports", stable_key="teleport:end", scene="End", teleport_item_stable_key="item:rune")
    process_progression(conn)
    assert old in {
        row[0] for row in conn.execute("SELECT way_key FROM progression_ways WHERE node_stable_key='zone:end'")
    }


def test_both_start_scenes_have_independent_initial_mechanisms(conn):
    graph = builder(conn)
    for zone, mechanism in (
        ("zone:start", "mechanic:new_character_start"),
        ("zone:other", "mechanic:alternate_start"),
    ):
        assert graph.kinds[mechanism] == "mechanism"
        assert list(graph.ways[mechanism].values()) == [()]
        assert (Need("from", mechanism),) in graph.ways[zone].values()
        assert graph.tiers[zone] == 0
        assert graph.tiers[mechanism] == 0


@pytest.mark.parametrize("fact", ["progression.new_character_scene", "progression.alternate_start_scene"])
@pytest.mark.parametrize("failure", ["missing", "unknown scene"])
def test_each_start_fact_requires_an_existing_zone(conn, fact, failure):
    if failure == "missing":
        conn.execute("DELETE FROM code_facts WHERE fact_id=?", (fact,))
    else:
        conn.execute("UPDATE code_facts SET value='MissingScene' WHERE fact_id=?", (fact,))
    with pytest.raises(ValueError, match=fact):
        builder(conn)


def test_both_starts_require_verified_selection_semantics(conn):
    conn.execute("UPDATE code_facts SET value='false' WHERE fact_id='progression.start_selection'")
    with pytest.raises(ValueError, match="missing verified new-character start selection"):
        builder(conn)


@pytest.mark.parametrize("kind", ["ward1_absent", "ward2_absent", "unknown_ward_condition"])
@pytest.mark.parametrize("mechanism", ["shivering_phantom_wards", "combat_ward_cycle", "reliquary_wards"])
def test_unknown_ward_release_conditions_fail_closed(conn, kind, mechanism):
    release(conn, mechanism, kind, "")
    acquisition(conn, "character_drop", "character:copy")
    with pytest.raises(ValueError, match=f"unmapped release condition '{kind}'"):
        builder(conn)


def test_zone_use_requires_a_real_zone_node(conn):
    acquisition(conn, "item_conversion", "item:input")
    condition(conn, "zone_use", "zone:missing")
    with pytest.raises(ValueError, match="need resolves to no node: zone:missing"):
        builder(conn)
