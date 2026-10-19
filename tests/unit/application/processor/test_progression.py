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
    insert(connection, "classes", class_name="Default")
    insert(
        connection,
        "code_facts",
        fact_id="progression.playable_classes",
        key="strings",
        value="Fighter",
        value_type="text",
    )
    for fact, scene in (
        ("progression.new_character_scene", "Start"),
        ("progression.alternate_start_scene", "Other"),
    ):
        insert(connection, "code_facts", fact_id=fact, key="string", value=scene, value_type="text")
    insert(connection, "code_facts", fact_id="progression.start_selection", key="ok", value="true", value_type="bool")
    insert(
        connection, "code_facts", fact_id="progression.item_action_guards", key="ok", value="true", value_type="bool"
    )
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
    ],
)
def test_every_player_acquisition_kind(conn, kind, source):
    acquisition(conn, kind, source)
    location(conn)
    graph = builder(conn)
    assert any(need.relation == ACQUISITION_RELATIONS[kind] for need in needs(graph, "item:result"))
    if kind in {"common_world_item", "special_world_drop", "ui_grant"}:
        assert graph.kinds[source or "mechanic:" + kind] == "mechanism"


def test_the_auction_house_is_no_way_to_an_item(conn):
    acquisition(conn, "auction_house", "mechanic:auction_house")
    location(conn, source_copy_stable_key="character:copy")
    graph = builder(conn)
    assert not needs(graph, "item:result")
    assert "mechanic:auction_house" not in graph.kinds


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
    insert(conn, "barriers", barrier_key="door:test", kind="door", name="Test door")
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
    """A usable zone line from Start and the travel route that it is."""
    line = {"stable_key": key, "scene": "Start", "destination_zone_stable_key": "zone:end"} | changes
    insert(conn, "zone_lines", **line)
    insert(
        conn,
        "travel_routes",
        route_key=key,
        mechanism="zone_line",
        source_stable_key=key,
        from_zone_stable_key="zone:" + str(line["scene"]).lower(),
        to_zone_stable_key=line["destination_zone_stable_key"],
    )


def spell_route(conn: sqlite3.Connection, origin: str | None = None) -> None:
    """A spell that sends its caster to End, cast by clicking item:rune."""
    insert(conn, "spells", stable_key="spell:portal", spell_name="Portal", display_name="Portal", image_name="p")
    conn.execute(
        "UPDATE items SET item_effect_on_click_stable_key='spell:portal',required_slot='General'"
        " WHERE stable_key='item:rune'"
    )
    insert(
        conn,
        "travel_routes",
        route_key="travel:spell:portal:zone:end",
        mechanism="spell",
        source_stable_key="spell:portal",
        from_zone_stable_key=origin,
        to_zone_stable_key="zone:end",
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


def test_a_zone_line_that_never_opens_gives_no_way(conn):
    zone_line(conn)
    gate(conn, "never", "no", subject_kind="zone_line", subject_stable_key="zoneline:line")
    assert not builder(conn).ways.get("zone:end")


def test_a_spell_route_needs_its_spell_and_the_spell_its_item(conn):
    spell_route(conn)
    graph = builder(conn)
    assert list(graph.ways["zone:end"].values()) == [(Need("cast", "spell:portal"),)]
    assert list(graph.ways["spell:portal"].values()) == [(Need("casts", "item:rune"),)]


def test_a_spell_route_that_works_in_one_zone_needs_that_zone(conn):
    spell_route(conn, origin="zone:other")
    assert needs(builder(conn), "zone:end") == {Need("cast", "spell:portal"), Need("in zone", "zone:other")}


def test_a_way_back_through_the_node_itself_does_not_lift_its_milestone(conn):
    # End is entered past a gate, and Deep, which only End leads to, leads back.
    insert(
        conn,
        "zones",
        stable_key="zone:deep",
        scene_name="Deep",
        zone_name="Deep",
        display_name="Deep",
        image_name="Deep",
        zone_type="Dungeon",
    )
    zone_line(conn)
    gate(conn, "quest_done", "quest:gate", subject_kind="zone_line", subject_stable_key="zoneline:line")
    zone_line(conn, "zoneline:on", scene="End", destination_zone_stable_key="zone:deep")
    zone_line(conn, "zoneline:back", scene="Deep", destination_zone_stable_key="zone:end")
    graph = builder(conn)
    assert "zone:end" in graph.milestones
    assert "zone:deep" not in graph.milestones


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
    if mechanism == "npc_protector_weather":
        insert(
            conn,
            "world_states",
            stable_key="world_state:weather:raining:zone:start",
            state="raining",
            zone_stable_key="zone:start",
            uses_sun=1,
            natural_rain_can_start=1,
        )
        insert(
            conn,
            "world_state_producers",
            state_stable_key="world_state:weather:raining:zone:start",
            mechanism="natural_weather",
        )
    release(conn, mechanism, kind, key)
    acquisition(conn, "character_drop", "character:copy")
    route(conn, "death", "character", "character:copy")
    graph = builder(conn)
    assert expected in needs(graph, "item:result")
    assert expected in needs(graph, "quest:q")
    assert expected not in needs(graph, "character:copy")
    if mechanism == "npc_protector_weather":
        assert Need("natural weather", condition_key="weather:natural_rain") in needs(graph, expected.need_stable_key)


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


def test_ways_rank_as_first_ways_are_chosen_and_keep_every_fact(conn):
    graph = ProgressionBuilder(conn)
    for key in ("start", "a", "gap", "target"):
        graph.node(key, "class")
    graph.add("start", (), "fixture")
    graph.add("a", [Need("held", "start")], "fixture")
    direct, longer, blocked = ([Need("held", "start")], [Need("held", "a")], [Need("held", "gap")])
    graph.add("target", direct, "first fact")
    graph.add("target", direct, "second fact")
    graph.add("target", longer, "fixture")
    graph.add("target", blocked, "fixture")
    graph.mark_milestones()
    graph.order()
    first, slower, unreachable = (way_key(canonical_way(way)) for way in (direct, longer, blocked))

    assert graph.ranks["target", first] == (0, 1) < graph.ranks["target", slower] == (0, 2)
    assert ("target", unreachable) not in graph.ranks
    assert graph.facts["target", first] == {"first fact", "second fact"}


def test_build_rows_are_identical_and_keep_unchanged_way_identity(conn):
    zone_line(conn)
    process_progression(conn)
    tables = ("progression_nodes", "progression_ways", "progression_way_facts", "progression_needs", "progression_meta")
    before = {table: conn.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in tables}
    process_progression(conn)
    assert before == {table: conn.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in tables}
    old = conn.execute("SELECT way_key FROM progression_ways WHERE node_stable_key='zone:end'").fetchone()[0]
    spell_route(conn)
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


def test_only_playable_classes_are_choices_of_a_new_character(conn):
    graph = builder(conn)
    assert list(graph.ways["class:fighter"].values()) == [()]
    assert "class:default" not in graph.kinds


@pytest.mark.parametrize("failure", ["missing", "unknown class"])
def test_playable_classes_require_their_fact_and_class_rows(conn, failure):
    if failure == "missing":
        conn.execute("DELETE FROM code_facts WHERE fact_id='progression.playable_classes'")
    else:
        conn.execute("UPDATE code_facts SET value='Fighter,Ranger' WHERE fact_id='progression.playable_classes'")
    with pytest.raises(ValueError, match=r"progression\.playable_classes"):
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


def test_rain_release_needs_spell_from_casting_item_or_teaching_scroll(conn):
    state = "world_state:weather:raining:zone:start"
    insert(conn, "classes", class_name="Druid")
    conn.execute("UPDATE code_facts SET value='Fighter,Druid' WHERE fact_id='progression.playable_classes'")
    insert(conn, "item_classes", item_stable_key="item:key", class_name="Fighter")
    insert(conn, "item_classes", item_stable_key="item:key", class_name="Druid")
    insert(conn, "item_classes", item_stable_key="item:rune", class_name="Druid")
    insert(
        conn,
        "world_states",
        stable_key=state,
        state="raining",
        zone_stable_key="zone:start",
        uses_sun=1,
        natural_rain_can_start=0,
    )
    insert(
        conn,
        "spells",
        stable_key="spell:storm",
        spell_name="Invoke Storm",
        display_name="Invoke Storm",
        image_name="Invoke Storm",
        required_level=8,
    )
    insert(
        conn, "weather_spell_effects", spell_stable_key="spell:storm", weight_goal=0.9, since_rain=-1, cloud_amount=0.4
    )
    insert(conn, "world_state_producers", state_stable_key=state, mechanism="spell", spell_stable_key="spell:storm")
    conn.execute(
        "UPDATE items SET item_effect_on_click_stable_key='spell:storm',required_slot='Ring'"
        " WHERE stable_key='item:key'"
    )
    conn.execute("UPDATE items SET teach_spell_stable_key='spell:storm' WHERE stable_key='item:rune'")
    acquisition(conn, "starting_class", "class:fighter", item_stable_key="item:key")
    release(conn, "npc_protector_weather", "state", "raining")
    acquisition(conn, "character_drop", "character:copy", acquisition_key="key")
    graph = builder(conn)
    assert needs(graph, state) == {Need("in zone", "zone:start"), Need("cast", "spell:storm")}
    assert set(graph.ways["spell:storm"].values()) == {
        (Need("casts", "item:key"),),
        canonical_way([Need("teaches", "item:rune", required_level=8), Need("class", "class:druid")]),
    }
    assert Need("release", state) in needs(graph, "item:result")
    assert state in graph.milestones
    assert graph.tiers["item:result"] >= graph.tiers[state] > graph.tiers["spell:storm"]
    conn.execute("UPDATE spells SET required_level=80 WHERE stable_key='spell:storm'")
    higher_level = builder(conn)
    assert higher_level.tiers == graph.tiers
    assert Need("teaches", "item:rune", required_level=80) in needs(higher_level, "spell:storm")


def test_unknown_world_state_fails_closed(conn):
    gate(conn, "world_state", "world_state:weather:raining:zone:missing")
    with pytest.raises(ValueError, match="unmapped world state"):
        builder(conn)


@pytest.mark.parametrize(
    "relation,slot,classes,expected",
    [
        ("teaches", "General", (), {None}),
        ("teaches", "General", ("Druid",), {"class:druid"}),
        ("equipped", "Ring", (), {None}),
        ("equipped", "Ring", ("Druid",), {"class:druid"}),
        ("casts", "General", ("Druid",), {None}),
        ("casts", "Ring", (), set()),
        ("casts", "Ring", ("Druid",), {"class:druid"}),
        ("casts", "Ring", ("Druid", "Fighter"), {None}),
    ],
)
def test_item_action_class_rules(conn, relation, slot, classes, expected):
    insert(conn, "classes", class_name="Druid")
    conn.execute("UPDATE code_facts SET value='Fighter,Druid' WHERE fact_id='progression.playable_classes'")
    conn.execute("UPDATE items SET required_slot=? WHERE stable_key='item:key'", (slot,))
    for name in classes:
        insert(conn, "item_classes", item_stable_key="item:key", class_name=name)
    graph = ProgressionBuilder(conn)
    graph.build_nodes()
    item = next(row for row in graph.rows("items") if row["stable_key"] == "item:key")
    ways = graph.item_action(item, relation)
    assert {next((need.need_stable_key for need in way if need.relation == "class"), None) for way in ways} == expected


def test_click_that_requires_equipping_keeps_that_need(conn):
    conn.execute("UPDATE items SET required_slot='Ring',must_be_equipped_to_click=1 WHERE stable_key='item:key'")
    insert(conn, "item_classes", item_stable_key="item:key", class_name="Fighter")
    graph = ProgressionBuilder(conn)
    graph.build_nodes()
    item = next(row for row in graph.rows("items") if row["stable_key"] == "item:key")
    assert graph.item_action(item, "casts") == [
        canonical_way([Need("casts", "item:key"), Need("equipped", "item:key")])
    ]


@pytest.mark.parametrize("provenance", [False, True])
def test_death_sets_need_consumptive_release_items_for_every_distinct_copy(conn, provenance):
    release(conn, "trade_turn_in", "quest_variant", "Resource")
    if provenance:
        acquisition(conn, "character_drop", "character:other")
        condition(conn, "encounter_won", "character:copy", minimum=3)
        target = "item:result"
    else:
        gate(
            conn,
            "encounter_won",
            "character:copy",
            subject_stable_key="character:other",
            atom_quantity=3,
        )
        target = "character:other"

    required = needs(builder(conn), target)

    assert Need("defeated", "character:copy", quantity=3, advisory=True) in required
    assert Need("release", "item:input", quantity=6, slot="0") in required
    assert Need("release", "item:material", quantity=9, slot="1") in required


def arena_round(
    conn: sqlite3.Connection, index: int, coin: str, chest: str, *fighters: str, arena: str | None = "ARENA"
) -> None:
    key = f"arenaround:{arena}:{index}"
    insert(
        conn,
        "arena_rounds",
        stable_key=key,
        scene="Start",
        arena_object_name=arena,
        round_index=index,
        coin_item_stable_key=coin,
        award_chest_character_stable_key=chest,
    )
    for sequence, fighter in enumerate(fighters):
        insert(
            conn,
            "arena_round_enemies",
            arena_round_stable_key=key,
            sequence_index=sequence,
            enemy_character_stable_key=fighter,
        )


def test_arena_fighters_need_their_round_and_chests_wait_for_its_fighters(conn):
    conn.execute("UPDATE character_spawns SET source_script='VithArena'")
    arena_round(conn, 1, "item:input", "character:other", "character:copy")
    arena_round(conn, 2, "item:key", "character:ward", "character:copy", "character:copy")
    graph = builder(conn)
    place = Need("in zone", "zone:start")

    assert set(graph.ways["character:copy"].values()) == {
        canonical_way((Need("summoned with", "item:input"), place)),
        canonical_way((Need("summoned with", "item:key"), place)),
    }
    assert set(graph.ways["character:other"].values()) == {
        canonical_way((Need("summoned with", "item:input"), Need("defeated", "character:copy", advisory=True), place))
    }
    assert set(graph.ways["character:ward"].values()) == {
        canonical_way(
            (Need("summoned with", "item:key"), Need("defeated", "character:copy", quantity=2, advisory=True), place)
        )
    }


@pytest.mark.parametrize(
    "failure,message",
    [
        ("unbound", "arena placement belongs to no round"),
        ("anonymous", "arena round has no scene or arena identity"),
        ("ambiguous", "placement is ambiguous between arenas"),
    ],
)
def test_arena_placements_bind_to_rounds_of_one_arena(conn, failure, message):
    conn.execute("UPDATE character_spawns SET source_script='VithArena' WHERE character_stable_key='character:ward'")
    arena_round(
        conn, 1, "item:input", "character:other", "character:copy", arena=None if failure == "anonymous" else "ARENA"
    )
    if failure == "ambiguous":
        arena_round(conn, 1, "item:key", "character:ward", "character:copy", arena="OTHER")
    with pytest.raises(ValueError, match=message):
        builder(conn)


def summon(
    conn: sqlite3.Connection, summoner: str, kind: str = "alive", *, index: int = 0, field: str = "Adds"
) -> None:
    """Make the ward a summon of the summoner at the ward's placement."""
    insert(
        conn,
        "character_summons",
        character_stable_key="character:ward",
        spawn_point_stable_key="spawn:character:ward",
        source_script="Fight",
        source_field=field,
        summon=kind,
        summoner_index=index,
        summoner_stable_key=summoner,
    )


def test_an_add_appears_while_any_of_its_summoners_fights(conn):
    summon(conn, "character:copy")
    summon(conn, "character:other")
    zone = Need("in zone", "zone:start")
    assert set(builder(conn).ways["character:ward"].values()) == {
        canonical_way((zone, Need("summoned by", "character:copy"))),
        canonical_way((zone, Need("summoned by", "character:other"))),
    }


def test_a_death_summon_needs_one_death_of_each_summoner(conn):
    summon(conn, "character:copy", "defeated", index=0, field="Chest")
    summon(conn, "character:other", "defeated", index=1, field="Chest")
    assert list(builder(conn).ways["character:ward"].values()) == [
        canonical_way(
            (
                Need("in zone", "zone:start"),
                Need("defeated", "character:copy", advisory=True),
                Need("defeated", "character:other", advisory=True),
            )
        )
    ]


def test_a_dialog_summon_needs_the_spawning_keyword_and_its_quest(conn):
    insert(
        conn,
        "character_dialogs",
        character_stable_key="character:copy",
        dialog_index=4,
        keywords="Azynthi, azynthi",
        required_quest_stable_key="quest:gate",
        spawn_character_stable_key="character:ward",
    )
    summon(conn, "character:copy", "dialog", field="Spawn")
    assert needs(builder(conn), "character:ward") == {
        Need("in zone", "zone:start"),
        Need("talk to", "character:copy", keywords="Azynthi, azynthi"),
        Need("quest done", "quest:gate"),
    }


def test_a_dug_up_chest_needs_its_map_and_its_guardians_need_the_chest(conn):
    for key in ("character:chest", "character:guardian"):
        insert(
            conn,
            "characters",
            stable_key=key,
            display_name=key,
            image_name=key,
            encounter_tier="npc",
            can_be_damaged=1,
            invulnerable=0,
            level_scales_with_player=0,
        )
    insert(conn, "spells", stable_key="spell:read map", spell_name="Read Map", display_name="Read Map", image_name="m")
    conn.execute(
        "UPDATE items SET item_effect_on_click_stable_key='spell:read map',required_slot='General'"
        " WHERE stable_key='item:key'"
    )
    insert(conn, "treasure_locations", stable_key="treasure:end:1", scene="End", x=1, y=2, z=3)
    insert(
        conn,
        "treasure_chest_possible_spawns",
        chest_character_stable_key="character:chest",
        treasure_location_stable_key="treasure:end:1",
        level_min=10,
        level_max=20,
        player_level_min=10,
        player_level_max=19,
        scene="End",
    )
    insert(
        conn,
        "character_summons",
        character_stable_key="character:guardian",
        spawn_point_stable_key="treasure:end:1",
        source_script="TreasureChestEvent",
        source_field="Guardians",
        summon="alive",
        summoner_index=0,
        summoner_stable_key="character:chest",
    )
    graph = builder(conn)
    zone = Need("in zone", "zone:end")
    assert list(graph.ways["character:chest"].values()) == [
        canonical_way((Need("cast", "spell:read map", required_level=10), zone))
    ]
    assert list(graph.ways["character:guardian"].values()) == [
        canonical_way((Need("summoned by", "character:chest"), zone))
    ]
    assert list(graph.ways["spell:read map"].values()) == [(Need("casts", "item:key"),)]
