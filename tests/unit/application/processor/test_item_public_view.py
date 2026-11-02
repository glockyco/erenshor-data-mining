"""The rule that decides which item facts and conditions players see."""

from __future__ import annotations

from erenshor.application.processor.item_public_view import derive_public_view
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
)
from erenshor.domain.value_objects.item_public_view import public_conditions

ITEM = "item:fixture"


def acquisition(key: str, **overrides: object) -> ItemAcquisition:
    values: dict[str, object] = {
        "acquisition_key": key,
        "item_stable_key": ITEM,
        "kind": "vendor",
        "source_stable_key": "character:vendor",
        "probability_kind": "not_applicable",
    }
    values.update(overrides)
    return ItemAcquisition(**values)  # type: ignore[arg-type]


def condition(predicate: str, **overrides: object) -> ProvenanceCondition:
    values: dict[str, object] = {"gate_key": predicate, "group_index": 0, "atom_index": 0, "predicate": predicate}
    values.update(overrides)
    return ProvenanceCondition(**values)  # type: ignore[arg-type]


def view(*acquisitions: ItemAcquisition, uses: tuple[ItemUse, ...] = (), mechanisms=None, evidence=None):
    return derive_public_view(
        acquisitions,
        uses,
        (ItemDisposition(ITEM, "current"), ItemDisposition("item:retired", "removed")),
        evidence or {},
        mechanisms or {},
    )


def reasons(result) -> dict[str, str]:
    return {omission.owner_key: omission.reason for omission in result.omissions}


def test_only_facts_a_player_can_act_on_are_public() -> None:
    result = view(
        acquisition("shown"),
        acquisition("unconfirmed", player_access_state="unconfirmed_player"),
        acquisition("pool", probability_stage="native_pool"),
        acquisition("zero", probability_kind="exact", probability_min=0, probability_max=0),
        acquisition("never", conditions=(condition("never"),)),
        acquisition("retired", item_stable_key="item:retired"),
        acquisition(
            "too high",
            conditions=(condition("actor_level", actor="player", maximum=10),),
            location_source_key="character:vendor",
            locations=(
                ProvenanceLocation(
                    "spawn",
                    "spawn",
                    conditions=(condition("actor_level", gate_key="place", actor="player", minimum=20),),
                ),
            ),
        ),
    )
    assert [source.source_key for source in result.sources] == ["shown"]
    assert reasons(result) == {
        "unconfirmed": "unconfirmed_player",
        "pool": "native_pool",
        "zero": "zero_probability",
        "never": "unsatisfiable_conditions",
        "retired": "item_not_current",
        "too high": "no_compatible_place",
    }


def test_conditions_that_describe_a_mechanism_are_hidden() -> None:
    shown = condition("quest_done", reference_stable_key="quest:a")
    hidden = (
        condition("formula_operand", gate_key="formula", value="roll"),
        condition("source_replenishment", value="while_source_active"),
        condition("chance", phase="mechanic_parameter"),
        condition("account_state", reference_stable_key="account_state:x", value="true", phase="operation_outcome"),
        condition("item_not_owned", reference_stable_key="item:y", phase="source_initialization"),
    )
    [public] = public_conditions((shown, *hidden))
    assert (public.predicate, public.reference_stable_key, public.gate_index) == ("quest_done", "quest:a", 0)


def test_a_gate_with_an_alternative_that_needs_nothing_visible_is_hidden() -> None:
    either = (
        condition("quest_done", gate_key="either", reference_stable_key="quest:a"),
        condition("formula_operand", gate_key="either", group_index=1, value="roll"),
    )
    both = (
        condition("quest_done", gate_key="both", reference_stable_key="quest:b"),
        condition("actor_class", gate_key="both", group_index=1, reference_stable_key="class:c"),
    )
    conditions = public_conditions((*either, *both))
    assert [(c.gate_key, c.alternative_index) for c in conditions] == [("both", 0), ("both", 1)]
    assert {c.gate_index for c in conditions} == {0}


def test_a_gate_that_another_gate_or_every_place_requires_is_shown_once() -> None:
    def activation(gate: str) -> tuple[ProvenanceCondition, ...]:
        return (
            condition("quest_done", gate_key=gate, reference_stable_key="quest:claim"),
            condition("room_furnished", gate_key=gate, atom_index=1, reference_stable_key="item:vendor set"),
        )

    furnished = condition("room_furnished", gate_key="furnishing", reference_stable_key="item:vendor set")
    place = ProvenanceLocation("spawn", "spawn", conditions=(*activation("character"), *activation("spawn"), furnished))
    level = condition("actor_level", actor="player", minimum=5)
    result = view(
        acquisition(
            "stock", conditions=(*activation("character"), level), location_source_key="character:a", locations=(place,)
        )
    )
    [source] = result.sources
    assert [(c.gate_index, c.predicate) for c in source.conditions] == [(0, "actor_level")]
    [stored] = result.places
    assert [(c.gate_key, c.predicate) for c in stored.conditions] == [
        ("character", "quest_done"),
        ("character", "room_furnished"),
    ]


def test_catches_at_the_global_rate_become_one_any_water_source() -> None:
    bonus = acquisition(
        "bonus",
        kind="fishing_bonus",
        source_stable_key=None,
        mechanic="fishing_global_replacement",
        probability_kind="exact",
        probability_min=1.25,
        probability_max=1.25,
        probability_stage="native_pool",
    )

    def water(key: str, chance: float) -> ItemAcquisition:
        return acquisition(
            key,
            kind="fishing",
            source_stable_key=key,
            probability_kind="exact",
            probability_min=chance,
            probability_max=chance,
            probability_basis="per_successful_catch",
            quantity_kind="exact",
            quantity_min=1,
            quantity_max=1,
            conditions=(condition("time_of_day", actor="player", value="day"),),
        )

    result = view(bonus, water("water:a", 1.25), water("water:b", 1.25), water("water:c", 7.5))
    by_key = {source.source_key: source for source in result.sources}
    assert set(by_key) == {"bonus", "water:c"}
    any_water = by_key["bonus"]
    assert (any_water.kind, any_water.probability_min, any_water.place_set_key, any_water.conditions) == (
        "fishing",
        1.25,
        None,
        (),
    )
    assert reasons(result) == {"water:a": "any_water_member", "water:b": "any_water_member"}


def test_a_fact_that_can_use_only_some_places_names_that_subset_once() -> None:
    low = ProvenanceLocation("low", "spawn", player_level_min=1, player_level_max=10)
    high = ProvenanceLocation(
        "high", "spawn", conditions=(condition("actor_level", gate_key="place", actor="player", minimum=30),)
    )
    capped = (condition("actor_level", actor="player", maximum=20),)
    result = view(
        acquisition("all", location_source_key="character:a", locations=(low, high)),
        acquisition("capped", conditions=capped, location_source_key="character:a", locations=(low, high)),
        acquisition("capped too", conditions=capped, location_source_key="character:a", locations=(low, high)),
    )
    keys = {source.source_key: source.place_set_key for source in result.sources}
    assert keys["all"] == "character:a"
    assert keys["capped"] == keys["capped too"] != "character:a"
    assert sorted((place.place_set_key, place.place_key) for place in result.places) == sorted(
        [("character:a", "low"), ("character:a", "high"), (keys["capped"], "low")]
    )


def test_an_operation_needs_a_current_item_for_each_of_its_inputs() -> None:
    result = view(
        acquisition("molded", kind="crafting", source_stable_key="item:retired"),
        acquisition("offered", kind="crafting", source_stable_key="item:well"),
        uses=(
            ItemUse("mold", "item:retired", "item:retired", "crafting_recipe", outcome_key="molded"),
            # A material names its mold, not the craft it yields.
            ItemUse("material", ITEM, "item:retired", "crafting_material", material_slot=1),
            ItemUse("retired offer", "item:retired", "item:well", "quality_offering", outcome_key="offered"),
            ItemUse("current offer", ITEM, "item:well", "quality_offering", outcome_key="offered"),
        ),
    )
    assert [source.source_key for source in result.sources] == ["offered"]
    assert reasons(result) == {
        "molded": "input_not_current",
        "mold": "item_not_current",
        "material": "recipe_not_public",
        "retired offer": "item_not_current",
    }


def test_a_use_whose_outcome_is_hidden_is_hidden() -> None:
    result = view(
        acquisition("outcome", player_access_state="internal_only"),
        uses=(ItemUse("use", ITEM, None, "crafting_material", outcome_key="outcome"),),
    )
    assert result.uses == ()
    assert reasons(result)["use"] == "outcome_not_public"


def test_a_mechanism_keeps_its_shared_parameters_once() -> None:
    chance = condition(
        "formula_operand", gate_key="chance", value="chance_per_pair", minimum=40, phase="mechanic_parameter"
    )
    result = view(
        acquisition("a", mechanic="wells", conditions=(chance,)),
        acquisition("b", mechanic="wells", conditions=(chance,)),
        mechanisms={"wells": (chance,), "unused": (chance,)},
    )
    assert [(p.mechanic_key, p.value, p.minimum) for p in result.parameters] == [("wells", "chance_per_pair", 40)]
    assert all(source.conditions == () for source in result.sources)


def test_common_world_items_list_their_contributors() -> None:
    result = view(
        acquisition("common", kind="common_world_item", source_stable_key=None),
        evidence={"common": (ProvenanceEvidence("loot_drops", '["character:a","item:fixture"]'),)},
    )
    assert result.contributors == (("common", "character:a"),)
