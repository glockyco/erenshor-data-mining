"""Builder selection rules and independent input identity accounting."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.item_provenance_coverage import validate_item_provenance
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import (
    ProvenanceEvidence,
    conditions_satisfiable,
)


def _insert(connection: sqlite3.Connection, table: str, **values: object) -> None:
    columns = ",".join(f'"{column}"' for column in values)
    connection.execute(
        f'INSERT INTO "{table}" ({columns}) VALUES ({",".join("?" for _ in values)})',
        tuple(values.values()),
    )


def _evidence(builder: ProvenanceBuilder, relation: str, owner: str | None = None) -> list[ProvenanceEvidence]:
    """The input rows of one relation that the builder selected, for all facts or one."""
    return [
        entry
        for key, entries in builder.fact_evidence.items()
        if owner is None or key == owner
        for entry in entries
        if entry.input_relation == relation
    ]


def _drop_evidence(builder: ProvenanceBuilder, relation: str, owner: str | None = None) -> None:
    """Lose a relation's input rows, as a builder that forgot them would."""
    for key, entries in builder.fact_evidence.items():
        if owner is None or key == owner:
            builder.fact_evidence[key] = tuple(entry for entry in entries if entry.input_relation != relation)


@pytest.fixture
def native_inputs(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    writer = Writer(tmp_path / "coverage.sqlite")
    writer.create_schema()
    connection = writer.conn
    _insert(connection, "classes", class_name="Paladin", display_name="Paladin")
    _insert(
        connection,
        "spells",
        stable_key="spell:create",
        spell_name="Offering Stone",
        display_name="Offering Stone",
        image_name="",
    )
    smithing_ids = {
        "reward": "31377423",
        "removal": "2298018",
        "input": "2265228",
        "material": "46289586",
        "other": "340104",
    }
    for item in ("reward", "material", "recipe", "common", "input", "other", "furniture", "removal"):
        _insert(
            connection,
            "items",
            stable_key="item:" + item,
            display_name=item,
            image_name="",
            wiki_page_name=item.title(),
            is_wiki_generated=1,
            id=smithing_ids.get(item),
            required_slot="Head" if item == "furniture" else "Aura" if item == "other" else "General",
            item_level=10,
            sim_players_cant_get=0,
            is_unique=0,
            template=int(item == "recipe"),
            item_effect_on_click_stable_key="spell:create" if item == "input" else None,
            fuel_source=int(item == "material"),
            fuel_level=3 if item == "material" else 0,
        )
    _insert(connection, "item_classes", item_stable_key="item:other", class_name="Paladin")
    _insert(
        connection,
        "authored_sims",
        stable_key="authored-sim:fixture",
        prefab_guid="ffffffffffffffffffffffffffffffff",
        prefab_local_id=42,
        prefab_path="Assets/Fixture.prefab",
        object_name="Fixture seed",
        raw_character_stable_key="character:seed",
        npc_name="Fixture seed",
        seed_class_name="Paladin",
        seed_level=10,
        seed_skill_level=5,
        seed_is_male=1,
        seed_hair_name="Hair",
        seed_hair_color=0,
        seed_skin_color=0,
        is_gm_character=0,
        rival=0,
    )
    _insert(
        connection,
        "authored_sim_references",
        source_component_key="component:fixture-preset",
        reference_index=2,
        source_scene="One",
        source_scene_path="Assets/One.unity",
        authored_sim_stable_key="authored-sim:fixture",
    )
    _insert(
        connection,
        "authored_sim_equipment",
        authored_sim_stable_key="authored-sim:fixture",
        position=0,
        item_stable_key="item:reward",
    )
    _insert(
        connection,
        "authored_sim_equipment",
        authored_sim_stable_key="authored-sim:fixture",
        position=1,
        item_stable_key=None,
    )
    for copy, group in (("a", "a"), ("b", "a"), ("unused", "a")):
        _insert(
            connection,
            "characters",
            stable_key="character:" + copy,
            display_name=copy,
            image_name="",
            encounter_tier="npc",
            level_scales_with_player=0,
            invulnerable=0,
            can_be_damaged=1,
            treasure_chest=0,
        )
        _insert(
            connection,
            "character_deduplications",
            group_key="character:" + group,
            member_stable_key="character:" + copy,
            is_wiki_generated=int(copy != "unused"),
        )
    _insert(
        connection,
        "zones",
        stable_key="zone:one",
        scene_name="One",
        zone_name="One",
        display_name="One",
        image_name="",
        zone_type="Outdoor",
    )
    _insert(connection, "quests", stable_key="quest:one", display_name="One", image_name="")
    for copy in ("a", "b"):
        _insert(
            connection,
            "character_spawns",
            character_stable_key="character:" + copy,
            spawn_point_stable_key="spawn:" + copy,
            scene="One",
            x=1,
            y=2,
            z=3,
            is_directly_placed=0,
            furniture_item_stable_key="item:furniture",
            furniture_slot="L1",
        )
    _insert(connection, "treasure_locations", stable_key="treasure:one", scene="One", x=4, y=5, z=6)
    _insert(
        connection,
        "treasure_chest_possible_spawns",
        chest_character_stable_key="character:a",
        treasure_location_stable_key="treasure:one",
        scene="One",
        x=4,
        y=5,
        z=6,
        level_min=5,
        level_max=15,
        player_level_min=7,
        player_level_max=17,
    )
    _insert(connection, "zone_lines", stable_key="entry:one", scene="One", is_usable=1)
    _insert(
        connection,
        "target_entries",
        target_kind="character",
        target_stable_key="character:a",
        zone_line_stable_key="entry:one",
    )
    for subject, key in (("character", "character:a"), ("spawn_point", "spawn:a"), ("item_bag", "bag:one")):
        _insert(
            connection,
            "gate_conditions",
            subject_kind=subject,
            subject_stable_key=key,
            gate="unlock",
            group_index=0,
            atom_kind="quest_done",
            atom_stable_key="quest:one",
        )
    _insert(
        connection,
        "gate_conditions",
        subject_kind="vendor_item",
        subject_stable_key="character:a",
        item_stable_key="item:reward",
        gate="stock",
        group_index=1,
        atom_kind="item_held",
        atom_stable_key="item:material",
    )
    for copy, item, chance, common in (
        ("a", "reward", 25.0, 0),
        ("a", "common", 10.0, 1),
        ("b", "common", 30.0, 1),
        ("unused", "other", 80.0, 0),
    ):
        _insert(
            connection,
            "loot_drops",
            character_stable_key="character:" + copy,
            item_stable_key="item:" + item,
            loot_table_stable_key="loot-table:" + copy,
            source_component_is_enabled=1,
            drop_probability=chance,
            expected_per_kill=chance / 100,
            drop_count_distribution=json.dumps([1 - chance / 100, chance / 100]),
            is_actual=not common,
            is_guaranteed=0,
            is_common_world_item=common,
        )
    _insert(
        connection,
        "special_world_drops",
        item_stable_key="item:reward",
        pool="level_pool",
        drop_probability=0.25,
        min_level_exclusive=12,
    )
    _insert(
        connection,
        "character_vendor_items",
        character_stable_key="character:a",
        item_slot=2,
        item_stable_key="item:reward",
    )
    for slot in (1, 2):
        _insert(
            connection,
            "crafting_rewards",
            recipe_item_stable_key="item:recipe",
            reward_slot=slot,
            reward_item_stable_key="item:reward",
            reward_quantity=1,
        )
        _insert(
            connection,
            "crafting_recipes",
            recipe_item_stable_key="item:recipe",
            material_slot=slot,
            material_item_stable_key="item:material",
            material_quantity=slot + 3,
        )
    for variant in ("One", "Unrouted", "NoReward"):
        _insert(
            connection,
            "quest_variants",
            resource_name=variant,
            quest_stable_key="quest:one",
            repeatable=0,
            item_on_complete_stable_key=None if variant == "NoReward" else "item:reward",
            unlock_item_for_vendor_stable_key="item:other" if variant == "One" else None,
        )
    _insert(
        connection,
        "character_vendor_quest_unlocks",
        character_stable_key="character:a",
        quest_stable_key="quest:one",
        quest_slot=7,
        quest_variant_resource_name="One",
    )
    _insert(
        connection,
        "gate_conditions",
        subject_kind="vendor_item",
        subject_stable_key="character:a",
        item_stable_key="item:other",
        gate="vendor_unlock",
        group_index=0,
        atom_kind="quest_done",
        atom_stable_key="quest:one",
    )
    for copy in ("a", "unused"):
        _insert(
            connection,
            "character_dialogs",
            character_stable_key="character:" + copy,
            dialog_index=2,
            give_item_stable_key="item:reward",
            required_quest_stable_key="quest:one",
            assign_quest_stable_key="quest:one",
            assign_quest_variant_resource_name="One",
        )
    for slot, variant, copy in ((0, "One", "a"), (1, "One", "a"), (2, "NoReward", "a"), (0, "One", "unused")):
        _insert(
            connection,
            "character_quest_manager_quests",
            character_stable_key="character:" + copy,
            quest_stable_key="quest:one",
            quest_slot=slot,
            quest_variant_resource_name=variant,
        )
    for slot in (0, 1):
        _insert(
            connection,
            "quest_required_items",
            quest_variant_resource_name="One",
            required_slot=slot,
            item_stable_key="item:material",
            quantity=slot + 2,
        )
    _insert(connection, "mining_nodes", stable_key="node:one", scene="One", x=3, y=4, z=5)
    _insert(
        connection,
        "mining_node_items",
        mining_node_stable_key="node:one",
        item_stable_key="item:reward",
        drop_chance=15,
    )
    _insert(connection, "waters", stable_key="water:one", scene="One", x=6, y=7, z=8)
    for period, chance in (("DayFishable", 25), ("NightFishable", 75)):
        _insert(
            connection,
            "water_fishables",
            water_stable_key="water:one",
            type=period,
            item_stable_key="item:reward",
            drop_chance=chance,
        )
    _insert(connection, "fishing_bonus_catches", item_stable_key="item:other", chance_per_catch=3)
    _insert(
        connection,
        "item_bags",
        stable_key="bag:one",
        item_stable_key="item:reward",
        scene="One",
        x=4,
        y=3,
        z=2,
        respawns=0,
        respawn_timer=0,
    )
    _insert(
        connection,
        "item_drops",
        source_item_stable_key="item:input",
        dropped_item_stable_key="item:reward",
        pool_stable_key="pool:fossils",
        drop_probability=40,
        is_guaranteed=1,
    )
    _insert(
        connection,
        "spell_created_items",
        source_item_stable_key="item:input",
        created_item_stable_key="item:other",
        spell_stable_key="spell:create",
        grant_fact_id="item.offering_stone_grant",
        quantity=1,
    )
    _insert(
        connection,
        "item_conversions",
        input_item_stable_key="item:input",
        output_item_stable_key="item:reward",
        zone_stable_key="zone:one",
        mechanic="chessboard",
    )
    _insert(
        connection, "item_zone_restrictions", item_stable_key="item:input", zone_stable_key="zone:one", outcome="unused"
    )
    _insert(
        connection,
        "quality_offerings",
        character_stable_key="character:a",
        first_item_stable_key="item:material",
        second_item_stable_key="item:other",
        chance_per_stone_pair=3,
        chance_per_improvement_level=2,
        enhance_chance_per_stone_pair=1,
        result_quality="Blessed",
        enhanced_quality="Divine",
    )
    for slot in (0, 1):
        _insert(
            connection, "class_starting_items", class_name="Paladin", sort_order=slot, item_stable_key="item:reward"
        )
    _insert(connection, "auction_house_brokers", character_stable_key="character:a")
    for route in ("direct", "replacement"):
        _insert(
            connection,
            "auction_house_items",
            item_stable_key="item:reward",
            route=route,
            min_sim_level=10,
            max_sim_level=20,
            min_player_level=15,
            max_player_level=25,
        )
    _insert(connection, "code_facts_meta", assembly_sha256="fixture-assembly", game_build_id="fixture-build")
    assertions = (
        "item_database_pool",
        "direct_draw",
        "sim_level_clamp",
        "display_item",
        "replacement_draw",
        "gear_draw",
        "gear_rival_bounds",
        "gear_lower_window",
        "gear_class_gate",
        "gear_duelist_effect",
        "gear_paladin_effect",
        "stored_items_transfer",
        "broker_gate",
        "admission",
        "gear_incompatible_storage",
        "gear_primary_storage",
        "gear_secondary_storage",
        "gear_base_upper",
        "gear_normal_upper",
        "gear_base_lower",
        "gear_initial_lower",
    )
    for assertion in assertions:
        _insert(connection, "code_facts", fact_id="auction." + assertion, key="ok", value="true")
    for fact_id in (
        "sim.aura_equipment_slot",
        "sim.aura_equipment_added",
        "sim.generated_equipment_slot_gate",
        "sim.generated_equipment_nonweapon_gate",
        "sim.generated_equipment_assignment",
        "smithing.planar_fuel",
        "loot.start_initialization_sequence",
        "loot.character_component_binding",
        "loot.corpse_component_binding",
        "item_bag.unique_initialization",
        "item_bag.single_pickup",
        "inventory.default_single_add",
        "inventory.default_single_force",
        "smithing.template_flag",
        "smithing.fuel_flag",
        "smithing.single_template_amount",
        "smithing.single_fuel_amount",
        "smithing.fuel_quality",
        "smithing.planar_input_quality",
        "smithing.planar_single_input",
        "smithing.planar_output_quality",
        "smithing.blessing_input_quality",
        "smithing.blessing_single_input",
        "smithing.blessing_outputs",
        "smithing.ascension_input_quality",
        "smithing.ascension_two_inputs",
        "smithing.ascension_equal_inputs",
        "smithing.ascension_output_quality",
    ):
        _insert(connection, "code_facts", fact_id=fact_id, key="ok", value="true")
    for key, value in (("spell_name", "Offering Stone"), ("created_item_id", "340104"), ("quantity", "1")):
        _insert(connection, "code_facts", fact_id="item.offering_stone_grant", key=key, value=value)
    for key, value in (
        ("spell_name", "Break Fossil"),
        ("quantity", "1"),
        ("pool", "GameData.Misc.FossilGame"),
        ("rolls", "1"),
    ):
        _insert(connection, "code_facts", fact_id="item.fossil_pool_grant", key=key, value=value)
    for name, value in (
        ("direct_level_cap", 35),
        ("direct_level_above", 3),
        ("direct_level_below", 5),
        ("sim_level_cap", 35),
        ("player_level_cap", 35),
    ):
        _insert(connection, "code_facts", fact_id="auction." + name, key="value", value=str(value))
    _insert(connection, "code_facts", fact_id="auction.updateah_gates", key="item_level", value=">= 40")
    _insert(connection, "code_facts", fact_id="auction.replacebag_gates", key="item_level", value="<= 0,> 39")
    _insert(connection, "code_facts", fact_id="smithing.upgrade_ids", key="strings", value="31377423,2298018,2265228")
    for component, source, item in (
        ("PlanningTableUI", "ui:planning", "item:reward"),
        ("ReplenishTMOGHide", "ui:cosmetic", "item:other"),
        ("ReplenishTMOGHide", "ui:empty", None),
    ):
        _insert(
            connection,
            "ui_item_sources",
            stable_key=source,
            component_type=component,
            scene="One",
            hierarchy_path=source,
            slot="0",
            icon_hierarchy_path=source + "/Icon",
            serialized_item_stable_key=item,
            serialized_quantity=4,
            replenish_item_stable_key=item,
            display_only=0,
            vendor_slot=0,
            loot_slot=0,
            bank_slot=0,
            mouse_slot=0,
            player_owned=0,
            not_in_inventory=1,
            slot_type="Item",
        )
    _insert(
        connection,
        "ui_item_access_targets",
        stable_key="desk:one",
        scene="One",
        hierarchy_path="Desk",
        tag="PlanningDesk",
        active_self=1,
        active_in_hierarchy=0,
        x=8,
        y=9,
        z=10,
    )
    for group, predicate, reference in ((0, "quest_done", "quest:one"), (1, "item_held", "item:material")):
        _insert(
            connection,
            "gate_conditions",
            subject_kind="ui_item_access_target",
            subject_stable_key="desk:one",
            gate="activation",
            group_index=group,
            atom_kind=predicate,
            atom_stable_key=reference,
        )
    yield connection
    connection.close()


@pytest.fixture
def selected(native_inputs: sqlite3.Connection) -> ProvenanceBuilder:
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    return builder


@pytest.fixture
def persisted(native_inputs: sqlite3.Connection) -> tuple[sqlite3.Connection, ProvenanceBuilder]:
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    return native_inputs, builder


def test_all_input_families_are_accounted_without_rederiving_facts(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    audit = validate_item_provenance(connection, builder, require_all_native_tables=False)
    for relation in (
        "loot_drops",
        "special_world_drops",
        "crafting_recipes",
        "crafting_rewards",
        "character_dialogs",
        "character_quest_manager_quests",
        "quest_required_items",
        "mining_node_items",
        "water_fishables",
        "fishing_bonus_catches",
        "item_bags",
        "item_drops",
        "spell_created_items",
        "item_conversions",
        "item_zone_restrictions",
        "quality_offerings",
        "class_starting_items",
        "auction_house_items",
        "ui_item_sources",
        "ui_item_access_targets",
        "items",
        "item_classes",
        "code_facts",
        "authored_sims",
        "authored_sim_references",
        "authored_sim_equipment",
    ):
        assert audit["input_counts"][relation] == connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]
    assert audit["input_counts"]["vendor_offers"] == 2
    assert audit["contract_counts"] == {
        "acquisitions": len(builder.acquisitions),
        "uses": len(builder.uses),
        "dispositions": 8,
    }
    assert audit["exclusions"]


def test_replacing_an_origin_with_another_origin_keeps_count_but_fails(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    before = sum(len(entries) for entries in builder.fact_evidence.values())
    for key, entries in builder.fact_evidence.items():
        builder.fact_evidence[key] = tuple(
            ProvenanceEvidence(entry.input_relation, '["wrong-source"]')
            if entry.input_relation == "mining_node_items"
            else entry
            for entry in entries
        )
    assert sum(len(entries) for entries in builder.fact_evidence.values()) == before
    with pytest.raises(ValueError, match="mining_node_items"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_native_input_added_after_selection_is_not_hidden_by_builder_expectations(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    _insert(connection, "class_starting_items", class_name="Arcanist", sort_order=0, item_stable_key="item:reward")
    with pytest.raises(ValueError, match=r"class_starting_items.*Arcanist"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_missing_excluded_identity_fails_naming_the_input(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    identity = ("loot_drops", '["character:unused","item:other"]')
    assert builder.input_exclusions.pop(identity) == "unencountered_copy"
    with pytest.raises(ValueError, match=r"loot_drops.*character:unused.*item:other"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_excluded_identity_accepts_a_nonempty_builder_reason(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    identity = ("loot_drops", '["character:unused","item:other"]')
    builder.input_exclusions[identity] = "Reviewed fixture exclusion, selected by the builder"
    audit = validate_item_provenance(connection, builder, require_all_native_tables=False)
    assert {
        "relation": identity[0],
        "primary_key": identity[1],
        "reason": builder.input_exclusions[identity],
    } in audit["exclusions"]


@pytest.mark.parametrize("reason", ["", " "])
def test_excluded_identity_requires_a_nonempty_reason(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
    reason: str,
) -> None:
    connection, builder = persisted
    builder.input_exclusions["loot_drops", '["character:unused","item:other"]'] = reason
    with pytest.raises(ValueError, match="reason"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_missing_used_identity_fails_naming_the_input(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    _drop_evidence(builder, "mining_node_items")
    with pytest.raises(ValueError, match=r"mining_node_items.*node:one.*item:reward"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_reviewed_historical_item_disposition_does_not_invent_a_current_item(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    _insert(
        connection,
        "item_dispositions",
        item_stable_key="item:historical",
        disposition="removed",
        reason="Reviewed removed lifecycle",
        evidence="reviewed-source",
        current_pages="[]",
        former_pages='["Old Item"]',
    )
    audit = validate_item_provenance(connection, builder, require_all_native_tables=False)
    assert audit["contract_counts"]["dispositions"] == 9
    connection.execute("UPDATE item_dispositions SET evidence=NULL WHERE item_stable_key='item:historical'")
    with pytest.raises(ValueError, match="Unreviewed"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_disposition_page_identity_is_not_just_a_row_count(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    connection.execute("UPDATE item_dispositions SET current_pages='[]' WHERE item_stable_key='item:reward'")
    with pytest.raises(ValueError, match="current item disposition page"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_day_night_variants_keep_their_own_local_probabilities(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    fishing = [fact for fact in builder.acquisitions if fact.kind == "fishing"]
    assert {(fact.variant_key, fact.probability_min, fact.probability_max) for fact in fishing} == {
        ("DayFishable", 25, 25),
        ("NightFishable", 75, 75),
    }
    for fact in fishing:
        assert fact.source_stable_key == "water:one"
        assert fact.probability_basis == "per_successful_catch"
        assert (fact.quantity_min, fact.quantity_max) == (1, 1)
        assert [(atom.predicate, atom.value, atom.phase) for atom in fact.conditions] == [
            ("time_of_day", "day" if fact.variant_key == "DayFishable" else "night", "operation_input")
        ]
        assert [(place.relation, place.x, place.y, place.z) for place in fact.locations] == [("fixed", 6, 7, 8)]


def test_unlocated_copy_is_an_explicit_location_not_missing_coverage(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("DELETE FROM character_spawns WHERE character_stable_key='character:b'")
    native_inputs.execute(
        "INSERT INTO spells (stable_key, display_name, image_name, pet_to_summon_stable_key) "
        "VALUES ('spell:pet', 'Pet', '', 'character:b')"
    )
    _insert(
        native_inputs,
        "loot_drops",
        character_stable_key="character:b",
        item_stable_key="item:reward",
        loot_table_stable_key="loot-table:b",
        source_component_is_enabled=1,
        drop_probability=30,
        is_actual=1,
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    fact = next(
        fact
        for fact in builder.acquisitions
        if fact.kind == "character_drop" and fact.source_copy_stable_key == "character:b"
    )
    assert len(fact.locations) == 1
    assert (fact.locations[0].relation, fact.locations[0].source_copy_stable_key) == ("unlocated", "character:b")


@pytest.mark.parametrize(
    "kind",
    [
        "character_drop",
        "common_world_item",
        "special_world_drop",
        "vendor",
        "dialog",
        "crafting",
        "quest_reward",
        "mining",
        "fishing",
        "fishing_bonus",
        "item_bag",
        "item_drop",
        "spell_created",
        "item_conversion",
        "starting_class",
        "auction_house",
        "ui_grant",
        "internal_equipment",
    ],
)
def test_every_populated_acquisition_family_selects_facts_with_input_identities(
    selected: ProvenanceBuilder,
    kind: str,
) -> None:
    builder = selected
    facts = [fact for fact in builder.acquisitions if fact.kind == kind]
    assert facts
    assert all(fact.item_stable_key for fact in facts)
    assert all(builder.fact_evidence[fact.acquisition_key] for fact in facts)


@pytest.mark.parametrize(
    "kind",
    [
        "crafting_recipe",
        "crafting_material",
        "quest_requirement",
        "item_drop",
        "spell_created",
        "item_conversion",
        "zone_restriction",
        "quality_offering",
        "smithing",
    ],
)
def test_every_populated_use_family_selects_facts_with_input_identities(
    selected: ProvenanceBuilder,
    kind: str,
) -> None:
    builder = selected
    facts = [fact for fact in builder.uses if fact.kind == kind]
    assert facts
    assert all(fact.item_stable_key for fact in facts)
    assert all(builder.fact_evidence[fact.use_key] for fact in facts)


def test_quest_rewards_select_only_executed_manager_routes(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    facts = [fact for fact in builder.acquisitions if fact.kind == "quest_reward"]
    assert len(facts) == 2
    assert {
        (fact.source_stable_key, fact.source_copy_stable_key, fact.variant_key, fact.item_stable_key) for fact in facts
    } == {("quest:one", "character:a", "One", "item:reward")}
    assert {
        entry.input_primary_key
        for fact in facts
        for entry in _evidence(builder, "character_quest_manager_quests", fact.acquisition_key)
    } == {
        '["character:a",0]',
        '["character:a",1]',
    }
    assert len({fact.mechanic for fact in facts}) == 2
    assert builder.input_exclusions["quest_variants", '["Unrouted"]'] == "no_executed_item_grant"


def test_quest_turnin_duplicate_slots_are_aggregated_only_in_the_gate(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    rewards = [fact for fact in builder.acquisitions if fact.kind == "quest_reward"]
    assert len(rewards) == 2
    for fact in rewards:
        assert [
            (atom.reference_stable_key, atom.minimum) for atom in fact.conditions if atom.gate_key == "turnin_items"
        ] == [("item:material", 5)]
    uses = [use for use in builder.uses if use.kind == "quest_requirement"]
    assert {(use.material_slot, use.quantity_min, use.quantity_max) for use in uses} == {(0, 2, 2), (1, 3, 3)}


_OFFERING_COLUMNS = (
    "first_item_stable_key, second_item_stable_key, chance_per_stone_pair, chance_per_improvement_level, "
    "enhance_chance_per_stone_pair, result_quality, enhanced_quality"
)


def test_flame_wells_of_one_group_share_each_offering_use(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute(
        f"INSERT INTO quality_offerings (character_stable_key, {_OFFERING_COLUMNS}) "
        f"SELECT 'character:b', {_OFFERING_COLUMNS} FROM quality_offerings WHERE character_stable_key='character:a'"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    offerings = [use for use in builder.uses if use.kind == "quality_offering"]
    inputs = [(use.item_stable_key, use.material_slot) for use in offerings]
    assert len(inputs) == len(set(inputs))
    assert {use.target_stable_key for use in offerings} == {"character:a"}
    for use in offerings:
        assert {location.source_copy_stable_key for location in use.locations} == {"character:a", "character:b"}


def test_flame_wells_of_one_group_must_take_one_offering(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute(
        f"INSERT INTO quality_offerings (character_stable_key, {_OFFERING_COLUMNS}) "
        f"SELECT 'character:b', {_OFFERING_COLUMNS} FROM quality_offerings WHERE character_stable_key='character:a'"
    )
    native_inputs.execute(
        "UPDATE quality_offerings SET chance_per_stone_pair=9 WHERE character_stable_key='character:b'"
    )
    with pytest.raises(ValueError, match="take different offerings"):
        ProvenanceBuilder(native_inputs).select()


@pytest.mark.parametrize("active_in_hierarchy", [0, 1])
def test_box_of_portals_keeps_shared_quest_gate(native_inputs: sqlite3.Connection, active_in_hierarchy: int) -> None:
    native_inputs.execute("UPDATE items SET display_name='Box of Portals' WHERE stable_key='item:reward'")
    native_inputs.execute("UPDATE ui_item_access_targets SET active_in_hierarchy=?", (active_in_hierarchy,))
    native_inputs.execute("DELETE FROM gate_conditions WHERE subject_kind='ui_item_access_target'")
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="ui_item_access_target",
        subject_stable_key="desk:one",
        gate="activation",
        group_index=0,
        atom_kind="quest_done",
        atom_stable_key="quest:one",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.ui_grants()
    box = next(fact for fact in builder.acquisitions if fact.source_stable_key == "ui:planning")
    assert box.item_stable_key == "item:reward"
    assert len(box.locations) == 1
    location = box.locations[0]
    assert location.location_key == "desk:one"
    assert [(atom.predicate, atom.reference_stable_key, atom.scope) for atom in location.conditions] == [
        ("quest_done", "quest:one", "desk:one")
    ]
    assert {(row.input_relation, row.input_primary_key) for row in builder.fact_evidence[box.acquisition_key]} == {
        ("ui_item_sources", '["ui:planning"]'),
        ("ui_item_access_targets", '["desk:one"]'),
    }


def test_ui_access_preserves_shared_gate_alternatives_and_impossibility(native_inputs: sqlite3.Connection) -> None:
    builder = ProvenanceBuilder(native_inputs)
    builder.ui_grants()
    box = next(fact for fact in builder.acquisitions if fact.source_stable_key == "ui:planning")
    assert sorted(
        (atom.group_index, atom.predicate, atom.reference_stable_key) for atom in box.locations[0].conditions
    ) == [
        (0, "quest_done", "quest:one"),
        (1, "item_held", "item:material"),
    ]
    native_inputs.execute("DELETE FROM gate_conditions WHERE subject_kind='ui_item_access_target'")
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="ui_item_access_target",
        subject_stable_key="desk:one",
        gate="activation",
        group_index=0,
        atom_kind="never",
        atom_stable_key="desk:one",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.ui_grants()
    box = next(fact for fact in builder.acquisitions if fact.source_stable_key == "ui:planning")
    assert not conditions_satisfiable(box.locations[0].conditions)


def test_ui_location_preserves_repeated_defeat_quantity(native_inputs: sqlite3.Connection) -> None:
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="ui_item_access_target",
        subject_stable_key="desk:one",
        gate="ward_deaths",
        group_index=0,
        atom_kind="encounter_won",
        atom_stable_key="character:a",
        atom_quantity=9,
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    box = next(fact for fact in builder.acquisitions if fact.source_stable_key == "ui:planning")
    assert len(box.locations) == 1
    defeats = [atom for atom in box.locations[0].conditions if atom.predicate == "encounter_won"]
    assert len(defeats) == 1
    assert (defeats[0].reference_stable_key, defeats[0].scope, defeats[0].minimum) == ("character:a", "desk:one", 9)


@pytest.mark.parametrize("assembly", ["fixture-assembly", "old-assembly"])
def test_verified_ui_access_requires_matching_durable_receipt(
    native_inputs: sqlite3.Connection,
    assembly: str,
) -> None:
    _insert(
        native_inputs,
        "item_access_observations",
        component_type="ReplenishTMOGHide",
        slot="0",
        assembly_sha256=assembly,
        player_access_state="verified_player",
        transfer="normal_pointer_inventory_transfer",
        replenishment="while_source_active",
        receipt="Native fixture transfer and replenishment.",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    cosmetic = next(fact for fact in builder.acquisitions if fact.source_stable_key == "ui:cosmetic")
    assert cosmetic.player_access_state == (
        "verified_player" if assembly == "fixture-assembly" else "unconfirmed_player"
    )


def test_unused_native_ui_locations_have_explicit_exclusion_outcomes(native_inputs: sqlite3.Connection) -> None:
    _insert(
        native_inputs,
        "ui_item_access_targets",
        stable_key="desk:unused",
        scene="One",
        hierarchy_path="Other",
        tag="Other",
        active_self=1,
        active_in_hierarchy=1,
        x=0,
        y=0,
        z=0,
    )
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="ui_item_access_target",
        subject_stable_key="desk:unused",
        gate="activation",
        group_index=0,
        atom_kind="quest_done",
        atom_stable_key="quest:one",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder, require_all_native_tables=False)
    assert audit["input_counts"]["ui_item_access_targets"] == 2
    assert builder.input_exclusions["ui_item_access_targets", '["desk:unused"]'] == "unused_native_ui_target"
    assert ProvenanceEvidence("ui_item_access_targets", '["desk:unused"]') not in _evidence(
        builder, "ui_item_access_targets"
    )
    builder.input_exclusions.pop(("ui_item_access_targets", '["desk:unused"]'))
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(native_inputs, builder, require_all_native_tables=False)


def test_validator_does_not_require_a_connection_row_factory(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    connection.row_factory = None
    audit = validate_item_provenance(connection, builder, require_all_native_tables=False)
    assert audit["input_counts"]["water_fishables"] == 2


@pytest.mark.parametrize(
    "relation",
    [
        "loot_drops",
        "special_world_drops",
        "vendor_offers",
        "character_dialogs",
        "crafting_rewards",
        "crafting_recipes",
        "quest_variants",
        "character_quest_manager_quests",
        "quest_required_items",
        "mining_node_items",
        "water_fishables",
        "fishing_bonus_catches",
        "item_bags",
        "item_drops",
        "spell_created_items",
        "item_conversions",
        "item_zone_restrictions",
        "quality_offerings",
        "class_starting_items",
        "auction_house_items",
        "ui_item_sources",
        "ui_item_access_targets",
        "items",
        "item_classes",
        "code_facts",
    ],
)
def test_each_populated_origin_relation_is_required(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
    relation: str,
) -> None:
    connection, builder = persisted
    assert _evidence(builder, relation)
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    _drop_evidence(builder, relation)
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


@pytest.fixture
def raw_persisted(
    native_inputs: sqlite3.Connection,
) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder]]:
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.executescript(
        "CREATE TABLE Characters (StableKey TEXT PRIMARY KEY, DestroyOnDeath "
        "INTEGER, DoNotLeaveCorpse INTEGER, IsSimPlayer INTEGER);"
        "CREATE TABLE LootDrops (LootTableStableKey TEXT, CharacterStableKey TEXT, ItemStableKey TEXT, "
        "DropProbability REAL, ExpectedPerKill REAL, DropCountDistribution TEXT, "
        "IsActual INTEGER, IsGuaranteed INTEGER, "
        "IsCommon INTEGER, IsCommonWorldItem INTEGER, IsUncommon INTEGER, IsRare INTEGER, IsLegendary INTEGER, "
        "IsUltraRare INTEGER, PRIMARY KEY(LootTableStableKey,ItemStableKey));"
        "CREATE TABLE LootTableSources (StableKey TEXT PRIMARY KEY, "
        "CharacterStableKey TEXT, MiningNodeStableKey TEXT, ComponentIndex INTEGER, "
        "ComponentIsEnabled INTEGER, MaxNumberDrops INTEGER, MaxNonCommonDrops "
        "INTEGER, NumberOfGuaranteedDrops INTEGER, "
        "UltraRareDropCount INTEGER, LegendaryDropCount INTEGER, RareDropCount INTEGER, UncommonDropCount INTEGER, "
        "CommonDropCount INTEGER, GuaranteeOneDropCount INTEGER, ActualDropsCount INTEGER);"
        "CREATE TABLE LootTablePoolSlots (LootTableStableKey TEXT, Pool TEXT, Position INTEGER, ItemStableKey TEXT, "
        "PRIMARY KEY(LootTableStableKey,Pool,Position));"
        "CREATE TABLE CommonWorldItems (Position INTEGER PRIMARY KEY, ItemStableKey TEXT);"
        "CREATE TABLE SpecialWorldDropItems (Pool TEXT, Position INTEGER, "
        "ItemStableKey TEXT, PRIMARY KEY(Pool,Position));"
        "CREATE TABLE SpecialWorldDropFlags (Name TEXT PRIMARY KEY, Value INTEGER);"
        "CREATE TABLE MiningNodes (StableKey TEXT PRIMARY KEY, CommonCount INTEGER, "
        "RareCount INTEGER, LegendCount INTEGER);"
        "CREATE TABLE MiningNodeItems (MiningNodeStableKey TEXT, ItemStableKey TEXT, DropChance REAL, "
        "PRIMARY KEY(MiningNodeStableKey,ItemStableKey));"
        "CREATE TABLE MiningNodePoolSlots (MiningNodeStableKey TEXT, Pool TEXT, Position INTEGER, ItemStableKey TEXT, "
        "PRIMARY KEY(MiningNodeStableKey,Pool,Position));"
        "CREATE TABLE MiningFallbackItems (SourceKey TEXT PRIMARY KEY, ItemStableKey TEXT);"
        "CREATE TABLE Waters (StableKey TEXT PRIMARY KEY);"
        "CREATE TABLE WaterFishables (WaterStableKey TEXT, Type TEXT, Position INTEGER, ItemStableKey TEXT, "
        "PRIMARY KEY(WaterStableKey,Type,Position));"
        "CREATE TABLE ItemDrops (SourceItemStableKey TEXT, DroppedItemStableKey TEXT, PoolStableKey TEXT, "
        "DropProbability REAL, IsGuaranteed INTEGER, PRIMARY "
        "KEY(SourceItemStableKey,DroppedItemStableKey,PoolStableKey));"
        "CREATE TABLE ItemDropPools (PoolStableKey TEXT PRIMARY KEY, SourceComponentKey TEXT, SlotCount INTEGER);"
        "CREATE TABLE ItemDropPoolSlots (PoolStableKey TEXT, Position INTEGER, "
        "ItemStableKey TEXT, PRIMARY KEY(PoolStableKey,Position));"
        "CREATE TABLE NativeItemBindings (BindingKey TEXT PRIMARY KEY, "
        "SourceComponentKey TEXT NOT NULL, ItemStableKey TEXT);"
    )
    _insert(
        raw,
        "NativeItemBindings",
        BindingKey="GameManager.PlanarShard",
        SourceComponentKey="component:game-manager",
        ItemStableKey="item:material",
    )
    for copy in ("a", "b", "unused"):
        _insert(raw, "Characters", StableKey="character:" + copy, DestroyOnDeath=0, DoNotLeaveCorpse=0, IsSimPlayer=0)
    mapping = {
        "LootTableStableKey": "loot_table_stable_key",
        "CharacterStableKey": "character_stable_key",
        "ItemStableKey": "item_stable_key",
        "DropProbability": "drop_probability",
        "ExpectedPerKill": "expected_per_kill",
        "DropCountDistribution": "drop_count_distribution",
        "IsActual": "is_actual",
        "IsGuaranteed": "is_guaranteed",
        "IsCommon": "is_common",
        "IsCommonWorldItem": "is_common_world_item",
        "IsUncommon": "is_uncommon",
        "IsRare": "is_rare",
        "IsLegendary": "is_legendary",
        "IsUltraRare": "is_ultra_rare",
    }
    for row in native_inputs.execute("SELECT * FROM loot_drops"):
        _insert(raw, "LootDrops", **{native: row[clean] for native, clean in mapping.items()})
    for copy, flags in (("destroyed", (1, 0, 0)), ("corpse", (0, 1, 0)), ("sim", (0, 0, 1)), ("reviewed", (0, 0, 0))):
        _insert(
            raw,
            "Characters",
            StableKey="character:" + copy,
            DestroyOnDeath=flags[0],
            DoNotLeaveCorpse=flags[1],
            IsSimPlayer=flags[2],
        )
        _insert(
            raw,
            "LootDrops",
            LootTableStableKey="loot-table:" + copy,
            CharacterStableKey="character:" + copy,
            ItemStableKey="item:reward",
            DropProbability=100,
            ExpectedPerKill=1,
            DropCountDistribution="[0,1]",
            IsActual=1,
            IsGuaranteed=0,
        )
    for copy in ("a", "b", "unused", "destroyed", "corpse", "sim", "reviewed", "hostless"):
        actual = [] if copy in ("b", "hostless") else ["item:other" if copy == "unused" else "item:reward"]
        common = ["item:material"] if copy in ("a", "b") else []
        _insert(
            raw,
            "LootTableSources",
            StableKey="loot-table:" + copy,
            CharacterStableKey=None if copy == "hostless" else "character:" + copy,
            MiningNodeStableKey=None,
            ComponentIndex=0,
            ComponentIsEnabled=1,
            MaxNumberDrops=2,
            MaxNonCommonDrops=1,
            NumberOfGuaranteedDrops=0,
            UltraRareDropCount=0,
            LegendaryDropCount=0,
            RareDropCount=0,
            UncommonDropCount=0,
            CommonDropCount=len(common),
            GuaranteeOneDropCount=0,
            ActualDropsCount=len(actual),
        )
        for pool, entries in (("ActualDrops", actual), ("CommonDrop", common)):
            for position, item in enumerate(entries):
                _insert(
                    raw,
                    "LootTablePoolSlots",
                    LootTableStableKey="loot-table:" + copy,
                    Pool=pool,
                    Position=position,
                    ItemStableKey=item,
                )
    for position, item in enumerate(("item:common", None)):
        _insert(raw, "CommonWorldItems", Position=position, ItemStableKey=item)
    for pool, entries in (("Maps", ("item:other", None, None, None)), ("level_pool", ("item:reward", None))):
        for position, item in enumerate(entries):
            _insert(raw, "SpecialWorldDropItems", Pool=pool, Position=position, ItemStableKey=item)
    _insert(raw, "SpecialWorldDropFlags", Name="DropMasks", Value=0)
    _insert(raw, "SpecialWorldDropFlags", Name="DemoBuild", Value=0)
    _insert(raw, "MiningNodes", StableKey="node:one", CommonCount=2, RareCount=0, LegendCount=0)
    _insert(raw, "MiningNodeItems", MiningNodeStableKey="node:one", ItemStableKey="item:reward", DropChance=15)
    for pool, entries in (("guarantee", ("item:reward",)), ("Common", ("item:reward", None))):
        for position, item in enumerate(entries):
            _insert(
                raw,
                "MiningNodePoolSlots",
                MiningNodeStableKey="node:one",
                Pool=pool,
                Position=position,
                ItemStableKey=item,
            )
    _insert(raw, "MiningFallbackItems", SourceKey="GameManager.GuaranteeMine", ItemStableKey="item:material")
    _insert(raw, "Waters", StableKey="water:one")
    for period, entries in (
        ("DayFishable", ("item:reward", None)),
        ("NightFishable", ("item:reward", "item:reward", None)),
    ):
        for position, item in enumerate(entries):
            _insert(
                raw, "WaterFishables", WaterStableKey="water:one", Type=period, Position=position, ItemStableKey=item
            )
    _insert(raw, "ItemDropPools", PoolStableKey="pool:fossils", SourceComponentKey="GameData.FossilGame", SlotCount=5)
    _insert(
        raw,
        "ItemDrops",
        SourceItemStableKey="item:input",
        DroppedItemStableKey="item:reward",
        PoolStableKey="pool:fossils",
        DropProbability=40,
        IsGuaranteed=1,
    )
    for position, item in enumerate(("item:reward", "item:reward", None, None, None)):
        _insert(raw, "ItemDropPoolSlots", PoolStableKey="pool:fossils", Position=position, ItemStableKey=item)
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.raw_loot_evidence(raw, frozenset({"character:reviewed"}))
    builder.attach_native_inputs(raw)
    builder.account_support_inputs()
    builder.attach_direct_native_inputs(raw)
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    yield native_inputs, raw, builder
    raw.close()


def test_raw_native_anti_join_preserves_every_host_exclusion_and_origin(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, raw, builder = raw_persisted
    audit = validate_item_provenance(
        connection,
        builder,
        raw=raw,
        require_all_native_tables=False,
    )
    assert audit["input_counts"]["raw.LootDrops"] == 8
    atoms = [atom for fact in builder.acquisitions for atom in fact.conditions if atom.gate_key == "loot_host"]
    assert len(atoms) == 4
    assert {atom.value for atom in atoms} == {
        "loot_host_destroy_on_death",
        "loot_host_do_not_leave_corpse",
        "non_player_host",
        "reviewed_unexecuted_loot",
    }
    assert builder.input_exclusions["raw.LootTableSources", '["loot-table:hostless"]'] == "loot_host_missing"


def test_lifecycle_input_requires_historical_keys_without_guessing_page_only_keys(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
    tmp_path: Path,
) -> None:
    connection, builder = persisted
    path = tmp_path / "lifecycle.json"
    page = {
        "stable_key": "item:historical",
        "state": "removed",
        "thing": "item",
        "update": None,
        "date": None,
        "patch_notes_url": None,
        "source": "Reviewed removal",
    }
    path.write_text(
        json.dumps(
            {"pages": {"Old Item": page, "Page Only": {**page, "stable_key": None}}, "renames": {}, "splits": {}}
        ),
        encoding="utf-8",
    )
    _insert(
        connection,
        "item_dispositions",
        item_stable_key="item:historical",
        disposition="removed",
        reason="Reviewed removed lifecycle",
        evidence="Reviewed removal",
        current_pages="[]",
        former_pages='["Old Item"]',
    )
    audit = validate_item_provenance(connection, builder, lifecycle_path=path, require_all_native_tables=False)
    assert audit["contract_counts"]["dispositions"] == 9
    connection.execute("DELETE FROM item_dispositions WHERE item_stable_key='item:historical'")
    with pytest.raises(ValueError, match="disposition identities"):
        validate_item_provenance(connection, builder, lifecycle_path=path, require_all_native_tables=False)


@pytest.mark.parametrize("kind", ["character_drop", "special_world_drop"])
def test_unique_loot_requires_native_ownership_replacement_condition(
    native_inputs: sqlite3.Connection,
    kind: str,
) -> None:
    native_inputs.execute("UPDATE items SET is_unique=1 WHERE stable_key IN ('item:reward', 'item:common')")
    native_inputs.execute("UPDATE loot_drops SET is_unique=0")
    _insert(native_inputs, "code_facts", fact_id="loot.owned_unique_replacement", key="ok", value="true")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == kind and fact.item_stable_key == "item:reward"]
    assert len(facts) == 1
    assert [
        (atom.predicate, atom.reference_stable_key, atom.value)
        for atom in facts[0].conditions
        if atom.gate_key == "not_owned"
    ] == [
        ("item_not_owned", "item:reward", "stored_slots_and_equipment_slots"),
    ]
    common = [fact for fact in builder.acquisitions if fact.kind == "common_world_item"]
    assert common
    assert not any(atom.gate_key == "not_owned" for fact in common for atom in fact.conditions)


def test_guaranteed_roll_count_is_a_native_quantity_dimension(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE characters SET guaranteed_drop_rolls=3 WHERE stable_key='character:a'")
    native_inputs.execute(
        "UPDATE loot_drops SET is_guaranteed=1 "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:reward'"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == "character_drop"]
    assert len(facts) == 1
    assert facts[0].guaranteed_roll_count == 3


def test_dialog_ownership_condition_preserves_native_inventory_scope(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    dialogs = [fact for fact in builder.acquisitions if fact.kind == "dialog"]
    assert len(dialogs) == 1
    assert [(atom.predicate, atom.value) for atom in dialogs[0].conditions if atom.predicate == "item_not_owned"] == [
        ("item_not_owned", "stored_slots_and_equipment_slots")
    ]


def test_same_named_character_and_spawn_gates_preserve_independent_or_groups(
    native_inputs: sqlite3.Connection,
) -> None:
    native_inputs.execute(
        "UPDATE gate_conditions SET atom_kind='never' WHERE subject_kind='character' "
        "AND subject_stable_key='character:a' AND gate='unlock'"
    )
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="character",
        subject_stable_key="character:a",
        gate="unlock",
        group_index=1,
        atom_kind="quest_done",
        atom_stable_key="quest:one",
    )
    _insert(
        native_inputs,
        "gate_conditions",
        subject_kind="spawn_point",
        subject_stable_key="spawn:a",
        gate="unlock",
        group_index=1,
        atom_kind="never",
        atom_stable_key="quest:one",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    fact = next(
        fact
        for fact in builder.acquisitions
        if fact.kind == "character_drop" and fact.source_copy_stable_key == "character:a"
    )
    locations = [location for location in fact.locations if location.relation == "spawn"]
    assert len(locations) == 1
    atoms = locations[0].conditions
    character_gate = 'gate:["character","character:a",null,"unlock"]'
    spawn_gate = 'gate:["spawn_point","spawn:a",null,"unlock"]'
    for gate in (character_gate, spawn_gate):
        assert {atom.group_index for atom in atoms if atom.gate_key == gate} == {0, 1}
    assert conditions_satisfiable(atoms)
    impossible_spawn = tuple(
        replace(atom, predicate="never") if atom.gate_key == spawn_gate else atom for atom in atoms
    )
    assert not conditions_satisfiable(impossible_spawn)


def test_initialization_parameters_and_operation_time_keep_their_phases(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    loot = next(fact for fact in builder.acquisitions if fact.kind == "character_drop")
    context = [atom for atom in loot.conditions if atom.gate_key == "probability_context"]
    assert {(atom.value, atom.minimum, atom.maximum, atom.actor) for atom in context} == {
        ("server_loot_rate", 1, 1, None),
        ("loot_bless_bonus", 0, 0, None),
        ("top_guild_bonus", 0, 0, "player"),
        ("initial_owned_unique_item_count", 0, 0, "player"),
    }
    assert {atom.phase for atom in context} == {"source_initialization"}
    assert {atom.scope for atom in context} == {"probability"}
    for fact in builder.acquisitions:
        for atom in fact.conditions:
            if atom.gate_key == "time":
                assert atom.phase == "operation_input"


def test_unique_bag_suppression_is_an_initialization_condition(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE items SET is_unique=1 WHERE stable_key='item:reward'")
    _insert(native_inputs, "code_facts", fact_id="loot.owned_unique_replacement", key="ok", value="true")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    bag = next(fact for fact in builder.acquisitions if fact.kind == "item_bag")
    assert [
        (atom.predicate, atom.value, atom.phase) for atom in bag.conditions if atom.gate_key == "initial_ownership"
    ] == [
        ("item_not_owned", "stored_slots_and_equipment_slots", "source_initialization"),
    ]


def test_special_pool_zero_level_sentinel_has_no_enemy_level_gate(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE special_world_drops SET min_level_exclusive=0")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == "special_world_drop"]
    assert len(facts) == 1
    assert not any(atom.gate_key == "enemy_level" for atom in facts[0].conditions)


def test_dialog_repeatability_comes_from_exact_assigned_resource(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE quest_variants SET repeatable=1 WHERE resource_name IN ('Unrouted', 'NoReward')")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    dialogs = [fact for fact in builder.acquisitions if fact.kind == "dialog"]
    assert len(dialogs) == 1
    assert [
        (atom.predicate, atom.reference_stable_key)
        for atom in dialogs[0].conditions
        if atom.gate_key == "dialog_assignment"
    ] == [("quest_not_done", "quest:one")]


def test_duplicate_vendor_slots_are_one_offer_with_all_native_identities(native_inputs: sqlite3.Connection) -> None:
    _insert(
        native_inputs,
        "character_vendor_items",
        character_stable_key="character:a",
        item_slot=9,
        item_stable_key="item:reward",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder, require_all_native_tables=False)
    assert audit["input_counts"]["vendor_offers"] == 3
    facts = [
        fact
        for fact in builder.acquisitions
        if fact.kind == "vendor"
        and fact.source_copy_stable_key == "character:a"
        and fact.item_stable_key == "item:reward"
    ]
    assert len(facts) == 1 and facts[0].variant_key is None
    owner = facts[0].acquisition_key
    assert {entry.input_primary_key for entry in _evidence(builder, "vendor_offers", owner)} == {
        '["character:a","base",2]',
        '["character:a","base",9]',
    }
    builder.fact_evidence[owner] = tuple(
        entry
        for entry in builder.fact_evidence[owner]
        if entry != ProvenanceEvidence("vendor_offers", '["character:a","base",9]')
    )
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(native_inputs, builder, require_all_native_tables=False)


def test_item_draw_pool_is_part_of_each_outcome_and_use_identity(native_inputs: sqlite3.Connection) -> None:
    _insert(
        native_inputs,
        "item_drops",
        source_item_stable_key="item:input",
        dropped_item_stable_key="item:reward",
        pool_stable_key="pool:second",
        drop_probability=25,
        is_guaranteed=0,
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = sorted(
        (fact for fact in builder.acquisitions if fact.kind == "item_drop"), key=lambda fact: fact.variant_key or ""
    )
    assert len(facts) == 2
    assert [fact.variant_key for fact in facts] == ["pool:fossils", "pool:second"]
    for fact in facts:
        use = next(use for use in builder.uses if use.outcome_key == fact.acquisition_key)
        assert (fact.quantity_min, fact.guaranteed_roll_count, use.variant_key) == (1, 1, fact.variant_key)
    assert [(fact.expected_quantity, json.loads(fact.count_distribution or "null")) for fact in facts] == [
        (0.4, [0.6, 0.4]),
        (0.25, [0.75, 0.25]),
    ]


@pytest.mark.parametrize(
    "relation",
    [
        "raw.LootDrops",
        "raw.LootTableSources",
        "raw.LootTablePoolSlots",
        "raw.CommonWorldItems",
        "raw.SpecialWorldDropItems",
        "raw.MiningNodes",
        "raw.MiningNodeItems",
        "raw.MiningNodePoolSlots",
        "raw.Waters",
        "raw.WaterFishables",
        "raw.ItemDrops",
        "raw.ItemDropPools",
        "raw.ItemDropPoolSlots",
    ],
)
def test_native_configuration_and_all_slot_origins_are_required(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
    relation: str,
) -> None:
    connection, raw, builder = raw_persisted
    validate_item_provenance(
        connection,
        builder,
        raw=raw,
        require_all_native_tables=False,
    )
    assert _evidence(builder, relation)
    _drop_evidence(builder, relation)
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(
            connection,
            builder,
            raw=raw,
            require_all_native_tables=False,
        )


@pytest.mark.parametrize("relation", ["authored_sims", "authored_sim_references", "authored_sim_equipment"])
def test_authored_native_defaults_remain_internal_with_complete_evidence(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
    relation: str,
) -> None:
    connection, builder = persisted
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    seeds = [fact for fact in builder.acquisitions if fact.mechanic == "authored_sim_seed"]
    assert len(seeds) == 1 and seeds[0].player_access_state == "internal_only"
    assert len(_evidence(builder, relation)) == 1
    _drop_evidence(builder, relation)
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_empty_authored_seed_configuration_is_explicit(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE authored_sim_equipment SET item_stable_key=NULL")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder, require_all_native_tables=False)
    assert audit["input_counts"]["authored_sim_equipment"] == 2
    assert builder.input_exclusions["authored_sims", '["authored-sim:fixture"]'] == "empty_authored_seed_configuration"
    assert (
        builder.input_exclusions["authored_sim_references", '["component:fixture-preset",2]']
        == "empty_authored_seed_configuration"
    )
    assert not any(fact.mechanic == "authored_sim_seed" for fact in builder.acquisitions)


def test_literal_grant_quantity_changes_the_selected_fact(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE spell_created_items SET quantity=2")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    fact = next(fact for fact in builder.acquisitions if fact.kind == "spell_created")
    assert (fact.item_stable_key, fact.variant_key, fact.quantity_min, fact.quantity_max) == (
        "item:other",
        "spell:create",
        2,
        2,
    )
    use = next(use for use in builder.uses if use.kind == "spell_created")
    assert (use.item_stable_key, use.quantity_min, use.outcome_key) == ("item:input", 1, fact.acquisition_key)


def test_smithing_native_byproduct_links_every_consumed_role(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> None:
    _, _, builder = raw_persisted
    outcomes = [fact for fact in builder.acquisitions if fact.variant_key == "blessing_removal_byproduct"]
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert (outcome.item_stable_key, outcome.quantity_min) == ("item:material", 1)
    consumed = [
        use
        for use in builder.uses
        if use.mechanic
        in (
            "remove_blessing",
            "blessing_removal_material",
            "blessing_removal_fuel",
        )
    ]
    assert len(consumed) == 3
    assert {use.outcome_key for use in consumed} == {outcome.acquisition_key}


def test_partial_native_fixture_reports_missing_families_and_full_mode_rejects_them(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, raw, builder = raw_persisted
    audit = validate_item_provenance(
        connection,
        builder,
        raw=raw,
        require_all_native_tables=False,
    )
    assert "CraftingRecipes" in audit["unsupported_native_tables"]
    assert "AuthoredSimEquipment" in audit["unsupported_native_tables"]
    assert "TreasureLocations" in audit["unsupported_native_tables"]
    with pytest.raises(ValueError, match="Unsupported native input tables"):
        validate_item_provenance(
            connection,
            builder,
            raw=raw,
            require_all_native_tables=True,
        )


def test_full_native_mode_requires_an_actual_native_database(
    persisted: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = persisted
    with pytest.raises(ValueError, match="requires a raw database"):
        validate_item_provenance(connection, builder, require_all_native_tables=True)


@pytest.mark.parametrize(
    ("table", "ddl", "rows"),
    [
        (
            "CraftingRecipes",
            "RecipeItemStableKey TEXT,MaterialSlot INTEGER,MaterialItemStableKey TEXT,MaterialQuantity INTEGER,"
            "PRIMARY KEY(RecipeItemStableKey,MaterialSlot)",
            (("item:recipe", 1, "item:material", 4), ("item:recipe", 2, "item:material", 5)),
        ),
        (
            "CraftingRewards",
            "RecipeItemStableKey TEXT,RewardSlot INTEGER,RewardItemStableKey TEXT,RewardQuantity INTEGER,"
            "PRIMARY KEY(RecipeItemStableKey,RewardSlot)",
            (("item:recipe", 1, "item:reward", 1), ("item:recipe", 2, "item:reward", 1)),
        ),
        (
            "ClassStartingItems",
            "ClassName TEXT,SortOrder INTEGER,ItemStableKey TEXT,PRIMARY KEY(ClassName,SortOrder)",
            (("Paladin", 0, "item:reward"), ("Paladin", 1, "item:reward")),
        ),
        (
            "ItemBags",
            "StableKey TEXT PRIMARY KEY,ItemStableKey TEXT,Scene TEXT,X REAL,Y REAL,Z "
            "REAL,Respawns INTEGER,RespawnTimer REAL",
            (("bag:one", "item:reward", "One", 4, 3, 2, 0, 0),),
        ),
        (
            "CharacterVendorItems",
            "CharacterStableKey TEXT,ItemSlot INTEGER,ItemStableKey TEXT,PRIMARY KEY(CharacterStableKey,ItemSlot)",
            (("character:a", 2, "item:reward"),),
        ),
        (
            "CharacterVendorQuestUnlocks",
            "CharacterStableKey TEXT,QuestSlot INTEGER,QuestStableKey TEXT,QuestVariantResourceName TEXT,"
            "PRIMARY KEY(CharacterStableKey,QuestSlot)",
            (("character:a", 7, "quest:one", "One"),),
        ),
        (
            "CharacterDialogs",
            "CharacterStableKey TEXT,DialogIndex INTEGER,GiveItemStableKey TEXT,RequiredQuestStableKey TEXT,"
            "AssignQuestStableKey TEXT,AssignQuestVariantResourceName "
            "TEXT,CompleteQuestStableKey TEXT,PRIMARY "
            "KEY(CharacterStableKey,DialogIndex)",
            (
                ("character:a", 2, "item:reward", "quest:one", "quest:one", "One", None),
                ("character:unused", 2, "item:reward", "quest:one", "quest:one", "One", None),
            ),
        ),
        (
            "CharacterQuestManagerQuests",
            "CharacterStableKey TEXT,QuestSlot INTEGER,QuestStableKey TEXT,QuestVariantResourceName TEXT,"
            "PRIMARY KEY(CharacterStableKey,QuestSlot)",
            (
                ("character:a", 0, "quest:one", "One"),
                ("character:a", 1, "quest:one", "One"),
                ("character:a", 2, "quest:one", "NoReward"),
                ("character:unused", 0, "quest:one", "One"),
            ),
        ),
        (
            "QuestVariants",
            "ResourceName TEXT PRIMARY KEY,QuestStableKey TEXT,Repeatable INTEGER,"
            "ItemOnCompleteStableKey TEXT,UnlockItemForVendorStableKey TEXT",
            (
                ("One", "quest:one", 0, "item:reward", "item:other"),
                ("Unrouted", "quest:one", 0, "item:reward", None),
                ("NoReward", "quest:one", 0, None, None),
            ),
        ),
        (
            "QuestRequiredItems",
            "QuestVariantResourceName TEXT,RequiredSlot INTEGER,ItemStableKey TEXT,Quantity INTEGER,"
            "PRIMARY KEY(QuestVariantResourceName,RequiredSlot)",
            (("One", 0, "item:material", 2), ("One", 1, "item:material", 3)),
        ),
        (
            "AuthoredSims",
            "StableKey TEXT PRIMARY KEY,PrefabGuid TEXT,PrefabLocalId INTEGER,PrefabPath TEXT,ObjectName TEXT,"
            "RawCharacterStableKey TEXT,NPCName TEXT,SeedClassName TEXT,SeedLevel "
            "INTEGER,SeedSkillLevel REAL,SeedIsMale INTEGER,"
            "SeedHairName TEXT,SeedHairColor INTEGER,SeedSkinColor INTEGER,IsGMCharacter INTEGER,Rival INTEGER",
            (
                (
                    "authored-sim:fixture",
                    "ffffffffffffffffffffffffffffffff",
                    42,
                    "Assets/Fixture.prefab",
                    "Fixture seed",
                    "character:seed",
                    "Fixture seed",
                    "Paladin",
                    10,
                    5,
                    1,
                    "Hair",
                    0,
                    0,
                    0,
                    0,
                ),
            ),
        ),
        (
            "AuthoredSimReferences",
            "SourceComponentKey TEXT,ReferenceIndex INTEGER,SourceScene TEXT,SourceScenePath TEXT,"
            "AuthoredSimStableKey TEXT,PRIMARY KEY(SourceComponentKey,ReferenceIndex)",
            (("component:fixture-preset", 2, "One", "Assets/One.unity", "authored-sim:fixture"),),
        ),
        (
            "AuthoredSimEquipment",
            "AuthoredSimStableKey TEXT,Position INTEGER,ItemStableKey TEXT,PRIMARY KEY(AuthoredSimStableKey,Position)",
            (("authored-sim:fixture", 0, "item:reward"), ("authored-sim:fixture", 1, None)),
        ),
        (
            "TreasureLocations",
            "StableKey TEXT PRIMARY KEY,Scene TEXT,X REAL,Y REAL,Z REAL",
            (("treasure:one", "One", 4, 5, 6),),
        ),
    ],
)
def test_direct_native_relation_primary_keys_are_required(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
    table: str,
    ddl: str,
    rows: tuple[tuple[object, ...], ...],
) -> None:
    connection, raw, builder = raw_persisted
    raw.execute(f"CREATE TABLE {table} ({ddl})")
    raw.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})", rows)
    if table == "AuthoredSims":
        _insert(raw, "Characters", StableKey="character:seed", DestroyOnDeath=0, DoNotLeaveCorpse=0, IsSimPlayer=1)
    builder.attach_direct_native_inputs(raw)
    audit = validate_item_provenance(connection, builder, raw=raw, require_all_native_tables=False)
    relation = "raw." + table
    assert audit["direct_native_counts"][relation] == len(rows)
    assert table not in audit["unsupported_native_tables"]
    _drop_evidence(builder, relation)
    for identity in tuple(builder.input_exclusions):
        if identity[0] == relation:
            del builder.input_exclusions[identity]
    with pytest.raises(ValueError, match=relation):
        validate_item_provenance(connection, builder, raw=raw, require_all_native_tables=False)


def _seed_claim_context(native_inputs: sqlite3.Connection, spawn: str) -> None:
    _insert(native_inputs, "quests", stable_key="quest:claim", display_name="Claim", image_name="")
    _insert(
        native_inputs,
        "encounter_placements",
        encounter_key="encounter:fixture-claim",
        root_spawn_stable_key=spawn,
        member_spawn_stable_key=spawn,
        role="root",
        context_kind="account_claim",
        post_completion_role="player_home",
    )
    for scope, state in (("account", "account_state:reliquary_claimed"), ("character", "quest:claim")):
        _insert(
            native_inputs,
            "encounter_conditions",
            encounter_key="encounter:fixture-claim",
            state_scope=scope,
            state_key=state,
            required_value="false",
        )
    for event, scope, state in (
        ("host_death", "account", "account_state:reliquary_claimed"),
        ("host_death", "character", "quest:claim"),
        ("scene_awake_quest_completed", "account", "account_state:reliquary_claimed"),
        ("scene_awake_account_claimed", "character", "quest:claim"),
    ):
        _insert(
            native_inputs,
            "encounter_completions",
            encounter_key="encounter:fixture-claim",
            event_kind=event,
            state_scope=scope,
            state_key=state,
            result_value="true",
        )
    for event, scope, state in (
        ("scene_awake_quest_completed", "character", "quest:claim"),
        ("scene_awake_account_claimed", "account", "account_state:reliquary_claimed"),
    ):
        _insert(
            native_inputs,
            "encounter_event_conditions",
            encounter_key="encounter:fixture-claim",
            event_kind=event,
            state_scope=scope,
            state_key=state,
            required_value="true",
        )
    for fact in (
        "guide.gates.reliquary_sources",
        "guide.gates.reliquary_wards",
        "guide.gates.reliquary_claim_awake",
        "guide.gates.reliquary_claim_saved",
        "guide.gates.reliquary_claim_loaded",
    ):
        _insert(native_inputs, "code_facts", fact_id=fact, key="ok", value="true")


@pytest.fixture
def claiming_encounter(
    native_inputs: sqlite3.Connection,
) -> tuple[sqlite3.Connection, ProvenanceBuilder]:
    _seed_claim_context(native_inputs, "spawn:a")
    _insert(
        native_inputs,
        "character_vendor_items",
        character_stable_key="character:b",
        item_slot=6,
        item_stable_key="item:reward",
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    return native_inputs, builder


def test_encounter_state_is_local_to_the_actual_member_placement(
    claiming_encounter: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, builder = claiming_encounter
    audit = validate_item_provenance(connection, builder, require_all_native_tables=False)
    assert {
        relation: audit["input_counts"][relation]
        for relation in (
            "encounter_placements",
            "encounter_conditions",
            "encounter_completions",
            "encounter_event_conditions",
        )
    } == {
        "encounter_placements": 1,
        "encounter_conditions": 2,
        "encounter_completions": 4,
        "encounter_event_conditions": 2,
    }
    vendors = [fact for fact in builder.acquisitions if fact.kind == "vendor" and fact.item_stable_key == "item:reward"]
    assert len(vendors) == 2
    assert sum(len(fact.locations) for fact in vendors) == 3
    for fact in vendors:
        assert fact.player_access_state == "verified_player"
        assert not any(atom.predicate == "account_state" for atom in fact.conditions)
        for location in fact.locations:
            states = [atom for atom in location.conditions if atom.predicate == "account_state"]
            legacy = [
                atom
                for atom in location.conditions
                if atom.predicate == "quest_not_done" and atom.reference_stable_key == "quest:claim"
            ]
            if fact.source_copy_stable_key == "character:a" and location.coordinate_stable_key == "spawn:a":
                assert len(states) == len(legacy) == 1
                assert (
                    states[0].actor,
                    states[0].value,
                    states[0].reference_stable_key,
                    states[0].scope,
                    states[0].phase,
                ) == (
                    "account",
                    "false",
                    "account_state:reliquary_claimed",
                    location.location_key,
                    "availability",
                )
                assert legacy[0].scope == location.location_key
            else:
                assert states == legacy == []


@pytest.mark.parametrize(
    "relation",
    [
        "encounter_placements",
        "encounter_conditions",
        "encounter_completions",
        "encounter_event_conditions",
    ],
)
def test_all_shared_encounter_configuration_origins_remain_required(
    claiming_encounter: tuple[sqlite3.Connection, ProvenanceBuilder],
    relation: str,
) -> None:
    connection, builder = claiming_encounter
    validate_item_provenance(connection, builder, require_all_native_tables=False)
    assert _evidence(builder, relation)
    _drop_evidence(builder, relation)
    with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
        validate_item_provenance(connection, builder, require_all_native_tables=False)


def test_special_template_material_slots_preserve_unexecuted_and_normal_quality_conditions(
    native_inputs: sqlite3.Connection,
) -> None:
    native_inputs.execute("UPDATE items SET template=1 WHERE stable_key='item:removal'")
    _insert(
        native_inputs,
        "crafting_rewards",
        recipe_item_stable_key="item:removal",
        reward_slot=1,
        reward_item_stable_key="item:other",
        reward_quantity=1,
    )
    _insert(
        native_inputs,
        "crafting_recipes",
        recipe_item_stable_key="item:removal",
        material_slot=1,
        material_item_stable_key="item:furniture",
        material_quantity=1,
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    rewards = [
        fact for fact in builder.acquisitions if fact.kind == "crafting" and fact.source_stable_key == "item:removal"
    ]
    assert len(rewards) == 1 and rewards[0].player_access_state == "non_acquirable"
    materials = [
        use for use in builder.uses if use.kind == "crafting_material" and use.target_stable_key == "item:removal"
    ]
    assert len(materials) == 1
    assert {atom.gate_key for atom in materials[0].conditions} == {"unexecuted_material_slot", "material_quality"}
    assert not any(use.mechanic == "forge_fuel" and use.target_stable_key == "item:removal" for use in builder.uses)


def test_gear_recipe_quantities_are_physical_units_not_encoded_quality(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE crafting_rewards SET reward_item_stable_key='item:furniture'")
    native_inputs.execute(
        "UPDATE crafting_recipes SET material_item_stable_key='item:furniture', "
        "material_quantity=1 WHERE material_slot=1"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    rewards = [fact for fact in builder.acquisitions if fact.kind == "crafting"]
    assert len(rewards) == 2
    for fact in rewards:
        assert (fact.quantity_min, fact.quantity_max) == (1, 1)
        assert [(atom.value, atom.phase) for atom in fact.conditions if atom.gate_key == "fuel_quality"] == [
            ("selected_fuel_level_plus_one", "operation_outcome"),
        ]
    materials = [use for use in builder.uses if use.kind == "crafting_material" and use.material_slot == 1]
    assert len(materials) == 1
    assert (materials[0].quantity_min, materials[0].quantity_max) == (1, 1)
    assert [(atom.value, atom.phase) for atom in materials[0].conditions if atom.gate_key == "material_quality"] == [
        ("normal", "operation_input"),
    ]


def test_offered_equipment_carries_the_same_native_result_and_coefficients_as_stones(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    gear = [use for use in builder.uses if use.kind == "quality_offering" and use.material_slot == 2]
    assert len(gear) == 1
    conditions = gear[0].conditions
    assert {
        atom.value: atom.minimum
        for atom in conditions
        if atom.phase == "mechanic_parameter"
        and atom.gate_key
        in (
            "chance_per_pair",
            "chance_per_improvement",
            "enhance_chance",
        )
    } == {"chance_per_stone_pair": 3, "chance_per_improvement_level": 2, "enhance_chance_per_stone_pair": 1}
    assert {atom.gate_key for atom in conditions if atom.phase == "operation_outcome"} >= {
        "result_quality",
        "enhanced_quality",
    }


def test_encounter_without_located_item_action_is_explicitly_accounted(native_inputs: sqlite3.Connection) -> None:
    _seed_claim_context(native_inputs, "spawn:b")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder, require_all_native_tables=False)
    excluded = [row for row in audit["exclusions"] if row["relation"].startswith("encounter_")]
    assert len(excluded) == 9
    assert {row["reason"] for row in excluded} == {"no_located_item_action"}
    assert not any(
        entry.input_relation.startswith("encounter_") for entries in builder.fact_evidence.values() for entry in entries
    )


def test_orphan_encounter_state_requires_a_placement_during_selection(
    claiming_encounter: tuple[sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, _ = claiming_encounter
    _insert(
        connection,
        "encounter_conditions",
        encounter_key="encounter:orphan",
        state_scope="account",
        state_key="account_state:reliquary_claimed",
        required_value="false",
    )
    builder = ProvenanceBuilder(connection)
    builder.select()
    with pytest.raises(ValueError, match="no placement"):
        builder.account_support_inputs()


@pytest.mark.parametrize("key", ["quantity", "rolls"])
def test_pool_draw_count_proofs_reject_unsupported_operations(native_inputs: sqlite3.Connection, key: str) -> None:
    native_inputs.execute("UPDATE code_facts SET value='2' WHERE fact_id='item.fossil_pool_grant' AND key=?", (key,))
    with pytest.raises(ValueError, match="single-roll, single-item"):
        ProvenanceBuilder(native_inputs).select()


def test_disabled_common_world_row_cannot_execute_initializer_pools(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute(
        "UPDATE loot_drops SET source_component_is_enabled=0 WHERE character_stable_key='character:a' "
        "AND item_stable_key='item:common'"
    )
    with pytest.raises(ValueError, match="disabled loot component"):
        ProvenanceBuilder(native_inputs).select()


@pytest.fixture
def disabled_preseed(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder]:
    connection, raw, _exclusions = raw_persisted
    connection.execute("UPDATE items SET is_unique=1 WHERE stable_key='item:reward'")
    _insert(connection, "code_facts", fact_id="loot.owned_unique_replacement", key="ok", value="true")
    connection.execute(
        "DELETE FROM loot_drops WHERE character_stable_key='character:a' AND item_stable_key='item:common'"
    )
    raw.execute("DELETE FROM LootDrops WHERE LootTableStableKey='loot-table:a' AND ItemStableKey='item:common'")
    connection.execute(
        "UPDATE loot_drops SET source_component_is_enabled=0,drop_probability=100,expected_per_kill=1,"
        "drop_count_distribution='[0,1]' WHERE character_stable_key='character:a' AND item_stable_key='item:reward'"
    )
    raw.execute(
        "UPDATE LootDrops SET DropProbability=100,ExpectedPerKill=1,DropCountDistribution='[0,1]' "
        "WHERE LootTableStableKey='loot-table:a' AND ItemStableKey='item:reward'"
    )
    raw.execute("UPDATE LootTableSources SET ComponentIsEnabled=0 WHERE StableKey='loot-table:a'")
    builder = ProvenanceBuilder(connection)
    builder.select()
    builder.raw_loot_evidence(raw, frozenset({"character:reviewed"}))
    builder.attach_native_inputs(raw)
    builder.account_support_inputs()
    builder.attach_direct_native_inputs(raw)
    return connection, raw, builder


def test_disabled_actual_preseed_retains_native_copies_without_claiming_player_access_or_initialization(
    disabled_preseed: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> None:
    _, _, builder = disabled_preseed
    facts = [
        fact
        for fact in builder.acquisitions
        if fact.kind == "character_drop"
        and fact.source_copy_stable_key == "character:a"
        and fact.item_stable_key == "item:reward"
    ]
    assert len(facts) == 1
    fact = facts[0]
    assert (
        fact.player_access_state,
        fact.mechanic,
        fact.probability_min,
        json.loads(fact.count_distribution or "null"),
        fact.quantity_min,
        fact.quantity_max,
        fact.guarantee_scope,
        fact.guaranteed_roll_count,
    ) == (
        "unconfirmed_player",
        "preseeded_before_start",
        100,
        [0, 1],
        1,
        1,
        None,
        None,
    )
    assert not any(
        atom.gate_key in ("not_owned", "probability_context") or atom.predicate == "never" for atom in fact.conditions
    )
    assert ProvenanceEvidence("raw.LootTableSources", '["loot-table:a"]') in _evidence(
        builder,
        "raw.LootTableSources",
        fact.acquisition_key,
    )


@pytest.mark.parametrize(
    ("distribution", "chance", "expected", "low", "high", "kind", "access"),
    [
        ("[0,0,1]", 100, 2, 2, 2, "exact", "verified_player"),
        ("[0,0,0.25,0.75]", 100, 2.75, 2, 3, "bounded", "verified_player"),
        ("[1,0,0]", 0, 0, None, None, "unknown", "non_acquirable"),
        (None, None, None, None, None, "unknown", "verified_player"),
    ],
)
def test_character_copy_quantity_uses_only_positive_native_count_support(
    *,
    native_inputs: sqlite3.Connection,
    distribution: str | None,
    chance: float | None,
    expected: float | None,
    low: int | None,
    high: int | None,
    kind: str,
    access: str,
) -> None:
    native_inputs.execute(
        "UPDATE loot_drops SET drop_count_distribution=?,drop_probability=?,expected_per_kill=? "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:reward'",
        (distribution, chance, expected),
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [
        fact
        for fact in builder.acquisitions
        if fact.kind == "character_drop" and fact.source_copy_stable_key == "character:a"
    ]
    assert len(facts) == 1
    fact = facts[0]
    assert (fact.quantity_min, fact.quantity_max, fact.quantity_kind, fact.player_access_state) == (
        low,
        high,
        kind,
        access,
    )


@pytest.mark.parametrize("unknown_contributor", [False, True])
def test_global_common_quantity_bounds_require_every_contributing_count_distribution(
    native_inputs: sqlite3.Connection,
    unknown_contributor: bool,
) -> None:
    native_inputs.execute(
        "UPDATE loot_drops SET drop_count_distribution='[0.5,0,0.5]',drop_probability=50,expected_per_kill=1 "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:common'"
    )
    native_inputs.execute(
        "UPDATE loot_drops SET drop_count_distribution=?,drop_probability=25,expected_per_kill=0.25 "
        "WHERE character_stable_key='character:b' AND item_stable_key='item:common'",
        (None if unknown_contributor else "[0.75,0.25]",),
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == "common_world_item"]
    assert len(facts) == 1
    fact = facts[0]
    assert (
        fact.quantity_min,
        fact.quantity_max,
        fact.quantity_kind,
        fact.count_distribution,
        fact.expected_quantity,
    ) == ((None, None, "unknown", None, None) if unknown_contributor else (1, 2, "bounded", None, None))


@pytest.mark.parametrize("enabled", [0, 1])
@pytest.mark.parametrize(
    ("immune", "damageable", "chest", "available"),
    [(0, 1, 0, True), (1, 1, 0, True), (1, 0, 0, False), (1, 0, 1, True)],
    ids=["mortal", "native_release", "permanently_immune", "chest_break"],
)
def test_kill_loot_access_is_separate_from_native_inventory_and_initializer(
    *,
    native_inputs: sqlite3.Connection,
    enabled: int,
    immune: int,
    damageable: int,
    chest: int,
    available: bool,
) -> None:
    native_inputs.execute(
        "UPDATE characters SET invulnerable=?,can_be_damaged=?,treasure_chest=? WHERE stable_key='character:a'",
        (immune, damageable, chest),
    )
    if chest:
        for fact in ("treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt"):
            _insert(native_inputs, "code_facts", fact_id=fact, key="ok", value="true")
    native_inputs.execute(
        "UPDATE loot_drops SET source_component_is_enabled=? "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:reward'",
        (enabled,),
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    fact = next(
        fact
        for fact in builder.acquisitions
        if fact.kind == "character_drop" and fact.source_copy_stable_key == "character:a"
    )
    access = "non_acquirable" if not available else "verified_player" if enabled else "unconfirmed_player"
    assert fact.player_access_state == access
    assert (fact.probability_min, fact.probability_max, fact.expected_quantity) == (25, 25, 0.25)
    assert fact.count_distribution is not None
    assert json.loads(fact.count_distribution) == [0.75, 0.25]
    assert (fact.quantity_min, fact.quantity_max) == (1, 1)
    assert {
        json.loads(evidence.input_primary_key)[0]
        for evidence in builder.fact_evidence[fact.acquisition_key]
        if evidence.input_relation == "code_facts" and json.loads(evidence.input_primary_key)[0].startswith("treasure.")
    } == ({"treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt"} if chest else set())
    assert fact.mechanic == ("loot_roll" if enabled else "preseeded_before_start")
    assert any(atom.phase == "source_initialization" for atom in fact.conditions) == bool(enabled)
    assert not any(atom.predicate == "never" for atom in fact.conditions)
    assert any(
        evidence.input_relation == "loot_drops"
        and json.loads(evidence.input_primary_key) == ["character:a", "item:reward"]
        for evidence in builder.fact_evidence[fact.acquisition_key]
    )


@pytest.mark.parametrize(("a_damageable", "b_damageable"), [(1, 1), (1, 0), (0, 1), (0, 0)])
def test_common_world_bounds_and_native_coverage_use_only_loot_capable_contributors(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
    a_damageable: int,
    b_damageable: int,
) -> None:
    connection, raw, _exclusions = raw_persisted
    for copy, damageable in (("a", a_damageable), ("b", b_damageable)):
        connection.execute(
            "UPDATE characters SET invulnerable=1,can_be_damaged=? WHERE stable_key=?",
            (damageable, "character:" + copy),
        )
    connection.execute(
        "UPDATE loot_drops SET drop_probability=100,expected_per_kill=3,drop_count_distribution='[0,0,0,1]' "
        "WHERE character_stable_key='character:b' AND item_stable_key='item:common'"
    )
    raw.execute(
        "UPDATE LootDrops SET DropProbability=100,ExpectedPerKill=3,DropCountDistribution='[0,0,0,1]' "
        "WHERE CharacterStableKey='character:b' AND ItemStableKey='item:common'"
    )
    for table in (
        "item_acquisition_conditions",
        "item_use_conditions",
        "item_source_locations",
        "item_mechanic_conditions",
        "item_acquisition_contributors",
        "item_uses",
        "item_acquisitions",
        "item_dispositions",
    ):
        connection.execute(f"DELETE FROM {table}")
    builder = ProvenanceBuilder(connection)
    builder.select()
    builder.raw_loot_evidence(raw, frozenset({"character:reviewed"}))
    builder.attach_native_inputs(raw)
    builder.account_support_inputs()
    builder.attach_direct_native_inputs(raw)
    builder.persist()
    connection.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(
        connection,
        builder,
        raw=raw,
        require_all_native_tables=False,
    )
    assert audit["input_counts"]["loot_drops"] == 4
    facts = [fact for fact in builder.acquisitions if fact.kind == "common_world_item"]
    eligible = {copy for copy, capable in (("a", a_damageable), ("b", b_damageable)) if capable}
    assert len(facts) == int(bool(eligible))
    if facts:
        fact = facts[0]
        chances = [10 if copy == "a" else 100 for copy in eligible]
        quantities = [1 if copy == "a" else 3 for copy in eligible]
        assert (fact.probability_min, fact.probability_max) == (min(chances), max(chances))
        assert (fact.quantity_min, fact.quantity_max) == (min(quantities), max(quantities))
        assert fact.player_access_state == "verified_player"
        assert {
            json.loads(evidence.input_primary_key)[0]
            for evidence in builder.fact_evidence[fact.acquisition_key]
            if evidence.input_relation == "loot_drops"
        } == {"character:" + copy for copy in eligible}
    for copy in {"a", "b"} - eligible:
        assert builder.input_exclusions["loot_drops", f'["character:{copy}","item:common"]'] == (
            "loot_host_undamageable"
        )
        assert builder.input_exclusions["raw.LootDrops", f'["loot-table:{copy}","item:common"]'] == (
            "loot_host_undamageable"
        )
    if not b_damageable:
        assert builder.input_exclusions["raw.LootTableSources", '["loot-table:b"]'] == "loot_host_undamageable"
        excluded_slot_reasons = [
            reason
            for (relation, primary), reason in builder.input_exclusions.items()
            if relation == "raw.LootTablePoolSlots" and json.loads(primary)[0] == "loot-table:b"
        ]
        assert excluded_slot_reasons and set(excluded_slot_reasons) == {"loot_host_undamageable"}
        del builder.input_exclusions["loot_drops", '["character:b","item:common"]']
        with pytest.raises(ValueError, match="Unaccounted item provenance inputs"):
            validate_item_provenance(
                connection,
                builder,
                raw=raw,
                require_all_native_tables=False,
            )


@pytest.mark.parametrize("missing", ["treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt"])
def test_immune_chest_loot_requires_pinned_native_break_and_interaction_evidence(
    native_inputs: sqlite3.Connection,
    missing: str,
) -> None:
    native_inputs.execute(
        "UPDATE characters SET invulnerable=1,can_be_damaged=0,treasure_chest=1 WHERE stable_key='character:a'"
    )
    for fact in {"treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt"} - {missing}:
        _insert(native_inputs, "code_facts", fact_id=fact, key="ok", value="true")
    with pytest.raises(ValueError, match=missing):
        ProvenanceBuilder(native_inputs).loot()


def test_immune_common_world_unknown_rate_cannot_poison_eligible_bounds(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE characters SET invulnerable=1,can_be_damaged=0 WHERE stable_key='character:b'")
    native_inputs.execute(
        "UPDATE loot_drops SET drop_probability=NULL,expected_per_kill=NULL,drop_count_distribution=NULL "
        "WHERE character_stable_key='character:b' AND item_stable_key='item:common'"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == "common_world_item"]
    assert len(facts) == 1
    fact = facts[0]
    assert (fact.probability_kind, fact.probability_min, fact.probability_max) == ("exact", 10, 10)
    assert (fact.quantity_kind, fact.quantity_min, fact.quantity_max) == ("exact", 1, 1)


def test_gathering_and_global_fishing_replacement_select_distinct_stages(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    mining = next(fact for fact in builder.acquisitions if fact.kind == "mining")
    assert (
        mining.source_stable_key,
        mining.item_stable_key,
        mining.probability_min,
        mining.probability_max,
        mining.probability_basis,
    ) == ("node:one", "item:reward", 15, 15, "per_node")
    assert [(place.relation, place.x, place.y, place.z) for place in mining.locations] == [("fixed", 3, 4, 5)]
    bonus = next(fact for fact in builder.acquisitions if fact.kind == "fishing_bonus")
    assert (
        bonus.item_stable_key,
        bonus.source_stable_key,
        bonus.mechanic,
        bonus.probability_min,
        bonus.probability_max,
        bonus.probability_stage,
    ) == (
        "item:other",
        None,
        "fishing_global_replacement",
        3,
        3,
        "native_pool",
    )
    assert bonus.conditions == bonus.locations == ()


def test_auction_routes_keep_actor_bounds_and_shared_broker_places(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    facts = [fact for fact in builder.acquisitions if fact.kind == "auction_house"]
    assert {fact.variant_key for fact in facts} == {"direct", "replacement"}
    assert len({fact.acquisition_key for fact in facts}) == 2
    for fact in facts:
        assert fact.item_stable_key == "item:reward"
        assert fact.probability_basis == "per_listing_opportunity"
        assert {(atom.actor, atom.minimum, atom.maximum) for atom in fact.conditions} == {
            ("sim", 10, 20),
            ("player", 15, 25),
        }
        assert fact.locations
        assert {place.relation for place in fact.locations} == {"interaction"}
        assert {place.source_copy_stable_key for place in fact.locations} == {"character:a"}
    starting = [fact for fact in builder.acquisitions if fact.kind == "starting_class"]
    assert len(starting) == 2
    assert {fact.item_stable_key for fact in starting} == {"item:reward"}


def test_internal_equipment_retains_actor_class_and_authored_seed_phase(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    generated = [fact for fact in builder.acquisitions if fact.mechanic == "simulated_equipment_generation"]
    assert len(generated) == 2
    for fact in generated:
        assert (fact.item_stable_key, fact.player_access_state) == ("item:other", "internal_only")
        assert [
            (atom.reference_stable_key, atom.actor) for atom in fact.conditions if atom.gate_key == "actor_class"
        ] == [("class:paladin", "sim")]
    seed = next(fact for fact in builder.acquisitions if fact.mechanic == "authored_sim_seed")
    assert (seed.item_stable_key, seed.variant_key, seed.player_access_state) == ("item:reward", "0", "internal_only")
    assert [
        (atom.minimum, atom.maximum, atom.actor, atom.phase)
        for atom in seed.conditions
        if atom.gate_key == "seed_level"
    ] == [(10, 10, "sim", "source_initialization")]


def test_crafting_reward_slots_and_material_quantities_remain_independent(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    rewards = [
        fact for fact in builder.acquisitions if fact.kind == "crafting" and fact.source_stable_key == "item:recipe"
    ]
    assert len(rewards) == 2
    assert len({fact.acquisition_key for fact in rewards}) == 2
    assert {(fact.item_stable_key, fact.quantity_min, fact.quantity_max) for fact in rewards} == {
        ("item:reward", 1, 1),
    }
    materials = [
        use for use in builder.uses if use.kind == "crafting_material" and use.target_stable_key == "item:recipe"
    ]
    assert {(use.material_slot, use.item_stable_key, use.quantity_min, use.quantity_max) for use in materials} == {
        (1, "item:material", 4, 4),
        (2, "item:material", 5, 5),
    }


def test_item_conversion_keeps_zone_gate_and_links_consumed_input_to_outcome(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    fact = next(fact for fact in builder.acquisitions if fact.kind == "item_conversion")
    use = next(use for use in builder.uses if use.kind == "item_conversion")
    assert (fact.item_stable_key, fact.source_stable_key, fact.mechanic) == ("item:reward", "item:input", "chessboard")
    assert [(atom.predicate, atom.reference_stable_key) for atom in fact.conditions] == [("zone_use", "zone:one")]
    assert (use.item_stable_key, use.target_stable_key, use.outcome_key) == (
        "item:input",
        "item:reward",
        fact.acquisition_key,
    )
    restriction = next(use for use in builder.uses if use.kind == "zone_restriction")
    assert restriction.item_stable_key == "item:input"


@pytest.mark.parametrize(
    ("relation", "mutation", "kind", "expected"),
    [
        (
            "loot_drops",
            "UPDATE loot_drops SET drop_probability=50 WHERE item_stable_key='item:reward'",
            "character_drop",
            50,
        ),
        ("mining_node_items", "UPDATE mining_node_items SET drop_chance=60", "mining", 60),
        ("water_fishables", "UPDATE water_fishables SET drop_chance=20", "fishing", 20),
        ("fishing_bonus_catches", "UPDATE fishing_bonus_catches SET chance_per_catch=4", "fishing_bonus", 4),
    ],
)
def test_input_probability_changes_reach_selected_facts(
    native_inputs: sqlite3.Connection,
    relation: str,
    mutation: str,
    kind: str,
    expected: int,
) -> None:
    assert native_inputs.execute(f"SELECT count(*) FROM {relation}").fetchone()[0] > 0
    native_inputs.execute(mutation)
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    facts = [fact for fact in builder.acquisitions if fact.kind == kind]
    assert facts
    assert {(fact.probability_min, fact.probability_max) for fact in facts} == {(expected, expected)}


def test_flame_well_stone_counts_and_equipment_quality_keep_operation_phases(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    stones = [use for use in builder.uses if use.kind == "quality_offering" and use.material_slot in (0, 1)]
    assert {(use.material_slot, use.quantity_min, use.quantity_max) for use in stones} == {
        (0, 1, None),
        (1, 1, None),
    }
    for use in stones:
        assert [
            (atom.value, atom.minimum, atom.phase) for atom in use.conditions if atom.gate_key == "stone_counts"
        ] == [("equal_positive_stone_counts", 1, "operation_input")]
    gear = next(use for use in builder.uses if use.kind == "quality_offering" and use.material_slot == 2)
    assert (gear.item_stable_key, gear.quantity_min, gear.quantity_max) == ("item:furniture", 1, 1)
    assert {
        (atom.group_index, atom.minimum, atom.maximum, atom.phase)
        for atom in gear.conditions
        if atom.gate_key == "eligible_quality"
    } == {
        (0, 1, 1, "operation_input"),
        (1, 11, None, "operation_input"),
    }
    assert {
        (atom.gate_key, atom.value, atom.phase)
        for atom in gear.conditions
        if atom.gate_key in ("result_quality", "enhanced_quality", "failure")
    } == {
        ("result_quality", "Blessed", "operation_outcome"),
        ("enhanced_quality", "Divine", "operation_outcome"),
        ("failure", "return_original_equipment_quality", "operation_outcome"),
    }


def test_smithing_fuel_parameters_and_quality_alternatives_are_not_defaults(
    selected: ProvenanceBuilder,
) -> None:
    builder = selected
    fuel = [
        use
        for use in builder.uses
        if use.mechanic
        in (
            "forge_fuel",
            "blessing_removal_fuel",
            "combining_fuel",
        )
    ]
    assert {use.mechanic for use in fuel} == {"forge_fuel", "blessing_removal_fuel", "combining_fuel"}
    for use in fuel:
        assert (use.item_stable_key, use.quantity_min, use.quantity_max) == ("item:material", 1, 1)
        assert [
            (atom.minimum, atom.maximum, atom.phase) for atom in use.conditions if atom.gate_key == "fuel_level"
        ] == [(3, 3, "mechanic_parameter")]
    combining = next(use for use in builder.uses if use.mechanic == "combine_matching")
    assert (combining.item_stable_key, combining.quantity_min, combining.quantity_max) == ("item:furniture", 2, 2)
    assert {
        (atom.group_index, atom.minimum, atom.maximum, atom.phase)
        for atom in combining.conditions
        if atom.gate_key == "input_quality"
    } == {
        (0, 1, 1, "operation_input"),
        (1, 11, 14, "operation_input"),
    }
    assert [
        (atom.value, atom.maximum, atom.phase) for atom in combining.conditions if atom.gate_key == "improvement"
    ] == [("normal_to_11_else_plus_1", 15, "operation_outcome")]
    upgrade = next(use for use in builder.uses if use.mechanic == "quality_upgrade")
    assert [(atom.gate_key, atom.value, atom.phase) for atom in upgrade.conditions] == [
        ("input_quality", "blessed", "operation_input"),
        ("output_quality", "divine", "operation_outcome"),
    ]


def test_populated_unknown_native_item_input_table_is_rejected(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, ProvenanceBuilder],
) -> None:
    connection, raw, builder = raw_persisted
    raw.execute("CREATE TABLE FutureItemGrants (StableKey TEXT PRIMARY KEY, ItemStableKey TEXT)")
    validate_item_provenance(connection, builder, raw=raw, require_all_native_tables=False)
    _insert(raw, "FutureItemGrants", StableKey="grant:future", ItemStableKey="item:reward")
    with pytest.raises(ValueError, match="FutureItemGrants"):
        validate_item_provenance(connection, builder, raw=raw, require_all_native_tables=False)
