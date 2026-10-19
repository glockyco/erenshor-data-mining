"""Native identities and typed outcomes remain required after canonical persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.item_provenance_coverage import validate_item_provenance
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import ProvenanceCondition, conditions_satisfiable


def _insert(connection: sqlite3.Connection, table: str, **values: object) -> None:
    columns = ",".join(f'"{column}"' for column in values)
    connection.execute(
        f'INSERT INTO "{table}" ({columns}) VALUES ({",".join("?" for _ in values)})',
        tuple(values.values()),
    )


def _delete_kind(connection: sqlite3.Connection, family: str, kind: str) -> None:
    table, key = {
        "acquisition": ("item_acquisitions", "acquisition_key"),
        "use": ("item_uses", "use_key"),
    }[family]
    owners = f"SELECT {key} FROM {table} WHERE kind=?"
    for child in (f"item_{family}_conditions", f"item_{family}_locations", "item_provenance_evidence"):
        connection.execute(f"DELETE FROM {child} WHERE owner_key IN ({owners})", (kind,))
    connection.execute(f"DELETE FROM {table} WHERE kind=?", (kind,))


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
def persisted(native_inputs: sqlite3.Connection) -> tuple[sqlite3.Connection, dict[tuple[str, str], str]]:
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    return native_inputs, dict(builder.input_exclusions)


def test_all_native_families_have_identity_and_dimension_coverage(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    audit = validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert audit["input_counts"] == {
        "auction_house_items": 2,
        "character_dialogs": 2,
        "character_quest_manager_quests": 4,
        "class_starting_items": 2,
        "crafting_recipes": 2,
        "crafting_rewards": 2,
        "fishing_bonus_catches": 1,
        "code_facts": 37,
        "items": 3,
        "item_classes": 1,
        "authored_sims": 1,
        "authored_sim_references": 1,
        "authored_sim_equipment": 2,
        "item_bags": 1,
        "item_conversions": 1,
        "item_drops": 1,
        "item_zone_restrictions": 1,
        "loot_drops": 4,
        "mining_node_items": 1,
        "quality_offerings": 1,
        "quest_required_items": 2,
        "quest_variants": 2,
        "special_world_drops": 1,
        "spell_created_items": 1,
        "ui_item_access_targets": 1,
        "ui_item_sources": 3,
        "vendor_offers": 2,
        "water_fishables": 2,
    }
    assert audit["contract_counts"] == {"acquisitions": 27, "uses": 22, "dispositions": 8}
    assert len(audit["exclusions"]) == 7


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("delete_fishing_kind", "acquisition identities"),
        ("DELETE FROM item_provenance_evidence WHERE input_relation='mining_node_items'", "evidence"),
        ("UPDATE item_acquisitions SET quantity_min=NULL WHERE kind='crafting'", "quantity_min"),
        ("DELETE FROM item_acquisition_conditions WHERE gate_key='time'", "conditions"),
        ("UPDATE item_acquisitions SET probability_min=NULL WHERE kind='fishing'", "probability_min"),
        (
            "DELETE FROM item_acquisition_locations WHERE owner_key IN "
            "(SELECT acquisition_key FROM item_acquisitions WHERE kind='mining')",
            "locations",
        ),
        ("DELETE FROM item_dispositions WHERE item_stable_key='item:reward'", "dispositions"),
        (
            "UPDATE item_acquisitions SET probability_stage='final_acquisition' WHERE kind='fishing_bonus'",
            "probability_stage",
        ),
        ("UPDATE item_acquisitions SET source_copy_stable_key=NULL WHERE kind='vendor'", "source_copy_stable_key"),
        ("UPDATE item_acquisitions SET variant_key=NULL WHERE kind='fishing'", "variant_key"),
        ("UPDATE item_uses SET material_slot=NULL WHERE kind='crafting_material'", "material_slot"),
        ("UPDATE item_uses SET quantity_max=NULL WHERE kind='quest_requirement'", "quantity_max"),
        ("UPDATE item_uses SET outcome_key=NULL WHERE kind='item_drop'", "outcome_key"),
        ("UPDATE item_acquisitions SET count_distribution=NULL WHERE kind='character_drop'", "count_distribution"),
        ("UPDATE item_acquisitions SET guarantee_scope=NULL WHERE kind='item_drop'", "guarantee_scope"),
        ("UPDATE item_acquisition_locations SET x=x+1 WHERE relation='fixed'", "locations"),
        ("UPDATE item_acquisition_locations SET entry_zone_line_keys='[]' WHERE relation='spawn'", "locations"),
        ("UPDATE item_acquisition_locations SET conditions='[]' WHERE relation='spawn'", "locations"),
        ("UPDATE item_acquisition_locations SET conditions='[]' WHERE location_key='desk:one'", "locations"),
        ("UPDATE item_acquisition_locations SET player_level_min=NULL WHERE relation='possible_treasure'", "locations"),
        ("UPDATE item_acquisition_locations SET source_copy_stable_key=NULL WHERE relation='interaction'", "locations"),
    ],
)
def test_mutations_cannot_silently_drop_contract_dimensions(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
    message: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    if mutation == "delete_fishing_kind":
        _delete_kind(connection, "acquisition", "fishing")
    else:
        connection.execute(mutation)
    with pytest.raises(ValueError, match=message):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_replacing_an_origin_with_another_origin_keeps_count_but_fails(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    before = connection.execute("SELECT count(*) FROM item_provenance_evidence").fetchone()[0]
    connection.execute(
        "UPDATE item_provenance_evidence SET input_primary_key='[\"wrong-source\"]' "
        "WHERE input_relation='mining_node_items'"
    )
    assert connection.execute("SELECT count(*) FROM item_provenance_evidence").fetchone()[0] == before
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_native_input_added_after_selection_is_not_hidden_by_builder_expectations(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    _insert(connection, "class_starting_items", class_name="Arcanist", sort_order=0, item_stable_key="item:reward")
    with pytest.raises(ValueError, match="acquisition identities"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


@pytest.mark.parametrize("change", ["missing", "wrong_reason", "unknown", "covered"])
def test_exclusions_require_the_exact_native_identity_and_outcome(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    change: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    identity = ("loot_drops", '["character:unused","item:other"]')
    assert exclusions[identity] == "unencountered_copy"
    if change == "missing":
        exclusions.pop(identity)
    elif change == "wrong_reason":
        exclusions[identity] = "unused_access_observation"
    elif change == "unknown":
        exclusions[("loot_drops", '["missing","item:other"]')] = "unencountered_copy"
    else:
        exclusions[("mining_node_items", '["node:one","item:reward"]')] = "unencountered_copy"
    with pytest.raises(ValueError, match="exclusions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_unsupported_extra_fact_kind_fails(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute("UPDATE item_acquisitions SET kind='invented' WHERE kind='mining'")
    with pytest.raises(ValueError, match="kind"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_reviewed_historical_item_disposition_does_not_invent_a_current_item(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
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
    audit = validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert audit["contract_counts"]["dispositions"] == 9
    connection.execute("UPDATE item_dispositions SET evidence=NULL WHERE item_stable_key='item:historical'")
    with pytest.raises(ValueError, match="Unreviewed"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_disposition_page_identity_is_not_just_a_row_count(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute("UPDATE item_dispositions SET current_pages='[]' WHERE item_stable_key='item:reward'")
    with pytest.raises(ValueError, match="current item disposition page"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_day_night_variants_keep_their_own_local_probabilities(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    assert (
        connection.execute("SELECT count(*) FROM water_fishables WHERE item_stable_key='item:reward'").fetchone()[0]
        == 2
    )
    assert connection.execute("SELECT count(*) FROM item_acquisitions WHERE kind='fishing'").fetchone()[0] == 2
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute(
        "UPDATE item_acquisitions SET probability_min=75, probability_max=75 WHERE variant_key='DayFishable'"
    )
    with pytest.raises(ValueError, match="probability_min"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_locations WHERE relation='unlocated' "
            "AND source_copy_stable_key='character:b'"
        ).fetchone()[0]
        == 1
    )


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
def test_every_populated_acquisition_family_is_a_positive_control(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    kind: str,
) -> None:
    connection, exclusions = persisted
    assert connection.execute("SELECT count(*) FROM item_acquisitions WHERE kind=?", (kind,)).fetchone()[0] > 0
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    _delete_kind(connection, "acquisition", kind)
    with pytest.raises(ValueError, match="acquisition identities"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
def test_every_populated_use_family_is_a_positive_control(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    kind: str,
) -> None:
    connection, exclusions = persisted
    assert connection.execute("SELECT count(*) FROM item_uses WHERE kind=?", (kind,)).fetchone()[0] > 0
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    _delete_kind(connection, "use", kind)
    with pytest.raises(ValueError, match="use identities"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_same_count_source_copy_swap_fails(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert connection.execute("SELECT count(*) FROM item_acquisitions WHERE kind='quest_reward'").fetchone()[0] == 2
    connection.execute("UPDATE item_acquisitions SET source_copy_stable_key='character:b' WHERE kind='quest_reward'")
    with pytest.raises(ValueError, match="source_copy_stable_key"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_quest_turnin_duplicate_slots_are_aggregated_only_in_the_gate(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions WHERE gate_key='turnin_items' AND minimum=5"
        ).fetchone()[0]
        == 2
    )
    assert connection.execute("SELECT count(*) FROM item_uses WHERE kind='quest_requirement'").fetchone()[0] == 2
    connection.execute("UPDATE item_acquisition_conditions SET minimum=2 WHERE gate_key='turnin_items'")
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_use_condition_and_location_coverage_is_independent(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    counts = dict(
        connection.execute(
            "SELECT u.kind, count(*) FROM item_use_conditions c JOIN item_uses u ON u.use_key=c.owner_key "
            "WHERE c.predicate='formula_operand' GROUP BY u.kind"
        ).fetchall()
    )
    assert counts == {"quality_offering": 21, "smithing": 5}
    connection.execute("DELETE FROM item_use_conditions WHERE predicate='formula_operand'")
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    assert {(row.input_relation, row.input_primary_key) for row in box.evidence} == {
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


def test_ui_location_preserves_repeated_defeat_quantity_and_coverage(native_inputs: sqlite3.Connection) -> None:
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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    owner, encoded = native_inputs.execute(
        "SELECT owner_key, conditions FROM item_acquisition_locations WHERE location_key='desk:one'"
    ).fetchone()
    conditions = json.loads(encoded)
    defeats = [condition for condition in conditions if condition["predicate"] == "encounter_won"]
    assert len(defeats) == 1
    assert defeats[0]["reference_stable_key"] == "character:a"
    assert defeats[0]["scope"] == "desk:one"
    assert defeats[0]["minimum"] == 9
    defeats[0]["minimum"] = 1
    native_inputs.execute(
        "UPDATE item_acquisition_locations SET conditions=? WHERE owner_key=? AND location_key='desk:one'",
        (json.dumps(conditions), owner),
    )
    with pytest.raises(ValueError, match="locations"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert audit["input_counts"]["item_access_observations"] == 1
    actual = native_inputs.execute(
        "SELECT player_access_state FROM item_acquisitions WHERE source_stable_key='ui:cosmetic'"
    ).fetchone()[0]
    assert actual == ("verified_player" if assembly == "fixture-assembly" else "unconfirmed_player")
    native_inputs.execute(
        "UPDATE item_acquisitions SET player_access_state=? WHERE source_stable_key='ui:cosmetic'",
        ("unconfirmed_player" if actual == "verified_player" else "verified_player",),
    )
    with pytest.raises(ValueError, match="player_access_state"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert audit["input_counts"]["ui_item_access_targets"] == 2
    assert builder.input_exclusions["ui_item_access_targets", '["desk:unused"]'] == "unused_native_ui_target"
    assert (
        native_inputs.execute(
            "SELECT COUNT(*) FROM item_provenance_evidence "
            "WHERE input_relation='ui_item_access_targets' AND input_primary_key=?",
            ('["desk:unused"]',),
        ).fetchone()[0]
        == 0
    )
    builder.input_exclusions.pop(("ui_item_access_targets", '["desk:unused"]'))
    with pytest.raises(ValueError, match="exclusions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_validator_does_not_require_a_connection_row_factory(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    connection.row_factory = None
    audit = validate_item_provenance(connection, exclusions, require_all_native_tables=False)
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
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    relation: str,
) -> None:
    connection, exclusions = persisted
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation=?",
            (relation,),
        ).fetchone()[0]
        > 0
    )
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute("DELETE FROM item_provenance_evidence WHERE input_relation=?", (relation,))
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


@pytest.fixture
def raw_persisted(
    native_inputs: sqlite3.Connection,
) -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]]]:
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
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    yield native_inputs, raw, dict(builder.input_exclusions)
    raw.close()


def test_raw_native_anti_join_preserves_every_host_exclusion_and_origin(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["input_counts"]["raw.LootDrops"] == 8
    assert (
        connection.execute("SELECT count(*) FROM item_acquisition_conditions WHERE gate_key='loot_host'").fetchone()[0]
        == 4
    )
    assert {
        row[0] for row in connection.execute("SELECT value FROM item_acquisition_conditions WHERE gate_key='loot_host'")
    } == {
        "loot_host_destroy_on_death",
        "loot_host_do_not_leave_corpse",
        "non_player_host",
        "reviewed_unexecuted_loot",
    }
    assert exclusions["raw.LootTableSources", '["loot-table:hostless"]'] == "loot_host_missing"
    connection.execute("DELETE FROM item_acquisition_conditions WHERE gate_key='loot_host'")
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM loot_drops WHERE character_stable_key='character:a' AND item_stable_key='item:reward'",
        "UPDATE loot_drops SET drop_probability=99 "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:reward'",
    ],
)
def test_raw_native_inputs_detect_clean_input_loss_or_probability_rewriting(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    connection.execute(mutation)
    with pytest.raises(ValueError, match=r"serialized loot exclusion|Native loot dimension"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_raw_host_flags_are_checked_even_when_clean_and_contract_agree(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    raw.execute("UPDATE Characters SET DestroyOnDeath=1 WHERE StableKey='character:a'")
    with pytest.raises(ValueError, match="Ineligible raw loot host"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_lifecycle_input_requires_historical_keys_without_guessing_page_only_keys(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    tmp_path: Path,
) -> None:
    connection, exclusions = persisted
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
    audit = validate_item_provenance(connection, exclusions, lifecycle_path=path, require_all_native_tables=False)
    assert audit["contract_counts"]["dispositions"] == 9
    connection.execute("DELETE FROM item_dispositions WHERE item_stable_key='item:historical'")
    with pytest.raises(ValueError, match="disposition identities"):
        validate_item_provenance(connection, exclusions, lifecycle_path=path, require_all_native_tables=False)


@pytest.mark.parametrize("mutation", ["condition", "scope"])
@pytest.mark.parametrize("kind", ["character_drop", "special_world_drop"])
def test_unique_loot_requires_native_ownership_replacement_condition(
    native_inputs: sqlite3.Connection,
    kind: str,
    mutation: str,
) -> None:
    native_inputs.execute("UPDATE items SET is_unique=1 WHERE stable_key IN ('item:reward', 'item:common')")
    native_inputs.execute("UPDATE loot_drops SET is_unique=0")
    _insert(native_inputs, "code_facts", fact_id="loot.owned_unique_replacement", key="ok", value="true")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert audit["input_counts"]["code_facts"] == 38
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind=? AND c.gate_key='not_owned' AND c.predicate='item_not_owned' "
            "AND c.reference_stable_key='item:reward' AND c.value='stored_slots_and_equipment_slots'",
            (kind,),
        ).fetchone()[0]
        == 1
    )
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind='common_world_item' AND c.gate_key='not_owned'"
        ).fetchone()[0]
        == 0
    )
    if mutation == "condition":
        native_inputs.execute(
            "DELETE FROM item_acquisition_conditions WHERE gate_key='not_owned' AND owner_key IN "
            "(SELECT acquisition_key FROM item_acquisitions WHERE kind=?)",
            (kind,),
        )
    else:
        native_inputs.execute(
            "UPDATE item_acquisition_conditions SET value=NULL WHERE gate_key='not_owned' AND owner_key IN "
            "(SELECT acquisition_key FROM item_acquisitions WHERE kind=?)",
            (kind,),
        )
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_guaranteed_roll_count_is_a_native_quantity_dimension(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE characters SET guaranteed_drop_rolls=3 WHERE stable_key='character:a'")
    native_inputs.execute(
        "UPDATE loot_drops SET is_guaranteed=1 "
        "WHERE character_stable_key='character:a' AND item_stable_key='item:reward'"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisitions WHERE kind='character_drop' AND guaranteed_roll_count=3"
        ).fetchone()[0]
        == 1
    )
    native_inputs.execute("UPDATE item_acquisitions SET guaranteed_roll_count=NULL WHERE kind='character_drop'")
    with pytest.raises(ValueError, match="guaranteed_roll_count"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_raw_unknown_required_item_cannot_be_an_exclusion(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    _insert(
        raw,
        "LootDrops",
        LootTableStableKey="loot-table:hostless",
        CharacterStableKey=None,
        ItemStableKey="item:absent",
        DropProbability=100,
    )
    with pytest.raises(ValueError, match="absent native item"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_dialog_ownership_condition_preserves_native_inventory_scope(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind='dialog' AND c.predicate='item_not_owned' AND c.value='stored_slots_and_equipment_slots'"
        ).fetchone()[0]
        == 1
    )
    connection.execute(
        "UPDATE item_acquisition_conditions SET value=NULL WHERE predicate='item_not_owned' AND owner_key IN "
        "(SELECT acquisition_key FROM item_acquisitions WHERE kind='dialog')"
    )
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    rows = native_inputs.execute(
        "SELECT l.owner_key, l.location_key, l.conditions FROM item_acquisition_locations l "
        "JOIN item_acquisitions a ON a.acquisition_key=l.owner_key "
        "WHERE a.kind='character_drop' AND a.source_copy_stable_key='character:a' AND l.relation='spawn'"
    ).fetchall()
    assert len(rows) == 1
    owner, location, serialized = rows[0]
    atoms = json.loads(serialized)
    character_gate = 'gate:["character","character:a",null,"unlock"]'
    spawn_gate = 'gate:["spawn_point","spawn:a",null,"unlock"]'
    for gate in (character_gate, spawn_gate):
        assert {atom["group_index"] for atom in atoms if atom["gate_key"] == gate} == {0, 1}
    assert conditions_satisfiable(tuple(ProvenanceCondition(**atom) for atom in atoms))
    impossible_spawn = [{**atom, "predicate": "never"} if atom["gate_key"] == spawn_gate else atom for atom in atoms]
    assert not conditions_satisfiable(tuple(ProvenanceCondition(**atom) for atom in impossible_spawn))
    native_inputs.execute(
        "UPDATE item_acquisition_locations SET conditions=? WHERE owner_key=? AND location_key=?",
        (json.dumps([atom for atom in atoms if atom["gate_key"] != spawn_gate]), owner, location),
    )
    with pytest.raises(ValueError, match="locations"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE item_acquisition_conditions SET phase='availability' WHERE gate_key='probability_context'",
        "UPDATE item_acquisition_conditions SET minimum=1, maximum=1 WHERE "
        "gate_key='probability_context' AND value='loot_bless_bonus'",
        "UPDATE item_acquisition_conditions SET actor=NULL WHERE "
        "gate_key='probability_context' AND value='top_guild_bonus'",
        "UPDATE item_acquisition_conditions SET phase='availability' WHERE gate_key='time'",
    ],
)
def test_initialization_parameters_and_operation_time_keep_their_phases(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions WHERE "
            "gate_key='probability_context' AND phase='source_initialization'"
        ).fetchone()[0]
        == 12
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions WHERE gate_key='time' AND phase='operation_input'"
        ).fetchone()[0]
        == 2
    )
    connection.execute(mutation)
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_unique_bag_suppression_is_an_initialization_condition(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE items SET is_unique=1 WHERE stable_key='item:reward'")
    _insert(native_inputs, "code_facts", fact_id="loot.owned_unique_replacement", key="ok", value="true")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind='item_bag' AND c.gate_key='initial_ownership' AND c.phase='source_initialization' "
            "AND c.value='stored_slots_and_equipment_slots'"
        ).fetchone()[0]
        == 1
    )
    native_inputs.execute(
        "UPDATE item_acquisition_conditions SET phase='operation_input' WHERE gate_key='initial_ownership'"
    )
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_special_pool_zero_level_sentinel_has_no_enemy_level_gate(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE special_world_drops SET min_level_exclusive=0")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute("SELECT count(*) FROM item_acquisitions WHERE kind='special_world_drop'").fetchone()[0]
        == 1
    )
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_conditions WHERE gate_key='enemy_level'"
        ).fetchone()[0]
        == 0
    )


def test_dialog_repeatability_comes_from_exact_assigned_resource(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE quest_variants SET repeatable=1 WHERE resource_name IN ('Unrouted', 'NoReward')")
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind='dialog' AND c.gate_key='dialog_assignment' AND c.predicate='quest_not_done' "
            "AND c.reference_stable_key='quest:one'"
        ).fetchone()[0]
        == 1
    )
    native_inputs.execute("DELETE FROM item_acquisition_conditions WHERE gate_key='dialog_assignment'")
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert audit["input_counts"]["vendor_offers"] == 3
    rows = native_inputs.execute(
        "SELECT acquisition_key, variant_key FROM item_acquisitions WHERE kind='vendor' "
        "AND source_copy_stable_key='character:a' AND item_stable_key='item:reward'"
    ).fetchall()
    assert len(rows) == 1 and rows[0][1] is None
    assert {
        row[0]
        for row in native_inputs.execute(
            "SELECT input_primary_key FROM item_provenance_evidence WHERE owner_key=? "
            "AND input_relation='vendor_offers'",
            (rows[0][0],),
        )
    } == {'["character:a","base",2]', '["character:a","base",9]'}
    native_inputs.execute(
        "DELETE FROM item_provenance_evidence WHERE owner_key=? AND input_relation='vendor_offers' "
        "AND input_primary_key=?",
        (rows[0][0], '["character:a","base",9]'),
    )
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    rows = native_inputs.execute(
        "SELECT a.acquisition_key, a.variant_key, a.quantity_min, a.expected_quantity, a.count_distribution, "
        "a.guaranteed_roll_count, u.outcome_key FROM item_acquisitions a JOIN item_uses u "
        "ON u.outcome_key=a.acquisition_key WHERE a.kind='item_drop' ORDER BY a.variant_key"
    ).fetchall()
    assert len(rows) == 2
    assert [row[1] for row in rows] == ["pool:fossils", "pool:second"]
    assert all(row[2] == 1 and row[5] == 1 and row[0] == row[6] for row in rows)
    assert [(row[3], json.loads(row[4])) for row in rows] == [(0.4, [0.6, 0.4]), (0.25, [0.75, 0.25])]
    native_inputs.execute(
        "UPDATE item_acquisitions SET variant_key=NULL WHERE kind='item_drop' AND variant_key='pool:second'"
    )
    with pytest.raises(ValueError, match="variant_key"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    relation: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation=?",
            (relation,),
        ).fetchone()[0]
        > 0
    )
    connection.execute("DELETE FROM item_provenance_evidence WHERE input_relation=?", (relation,))
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM ItemDropPoolSlots WHERE PoolStableKey='pool:fossils' AND Position=4",
        "UPDATE ItemDropPoolSlots SET ItemStableKey='item:reward' WHERE PoolStableKey='pool:fossils' AND Position=4",
    ],
)
def test_native_null_pool_positions_retain_denominator_weight(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert (
        raw.execute(
            "SELECT count(*) FROM ItemDropPoolSlots WHERE PoolStableKey='pool:fossils' AND ItemStableKey IS NULL"
        ).fetchone()[0]
        == 3
    )
    raw.execute(mutation)
    with pytest.raises(ValueError, match=r"positions|probability"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_missing_positive_native_mining_outcome_is_not_an_exclusion(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert raw.execute("SELECT count(*) FROM MiningNodeItems").fetchone()[0] == 1
    connection.execute("DELETE FROM mining_node_items")
    with pytest.raises(ValueError, match="mandatory native"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.mark.parametrize(
    ("mutation", "dimension"),
    [
        (
            "UPDATE item_acquisitions SET player_access_state='verified_player' WHERE mechanic='authored_sim_seed'",
            "player_access_state",
        ),
        ("UPDATE item_acquisitions SET variant_key=NULL WHERE mechanic='authored_sim_seed'", "variant_key"),
        ("UPDATE item_acquisition_conditions SET phase='availability' WHERE gate_key='seed_level'", "conditions"),
        ("UPDATE item_acquisition_conditions SET minimum=11 WHERE gate_key='seed_level'", "conditions"),
        (
            "UPDATE item_uses SET quantity_max=1 WHERE kind='quality_offering' AND material_slot IN (0,1)",
            "quantity_max",
        ),
        ("UPDATE item_use_conditions SET phase='operation_outcome' WHERE gate_key='chance_per_pair'", "conditions"),
        ("UPDATE item_use_conditions SET minimum=2 WHERE gate_key='fuel_level'", "conditions"),
        ("DELETE FROM item_use_conditions WHERE gate_key='input_quality' AND group_index=1", "conditions"),
    ],
)
def test_seed_and_quality_operation_dimensions_are_not_presentation_defaults(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
    dimension: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute(mutation)
    with pytest.raises(ValueError, match=dimension):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


@pytest.mark.parametrize("relation", ["authored_sims", "authored_sim_references", "authored_sim_equipment"])
def test_authored_native_defaults_remain_internal_with_complete_evidence(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    relation: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisitions WHERE mechanic='authored_sim_seed' "
            "AND player_access_state='internal_only'"
        ).fetchone()[0]
        == 1
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_dispositions WHERE item_stable_key='item:reward' AND disposition='current'"
        ).fetchone()[0]
        == 1
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation=?",
            (relation,),
        ).fetchone()[0]
        == 1
    )
    connection.execute("DELETE FROM item_provenance_evidence WHERE input_relation=?", (relation,))
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert audit["input_counts"]["authored_sim_equipment"] == 2
    assert builder.input_exclusions["authored_sims", '["authored-sim:fixture"]'] == "empty_authored_seed_configuration"
    assert (
        builder.input_exclusions["authored_sim_references", '["component:fixture-preset",2]']
        == "empty_authored_seed_configuration"
    )
    assert (
        native_inputs.execute("SELECT count(*) FROM item_acquisitions WHERE mechanic='authored_sim_seed'").fetchone()[0]
        == 0
    )


def test_literal_grant_quantity_must_match_the_extracted_native_operand(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute("UPDATE code_facts SET value='2' WHERE fact_id='item.offering_stone_grant' AND key='quantity'")
    with pytest.raises(ValueError, match="Literal item grant"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_smithing_native_byproduct_links_every_consumed_role(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    outcomes = connection.execute(
        "SELECT acquisition_key FROM item_acquisitions WHERE variant_key='blessing_removal_byproduct' "
        "AND item_stable_key='item:material' AND quantity_min=1"
    ).fetchall()
    assert len(outcomes) == 1
    assert (
        connection.execute(
            "SELECT count(*) FROM item_uses WHERE mechanic IN "
            "('remove_blessing','blessing_removal_material','blessing_removal_fuel') AND outcome_key=?",
            (outcomes[0][0],),
        ).fetchone()[0]
        == 3
    )
    connection.execute("UPDATE item_uses SET outcome_key=NULL WHERE mechanic='blessing_removal_fuel'")
    with pytest.raises(ValueError, match="outcome_key"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_partial_native_fixture_reports_missing_families_and_full_mode_rejects_them(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert "CraftingRecipes" in audit["unsupported_native_tables"]
    assert "AuthoredSimEquipment" in audit["unsupported_native_tables"]
    assert "TreasureLocations" in audit["unsupported_native_tables"]
    with pytest.raises(ValueError, match="Unsupported native input tables"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=True,
        )


def test_full_native_mode_requires_an_actual_native_database(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    with pytest.raises(ValueError, match="requires a raw database"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=True)


@pytest.mark.parametrize(
    ("table", "ddl", "rows", "mutation"),
    [
        (
            "CraftingRecipes",
            "RecipeItemStableKey TEXT,MaterialSlot INTEGER,MaterialItemStableKey TEXT,MaterialQuantity INTEGER,"
            "PRIMARY KEY(RecipeItemStableKey,MaterialSlot)",
            (("item:recipe", 1, "item:material", 4), ("item:recipe", 2, "item:material", 5)),
            "DELETE FROM crafting_recipes WHERE material_slot=2",
        ),
        (
            "CraftingRewards",
            "RecipeItemStableKey TEXT,RewardSlot INTEGER,RewardItemStableKey TEXT,RewardQuantity INTEGER,"
            "PRIMARY KEY(RecipeItemStableKey,RewardSlot)",
            (("item:recipe", 1, "item:reward", 1), ("item:recipe", 2, "item:reward", 1)),
            "DELETE FROM crafting_rewards WHERE reward_slot=2",
        ),
        (
            "ClassStartingItems",
            "ClassName TEXT,SortOrder INTEGER,ItemStableKey TEXT,PRIMARY KEY(ClassName,SortOrder)",
            (("Paladin", 0, "item:reward"), ("Paladin", 1, "item:reward")),
            "DELETE FROM class_starting_items WHERE sort_order=1",
        ),
        (
            "ItemBags",
            "StableKey TEXT PRIMARY KEY,ItemStableKey TEXT,Scene TEXT,X REAL,Y REAL,Z "
            "REAL,Respawns INTEGER,RespawnTimer REAL",
            (("bag:one", "item:reward", "One", 4, 3, 2, 0, 0),),
            "DELETE FROM item_bags",
        ),
        (
            "CharacterVendorItems",
            "CharacterStableKey TEXT,ItemSlot INTEGER,ItemStableKey TEXT,PRIMARY KEY(CharacterStableKey,ItemSlot)",
            (("character:a", 2, "item:reward"),),
            "DELETE FROM character_vendor_items",
        ),
        (
            "CharacterVendorQuestUnlocks",
            "CharacterStableKey TEXT,QuestSlot INTEGER,QuestStableKey TEXT,QuestVariantResourceName TEXT,"
            "PRIMARY KEY(CharacterStableKey,QuestSlot)",
            (("character:a", 7, "quest:one", "One"),),
            "DELETE FROM character_vendor_quest_unlocks",
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
            "DELETE FROM character_dialogs WHERE character_stable_key='character:a'",
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
            "DELETE FROM character_quest_manager_quests WHERE character_stable_key='character:a' AND quest_slot=1",
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
            "DELETE FROM quest_variants WHERE resource_name='Unrouted'",
        ),
        (
            "QuestRequiredItems",
            "QuestVariantResourceName TEXT,RequiredSlot INTEGER,ItemStableKey TEXT,Quantity INTEGER,"
            "PRIMARY KEY(QuestVariantResourceName,RequiredSlot)",
            (("One", 0, "item:material", 2), ("One", 1, "item:material", 3)),
            "DELETE FROM quest_required_items WHERE required_slot=1",
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
            "UPDATE authored_sims SET seed_level=11",
        ),
        (
            "AuthoredSimReferences",
            "SourceComponentKey TEXT,ReferenceIndex INTEGER,SourceScene TEXT,SourceScenePath TEXT,"
            "AuthoredSimStableKey TEXT,PRIMARY KEY(SourceComponentKey,ReferenceIndex)",
            (("component:fixture-preset", 2, "One", "Assets/One.unity", "authored-sim:fixture"),),
            "DELETE FROM authored_sim_references",
        ),
        (
            "AuthoredSimEquipment",
            "AuthoredSimStableKey TEXT,Position INTEGER,ItemStableKey TEXT,PRIMARY KEY(AuthoredSimStableKey,Position)",
            (("authored-sim:fixture", 0, "item:reward"), ("authored-sim:fixture", 1, None)),
            "DELETE FROM authored_sim_equipment WHERE position=1",
        ),
        (
            "TreasureLocations",
            "StableKey TEXT PRIMARY KEY,Scene TEXT,X REAL,Y REAL,Z REAL",
            (("treasure:one", "One", 4, 5, 6),),
            "UPDATE treasure_locations SET x=99",
        ),
    ],
)
def test_direct_native_occurrences_cannot_disappear_before_canonical_selection(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    table: str,
    ddl: str,
    rows: tuple[tuple[object, ...], ...],
    mutation: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    raw.execute(f"CREATE TABLE {table} ({ddl})")
    raw.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in rows[0])})", rows)
    if table == "AuthoredSims":
        _insert(raw, "Characters", StableKey="character:seed", DestroyOnDeath=0, DoNotLeaveCorpse=0, IsSimPlayer=1)
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["raw." + table] == len(rows)
    assert table not in audit["unsupported_native_tables"]
    connection.execute(mutation)
    with pytest.raises(ValueError, match=r"[Dd]irect native"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


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
) -> tuple[sqlite3.Connection, dict[tuple[str, str], str]]:
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
    return native_inputs, dict(builder.input_exclusions)


def test_encounter_state_is_local_to_the_actual_member_placement(
    claiming_encounter: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = claiming_encounter
    audit = validate_item_provenance(connection, exclusions, require_all_native_tables=False)
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
    locations = connection.execute(
        "SELECT a.source_copy_stable_key,l.coordinate_stable_key,l.location_key,l.conditions "
        "FROM item_acquisition_locations l JOIN item_acquisitions a ON a.acquisition_key=l.owner_key "
        "WHERE a.kind='vendor' AND a.item_stable_key='item:reward'"
    ).fetchall()
    assert len(locations) == 3
    for copy, coordinate, scope, serialized in locations:
        atoms = json.loads(serialized)
        states = [atom for atom in atoms if atom["predicate"] == "account_state"]
        legacy = [
            atom
            for atom in atoms
            if atom["predicate"] == "quest_not_done" and atom["reference_stable_key"] == "quest:claim"
        ]
        if copy == "character:a" and coordinate == "spawn:a":
            assert len(states) == len(legacy) == 1
            assert states[0]["actor"] == "account" and states[0]["value"] == "false"
            assert states[0]["reference_stable_key"] == "account_state:reliquary_claimed"
            assert states[0]["scope"] == scope and states[0]["phase"] == "availability"
            assert legacy[0]["scope"] == scope
        else:
            assert states == legacy == []
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions c JOIN item_acquisitions a "
            "ON a.acquisition_key=c.owner_key "
            "WHERE a.kind='vendor' AND c.predicate='account_state'"
        ).fetchone()[0]
        == 0
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisitions WHERE kind='vendor' AND item_stable_key='item:reward' "
            "AND player_access_state='verified_player'"
        ).fetchone()[0]
        == 2
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_dispositions WHERE item_stable_key='item:reward' AND disposition='current'"
        ).fetchone()[0]
        == 1
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor", None),
        ("value", None),
        ("value", "true"),
        ("reference_stable_key", "quest:claim"),
        ("scope", "source"),
        ("phase", "operation_outcome"),
    ],
)
def test_account_state_location_atoms_preserve_the_native_scope_and_phase(
    claiming_encounter: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    field: str,
    value: object,
) -> None:
    connection, exclusions = claiming_encounter
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    rows = connection.execute(
        "SELECT l.owner_key,l.location_key,l.conditions FROM item_acquisition_locations l "
        "JOIN item_acquisitions a ON a.acquisition_key=l.owner_key "
        "WHERE a.kind='vendor' AND a.item_stable_key='item:reward' AND l.coordinate_stable_key='spawn:a'"
    ).fetchall()
    assert len(rows) == 1
    owner, location, serialized = rows[0]
    atoms = json.loads(serialized)
    selected = [atom for atom in atoms if atom["predicate"] == "account_state"]
    assert len(selected) == 1
    selected[0][field] = value
    connection.execute(
        "UPDATE item_acquisition_locations SET conditions=? WHERE owner_key=? AND location_key=?",
        (json.dumps(atoms), owner, location),
    )
    with pytest.raises(ValueError, match="locations"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    claiming_encounter: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    relation: str,
) -> None:
    connection, exclusions = claiming_encounter
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation=?",
            (relation,),
        ).fetchone()[0]
        > 0
    )
    connection.execute("DELETE FROM item_provenance_evidence WHERE input_relation=?", (relation,))
    with pytest.raises(ValueError, match="evidence"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_direct_native_non_world_exclusion_requires_the_native_sim_flag(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    raw.execute(
        "CREATE TABLE CharacterVendorItems (CharacterStableKey TEXT,ItemSlot INTEGER,ItemStableKey TEXT,"
        "PRIMARY KEY(CharacterStableKey,ItemSlot))"
    )
    _insert(raw, "Characters", StableKey="character:direct-sim", DestroyOnDeath=0, DoNotLeaveCorpse=0, IsSimPlayer=1)
    _insert(raw, "CharacterVendorItems", CharacterStableKey="character:a", ItemSlot=2, ItemStableKey="item:reward")
    _insert(
        raw, "CharacterVendorItems", CharacterStableKey="character:direct-sim", ItemSlot=4, ItemStableKey="item:reward"
    )
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["raw.CharacterVendorItems"] == 2
    assert audit["direct_native_exclusions"] == [
        {
            "relation": "raw.CharacterVendorItems",
            "primary_key": '["character:direct-sim",4]',
            "reason": "non_world_character_input",
        }
    ]
    raw.execute("UPDATE Characters SET IsSimPlayer=0 WHERE StableKey='character:direct-sim'")
    with pytest.raises(ValueError, match="no mapped world character"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisitions WHERE kind='crafting' AND source_stable_key='item:removal' "
            "AND player_access_state='non_acquirable'"
        ).fetchone()[0]
        == 1
    )
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_use_conditions c JOIN item_uses u ON u.use_key=c.owner_key "
            "WHERE u.kind='crafting_material' AND u.target_stable_key='item:removal' "
            "AND c.gate_key IN ('unexecuted_material_slot','material_quality')"
        ).fetchone()[0]
        == 2
    )
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_uses WHERE mechanic='forge_fuel' AND target_stable_key='item:removal'"
        ).fetchone()[0]
        == 0
    )
    native_inputs.execute(
        "DELETE FROM item_use_conditions WHERE gate_key='unexecuted_material_slot' AND owner_key IN "
        "(SELECT use_key FROM item_uses WHERE kind='crafting_material' AND target_stable_key='item:removal')"
    )
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_gear_recipe_quantities_are_physical_units_not_encoded_quality(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE crafting_rewards SET reward_item_stable_key='item:furniture'")
    native_inputs.execute(
        "UPDATE crafting_recipes SET material_item_stable_key='item:furniture', "
        "material_quantity=1 WHERE material_slot=1"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_acquisitions a JOIN item_acquisition_conditions c "
            "ON c.owner_key=a.acquisition_key "
            "WHERE a.kind='crafting' AND a.quantity_min=1 AND a.quantity_max=1 AND c.gate_key='fuel_quality' "
            "AND c.phase='operation_outcome'"
        ).fetchone()[0]
        == 2
    )
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_use_conditions c JOIN item_uses u ON u.use_key=c.owner_key "
            "WHERE u.kind='crafting_material' AND u.quantity_min=1 AND u.quantity_max=1 "
            "AND c.gate_key='material_quality' AND c.value='normal' AND c.phase='operation_input'"
        ).fetchone()[0]
        == 1
    )
    native_inputs.execute("DELETE FROM item_use_conditions WHERE gate_key='material_quality'")
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


def test_offered_equipment_carries_the_same_native_result_and_coefficients_as_stones(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    gear = connection.execute(
        "SELECT use_key FROM item_uses WHERE kind='quality_offering' AND material_slot=2"
    ).fetchall()
    assert len(gear) == 1
    assert dict(
        connection.execute(
            "SELECT value,minimum FROM item_use_conditions WHERE owner_key=? AND phase='mechanic_parameter' "
            "AND gate_key IN ('chance_per_pair','chance_per_improvement','enhance_chance')",
            (gear[0][0],),
        ).fetchall()
    ) == {"chance_per_stone_pair": 3, "chance_per_improvement_level": 2, "enhance_chance_per_stone_pair": 1}
    assert (
        connection.execute(
            "SELECT count(*) FROM item_use_conditions WHERE owner_key=? AND phase='operation_outcome' "
            "AND gate_key IN ('result_quality','enhanced_quality')",
            (gear[0][0],),
        ).fetchone()[0]
        == 2
    )
    connection.execute(
        "DELETE FROM item_use_conditions WHERE owner_key=? AND gate_key='result_quality'",
        (gear[0][0],),
    )
    with pytest.raises(ValueError, match="conditions"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


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
    audit = validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    excluded = [row for row in audit["exclusions"] if row["relation"].startswith("encounter_")]
    assert len(excluded) == 9
    assert {row["reason"] for row in excluded} == {"no_located_item_action"}
    assert (
        native_inputs.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation LIKE 'encounter_%'"
        ).fetchone()[0]
        == 0
    )


def test_orphan_encounter_state_is_not_misclassified_as_no_item_action(
    claiming_encounter: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = claiming_encounter
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    _insert(
        connection,
        "encounter_conditions",
        encounter_key="encounter:orphan",
        state_scope="account",
        state_key="account_state:reliquary_claimed",
        required_value="false",
    )
    with pytest.raises(ValueError, match="no native placement context"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


def test_native_treasure_reading_flags_and_chest_tiers_require_every_possible_site(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    raw.executescript(
        "CREATE TABLE TreasureLocations (StableKey TEXT PRIMARY KEY,Scene TEXT,X REAL,Y REAL,Z REAL);"
        "CREATE TABLE TreasureHunting (ZoneName TEXT PRIMARY KEY,ZoneDisplayName TEXT,IsPickableAlways INTEGER,"
        "IsPickableGreater20 INTEGER,IsPickableGreater30 INTEGER);"
    )
    _insert(raw, "TreasureLocations", StableKey="treasure:one", Scene="One", X=4, Y=5, Z=6)
    _insert(
        raw,
        "TreasureHunting",
        ZoneName="One",
        ZoneDisplayName="One",
        IsPickableAlways=1,
        IsPickableGreater20=0,
        IsPickableGreater30=0,
    )
    _insert(
        connection,
        "treasure_hunting",
        zone_name="One",
        zone_display_name="One",
        is_pickable_always=1,
        is_pickable_greater_20=0,
        is_pickable_greater_30=0,
        min_reading_level=1,
    )
    for fact in ("treasure.zone_pool_by_level", "treasure.chest_tier_by_level", "player.level_cap"):
        _insert(connection, "code_facts", fact_id=fact, key="ok", value="true")
    connection.execute("DELETE FROM treasure_chest_possible_spawns")
    connection.execute("DELETE FROM item_acquisition_locations WHERE coordinate_stable_key='treasure:one'")
    connection.execute("DELETE FROM item_use_locations WHERE coordinate_stable_key='treasure:one'")
    for chest, low, high, minimum, maximum in (
        ("character:treasurechest 0-10 1", 0, 10, 1, 9),
        ("character:treasurechest 10-20 1", 10, 20, 10, 19),
        ("character:treasurechest 20-30 1", 20, 30, 20, 29),
        ("character:treasurechest 30-35", 30, 999, 30, 35),
    ):
        _insert(raw, "Characters", StableKey=chest, DestroyOnDeath=0, DoNotLeaveCorpse=0, IsSimPlayer=0)
        _insert(
            connection,
            "characters",
            stable_key=chest,
            display_name=chest,
            image_name="",
            encounter_tier="chest",
            level_scales_with_player=1,
        )
        _insert(connection, "character_deduplications", group_key=chest, member_stable_key=chest, is_wiki_generated=1)
        _insert(
            connection,
            "treasure_chest_possible_spawns",
            chest_character_stable_key=chest,
            treasure_location_stable_key="treasure:one",
            level_min=low,
            level_max=high,
            player_level_min=minimum,
            player_level_max=maximum,
            scene="One",
            x=4,
            y=5,
            z=6,
        )
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["raw.TreasureHunting"] == 1
    assert audit["direct_native_counts"]["raw.TreasureLocations"] == 1
    assert connection.execute("SELECT count(*) FROM treasure_chest_possible_spawns").fetchone()[0] == 4
    connection.execute(
        "DELETE FROM treasure_chest_possible_spawns WHERE chest_character_stable_key='character:treasurechest 20-30 1'"
    )
    with pytest.raises(ValueError, match="Native treasure locations and tiers"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            "UPDATE LootTableSources SET CharacterStableKey='character:a' WHERE StableKey='loot-table:component'",
            "mining",
        ),
        (
            "UPDATE LootTableSources SET MiningNodeStableKey='node:missing' WHERE StableKey='loot-table:component'",
            "Missing native",
        ),
        (
            "UPDATE LootTablePoolSlots SET ItemStableKey='item:reward' WHERE LootTableStableKey='loot-table:component'",
            "mining",
        ),
        ("UPDATE LootTableSources SET MiningNodeStableKey=NULL WHERE StableKey='loot-table:component'", "exclusions"),
    ],
)
def test_non_world_mining_host_requires_the_actual_native_binding_and_no_item_grants(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    mutation: str,
    message: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    _insert(
        raw,
        "LootTableSources",
        StableKey="loot-table:component",
        CharacterStableKey=None,
        MiningNodeStableKey="node:one",
        ComponentIndex=0,
        ComponentIsEnabled=1,
        MaxNumberDrops=0,
        MaxNonCommonDrops=0,
        NumberOfGuaranteedDrops=0,
        UltraRareDropCount=0,
        LegendaryDropCount=0,
        RareDropCount=0,
        UncommonDropCount=0,
        CommonDropCount=1,
        GuaranteeOneDropCount=0,
        ActualDropsCount=0,
    )
    _insert(
        raw,
        "LootTablePoolSlots",
        LootTableStableKey="loot-table:component",
        Pool="CommonDrop",
        Position=0,
        ItemStableKey=None,
    )
    exclusions["raw.LootTableSources", '["loot-table:component"]'] = "non_world_mining_host"
    exclusions["raw.LootTablePoolSlots", '["loot-table:component","CommonDrop",0]'] = "non_world_mining_host"
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["input_counts"]["raw.LootTableSources"] == 9
    assert (
        raw.execute("SELECT count(*) FROM LootDrops WHERE LootTableStableKey='loot-table:component'").fetchone()[0] == 0
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisitions WHERE source_stable_key='loot-table:component'"
        ).fetchone()[0]
        == 0
    )
    raw.execute(mutation)
    with pytest.raises(ValueError, match=message):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def _seed_native_item_registry(raw: sqlite3.Connection) -> None:
    raw.execute(
        'CREATE TABLE Items (StableKey TEXT PRIMARY KEY,Id TEXT,"Unique" INTEGER,RequiredSlot TEXT,Template INTEGER,'
        "FuelSource INTEGER,FuelLevel INTEGER,ItemLevel INTEGER,SimPlayersCantGet "
        "INTEGER,ItemEffectOnClickStableKey TEXT)"
    )
    ids = {"reward": "31377423", "removal": "2298018", "input": "2265228", "material": "46289586", "other": "340104"}
    for name in ("reward", "material", "recipe", "common", "input", "other", "furniture", "removal"):
        _insert(
            raw,
            "Items",
            StableKey="item:" + name,
            Id=ids.get(name),
            Unique=0,
            RequiredSlot="Head" if name == "furniture" else "Aura" if name == "other" else "General",
            Template=int(name == "recipe"),
            FuelSource=int(name == "material"),
            FuelLevel=3 if name == "material" else 0,
            ItemLevel=10,
            SimPlayersCantGet=0,
            ItemEffectOnClickStableKey="spell:create" if name == "input" else None,
        )


def test_native_unique_flag_cannot_be_lost_by_both_cleaning_and_canonical_selection(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    _seed_native_item_registry(raw)
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["raw.Items"] == 8
    assert "Spells" in audit["unsupported_native_tables"]
    raw.execute('UPDATE Items SET "Unique"=1 WHERE StableKey=?', ("item:reward",))
    with pytest.raises(ValueError, match="Direct native dimension differs: Items"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.fixture
def registry_click_sources(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]]:
    connection, raw, _exclusions = raw_persisted
    _seed_native_item_registry(raw)
    raw.execute("CREATE TABLE Spells (StableKey TEXT PRIMARY KEY,SpellName TEXT)")
    _insert(raw, "Spells", StableKey="spell:create", SpellName="Offering Stone")
    _insert(raw, "Spells", StableKey="spell:break-fossil", SpellName="Break Fossil")
    _insert(
        connection,
        "spells",
        stable_key="spell:break-fossil",
        spell_name="Break Fossil",
        display_name="Break Fossil",
        image_name="",
    )
    for name in ("fossil", "second-fossil"):
        _insert(
            connection,
            "items",
            stable_key="item:" + name,
            display_name=name,
            image_name="",
            id=name,
            required_slot="General",
            template=0,
            fuel_source=0,
            fuel_level=0,
            item_level=10,
            sim_players_cant_get=0,
            is_unique=0,
            item_effect_on_click_stable_key="spell:break-fossil",
        )
        _insert(
            raw,
            "Items",
            StableKey="item:" + name,
            Id=name,
            Unique=0,
            RequiredSlot="General",
            Template=0,
            FuelSource=0,
            FuelLevel=0,
            ItemLevel=10,
            SimPlayersCantGet=0,
            ItemEffectOnClickStableKey="spell:break-fossil",
        )
    connection.execute("UPDATE item_drops SET source_item_stable_key='item:fossil',pool_stable_key='Misc.FossilGame'")
    raw.execute("UPDATE ItemDrops SET SourceItemStableKey='item:fossil',PoolStableKey='Misc.FossilGame'")
    raw.execute("UPDATE ItemDropPools SET PoolStableKey='Misc.FossilGame'")
    raw.execute("UPDATE ItemDropPoolSlots SET PoolStableKey='Misc.FossilGame'")
    _insert(
        connection,
        "item_drops",
        source_item_stable_key="item:second-fossil",
        dropped_item_stable_key="item:reward",
        pool_stable_key="Misc.FossilGame",
        drop_probability=40,
        is_guaranteed=1,
    )
    _insert(
        raw,
        "ItemDrops",
        SourceItemStableKey="item:second-fossil",
        DroppedItemStableKey="item:reward",
        PoolStableKey="Misc.FossilGame",
        DropProbability=40,
        IsGuaranteed=1,
    )
    for table in (
        "item_acquisition_conditions",
        "item_use_conditions",
        "item_acquisition_locations",
        "item_use_locations",
        "item_provenance_evidence",
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
    builder.persist()
    connection.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', CASE WHEN wiki_page_name IS NULL THEN '[]' "
        "ELSE json_array(wiki_page_name) END, '[]' FROM items"
    )
    return connection, raw, dict(builder.input_exclusions)


def test_literal_click_source_cannot_disappear_before_canonical_selection(
    registry_click_sources: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = registry_click_sources
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["derived.spell_created_items"] == 1
    assert audit["direct_native_counts"]["raw.Items"] == 10
    connection.execute("DELETE FROM spell_created_items")
    with pytest.raises(ValueError, match="Native literal click grants"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_one_native_pool_click_source_cannot_be_hidden_by_another_sources_shared_configuration(
    registry_click_sources: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = registry_click_sources
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["derived.item_drops"] == 2
    assert raw.execute("SELECT count(*) FROM ItemDrops").fetchone()[0] == 2
    raw.execute("DELETE FROM ItemDrops WHERE SourceItemStableKey='item:second-fossil'")
    connection.execute("DELETE FROM item_drops WHERE source_item_stable_key='item:second-fossil'")
    with pytest.raises(ValueError, match="Native click sources and slot weights"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


@pytest.mark.parametrize("key", ["quantity", "rolls"])
def test_pool_draw_count_proofs_cannot_change_without_rederiving_the_contract(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
    key: str,
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE input_relation='code_facts' "
            "AND input_primary_key LIKE '[\"item.fossil_pool_grant\",%'"
        ).fetchone()[0]
        == 8
    )
    connection.execute("UPDATE code_facts SET value='2' WHERE fact_id='item.fossil_pool_grant' AND key=?", (key,))
    with pytest.raises(ValueError, match="single-item, single-roll"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


@pytest.mark.parametrize("table", ["ItemClasses", "Spells"])
def test_native_actor_class_and_spell_discriminators_are_authoritative(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
    table: str,
) -> None:
    connection, raw, exclusions = raw_persisted
    if table == "ItemClasses":
        raw.execute("CREATE TABLE ItemClasses (ItemStableKey TEXT,ClassName TEXT,PRIMARY KEY(ItemStableKey,ClassName))")
        _insert(raw, "ItemClasses", ItemStableKey="item:other", ClassName="Paladin")
        mutation = "DELETE FROM item_classes"
    else:
        raw.execute("CREATE TABLE Spells (StableKey TEXT PRIMARY KEY,SpellName TEXT)")
        _insert(raw, "Spells", StableKey="spell:create", SpellName="Offering Stone")
        mutation = "UPDATE Spells SET SpellName='Other'"
    audit = validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert audit["direct_native_counts"]["raw." + table] == 1
    (connection if table == "ItemClasses" else raw).execute(mutation)
    with pytest.raises(ValueError, match=r"[Dd]irect native"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_native_component_enablement_cannot_be_lost_between_raw_and_clean(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = raw_persisted
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    assert connection.execute("SELECT count(*) FROM loot_drops WHERE source_component_is_enabled=1").fetchone()[0] == 4
    raw.execute("UPDATE LootTableSources SET ComponentIsEnabled=0 WHERE StableKey='loot-table:a'")
    with pytest.raises(ValueError, match="component enablement differs"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
        )


def test_disabled_common_world_row_cannot_bypass_initializer_rejection(
    persisted: tuple[sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, exclusions = persisted
    validate_item_provenance(connection, exclusions, require_all_native_tables=False)
    connection.execute(
        "UPDATE loot_drops SET source_component_is_enabled=0 WHERE character_stable_key='character:a' "
        "AND item_stable_key='item:common'"
    )
    with pytest.raises(ValueError, match="Disabled native loot"):
        validate_item_provenance(connection, exclusions, require_all_native_tables=False)


@pytest.fixture
def disabled_preseed(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]]:
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
    for table in (
        "item_acquisition_conditions",
        "item_use_conditions",
        "item_acquisition_locations",
        "item_use_locations",
        "item_provenance_evidence",
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
    builder.persist()
    connection.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    return connection, raw, dict(builder.input_exclusions)


def test_disabled_actual_preseed_retains_native_copies_without_claiming_player_access_or_initialization(
    disabled_preseed: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
) -> None:
    connection, raw, exclusions = disabled_preseed
    validate_item_provenance(
        connection,
        exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
        require_all_native_tables=False,
    )
    rows = connection.execute(
        "SELECT acquisition_key,player_access_state,mechanic,probability_min,count_distribution,"
        "quantity_min,quantity_max,guarantee_scope,guaranteed_roll_count FROM item_acquisitions "
        "WHERE kind='character_drop' AND source_copy_stable_key='character:a' AND item_stable_key='item:reward'"
    ).fetchall()
    assert len(rows) == 1
    owner, state, mechanic, chance, distribution, low, high, guarantee, rolls = rows[0]
    assert (state, mechanic, chance, json.loads(distribution), low, high, guarantee, rolls) == (
        "unconfirmed_player",
        "preseeded_before_start",
        100,
        [0, 1],
        1,
        1,
        None,
        None,
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_acquisition_conditions WHERE owner_key=? "
            "AND (gate_key IN ('not_owned','probability_context') OR predicate='never')",
            (owner,),
        ).fetchone()[0]
        == 0
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_provenance_evidence WHERE owner_key=? AND input_relation='raw.LootTableSources' "
            "AND input_primary_key='[\"loot-table:a\"]'",
            (owner,),
        ).fetchone()[0]
        == 1
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM item_dispositions WHERE item_stable_key='item:reward' AND disposition='current'"
        ).fetchone()[0]
        == 1
    )
    connection.execute(
        "UPDATE item_acquisitions SET player_access_state='verified_player' WHERE acquisition_key=?", (owner,)
    )
    with pytest.raises(ValueError, match="player_access_state"):
        validate_item_provenance(
            connection,
            exclusions,
            raw=raw,
            reviewed_unreachable=frozenset({"character:reviewed"}),
            require_all_native_tables=False,
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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    rows = native_inputs.execute(
        "SELECT quantity_min,quantity_max,quantity_kind,player_access_state FROM item_acquisitions "
        "WHERE kind='character_drop' AND source_copy_stable_key='character:a'"
    ).fetchall()
    assert len(rows) == 1 and tuple(rows[0]) == (low, high, kind, access)
    native_inputs.execute(
        "UPDATE item_acquisitions SET quantity_min=9 WHERE kind='character_drop' AND "
        "source_copy_stable_key='character:a'"
    )
    with pytest.raises(ValueError, match="quantity_min"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    rows = native_inputs.execute(
        "SELECT quantity_min,quantity_max,quantity_kind,count_distribution,expected_quantity FROM item_acquisitions "
        "WHERE kind='common_world_item'"
    ).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == (
        (None, None, "unknown", None, None) if unknown_contributor else (1, 2, "bounded", None, None)
    )
    native_inputs.execute("UPDATE item_acquisitions SET quantity_max=9 WHERE kind='common_world_item'")
    with pytest.raises(ValueError, match="quantity_max"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


@pytest.mark.parametrize("enabled", [0, 1])
@pytest.mark.parametrize(
    ("immune", "damageable", "chest", "available"),
    [(0, 1, 0, True), (1, 1, 0, True), (1, 0, 0, False), (1, 0, 1, True)],
    ids=["mortal", "native_release", "permanently_immune", "chest_break"],
)
def test_kill_loot_access_is_separate_from_native_inventory_and_initializer(
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
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
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
        for evidence in fact.evidence
        if evidence.input_relation == "code_facts" and json.loads(evidence.input_primary_key)[0].startswith("treasure.")
    } == ({"treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt"} if chest else set())
    assert fact.mechanic == (None if enabled else "preseeded_before_start")
    assert any(atom.phase == "source_initialization" for atom in fact.conditions) == bool(enabled)
    assert not any(atom.predicate == "never" for atom in fact.conditions)
    assert any(
        evidence.input_relation == "loot_drops"
        and json.loads(evidence.input_primary_key) == ["character:a", "item:reward"]
        for evidence in fact.evidence
    )
    native_inputs.execute(
        "UPDATE item_acquisitions SET player_access_state=? WHERE acquisition_key=?",
        ("verified_player" if access != "verified_player" else "non_acquirable", fact.acquisition_key),
    )
    with pytest.raises(ValueError, match="player_access_state"):
        validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)


@pytest.mark.parametrize(("a_damageable", "b_damageable"), [(1, 1), (1, 0), (0, 1), (0, 0)])
def test_common_world_bounds_and_native_coverage_use_only_loot_capable_contributors(
    raw_persisted: tuple[sqlite3.Connection, sqlite3.Connection, dict[tuple[str, str], str]],
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
        "item_acquisition_locations",
        "item_use_locations",
        "item_provenance_evidence",
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
    builder.persist()
    connection.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    audit = validate_item_provenance(
        connection,
        builder.input_exclusions,
        raw=raw,
        reviewed_unreachable=frozenset({"character:reviewed"}),
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
            for evidence in fact.evidence
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
        missing = dict(builder.input_exclusions)
        del missing["loot_drops", '["character:b","item:common"]']
        with pytest.raises(ValueError, match="exclusion"):
            validate_item_provenance(
                connection,
                missing,
                raw=raw,
                reviewed_unreachable=frozenset({"character:reviewed"}),
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
    with pytest.raises(ValueError, match=missing):
        validate_item_provenance(native_inputs, {}, require_all_native_tables=False)


def test_immune_common_world_unknown_rate_cannot_poison_eligible_bounds(native_inputs: sqlite3.Connection) -> None:
    native_inputs.execute("UPDATE characters SET invulnerable=1,can_be_damaged=0 WHERE stable_key='character:b'")
    native_inputs.execute(
        "UPDATE loot_drops SET drop_probability=NULL,expected_per_kill=NULL,drop_count_distribution=NULL "
        "WHERE character_stable_key='character:b' AND item_stable_key='item:common'"
    )
    builder = ProvenanceBuilder(native_inputs)
    builder.select()
    builder.account_support_inputs()
    builder.persist()
    native_inputs.execute(
        "INSERT INTO item_dispositions (item_stable_key, disposition, current_pages, former_pages) "
        "SELECT stable_key, 'current', json_array(wiki_page_name), '[]' FROM items"
    )
    validate_item_provenance(native_inputs, builder.input_exclusions, require_all_native_tables=False)
    facts = [fact for fact in builder.acquisitions if fact.kind == "common_world_item"]
    assert len(facts) == 1
    fact = facts[0]
    assert (fact.probability_kind, fact.probability_min, fact.probability_max) == ("exact", 10, 10)
    assert (fact.quantity_kind, fact.quantity_min, fact.quantity_max) == ("exact", 1, 1)
