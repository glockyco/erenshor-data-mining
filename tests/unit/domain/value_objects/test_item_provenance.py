"""Schema1 facts preserve every dimension and reject malformed contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, fields, replace

import pytest

from erenshor.domain.value_objects.item_provenance import (
    CONDITION_PHASES,
    PROVENANCE_SCHEMA_VERSION,
    ConditionPhase,
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    conditions_satisfiable,
    fact_from_dict,
    fact_to_dict,
    is_actionable_acquisition,
    validate_provenance_metadata,
    validate_provenance_schema_version,
)


def _acquisition() -> ItemAcquisition:
    condition = ProvenanceCondition(
        "furnishing",
        2,
        3,
        "room_furnished",
        "item:furniture",
        "slot:2",
        "player",
        "furnished",
        1.25,
        3.5,
        False,
        True,
        "placement:copy",
    )
    location = ProvenanceLocation(
        "location:copy",
        "possible_treasure",
        "Scene",
        "zone:scene",
        "placement:copy",
        "point:copy",
        1.123456789,
        -2.25,
        3.75,
        "placement:copy",
        10,
        25,
        (condition,),
        ("entry:a", "entry:b"),
        "character:copy",
    )
    return ItemAcquisition(
        "acquisition:one",
        "item:one",
        "character_drop",
        "group:one",
        "group:one",
        "character:copy",
        "variant:one",
        "mechanic:one",
        "verified_player",
        "bounded",
        0.123456789,
        35.75,
        "per_kill",
        "final_acquisition",
        0.5,
        4.5,
        "bounded",
        1.23456789,
        '{"0":0.2,"1":0.3,"2":0.5}',
        "pool",
        3,
        (condition,),
        (location,),
        (ProvenanceEvidence("loot_drops", '["copy","item"]'),),
    )


def test_json_roundtrip_retains_every_fact_dimension() -> None:
    acquisition = _acquisition()
    use = ItemUse(
        "use:one",
        "item:one",
        "item:target",
        "crafting_material",
        "variant:one",
        2,
        0.5,
        4.5,
        "bounded",
        "mechanic:one",
        acquisition.acquisition_key,
        acquisition.conditions,
        acquisition.locations,
        acquisition.evidence,
    )
    disposition = ItemDisposition("item:one", "current", "Reviewed", "review:one", ("Current",), ("Former",))
    for fact in (acquisition, use, disposition):
        encoded = fact_to_dict(fact)
        assert set(encoded) == {field.name for field in fields(fact)}
        assert fact_from_dict(json.loads(json.dumps(encoded))) == fact


@pytest.mark.parametrize("count", [None, 0, 4])
def test_pool_guarantee_count_is_independent_of_item_chance(count: int | None) -> None:
    fact = replace(_acquisition(), guaranteed_roll_count=count)
    decoded = fact_from_dict(json.loads(json.dumps(fact_to_dict(fact))))
    assert decoded == fact
    assert isinstance(decoded, ItemAcquisition)
    assert decoded.guaranteed_roll_count == count
    assert decoded.probability_min == 0.123456789
    assert decoded.guarantee_scope == "pool"


@pytest.mark.parametrize("field", [field.name for field in fields(ItemAcquisition)])
def test_decoder_rejects_every_missing_acquisition_dimension(field: str) -> None:
    data = asdict(_acquisition())
    del data[field]
    with pytest.raises(ValueError):
        fact_from_dict(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "future_kind"),
        ("player_access_state", "maybe"),
        ("probability_kind", "likely"),
        ("probability_stage", "intermediate"),
        ("probability_basis", "per_unknown"),
        ("probability_min", True),
        ("probability_min", "0.1"),
        ("probability_min", -1),
        ("probability_max", 101),
        ("probability_min", float("nan")),
        ("probability_max", float("inf")),
        ("quantity_kind", "many"),
        ("quantity_kind", "fixed"),
        ("quantity_min", -0.5),
        ("quantity_max", "2"),
        ("expected_quantity", -1),
        ("expected_quantity", float("nan")),
        ("guarantee_scope", "always"),
        ("guaranteed_roll_count", True),
        ("guaranteed_roll_count", -1),
        ("guaranteed_roll_count", 2.0),
        ("count_distribution", "invalid"),
        ("count_distribution", '{"-1":0.5}'),
        ("count_distribution", '{"1":true}'),
        ("count_distribution", '{"1":1.5}'),
        ("count_distribution", '{"1":0.75,"2":0.75}'),
        ("count_distribution", "null"),
        ("conditions", {}),
        ("locations", "none"),
        ("evidence", ["untyped"]),
    ],
)
def test_decoder_rejects_malformed_acquisition_fields(field: str, value: object) -> None:
    data = asdict(_acquisition())
    data[field] = value
    with pytest.raises(ValueError):
        fact_from_dict(data)


@pytest.mark.parametrize(
    "kind,minimum,maximum",
    [
        ("exact", 1, 2),
        ("exact", None, None),
        ("unknown", 0, 0),
        ("not_applicable", 0, 1),
        ("bounded", None, 1),
        ("bounded", 3, 1),
    ],
)
def test_probability_interval_semantics_are_validated(kind: str, minimum: object, maximum: object) -> None:
    data = asdict(_acquisition())
    data.update(probability_kind=kind, probability_min=minimum, probability_max=maximum)
    with pytest.raises(ValueError):
        fact_from_dict(data)


@pytest.mark.parametrize(
    "family,field,value",
    [
        ("conditions", "predicate", "unknown"),
        ("conditions", "group_index", -1),
        ("conditions", "atom_index", True),
        ("conditions", "minimum", "2"),
        ("conditions", "maximum", float("inf")),
        ("conditions", "minimum_inclusive", 1),
        ("conditions", "actor", "unknown_actor"),
        ("conditions", "scope", ""),
        ("conditions", "reference_stable_key", None),
        ("locations", "relation", "unknown"),
        ("locations", "x", float("nan")),
        ("locations", "y", None),
        ("locations", "player_level_min", 2.5),
        ("locations", "player_level_max", 0),
        ("locations", "entry_zone_line_keys", [None]),
        ("locations", "conditions", [None]),
        ("evidence", "input_relation", ""),
        ("evidence", "input_primary_key", 123),
    ],
)
def test_decoder_rejects_malformed_children(family: str, field: str, value: object) -> None:
    data = asdict(_acquisition())
    child = dict(data[family][0])
    child[field] = value
    data[family] = [child]
    with pytest.raises(ValueError):
        fact_from_dict(data)


@pytest.mark.parametrize("family", [None, "conditions", "locations", "evidence"])
def test_decoder_rejects_unknown_mandatory_fields(family: str | None) -> None:
    data = asdict(_acquisition())
    if family is None:
        data["new_mandatory_dimension"] = "not understood"
    else:
        child = dict(data[family][0])
        child["new_mandatory_dimension"] = "not understood"
        data[family] = [child]
    with pytest.raises(ValueError, match="unknown fields"):
        fact_from_dict(data)


@pytest.mark.parametrize("family", ["conditions", "locations", "evidence"])
def test_decoder_rejects_duplicate_child_identities(family: str) -> None:
    data = asdict(_acquisition())
    data[family] = [data[family][0], data[family][0]]
    with pytest.raises(ValueError, match="Duplicate"):
        fact_from_dict(data)


def test_encoder_rejects_invalid_in_memory_facts() -> None:
    with pytest.raises(ValueError):
        fact_to_dict(replace(_acquisition(), probability_min=float("nan")))


@pytest.mark.parametrize("version", [None, True, "1", 1.0, 0, PROVENANCE_SCHEMA_VERSION + 1])
def test_shared_schema_version_is_strict(version: object) -> None:
    with pytest.raises(ValueError):
        validate_provenance_schema_version(version)
    validate_provenance_schema_version(PROVENANCE_SCHEMA_VERSION)


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"schema_version": 1},
        {"schema_version": 1, "game_build_id": "", "input_digests": "{}"},
        {"schema_version": 1, "game_build_id": "build", "input_digests": "[]"},
        {"schema_version": 1, "game_build_id": "build", "input_digests": '{"items":"bad"}'},
        {"schema_version": 1, "game_build_id": "build", "input_digests": "{}", "future": True},
    ],
)
def test_metadata_rejects_invalid_contracts(metadata: object) -> None:
    with pytest.raises(ValueError):
        validate_provenance_metadata(metadata)


def test_metadata_accepts_shared_schema_and_real_digests() -> None:
    validate_provenance_metadata(
        {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "game_build_id": "build",
            "input_digests": json.dumps({"items": "a" * 64}),
        }
    )


def test_impossible_or_group_does_not_poison_a_possible_alternative() -> None:
    conditions = (
        ProvenanceCondition("unlock", 0, 0, "never"),
        ProvenanceCondition("unlock", 1, 0, "quest_done", "quest:one"),
    )
    assert conditions_satisfiable(conditions)
    assert is_actionable_acquisition(replace(_acquisition(), conditions=conditions))


def test_every_or_group_must_be_impossible_before_gate_fails() -> None:
    conditions = (
        ProvenanceCondition("unlock", 0, 0, "never"),
        ProvenanceCondition("unlock", 1, 0, "actor_level", actor="player", minimum=20),
        ProvenanceCondition("unlock", 1, 1, "actor_level", actor="player", maximum=10),
    )
    assert not conditions_satisfiable(conditions)


def test_and_gates_must_have_a_compatible_choice() -> None:
    conditions = (
        ProvenanceCondition("activate", 0, 0, "quest_done", "quest:one"),
        ProvenanceCondition("stop", 0, 0, "quest_not_done", "quest:one"),
        ProvenanceCondition("stop", 1, 0, "quest_done", "quest:two"),
    )
    assert conditions_satisfiable(conditions)
    assert not conditions_satisfiable(conditions[:2])


def test_numeric_bounds_respect_open_endpoints_and_actor_scope() -> None:
    lower = ProvenanceCondition("lower", 0, 0, "actor_level", actor="player", minimum=10, minimum_inclusive=False)
    upper = ProvenanceCondition("upper", 0, 0, "actor_level", actor="player", maximum=10)
    assert not conditions_satisfiable((lower, upper))
    assert conditions_satisfiable((replace(lower, minimum_inclusive=True), upper))
    assert conditions_satisfiable((lower, replace(upper, actor="sim")))


def test_source_and_location_conditions_must_be_compatible() -> None:
    fact = replace(
        _acquisition(),
        conditions=(ProvenanceCondition("source", 0, 0, "quest_done", "quest:one"),),
        locations=(
            ProvenanceLocation(
                "placement", "unlocated", conditions=(ProvenanceCondition("stop", 0, 0, "quest_not_done", "quest:one"),)
            ),
        ),
    )
    assert not is_actionable_acquisition(fact)
    possible = ProvenanceLocation("other", "unlocated")
    assert is_actionable_acquisition(replace(fact, locations=(*fact.locations, possible)))


@pytest.mark.parametrize(
    "fact",
    [
        ItemUse("use:one", "item:one", "item:target", "crafting_material"),
        ItemDisposition("item:one", "current"),
    ],
)
def test_nonacquisition_facts_reject_every_missing_or_unknown_dimension(fact: ItemUse | ItemDisposition) -> None:
    for field in fields(fact):
        data = asdict(fact)
        del data[field.name]
        with pytest.raises(ValueError):
            fact_from_dict(data)
    data = asdict(fact)
    data["future_mandatory_field"] = "unsupported"
    with pytest.raises(ValueError):
        fact_from_dict(data)


@pytest.mark.parametrize("family", ["conditions", "locations", "evidence"])
def test_child_codecs_reject_every_lost_dimension(family: str) -> None:
    original = asdict(_acquisition())
    for field in original[family][0]:
        data = asdict(_acquisition())
        child = dict(data[family][0])
        del child[field]
        data[family] = [child]
        with pytest.raises(ValueError):
            fact_from_dict(data)


def test_item_ownership_contradictions_respect_or_alternatives() -> None:
    held = ProvenanceCondition(
        "ownership",
        0,
        0,
        "item_held",
        "item:key",
        value="stored_slots_and_equipment_slots",
    )
    absent = ProvenanceCondition(
        "ownership",
        0,
        1,
        "item_not_owned",
        "item:key",
        value="stored_slots_and_equipment_slots",
    )
    possible = ProvenanceCondition("ownership", 1, 0, "item_held", "item:other")
    assert not conditions_satisfiable((held, absent))
    assert conditions_satisfiable((held, absent, possible))


def test_placement_scope_does_not_hide_global_player_state_contradictions() -> None:
    source = ProvenanceCondition("source", 0, 0, "quest_done", "quest:one")
    placement = ProvenanceCondition("placement", 0, 0, "quest_not_done", "quest:one", scope="placement:one")
    assert not conditions_satisfiable((source, placement))


@pytest.mark.parametrize("predicate", ["item_held", "key_held"])
def test_unlock_item_checks_do_not_conflict_with_inventory_only_absence(predicate: str) -> None:
    unlock = ProvenanceCondition("door", 0, 0, predicate, "item:key")
    absent = ProvenanceCondition(
        "loot",
        0,
        0,
        "item_not_owned",
        "item:key",
        value="stored_slots_and_equipment_slots",
    )
    assert conditions_satisfiable((unlock, absent))
    assert conditions_satisfiable((replace(unlock, value="keyring"), absent))


def test_inventory_membership_scope_survives_codec_roundtrip() -> None:
    condition = ProvenanceCondition(
        "not_owned",
        0,
        0,
        "item_not_owned",
        "item:key",
        value="stored_slots_and_equipment_slots",
    )
    fact = replace(_acquisition(), conditions=(condition,))
    assert fact_from_dict(json.loads(json.dumps(fact_to_dict(fact)))) == fact


def test_quantity_fixed_alias_is_rejected_even_with_equal_bounds() -> None:
    data = asdict(replace(_acquisition(), quantity_min=2, quantity_max=2, quantity_kind="exact"))
    data["quantity_kind"] = "fixed"
    with pytest.raises(ValueError, match="Unsupported provenance value"):
        fact_from_dict(data)


@pytest.mark.parametrize("phase", CONDITION_PHASES)
def test_condition_phase_is_lossless_and_mandatory(phase: ConditionPhase) -> None:
    original = _acquisition()
    condition = replace(original.conditions[0], phase=phase)
    fact = replace(original, conditions=(condition,))
    data = json.loads(json.dumps(fact_to_dict(fact)))
    assert fact_from_dict(data) == fact
    del data["conditions"][0]["phase"]
    with pytest.raises(ValueError, match="missing fields"):
        fact_from_dict(data)


def test_unknown_condition_phase_is_rejected() -> None:
    data = asdict(_acquisition())
    condition = dict(data["conditions"][0])
    condition["phase"] = "unknown_execution_phase"
    data["conditions"] = [condition]
    with pytest.raises(ValueError, match="Unsupported provenance value"):
        fact_from_dict(data)


def test_initial_absence_and_current_item_possession_are_compatible() -> None:
    initial = ProvenanceCondition(
        "membership",
        0,
        0,
        "item_not_owned",
        "item:key",
        value="stored_slots_and_equipment_slots",
        phase="source_initialization",
    )
    current = ProvenanceCondition(
        "membership",
        0,
        0,
        "item_held",
        "item:key",
        value="stored_slots_and_equipment_slots",
        phase="operation_input",
    )
    assert conditions_satisfiable((initial, current))
    assert not conditions_satisfiable((replace(initial, phase="availability"), current))


def test_availability_and_operation_input_share_current_quest_state() -> None:
    available = ProvenanceCondition("world", 0, 0, "quest_not_done", "quest:one")
    turnin = ProvenanceCondition("input", 0, 0, "quest_done", "quest:one", phase="operation_input")
    assert not conditions_satisfiable((available, turnin))
    assert conditions_satisfiable((available, replace(turnin, phase="operation_outcome")))


def test_input_quality_and_outcome_quality_have_distinct_state_contexts() -> None:
    before = ProvenanceCondition("quality", 0, 0, "quality", minimum=2, maximum=3, phase="operation_input")
    after = ProvenanceCondition("quality", 0, 0, "quality", minimum=0, maximum=0, phase="operation_outcome")
    assert conditions_satisfiable((before, after))
    assert not conditions_satisfiable((before, replace(after, phase="availability")))


def test_condition_identity_includes_execution_phase() -> None:
    initial = ProvenanceCondition(
        "membership",
        0,
        0,
        "item_not_owned",
        "item:key",
        phase="source_initialization",
    )
    current = replace(initial, predicate="item_held", phase="operation_input")
    fact = replace(_acquisition(), conditions=(initial, current))
    assert fact_from_dict(json.loads(json.dumps(fact_to_dict(fact)))) == fact


@pytest.mark.parametrize("minimum,maximum", [(1, None), (None, 5)])
def test_one_sided_bounded_quantities_are_lossless(minimum: float | None, maximum: float | None) -> None:
    acquisition = replace(
        _acquisition(),
        quantity_kind="bounded",
        quantity_min=minimum,
        quantity_max=maximum,
    )
    use = ItemUse(
        "use:quantity",
        "item:one",
        "item:target",
        "quality_offering",
        quantity_kind="bounded",
        quantity_min=minimum,
        quantity_max=maximum,
    )
    for fact in (acquisition, use):
        assert fact_from_dict(json.loads(json.dumps(fact_to_dict(fact)))) == fact


def test_bounded_quantities_require_at_least_one_known_endpoint() -> None:
    acquisition = replace(_acquisition(), quantity_kind="bounded", quantity_min=None, quantity_max=None)
    use = ItemUse("use:quantity", "item:one", "item:target", "quality_offering", quantity_kind="bounded")
    for fact in (acquisition, use):
        with pytest.raises(ValueError, match="at least one numeric bound"):
            fact_to_dict(fact)


@pytest.mark.parametrize("minimum,maximum", [(1, None), (None, 5), (None, None)])
def test_bounded_probabilities_still_require_both_endpoints(
    minimum: float | None,
    maximum: float | None,
) -> None:
    fact = replace(
        _acquisition(),
        probability_kind="bounded",
        probability_min=minimum,
        probability_max=maximum,
    )
    with pytest.raises(ValueError, match="both numeric bounds"):
        fact_to_dict(fact)


@pytest.mark.parametrize("phase", ["availability", "operation_outcome"])
@pytest.mark.parametrize("value", ["true", "false"])
def test_account_claim_state_roundtrips_losslessly(phase: ConditionPhase, value: str) -> None:
    condition = ProvenanceCondition(
        "account_claim",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value=value,
        scope="placement:reliquary",
        phase=phase,
    )
    fact = replace(_acquisition(), conditions=(condition,))
    assert fact_from_dict(json.loads(json.dumps(fact_to_dict(fact)))) == fact


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor", None),
        ("actor", "player"),
        ("actor", "sim"),
        ("reference_stable_key", None),
        ("reference_stable_key", "quest:reliquary_claimed"),
        ("reference_stable_key", "account_state:unknown_state"),
        ("value", None),
        ("value", True),
        ("value", "True"),
        ("value", "claimed"),
        ("phase", "source_initialization"),
        ("phase", "operation_input"),
        ("phase", "mechanic_parameter"),
    ],
)
def test_account_claim_state_rejects_malformed_typed_dimensions(field: str, value: object) -> None:
    condition = ProvenanceCondition(
        "account_claim",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="false",
        scope="placement:reliquary",
    )
    data = asdict(replace(_acquisition(), conditions=(condition,)))
    child = dict(data["conditions"][0])
    child[field] = value
    data["conditions"] = [child]
    with pytest.raises(ValueError):
        fact_from_dict(data)


def test_account_claim_state_rejects_opposite_current_values_across_location_scopes() -> None:
    unclaimed = ProvenanceCondition(
        "availability",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="false",
        scope="placement:reliquary",
    )
    claimed = replace(unclaimed, gate_key="other_gate", value="true", scope="source")
    assert not conditions_satisfiable((unclaimed, claimed))
    assert conditions_satisfiable((unclaimed, replace(claimed, phase="operation_outcome")))
    assert is_actionable_acquisition(
        replace(
            _acquisition(),
            conditions=(unclaimed, replace(claimed, phase="operation_outcome")),
        )
    )


def test_account_claim_state_keeps_viable_or_groups() -> None:
    unclaimed = ProvenanceCondition(
        "claim",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="false",
    )
    claimed = replace(unclaimed, atom_index=1, value="true")
    alternative = replace(unclaimed, group_index=1)
    assert not conditions_satisfiable((unclaimed, claimed))
    assert conditions_satisfiable((unclaimed, claimed, alternative))


def test_account_claim_state_is_not_a_quest_completion_alias() -> None:
    unclaimed = ProvenanceCondition(
        "account_claim",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="false",
    )
    quest = ProvenanceCondition("quest", 0, 0, "quest_done", "quest:reliquary")
    assert conditions_satisfiable((unclaimed, quest))
